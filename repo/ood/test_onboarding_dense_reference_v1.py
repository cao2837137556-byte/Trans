import copy
import random
import unittest

import onboarding_dense_reference_v1 as dense


def row(uid, component='c', t=1, **extra):
    return dict(uid=uid, component_id=component, timestamp=t, partition='LEARN',
                device='d', protocol=6, source_sha256='source', capture_id='capture',
                frame=int(t) + 1, label=0, use='REFERENCE', **extra)


WINDOWS = [dict(partition='LEARN', device='d', source_sha256='source',
                capture_id='capture', start=0, end=100, reference_end=100,
                frame_end=101)]


class DenseReferenceTests(unittest.TestCase):
    def plan(self, rows, encoded=None, **kw):
        return dense.plan_dense_positions(rows, WINDOWS,
            encoded_uids=[r['uid'] for r in rows] if encoded is None else encoded, **kw)

    def test_no_label_score_or_fit_role_selection(self):
        rows = [row(str(i), str(i % 3), i) for i in range(30)]
        expected = self.plan(rows, cap=9)
        altered = [dict(r, label=1, score=1e20, fit_role='CAL') for r in rows]
        self.assertEqual(expected, self.plan(altered, cap=9))

    def test_permutation_stability_and_balanced_components(self):
        rows = [row(str(i), str(i % 3), i) for i in range(30)]
        expected = self.plan(rows, cap=8)
        random.Random(27).shuffle(rows)
        actual = self.plan(rows, cap=8)
        self.assertEqual(expected['selected_uids'], actual['selected_uids'])
        selected = [rows[i] for i in actual['selected_indices']]
        counts = [sum(r['component_id'] == str(c) for r in selected) for c in range(3)]
        self.assertLessEqual(max(counts) - min(counts), 1)

    def test_time_uniform_not_packet_rank(self):
        rows = [row(str(i), t=t) for i, t in enumerate([0, 1, 2, 3, 49, 100])]
        p = self.plan(rows, cap=3)
        self.assertEqual({rows[i]['timestamp'] for i in p['selected_indices']}, {0, 49, 100})

    def test_encoded_first_and_original_bank_preserved(self):
        rows = [row(str(i), t=i) for i in range(20)]
        p = self.plan(rows, encoded={'2', '5', '8'}, mandatory_uids=['2'], cap=5)
        self.assertTrue({'2', '5', '8'} <= set(p['selected_uids']))
        self.assertEqual(len(p['supplemental_encoding_uids']), 2)

    def test_component_round_robin_counts_original_anchors(self):
        rows = [row('a' + str(i), component='a', t=i) for i in range(4)]
        rows.append(row('b0', component='b', t=0))
        p = self.plan(rows, mandatory_uids=['a0', 'a1', 'a2'], cap=4)
        self.assertEqual(set(p['selected_uids']), {'a0', 'a1', 'a2', 'b0'})

    def test_new_encoding_round_robin_counts_already_encoded_positions(self):
        rows = [row('a' + str(i), component='a', t=i) for i in range(4)]
        rows.append(row('b0', component='b', t=0))
        p = self.plan(rows, encoded=['a0', 'a1', 'a2'], cap=4)
        self.assertEqual(set(p['selected_uids']), {'a0', 'a1', 'a2', 'b0'})
        self.assertEqual(p['supplemental_encoding_uids'], ['b0'])

    def test_uniform_time_equal_distance_uses_salted_uid(self):
        rows = [row(str(t), t=t) for t in (0, 4, 6, 10)]
        p = self.plan(rows, cap=3)
        midpoint = min(('4', '6'), key=lambda uid: dense._rank(uid, dense.SALT))
        self.assertEqual(set(p['selected_uids']), {'0', midpoint, '10'})

    def test_scope_causal_boundaries_and_wrong_identity(self):
        rows = [row('start', t=0), row('end', t=100), row('future', t=101),
                dict(row('wrong'), source_sha256='other'),
                dict(row('frame'), frame=102), dict(row('capture'), capture_id='other')]
        p = self.plan(rows)
        self.assertEqual(p['selected_uids'], ['end', 'start'])
        self.assertEqual(p['excluded_positions'], 4)

    def test_uid_dedup_and_conflict(self):
        r = row('x')
        self.assertEqual(self.plan([r, dict(r)])['duplicate_positions'], 1)
        with self.assertRaisesRegex(ValueError, 'CONFLICTING_DUPLICATE'):
            self.plan([r, dict(r, timestamp=2)])

    def test_device_protocol_cap_isolation(self):
        rows = [row(str(i), t=i) for i in range(20)]
        rows += [dict(row('udp' + str(i), t=i), protocol=17) for i in range(20)]
        p = self.plan(rows, cap=4)
        self.assertEqual([g['selected_positions'] for g in p['groups']], [4, 4])

    def test_trust_label_and_cal_leakage_guards(self):
        rows = [row('a')]
        p = self.plan(rows)
        with self.assertRaisesRegex(ValueError, 'TRUSTED_SOURCE'):
            dense.materialize_source_metadata(p, rows, trusted_scope_verified=False)
        with self.assertRaisesRegex(ValueError, 'NONNORMAL_LABEL'):
            dense.materialize_source_metadata(p, [dict(rows[0], label=1)], trusted_scope_verified=True)
        with self.assertRaisesRegex(ValueError, 'CAL_REFERENCE'):
            dense.materialize_source_metadata(p, rows, trusted_scope_verified=True, cal_components={'c'})
        self.assertEqual(dense.materialize_source_metadata(p, rows, trusted_scope_verified=True)[0]['use'], 'REFERENCE')

    def test_no_unencoded_materialization_or_missing_anchor(self):
        rows = [row('a')]
        p = self.plan(rows, encoded=[])
        with self.assertRaisesRegex(ValueError, 'E3_ENCODING_REQUIRED'):
            dense.materialize_source_metadata(p, rows, trusted_scope_verified=True)
        with self.assertRaisesRegex(ValueError, 'MANDATORY_REFERENCE_NOT_ENCODED'):
            self.plan(rows, encoded=[], mandatory_uids=['a'])
        with self.assertRaisesRegex(ValueError, 'OUTSIDE_SCOPE'):
            self.plan([row('a', t=102)], mandatory_uids=['a'])

    def test_postencoding_materialization_consumes_same_frozen_plan(self):
        rows = [row('a', t=1), row('b', t=2)]
        p = self.plan(rows, encoded=['a'])
        frozen = copy.deepcopy(p)
        with self.assertRaisesRegex(ValueError, 'E3_ENCODING_REQUIRED'):
            dense.materialize_source_metadata(p, rows, trusted_scope_verified=True)
        with self.assertRaisesRegex(ValueError, 'SELECTED_UID_NOT_ENCODED'):
            dense.materialize_source_metadata(p, rows, trusted_scope_verified=True,
                                               available_encoded_uids={'a'})
        selected = dense.materialize_source_metadata(p, rows,
            trusted_scope_verified=True, available_encoded_uids={'a', 'b'})
        self.assertEqual([r['uid'] for r in selected], p['selected_uids'])
        self.assertEqual(p, frozen)
        self.assertEqual(p['supplemental_encoding_uids'], ['b'])

    def test_postencoding_availability_does_not_bypass_label_or_cal_guards(self):
        rows = [row('a')]
        p = self.plan(rows, encoded=[])
        for altered, message in ((dict(rows[0], label=1), 'NONNORMAL_LABEL'),
                                 (dict(rows[0], fit_role='CAL'), 'CAL_REFERENCE')):
            with self.assertRaisesRegex(ValueError, message):
                dense.materialize_source_metadata(p, [altered],
                    trusted_scope_verified=True, available_encoded_uids={'a'})

    def test_input_immutability_and_invalid_scope(self):
        rows = [row('a')]
        original = copy.deepcopy(rows)
        self.plan(rows)
        self.assertEqual(original, rows)
        with self.assertRaisesRegex(ValueError, 'CAP'):
            self.plan(rows, cap=4097)
        with self.assertRaisesRegex(ValueError, 'CUTOFF_MISMATCH'):
            dense.plan_dense_positions(rows, WINDOWS + [dict(WINDOWS[0], reference_end=101)], encoded_uids=['a'])


if __name__ == '__main__':
    unittest.main()
