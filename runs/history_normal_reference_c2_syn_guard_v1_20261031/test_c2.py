"""Synthetic checks for leakage barriers, UID alignment and score preservation."""
import sys
import unittest
from unittest.mock import Mock

import numpy as np

from common import ROOT, align_q, require_dev_pass, restore_raw, syn_guard
import run

sys.path.insert(0, str(ROOT / 'runs/history_normal_reference_keyrepair_v1_20261031'))
from hnr import evaluation as ev


def descriptor(proto, flags):
    q = np.zeros(14, dtype=np.float32)
    q[0] = int(proto == 6)
    q[1:10] = [(flags >> i) & 1 for i in range(9)]
    return q


class C2Tests(unittest.TestCase):
    def test_syn_synack_fin_udp_and_odd_syn_rst(self):
        q = np.stack([descriptor(6, 2), descriptor(6, 18), descriptor(6, 17),
                      descriptor(17, 2), descriptor(6, 16), descriptor(6, 6)])
        self.assertEqual(syn_guard(q).tolist(), [True, False, False, False, False, True])

    def test_flag_fraction_is_rejected(self):
        q = descriptor(6, 2)[None, :]
        q[0, 2] = .5
        with self.assertRaisesRegex(ValueError, 'BINARY'):
            syn_guard(q)

    def test_nonfinite_q_rejected(self):
        q = descriptor(6, 2)[None, :]
        q[0, 12] = np.nan
        with self.assertRaisesRegex(ValueError, 'SCHEMA'):
            syn_guard(q)

    def test_uid_alignment_uses_ids_not_file_order(self):
        a, b = descriptor(6, 2), descriptor(6, 18)
        result = align_q(['a', 'b'], [(['b'], b[None, :]), (['a'], a[None, :])])
        np.testing.assert_array_equal(syn_guard(result), [True, False])

    def test_duplicate_shard_uid_is_rejected(self):
        q = descriptor(6, 2)[None, :]
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_SHARD'):
            align_q(['a'], [(['a'], q), (['a'], q)])

    def test_missing_or_extra_uid_is_rejected(self):
        q = descriptor(6, 2)[None, :]
        with self.assertRaisesRegex(ValueError, 'UID_SET'):
            align_q(['a'], [(['b'], q)])

    def test_input_scores_preserved_and_raw_restored(self):
        raw = np.array([[1., 2., 3., 2.], [4., 5., 6., 5.]])
        old = raw - .5
        saved = old.copy()
        result = restore_raw(raw, old, np.array([True, False]))
        np.testing.assert_array_equal(result[0], raw[0])
        np.testing.assert_array_equal(result[1], old[1])
        np.testing.assert_array_equal(old, saved)

    def test_nonmonotone_old_score_rejected(self):
        raw = np.zeros((2, 3))
        with self.assertRaisesRegex(ValueError, 'NOT_MONOTONE'):
            restore_raw(raw, np.ones_like(raw), np.array([True, False]))

    def test_finite_and_boolean_guards_required(self):
        raw = np.zeros((2, 3))
        with self.assertRaisesRegex(ValueError, 'GUARD_SHAPE'):
            restore_raw(raw, raw, np.array([1, 0]))
        raw[0, 1] = np.inf
        with self.assertRaisesRegex(ValueError, 'NONFINITE'):
            restore_raw(raw, raw, np.array([True, False]))

    def test_strict_threshold_and_ensemble_restore(self):
        raw = np.array([[0., 0., 0.], [np.nextafter(0., 1.), 1., -1.]])
        old = raw - 1.
        result = restore_raw(raw, old, np.array([True, False]))
        frozen = {'cuts': {'cuts': [0., 0., 0.], 'ensemble_cut': 0.}}
        pred = ev.decisions(result, frozen)
        self.assertFalse(pred[0].any())
        np.testing.assert_array_equal(pred[1], ev.decisions(old, frozen)[1])

    def test_dev_failure_blocks_every_ab_input_read(self):
        inputs = Mock()
        with self.assertRaisesRegex(ValueError, 'DEV_GATE_REQUIRED'):
            run.ab_stage(inputs, None, None, {'status': 'STOP_DEV_FAIL', 'no_AB_loaded': True}, None, None)
        self.assertEqual(inputs.mock_calls, [])

    def test_dev_pass_requires_no_prior_ab_read(self):
        with self.assertRaisesRegex(ValueError, 'DEV_GATE_REQUIRED'):
            require_dev_pass({'status': 'PASS_DEV', 'no_AB_loaded': False})

    def test_original_dev_fifty_percent_boundary(self):
        rr = [dict(uid=str(i), label=0, use='QUERY', device=device)
              for i, device in enumerate([r['device'] for r in ev.TARGETS.values()] * 4)]
        raw = np.ones(12, dtype=bool)
        after = np.array([True]*6 + [False]*6)
        self.assertEqual(ev.dev_gate(rr, raw, after)['status'], 'PASS_DEV')
        after[6] = True
        self.assertEqual(ev.dev_gate(rr, raw, after)['status'], 'STOP_DEV_FAIL')


if __name__ == '__main__':
    unittest.main(verbosity=2)
