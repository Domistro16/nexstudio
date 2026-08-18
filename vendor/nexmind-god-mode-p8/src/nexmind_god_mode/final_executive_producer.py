from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List

from .final_critic_ensemble import FinalCriticEnsemble
from .final_producer_contracts import validate_final_producer_output

class FinalExecutiveProducer:
    """Independent final critic. It cannot repair or commit; it can only accept, reject, revise, or escalate."""
    def __init__(self, provider, ensemble:FinalCriticEnsemble|None=None):
        self.provider=provider;self.ensemble=ensemble or FinalCriticEnsemble()

    def review(self, production_id:str, brief:Dict[str,Any], story:Dict[str,Any], showrunner_state:Dict[str,Any], final_board:Dict[str,Any], *, multimodal_evidence:Dict[str,Any]|None=None, calibration:Dict[str,Any]|None=None)->Dict[str,Any]:
        hard=self.ensemble.evaluate(showrunner_state,final_board)
        request={
            'production_id':production_id,
            'brief':deepcopy(brief),
            'film_thesis':deepcopy(story.get('film_thesis',{})),
            'committed_decisions':deepcopy(showrunner_state.get('decisions',{})),
            'canonical_final_storyboard':deepcopy(final_board),
            'hard_gate_evidence':deepcopy(hard),
            'multimodal_evidence':deepcopy(multimodal_evidence or {'status':'MISSING','artifacts':[]}),
            'calibration':deepcopy(calibration or {'status':'INSUFFICIENT_HUMAN_CALIBRATION','human_reviews':0}),
            'instruction':{
                'role':'Independent Final Executive Producer / Creative Critic',
                'constitutional_rule':'You may reject work from every department, including Showrunner-selected work. You may not rewrite or commit it.',
                'evaluate_separately':[
                    'factual truth','story clarity','visual communication','art/craft','cinematography','editorial rhythm','motion physicality','sound function/rights','final payoff','commercial taste','originality/divergence','engagement/memorability','authorship specificity','reference independence','aesthetic coherence','emotional resonance','uncertainty'
                ],
                'department_revision_rule':'For every creative REVISE/REJECT issue, identify the responsible creative department, required change, what good work must be preserved, and priority. Do not assign technical provider/evidence availability as a creative department repair.',
                'creative_failure_law':'A film is not commercially acceptable merely because nothing is technically wrong. Boring, derivative, generic/template-like, aesthetically weak, emotionally flat/mismatched, under-authored environments, weak character performance, or a reference-dependent imitation MUST receive REVISE/REJECT and department-owned repairs.',
                'quality_target':'Judge against a 9.5-class senior commercial creative bar. ACCEPT requires elite work, not competence.',
                'calibration_boundary':'Human calibration is orchestration/release-policy telemetry. Judge the film itself here; do not alter the creative verdict solely because calibration is missing or weak. The autonomy gate evaluates calibration after the exact judge ensemble is resolved.',
                'forbidden':['single blended quality score','polite acceptance because mechanical QA passed','accepting a boring-but-valid film','accepting derivative/reference-copy work','accepting generic template-like work','invented human calibration','ignoring missing multimodal evidence','changing the creative verdict solely because calibration is unavailable'],
            }
        }
        review=validate_final_producer_output(self.provider.complete('final_producer',request))
        # Deterministic truth outranks model taste.
        failed=[g for g in hard if g['status']=='FAIL']
        if failed and review['verdict']=='ACCEPT':
            review=deepcopy(review);review['verdict']='REVISE';review['hard_gates']=deepcopy(hard);review['issues']=['HARD_GATE_FAILURE: '+','.join(g['dimension'] for g in failed),*review['issues']];review['revision_plan']=['Resolve hard-gate failures before final acceptance: '+','.join(g['dimension'] for g in failed),*review['revision_plan']];review['commercial_recommendation']='DO_NOT_RENDER'
        else:
            review=deepcopy(review);review['hard_gates']=deepcopy(hard)

        # The model's own dimensional judgment cannot be laundered by an ACCEPT
        # label. This is not a deterministic substitute for taste: the model still
        # supplies the taste assessment, while policy enforces the agreed 9.5 bar.
        craft={k:float(v.get('score',0.0)) for k,v in (review.get('craft_scores') or {}).items() if isinstance(v,dict)}
        taste={k:float(v.get('score',0.0)) for k,v in (review.get('taste_judgments') or {}).items() if isinstance(v,dict)}
        critical_craft={'story_clarity','visual_communication','art_craft','visual_hierarchy','final_payoff','commercial_finish'}
        critical_taste={'originality','contextual_appropriateness','commercial_believability','engagement_memorability','authorship_specificity','reference_independence','aesthetic_coherence','emotional_resonance'}
        low=[f'craft:{k}={v:.2f}' for k,v in craft.items() if v<9.0] + [f'taste:{k}={v:.2f}' for k,v in taste.items() if v<9.0]
        critical_low=[f'craft:{k}={craft.get(k,0.0):.2f}' for k in critical_craft if craft.get(k,0.0)<9.5] + [f'taste:{k}={taste.get(k,0.0):.2f}' for k in critical_taste if taste.get(k,0.0)<9.5]
        craft_mean=(sum(craft.values())/len(craft)) if craft else 0.0
        taste_mean=(sum(taste.values())/len(taste)) if taste else 0.0
        if review.get('verdict')=='ACCEPT' and (craft_mean<9.5 or taste_mean<9.5 or low or critical_low):
            review['verdict']='REVISE'
            review['issues']=[f'ELITE_QUALITY_FLOOR_NOT_MET: craft_mean={craft_mean:.2f}, taste_mean={taste_mean:.2f}', *critical_low, *low, *review.get('issues',[])]
            review['revision_plan']=['Re-author the responsible creative decisions until craft/taste mean >=9.5, every dimension >=9.0, and every critical dimension >=9.5. Do not lower the gate or substitute generic execution.', *review.get('revision_plan',[])]
            review['commercial_recommendation']='DO_NOT_RENDER'

        # Perceptual evidence belongs to this judge because it determines whether the
        # judge actually saw/heard the finished film. Human calibration does not.
        # The exact Final Producer + independent-auditor ensemble is not known until
        # both provider calls complete, so mutating the creative verdict here based on
        # a preliminary calibration lookup creates a circular/stale authority. The
        # orchestration-level autonomy gate evaluates calibration after the ensemble
        # identity has been resolved and can then require human review without
        # contaminating this film-specific creative judgment.
        mm=(multimodal_evidence or {}).get('status')=='COMPLETE'
        review['uncertainty']['multimodal_evidence_complete']=bool(mm)
        return validate_final_producer_output(review)
