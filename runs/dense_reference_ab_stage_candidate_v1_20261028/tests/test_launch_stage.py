import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fixtures import synthetic_manifest, matrix
import launch_stage as launch


class LauncherGates(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.package = self.root/'package'
        self.package.mkdir()
        self.fixture = synthetic_manifest(self.package)
        self.manifest = matrix.read(self.fixture.manifest)
        self.manifest['synthetic_only'] = False
        matrix.write(self.fixture.manifest, self.manifest)
        self.package_sha = 'a'*64
        self.approval = dict(schema='dense-reference-ab-stage-authorization-v1', status='AUTHORIZED',
            scope=matrix.STAGE_SCOPE, allow_target_evaluation=True, protocol_amendment_confirmed=True,
            evaluated_pools=list(matrix.AB_POOLS), deferred_pool=matrix.THIRD_POOL,
            evidence='SYNTHETIC UNIT TEST ONLY', package_sha256=self.package_sha,
            manifest_sha256=matrix.sha(self.fixture.manifest),
            source_cal_result_sha256=matrix.sha(self.fixture.source_cal_result),
            total_wall_seconds=7200, retries=0)
        self.auth_path = self.package/'auth.json'
        matrix.write(self.auth_path, self.approval)
        self.output = self.root/'science'
        self.argv = ['--package', str(self.package), '--assets-root', str(self.package),
            '--manifest', self.fixture.manifest, '--source-cal-result', self.fixture.source_cal_result,
            '--approval-file', str(self.auth_path), '--output', str(self.output)]

    def test_package_wall_and_retry_contract_before_target_assembly(self):
        for field, bad in [('package_sha256', 'wrong'), ('total_wall_seconds', 7201), ('retries', 1),
                           ('total_wall_seconds', True), ('retries', False)]:
            with self.subTest(field=field, value=bad):
                invalid = dict(self.approval, **{field: bad})
                with self.assertRaises(RuntimeError):
                    launch.validate_stage_approval(self.manifest, matrix.sha(self.fixture.manifest),
                        matrix.sha(self.fixture.source_cal_result), invalid, self.package_sha)

    def test_missing_approval_preserves_failure_without_target_assembly(self):
        self.auth_path.unlink()
        with patch.object(launch, 'verify_package', return_value=self.package_sha), \
             patch.object(launch, 'assemble_view') as target_view, \
             patch.object(launch, 'run_stage') as worker:
            self.assertEqual(launch.main(self.argv), 70)
        target_view.assert_not_called()
        worker.assert_not_called()
        status = matrix.read(self.output/'status.json')
        self.assertEqual(status['status'], 'EXCEPTION_STOP')
        self.assertTrue(status['evidence_preserved'])
        self.assertFalse((self.output/'readonly_view').exists())

    def test_old_scope_cannot_assemble_target_view(self):
        self.approval['scope'] = 'REGISTERED_DENSE_MATRIX'
        matrix.write(self.auth_path, self.approval)
        with patch.object(launch, 'verify_package', return_value=self.package_sha), \
             patch.object(launch, 'assemble_view') as target_view, \
             patch.object(launch, 'run_stage') as worker:
            self.assertEqual(launch.main(self.argv), 70)
        target_view.assert_not_called()
        worker.assert_not_called()

    def test_expected_numpy_module_must_use_verified_overlay_and_version(self):
        module = str(launch.EXPECTED_NUMPY_ROOT/'numpy/__init__.py')
        with patch.object(launch.np, '__version__', '2.0.1'), patch.object(launch.np, '__file__', module):
            self.assertEqual(launch.validate_numpy_runtime()['version'], '2.0.1')
        for version, path in [('1.26.4', module), ('2.0.1', str(self.root/'other/numpy/__init__.py'))]:
            with patch.object(launch.np, '__version__', version), patch.object(launch.np, '__file__', path):
                with self.assertRaisesRegex(RuntimeError, 'EXACT_NUMPY201'):
                    launch.validate_numpy_runtime()

    def test_resource_limits_spend_preflight_time_inside_total_budget(self):
        limits = launch.stage_limits(7200, 421)
        self.assertEqual(limits['wall_seconds'], 6779)
        self.assertEqual(limits['rss_bytes'], 8*1024**3)
        self.assertEqual(limits['output_bytes'], 2*1024**3)
        self.assertEqual(limits['min_free_bytes'], 12*1024**3)
        with self.assertRaisesRegex(RuntimeError, 'TOTAL_WALL_LIMIT'):
            launch.stage_limits(7200, 7200)
        with self.assertRaisesRegex(RuntimeError, 'TOTAL_WALL_BUDGET'):
            launch.stage_limits(7201, 0)

    def test_existing_output_never_overwritten(self):
        self.output.mkdir()
        (self.output/'keep').write_text('unchanged')
        with self.assertRaisesRegex(RuntimeError, 'FRESH_EXTERNAL_OUTPUT_REQUIRED'):
            launch.main(self.argv)
        self.assertEqual((self.output/'keep').read_text(), 'unchanged')

    def test_approved_synthetic_worker_scientific_fail_finishes_without_retry(self):
        (self.package/'config').mkdir()
        matrix.write(self.package/'config/RUNTIME_ASSET_MANIFEST.json', dict(files=[]))
        def fake_worker(argv, *, output, control, limits, env, stop_file, expected, notify):
            self.assertEqual(expected, ('AB_STAGE_COMPLETE_THIRD_POOL_PENDING',))
            self.assertEqual(env['OMP_NUM_THREADS'], '4')
            self.assertIn(str(launch.EXPECTED_NUMPY_ROOT), env['PYTHONPATH'])
            self.assertLessEqual(limits['wall_seconds'], 7200)
            output.mkdir()
            matrix.write(output/'RESULT.json', dict(status='AB_STAGE_COMPLETE_THIRD_POOL_PENDING',
                scientific_status='FAIL', stage_scientific_status='FAIL'))
            return dict(elapsed_seconds=1.)
        with patch.object(launch, 'verify_package', return_value=self.package_sha), \
             patch.object(launch, 'validate_numpy_runtime', return_value=dict(version='2.0.1')), \
             patch.object(launch, 'run_stage', side_effect=fake_worker) as worker:
            self.assertEqual(launch.main(self.argv), 0)
        self.assertEqual(worker.call_count, 1)
        final = matrix.read(self.output/'RESULT.json')
        self.assertEqual(final['status'], 'COMPLETE')
        self.assertEqual(final['scientific_status'], 'FAIL')
        self.assertFalse(final['original_registered_matrix_complete'])
        self.assertEqual(final['retries'], 0)
        self.assertEqual(final['new_source_cal_runs'], 0)
        self.assertEqual(final['model_forward_calls'], 0)


if __name__ == '__main__':
    unittest.main()
