import copy, pathlib, sys, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from nexmind_god_mode.final_producer_contracts import validate_final_producer_output,validate_human_review,human_review_gate,ContractViolation,HUMAN_REVIEW_DIMENSIONS,CRAFT_DIMENSIONS,TASTE_DIMENSIONS
from nexmind_god_mode.final_critic_ensemble import FinalCriticEnsemble,PRIOR_SLOTS
from nexmind_god_mode.final_executive_producer import FinalExecutiveProducer
from nexmind_god_mode.human_calibration import HumanCalibrationRegistry
from nexmind_god_mode.showrunner_p8 import NexMindSupremeShowrunnerP8
from nexmind_god_mode.p0_kernel import AuthorityViolation,CreativeLockError
from nexmind_god_mode.showrunner_p2 import ProducerGateError
from nexmind_god_mode.council_p8 import CreativeCouncilP8
from nexmind_god_mode.final_production_dossier import FinalProductionDossierCompiler

CRAFT=list(CRAFT_DIMENSIONS)
TASTE=list(TASTE_DIMENSIONS)
def score(v=9.7):return {'score':v,'confidence':'MEDIUM','rationale':'specific diagnostic rationale'}
def review(verdict='ACCEPT'):
 return {'verdict':verdict,'hard_gates':[{'dimension':'EVIDENCE_TRUTH','status':'PASS','code':'OK','evidence':['verified']}], 'craft_scores':{k:score() for k in CRAFT},'taste_judgments':{k:score() for k in TASTE},'divergence':{'novelty':8.2,'conceptual_risk':6.5,'template_similarity':2.0,'rationale':'distinct from generic template grammar'},'uncertainty':{'confidence':'MEDIUM','reasons':[],'human_review_required':False,'multimodal_evidence_complete':True},'strengths':['clear causal thesis'],'issues':[] if verdict=='ACCEPT' else ['needs revision'],'revision_plan':[] if verdict=='ACCEPT' else ['rebuild weak section'],'commercial_recommendation':'MACHINE_ACCEPT_HUMAN_REVIEW_REQUIRED' if verdict=='ACCEPT' else 'DO_NOT_RENDER'}
def human(v=9.7,**kw):
 d={'reviewer_id':'HUMAN-001','reviewer_provenance':'independent named reviewer','blind':True,'independent':True,'scores':{k:v for k in HUMAN_REVIEW_DIMENSIONS},'hard_rejects':[],'notes':'blind review'};d.update(kw);return d

def story():return {'film_thesis':{'central_argument':'One clear causal argument','final_payoff':'The audience sees the whole consequence'},'beats':[{'beat_id':'B1'},{'beat_id':'B2'}]}
def board():return {'schema':'NexMindCanonicalSoundStoryboardV4','beats':[{'beat_id':'B1','sound_plan_status':'DIRECTED_SOUND'},{'beat_id':'B2','sound_plan_status':'DIRECTED_SOUND','final_payoff':'resolved'}], 'unresolved_departments':['final_producer']}
def semantic(slot):
 if slot=='film_thesis':return {'central_argument':'One clear causal argument','final_payoff':'The audience sees the whole consequence'}
 if slot=='visual_concept':return {'visual_thesis':'one dominant physical argument','hero_kind':'literal hero object','transformation':'state changes causally','beat_treatments':[1,2]}
 if slot=='art_direction':return {'art_thesis':'authored visual world','hero_treatment':'dominant','settled_state':'resolved','risk_notes':[]}
 if slot=='cinematography':return {'cinema_thesis':'camera follows attention','shots':[{'motivation':'reveal'},{'motivation':'payoff'}]}
 if slot=='editorial_rhythm':return {'rhythm_thesis':'escalating pace','beats':[{'duration':2},{'duration':5}]}
 if slot=='motion_performance':return {'motion_thesis':'motivated action only','actions':[{'status':'EXECUTABLE','contact_requirement':'TARGET_CONTACT'}]}
 if slot=='sound_direction':return {'sound_thesis':'silence and action cues','resource_gaps':[],'events':[{'kind':'SILENCE'},{'kind':'FOLEY'}]}
 if slot=='storyboard':return {'rehearsal_states':['opening','settled','payoff']}
 if slot=='storyboard_temporal':return {'timing':'resolved'}
 return {'resolved':True}
def seed(sr):
 for slot in PRIOR_SLOTS:sr.state['decisions'][slot]={'decision_slot':slot,'department':'fixture','proposal_id':slot,'payload':semantic(slot),'revision':sr.state['revision'],'status':'COMMITTED_BY_SHOWRUNNER','producer_review_id':'fixture-review'}
 return sr
class P:
 def __init__(self,payload=None):self.payload=payload or review()
 def complete(self,task,request):
  if task!='final_producer':raise RuntimeError(task)
  return copy.deepcopy(self.payload)

class T(unittest.TestCase):
 def test_contract_forbids_single_score(self):
  r=review();r['overall_score']=9.7
  with self.assertRaises(ContractViolation):validate_final_producer_output(r)
 def test_contract_hard_fail_cannot_accept(self):
  r=review();r['hard_gates'][0]['status']='FAIL'
  with self.assertRaisesRegex(ContractViolation,'hard-gate'):validate_final_producer_output(r)
 def test_accept_cannot_hide_blocking_issue_or_revision(self):
  r=review();r['issues']=['The film is generic despite clean mechanics.']
  with self.assertRaisesRegex(ContractViolation,'blocking issues'):validate_final_producer_output(r)
  r=review();r['revision_plan']=['Re-author the generic visual concept.']
  with self.assertRaisesRegex(ContractViolation,'revision plan'):validate_final_producer_output(r)
 def test_human_review_must_be_blind_independent(self):
  with self.assertRaises(ContractViolation):validate_human_review(human(blind=False))
 def test_human_elite_thresholds(self):
  self.assertEqual(human_review_gate(human())['status'],'PASS');x=human();x['scores']['visual_communication']=8.9;self.assertEqual(human_review_gate(x)['status'],'FAIL')
 def test_calibration_does_not_count_synthetic(self):
  c=HumanCalibrationRegistry();c.add('P',review(),human(),synthetic=True);self.assertEqual(c.status()['human_reviews'],0);self.assertEqual(c.status()['status'],'INSUFFICIENT_HUMAN_CALIBRATION')
 def test_ensemble_passes_complete_semantic_state(self):
  sr=seed(NexMindSupremeShowrunnerP8('P',{'topic':'x'}));g=FinalCriticEnsemble().evaluate(sr.state,board());self.assertEqual(len(g),11);self.assertFalse([x for x in g if x['status']=='FAIL'])
 def test_ensemble_detects_missing_department(self):
  sr=seed(NexMindSupremeShowrunnerP8('P',{'topic':'x'}));sr.state['decisions'].pop('motion_performance');g=FinalCriticEnsemble().evaluate(sr.state,board());self.assertEqual(next(x for x in g if x['dimension']=='DEPARTMENT_COMPLETENESS')['status'],'FAIL')
 def test_final_producer_judges_film_without_preensemble_calibration_mutation(self):
  sr=seed(NexMindSupremeShowrunnerP8('P',{'topic':'x'}));r=FinalExecutiveProducer(P()).review('P',{'topic':'x'},story(),sr.state,board(),multimodal_evidence={'status':'COMPLETE','artifacts':['contact-sheet.png']},calibration={'status':'INSUFFICIENT_HUMAN_CALIBRATION','human_reviews':0});self.assertEqual(r['verdict'],'ACCEPT');self.assertFalse(r['uncertainty']['human_review_required'])
 def test_hard_gate_failure_overrides_model_accept(self):
  sr=seed(NexMindSupremeShowrunnerP8('P',{'topic':'x'}));sr.state['decisions'].pop('sound_direction');r=FinalExecutiveProducer(P()).review('P',{'topic':'x'},story(),sr.state,board(),calibration={'status':'CALIBRATED'});self.assertEqual(r['verdict'],'REVISE');self.assertEqual(r['commercial_recommendation'],'DO_NOT_RENDER')
 def test_direct_final_producer_commit_blocked(self):
  sr=seed(NexMindSupremeShowrunnerP8('P',{'topic':'x'}));ref=sr.submit_proposal('FakeFinalProducer','F',{'representation':'REVIEW','visual_thesis':'x','hero_kind':'x','transformation':'x','camera_idea':'x'})
  with self.assertRaises(AuthorityViolation):sr.commit_decision('final_producer',ref)
 def test_final_review_bound_to_complete_state_and_board(self):
  sr=seed(NexMindSupremeShowrunnerP8('P',{'topic':'x'}));r=FinalExecutiveProducer(P()).review('P',{'topic':'x'},story(),sr.state,board(),calibration={'status':'INSUFFICIENT_HUMAN_CALIBRATION'});tok=sr.register_final_producer_review(r,board());sr.state['decisions']['sound_direction']['payload']['sound_thesis']='tampered'
  with self.assertRaisesRegex(ProducerGateError,'stale|tampered'):sr.commit_final_producer(tok,board())
 def test_direct_showrunner_gate_does_not_invent_calibration_authority(self):
  sr=seed(NexMindSupremeShowrunnerP8('P',{'topic':'x'}));r=FinalExecutiveProducer(P()).review('P',{'topic':'x'},story(),sr.state,board(),calibration={'status':'INSUFFICIENT_HUMAN_CALIBRATION'});tok=sr.register_final_producer_review(r,board());sr.commit_final_producer(tok,board());self.assertEqual(sr.p8_ready_gate()['status'],'PASS');self.assertTrue(sr.creative_lock()['locked'])
 def test_real_elite_human_review_unlocks_fixture(self):
  sr=seed(NexMindSupremeShowrunnerP8('P',{'topic':'x'}));r=FinalExecutiveProducer(P()).review('P',{'topic':'x'},story(),sr.state,board(),calibration={'status':'INSUFFICIENT_HUMAN_CALIBRATION'});tok=sr.register_final_producer_review(r,board());sr.commit_final_producer(tok,board());self.assertEqual(sr.register_human_creative_review(human())['status'],'PASS');self.assertEqual(sr.p8_ready_gate()['status'],'PASS');self.assertTrue(sr.creative_lock()['locked'])
 def test_weak_human_review_is_still_rejected_by_human_gate(self):
  sr=seed(NexMindSupremeShowrunnerP8('P',{'topic':'x'}));x=human();x['scores']['commercial_believability']=8.5;self.assertEqual(sr.register_human_creative_review(x)['status'],'FAIL')
 def test_council_reports_calibration_without_mutating_creative_verdict(self):
  sr=seed(NexMindSupremeShowrunnerP8('P',{'topic':'x'}));c=CreativeCouncilP8(sr,FinalExecutiveProducer(P()),HumanCalibrationRegistry());rr=c.final_review(story(),board(),multimodal_evidence={'status':'MISSING','artifacts':[]});self.assertEqual(rr['calibration']['status'],'INSUFFICIENT_HUMAN_CALIBRATION');self.assertEqual(rr['review']['verdict'],'ACCEPT');c.commit_review(rr,board());d=FinalProductionDossierCompiler().compile(board(),rr['review']);self.assertEqual(d['creative_lock_eligibility'],'ELIGIBLE');self.assertEqual(d['unresolved_departments'],[])

if __name__=='__main__':unittest.main(verbosity=2)
