#!/usr/bin/env python3
from __future__ import annotations
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'vendor/nexmind-god-mode-p8/src'))
from nexmind_god_mode.final_producer_contracts import CRAFT_DIMENSIONS,TASTE_DIMENSIONS,HARD_GATE_DIMENSIONS
from nexmind_god_mode.studio_quality import studio_autonomous_quality_gate,build_repair_request

def dim(score=9.7,why='strong'):
    return {'score':score,'confidence':'HIGH','rationale':why}
def review():
    return {
      'verdict':'ACCEPT',
      'hard_gates':[{'dimension':d,'status':'PASS','code':'OK','evidence':['encoded evidence']} for d in sorted(HARD_GATE_DIMENSIONS)],
      'craft_scores':{d:dim() for d in CRAFT_DIMENSIONS},
      'taste_judgments':{d:dim() for d in TASTE_DIMENSIONS},
      'divergence':{'novelty':9.2,'conceptual_risk':6.0,'template_similarity':1.0,'rationale':'distinctive'},
      'uncertainty':{'confidence':'HIGH','reasons':[],'human_review_required':False,'multimodal_evidence_complete':True},
      'strengths':['clean execution'],'issues':[],'revision_plan':[],'commercial_recommendation':'MACHINE_ACCEPT_HUMAN_REVIEW_REQUIRED'
    }

def fail_gate(r,dimension):
    for g in r['hard_gates']:
        if g['dimension']==dimension:g['status']='FAIL';g['code']='NEGATIVE_CONTROL';g['evidence']=['control deliberately violates this dimension'];break

def run(control):
    r=review(); cid=control['id']
    if cid=='NC01': r['taste_judgments']['engagement_memorability']=dim(6.0,'polished but boring and forgettable')
    elif cid=='NC02': fail_gate(r,'STORY_COHERENCE')
    elif cid=='NC03': r['taste_judgments']['authorship_specificity']=dim(5.8,'generic and transferable')
    elif cid=='NC04': r['taste_judgments']['reference_independence']=dim(4.5,'derivative of reference language')
    elif cid=='NC05': r['taste_judgments']['emotional_resonance']=dim(5.5,'emotionally mismatched to brief')
    elif cid=='NC06': r['craft_scores']['final_payoff']=dim(6.0,'opening promises more than payoff delivers')
    elif cid=='NC07': r['craft_scores']['art_craft']=dim(6.0,'art execution below commercial bar')
    elif cid=='NC08': r['taste_judgments']['aesthetic_coherence']=dim(6.2,'environment is under-authored and spatially thin')
    elif cid=='NC09': r['divergence']['template_similarity']=8.5;r['divergence']['rationale']='reuses a familiar production template'
    elif cid=='NC10': r['taste_judgments']['contextual_appropriateness']=dim(6.0,'visual language does not fit the brand/context')
    q=studio_autonomous_quality_gate(r,calibration={'status':'CALIBRATED'},multimodal_evidence={'status':'COMPLETE','perceptually_reviewed':True})
    repair=build_repair_request(r,q,round_number=1)
    return {'id':cid,'class':control['class'],'status':q['status'],'reasons':q['reasons'],'repair_scope':repair['escalation_scope'],'invalidate_slots':repair['invalidate_slots'],'pass':q['status']=='REPAIR' and repair['production_disposition']=='CONTINUE_REPLANNING' and repair['quality_floor_may_weaken'] is False}

spec=json.loads((ROOT/'evaluations/nexmind-p8-commercial-brain-v2/CREATIVE_NEGATIVE_CONTROLS_V3.json').read_text())
results=[run(x) for x in spec['controls']]
out={'schema':'NexMindP8CreativeNegativeControlsPolicyQAV3','status':'PASS' if all(x['pass'] for x in results) else 'FAIL','passed':sum(x['pass'] for x in results),'total':len(results),'commercial_score_evidence':False,'results':results}
(ROOT/'reports/P8_CREATIVE_NEGATIVE_CONTROLS_QA_V3.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2));raise SystemExit(0 if out['status']=='PASS' else 1)
