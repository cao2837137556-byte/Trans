"""Generated-data checks; no parent cache, PCAP, target labels or model training run."""
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
import numpy as np
import torch
from torch.nn import functional as F
import modern_head_models_v1 as m
import modern_head_train_v1 as t


def configuration():
    config = dict(schema='modern-head-comparison-v1', families=list(m.FAMILIES), seeds=list(m.c.SEEDS),
                  training=m.default_training_config(), synthetic_only=True)
    config['training']['epochs'] = 2; config['training']['batch_size'] = 16
    config['training']['lightgbm']['num_boost_round'] = 3
    return config


def fixture(n=64):
    rng = np.random.RandomState(943)
    rows = [dict(uid='synthetic-%04d' % i, partition='LEARN', fit_role='FIT', use='QUERY',
                 device='device%d' % (i % 3), activity='activity%d' % (i % 5),
                 capture_id='capture%d' % (i % 7), session_id='session%d' % (i % 11),
                 component_id='component%d' % i, label=i % 2) for i in range(n)]
    values = rng.normal(size=(n, 794)).astype(np.float32)
    q = rng.uniform(size=(n, 14)).astype(np.float32)
    norm = (rng.normal(size=768), rng.uniform(.5, 2., size=768))
    return rows, values, q, norm, np.arange(n, dtype=np.int64)


class Progress:
    def __init__(self): self.ticks = []
    def tick(self, done, total): self.ticks.append((done, total))


class ObjectiveTests(unittest.TestCase):
    def test_tabm_member_loss_matches_explicit_loop(self):
        torch.manual_seed(8); z = torch.randn(7, 32, requires_grad=True)
        y = torch.tensor([0, 1, 1, 0, 1, 0, 1], dtype=torch.float32)
        w = np.arange(1., 8.)/40.
        actual = m.tabm_weighted_bce(z, y, w, 99)
        expected = torch.stack([m.k.objective(z[:, j], y, w, 99) for j in range(32)]).mean()
        self.assertTrue(torch.allclose(actual, expected, atol=1e-14, rtol=1e-14))
        ga, = torch.autograd.grad(actual, z, retain_graph=True)
        ge, = torch.autograd.grad(expected, z)
        self.assertTrue(torch.allclose(ga, ge, atol=1e-7, rtol=1e-6))

    def test_not_bce_of_averaged_probability(self):
        z = torch.tensor([[-8., 8.]*16, [-3., 9.]*16])
        y = torch.tensor([0., 1.]); w = np.array([.5, .5])
        member_loss = m.tabm_weighted_bce(z, y, w, 2)
        averaged_loss = m.k.objective(m.tabm_mean_probability_logit(z), y.double(), w, 2)
        self.assertGreater(float(member_loss-averaged_loss), 1.)

    def test_internal_score_equals_probability_mean(self):
        z = torch.linspace(-3, 9, 128).reshape(4, 32)
        expected = torch.logit(torch.sigmoid(z.double()).mean(1))
        self.assertTrue(torch.allclose(m.tabm_mean_probability_logit(z), expected, atol=1e-12, rtol=1e-12))

    def test_saturated_scores_stay_finite_ordered(self):
        z = torch.tensor([[-10000.]*32, [-1000.]*32, [1000.]*32, [10000.]*32])
        actual = m.tabm_mean_probability_logit(z)
        self.assertTrue(torch.equal(actual, z[:, 0].double()))
        self.assertTrue(bool(torch.isfinite(actual).all()))
        self.assertTrue(bool((actual[1:] > actual[:-1]).all()))

    def test_symmetric_extremes_are_zero(self):
        z = torch.tensor([[-10000., 10000.]*16])
        self.assertEqual(float(m.tabm_mean_probability_logit(z)[0]), 0.)

    def test_tree_weights_preserve_ratios_and_class_mass(self):
        rows, *_ = fixture(); w = m.k.weights(rows); scaled = m.lightgbm_weights(w)
        self.assertTrue(np.array_equal(scaled, len(rows)*w))
        self.assertAlmostEqual(scaled.mean(), 1.)
        for label in (0, 1):
            self.assertAlmostEqual(sum(scaled[i] for i,r in enumerate(rows) if r['label'] == label), len(rows)/2)

    def test_index_view_uses_original_weights_bitwise(self):
        rows, values, q, norm, ix = fixture()
        ix = ix[::-1]
        _, _, weights, identity = t.fit_inputs(rows, values, q, norm, ix, True)
        expected = m.k.weights([rows[int(i)] for i in ix])
        self.assertTrue(np.array_equal(weights, expected))
        self.assertEqual(identity['weight_sha256'], hashlib.sha256(expected.tobytes()).hexdigest())
        self.assertEqual(identity['ordered_uid_sha256'], hashlib.sha256(''.join(rows[int(i)]['uid']+'\n' for i in ix).encode()).hexdigest())


class IsolationTests(unittest.TestCase):
    def test_production_recipe_is_fixed(self):
        config = configuration(); config['synthetic_only'] = False; config['training'] = m.default_training_config()
        m.validate_config(config)
        for field, value in [('epochs', 41), ('batch_size', 128), ('numerical_threads', 8)]:
            modified = copy.deepcopy(config); modified['training'][field] = value
            with self.assertRaisesRegex(RuntimeError, 'FROZEN_RECIPE'): m.validate_config(modified)

    def test_synthetic_override_cannot_escape_production(self):
        config = configuration()
        with self.assertRaisesRegex(RuntimeError, 'PRODUCTION_FLAG'): m.validate_config(config)
        config['training']['epochs'] = 3
        with self.assertRaisesRegex(RuntimeError, 'SYNTHETIC_BOUNDS'): m.validate_config(config, True)

    def test_cal_target_reference_rejected(self):
        for changed in [dict(fit_role='CAL'), dict(partition='CIC_DEV'), dict(use='REFERENCE')]:
            rows, values, q, norm, ix = fixture()
            rows[0].update(changed)
            with self.assertRaisesRegex(RuntimeError, 'FIT_ONLY'): t.fit_inputs(rows, values, q, norm, ix, True)

    def test_duplicate_indices_and_uid_rejected(self):
        rows, values, q, norm, ix = fixture()
        bad = ix.copy(); bad[-1] = 0
        with self.assertRaisesRegex(RuntimeError, 'FIT_INDICES'): t.fit_inputs(rows, values, q, norm, bad, True)
        rows[-1]['uid'] = rows[0]['uid']
        with self.assertRaisesRegex(RuntimeError, 'DUPLICATE_FIT_UID'): t.fit_inputs(rows, values, q, norm, ix, True)

    def test_all_tree_random_seeds_explicit(self):
        for seed in m.c.SEEDS:
            p = m.lightgbm_parameters(configuration(), seed)
            for name in ('seed','data_random_seed','feature_fraction_seed','bagging_seed','drop_seed','extra_seed'):
                self.assertEqual(p[name], seed)
            self.assertEqual(p['num_threads'], 4)
            self.assertNotIn('early_stopping_rounds', p)


class EndpointTests(unittest.TestCase):
    def test_all_families_train_save_reload_same_scores(self):
        config = configuration(); rows, values, q, norm, ix = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            for family in m.FAMILIES:
                with self.subTest(family=family):
                    out = Path(temporary)/family; progress = Progress()
                    model = t.train(config, rows, values, q, norm, ix, family, 27, out, progress, True)
                    initial = m.scores(model, family, values, q, ix, norm)
                    replay = m.scores(t.load(out, family, 27, config), family, values, q, ix, norm)
                    self.assertTrue(np.array_equal(initial, replay))
                    receipt = m.c.read(out/'endpoint.json')
                    self.assertTrue(receipt['synthetic_only'])
                    self.assertFalse(receipt['CAL_used'] or receipt['DEV_used'] or receipt['reference_used'])
                    self.assertEqual(receipt['rows'], len(rows))
                    self.assertTrue(progress.ticks)
                    self.assertEqual(receipt['updates'], 3 if family == 'LightGBM' else 8)

    def test_mlp_endpoint_bitwise_matches_original_query_bce(self):
        import query_tail_train_v2 as original
        config = configuration(); rows, values, q, norm, ix = fixture()
        hp = config['training']
        optimizer = {key:value for key,value in hp['optimizer_mlp'].items() if key not in ('foreach', 'amsgrad')}
        design = dict(synthetic_only=True, training=dict(epochs=hp['epochs'], batch_size=hp['batch_size'],
                      tail_negatives_per_batch=128, optimizer_parent_values=optimizer, diagnostics=dict(enabled=False)))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            old = original.train(design, rows, values, q, norm, ix, np.zeros(len(rows), dtype=np.int64),
                                 'QUERY_BCE', 27, root/'old', Progress(), synthetic=True)
            new = t.train(config, rows, values, q, norm, ix, 'MLP_QUERY_BCE', 27, root/'new', Progress(), True)
            for key, value in old.state_dict().items(): self.assertTrue(torch.equal(value, new.state_dict()[key]), key)
            self.assertTrue(np.array_equal(m.k.scores(old, values, q, ix, norm, 782),
                                           m.scores(new, 'MLP_QUERY_BCE', values, q, ix, norm)))

    def test_model_seal_tampering_is_rejected(self):
        config = configuration(); rows, values, q, norm, ix = fixture(32)
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)/'head'
            t.train(config, rows, values, q, norm, ix, 'MLP_QUERY_BCE', 27, out, Progress(), True)
            with (out/'head.npz').open('ab') as stream: stream.write(b'broken')
            with self.assertRaisesRegex(RuntimeError, 'IDENTITY'): t.load(out, 'MLP_QUERY_BCE', 27, config)

    def test_adoption_requires_replay_proof_and_preserves_head_bytes(self):
        import query_tail_train_v2 as original
        config = configuration(); rows, values, q, norm, ix = fixture(32); hp = config['training']
        optimizer = {key:value for key,value in hp['optimizer_mlp'].items() if key not in ('foreach', 'amsgrad')}
        design = dict(synthetic_only=True, training=dict(epochs=hp['epochs'], batch_size=hp['batch_size'],
                      tail_negatives_per_batch=128, optimizer_parent_values=optimizer, diagnostics=dict(enabled=False)))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); old_dir = root/'original'
            original.train(design, rows, values, q, norm, ix, np.zeros(len(rows), dtype=np.int64),
                           'QUERY_BCE', 27, old_dir, Progress(), synthetic=True)
            _, _, _, identity = t.fit_inputs(rows, values, q, norm, ix, True)
            proof = dict(status='PASS', runtime_compatible=True, runtime_fingerprint={'synthetic_generated_test': True},
                         score_and_decision_bitwise=dict(CAL=True, CIC_DEV=True, UNSW_DEV=True),
                         original_head_sha256=m.c.sha(old_dir/'head.npz'),
                         original_endpoint_sha256=m.c.sha(old_dir/'endpoint.json'),
                         original_design_digest=m.c.digest(design), seed=27,
                         ordered_uid_sha256=identity['ordered_uid_sha256'])
            absent_runtime = dict(proof, runtime_fingerprint={})
            with self.assertRaisesRegex(RuntimeError, 'REUSE_PROOF_REQUIRED'):
                t.adopt_mlp(old_dir, design, config, rows, values, q, norm, ix, root/'rejected', absent_runtime)
            self.assertFalse((root/'rejected').exists())
            model = t.adopt_mlp(old_dir, design, config, rows, values, q, norm, ix, root/'adopted', proof)
            replay = t.load(root/'adopted', 'MLP_QUERY_BCE', 27, config)
            self.assertEqual((old_dir/'head.npz').read_bytes(), (root/'adopted'/'head.npz').read_bytes())
            self.assertTrue(np.array_equal(m.scores(model, 'MLP_QUERY_BCE', values, q, ix, norm),
                                           m.scores(replay, 'MLP_QUERY_BCE', values, q, ix, norm)))
            receipt = m.c.read(root/'adopted'/'endpoint.json')
            self.assertTrue(receipt['reused']); self.assertEqual(receipt['training_seconds'], 0.)

    def test_tabm_uses_official_source_and_no_embeddings(self):
        config = configuration(); model = m.classifier('TabM', 27, config)
        self.assertEqual(m.official_tabm().__version__, '0.0.3')
        self.assertIsNone(model.num_module)
        self.assertIsNone(model.cat_module)
        self.assertEqual(model.backbone.k, 32)
        with torch.inference_mode(): self.assertEqual(tuple(model(torch.zeros(2, 782)).shape), (2, 32, 1))


if __name__ == '__main__': unittest.main()
