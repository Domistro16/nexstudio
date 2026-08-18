#!/usr/bin/env python3
from __future__ import annotations
import copy,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SERVICE=ROOT/'services'/'studio-nexmind-p8'
P8=ROOT/'vendor'/'nexmind-god-mode-p8'/'src'
sys.path.insert(0,str(SERVICE));sys.path.insert(0,str(P8))
import orchestrator as o
from nexmind_god_mode.story_director import StoryDirector
from nexmind_god_mode.executive_producer import ExecutiveProducer
from nexmind_god_mode.contracts import ContractViolation
from nexmind_god_mode.showrunner_p8 import NexMindSupremeShowrunnerP8

checks=[]
def check(name,ok,detail=''):
    checks.append({'name':name,'pass':bool(ok),'detail':str(detail or '')})

def story(argument='One heat decision protects a human moment.'):
    return {
      'film_thesis':{
        'central_argument':argument,'film_kind':'30-second human explainer','audience_before':'heat is a setting','audience_after':'heat is useful judgment','hero_kind':'cook and pan','camera_idea':'observe the causal cooking decision','emotional_trajectory':['tension','relief'],'visual_trajectory':['problem','proof'],'opening_contract':'Open on one cooking problem.','final_payoff':'End on the resolved human consequence.','anti_goals':['no feature list']},
      'beats':[
        {'beat_id':'B1','purpose':'problem','question':'what changes?','audience_before':'uncertain','audience_after':'sees need','hero_state':'food approaches a difficult state','reveal':'one small decision matters','required_claim_ids':['C1'],'narration_mode':'SILENT','narration_text':'','narration_purpose':''},
        {'beat_id':'B2','purpose':'payoff','question':'why useful?','audience_before':'sees decision','audience_after':'understands benefit','hero_state':'food settles into the intended state','reveal':'the cook can return attention elsewhere','required_claim_ids':['C1'],'narration_mode':'SILENT','narration_text':'','narration_purpose':''},
      ]}

# 1. Nested competition must be a contract failure, not a Producer taste argument.
try:
    StoryDirector._enforce_single_strategy_candidate(story('Three materially different routes were compared; the restored-attention route is selected because it is strongest.'))
    nested_rejected=False
except ContractViolation:
    nested_rejected=True
check('Story candidate cannot contain nested strategy competition',nested_rejected)
try:
    StoryDirector._enforce_single_strategy_candidate(story())
    one_ok=True
except ContractViolation:
    one_ok=False
check('One committed Story strategy remains valid',one_ok)

# 2. Candidate generation prompt must make outer competition authoritative.
class CaptureProvider:
    def __init__(self): self.requests=[]; self.i=0
    def complete(self,task,request):
        self.requests.append((task,copy.deepcopy(request)));self.i+=1
        s=story(f'Film {self.i}: one complete causal strategy about precise heat and human usefulness.')
        return s
cap=CaptureProvider(); sd=StoryDirector(cap)
brief={'topic':'portable induction cooktop','goal':'make precise heat human','duration_s':30,'family':'EXPLAINER'}
evidence=[{'claim_id':'C1','claim':'precise heat control','source':'user','status':'USER_SUPPLIED'}]
out=sd.propose_candidates('qa',brief,evidence,{})
check('Simple B01 Story competition produces two outer candidates',len(out)==2,len(out))
reqs=[r for t,r in cap.requests if t=='story']
check('Every Story request declares ONE_CANDIDATE_EQUALS_ONE_FILM',all((r.get('instruction') or {}).get('competition_law','').startswith('ONE_CANDIDATE_EQUALS_ONE_FILM') for r in reqs))
check('Second candidate sees prior strategy only as negative anti-repetition context',bool(reqs[1].get('candidate_competition_context',{}).get('prior_candidate_signatures')) and 'negative-only' in reqs[1]['candidate_competition_context']['law'])

# 3. Repair context must be anchor-scoped rather than merge unrelated candidate criticism.
reviewed=[
 {'candidate':{'candidate_id':'A','visual_thesis':'a','hero_kind':'h','transformation':'x'},'review':{'verdict':'REVISE','commercial_confidence':'HIGH','issues':[{'severity':'MODERATE','area':'A','required_change':'Fix A only.'}],'strengths':['A strength'],'revision_brief':'Fix A only.'}},
 {'candidate':{'candidate_id':'B','visual_thesis':'b','hero_kind':'h','transformation':'y'},'review':{'verdict':'REJECT','commercial_confidence':'LOW','issues':[{'severity':'MAJOR','area':'B1','required_change':'Fix B1.'},{'severity':'MAJOR','area':'B2','required_change':'Fix B2.'}],'strengths':['B strength'],'revision_brief':'Fix B.'}},
]
ctx=o._reviews_context(reviewed)
check('Surgical repair context uses strongest rejected candidate A',ctx.get('previous_output',{}).get('candidate_id')=='A',ctx.get('previous_output'))
check('Anchor A receives only its own active Producer issue',len(ctx.get('issues') or [])==1 and o._required_change_text(ctx['issues'][0])=='Fix A only.',ctx.get('issues'))
check('Other rejected candidates remain diagnostic, not binding',len(ctx.get('rejected_candidates') or [])==2 and sum(1 for x in ctx['rejected_candidates'] if x.get('binding_to_repair_anchor'))==1)

# 4. Full Story restart must be clean and must not preserve rejected inventions.
rr={
 'round':1,'owner_department':'STORY','source_department':'STORY','quality_reasons':['LOCAL_CREATIVE_LINEAGE_EXHAUSTED'],
 'issues':[{'required_change':'Preserve the plate, basil, receipt and pendant while changing the strategy.'}],
 'revision_plan':['Keep the plate and receipt.'],
 'cumulative_lifetime_attempts':{'STORY':4,'VISUAL_CONCEPT':3},
 'rejected_candidates':[{'candidate':{'story_signature':{'central_argument':'old plate story','hero_kind':'plate','opening_contract':'companion holds plate','final_payoff':'receipt by plate'}}}],
}
nxt=o._next_broader_strategy_request({'productionId':'qa','broaderStrategyMaxRounds':3},rr,'STORY')
rctx=nxt['request']['autonomousRepairContext']
check('Full Story restart removes previous_output repair anchor',rctx.get('previous_output') is None)
check('Full Story restart clears sticky rejected-device requirements',rctx.get('sticky_requirements')==[],rctx.get('sticky_requirements'))
serialized=json.dumps({'issues':rctx.get('issues'),'revision_plan':rctx.get('revision_plan'),'strengths':rctx.get('strengths_to_preserve')},ensure_ascii=False).lower()
check('Rejected plate/basil/receipt instructions are not carried as positive restart requirements',all(x not in serialized for x in ('basil','receipt','pendant','preserve the plate')),serialized)
check('Exhausted Story remains available only as negative anti-repetition signature',bool(rctx.get('exhausted_strategy_signatures')) and 'plate' in json.dumps(rctx['exhausted_strategy_signatures']).lower())
check('Full restart preserves cumulative lifetime attempt telemetry',rctx.get('cumulative_lifetime_attempts',{}).get('STORY')==4,rctx.get('cumulative_lifetime_attempts'))

# 5. Internal repair history must not inflate simple B01 candidate count.
long_internal=copy.deepcopy(brief);long_internal['autonomous_revision_context']={'issues':['x'*6000],'sticky_requirements':['y'*6000]}
check('Long internal repair context does not inflate 30s Story candidate count',StoryDirector._candidate_target(long_internal,evidence)==2,StoryDirector._candidate_target(long_internal,evidence))

# 6. Story Producer gate must be Story-specific and not require Visual-owned premium fields.
class ProducerCapture:
    def __init__(self): self.request=None
    def complete(self,task,request):
        self.request=copy.deepcopy(request)
        return {'verdict':'ACCEPT','issues':[],'strengths':['clear story'],'revision_brief':'','commercial_confidence':'HIGH'}
pc=ProducerCapture(); ep=ExecutiveProducer(pc)
st=story();cand={'candidate_id':'S','representation':'NARRATIVE_ARGUMENT','visual_thesis':st['film_thesis']['central_argument'],'hero_kind':'cook','transformation':'before -> after','camera_idea':'observe decision','rationale':'earned payoff','beat_treatments':[{'beat_id':'B1','hero_state':'x','visual_action':'y','audience_takeaway':'z enough meaning'}]}
ep.review('qa',{'topic':'x','autonomous_revision_context':{'previous_output':{'huge':'x'*10000},'issues':[{'required_change':'fix'}]}},st,cand,editable_contract={'owner_department':'STORY','editable_fields':['film_thesis.central_argument'],'boundary':'story'})
questions=' '.join(pc.request['instruction']['questions']).lower()
check('Producer uses STORY review scope for Story',pc.request['instruction'].get('review_scope')=='STORY')
check('Story Producer explicitly leaves visual premium fields downstream',all(x in questions for x in ('do not demand concept_signature','rehearsal_states','memorability_device','originality_guard')))
check('Producer request strips heavy previous_output from embedded brief', 'autonomous_revision_context' not in pc.request['brief'])
check('Producer receives compact active revision context instead',pc.request.get('revision_context',{}).get('issues')==[{'required_change':'fix'}],pc.request.get('revision_context'))

# 7. New full-run state must import cumulative lifetime attempt counts.
sr=NexMindSupremeShowrunnerP8('qa',{'topic':'x','autonomous_revision_context':{'round':2,'cumulative_lifetime_attempts':{'STORY':6,'VISUAL_CONCEPT':3}}})
o._ensure_repair_state(sr,{'STORY':2,'VISUAL_CONCEPT':3,'ART_DIRECTION':3,'CINEMATOGRAPHY':2,'EDITORIAL_RHYTHM':2,'MOTION_PERFORMANCE':3,'SOUND_DIRECTION':2})
check('Fresh Story lineage imports cumulative lifetime attempts',sr.state['autonomous_creative_repair']['lifetime_attempts'].get('STORY')==6,sr.state['autonomous_creative_repair']['lifetime_attempts'])
check('Fresh Story lineage tracks global broader round',sr.state['autonomous_creative_repair'].get('global_broader_round')==2,sr.state['autonomous_creative_repair'].get('global_broader_round'))

status='PASS' if all(x['pass'] for x in checks) else 'FAIL'
out={'schema':'NexMindStoryGovernanceQAV1','status':status,'passed':sum(x['pass'] for x in checks),'total':len(checks),'failed':[x for x in checks if not x['pass']],'checks':checks,'law':'OUTER_COUNCIL_OWNS_COMPETITION__ONE_STORY_CANDIDATE_ONE_FILM__ANCHOR_SCOPED_REPAIR__CLEAN_STORY_RESTART__STORY_PRODUCER_BOUNDARY'}
print(json.dumps(out,indent=2,ensure_ascii=False))
raise SystemExit(0 if status=='PASS' else 1)
