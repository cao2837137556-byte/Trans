import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from fixtures import matrix, metrics, synthetic_manifest, row, source_fixture, trace


class ScopeAndAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.args = synthetic_manifest(self.root)
        self.manifest = matrix.read(self.args.manifest)

    def real_authorization(self):
        self.manifest['synthetic_only'] = False
        matrix.write(self.args.manifest, self.manifest)
        auth = dict(schema='dense-reference-ab-stage-authorization-v1', status='AUTHORIZED',
                    scope=matrix.STAGE_SCOPE, allow_target_evaluation=True,
                    protocol_amendment_confirmed=True, evaluated_pools=list(matrix.AB_POOLS),
                    deferred_pool=matrix.THIRD_POOL, evidence='SYNTHETIC UNIT TEST ONLY',
                    manifest_sha256=matrix.sha(self.args.manifest),
                    source_cal_result_sha256=matrix.sha(self.args.source_cal_result))
        self.args.synthetic_dry_run = False
        self.args.authorization = str(self.root/'auth.json')
        matrix.write(self.args.authorization, auth)
        return auth

    def test_no_authorization_refuses_before_target_loading(self):
        self.real_authorization()
        self.args.authorization = None
        with patch.object(matrix.Inputs, 'dataset', side_effect=AssertionError('target loaded')) as load:
            with self.assertRaisesRegex(ValueError, 'AB_STAGE_TARGET_AUTHORIZATION_REQUIRED'):
                matrix.run(self.args)
        load.assert_not_called()
        self.assertFalse((self.root/'output').exists())

    def test_prior_full_matrix_authorization_is_not_stage_authorization(self):
        auth = self.real_authorization()
        auth.update(schema='dense-reference-matrix-authorization-v1', scope='REGISTERED_DENSE_MATRIX')
        matrix.write(self.args.authorization, auth)
        with patch.object(matrix.Inputs, 'dataset') as load:
            with self.assertRaisesRegex(ValueError, 'AB_STAGE_TARGET_AUTHORIZATION_REQUIRED'):
                matrix.run(self.args)
        load.assert_not_called()

    def test_scope_amendment_and_exact_pools_are_required(self):
        valid = self.real_authorization()
        for field, value in [('protocol_amendment_confirmed', False),
                             ('evaluated_pools', ['CIC_DEV']), ('deferred_pool', None),
                             ('manifest_sha256', '0'*64), ('source_cal_result_sha256', '0'*64)]:
            with self.subTest(field=field):
                auth = dict(valid, **{field: value})
                matrix.write(self.args.authorization, auth)
                with self.assertRaisesRegex(ValueError, 'AB_STAGE_TARGET_AUTHORIZATION_REQUIRED'):
                    matrix.run(self.args)

    def test_manifest_cannot_claim_full_matrix_ready_or_remove_deferred_pool(self):
        for field, value in [('full_matrix_ready', True),
                             ('original_registered_matrix_complete', True),
                             ('third_pool_deferred', {}), ('evaluation_scope', 'REGISTERED_DENSE_MATRIX'),
                             ('pools', self.manifest['pools'][:1])]:
            with self.subTest(field=field):
                changed = copy.deepcopy(self.manifest)
                changed[field] = value
                with self.assertRaises(ValueError):
                    matrix.validate_stage_scope(changed)

    def test_stage_ready_is_required_before_production_target_loading(self):
        self.manifest['stage_matrix_ready'] = False
        self.real_authorization()
        with patch.object(matrix.Inputs, 'dataset') as load:
            with self.assertRaisesRegex(ValueError, 'AB_STAGE_MATERIALIZATION_REQUIRED'):
                matrix.run(self.args)
        load.assert_not_called()

    def test_synthetic_flag_cannot_accept_production_manifest(self):
        self.manifest['synthetic_only'] = False
        matrix.write(self.args.manifest, self.manifest)
        with patch.object(matrix.Inputs, 'dataset') as load:
            with self.assertRaisesRegex(ValueError, 'SYNTHETIC_CANNOT_LOAD_REAL_TARGETS'):
                matrix.run(self.args)
        load.assert_not_called()

    def test_synthetic_metadata_must_attest_fixture_before_score_loading(self):
        import gzip
        import json
        spec = self.manifest['pools'][0]['query']['rows']
        path = self.root/spec['path']
        with gzip.open(path, 'rt', encoding='utf-8') as stream:
            rows = [json.loads(line) for line in stream]
        rows[0].pop('synthetic_fixture')
        with gzip.open(path, 'wt', encoding='utf-8') as stream:
            for value in rows:
                stream.write(json.dumps(value)+'\n')
        spec['sha256'] = matrix.sha(path)
        matrix.write(self.args.manifest, self.manifest)
        with patch.object(matrix.Inputs, 'dataset') as load:
            with self.assertRaisesRegex(ValueError, 'SYNTHETIC_FIXTURE_METADATA_REQUIRED'):
                matrix.run(self.args)
        load.assert_not_called()

    def test_corrupt_input_stops_with_preserved_exception_state(self):
        with (self.root/'CIC_DEV.npz').open('ab') as stream:
            stream.write(b'corruption')
        with self.assertRaisesRegex(ValueError, 'INPUT_SHA256'):
            matrix.run(self.args)
        status = matrix.read(self.root/'output/status.json')
        self.assertEqual(status['status'], 'EXCEPTION_STOP')
        self.assertTrue(status['preserve_scene'])
        self.assertFalse((self.root/'output/RESULT.json').exists())

    def test_synthetic_stage_completes_all_cells_and_keeps_third_pool_missing(self):
        result = matrix.run(self.args)
        self.assertEqual(result['status'], 'AB_STAGE_COMPLETE_THIRD_POOL_PENDING')
        self.assertEqual(result['technical_status'], 'COMPLETE')
        self.assertFalse(result['original_registered_matrix_complete'])
        self.assertFalse(result['full_matrix_ready'])
        self.assertNotEqual(result['scientific_status'], 'PASS')
        self.assertEqual(result['original_registered_matrix_scientific_status'],
                         'NOT_EVALUATED_MISSING_THIRD_POOL')
        self.assertEqual(result['pools'][matrix.THIRD_POOL]['evaluated'], False)
        self.assertEqual(result['missing_pools'], [matrix.THIRD_POOL])
        self.assertEqual(result['model_forward_calls'], 0)
        self.assertEqual(result['training_updates'], 0)
        self.assertEqual(result['threshold_refit_calls'], 0)
        self.assertFalse(result['recall99_threshold_selection'])
        self.assertEqual(len(list((self.root/'output').rglob('*decisions.npz'))), 24)
        for pool in matrix.AB_POOLS:
            self.assertEqual(result['pools'][pool]['completeness']['evaluated_arm_epsilon_cells'], 12)

    def test_even_passing_ab_stage_cannot_promote_missing_full_matrix(self):
        registered_gate = metrics.target_gate
        def passing_gate(report, epsilon):
            value = registered_gate(report, epsilon)
            value['status'] = 'PASS'
            value['attack']['status'] = 'PASS'
            return value
        with patch.object(metrics, 'target_gate', side_effect=passing_gate):
            result = matrix.run(self.args)
        self.assertEqual(result['stage_scientific_status'], 'PASS')
        self.assertEqual(result['scientific_status'], 'NOT_EVALUABLE')
        self.assertEqual(result['original_registered_matrix_scientific_status'],
                         'NOT_EVALUATED_MISSING_THIRD_POOL')
        self.assertFalse(result['original_registered_matrix_complete'])


class ScoresAndFormulaTests(unittest.TestCase):
    def test_persisted_scores_reproduce_all_seed_and_ensemble_decisions(self):
        prep, source = source_fixture()
        points = matrix.source_workpoints(source, {arm: prep for arm in ('R-B2', 'R-DENSE')})
        rows = [row('n'), row('a', 1)]
        logits = np.array([[0.05, 0.1, 0.0], [0.2, 0.3, -0.1]], dtype=np.float64)
        data = dict(rows=rows, logits=logits)
        cuts, ec, scales = np.array([0., 0., 0.]), 0., np.array([1., 1., 1.])
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            result = matrix.evaluate_pool('CIC_DEV', data, {a: trace(2, 1.) for a in matrix.ARMS},
                        points, cuts, ec, scales, {'*': dict(cutoff=2.)}, folder)
            self.assertEqual(result['completeness']['evaluated_arm_epsilon_cells'], 12)
            for path in folder.glob('*decisions.npz'):
                with np.load(path, allow_pickle=False) as saved:
                    self.assertEqual(saved['uid'].tolist(), [r['uid'] for r in rows])
                    self.assertEqual(saved['seeds'].tolist(), [27, 127, 227])
                    self.assertEqual(saved['raw_logits'].tobytes(), logits.tobytes())
                    expected = matrix.core.apply_correction(logits, saved['support'], scales,
                                                            float(saved['selected_lambda']))
                    self.assertEqual(saved['corrected_logits'].tobytes(), expected.tobytes())
                    np.testing.assert_array_equal(saved['base'],
                        matrix.decisions(saved['raw_logits'], saved['cuts'], float(saved['ensemble_cut'])))
                    np.testing.assert_array_equal(saved['corrected'],
                        matrix.decisions(saved['corrected_logits'], saved['cuts'], float(saved['ensemble_cut'])))
                    self.assertEqual(saved['raw_ensemble_logits'].tobytes(),
                                     matrix.core.ordered_ensemble(logits).tobytes())
                    self.assertEqual(saved['corrected_ensemble_logits'].tobytes(),
                                     matrix.core.ordered_ensemble(expected).tobytes())

    def test_registered_evaluate_pool_metrics_and_decisions_are_unchanged(self):
        original_path = Path(__file__).with_name('original_matrix_frozen.py')
        spec = importlib.util.spec_from_file_location('registered_matrix_for_parity', original_path)
        original = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(original)
        prep, source = source_fixture()
        points = matrix.source_workpoints(source, {a: prep for a in ('R-B2', 'R-DENSE')})
        rows = [row('normal'), row('attack', 1)]
        data = dict(rows=rows, logits=np.array([[0.05, 0.1, 0.0], [0.2, 0.3, -0.1]]))
        traces = {a: trace(2, 0.5 if a == 'R-DENSE-WRONG' else 1.) for a in matrix.ARMS}
        with tempfile.TemporaryDirectory() as tmp:
            first, second = Path(tmp)/'old', Path(tmp)/'new'
            first.mkdir()
            second.mkdir()
            args = ('CIC_DEV', data, traces, points, [0.,0.,0.], 0., [1.,1.,1.], {'*':dict(cutoff=2.)})
            expected = original.evaluate_pool(*args, first)
            actual = matrix.evaluate_pool(*args, second)
            self.assertEqual(actual, expected)
            for path in first.glob('*decisions.npz'):
                with np.load(path, allow_pickle=False) as before, np.load(second/path.name, allow_pickle=False) as after:
                    for field in ('uid', 'base', 'corrected'):
                        self.assertEqual(before[field].tobytes(), after[field].tobytes())


if __name__ == '__main__':
    unittest.main()
