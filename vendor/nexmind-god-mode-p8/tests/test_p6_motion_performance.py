import copy, json, pathlib, subprocess, sys, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from nexmind_god_mode.motion_contracts import validate_motion_output, validate_motion_candidate
from nexmind_god_mode.performer_capabilities import PerformerCapabilityRegistry
from nexmind_god_mode.motion_director import MotionPerformanceDirector
from nexmind_god_mode.p6_producer import MotionExecutiveProducer
from nexmind_god_mode.p6_showrunner_reasoner import MotionShowrunnerDecisionIntelligence
from nexmind_god_mode.showrunner_p6 import NexMindSupremeShowrunnerP6
from nexmind_god_mode.council_p6 import CreativeCouncilP6
from nexmind_god_mode.storyboard_compiler_v3 import PerformanceStoryboardCompiler
from nexmind_god_mode.contracts import ContractViolation
from nexmind_god_mode.p0_kernel import AuthorityViolation
from nexmind_god_mode.showrunner_p2 import ProducerGateError

BEATS={'B1','B2','B3'}
def action(i,b,verb,perf='STICKMAN_V2',req=None,goal='COMMUNICATE_ACTION',fallback='FAIL_CLOSED',dep=None,contact='NONE',before='UNCHANGED',after='UNCHANGED',overlap='MAY_OVERLAP'):
    return {'action_id':f'A{i}','beat_id':b,'actor':'actor-1','semantic_action':goal,'requested_verb':verb,'performer_class':perf,'target':'target-1','prop':'prop-1','semantic_goal':goal,'causal_role':'meaning-bearing change','dependencies':dep or [],'overlap_policy':overlap,'anticipation':'only if useful','contact_requirement':contact,'ownership_before':before,'ownership_after':after,'settle':'clear settled pose/state','reduced_motion':'preserve semantic state','fallback_policy':fallback,'available_requirements':req or [],'motivation':'show the causal state change clearly'}

def candidate(cid,variant=1):
    if variant==1:
        acts=[action(1,'B1','SIT',req=['seat_anchor'],contact='SEAT_CONTACT',overlap='SERIAL_REQUIRED'),action(2,'B2','PICKUP',req=['grip_frame','support_state'],contact='GRIP_CONTACT',before='WORLD',after='ACTOR',overlap='SERIAL_REQUIRED'),action(3,'B3','HANDOFF_DIRECT',req=['support_surface','grip_frame'],goal='TRANSFER_OWNERSHIP',fallback='ALLOW_SEMANTIC_EQUIVALENT',dep=['A2'],contact='SHARED_SUPPORT_CONTACT',before='ACTOR',after='RECEIVER',overlap='SERIAL_REQUIRED')]
    elif variant==2:
        acts=[action(1,'B1','HOLD',perf='SCENE_GRAPH',overlap='HOLD'),action(2,'B2','REVEAL',perf='SCENE_GRAPH'),action(3,'B3','TRANSFORM',perf='SCENE_GRAPH',dep=['A2'])]
    else:
        acts=[action(1,'B1','WALK'),action(2,'B2','PRESS',req=['button_target'],contact='TARGET_CONTACT',overlap='SERIAL_REQUIRED'),action(3,'B3','DANCE')]
    return {'candidate_id':cid,'motion_thesis':f'motion strategy {variant}','restraint_strategy':'move only the semantic delta','actions':acts,'beat_motion_summary':[{'beat_id':b,'summary':f'motion for {b}'} for b in ['B1','B2','B3']],'global_rules':['no idle bobbing','dependencies serialize','safe explanatory overlap allowed'],'risk_notes':[]}

def story(): return {'film_thesis':{'central_argument':'A physical action becomes legible when cause and ownership are visible.'},'beats':[{'beat_id':'B1'},{'beat_id':'B2'},{'beat_id':'B3'}]}

class P6Provider:
    def complete(self,task,request):
        if task=='motion_performance': return {'candidates':[candidate('M1',1),candidate('M2',2),candidate('M3',3)]}
        if task=='motion_review':
            c=request['motion_candidate']; ok=c.get('executable') and not c.get('capability_gaps')
            return {'verdict':'ACCEPT' if ok else 'REVISE','issues':[] if ok else [{'code':'GAP'}],'strengths':['semantic delta is explicit'] if ok else [],'revision_brief':'' if ok else 'Remove unsupported performer actions.','commercial_confidence':'HIGH' if ok else 'LOW'}
        if task=='showrunner_select_motion':
            ids=[x['candidate']['candidate_id'] for x in request['candidates']]
            chosen='M1' if 'M1' in ids else ids[0]
            return {'selected_candidate_id':chosen,'why':'Best causal physical choreography with explicit capability-safe transfer.','tradeoffs':['Uses a support-surface handoff instead of direct free-air handoff.'],'rejected_alternatives':[{'candidate_id':x,'reason':'Weaker physical storytelling'} for x in ids if x!=chosen]}
        raise RuntimeError(task)

def seed_prior(sr):
    for slot in ['film_thesis','visual_concept','art_direction','storyboard','cinematography','editorial_rhythm','storyboard_temporal']:
        sr.state['decisions'][slot]={'proposal_id':slot+'-fixture','department':'fixture','payload':{'slot':slot},'revision':sr.state['revision'],'producer_review_id':'fixture-review'}
    return sr

class P6Tests(unittest.TestCase):
    def test_motion_contract_diverse(self): self.assertEqual(len(validate_motion_output({'candidates':[candidate('M1',1),candidate('M2',2),candidate('M3',3)]},BEATS)),3)
    def test_raw_joint_or_geometry_leak_blocked(self):
        c=candidate('M1',1); c['actions'][0]['coordinates']=[1,2]
        with self.assertRaises(ContractViolation): validate_motion_candidate(c,BEATS)
    def test_idle_bobbing_rejected(self):
        c=candidate('M1',1); c['actions'][0]['motivation']='idle bobbing'
        with self.assertRaisesRegex(ContractViolation,'decorative'): validate_motion_candidate(c,BEATS)
    def test_dependency_missing_blocked(self):
        c=candidate('M1',1); c['actions'][2]['dependencies']=['NOPE']
        with self.assertRaisesRegex(ContractViolation,'dependencies'): validate_motion_candidate(c,BEATS)
    def test_stickman_pickup_supported_with_real_requirements(self):
        d=PerformerCapabilityRegistry().resolve('STICKMAN_V2','PICKUP',{'grip_frame','support_state'},semantic_goal='PICK_OBJECT',fallback_policy='FAIL_CLOSED'); self.assertEqual(d['status'],'SUPPORTED')
    def test_pickup_missing_grip_fails_closed(self):
        d=PerformerCapabilityRegistry().resolve('STICKMAN_V2','PICKUP',{'support_state'},semantic_goal='PICK_OBJECT',fallback_policy='FAIL_CLOSED'); self.assertEqual(d['code'],'MISSING_PERFORMER_REQUIREMENTS')
    def test_heavy_carry_fails_closed(self): self.assertEqual(PerformerCapabilityRegistry().resolve('STICKMAN_V2','CARRY_HEAVY',{'grip_frame'},semantic_goal='CARRY',fallback_policy='FAIL_CLOSED')['code'],'HEAVY_CARRY_DONOR_REQUIRED')
    def test_sidestep_fails_closed(self): self.assertEqual(PerformerCapabilityRegistry().resolve('STICKMAN_V2','SIDESTEP',set(),semantic_goal='MOVE',fallback_policy='FAIL_CLOSED')['code'],'NO_AUTHORED_SIDESTEP_DONOR')
    def test_direct_handoff_rewrites_only_when_semantically_safe(self):
        r=PerformerCapabilityRegistry(); d=r.resolve('STICKMAN_V2','HANDOFF_DIRECT',{'support_surface','grip_frame'},semantic_goal='TRANSFER_OWNERSHIP',fallback_policy='ALLOW_SEMANTIC_EQUIVALENT'); self.assertEqual(d['status'],'REWRITE'); self.assertEqual(d['resolved_verb'],'HANDOFF_PLACE_AND_TAKE')
        u=r.resolve('STICKMAN_V2','HANDOFF_DIRECT',{'support_surface','grip_frame'},semantic_goal='SHOW_DIRECT_HAND_CONTACT',fallback_policy='ALLOW_SEMANTIC_EQUIVALENT'); self.assertEqual(u['status'],'UNSUPPORTED')
    def test_robot_grasp_not_invented(self): self.assertEqual(PerformerCapabilityRegistry().resolve('ROBOT','PICKUP',{'grip_frame'},semantic_goal='GRASP',fallback_policy='FAIL_CLOSED')['code'],'ROBOT_GRASP_CAPABILITY_NOT_PROVEN')
    def test_walk_run_dance_admitted(self):
        r=PerformerCapabilityRegistry()
        for v in ['WALK','RUN','DANCE']:
            self.assertEqual(r.resolve('STICKMAN_V2',v,set(),semantic_goal='PERFORM',fallback_policy='FAIL_CLOSED')['status'],'SUPPORTED')
    def test_director_resolves_safe_handoff(self):
        out=MotionPerformanceDirector(P6Provider(),PerformerCapabilityRegistry()).propose('P',{'topic':'x'},story(),{}, {}, {}, {}, {'beats':[]},{})
        self.assertTrue(out[0]['executable']); self.assertEqual(out[0]['actions'][2]['execution']['resolved_verb'],'HANDOFF_PLACE_AND_TAKE')
    def test_producer_rejects_capability_gap(self):
        c=candidate('BAD',1); c['actions'][1]['available_requirements']=[]
        d=MotionPerformanceDirector(P6Provider(),PerformerCapabilityRegistry())
        resolved=d._resolve(c); r=MotionExecutiveProducer(P6Provider()).review('P',{'topic':'x'},story(),resolved); self.assertEqual(r['verdict'],'REVISE')
    def test_direct_motion_commit_blocked(self):
        sr=seed_prior(NexMindSupremeShowrunnerP6('P',{'topic':'x'})); ref=sr.submit_proposal('MotionPerformanceDirector','M',{'representation':'MOTION_PERFORMANCE_PLAN','visual_thesis':'x','hero_kind':'x','transformation':'x','camera_idea':'x'})
        with self.assertRaises(AuthorityViolation): sr.commit_decision('motion_performance',ref)
    def test_review_token_payload_bound(self):
        sr=seed_prior(NexMindSupremeShowrunnerP6('P',{'topic':'x'})); ref=sr.submit_proposal('MotionPerformanceDirector','M',{'representation':'MOTION_PERFORMANCE_PLAN','visual_thesis':'x','hero_kind':'x','transformation':'x','camera_idea':'x'}); rv={'verdict':'ACCEPT','issues':[],'strengths':[],'revision_brief':'','commercial_confidence':'HIGH'}; tok=sr.register_p6_review(ref,rv); sr.state['proposals']['MotionPerformanceDirector']['M']['payload']['visual_thesis']='tamper'
        with self.assertRaisesRegex(ProducerGateError,'tampered'): sr.commit_p6_reviewed(ref,tok)
    def test_review_stale_after_replan(self):
        sr=seed_prior(NexMindSupremeShowrunnerP6('P',{'topic':'x'})); ref=sr.submit_proposal('MotionPerformanceDirector','M',{'representation':'MOTION_PERFORMANCE_PLAN','visual_thesis':'x','hero_kind':'x','transformation':'x','camera_idea':'x'}); rv={'verdict':'ACCEPT','issues':[],'strengths':[],'revision_brief':'','commercial_confidence':'HIGH'}; tok=sr.register_p6_review(ref,rv); sr.replan('change motion')
        with self.assertRaisesRegex(ProducerGateError,'stale'): sr.commit_p6_reviewed(ref,tok)
    def test_full_p6_council_gate_and_final_lock_truth(self):
        p=P6Provider(); sr=seed_prior(NexMindSupremeShowrunnerP6('P',{'topic':'physical transfer'})); council=CreativeCouncilP6(sr,MotionPerformanceDirector(p,PerformerCapabilityRegistry()),MotionExecutiveProducer(p),MotionShowrunnerDecisionIntelligence(p),PerformanceStoryboardCompiler()); s=story(); dev=council.develop(s,{}, {}, {}, {}, {'schema':'NexMindCanonicalTemporalStoryboardV2','beats':[{'beat_id':'B1','motion_plan_status':'UNRESOLVED_MOTION_DIRECTOR','sound_plan_status':'UNRESOLVED_SOUND_DIRECTOR'},{'beat_id':'B2','motion_plan_status':'UNRESOLVED_MOTION_DIRECTOR','sound_plan_status':'UNRESOLVED_SOUND_DIRECTOR'},{'beat_id':'B3','motion_plan_status':'UNRESOLVED_MOTION_DIRECTOR','sound_plan_status':'UNRESOLVED_SOUND_DIRECTOR'}]}); self.assertTrue(dev['diversity']['meaningfully_diverse']); sel=council.select(s,dev); self.assertEqual(sel['candidate']['candidate_id'],'M1'); self.assertEqual(sr.p6_ready_gate()['status'],'PASS')
        with self.assertRaises(ProducerGateError) as cm: sr.creative_lock()
        self.assertEqual(set(cm.exception.args[0]['missing_decisions']),{'sound_direction','final_producer'})
    def test_performance_storyboard_replaces_motion_unresolved_only(self):
        board={'schema':'NexMindCanonicalTemporalStoryboardV2','beats':[{'beat_id':'B1','motion_plan_status':'UNRESOLVED_MOTION_DIRECTOR','sound_plan_status':'UNRESOLVED_SOUND_DIRECTOR'},{'beat_id':'B2','motion_plan_status':'UNRESOLVED_MOTION_DIRECTOR','sound_plan_status':'UNRESOLVED_SOUND_DIRECTOR'},{'beat_id':'B3','motion_plan_status':'UNRESOLVED_MOTION_DIRECTOR','sound_plan_status':'UNRESOLVED_SOUND_DIRECTOR'}]}; m=MotionPerformanceDirector(P6Provider(),PerformerCapabilityRegistry()).propose('P',{'topic':'x'},story(),{}, {}, {}, {},board,{})[0]; out=PerformanceStoryboardCompiler().compile(board,m); self.assertTrue(all(x['motion_plan_status']=='DIRECTED_MOTION_PERFORMANCE' and x['sound_plan_status']=='UNRESOLVED_SOUND_DIRECTOR' for x in out['beats']))
    def test_production_source_no_fixture_subject(self):
        prod='\n'.join(p.read_text(encoding="utf-8", errors='ignore').lower() for p in (ROOT/'src').rglob('*.py')); self.assertNotIn('physical transfer',prod)

if __name__=='__main__': unittest.main(verbosity=2)
