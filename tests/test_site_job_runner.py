"""The dispatcher reports a useful reason when a board scene fails its gate."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

module_path = Path(__file__).resolve().parents[1] / 'services/studio-family-engines/site_job_runner.py'
spec = importlib.util.spec_from_file_location('site_job_runner', module_path)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class SiteJobFailures(unittest.TestCase):
    def test_art_rejection_reports_the_real_cause(self):
        for reason in ['semantic-loose', 'semantic-art', 'generic-art']:
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as directory:
                job = Path(directory)
                (job / 'job.log').write_text(f'--- P8 dispatch ---\nWHITEBOARD_JOB_FAILED: GATE_REFUSED 16:9:{reason}:5:toothpick\n')
                code, message = runner._engine_failure(job, 1)
                self.assertEqual(code, 'BOARD_SCENE_ART_REFUSED')
                self.assertIn('artwork', message)
                self.assertIn('narration and settings are saved', message)
                self.assertNotIn('engine exited', message)

    def test_layout_rejection_does_not_report_an_opaque_engine_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            job = Path(directory)
            (job / 'job.log').write_text('--- P8 dispatch ---\nWHITEBOARD_JOB_FAILED: GATE_REFUSED 1:1:overlap/off-frame:2:clay,slab\n')
            code, message = runner._engine_failure(job, 1)
            self.assertEqual(code, 'BOARD_SCENE_LAYOUT_REFUSED')
            self.assertIn('overlap', message)
            self.assertIn('narration and settings are saved', message)
            self.assertNotIn('engine exited', message)

    def test_gate_failure_code_is_the_gate_rule_not_the_aspect(self):
        self.assertEqual(runner._gate_code('16x9:b09:ILLUSTRATION_COLLIDES_TEXT:e1_highlight2:3'),
                         'ILLUSTRATION_COLLIDES_TEXT')
        self.assertEqual(runner._gate_code('TYPE_LAYOUT_UNSATISFIABLE'), 'TYPE_LAYOUT_UNSATISFIABLE')
        self.assertEqual(runner._gate_code('9x16:b01:legible'), 'ENGINE_QA_GATE_FAILED')

    def test_a_previous_layout_failure_does_not_mask_the_current_narration_error(self):
        with tempfile.TemporaryDirectory() as directory:
            job = Path(directory)
            (job / 'job.log').write_text('--- P8 dispatch ---\nGATE_REFUSED overlap/off-frame\n--- P8 dispatch ---\nNARRATION_PROVIDER_UNAVAILABLE\n')
            code, _ = runner._engine_failure(job, 1)
            self.assertEqual(code, 'NARRATION_PROVIDER_UNAVAILABLE')


if __name__ == '__main__':
    unittest.main()
