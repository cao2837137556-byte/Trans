"""Negative identity and reference replay contracts on synthetic data only."""
import sys
import gzip
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import common as c
import pipeline
from test_pipeline import fixture, target_fixture
from test_reference_core import bank, data, row


class ContractTests(unittest.TestCase):
    def test_synthetic_complete_fit_cal_and_target_matrix(self):
        source = fixture()
        for item in source['rows']:
            if item['fit_role'] == 'FIT':
                item['timestamp'] = 20.
        calls = []
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            fit_dir, cal_dir, eval_dir = (base/name for name in ('fit', 'cal', 'eval'))
            # The residual-signal gate has its own tests. Force only that scientific
            # gate so this tiny fixture reaches all five real optimizer endpoints.
            with patch.object(pipeline.tasklib, 'residual_signal',
                              return_value={'status': 'READY', 'synthetic_override': True}):
                fit = pipeline.fit_source(source, fit_dir, synthetic=True,
                                          auxiliary_epochs=1, module_steps=1)
            self.assertEqual(fit['status'], 'COMPLETE')
            self.assertTrue(fit['synthetic_only'])
            self.assertEqual(len(fit['auxiliary']), 2)
            self.assertEqual(len(fit['modules']), 3)
            self.assertTrue(all(x['updates'] == 1 for x in fit['auxiliary'].values()))
            self.assertTrue(all(x['updates'] == 1 for x in fit['modules'].values()))
            for arm in c.ARMS:
                replay = c.read(fit_dir/arm/'replay.json')
                self.assertEqual(replay['status'], 'PASS')
                self.assertTrue(replay['groups'])
            c.verify_seal(fit_dir)
            with self.assertRaisesRegex(ValueError, 'SYNTHETIC_MODEL_IN_PRODUCTION'):
                pipeline._load_modules(fit_dir, synthetic=False)
            calibration = pipeline.calibrate_source(source, fit_dir, cal_dir,
                                                    synthetic=True)
            self.assertEqual(calibration['status'], 'SEALED')
            self.assertTrue(calibration['synthetic_only'])
            c.verify_seal(cal_dir)

            def load_targets():
                calls.append(True)
                return target_fixture()

            decision = pipeline.evaluate_targets(source, fit_dir, cal_dir,
                                                 load_targets, eval_dir,
                                                 synthetic=True)
            self.assertEqual(calls, [True])
            self.assertFalse(decision['automatic_promotion'])
            summary = c.read(eval_dir/'paired_summary.json')
            self.assertEqual(len(summary['cells']), 40)
            self.assertEqual(c.read(eval_dir/'EVALUATION_COMPLETE.json')['cells'], 40)
            for pool in ('CIC_DEV', 'UNSW_DEV'):
                for arm in c.ARMS:
                    for control in ('EMPTY', 'WRONG'):
                        path = eval_dir/'predictions'/pool/control/arm/'predictions.jsonl.gz'
                        self.assertTrue(path.is_file())
                        with gzip.open(path, 'rt', encoding='utf-8') as stream:
                            self.assertEqual(len([json.loads(line) for line in stream]), 2)
            c.verify_seal(eval_dir)

    def test_missing_fixed_fit_device_rejected(self):
        source = fixture()
        missing = c.GROUPS[1][-1]
        rows = [dict(item) for item in source['rows']]
        for item in rows:
            if item['device'] == missing and item['fit_role'] == 'FIT':
                item['fit_role'] = 'CAL'
        fit = [i for i, item in enumerate(rows) if item['fit_role'] == 'FIT']
        cal = [i for i, item in enumerate(rows) if item['fit_role'] == 'CAL']
        self.assertEqual({item['device'] for item in rows},
                         set(c.GROUPS[0]) | set(c.GROUPS[1]))
        self.assertNotIn(missing, {rows[i]['device'] for i in fit})
        with self.assertRaisesRegex(ValueError, 'SOURCE_SIX_DEVICE_RECIPE'):
            pipeline.source_isolation(rows, fit, cal, source['references'])

    def test_source_binding_change_rejected_before_target_loader(self):
        source = fixture()
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            fit_dir, cal_dir = base/'fit', base/'cal'
            pipeline.fit_source(source, fit_dir, synthetic=True)
            pipeline.calibrate_source(source, fit_dir, cal_dir, synthetic=True)
            changed = dict(source, binding=dict(source['binding'], changed=True))
            with self.assertRaisesRegex(ValueError, 'FIT_SOURCE_BINDING_CHANGED'):
                pipeline.calibrate_source(changed, fit_dir, base/'changed_cal', synthetic=True)
            calls = []

            def target_loader():
                calls.append(True)
                raise AssertionError('target loader must not run')

            with self.assertRaisesRegex(ValueError, 'FIT_SOURCE_BINDING_CHANGED'):
                pipeline.evaluate_targets(changed, fit_dir, cal_dir, target_loader,
                                          base/'changed_eval', synthetic=True)
            self.assertEqual(calls, [])
            with patch.object(pipeline, 'implementation_hashes', return_value={'drift': 'x'}):
                with self.assertRaisesRegex(ValueError, 'IMPLEMENTATION_CODE_CHANGED_AFTER_FIT'):
                    pipeline.evaluate_targets(source, fit_dir, cal_dir, target_loader,
                                              base/'code_changed', synthetic=True)
            self.assertEqual(calls, [])

    def test_qualification_trace_metadata_parity(self):
        refs = [row('a', component='a', capture='same', frame=1, end=5,
                    frame_end=4),
                row('b', component='b', capture='same', frame=2, end=5,
                    frame_end=4)]
        queries = [row('eligible', use='QUERY', capture='same', frame=5, timestamp=6),
                   row('cut-equal', use='QUERY', capture='same', frame=5, timestamp=5),
                   row('frame-equal', use='QUERY', capture='same', frame=4, timestamp=6)]
        self._assert_parity(bank(refs), queries)
        self._assert_parity(bank([row('only-a', component='a'),
                                  row('also-a', component='a', frame=2)]),
                            [row('few-components', use='QUERY', capture='new',
                                 frame=3, timestamp=3)])
        target = [row('history', partition='DEV', component='a', capture='c',
                      frame=1, timestamp=1, frame_end=3),
                  row('other', partition='DEV', component='b', capture='c',
                      frame=2, timestamp=1, frame_end=3)]
        self._assert_parity(bank(target, allow_target_prebank=True),
                            [dict(target[0], use='QUERY')])

    def _assert_parity(self, reference_bank, queries):
        e3, q14, uids = data(queries)
        metadata = reference_bank.qualification(queries)
        trace = reference_bank.trace(queries, e3, q14,
                                     feature_uids=uids, q_uids=uids)
        for field in ('eligible', 'reason', 'legal_reference_count',
                      'legal_component_count', 'bank_end', 'bank_end_frame',
                      'bank_key', 'prebank_audit'):
            for left, right in zip(metadata[field], trace[field]):
                if field == 'bank_end' and np.isnan(left):
                    self.assertTrue(np.isnan(right))
                else:
                    self.assertEqual(left, right, field)

    def test_trace_256_64_vs_127_31_representatives_and_distances(self):
        refs = [row('ref-%03d' % i, component='c%d' % (i % 3),
                    capture='old', frame=i+1) for i in range(70)]
        reference_e3, reference_q14, reference_uids = data(
            refs, np.arange(70, dtype=np.float64)/70)
        reference_bank = pipeline.ReferenceBank(
            refs, reference_e3, reference_q14,
            (np.zeros(768), np.ones(768)),
            feature_uids=reference_uids, q_uids=reference_uids)
        queries = [row('query-%03d' % i, use='QUERY', capture='new',
                       frame=100+i, timestamp=3) for i in range(259)]
        e3, q14, uids = data(queries, (np.arange(len(queries)) % 67)/67)
        options = dict(feature_uids=uids, q_uids=uids)
        full = reference_bank.trace(queries, e3, q14, query_batch=256,
                                    reference_block=64, **options)
        split = reference_bank.trace(queries, e3, q14, query_batch=127,
                                     reference_block=31, **options)
        for field in ('eligible', 'reason', 'legal_reference_count',
                      'legal_component_count', 'matched_reference_uids',
                      'matched_components'):
            np.testing.assert_array_equal(full[field], split[field])
        self.assertTrue(full['eligible'].all())
        np.testing.assert_array_equal(full['d'], split['d'])
        np.testing.assert_array_equal(full['dz'], split['dz'])
        np.testing.assert_array_equal(full['dq'], split['dq'])


if __name__ == '__main__':
    unittest.main()
