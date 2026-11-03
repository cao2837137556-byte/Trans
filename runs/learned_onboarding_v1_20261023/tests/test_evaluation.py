import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from evaluation import (ScalarV3, apply_scalar_correction, calibrate_lambda,
                        evaluate_pair, scalar_v3_fit_scales, scientific_decision)


def row(uid, label, device='D', denominator=1, role='DEV'):
    return dict(uid=uid, label=label, use='QUERY', partition=role,
                fit_role='CAL' if role == 'LEARN' else None,
                device=device, protocol=6, activity='a', capture_id='c',
                session_id='s', component_id=uid, timestamp=2., frame=2,
                label_metric_weight_denominator=denominator)


class EvaluationTests(unittest.TestCase):
    def test_exact_fallback_and_strict_boundary(self):
        x = np.array([1., 1.1, 1.3])
        a = np.array([1., 0., 1.])
        mask = np.array([True, False, True])
        self.assertTrue(np.array_equal(apply_scalar_correction(x, a, mask, 1., 0), x))
        corrected = apply_scalar_correction(x, a, mask, 1., .25)
        self.assertEqual(corrected.tolist(), [.75, 1.1, 1.05])
        self.assertEqual(float(apply_scalar_correction(np.array([1.25]),
                         np.array([1.]), np.array([True]), 1., .25)[0]), 1.)

    def test_calibration_worst_donor_and_uninformative(self):
        rows = [row('a', 1, role='LEARN'), row('b', 1, role='LEARN')]
        base = np.array([1.2, .8])
        strengths = np.array([[.1, 1.], [1., 1.]])
        legal = np.ones((2, 2), dtype=bool)
        report = calibrate_lambda(rows, base, 1., strengths, legal, 1.,
                                  bank_keys=['own', 'donor'])
        self.assertEqual(report['selected_lambda'], .1)
        rejected = report['candidates'][-1]
        self.assertEqual(rejected['new_miss_uids'], ['a'])
        self.assertEqual(rejected['new_miss_pair_count'], 1)
        self.assertEqual(rejected['banks'][0]['new_miss_pairs'], 0)
        self.assertEqual(rejected['banks'][1]['new_miss_pairs'], 1)
        empty = calibrate_lambda(rows, base, 1., np.zeros((2, 0)),
                                 np.zeros((2, 0), dtype=bool), 1.)
        self.assertEqual(empty['status'], 'PROTECTION_UNINFORMATIVE')
        self.assertEqual(empty['selected_lambda'], 0.)
        baseline_miss = calibrate_lambda(rows, [.8, .7], 1.,
            np.ones((2, 1)), np.ones((2, 1), dtype=bool), 1.)
        self.assertEqual(baseline_miss['selected_lambda'], 0.)

    def test_paired_weight_and_nonoverlap_lower_bounds(self):
        rows = [row('a', 0, denominator=1), row('b', 0, denominator=3),
                row('c', 0, denominator=1), row('d', 1, denominator=1)]
        base = np.array([1.2, 1.4, 1.25, 1.4])
        corrected = np.array([1.2, 1.4, 1., 1.4])
        report = evaluate_pair(rows, base, corrected, 1.,
            np.array([False, True, True, False]), 1., .25,
            strengths=[0., .1, 1., 0.])
        summary = report['summary']
        self.assertAlmostEqual(summary['base']['normal']['weighted_rate'], 1.)
        self.assertAlmostEqual(summary['corrected']['normal']['weighted_rate'], 4/7)
        self.assertEqual(summary['normal_fp_lower_bound']['ineligible_count'], 1)
        self.assertEqual(summary['normal_fp_lower_bound']['cap_unreachable_count'], 1)
        self.assertEqual(summary['normal_fp_lower_bound']['total_rate'], 2/3)
        self.assertEqual(summary['actual_eligible_normal_fp_remaining'], 1)
        self.assertEqual(summary['corrected_normal_fp'], 1)
        self.assertEqual(len(report['per_query']), len(rows))
        self.assertFalse(report['per_query'][2]['corrected_alarm'])

    def test_added_fn_and_original_fn(self):
        rows = [row('detected', 1), row('old_miss', 1)]
        report = evaluate_pair(rows, [1.2, .8], [1., .8], 1.,
                               np.array([True, False]), 1., .25,
                               strengths=[.8, 0.])['summary']
        self.assertEqual(report['base_true_positives'], 1)
        self.assertEqual(report['base_false_negatives'], 1)
        self.assertEqual(report['new_fn_uids'], ['detected'])

    def test_scalar_v3_scale_matches_original_real_seed_column(self):
        root = Path(__file__).resolve().parents[3]
        sys.path.insert(0, str(root / 'repo' / 'ood'))
        from constrained_onboarding_core_v3 import fit_scales
        rows = []
        for i, label in enumerate([0, 0, 0, 1, 1, 1]):
            r = row(str(i), label, role='LEARN')
            r['fit_role'] = 'FIT'
            rows.append(r)
        actual = np.array([.1, .2, .4, .7, .8, .9])
        other = np.column_stack([actual, actual+.1, actual+.2])
        old = fit_scales(rows, other)
        scalar = scalar_v3_fit_scales(rows, actual)
        self.assertEqual(scalar['scale'], old['scales'][0])
        self.assertEqual(scalar['q10'], old['q10'][0])
        self.assertEqual(scalar['q90'], old['q90'][0])
        # Support and scalar subtraction match the historical first column.
        from constrained_onboarding_core_v3 import apply_correction
        support = np.array([.2, .5, 1., 0., .3, 1.])
        expected = apply_correction(other, support, old, .25)[:, 0]
        observed = apply_scalar_correction(actual, support,
                                            np.ones(6, dtype=bool),
                                            scalar['scale'], .25)
        np.testing.assert_array_equal(observed, expected)
        for candidate in (0., .05, .1, .25):
            old_scores = apply_correction(other, support, old, candidate)[:, 0]
            new_scores = apply_scalar_correction(actual, support,
                np.ones(6, dtype=bool), scalar['scale'], candidate)
            np.testing.assert_array_equal(old_scores, new_scores)
            for cut in (.15, .4, .75):
                self.assertEqual(int(((actual > cut) & ~(old_scores > cut)).sum()),
                                 int(((actual > cut) & ~(new_scores > cut)).sum()))

    def test_v3_uninformative_selection_keeps_old_policy(self):
        rows = [row('cal', 1, role='LEARN')]
        receipt = calibrate_lambda(rows, [.8], 1., np.zeros((1, 0)),
            np.zeros((1, 0), dtype=bool), 1., require_informative=False)
        self.assertEqual(receipt['selected_lambda'], .25)
        self.assertEqual(receipt['status'], 'V3_NO_INFORMATION')

    def test_scientific_layers_use_all_cells(self):
        rows = [row('normal', 0), row('attack', 1)]
        matrix = {}
        for pool in ('CIC_DEV', 'UNSW_DEV'):
            for bank in ('OLD_BANK', 'B0', 'B1', 'B2'):
                for arm in ('BASE', 'V3', 'L_STANDARD', 'L_HARD', 'L_QUERY_ONLY'):
                    score = [1.2, 1.2]
                    if arm == 'L_HARD' and bank == 'B2':
                        score = [.95, 1.2]
                    matrix[(pool, bank, arm)] = evaluate_pair(
                        rows, [1.2, 1.2], score, 1., np.array([True, True]),
                        1., .25, strengths=[1., 0.], pool=pool, bank=bank, arm=arm)
        decision = scientific_decision(matrix)
        self.assertEqual(decision['attack_protection']['L_HARD']['status'], 'PASS')
        self.assertEqual(decision['hard_task_value']['status'], 'PASS')
        self.assertEqual(decision['reference_attribution']['status'], 'PASS')
        self.assertEqual(decision['learned_benefit']['L_HARD']['status'], 'PASS')
        del matrix[('UNSW_DEV', 'B1', 'L_HARD')]
        with self.assertRaisesRegex(ValueError, 'MISSING_MATRIX_CELL'):
            scientific_decision(matrix)

    def test_device_weighted_worsening_blocks_hard_gain(self):
        rows = [row('heavy', 0, 'D1', 1), row('light', 0, 'D1', 10),
                row('other', 0, 'D2', 1), row('attack', 1, 'D2', 1)]
        matrix = {}
        for pool in ('CIC_DEV', 'UNSW_DEV'):
            for bank in ('OLD_BANK', 'B0', 'B1', 'B2'):
                for arm in ('BASE', 'V3', 'L_STANDARD', 'L_HARD', 'L_QUERY_ONLY'):
                    scores = [1.2]*4
                    if bank == 'B2' and arm == 'L_STANDARD':
                        scores = [.95, 1.2, 1.2, 1.2]
                    if bank == 'B2' and arm == 'L_HARD':
                        scores = [1.2, .95, .95, 1.2]
                    matrix[(pool, bank, arm)] = evaluate_pair(rows, [1.2]*4,
                        scores, 1., np.ones(4, bool), 1., .25,
                        strengths=[1., 1., 1., 0.],
                        pool=pool, bank=bank, arm=arm)
        result = scientific_decision(matrix)
        self.assertEqual(result['attack_protection']['L_HARD']['status'], 'PASS')
        self.assertEqual(result['hard_task_value']['status'], 'NO_INCREMENTAL_GAIN')
        comparison = result['hard_task_value']['comparison']['pools'][0]
        self.assertGreater(comparison['weighted_fpr_gain'], 0)
        self.assertLess(comparison['device_deltas']['D1']['weighted_fpr_gain'], 0)
        self.assertFalse(comparison['no_worse'])
        self.assertEqual(len(result['versus_v3_all_cells']['L_HARD']), 8)

    def test_original_attack_floor_is_separate_from_new_fn_gate(self):
        rows = [row('normal', 0), row('detected', 1), row('old_miss', 1)]
        matrix = {}
        for pool in ('CIC_DEV', 'UNSW_DEV'):
            for bank in ('OLD_BANK', 'B0', 'B1', 'B2'):
                for arm in ('BASE', 'V3', 'L_STANDARD', 'L_HARD', 'L_QUERY_ONLY'):
                    matrix[(pool, bank, arm)] = evaluate_pair(rows,
                        [1.2, 1.2, .8], [1.2, 1.2, .8], 1.,
                        np.ones(3, bool), 1., 0., pool=pool, bank=bank, arm=arm)
        result = scientific_decision(matrix)
        self.assertEqual(result['attack_protection']['L_HARD']['status'], 'PASS')
        self.assertEqual(result['original_attack_contract']['L_HARD']['status'], 'FAIL')
        cell = matrix[('CIC_DEV', 'B2', 'L_HARD')]['summary']
        self.assertFalse(cell['original_attack_contract']['base']['pool_attack_99'])
        self.assertFalse(cell['original_attack_contract']['corrected']['seed_attack_97'])


if __name__ == '__main__':
    unittest.main()
