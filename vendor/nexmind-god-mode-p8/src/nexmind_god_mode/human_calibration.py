from __future__ import annotations
import hashlib, math
from copy import deepcopy
from typing import Any, Dict
from .final_producer_contracts import validate_human_review, human_review_gate

MACHINE_HUMAN_MAP = {
    "story_clarity": (("craft_scores", "story_clarity"),),
    "visual_communication": (("craft_scores", "visual_communication"),),
    "illustration_art_quality": (("craft_scores", "art_craft"), ("taste_judgments", "illustration_quality")),
    "character_subject_storytelling": (("craft_scores", "visual_communication"), ("taste_judgments", "emotional_appropriateness")),
    "visual_hierarchy": (("craft_scores", "visual_hierarchy"),),
    "originality_appropriateness": (("taste_judgments", "originality"), ("taste_judgments", "contextual_appropriateness")),
    "continuity_transformation": (("craft_scores", "editorial_rhythm"), ("craft_scores", "motion_intentionality")),
    "motion_intentionality": (("craft_scores", "motion_intentionality"),),
    "cinematography": (("craft_scores", "cinematography"),),
    "editorial_rhythm": (("craft_scores", "editorial_rhythm"),),
    "sound_design": (("craft_scores", "sound_design"),),
    "beauty_composition_taste": (("taste_judgments", "beauty_composition"),),
    "charm_appeal": (("taste_judgments", "charm_appeal"),),
    "emotional_appropriateness": (("taste_judgments", "emotional_appropriateness"),),
    "final_payoff": (("craft_scores", "final_payoff"),),
    "commercial_believability": (("taste_judgments", "commercial_believability"),),
    "engagement_memorability": (("taste_judgments", "engagement_memorability"),),
    "authorship_specificity": (("taste_judgments", "authorship_specificity"),),
    "reference_independence": (("taste_judgments", "reference_independence"),),
    "aesthetic_coherence": (("taste_judgments", "aesthetic_coherence"),),
    "emotional_resonance": (("taste_judgments", "emotional_resonance"),),
}

class HumanCalibrationRegistry:
    SCHEMA="NexMindHumanCalibrationV3"
    MIN_REAL_REVIEWS=12
    AUTONOMY_MIN_REAL_REVIEWS=36
    AUTONOMY_MIN_DISTINCT_PRODUCTIONS=12
    AUTONOMY_MIN_DISTINCT_REVIEWERS=5
    MAX_REVIEWER_CONCENTRATION=.35
    HELD_OUT_FRACTION=.20
    MIN_MEAN_CORRELATION=.80
    MIN_DIM_CORRELATION=.60
    MAX_MEAN_ABSOLUTE_ERROR=.70
    MAX_DIM_ABSOLUTE_ERROR=1.00
    MAX_OPTIMISM_BIAS=.35

    def __init__(self, *, target_family:str|None=None, p8_build_hash:str|None=None, judge_ensemble_hash:str|None=None):
        self.records=[]
        self.target_family=str(target_family or '').upper() or None
        self.p8_build_hash=str(p8_build_hash or '') or None
        self.judge_ensemble_hash=str(judge_ensemble_hash or '') or None

    def add(self, production_id:str, machine_review:Dict[str,Any], human_review:Dict[str,Any], *, synthetic:bool=False, family:str|None=None, evidence_hash:str|None=None, p8_build_hash:str|None=None, judge_ensemble_hash:str|None=None):
        h=validate_human_review(human_review)
        self.records.append({'production_id':production_id,'family':str(family or '').upper() or None,'evidence_hash':str(evidence_hash or '') or None,'p8_build_hash':str(p8_build_hash or '') or None,'judge_ensemble_hash':str(judge_ensemble_hash or '') or None,'reviewer_id':str(h.get('reviewer_id') or ''),'machine_review':deepcopy(machine_review),'human_review':h,'human_gate':human_review_gate(h),'synthetic':bool(synthetic)})

    @staticmethod
    def _machine_score(review:Dict[str,Any], paths)->float|None:
        values=[]
        for group,name in paths:
            node=(review.get(group) or {}).get(name)
            if isinstance(node,dict) and isinstance(node.get('score'),(int,float)): values.append(float(node['score']))
        return sum(values)/len(values) if values else None

    @staticmethod
    def _rank(values):
        order=sorted(range(len(values)),key=lambda i:(values[i],i)); ranks=[0.0]*len(values);i=0
        while i<len(order):
            j=i+1
            while j<len(order) and values[order[j]]==values[order[i]]: j+=1
            r=(i+j-1)/2+1
            for k in range(i,j): ranks[order[k]]=r
            i=j
        return ranks

    @classmethod
    def _spearman(cls,a,b):
        if len(a)!=len(b) or len(a)<3:return 0.0
        ra,rb=cls._rank(a),cls._rank(b);ma=sum(ra)/len(ra);mb=sum(rb)/len(rb)
        num=sum((x-ma)*(y-mb) for x,y in zip(ra,rb));da=math.sqrt(sum((x-ma)**2 for x in ra));db=math.sqrt(sum((y-mb)**2 for y in rb))
        return num/(da*db) if da and db else 0.0

    @staticmethod
    def _held_out(record):
        key=f"{record.get('production_id')}:{record.get('evidence_hash')}:{record.get('reviewer_id')}"
        bucket=int(hashlib.sha256(key.encode()).hexdigest()[:8],16)%100
        return bucket < 20

    def status(self)->Dict[str,Any]:
        reasons=[]
        if not self.target_family: reasons.append('TARGET_FAMILY_NOT_BOUND')
        if not self.p8_build_hash: reasons.append('P8_BUILD_HASH_NOT_BOUND')
        if not self.judge_ensemble_hash: reasons.append('JUDGE_ENSEMBLE_HASH_NOT_BOUND')
        real=[r for r in self.records if not r['synthetic']]
        exact=[r for r in real if (not self.target_family or r.get('family')==self.target_family) and (not self.p8_build_hash or r.get('p8_build_hash')==self.p8_build_hash) and (not self.judge_ensemble_hash or r.get('judge_ensemble_hash')==self.judge_ensemble_hash)]
        base={'schema':self.SCHEMA,'family':self.target_family,'p8_build_hash':self.p8_build_hash,'judge_ensemble_hash':self.judge_ensemble_hash,'human_reviews':len(exact),'total_unscoped_reviews':len(real),'minimum_required':self.MIN_REAL_REVIEWS,'autonomy_minimum_required':self.AUTONOMY_MIN_REAL_REVIEWS}
        if len(exact)<self.MIN_REAL_REVIEWS:
            return {'status':'INSUFFICIENT_HUMAN_CALIBRATION',**base,'metrics':{},'reasons':reasons+['FEWER_THAN_12_EXACT_BUILD_JUDGE_FAMILY_REVIEWS']}
        reviewers={r['reviewer_id'] for r in exact if r['reviewer_id']}; counts={rid:sum(1 for r in exact if r['reviewer_id']==rid) for rid in reviewers}; concentration=max(counts.values())/len(exact) if counts else 1.0
        if len(reviewers)<self.AUTONOMY_MIN_DISTINCT_REVIEWERS: reasons.append('DISTINCT_REVIEWER_FLOOR_NOT_MET')
        if concentration>self.MAX_REVIEWER_CONCENTRATION: reasons.append('REVIEWER_CONCENTRATION_TOO_HIGH')
        distinct=len({r['production_id'] for r in exact})
        if len(exact)<self.AUTONOMY_MIN_REAL_REVIEWS: reasons.append('AUTONOMY_SAMPLE_FLOOR_NOT_MET')
        if distinct<self.AUTONOMY_MIN_DISTINCT_PRODUCTIONS: reasons.append('DISTINCT_PRODUCTION_FLOOR_NOT_MET')
        false_accepts=sum(1 for r in exact if r['machine_review'].get('verdict')=='ACCEPT' and r['human_gate'].get('status')!='PASS')
        if false_accepts: reasons.append('MACHINE_FALSE_ACCEPT_PRESENT')
        held=[r for r in exact if self._held_out(r)]; train=[r for r in exact if not self._held_out(r)]
        # Deterministic split can be slightly uneven on small samples; fail closed if held-out evidence is too thin.
        minimum_held=max(3,math.floor(len(exact)*.15))
        if len(held)<minimum_held: reasons.append('HELD_OUT_SAMPLE_TOO_SMALL')
        dimensions=[d for d in MACHINE_HUMAN_MAP if not (d=='character_subject_storytelling' and self.target_family!='STICKMAN')]
        metrics={};usable_corr=[];maes=[];optimism=[]
        for dim in dimensions:
            mx=[];hy=[]
            for r in held:
                m=self._machine_score(r['machine_review'],MACHINE_HUMAN_MAP[dim]); score=(r['human_review'].get('scores') or {}).get(dim)
                if m is None or not isinstance(score,(int,float)): continue
                mx.append(m);hy.append(float(score))
            corr=round(self._spearman(mx,hy),4) if len(mx)>=3 else None
            mae=round(sum(abs(a-b) for a,b in zip(mx,hy))/len(mx),4) if mx else None
            bias=round(sum((a-b) for a,b in zip(mx,hy))/len(mx),4) if mx else None
            metrics[dim]={'spearman_rank_correlation':corr,'mae':mae,'machine_minus_human_bias':bias,'held_out_n':len(mx)}
            if isinstance(corr,float):usable_corr.append(corr)
            if isinstance(mae,float):maes.append(mae)
            if isinstance(bias,float):optimism.append(max(0.0,bias))
        mean_corr=round(sum(usable_corr)/len(usable_corr),4) if usable_corr else None;mean_mae=round(sum(maes)/len(maes),4) if maes else None;max_mae=max(maes) if maes else None;max_optimism=max(optimism) if optimism else None
        weak=[d for d,m in metrics.items() if m['spearman_rank_correlation'] is None or m['spearman_rank_correlation']<self.MIN_DIM_CORRELATION]
        if mean_corr is None or mean_corr<self.MIN_MEAN_CORRELATION:reasons.append('MEAN_SPEARMAN_CORRELATION_TOO_LOW')
        if weak:reasons.append('DIMENSION_SPEARMAN_CORRELATION_TOO_LOW')
        if mean_mae is None or mean_mae>self.MAX_MEAN_ABSOLUTE_ERROR:reasons.append('MEAN_ABSOLUTE_ERROR_TOO_HIGH')
        if max_mae is None or max_mae>self.MAX_DIM_ABSOLUTE_ERROR:reasons.append('DIMENSION_ABSOLUTE_ERROR_TOO_HIGH')
        if max_optimism is None or max_optimism>self.MAX_OPTIMISM_BIAS:reasons.append('MACHINE_OPTIMISM_BIAS_TOO_HIGH')
        held_false=sum(1 for r in held if r['machine_review'].get('verdict')=='ACCEPT' and r['human_gate'].get('status')!='PASS')
        return {'status':'CALIBRATED' if not reasons else 'CALIBRATION_WEAK',**base,'distinct_productions':distinct,'distinct_reviewers':len(reviewers),'reviewer_concentration':round(concentration,4),'training_reviews':len(train),'held_out_reviews':len(held),'metrics':metrics,'mean_spearman_rank_correlation':mean_corr,'mean_absolute_error':mean_mae,'max_dimension_absolute_error':max_mae,'max_machine_optimism_bias':max_optimism,'machine_false_accepts':false_accepts,'held_out_machine_false_accepts':held_false,'reasons':reasons}
