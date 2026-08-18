import os,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from nexmind_god_mode.live_provider import RoleRouter,LiveCreativeModelProvider
from nexmind_god_mode.provider_schemas import SCHEMAS
class T(unittest.TestCase):
 def test_p7_routes(self):
  old=dict(os.environ)
  try:
   os.environ['NEXMIND_CREATIVE_MODEL']='test-creative-model';os.environ['NEXMIND_REVIEW_MODEL']='test-review-model';os.environ['NEXMIND_REVIEW_BASE_URL']='https://router.invalid/v1';r=RoleRouter();self.assertEqual((r.resolve('sound_direction').provider,r.resolve('sound_direction').model),('runtime','test-creative-model'));self.assertEqual(r.resolve('sound_review').model,'test-review-model');self.assertEqual(r.resolve('showrunner_select_sound').model,'test-review-model')
  finally:os.environ.clear();os.environ.update(old)
 def test_sound_schema_strict(self):self.assertFalse(SCHEMAS['sound_direction']['additionalProperties']);self.assertFalse(SCHEMAS['sound_direction']['properties']['candidates']['items']['properties']['events']['items']['additionalProperties'])
if __name__=='__main__':unittest.main(verbosity=2)
