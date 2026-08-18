import copy,json,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from nexmind_god_mode.sound_resources import SoundResourceRegistry
from nexmind_god_mode.sound_contracts import validate_sound_output,validate_sound_candidate
from nexmind_god_mode.sound_director import SoundDirector
from nexmind_god_mode.p7_producer import SoundExecutiveProducer
from nexmind_god_mode.p7_showrunner_reasoner import SoundShowrunnerDecisionIntelligence
from nexmind_god_mode.showrunner_p7 import NexMindSupremeShowrunnerP7
from nexmind_god_mode.council_p7 import CreativeCouncilP7
from nexmind_god_mode.storyboard_compiler_v4 import SoundStoryboardCompiler
from nexmind_god_mode.sound_specialists import TTSAdapter,MusicAdapter
from nexmind_god_mode.contracts import ContractViolation
from nexmind_god_mode.p0_kernel import AuthorityViolation
from nexmind_god_mode.showrunner_p2 import ProducerGateError
INDEX=ROOT/'donors'/'authorized_sound_index.json';BEATS={'B1','B2','B3'}
def ev(i,b,kind,tag,intensity='SOFT',optional=False,duck='LIGHT',before=False,after=False):return {'event_id':f'E{i}','beat_id':b,'kind':kind,'semantic_tag':tag,'intensity':intensity,'optional':optional,'ducking':duck,'narrative_reason':'mark a meaningful physical or narrative state change','sync_target':'semantic action point','silence_before':before,'silence_after':after}
def cand(cid,v=1):
 if v==1: events=[ev(1,'B1','SILENCE','silence','NONE',duck='NONE',after=True),ev(2,'B2','FOLEY','object.place',duck='MODERATE'),ev(3,'B3','SFX','ui.confirm',intensity='MEDIUM',duck='MODERATE')];music={'mode':'NONE','full_length_bed':False,'narrative_role':'silence and impact carry the arc','energy_arc':['still','impact','resolve'],'rights_policy':'NO_MUSIC'}
 elif v==2: events=[ev(1,'B1','SFX','ui.open',before=True),ev(2,'B2','SILENCE','silence','NONE',duck='NONE'),ev(3,'B3','TRANSITION','motion.complete',optional=True)];music={'mode':'MOTIF_ONLY','full_length_bed':False,'narrative_role':'a brief motif only at the final payoff','energy_arc':['none','none','motif'],'rights_policy':'EXISTING_AUTHORIZED_OR_OMIT'}
 else: events=[ev(1,'B1','SILENCE','silence','NONE',duck='NONE'),ev(2,'B2','MUSIC_CUE','music.rise'),ev(3,'B3','MUSIC_CUE','music.resolve')];music={'mode':'GENERATIVE','full_length_bed':False,'narrative_role':'short composed arc for transformation only','energy_arc':['still','rise','resolve'],'rights_policy':'RIGHTS_SAFE_PROVIDER_REQUIRED'}
 return {'candidate_id':cid,'sound_thesis':f'sonic strategy {v}','narration_strategy':'clear conversational narration with performance matched to argument','music_strategy':music,'motifs':['single restrained sonic identity'],'events':events,'beat_sound_summary':[{'beat_id':b,'summary':f'sound role {b}'} for b in ['B1','B2','B3']],'mix_intent':{'narration_priority':'PRIMARY','ducking_profile':'MODERATE','impact_headroom':'reserve room for one payoff','mastering_intent':'clean intelligible premium mix'},'silence_strategy':'silence before or after key reveals creates contrast','risk_notes':[]}
def story():return {'film_thesis':{'central_argument':'Sound makes state changes feel causal without clutter.'},'beats':[{'beat_id':'B1'},{'beat_id':'B2'},{'beat_id':'B3'}]}
class P:
 def complete(self,task,request):
  if task=='sound_direction':return {'candidates':[cand('S1',1),cand('S2',2),cand('S3',3)]}
  if task=='sound_review':
   c=request['sound_candidate'];ok=c.get('executable_resource_plan') and not c.get('music_strategy',{}).get('full_length_bed');return {'verdict':'ACCEPT' if ok else 'REVISE','issues':[] if ok else [{'code':'RESOURCE_OR_BED'}],'strengths':['restrained sound architecture'] if ok else [],'revision_brief':'' if ok else 'Resolve resource/music-bed issue.','commercial_confidence':'HIGH' if ok else 'LOW'}
  if task=='showrunner_select_sound':
   ids=[x['candidate']['candidate_id'] for x in request['candidates']];ch='S1' if 'S1' in ids else ids[0];return {'selected_candidate_id':ch,'why':'Silence, physical foley and one confirmation cue give the strongest causal hierarchy.','tradeoffs':['Less continuous music, more exposed silence.'],'rejected_alternatives':[{'candidate_id':x,'reason':'Weaker restraint or execution certainty'} for x in ids if x!=ch]}
  raise RuntimeError(task)
def seed(sr):
 for slot in ['film_thesis','visual_concept','art_direction','storyboard','cinematography','editorial_rhythm','storyboard_temporal','motion_performance']:sr.state['decisions'][slot]={'proposal_id':slot,'department':'fixture','payload':{},'revision':0,'producer_review_id':'r'}
 return sr
class T(unittest.TestCase):
 def setUp(self):self.r=SoundResourceRegistry.from_file(INDEX)
 def test_authorized_index_is_real_and_mapped(self):self.assertEqual(self.r.stats()['records'],10);self.assertEqual(self.r.resolve('object.place')['status'],'AUTHORIZED_ASSET')
 def test_unknown_required_sound_fails_closed(self):self.assertEqual(self.r.resolve('nonexistent.sound')['status'],'UNSUPPORTED_SOUND_TAG')
 def test_unknown_optional_sound_is_omitted(self):self.assertEqual(self.r.resolve('nonexistent.sound',optional=True)['status'],'OMITTED_UNMAPPED_OPTIONAL')
 def test_sound_candidates_diverse(self):self.assertEqual(len(validate_sound_output({'candidates':[cand('S1',1),cand('S2',2),cand('S3',3)]},BEATS)),3)
 def test_generic_full_length_music_bed_rejected(self):
  c=cand('X',1);c['music_strategy']={'mode':'EXISTING_LICENSED','full_length_bed':True,'narrative_role':'background music','energy_arc':['same'],'rights_policy':'LICENSED'}
  with self.assertRaisesRegex(ContractViolation,'full-length'):validate_sound_candidate(c,BEATS)
 def test_continuous_purposeful_sound_does_not_require_house_silence_quota(self):
  c=cand('X',1);c['events']=[ev(1,'B1','SFX','ui.open'),ev(2,'B2','SFX','ui.click'),ev(3,'B3','SFX','ui.confirm')]
  self.assertEqual(validate_sound_candidate(c,BEATS)['candidate_id'],'X')
 def test_director_resolves_authorized_assets_and_rejects_unavailable_music(self):
  out=SoundDirector(P(),self.r,music_generation_available=False).propose('P',{'topic':'x'},story(),{}, {}, {'beats':[]},{});self.assertTrue(out[0]['executable_resource_plan']);self.assertIn('audio.authorized.object_place_soft_01',out[0]['authorized_assets']);self.assertFalse(out[2]['executable_resource_plan']);self.assertEqual(out[2]['resource_gaps'][0]['code'],'RIGHTS_SAFE_MUSIC_PROVIDER_UNAVAILABLE')
 def test_tts_and_music_are_body_specialist_ports(self):self.assertEqual(TTSAdapter().capability()['role'],'body_specialist');self.assertEqual(MusicAdapter().capability()['role'],'body_specialist')
 def test_sound_direct_commit_blocked(self):
  sr=seed(NexMindSupremeShowrunnerP7('P',{'topic':'x'}));ref=sr.submit_proposal('SoundDirector','S',{'representation':'SOUND_DIRECTION_PLAN','visual_thesis':'x','hero_kind':'NONE','transformation':'x','camera_idea':'x'})
  with self.assertRaises(AuthorityViolation):sr.commit_decision('sound_direction',ref)
 def test_full_p7_council_leaves_only_final_producer(self):
  sr=seed(NexMindSupremeShowrunnerP7('P',{'topic':'x'}));p=P();c=CreativeCouncilP7(sr,SoundDirector(p,self.r,False),SoundExecutiveProducer(p),SoundShowrunnerDecisionIntelligence(p),SoundStoryboardCompiler());s=story();dev=c.develop(s,{}, {}, {'schema':'NexMindCanonicalPerformanceStoryboardV3','beats':[{'beat_id':'B1','sound_plan_status':'UNRESOLVED_SOUND_DIRECTOR'},{'beat_id':'B2','sound_plan_status':'UNRESOLVED_SOUND_DIRECTOR'},{'beat_id':'B3','sound_plan_status':'UNRESOLVED_SOUND_DIRECTOR'}]});self.assertTrue(dev['diversity']['meaningfully_diverse']);sel=c.select(s,dev);self.assertEqual(sel['candidate']['candidate_id'],'S1');self.assertEqual(sr.p7_ready_gate()['status'],'PASS')
  with self.assertRaises(ProducerGateError) as cm:sr.creative_lock()
  self.assertEqual(cm.exception.args[0]['missing_decisions'],['final_producer'])
 def test_sound_storyboard_resolves_sound_only(self):
  b={'schema':'NexMindCanonicalPerformanceStoryboardV3','beats':[{'beat_id':'B1','sound_plan_status':'UNRESOLVED_SOUND_DIRECTOR'},{'beat_id':'B2','sound_plan_status':'UNRESOLVED_SOUND_DIRECTOR'},{'beat_id':'B3','sound_plan_status':'UNRESOLVED_SOUND_DIRECTOR'}]};snd=SoundDirector(P(),self.r,False).propose('P',{'topic':'x'},story(),{}, {},b,{})[0];out=SoundStoryboardCompiler().compile(b,snd);self.assertTrue(all(x['sound_plan_status']=='DIRECTED_SOUND' for x in out['beats']));self.assertEqual(out['unresolved_departments'],['final_producer'])
if __name__=='__main__':unittest.main(verbosity=2)
