import copy
import importlib.util
import random
import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / 'src'
sys.path.insert(0, str(SRC))
import binding as b


def fixture(devices=('a', 'b', 'c'), counts=(12, 6, 3)):
    rows, windows = [], []
    for device, count in zip(devices, counts):
        windows.append(dict(partition='DEV', device=device, source_sha256='source',
            capture_id='capture', start=0, end=100, reference_end=100, frame_end=100))
        for i in range(count):
            rows.append(dict(uid=f'{device}-{i:03}', partition='DEV', device=device,
                protocol=6, source_sha256='source', capture_id='capture',
                component_id=f'{device}-component-{i % 3}', frame=i + 1,
                timestamp=float(i), label=0, score=999, reference_end=100, bank_end_frame=100))
    return rows, windows


class BindingTests(unittest.TestCase):
    def test_identity_only_under_label_and_score_changes(self):
        rows, windows = fixture()
        original = b.freeze_wrong_reference_plan('pool', rows, windows)
        changed = [dict(r, label=1, score=float('-inf'), arbitrary_feature=[1, 2]) for r in rows]
        self.assertEqual(original, b.freeze_wrong_reference_plan('pool', changed, windows))

    def test_donor_cycle_matches_frozen_sha_order(self):
        rows, windows = fixture()
        plan = b.freeze_wrong_reference_plan('pool', rows, windows)
        import hashlib
        order = sorted(('a', 'b', 'c'), key=lambda d: hashlib.sha256((b.DONOR_SALT + d).encode()).hexdigest())
        for group in plan['groups']:
            self.assertEqual(group['donor_device'], order[(order.index(group['device']) + 1) % len(order)])

    def test_determinism_under_input_permutation_except_ordered_dense_identity(self):
        rows, windows = fixture()
        plan = b.freeze_wrong_reference_plan('pool', rows, windows)
        random.Random(7).shuffle(rows)
        other = b.freeze_wrong_reference_plan('pool', rows, windows[::-1])
        self.assertEqual(plan['groups'], other['groups'])
        self.assertNotEqual(plan['dense_uid_sha256'], other['dense_uid_sha256'])

    def test_no_donor_not_evaluable(self):
        rows, windows = fixture(('a',), (4,))
        group = b.freeze_wrong_reference_plan('pool', rows, windows)['groups'][0]
        self.assertEqual(group['status'], 'NOT_EVALUABLE')
        self.assertIsNone(group['donor_device'])
        self.assertEqual(group['selected_uids'], [])

    def test_other_protocol_cannot_supply_donor(self):
        rows, windows = fixture(('a', 'b'), (4, 4))
        for row in rows:
            if row['device'] == 'b': row['protocol'] = 17
        self.assertTrue(all(g['status'] == 'NOT_EVALUABLE' for g in
            b.freeze_wrong_reference_plan('pool', rows, windows)['groups']))

    def test_different_window_cannot_supply_donor(self):
        rows, windows = fixture(('a', 'b'), (4, 4))
        windows[1]['end'] = 90
        self.assertTrue(all(g['status'] == 'NOT_EVALUABLE' for g in
            b.freeze_wrong_reference_plan('pool', rows, windows)['groups']))

    def test_downsample_and_shortage_recorded(self):
        rows, windows = fixture(('a', 'b'), (12, 6))
        groups = {g['device']: g for g in b.freeze_wrong_reference_plan('pool', rows, windows)['groups']}
        self.assertEqual(groups['a']['selected_positions'], 6)
        self.assertEqual(groups['a']['density_ratio'], .5)
        self.assertEqual(groups['b']['selected_positions'], 6)
        self.assertEqual(groups['b']['donor_positions'], 12)

    def test_component_round_robin_avoids_collapse(self):
        rows, _ = fixture(('a',), (12,))
        selected = b.subsample_dense(rows, 3)
        self.assertEqual(len({r['component_id'] for r in selected}), 3)

    def test_uniform_time_uses_endpoints_for_two(self):
        rows, _ = fixture(('a',), (12,))
        for row in rows: row['component_id'] = 'one'
        self.assertEqual([r['timestamp'] for r in b.subsample_dense(rows, 2)], [0., 11.])

    def test_exact_frozen_selection_implementation_compatibility(self):
        package = Path(__file__).resolve().parents[1]
        frozen_path = package / 'vendor/encoding_v2/repo/ood/onboarding_dense_reference_v1.py'
        spec = importlib.util.spec_from_file_location('frozen_dense', frozen_path)
        dense = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(dense)
        rows, _ = fixture()
        for count in (0, 1, 2, 3, 7, 12, 20, 99):
            expected = sorted(dense._balanced_select(rows, count, b.DENSE_SALT), key=lambda r: r['uid'])
            self.assertEqual(b.subsample_dense(rows, count), expected)

    def test_wrong_table_tampering_rejected(self):
        rows, windows = fixture()
        plan = b.freeze_wrong_reference_plan('pool', rows, windows)
        plan['groups'][0]['selected_uids'][0] = 'tampered'
        with self.assertRaisesRegex(ValueError, 'WRONG_PLAN_CHANGED'):
            b.verify_wrong_plan(plan, 'pool', rows, windows)

    def test_frozen_dense_uid_hash_tampering_rejected(self):
        rows, windows = fixture()
        with self.assertRaisesRegex(ValueError, 'FROZEN_DENSE_UIDS_CHANGED'):
            b.freeze_wrong_reference_plan('pool', rows, windows, expected_selected_uid_sha256='0' * 64)

    def test_duplicate_uid_rejected(self):
        rows, windows = fixture()
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_DENSE_UID'):
            b.freeze_wrong_reference_plan('pool', rows + [rows[0]], windows)

    def test_outside_window_rejected(self):
        rows, windows = fixture()
        rows[0]['timestamp'] = -1
        with self.assertRaisesRegex(ValueError, 'DENSE_ROW_OUTSIDE_WINDOW'):
            b.freeze_wrong_reference_plan('pool', rows, windows)

    def test_asset_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'asset'
            path.write_text('original')
            entry = b.asset(folder, path)
            path.write_text('modified')
            with self.assertRaisesRegex(ValueError, 'ASSET_CHANGED'):
                b.verify_asset(folder, entry)

    def test_third_pool_missing_assets_is_not_no_window_branch(self):
        mode = b.third_pool_mode(base={'path': 'BASE'}, b2_bank=None, receipt={})
        self.assertEqual(mode['mode'], 'BLOCKED_MISSING_FROZEN_BASE_B2')
        self.assertIsNone(mode['new_encoding_positions'])

    def test_third_pool_existing_receipt_no_window_b2_only(self):
        mode = b.third_pool_mode(base={'path': 'BASE'}, b2_bank={'path': 'B2'}, receipt={'status': 'COMPLETE'})
        self.assertEqual(mode['mode'], 'B2_REGRESSION_ONLY')
        self.assertEqual(mode['dense_arms'], 'NOT_APPLICABLE')
        self.assertEqual(mode['new_encoding_positions'], 0)

    def test_third_pool_existing_window_dense_branch(self):
        mode = b.third_pool_mode(base={'path': 'BASE'}, b2_bank={'path': 'B2'},
            receipt=dict(t0=0, cutoff=100, cutoff_frame=100, source_sha256='source'))
        self.assertEqual(mode['mode'], 'DENSE_MATRIX')
        self.assertEqual(mode['new_encoding_positions'], 'REQUIRES_EXACT_ENUMERATION')

    def test_third_pool_partial_window_not_silently_na(self):
        with self.assertRaisesRegex(ValueError, 'THIRD_POOL_PARTIAL_WINDOW_RECEIPT'):
            b.third_pool_mode(base={'path': 'BASE'}, b2_bank={'path': 'B2'}, receipt=dict(t0=0))

    def test_strict_preflight_rejects_third_pool_absence_and_blocked(self):
        bindings = dict(pools=[dict(pool_id=p, mode='DENSE_MATRIX') for p in ('CIC_DEV', 'UNSW_DEV')])
        with self.assertRaisesRegex(ValueError, 'THREE_REGISTERED_POOLS_REQUIRED'):
            b.require_full_matrix(bindings)
        bindings['pools'].append(dict(pool_id=b.THIRD_POOL, **b.third_pool_mode()))
        with self.assertRaisesRegex(ValueError, 'FROZEN_THIRD_POOL_INPUTS_MISSING'):
            b.require_full_matrix(bindings)

    def test_pair_budget_respects_time_frame_and_two_components(self):
        rows, windows = fixture(('a', 'b'), (3, 3))
        plan = b.freeze_wrong_reference_plan('pool', rows, windows)
        queries = [dict(rows[0], uid='q1', timestamp=101, frame=101),
                   dict(rows[0], uid='q2', timestamp=100, frame=101),
                   dict(rows[0], uid='q3', timestamp=101, frame=100)]
        budget = b.pair_budget(queries, rows, rows, plan)
        self.assertEqual(budget['R-DENSE']['distance_pairs'], 3)
        self.assertEqual(budget['R-DENSE-WRONG']['distance_pairs'], 3)
        self.assertEqual(budget['total_distance_pairs'], 9)


if __name__ == '__main__':
    unittest.main()
