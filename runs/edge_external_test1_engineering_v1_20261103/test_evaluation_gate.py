"""Meaningful external population/weight/safety/authorization regressions."""
import tempfile
import unittest
from pathlib import Path

import numpy as np

import evaluation as ev
from execution_gate import readiness


def row(uid, label=0, capture='c1', component='a', scenario='HTTP'):
    return dict(uid=uid, label=label, device='edge', capture_id=capture,
                component_id=component, scenario=scenario, timestamp_ns=100, frame=3)


class MetricsTests(unittest.TestCase):
    def test_high_frequency_component_does_not_hide_packet_rate(self):
        rows = [row(str(i)) for i in range(9)] + [row('9', component='b')]
        pred = np.array([True] * 9 + [False])
        m = ev.measure(rows, pred, ev.class_weights(rows))['normal']
        self.assertEqual(m['packet_alarm_rate'], .9)
        self.assertEqual(m['weighted_alarm_rate'], .5)

    def test_primary_reweights_and_preserves_same_population(self):
        rows = [row('1'), row('2', capture='c2'), row('3', 1)]
        rows[0].update(timestamp_ns=100, frame=5)
        rows[1].update(timestamp_ns=101, frame=1)
        rows[2].update(timestamp_ns=101, frame=7)
        views = ev.view_indices(rows, 100, 'c1', 5)
        self.assertEqual(views['post_window_primary'].tolist(), [1, 2])
        self.assertEqual(ev.class_weights([rows[1], rows[2]]).tolist(), [1., 1.])

    def test_low_raw_recall_disallows_even_small_withdrawal(self):
        rows = [row(str(i), 1) for i in range(1000)]
        raw = np.array([True] * 980 + [False] * 20)
        pred = raw.copy(); pred[0] = False
        result = ev.paired_safety(rows, raw, pred, ev.class_weights(rows))
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('LOW_RAW_RECALL_ANY_WITHDRAWAL', result['groups']['device:edge']['failures'])

    def test_no_attack_or_fabricated_event_pass(self):
        rows = [row('1')]
        safety = ev.paired_safety(rows, np.array([True]), np.array([False]), ev.class_weights(rows))
        self.assertEqual(safety['status'], 'NOT_EVALUABLE')
        self.assertTrue(safety['independent_official_event_gate'].startswith('NOT_EVALUABLE'))

    def test_alarms_cannot_increase_for_c5(self):
        with self.assertRaisesRegex(ValueError, 'C5_CANNOT_ADD'):
            ev.paired_safety([row('1')], np.array([False]), np.array([True]), np.ones(1))

    def test_missing_truth_and_duplicate_uids_fail(self):
        with self.assertRaisesRegex(ValueError, 'BINARY_TRUTH'):
            ev.class_weights([dict(row('1'), label=None)])
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_QUERY'):
            ev.report_view([row('1'), row('1')], {}, np.zeros((2, 4), dtype=bool), raw_uids=[], prediction_uids={})

    def test_independent_baseline_can_add_raw_negative_alarm(self):
        rows = [row('1'), row('2', 1)]
        raw = np.zeros((2, 4), dtype=bool)
        predictions = dict(C5_P3=raw.copy(), KNN5=np.ones((2, 4), dtype=bool))
        result = ev.report_view(rows, predictions, raw, raw_uids=['1', '2'],
            prediction_uids={k:['1', '2'] for k in predictions}, independent_methods=['KNN5'])
        baseline = result['methods']['KNN5']['ensemble']['safety']
        self.assertEqual(baseline['status'], 'DESCRIPTIVE_INDEPENDENT_DETECTOR')
        self.assertEqual(baseline['added_RAW_negative_alarms'], 2)

    def test_permuted_prediction_uids_rejected_even_if_shapes_match(self):
        predictions = dict(C5_P3=np.zeros((2, 4), dtype=bool))
        with self.assertRaisesRegex(ValueError, 'BROKEN_PREDICTION_UID_JOIN'):
            ev.report_view([row('1'), row('2')], predictions, predictions['C5_P3'],
                raw_uids=['1', '2'], prediction_uids=dict(C5_P3=['2', '1']))

    def test_local_pass_cannot_unlock_other_runtime(self):
        card = dict(status='FROZEN_ENGINEERING_READY_FOR_AUTHORIZATION', population=dict(sealed=True),
                    baselines=dict(source_calibrated=True),
                    same_runtime_preflight=dict(status='REAL_SLICE_E2E_PASS', runtime_identity='Windows310'),
                    runtime_identity='Linux311', artifact_pins={})
        with tempfile.TemporaryDirectory() as td:
            failures = readiness(card, Path(td))['failures']
        self.assertIn('RUNTIME_IDENTITY_NOT_EQUAL', failures)
        self.assertIn('BUDGET_NOT_FIXED:wall_seconds', failures)


if __name__ == '__main__':
    unittest.main()
