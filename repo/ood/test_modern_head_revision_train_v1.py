"""Incremental P1/P3 regression checks using generated rows and real LightGBM."""
import argparse
import copy
import hashlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
import numpy as np
import modern_head_models_v1 as m
import modern_head_train_v1 as t
from test_modern_head_models_v1 import configuration, fixture, Progress


NATIVE_OBSERVATIONS = []


class NativeStopTests(unittest.TestCase):
    def test_constant_features_save_and_replay_native_stop(self):
        config = configuration(); rows, values, q, norm, ix = fixture()
        values[:] = 0; q[:] = 0
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)/'constant'
            model = t.train(config, rows, values, q, norm, ix, 'LightGBM', 27, out, Progress(), True)
            endpoint = m.c.read(out/'endpoint.json'); log = m.c.read(out/'training_log.json')
            for key in ('requested_rounds', 'callback_iterations', 'effective_tree_iterations', 'native_stop'):
                self.assertEqual(endpoint[key], log[key], key)
            self.assertEqual(endpoint['requested_rounds'], 3)
            self.assertEqual(endpoint['effective_tree_iterations'], 1)
            self.assertTrue(endpoint['native_stop']); self.assertFalse(log['early_stopping'])
            self.assertTrue(np.array_equal(m.scores(model, 'LightGBM', values, q, ix, norm),
                m.scores(t.load(out, 'LightGBM', 27, config), 'LightGBM', values, q, ix, norm)))
            NATIVE_OBSERVATIONS.append(dict(fixture='constant_features_endpoint',
                **{key:endpoint[key] for key in ('requested_rounds', 'callback_iterations',
                  'effective_tree_iterations', 'native_stop', 'versions')}))

    def test_real_lightgbm_500_requests_are_distinct_from_retained_trees(self):
        # Exercise the production request count on 64 generated rows only. The
        # public trainer's <=3 synthetic budget is unchanged; no real FIT opens.
        config = configuration(); config['training']['lightgbm']['num_boost_round'] = 500
        rows, values, q, norm, ix = fixture(); values[:] = 0; q[:] = 0
        _, labels, weights, _ = t.fit_inputs(rows, values, q, norm, ix, True)
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            model, details = t._train_tree(config, values, q, norm, ix, labels, weights, 27, out, Progress())
            log = m.c.read(out/'training_log.json')
            self.assertEqual(details['requested_rounds'], 500)
            # Actual supported 4.6.0 Python API completes callbacks after the
            # native booster stops adding trees; this corrects review P1's premise.
            self.assertEqual(details['callback_iterations'], 500)
            self.assertEqual(details['effective_tree_iterations'], 1)
            self.assertTrue(details['native_stop']); self.assertEqual(len(log['rows']), 500)
            self.assertEqual(model.num_trees(), 1)
            NATIVE_OBSERVATIONS.append(dict(fixture='constant_features_500_requested',
                **{key:details[key] for key in ('requested_rounds', 'callback_iterations',
                  'effective_tree_iterations', 'native_stop')}, versions=t.versions('LightGBM')))


class ReusePreconditionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import query_tail_train_v2 as original
        cls.temporary = tempfile.TemporaryDirectory(); cls.base = Path(cls.temporary.name)
        cls.config = configuration()
        cls.rows, cls.values, cls.q, cls.norm, cls.ix = fixture(32)
        hp = cls.config['training']
        optimizer = {key:value for key,value in hp['optimizer_mlp'].items() if key not in ('foreach', 'amsgrad')}
        cls.design = dict(synthetic_only=True, training=dict(epochs=hp['epochs'], batch_size=hp['batch_size'],
            tail_negatives_per_batch=128, optimizer_parent_values=optimizer, diagnostics=dict(enabled=False)))
        cls.original = cls.base/'original'
        original.train(cls.design, cls.rows, cls.values, cls.q, cls.norm, cls.ix,
            np.zeros(len(cls.rows), dtype=np.int64), 'QUERY_BCE', 27, cls.original, Progress(), synthetic=True)
        _, _, _, cls.identity = t.fit_inputs(cls.rows, cls.values, cls.q, cls.norm, cls.ix, True)

    @classmethod
    def tearDownClass(cls): cls.temporary.cleanup()

    def setUp(self):
        self.folder = self.base/self._testMethodName
        shutil.copytree(self.original, self.folder)
        self.proof = dict(status='PASS', runtime_compatible=True,
            runtime_fingerprint=dict(synthetic_generated_test=True),
            score_and_decision_bitwise=dict(CAL=True, CIC_DEV=True, UNSW_DEV=True),
            original_head_sha256=m.c.sha(self.folder/'head.npz'),
            original_endpoint_sha256=m.c.sha(self.folder/'endpoint.json'),
            original_design_digest=m.c.digest(self.design), seed=27,
            ordered_uid_sha256=self.identity['ordered_uid_sha256'])

    def check(self, proof=None, design=None):
        return t.reuse_mlp_preconditions(self.folder, self.design if design is None else design,
            self.config, self.rows, self.values, self.q, self.norm, self.ix,
            self.proof if proof is None else proof)

    def alter_endpoint(self, change):
        endpoint = m.c.read(self.folder/'endpoint.json'); change(endpoint)
        m.c.write(self.folder/'endpoint.json', endpoint, replace=True)
        (self.folder/'SHA256SUMS').unlink(); m.c.seal(self.folder)
        self.proof['original_endpoint_sha256'] = m.c.sha(self.folder/'endpoint.json')

    def test_complete_check_is_read_only_and_adoption_preserves_model(self):
        before = {str(p):m.c.sha(p) for p in self.folder.iterdir() if p.is_file()}
        result = self.check(); self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['identity'], self.identity)
        self.assertEqual(before, {str(p):m.c.sha(p) for p in self.folder.iterdir() if p.is_file()})
        output = self.base/'adopted'
        t.adopt_mlp(self.folder, self.design, self.config, self.rows, self.values,
            self.q, self.norm, self.ix, output, self.proof)
        self.assertEqual((self.folder/'head.npz').read_bytes(), (output/'head.npz').read_bytes())

    def test_missing_runtime_proof_falls_back_without_output(self):
        proof = dict(self.proof, runtime_fingerprint={})
        result = self.check(proof); self.assertEqual(result['status'], 'TRAIN_REQUIRED')
        self.assertEqual(result['reason'], 'MLP_REUSE_PROOF_REQUIRED')
        output = self.base/'rejected'
        with self.assertRaises(t.ReuseIneligible) as error:
            t.adopt_mlp(self.folder, self.design, self.config, self.rows, self.values,
                self.q, self.norm, self.ix, output, proof)
        self.assertEqual(error.exception.reason, result['reason']); self.assertFalse(output.exists())

    def test_missing_metadata_falls_back_instead_of_keyerror(self):
        self.alter_endpoint(lambda endpoint:endpoint.pop('order_hashes'))
        result = self.check(); self.assertEqual(result['status'], 'TRAIN_REQUIRED')
        self.assertEqual(result['reason'], 'MLP_REUSE_SOURCE_METADATA_MISSING:order_hashes')

    def test_recipe_incompatibility_falls_back(self):
        design = copy.deepcopy(self.design); design['training']['epochs'] = 40
        self.assertEqual(self.check(design=design), dict(status='TRAIN_REQUIRED', reason='MLP_REUSE_RECIPE'))

    def test_fit_identity_incompatibility_falls_back(self):
        self.alter_endpoint(lambda endpoint:endpoint.update(normalizer_digest='0'*64))
        self.assertEqual(self.check(), dict(status='TRAIN_REQUIRED', reason='MLP_REUSE_IDENTITY:normalizer_digest'))

    def test_budget_incompatibility_falls_back(self):
        self.alter_endpoint(lambda endpoint:endpoint.update(updates=1))
        self.assertEqual(self.check(), dict(status='TRAIN_REQUIRED', reason='MLP_REUSE_ENDPOINT_BUDGET'))

    def test_source_seal_corruption_is_hard_failure(self):
        with (self.folder/'head.npz').open('ab') as stream: stream.write(b'corruption')
        with self.assertRaisesRegex(RuntimeError, 'IDENTITY') as error: self.check()
        self.assertNotIsInstance(error.exception, t.ReuseIneligible)

    def test_endpoint_model_hash_disagreement_is_hard_failure(self):
        self.alter_endpoint(lambda endpoint:endpoint.update(head_sha256='0'*64))
        with self.assertRaisesRegex(RuntimeError, 'IDENTITY') as error: self.check()
        self.assertNotIsInstance(error.exception, t.ReuseIneligible)

    def replace_model(self, change):
        with np.load(self.folder/'head.npz', allow_pickle=False) as saved:
            arrays = {name:saved[name].copy() for name in saved.files}
        change(arrays)
        (self.folder/'head.npz').unlink(); m.c.save_arrays(self.folder/'head.npz', **arrays)
        self.alter_endpoint(lambda endpoint:endpoint.update(head_sha256=m.c.sha(self.folder/'head.npz')))
        self.proof['original_head_sha256'] = m.c.sha(self.folder/'head.npz')

    def test_model_shape_incompatibility_falls_back(self):
        def wrong_shape(arrays):
            name = next(iter(arrays)); arrays[name] = arrays[name][:1]
        self.replace_model(wrong_shape)
        self.assertEqual(self.check(), dict(status='TRAIN_REQUIRED', reason='MLP_REUSE_HEAD_SHAPES'))

    def test_nonfinite_model_is_hard_failure(self):
        # np.inf is retained by save_arrays' equality check; it is still invalid
        # for an endpoint even when the archive hashes consistently describe it.
        def nonfinite(arrays): arrays[next(iter(arrays))].flat[0] = np.inf
        self.replace_model(nonfinite)
        with self.assertRaisesRegex(RuntimeError, 'MLP_REUSE_NONFINITE') as error: self.check()
        self.assertNotIsInstance(error.exception, t.ReuseIneligible)

    def test_initial_model_corruption_is_hard_failure(self):
        with (self.folder/'initial.npz').open('ab') as stream: stream.write(b'corruption')
        with self.assertRaisesRegex(RuntimeError, 'IDENTITY') as error: self.check()
        self.assertNotIsInstance(error.exception, t.ReuseIneligible)

    def test_missing_design_metadata_falls_back(self):
        self.assertEqual(self.check(design={}), dict(status='TRAIN_REQUIRED', reason='MLP_REUSE_RECIPE'))

    def test_replay_identity_incompatibility_falls_back(self):
        proof = dict(self.proof, seed=127)
        self.assertEqual(self.check(proof), dict(status='TRAIN_REQUIRED', reason='MLP_REUSE_PROOF_REQUIRED'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    log = io.StringIO(); suite = unittest.defaultTestLoader.loadTestsFromModule(__import__(__name__))
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    text = log.getvalue(); print(text, end='')
    if args.output:
        args.output.mkdir(parents=True, exist_ok=False)
        (args.output/'unittest.log').write_text(text, encoding='utf-8')
        m.c.write(args.output/'result.json', dict(status='PASS' if result.wasSuccessful() else 'FAIL',
            tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
            skipped=len(result.skipped), native_observations=NATIVE_OBSERVATIONS,
            log_sha256=m.c.sha(args.output/'unittest.log'), source_sha256=m.c.sha(__file__),
            train_source_sha256=m.c.sha(Path(t.__file__)), production_training=False))
    raise SystemExit(0 if result.wasSuccessful() else 1)
