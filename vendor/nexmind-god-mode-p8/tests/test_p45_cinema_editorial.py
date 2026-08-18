from __future__ import annotations
import copy,sys,unittest,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src')); sys.path.insert(0,str(ROOT/'tests'))
from test_p3_art_storyboard import story,visual,art_candidate,DynamicProvider,seed_p2
from nexmind_god_mode import (
    validate_cinema_output, validate_cinema_candidate, validate_editorial_output, validate_editorial_candidate, pacing_signature,
    CinematographyDirector, EditorialRhythmDirector, EditorialTimelineCompiler, P45ExecutiveProducer, P45ShowrunnerDecisionIntelligence,
    TemporalStoryboardCompiler, NexMindSupremeShowrunnerP45, CreativeCouncilP45,
    IllustrationFormResolver, P3ExecutiveProducer, ArtShowrunnerDecisionIntelligence, StoryboardCompiler, ArtDirector, CreativeCouncilP3
)
from nexmind_god_mode.contracts import ContractViolation
from nexmind_god_mode.showrunner_p2 import ProducerGateError
from nexmind_god_mode.p0_kernel import AuthorityViolation
from nexmind_god_mode.provider import ProviderError

INDEX=ROOT/'donors'/'NEXSTUDIO_ILLUSTRATION_CAPABILITY_INDEX_V1.json'


def camera_atom(atom,target,motivation,intensity='NONE'):
    return {"atom":atom,"target":target,"motivation":motivation,"intensity":intensity,"start_semantic_state":"current framing","end_semantic_state":"directed attention state"}

def cinema_candidate(cid,variant=1):
    if variant==1:
        shots=[
            {"beat_id":"B1","idiom":"HERO_ESTABLISH","shot_scale":"MEDIUM_WIDE","angle":"THREE_QUARTER","subject_target":"computer.hero","reveal_framing":"preserve full recognizable silhouette","depth_strategy":"LAYERED","camera_atom":camera_atom("HOLD","computer.hero","preserve recognition before revealing internals"),"transition_relation":"HOLD_CONTINUITY","attention_anchor":"computer.hero","continuity_reason":"same laptop remains the visual anchor"},
            {"beat_id":"B2","idiom":"COMPONENT_INSPECT","shot_scale":"MEDIUM_CLOSE","angle":"THREE_QUARTER","subject_target":"computer.internals","reveal_framing":"tighten only enough to read processor and memory while retaining laptop edge","depth_strategy":"SHALLOW_FOCUS","camera_atom":camera_atom("PUSH_IN","computer.internals","move closer because the audience must inspect the causal internal relationship","SUBTLE"),"transition_relation":"MATCH_POSITION","attention_anchor":"computer.hero","continuity_reason":"retain the laptop silhouette edge during inspection"},
            {"beat_id":"B3","idiom":"SYNTHESIS_PULLBACK","shot_scale":"MEDIUM_WIDE","angle":"THREE_QUARTER","subject_target":"computer.hero","reveal_framing":"restore the whole laptop with a subtle retained internal cue","depth_strategy":"LAYERED","camera_atom":camera_atom("PULL_BACK","computer.hero","restore the whole object for the final system synthesis","SUBTLE"),"transition_relation":"MATCH_POSITION","attention_anchor":"computer.hero","continuity_reason":"return to the same anchor for payoff"},
        ]
    elif variant==2:
        shots=[
            {"beat_id":"B1","idiom":"STATIC_TABLEAU","shot_scale":"MEDIUM","angle":"FRONTAL","subject_target":"computer.hero","reveal_framing":"single tableau with room for attached internals","depth_strategy":"DEEP_FOCUS","camera_atom":camera_atom("HOLD","computer.hero","hold to let the authored composition carry the explanation"),"transition_relation":"HOLD_CONTINUITY","attention_anchor":"computer.hero","continuity_reason":"composition evolves inside one stable frame"},
            {"beat_id":"B2","idiom":"REVEAL_SUPPORT","shot_scale":"MEDIUM","angle":"FRONTAL","subject_target":"computer.internals","reveal_framing":"internals reveal within the same tableau","depth_strategy":"DEEP_FOCUS","camera_atom":camera_atom("HOLD","computer.hero","hold because moving the camera would weaken spatial continuity"),"transition_relation":"HOLD_CONTINUITY","attention_anchor":"computer.hero","continuity_reason":"keep spatial relationships fixed"},
            {"beat_id":"B3","idiom":"STATIC_TABLEAU","shot_scale":"MEDIUM","angle":"FRONTAL","subject_target":"computer.hero","reveal_framing":"settled whole-system tableau","depth_strategy":"DEEP_FOCUS","camera_atom":camera_atom("HOLD","computer.hero","hold for final comprehension"),"transition_relation":"HOLD_CONTINUITY","attention_anchor":"computer.hero","continuity_reason":"final tableau preserves all learned relationships"},
        ]
    else:
        shots=[
            {"beat_id":"B1","idiom":"HERO_ESTABLISH","shot_scale":"WIDE","angle":"EYE_LEVEL","subject_target":"computer.hero","reveal_framing":"establish object and its working zone","depth_strategy":"LAYERED","camera_atom":camera_atom("HOLD","computer.hero","establish before following transformation"),"transition_relation":"HOLD_CONTINUITY","attention_anchor":"computer.hero","continuity_reason":"anchor identity first"},
            {"beat_id":"B2","idiom":"TRACK_TRANSFORMATION","shot_scale":"MEDIUM_CLOSE","angle":"PROFILE","subject_target":"data task through internals","reveal_framing":"follow causal path while keeping device context","depth_strategy":"SHALLOW_FOCUS","camera_atom":camera_atom("FOLLOW","data task","follow because the causal transformation itself is the subject","MODERATE"),"transition_relation":"CARRY_MOTION","attention_anchor":"data task","continuity_reason":"attention follows one persistent task rather than cutting to disconnected parts"},
            {"beat_id":"B3","idiom":"CONSEQUENCE_PULLBACK","shot_scale":"WIDE","angle":"EYE_LEVEL","subject_target":"computer.hero","reveal_framing":"show completed output in context of whole device","depth_strategy":"DEEP_FOCUS","camera_atom":camera_atom("HOLD","computer.hero","hold the consequence after the follow ends"),"transition_relation":"CUT_ON_REVEAL","attention_anchor":"computer.output","continuity_reason":"completed task resolves back into the whole system"},
        ]
    return {"candidate_id":cid,"cinema_thesis":f"Cinema strategy {variant} directs attention without decorative motion.","attention_strategy":"Preserve one attention anchor and only move when meaning changes scale or location.","shots":shots,"global_rules":["HOLD is first-class","no decorative camera"],"risk_notes":[]}


def editorial_candidate(cid,variant=1,film_kind='causal explainer'):
    rate=24; total=1080
    if variant==1:
        specs=[('B1','SETUP',0,300,60,230,'LOW',70,30,'CUT'),('B2','REVEAL',270,480,90,370,'PEAK',90,30,'MATCH_CUT'),('B3','SYNTHESIS',720,360,55,240,'MEDIUM',120,0,'HOLD_THROUGH')]
        profile='BUILD_INSPECT_SYNTHESIZE'
    elif variant==2:
        specs=[('B1','OPEN',0,360,70,270,'MEDIUM',80,0,'CUT'),('B2','PROOF',360,360,80,260,'MEDIUM',80,0,'CUT'),('B3','CLOSE',720,360,70,240,'MEDIUM',120,0,'HOLD_THROUGH')]
        profile='EVENLY_METERED_BY_INTENT'
    else:
        specs=[('B1','OPEN',0,240,45,170,'HIGH',50,30,'CARRY'),('B2','BUILD',210,420,70,320,'MEDIUM',70,30,'MATCH_CUT'),('B3','CLIMAX',600,480,70,330,'PEAK',150,0,'HOLD_THROUGH')]
        profile='FAST_ENTRY_LONG_PAYOFF'
    beats=[]
    for bid,role,start,dur,action,settle,energy,still,overlap,tx in specs:
        beats.append({"beat_id":bid,"role":role,"start":{"value":start,"rate":rate},"duration":{"value":dur,"rate":rate},"action_frame":action,"settle_frame":settle,"energy":energy,"stillness_frames":still,"overlap_to_next_frames":overlap,"transition":tx,"duration_rationale":f"{role} receives {dur} frames because its narrative job differs from neighboring beats."})
    return {"candidate_id":cid,"editorial_thesis":f"Rhythm strategy {variant} shapes a {film_kind} around comprehension and payoff.","project_rate":rate,"target_duration_frames":total,"rhythm_profile":profile,"peak_budget":2,"beats":beats,"final_payoff_hold_frames":100,"risk_notes":[]}

class P45Provider(DynamicProvider):
    def complete(self,task,request):
        if task=='cinematography':
            self.calls.append((task,copy.deepcopy(request))); return {"candidates":[cinema_candidate('C1',1),cinema_candidate('C2',2),cinema_candidate('C3',3)]}
        if task in {'cinematography_review','editorial_review','temporal_storyboard_review'}:
            self.calls.append((task,copy.deepcopy(request))); return {"verdict":"ACCEPT","issues":[],"strengths":["semantically directed"],"revision_brief":"","commercial_confidence":"HIGH"}
        if task=='showrunner_select_cinematography':
            self.calls.append((task,copy.deepcopy(request))); ids=[x['candidate']['candidate_id'] for x in request['candidates'] if x['review']['verdict']=='ACCEPT']; chosen='C1' if 'C1' in ids else ids[0]
            return {"selected_candidate_id":chosen,"why":"C1 balances meaningful inspection with real holds and a synthesis return.","tradeoffs":["One motivated push and pull instead of a fully static tableau"],"rejected_alternatives":[{"candidate_id":x,"reason":"Less balanced attention strategy"} for x in ids if x!=chosen]}
        if task=='editorial_rhythm':
            self.calls.append((task,copy.deepcopy(request))); fk=request['film_thesis']['film_kind']; return {"candidates":[editorial_candidate('E1',1,fk),editorial_candidate('E2',2,fk),editorial_candidate('E3',3,fk)]}
        if task=='showrunner_select_editorial':
            self.calls.append((task,copy.deepcopy(request))); fk=request['film_thesis']['film_kind']; chosen='E3' if 'manifesto' in fk.lower() else 'E1'; ids=[x['candidate']['candidate_id'] for x in request['candidates'] if x['review']['verdict']=='ACCEPT'];
            if chosen not in ids: chosen=ids[0]
            return {"selected_candidate_id":chosen,"why":"The rhythm shape matches the narrative function rather than dividing time evenly.","tradeoffs":["Some beats receive substantially different durations"],"rejected_alternatives":[{"candidate_id":x,"reason":"Weaker match to the film function"} for x in ids if x!=chosen]}
        return super().complete(task,request)


def seed_p3(sr,provider):
    s,v=seed_p2(sr)
    resolver=IllustrationFormResolver.from_file(INDEX)
    c=CreativeCouncilP3(sr,ArtDirector(provider),resolver,P3ExecutiveProducer(provider),ArtShowrunnerDecisionIntelligence(provider),StoryboardCompiler())
    ar=c.develop_art(s,v); sel=c.select_art(s,v,ar); board=c.compile_and_review_storyboard(s,v,sel)
    sr.p3_ready_gate()
    return s,v,sel['candidate'],board['board']

class P45Tests(unittest.TestCase):
    def test_cinema_contract_accepts_diverse_semantic_candidates(self):
        out=validate_cinema_output({"candidates":[cinema_candidate('C1',1),cinema_candidate('C2',2),cinema_candidate('C3',3)]},{'B1','B2','B3'},'computer.hero')
        self.assertEqual(len(out),3)
    def test_cinema_rejects_coordinate_leak(self):
        c=cinema_candidate('C1',1); c['shots'][0]['x']=10
        with self.assertRaises(ContractViolation): validate_cinema_candidate(c,{'B1','B2','B3'},'computer.hero')
    def test_cinema_rejects_unmotivated_move(self):
        c=cinema_candidate('C1',1); c['shots'][1]['camera_atom']['motivation']='because new beat'
        with self.assertRaisesRegex(ContractViolation,'semantic motivation'): validate_cinema_candidate(c,{'B1','B2','B3'},'computer.hero')
    def test_hold_is_first_class_and_has_no_fake_intensity(self):
        c=cinema_candidate('C2',2); self.assertTrue(all(s['camera_atom']['atom']=='HOLD' for s in c['shots']))
        c['shots'][0]['camera_atom']['intensity']='SUBTLE'
        with self.assertRaisesRegex(ContractViolation,'HOLD'): validate_cinema_candidate(c,{'B1','B2','B3'},'computer.hero')
    def test_camera_move_every_beat_requires_explicit_story_rule(self):
        c=cinema_candidate('C1',1)
        c['shots'][0]['camera_atom']=camera_atom('REFRAME','computer.hero','reframe to establish the subject','SUBTLE')
        c['shots'][2]['camera_atom']=camera_atom('PULL_BACK','computer.hero','pull back for synthesis','SUBTLE')
        # B2 already moves, so all three move.
        with self.assertRaisesRegex(ContractViolation,'every beat'): validate_cinema_candidate(c,{'B1','B2','B3'},'computer.hero')
        c['global_rules'].append('continuous_camera_is_story')
        validate_cinema_candidate(c,{'B1','B2','B3'},'computer.hero')
    def test_editorial_uses_rational_frames_only(self):
        e=editorial_candidate('E1',1); validate_editorial_candidate(e,{'B1','B2','B3'})
        blob=json.dumps(e); self.assertNotIn('.0',blob)
    def test_editorial_rejects_float_time(self):
        e=editorial_candidate('E1',1); e['beats'][0]['duration']['value']=300.0
        with self.assertRaises(ContractViolation): validate_editorial_candidate(e,{'B1','B2','B3'})
    def test_editorial_rejects_accidental_equal_subdivision(self):
        e=editorial_candidate('E2',2); e['rhythm_profile']='GENERIC'
        with self.assertRaisesRegex(ContractViolation,'equal beat subdivision'): validate_editorial_candidate(e,{'B1','B2','B3'})
    def test_editorial_peak_budget_enforced(self):
        e=editorial_candidate('E1',1); e['peak_budget']=1; e['beats'][0]['energy']='PEAK'; e['beats'][1]['energy']='PEAK'
        with self.assertRaisesRegex(ContractViolation,'peak budget'): validate_editorial_candidate(e,{'B1','B2','B3'})
    def test_editorial_timeline_is_otio_compatible_boundary(self):
        t=EditorialTimelineCompiler().compile(editorial_candidate('E1',1))
        self.assertEqual(t['time_model'],'RationalTime/TimeRange'); self.assertEqual(t['duration'],{'value':1080,'rate':24}); self.assertEqual(len(t['tracks'][0]['children']),3)
        def walk(x):
            if isinstance(x,float): return False
            if isinstance(x,dict): return all(walk(v) for v in x.values())
            if isinstance(x,list): return all(walk(v) for v in x)
            return True
        self.assertTrue(walk(t))
    def test_same_duration_different_film_functions_select_different_pacing(self):
        p=P45Provider(); reason=P45ShowrunnerDecisionIntelligence(p)
        base=story(); rev=[{"candidate":editorial_candidate('E1',1),"review":{"verdict":"ACCEPT"}},{"candidate":editorial_candidate('E2',2),"review":{"verdict":"ACCEPT"}},{"candidate":editorial_candidate('E3',3),"review":{"verdict":"ACCEPT"}}]
        a=reason.select_editorial('P1',base,rev); s2=copy.deepcopy(base); s2['film_thesis']['film_kind']='brand manifesto'; b=reason.select_editorial('P2',s2,rev)
        ca=next(x['candidate'] for x in rev if x['candidate']['candidate_id']==a['selected_candidate_id']); cb=next(x['candidate'] for x in rev if x['candidate']['candidate_id']==b['selected_candidate_id'])
        self.assertNotEqual(pacing_signature(ca),pacing_signature(cb)); self.assertEqual(ca['target_duration_frames'],cb['target_duration_frames'])
    def test_p45_direct_cinema_commit_blocked(self):
        sr=NexMindSupremeShowrunnerP45('P',{'topic':'x'}); ref=sr.submit_proposal('CinematographyDirector','C',cinema_candidate('C',1))
        with self.assertRaises(AuthorityViolation): sr.commit_decision('cinematography',ref)
    def test_p45_rejected_cinema_cannot_commit(self):
        sr=NexMindSupremeShowrunnerP45('P',{'topic':'x'}); ref=sr.submit_proposal('CinematographyDirector','C',cinema_candidate('C',1)); r={"verdict":"REVISE","issues":[],"strengths":[],"revision_brief":"fix","commercial_confidence":"LOW"}; tok=sr.register_p45_review('cinematography',ref,r)
        with self.assertRaises(ProducerGateError): sr.commit_p45_reviewed('cinematography',ref,tok)
    def test_p45_review_token_binds_exact_payload(self):
        sr=NexMindSupremeShowrunnerP45('P',{'topic':'x'}); ref=sr.submit_proposal('CinematographyDirector','C',cinema_candidate('C',1)); r={"verdict":"ACCEPT","issues":[],"strengths":[],"revision_brief":"","commercial_confidence":"HIGH"}; tok=sr.register_p45_review('cinematography',ref,r); sr.state['proposals']['CinematographyDirector']['C']['payload']['cinema_thesis']='tampered'
        with self.assertRaisesRegex(ProducerGateError,'tampered'): sr.commit_p45_reviewed('cinematography',ref,tok)
    def test_p45_review_becomes_stale_after_replan(self):
        sr=NexMindSupremeShowrunnerP45('P',{'topic':'x'}); ref=sr.submit_proposal('CinematographyDirector','C',cinema_candidate('C',1)); r={"verdict":"ACCEPT","issues":[],"strengths":[],"revision_brief":"","commercial_confidence":"HIGH"}; tok=sr.register_p45_review('cinematography',ref,r); sr.replan('camera strategy changed')
        with self.assertRaisesRegex(ProducerGateError,'stale'): sr.commit_p45_reviewed('cinematography',ref,tok)
    def test_temporal_storyboard_marks_motion_and_sound_unresolved(self):
        p=P45Provider(); sr=NexMindSupremeShowrunnerP45('P',{'topic':'How a computer works'}); s,v,a,key=seed_p3(sr,p)
        tl=EditorialTimelineCompiler().compile(editorial_candidate('E1',1)); b=TemporalStoryboardCompiler().compile(key,cinema_candidate('C1',1),editorial_candidate('E1',1),tl); g=TemporalStoryboardCompiler().gate(b)
        self.assertEqual(g['status'],'PASS'); self.assertTrue(all(x['motion_plan_status']=='UNRESOLVED_MOTION_DIRECTOR' and x['sound_plan_status']=='UNRESOLVED_SOUND_DIRECTOR' for x in b['beats']))
    def test_full_p45_council_reaches_p45_gate_but_not_final_lock(self):
        p=P45Provider(); sr=NexMindSupremeShowrunnerP45('P',{'topic':'How a computer works'}); s,v,a,key=seed_p3(sr,p)
        c=CreativeCouncilP45(sr,CinematographyDirector(p),EditorialRhythmDirector(p),P45ExecutiveProducer(p),P45ShowrunnerDecisionIntelligence(p),EditorialTimelineCompiler(),TemporalStoryboardCompiler())
        cd=c.develop_cinema(s,v,a,key); self.assertTrue(cd['diversity']['meaningfully_diverse']); cs=c.select_cinema(s,cd)
        ed=c.develop_editorial(s,v,a,cs['candidate'],target_duration_frames=1080,project_rate=24); self.assertTrue(ed['diversity']['meaningfully_diverse']); es=c.select_editorial(s,ed)
        tb=c.compile_temporal_storyboard(s,key,cs,es); self.assertEqual(tb['review']['verdict'],'ACCEPT'); self.assertEqual(sr.p45_ready_gate()['status'],'PASS')
        with self.assertRaisesRegex(ProducerGateError,'FINAL_CREATIVE_LOCK_BLOCKED_INCOMPLETE_BRAIN') as cm: sr.creative_lock()
        missing=cm.exception.args[0]['missing_decisions']; self.assertEqual(set(missing),{'motion_performance','sound_direction','final_producer'})
    def test_temporal_storyboard_cannot_commit_before_cinema_editorial(self):
        sr=NexMindSupremeShowrunnerP45('P',{'topic':'x'}); ref=sr.submit_proposal('StoryboardCompilerV2','SB',{'schema':'NexMindCanonicalTemporalStoryboardV2'}); r={"verdict":"ACCEPT","issues":[],"strengths":[],"revision_brief":"","commercial_confidence":"HIGH"}; tok=sr.register_p45_review('storyboard_temporal',ref,r)
        with self.assertRaisesRegex(ProducerGateError,'requires key-state storyboard'): sr.commit_p45_reviewed('storyboard_temporal',ref,tok)
    def test_production_source_contains_no_fixture_topics(self):
        prod='\n'.join(p.read_text(encoding="utf-8", errors='ignore').lower() for p in (ROOT/'src').rglob('*.py'))
        for term in ['how a computer works','brand manifesto','computer.hero']:
            self.assertNotIn(term,prod)

if __name__=='__main__': unittest.main(verbosity=2)
