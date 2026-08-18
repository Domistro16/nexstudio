import pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from nexmind_god_mode.multimodal_evidence import build_multimodal_evidence
from nexmind_god_mode.rejection_feedback import RejectionFeedbackLedger
class T(unittest.TestCase):
 def test_multimodal_evidence_needs_visual_and_audio(self):
  v={'artifact_id':'v','kind':'CONTACT_SHEET','sha256':'a'*64,'source':'render/contact.png'};self.assertEqual(build_multimodal_evidence([v])['status'],'MISSING');a={'artifact_id':'a','kind':'AUDIO_MIX','sha256':'b'*64,'source':'render/mix.wav'};self.assertEqual(build_multimodal_evidence([v,a])['status'],'COMPLETE')
 def test_bad_hash_cannot_fake_render_evidence(self):
  self.assertEqual(build_multimodal_evidence([{'artifact_id':'v','kind':'VIDEO','sha256':'fake','source':'x'}],audio_expected=False)['status'],'MISSING')
 def test_feedback_ledger_is_structured_and_non_mutating(self):
  r={'verdict':'REVISE','issues':['weak payoff'],'revision_plan':['rebuild payoff'],'hard_gates':[{'dimension':'FINAL_PAYOFF','status':'FAIL'}],'taste_judgments':{'originality':{'score':7.5}}};l=RejectionFeedbackLedger();x=l.record_machine('P',0,r);self.assertEqual(x['hard_failures'],['FINAL_PAYOFF']);self.assertEqual(x['taste_low'],['originality']);r['issues'][0]='mutated';self.assertEqual(l.records[0]['issues'][0],'weak payoff')
if __name__=='__main__':unittest.main(verbosity=2)
