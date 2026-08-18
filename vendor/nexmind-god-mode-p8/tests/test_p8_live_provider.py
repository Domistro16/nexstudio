import os,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from nexmind_god_mode.live_provider import RoleRouter
from nexmind_god_mode.provider_schemas import SCHEMAS
class T(unittest.TestCase):
 def test_final_producer_route_is_exact(self):
  old=dict(os.environ)
  try:
   os.environ['NEXMIND_REVIEW_MODEL']='test-review-model';os.environ['NEXMIND_REVIEW_BASE_URL']='https://router.invalid/v1';os.environ['NEXMIND_REVIEW_INPUT_MODALITIES']='images,audio';os.environ['NEXMIND_REVIEW_AUDIO_INPUT_MODE']='chat_input_audio';r=RoleRouter().resolve('final_producer');self.assertEqual((r.provider,r.model,r.role),('runtime','test-review-model','IndependentFinalExecutiveProducer'))
  finally:os.environ.clear();os.environ.update(old)
 def test_final_producer_schema_is_strict_and_has_no_overall_score(self):
  s=SCHEMAS['final_producer'];self.assertFalse(s['additionalProperties']);self.assertNotIn('overall_score',s['properties']);self.assertIn('craft_scores',s['required']);self.assertIn('taste_judgments',s['required'])
if __name__=='__main__':unittest.main(verbosity=2)
