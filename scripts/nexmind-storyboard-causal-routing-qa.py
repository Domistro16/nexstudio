#!/usr/bin/env python3
from __future__ import annotations
import copy,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SERVICE=ROOT/'services'/'studio-nexmind-p8'
P8=ROOT/'vendor'/'nexmind-god-mode-p8'/'src'
sys.path.insert(0,str(SERVICE));sys.path.insert(0,str(P8))
import orchestrator as o
from nexmind_god_mode.p3_producer import P3ExecutiveProducer

checks=[]
def check(name,ok,detail=''):
    checks.append({'name':name,'pass':bool(ok),'detail':str(detail or '')})

def story():
    return {'film_thesis':{'central_argument':'One precise decision protects a human moment.','film_kind':'30-second explainer','audience_before':'heat is a setting','audience_after':'heat is useful judgment','hero_kind':'cook and pan','camera_idea':'observe the causal cooking decision','emotional_trajectory':['tension','relief'],'visual_trajectory':['problem','proof'],'opening_contract':'Open on one cooking problem.','final_payoff':'End on the resolved human consequence.','anti_goals':['no feature list']},'beats':[]}

ordinary={
 'verdict':'REVISE','commercial_confidence':'MEDIUM','strengths':[],
 'issues':[{'severity':'MAJOR','area':'Film thesis and payoff','finding':'The key states do not visibly serve the Film Thesis or make the payoff legible.','required_change':'Strengthen the visual realization of the hero transformation.'}],
 'revision_brief':'Make the visual escalation and payoff serve the accepted narrative thesis.'
}
owner=o._key_storyboard_review_owner(ordinary)
check('Storyboard thesis/payoff language does not reopen accepted Story',owner in {'VISUAL_CONCEPT','ART_DIRECTION'},owner)
check('Storyboard thesis/payoff realization routes to Visual Concept',owner=='VISUAL_CONCEPT',owner)

claimed=copy.deepcopy(ordinary)
claimed['issues'][0]['owner_department']='STORY'
claimed['issues'][0]['code']='WEAK_STORYBOARD_PAYOFF'
check('Uncertified STORY owner claim is ignored',o._key_storyboard_review_owner(claimed)!='STORY',o._key_storyboard_review_owner(claimed))

certified={
 'verdict':'REVISE','commercial_confidence':'LOW','strengths':[],
 'issues':[{'code':'STORY_INTERNAL_CONTRADICTION','owner_department':'STORY','severity':'MAJOR','finding':'The accepted Story puts the same causal state in mutually incompatible conditions.','required_change':'Repair the Story contradiction itself.'}],
 'revision_brief':'Repair the internal Story contradiction.'
}
check('Certified internal Story contradiction may reopen Story',o._key_storyboard_review_owner(certified)=='STORY',o._key_storyboard_review_owner(certified))
check('Generic deterministic storyboard failure routes to Visual Concept',o._key_storyboard_review_owner({'issues':[{'code':'GENERIC_STORYBOARD','beat_id':'B1'}]})=='VISUAL_CONCEPT')
check('Weak settled state routes to Art Direction',o._key_storyboard_review_owner({'issues':[{'code':'WEAK_SETTLED_STATE','beat_id':'B1'}]})=='ART_DIRECTION')

class Capture:
    def __init__(self): self.request=None
    def complete(self,task,request):
        self.request=copy.deepcopy(request)
        return {'verdict':'ACCEPT','issues':[],'strengths':['clear'],'revision_brief':'','commercial_confidence':'HIGH'}
cap=Capture();P3ExecutiveProducer(cap).review_storyboard('qa',{},story(),{'visual_thesis':'v'},{'art_thesis':'a'},{'beats':[]},{'status':'PASS'})
law=' '.join((cap.request.get('instruction') or {}).get('causal_owner_law') or [])
check('Storyboard Producer prompt protects accepted Story by default','Do not reopen STORY merely because' in law and 'STORY_INTERNAL_CONTRADICTION' in law,law)

status='PASS' if all(x['pass'] for x in checks) else 'FAIL'
out={'schema':'NexMindStoryboardCausalRoutingQAV1','status':status,'passed':sum(x['pass'] for x in checks),'total':len(checks),'failed':[x for x in checks if not x['pass']],'checks':checks,'law':'ACCEPTED_STORY_STICKY_AT_KEY_STORYBOARD__EXPLICIT_STORY_CONTRADICTION_REQUIRED'}
print(json.dumps(out,indent=2,ensure_ascii=False))
raise SystemExit(0 if status=='PASS' else 1)
