import importlib.util
from pathlib import Path
import sys
import unittest

import numpy as np

SRC = Path(__file__).resolve().parents[1] / 'src'
sys.path.insert(0, str(SRC))
import metrics


def row(uid, label=0, device='D', component='C', activity='N', capture='capture', session='session'):
    return dict(uid=uid, label=label, device=device, component_id=component, activity=activity,
                capture_id=capture, session_id=session, annotation_id=activity,
                timestamp=20., frame=20)


class WeightTests(unittest.TestCase):
    def test_rebuild_after_window_is_not_conditioned_original_weights(self):
        rows = [row('old', device='A', activity='old'), row('a1', device='A', activity='now'),
                row('a2', device='A', activity='now'), row('b1', device='B', activity='now')]
        full = metrics.hierarchical_weights(rows, 'CIC_DEV')
        late = metrics.hierarchical_weights(rows[1:], 'CIC_DEV')
        self.assertEqual(full.tolist(), [.25, .125, .125, .5])
        self.assertEqual(late.tolist(), [.25, .25, .5])
        self.assertFalse(np.array_equal(late, full[1:]/sum(full[1:])))

    def test_unsw_uses_component_hierarchy_and_annotation_for_attacks(self):
        rows = [row('a', component='C1'), row('b', component='C1'), row('c', component='C2'),
                row('x', 1, component='X', activity='tcp'), row('y', 1, component='Y', activity='udp'),
                row('z', 1, component='Z', activity='udp')]
        actual = metrics.hierarchical_weights(rows, 'UNSW_DEV')
        self.assertEqual(actual.tolist(), [.25, .25, .5, .5, .25, .25])

    def test_official_full_weight_identity_fail_closed(self):
        rr = [row('a'), row('b')]
        for r in rr:
            r['label_metric_weight_denominator'] = 2
        self.assertEqual(metrics.validate_full_weights(rr, 'CIC_DEV').tolist(), [.5, .5])
        rr[0]['label_metric_weight_denominator'] = 3
        with self.assertRaisesRegex(ValueError, 'FULL_HIERARCHY'):
            metrics.validate_full_weights(rr, 'CIC_DEV')

    def test_window_uses_receipt_cutoff_and_capture_frame(self):
        rr = [row('at'), row('after'), row('frame')]
        rr[0]['timestamp'] = 10.
        rr[1]['timestamp'] = 11.
        rr[2]['timestamp'], rr[2]['frame'] = 12., 10
        window = {'D': dict(cutoff=10., bank_end_frames={'capture': 10})}
        self.assertEqual(metrics.post_window_mask(rr, window).tolist(), [False, True, False])
        with self.assertRaisesRegex(ValueError, 'WINDOW_REQUIRED'):
            metrics.post_window_mask(rr, {})


class GateTests(unittest.TestCase):
    def test_cic_activity_budget_with_no_annotation_id(self):
        rows = [row('common', 1, activity='UDP'), row('rare', 1, activity='Hydra')]
        for r in rows:
            del r['annotation_id']
        report = metrics.report(rows, np.asarray([True, True]), np.asarray([True, False]),
                                np.asarray([.9995, .0005]), np.ones(2, dtype=bool), np.ones(2))
        gate = metrics.attack_gate(report, .1)
        self.assertNotIn('POOL_ATTACK_LOSS_EXCEEDS_EPSILON', gate['failures'])
        self.assertIn('ATTACK_TYPE_ATTACK_LOSS:Hydra', gate['failures'])

    def test_local_attack_failure_not_hidden_in_pool_average(self):
        rows = [row('safe', 1, device='large', activity='safe'),
                row('lost', 1, device='small', activity='rare')]
        before, after = np.asarray([True, True]), np.asarray([True, False])
        report = metrics.report(rows, before, after, np.asarray([.9995, .0005]),
                                np.ones(2, dtype=bool), np.ones(2))
        gate = metrics.attack_gate(report, .1)
        self.assertEqual(gate['status'], 'FAIL')
        self.assertNotIn('POOL_ATTACK_LOSS_EXCEEDS_EPSILON', gate['failures'])
        self.assertTrue(any('DEVICE_ATTACK_LOSS:small' == s for s in gate['failures']))
        self.assertTrue(any('ANNOTATION_ATTACK_LOSS:rare' == s for s in gate['failures']))

    def test_absolute_attack_floor_even_when_no_added_miss(self):
        rr = [row('a', 1), row('b', 1)]
        pred = np.asarray([True, False])
        report = metrics.report(rr, pred, pred, np.asarray([.98, .02]),
                                np.zeros(2, dtype=bool), np.zeros(2))
        self.assertIn('POOL_ATTACK_RECALL_BELOW_99', metrics.attack_gate(report, .1)['failures'])

    def test_no_attack_evidence_not_vacuous_pass(self):
        rr = [row('normal')]
        report = metrics.report(rr, np.asarray([False]), np.asarray([False]), np.asarray([1.]),
                                np.asarray([False]), np.zeros(1))
        self.assertEqual(metrics.target_gate(report, .1)['status'], 'NOT_EVALUABLE')

    def test_wrong_comparison_common_eligible_with_coverage(self):
        rr = [row('a'), row('b'), row('c')]
        result = metrics.paired_own_wrong(rr, np.asarray([False, True, False]),
                 np.asarray([True, False, False]), np.asarray([.2, .3, .5]),
                 np.asarray([True, True, False]), np.asarray([True, False, True]))
        self.assertEqual(result['rows'], 1)
        self.assertEqual(result['coverage']['normal']['weight_coverage'], .2)
        self.assertEqual(result['own']['normal']['weighted_rate'], 0.)
        self.assertEqual(result['wrong']['normal']['weighted_rate'], 1.)


if __name__ == '__main__':
    unittest.main()
