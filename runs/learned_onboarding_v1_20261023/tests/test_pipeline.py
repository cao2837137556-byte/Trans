"""Synthetic integration checks; no production fitting or target replay."""

import gzip
import gc
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / 'src'))

import common as c
import pipeline
from learning import _loss
from reference_core import ReferenceBank, make_features


def _features(rows):
    e3 = np.zeros((len(rows), 768), dtype=np.float64)
    q14 = np.zeros((len(rows), 14), dtype=np.float64)
    for i, row in enumerate(rows):
        e3[i, 0] = 1.
        e3[i, 1] = .05*(i % 3)
        q14[i, 0] = .05*(i % 4)
        q14[i, 1] = .02*(i % 2)
    return e3, q14


def _row(uid, device, partition, label, use, component, timestamp, *,
         fit_role=None, reference_end=None, protocol=6):
    row = dict(uid=uid, device=device, partition=partition, label=label,
        use=use, component_id=component, capture_id='capture-'+uid,
        source_sha256='sha-'+uid, session_id='session-'+uid,
        activity='normal' if label == 0 else 'attack', timestamp=timestamp,
        frame=2, protocol=protocol, label_metric_weight_denominator=1)
    if fit_role is not None:
        row['fit_role'] = fit_role
    if reference_end is not None:
        row['reference_end'] = reference_end
    return row


def _bundle(rows):
    e3, q14 = _features(rows)
    return dict(rows=rows, e3=e3, q14=q14,
                feature_uids=[r['uid'] for r in rows],
                q_uids=[r['uid'] for r in rows])


def fixture():
    devices = tuple(d for group in c.GROUPS for d in group)
    rows = []
    for device_index, device in enumerate(devices):
        for label in (0, 1):
            uid = 'fit-%d-%d' % (device_index, label)
            rows.append(_row(uid, device, 'LEARN', label, 'QUERY',
                uid, 20. if device_index == 0 else 5., fit_role='FIT'))
    fit_indices = list(range(len(rows)))
    rows.append(_row('cal-attack', devices[0], 'LEARN', 1, 'QUERY',
                     'cal-only', 20., fit_role='CAL'))
    refs = []
    for device_index, device in enumerate(devices):
        for component in (0, 1):
            uid = 'ref-%d-%d' % (device_index, component)
            refs.append(_row(uid, device, 'LEARN', 0, 'REFERENCE',
                'ref-component-%d-%d' % (device_index, component), 1.,
                reference_end=10.))
    source = _bundle(rows)
    source['references'] = _bundle(refs)
    source['fit_indices'] = fit_indices
    source['cal_indices'] = [len(rows)-1]
    source['normalizer'] = (np.zeros(768), np.ones(768))
    source['binding'] = dict(schema='synthetic-source', ordered_uids=source['feature_uids'])
    source['cut'] = 1.
    scores = np.asarray([.9 if r['label'] == 0 else 1.2 for r in rows], np.float64)
    source['score_main'] = lambda indices: scores[np.asarray(indices, np.int64)]
    return source


def target_fixture():
    result = {}
    for pool in ('CIC_DEV', 'UNSW_DEV'):
        rows = [_row(pool+'-normal', 'target-device', 'DEV', 0, 'QUERY',
                     pool+'-normal-component', 20.),
                _row(pool+'-attack', 'target-device', 'DEV', 1, 'QUERY',
                     pool+'-attack-component', 20.)]
        data = _bundle(rows)
        data['scores'] = np.array([1.2, 1.2], np.float64)
        refs = [_row(pool+'-ref-'+str(i), 'target-device', 'DEV', 0,
                     'REFERENCE', pool+'-ref-component-'+str(i), 1.,
                     reference_end=10.) for i in range(2)]
        data['banks'] = {name: _bundle(refs)
                         for name in ('OLD_BANK', 'B0', 'B1', 'B2')}
        result[pool] = data
    return result


class PipelineTests(unittest.TestCase):
    def test_noop_full_matrix_and_target_stage_order(self):
        source = fixture()
        source['target_loader'] = lambda: (_ for _ in ()).throw(
            AssertionError('fit_source must not touch target loader'))
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            fit_dir, cal_dir, eval_dir = (base/name for name in ('fit', 'cal', 'eval'))
            fit = pipeline.fit_source(source, fit_dir, synthetic=True)
            self.assertEqual(fit['status'], 'NOOP')
            self.assertEqual(fit['reason'], 'NOT_EVALUABLE')
            self.assertEqual(fit['target_queries_read'], 0)
            self.assertEqual(len(fit['modules']), 3)
            for arm in c.ARMS:
                self.assertEqual(fit['modules'][arm]['status'], 'NOT_TRAINED')
            c.verify_seal(fit_dir)
            cal = pipeline.calibrate_source(source, fit_dir, cal_dir, synthetic=True)
            self.assertEqual(cal['status'], 'SEALED')
            self.assertEqual(cal['target_queries_read'], 0)
            c.verify_seal(cal_dir)
            events = []
            def load_targets():
                c.verify_seal(fit_dir)
                c.verify_seal(cal_dir)
                events.append('target-loaded-after-seals')
                return target_fixture()
            decision = pipeline.evaluate_targets(source, fit_dir, cal_dir,
                load_targets, eval_dir, synthetic=True)
            self.assertEqual(events, ['target-loaded-after-seals'])
            self.assertEqual(c.read(eval_dir/'EVALUATION_COMPLETE.json')['cells'], 40)
            c.verify_seal(eval_dir)
            matrix = c.read(eval_dir/'paired_summary.json')
            self.assertEqual(len(matrix['cells']), 40)
            for pool in ('CIC_DEV', 'UNSW_DEV'):
                for policy in ('OLD_BANK', 'B0', 'B1', 'B2'):
                    for arm in c.ARMS:
                        path = eval_dir/'predictions'/pool/policy/arm/'predictions.jsonl.gz'
                        with gzip.open(path, 'rt', encoding='utf-8') as f:
                            predictions = [json.loads(line) for line in f]
                        self.assertEqual(len(predictions), 2)
                        self.assertTrue(all(p['base_score'] == p['corrected_score']
                                            for p in predictions))
                for arm in c.ARMS:
                    for control in ('EMPTY', 'WRONG'):
                        path = eval_dir/'predictions'/pool/control/arm/'predictions.jsonl.gz'
                        self.assertTrue(path.is_file())
                        with gzip.open(path, 'rt', encoding='utf-8') as f:
                            predictions = [json.loads(line) for line in f]
                        self.assertEqual(len(predictions), 2)
                        if control == 'EMPTY':
                            self.assertTrue(all(p['base_score'] == p['corrected_score']
                                                for p in predictions))
            self.assertFalse(decision['automatic_promotion'])
            self.assertEqual(decision['learned_benefit']['L_HARD']['status'], 'FAIL')

    def test_bad_seal_and_synthetic_production_gate_before_target_loader(self):
        source = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            fit_dir, cal_dir = base/'fit', base/'cal'
            pipeline.fit_source(source, fit_dir, synthetic=True)
            pipeline.calibrate_source(source, fit_dir, cal_dir, synthetic=True)
            calls = []
            def prohibited():
                calls.append(True)
                raise AssertionError('target loader was invoked')
            with self.assertRaisesRegex(ValueError, 'SYNTHETIC_MODEL_IN_PRODUCTION'):
                pipeline.evaluate_targets(source, fit_dir, cal_dir, prohibited,
                                          base/'production', synthetic=False)
            self.assertFalse(calls)
            changed_source = dict(source, binding=dict(source['binding'], tampered=True))
            with self.assertRaisesRegex(ValueError, 'FIT_SOURCE_BINDING_CHANGED'):
                pipeline.calibrate_source(changed_source, fit_dir, base/'wrong-cal',
                                          synthetic=True)
            with self.assertRaisesRegex(ValueError, 'FIT_SOURCE_BINDING_CHANGED'):
                pipeline.evaluate_targets(changed_source, fit_dir, cal_dir,
                                          prohibited, base/'wrong-eval', synthetic=True)
            self.assertFalse(calls)
            # Mutating a sealed calibration receipt must fail before the target callback.
            path = cal_dir/'calibration.json'
            value = c.read(path)
            value['cut'] = 99.
            c.write(path, value)
            with self.assertRaisesRegex(ValueError, 'INPUT_SHA256'):
                pipeline.evaluate_targets(source, fit_dir, cal_dir, prohibited,
                                          base/'tampered', synthetic=True)
            self.assertFalse(calls)

    def test_geometry_store_reconstruction_matches_reference_features(self):
        source = fixture()
        fit = source['fit_indices']
        rows = [source['rows'][i] for i in fit]
        z, q = source['e3'][fit], source['q14'][fit]
        refs = source['references']
        norm = source['normalizer']
        with tempfile.TemporaryDirectory() as tmp:
            store = pipeline.GeometryStore(Path(tmp)/'geometry', rows, z, q, refs)
            store.build(0, [(np.arange(len(rows)), norm)])
            bank = ReferenceBank(refs['rows'], refs['e3'], refs['q14'], norm,
                feature_uids=refs['feature_uids'], q_uids=refs['q_uids'])
            query_ix = np.array([0, 1], np.int64)
            query_rows = [rows[i] for i in query_ix]
            trace = bank.trace(query_rows, z[query_ix], q[query_ix],
                feature_uids=[r['uid'] for r in query_rows],
                q_uids=[r['uid'] for r in query_rows])
            self.assertTrue(trace['eligible'].all())
            score = np.array([1.2, .8])
            store.task_scores = {0: np.r_[score, np.zeros(len(rows)-2)]}
            columns = [store.key_index[(r['partition'], r['device'], r['protocol'])]
                       for r in query_rows]
            actual = store.features(0, query_ix, columns, np.array([1., 1.]),
                                    np.array([.5, .5]))
            expected = make_features(query_rows, q[query_ix], score, 1., .5, trace)
            np.testing.assert_array_equal(actual, expected)
            store.close()
            del store
            gc.collect()

    def test_geometry_batch_enumerates_worst_attack_bank(self):
        source = fixture()
        fit = source['fit_indices']
        rows = [source['rows'][i] for i in fit]
        z, q = source['e3'][fit], source['q14'][fit]
        with tempfile.TemporaryDirectory() as tmp:
            store = pipeline.GeometryStore(Path(tmp)/'geometry', rows, z, q,
                                           source['references'])
            store.build(0, [(np.arange(len(rows)), source['normalizer'])])
            attack_slot = 1
            columns = np.flatnonzero(store.eligible[attack_slot]).tolist()
            self.assertEqual(len(columns), 6)
            scores = np.zeros(len(rows), np.float64)
            scores[attack_slot] = 1.2
            store.task_scores = {0: scores}
            task = dict(uid=rows[attack_slot]['uid'], view=0, source_slot=attack_slot,
                        score=1.2, t=1., s=.5, label=1,
                        banks=[dict(column=j) for j in columns])
            batch = store.batch([task], [0])
            self.assertEqual(batch['candidate_mask'].shape, (1, 6))
            self.assertTrue(batch['candidate_mask'].all())
            class FixedModel(torch.nn.Module):
                def forward(self, x):
                    return torch.sigmoid(5*x[:, 14:15] + 3*x[:, 42:43])
            model = FixedModel()
            output = model(torch.from_numpy(batch['features'][0])).flatten()
            per = F.softplus(.25*output-.4) + (.25*output).square()
            actual = _loss(model, batch, False)
            self.assertAlmostEqual(float(actual), float(per.max()), places=7)
            store.close()
            del store
            gc.collect()


if __name__ == '__main__':
    unittest.main()
