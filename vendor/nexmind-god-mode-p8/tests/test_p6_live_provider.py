import os,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from nexmind_god_mode.live_provider import RoleRouter,LiveCreativeModelProvider
from nexmind_god_mode.provider_schemas import SCHEMAS
class P6LiveProviderTests(unittest.TestCase):
    def test_p6_exact_routes(self):
        old=dict(os.environ)
        try:
            os.environ.pop('NEXMIND_MOTION_PERFORMANCE_DIRECTOR_PROVIDER',None);os.environ.pop('NEXMIND_MOTION_PERFORMANCE_DIRECTOR_MODEL',None)
            os.environ.pop('NEXMIND_EXECUTIVE_PRODUCER_PROVIDER',None);os.environ.pop('NEXMIND_EXECUTIVE_PRODUCER_MODEL',None)
            os.environ.pop('NEXMIND_SUPREME_SHOWRUNNER_PROVIDER',None);os.environ.pop('NEXMIND_SUPREME_SHOWRUNNER_MODEL',None)
            os.environ['NEXMIND_CREATIVE_MODEL']='test-creative-model';os.environ['NEXMIND_REVIEW_MODEL']='test-review-model';os.environ['NEXMIND_REVIEW_BASE_URL']='https://router.invalid/v1'
            r=RoleRouter()
            self.assertEqual((r.resolve('motion_performance').provider,r.resolve('motion_performance').model),('runtime','test-creative-model'))
            self.assertEqual((r.resolve('motion_review').provider,r.resolve('motion_review').model),('runtime','test-review-model'))
            self.assertEqual((r.resolve('showrunner_select_motion').provider,r.resolve('showrunner_select_motion').model),('runtime','test-review-model'))
        finally:
            os.environ.clear();os.environ.update(old)
    def test_motion_schema_is_strict_nested(self):
        s=SCHEMAS['motion_performance']; self.assertFalse(s['additionalProperties']); a=s['properties']['candidates']['items']['properties']['actions']['items']; self.assertFalse(a['additionalProperties']); self.assertIn('HANDOFF_PLACE_AND_TAKE',a['properties']['requested_verb']['enum'])
    def test_motion_transport_uses_schema(self):
        os.environ['NEXMIND_API_KEY']='x'; os.environ['NEXMIND_CREATIVE_MODEL']='test-creative-model'; p=LiveCreativeModelProvider(); route=RoleRouter().resolve('motion_performance'); q=p._responses_payload('motion_performance',{'production_id':'P'},route); self.assertEqual(q['model'],'test-creative-model'); self.assertTrue(q['text']['format']['strict'])
if __name__=='__main__':unittest.main(verbosity=2)
