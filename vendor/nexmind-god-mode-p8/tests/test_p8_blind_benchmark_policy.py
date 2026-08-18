import json, os, unittest
from pathlib import Path
from nexmind_god_mode.provider import RecordedModelProvider
from nexmind_god_mode.benchmark_policy import assert_commercial_brain_benchmark_eligible, BenchmarkEligibilityError
from nexmind_god_mode.live_provider import LiveCreativeModelProvider

class BlindBenchmarkPolicyTests(unittest.TestCase):
    def test_recorded_provider_cannot_be_commercial_benchmark(self):
        with self.assertRaises(BenchmarkEligibilityError):
            assert_commercial_brain_benchmark_eligible(RecordedModelProvider({}))

    def test_contract_fixture_path_cannot_be_commercial_benchmark(self):
        class P: pass
        with self.assertRaises(BenchmarkEligibilityError):
            assert_commercial_brain_benchmark_eligible(P(),'tests/fixtures/contract_regression_only/case.json')

    def test_live_candidate_blinding_hides_original_ids_and_maps_back(self):
        p=LiveCreativeModelProvider()
        req={'production_id':'P','candidates':[{'candidate':{'candidate_id':'V1','idea':'a'}},{'candidate':{'candidate_id':'V2','idea':'b'}},{'candidate':{'candidate_id':'V3','idea':'c'}}]}
        blinded,forward,reverse=p._blind_showrunner_candidates('showrunner_select',req)
        raw=json.dumps(blinded)
        self.assertNotIn('"V1"',raw); self.assertNotIn('"V2"',raw); self.assertNotIn('"V3"',raw)
        self.assertEqual(3,len(blinded['candidates']))
        chosen=p._candidate_id(blinded['candidates'][0])
        out=p._unblind_showrunner_result({'selected_candidate_id':chosen,'why':'x','tradeoffs':[],'rejected_alternatives':[]},reverse)
        self.assertIn(out['selected_candidate_id'],{'V1','V2','V3'})
        self.assertEqual('RANDOMIZED_OPAQUE_LIVE_SELECTION_V2',p.candidate_order_audits[-1]['policy'])

if __name__=='__main__': unittest.main()
