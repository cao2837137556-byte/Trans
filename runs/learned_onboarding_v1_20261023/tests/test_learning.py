import sys
import gc
import tempfile
import unittest
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from learning import (auxiliary_normalizer, correction_model, fit_auxiliary_head,
                      load_auxiliary_head, load_module, score_auxiliary_head,
                      score_module, train_modules, verify_auxiliary_replay,
                      verify_module_replay, _loss, _replay_compare)
from tasks import mine_hard_tasks


def row(uid, label, view=0):
    return dict(uid=uid, partition='LEARN', fit_role='FIT', label=label,
                device=uid, activity='a', capture_id=uid, session_id=uid,
                component_id=uid, view=view, eligible=True)


class LearningTests(unittest.TestCase):
    def test_auxiliary_synthetic_replay_and_scope(self):
        rows = [row('a', 0), row('b', 1), row('c', 0), row('d', 1)]
        e3 = np.ones((4, 768), dtype=np.float32)
        e3[:, 0] = np.arange(4, dtype=np.float32)
        q14 = np.zeros((4, 14), dtype=np.float32)
        _, scale, zeros, _ = auxiliary_normalizer(rows, e3, np.arange(4))
        self.assertEqual(zeros, 767)
        self.assertTrue(np.all(scale[1:] == 1))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = fit_auxiliary_head(rows, e3, q14, np.arange(4), root / 'one',
                                       synthetic=True, epochs=1)
            second = fit_auxiliary_head(rows, e3, q14, np.arange(4), root / 'two',
                                        synthetic=True, epochs=1)
            self.assertEqual(first['updates'], second['updates'])
            self.assertEqual(first['updates'], 1)
            self.assertEqual(first['final_hash'], second['final_hash'])
            scores = score_auxiliary_head(first['checkpoint'], e3, q14, allow_synthetic=True)
            self.assertEqual(scores.shape, (4,))
            self.assertTrue(np.isfinite(scores).all())
            np.testing.assert_array_equal(
                scores, score_auxiliary_head(first['checkpoint'], e3, q14, allow_synthetic=True))
            expanded_e3 = np.repeat(e3, 65, axis=0)
            expanded_q14 = np.repeat(q14, 65, axis=0)
            whole = score_auxiliary_head(first['checkpoint'], expanded_e3, expanded_q14,
                                         allow_synthetic=True)
            split = np.concatenate([
                score_auxiliary_head(first['checkpoint'], expanded_e3[start:start+128],
                                     expanded_q14[start:start+128], allow_synthetic=True)
                for start in range(0, len(expanded_e3), 128)])
            np.testing.assert_allclose(whole, split, rtol=1e-6, atol=1e-6)
            replay = verify_auxiliary_replay(first['checkpoint'], expanded_e3,
                                              expanded_q14, cut=float(np.max(scores))+1,
                                              labels=np.zeros(len(expanded_e3), np.int64),
                                              allow_synthetic=True)
            self.assertTrue(replay['score_bitwise_reloaded'])
            self.assertTrue(replay['decisions_equal'])
            with self.assertRaisesRegex(ValueError, 'AUX_CHECKPOINT_SCOPE'):
                load_auxiliary_head(first['checkpoint'])

    def test_module_loss_worst_bank_and_query_mask(self):
        model = correction_model()
        features = np.zeros((2, 2, 50), np.float32)
        features[0, 0, 0] = 1
        features[1, 0, 14] = 1
        features[1, 1, 14] = -1
        batch = dict(features=features, candidate_mask=np.array([[True, False], [True, True]]),
                     margins=np.array([.2, .1]), scales=np.ones(2), labels=np.array([0, 1]))
        self.assertTrue(bool(torch.isfinite(_loss(model, batch, False))))
        with torch.no_grad():
            a = model(torch.from_numpy(features.reshape(-1, 50))).reshape(2, 2)
            normal_delta = .25*a[0, 0]
            normal = (normal_delta-.21).square()+.01*normal_delta.square()
            attack_delta = .25*a[1]
            attack = (F.softplus(attack_delta-.1)+attack_delta.square()).max()
            expected = (normal+attack)/2
        self.assertTrue(torch.allclose(_loss(model, batch, False), expected, rtol=0, atol=1e-7))
        zero = dict(batch, scales=np.zeros(2), candidate_mask=np.zeros((2, 2), bool))
        zero_loss = _loss(model, zero, False)
        self.assertEqual(float(zero_loss.detach()), 0.0)
        zero_loss.backward()
        self.assertTrue(all(p.grad is None or torch.count_nonzero(p.grad) == 0
                            for p in model.parameters()))
        masked = score_module(model, features.reshape(-1, 50), query_only=True)
        self.assertEqual(masked[2], masked[3])

    def test_module_synthetic_schedules_and_checkpoint(self):
        tasks = [row(f'{view}{label}', label, view)
                 for view in (0, 1) for label in (0, 1)]
        calls = []

        def get_batch(indices):
            calls.append(tuple(indices))
            n = len(indices)
            features = np.zeros((n, 2, 50), np.float32)
            features[:, 0, 0] = 1
            features[:, 1, 14] = 1
            labels = np.array([tasks[i]['label'] for i in indices])
            mask = np.zeros((n, 2), bool)
            mask[:, 0] = True
            mask[labels == 1, 1] = True
            return dict(features=features, candidate_mask=mask,
                        margins=np.full(n, .1), scales=np.ones(n), labels=labels)

        hard = {(t['view'], t['uid']) for t in tasks}
        with tempfile.TemporaryDirectory() as temp:
            receipts = train_modules(tasks, get_batch, temp, hard, synthetic=True, steps=1)
            self.assertEqual(calls[1], calls[2])
            self.assertEqual(len({r['init_hash'] for r in receipts.values()}), 1)
            for arm, receipt in receipts.items():
                self.assertEqual(receipt['updates'], 1)
                model, item = load_module(receipt['checkpoint'], allow_synthetic=True)
                self.assertEqual(item['arm'], arm)
                self.assertTrue(np.isfinite(score_module(model, np.zeros((2, 50), np.float32))).all())
                features = np.random.default_rng(27).normal(size=(257, 50)).astype(np.float32)
                whole = score_module(model, features, query_only=item['query_only'])
                np.testing.assert_array_equal(
                    whole, score_module(load_module(receipt['checkpoint'], allow_synthetic=True)[0],
                                        features, query_only=item['query_only']))
                split = np.concatenate([score_module(model, features[start:start+128],
                                                     query_only=item['query_only'])
                                        for start in range(0, len(features), 128)])
                np.testing.assert_allclose(whole, split, rtol=1e-6, atol=1e-6)
                replay = verify_module_replay(receipt['checkpoint'], features,
                    np.full(len(features), 1.2), np.full(len(features), .5), 1.0,
                    np.ones(len(features), np.int64), allow_synthetic=True)
                self.assertEqual(replay['rows'], len(features))
                with self.assertRaisesRegex(ValueError, 'MODULE_CHECKPOINT_SCOPE'):
                    load_module(receipt['checkpoint'])

    def test_replay_rejects_decision_flip_inside_score_tolerance(self):
        primary = np.array([1.00000001])
        split = np.array([.99999999])
        with self.assertRaisesRegex(ValueError, 'QUERY_BATCH_DECISION_DRIFT'):
            _replay_compare(primary, primary.copy(), split, primary,
                            np.zeros(1), 1.0, np.array([1]), 0., direct_scores=True)
        with self.assertRaisesRegex(ValueError, 'CHECKPOINT_SCORE_NOT_BITWISE'):
            _replay_compare(primary, np.nextafter(primary, np.inf), primary,
                            primary, np.zeros(1), 1.0, np.array([1]), 0.,
                            direct_scores=True)

    def test_geometry_batch_to_module_endpoint(self):
        import pipeline
        from test_pipeline import fixture

        source = fixture()
        rows = [source['rows'][i] for i in source['fit_indices']]
        for item in rows:
            item['timestamp'] = 20.
        e3 = source['e3'][source['fit_indices']]
        q14 = source['q14'][source['fit_indices']]
        norm = source['normalizer']
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp:
            base = Path(temp)
            geometry = pipeline.GeometryStore(base/'geometry', rows, e3, q14,
                                              source['references'])
            all_indices = np.arange(len(rows))
            geometry.build(0, [(all_indices, norm)])
            geometry.build(1, [(all_indices, norm)])
            folds = {item['uid']: {'fold': 'F0', 'group': item['uid']} for item in rows}
            formal = np.asarray([.9 if r['label'] == 0 else 1.2 for r in rows])
            auxiliary = np.asarray([.9 + .1*(i//2) if r['label'] == 0 else 1.2
                                    for i, r in enumerate(rows)])
            stat = {'t': 1.0, 's': .5}
            records = geometry.task_records({0: formal, 1: auxiliary},
                                            {'F0': stat}, folds,
                                            {r['device']: stat for r in rows})
            hard, _ = mine_hard_tasks(records)
            receipts = train_modules(records, lambda ix: geometry.batch(records, ix),
                                     base/'modules', hard, synthetic=True, steps=1)
            self.assertEqual({r['updates'] for r in receipts.values()}, {1})
            del geometry
            gc.collect()


if __name__ == '__main__':
    unittest.main()
