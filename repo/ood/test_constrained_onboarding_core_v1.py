"""Synthetic adversarial checks; no real data, snapshots or classifier forward."""
import copy
import unittest

import numpy as np

import constrained_onboarding_core_v1 as m


def row(uid, device='A', protocol=6, partition='LEARN', timestamp=20.,
        component=None, reference=False, label=0, fit_role='FIT', capture='query'):
    return dict(uid=uid, device=device, protocol=protocol, partition=partition,
                timestamp=timestamp, component_id=component or uid, frame=30,
                use='REFERENCE' if reference else 'QUERY', label=label,
                fit_role=fit_role, capture_id=capture, activity='normal' if label == 0 else 'attack',
                session_id='session-' + (component or uid), reference_end=10.)


def reference(uid, device='A', protocol=6, component=None, **kwargs):
    result = row(uid, device, protocol, timestamp=2., component=component,
                 reference=True, capture='reference', **kwargs)
    result['frame'] = 2
    return result


def vec(count, axis=0):
    result = np.zeros((count, 768), dtype=np.float64)
    result[:, axis] = 1.
    return result


def geometry(z=1., q=1., udp=True):
    return dict(protocols={'6': dict(status='READY', rho_z=z, rho_q=q),
                           '17': (dict(status='READY', rho_z=z, rho_q=q) if udp else
                                  dict(status='NO_SOURCE_GEOMETRY_SUPPORT'))})


def joined(rows):
    return dict(feature_uids=[r['uid'] for r in rows], q_uids=[r['uid'] for r in rows])


def bank(rows=None, e3=None, q14=None):
    rows = [reference('r1'), reference('r2')] if rows is None else rows
    return m.ReferenceBank(rows, vec(len(rows)) if e3 is None else e3,
                           np.zeros((len(rows), 14)) if q14 is None else q14,
                           (np.zeros(768), np.ones(768)), **joined(rows))


def own(b, rows=None, e3=None, q14=None, geom=None, **kwargs):
    rows = [row('q')] if rows is None else rows
    return b.own(rows, vec(len(rows)) if e3 is None else e3,
                 np.zeros((len(rows), 14)) if q14 is None else q14,
                 geometry() if geom is None else geom, **joined(rows), **kwargs)


class GeometryTests(unittest.TestCase):
    def test_same_reference_must_support_both_views(self):
        refs = [reference('r%d' % i) for i in range(4)]
        e3 = np.concatenate((vec(2), vec(2, axis=1)))
        q = np.concatenate((np.ones((2, 14)), np.zeros((2, 14))))
        answer = own(bank(refs, e3, q), geom=geometry(.5, .5))
        self.assertEqual(answer['second_dz'][0], 0.)
        self.assertEqual(answer['second_dq'][0], 0.)
        self.assertEqual(answer['second_joint'][0], 2.)
        self.assertEqual(answer['support'][0], 0.)

    def test_distinct_components_and_same_component_history(self):
        refs = [reference('r1', component='one'), reference('r2', component='one')]
        answer = own(bank(refs))
        self.assertFalse(answer['eligible'][0])
        self.assertEqual(answer['legal_component_count'][0], 1)
        refs.append(reference('r3', component='two'))
        answer = own(bank(refs), [row('q', component='one')])
        self.assertEqual(answer['support'][0], 1.)
        self.assertTrue(answer['same_component'][0])
        self.assertEqual(set(answer['matched_components'][0]), {'one', 'two'})

    def test_complete_bank_end_not_subset_or_protocol_maximum(self):
        refs = [reference('r1'), reference('r2'), reference('r3', protocol=17)]
        for r in refs:
            r['reference_end'] = 25.
        b = bank(refs)
        answer = own(b, override={('LEARN', 'A', 6): ['r1', 'r2']})
        self.assertFalse(answer['eligible'][0])
        self.assertEqual(answer['bank_end'][0], 25.)
        answer = own(b, [row('q', timestamp=25.)])
        self.assertFalse(answer['eligible'][0])
        answer = own(b, [row('q', timestamp=26.)])
        self.assertTrue(answer['eligible'][0])

    def test_future_frame_excluded_even_if_timestamp_passes(self):
        refs = [reference('r1'), reference('r2')]
        refs[1]['capture_id'] = 'query'
        refs[1]['frame'] = 30
        answer = own(bank(refs))
        self.assertFalse(answer['eligible'][0])
        self.assertEqual(answer['legal_component_count'][0], 1)

    def test_whole_window_frame_end_applies_across_protocol_and_subset(self):
        refs = [reference('r1'), reference('r2'), reference('u1', protocol=17)]
        for r in refs:
            r['capture_id'] = 'query'
            r['bank_end_frame'] = 100
        b = bank(refs)
        # Both selected references are earlier than the query, but the complete
        # observation window has not closed at the query frame.
        answer = own(b, override={('LEARN', 'A', 6): ['r1', 'r2']})
        self.assertFalse(answer['eligible'][0])
        self.assertEqual(answer['reason'][0], 'BANK_FRAME_NOT_YET_AVAILABLE')
        self.assertEqual(answer['bank_end_frame'][0], 100)
        query = row('q'); query['frame'] = 100
        self.assertFalse(own(b, [query])['eligible'][0])
        query['frame'] = 101
        self.assertTrue(own(b, [query])['eligible'][0])
        query['frame'] = 30; query['capture_id'] = 'different-capture'
        self.assertTrue(own(b, [query])['eligible'][0])

    def test_bank_frame_end_schema_and_consistency(self):
        refs = [reference('r1'), reference('r2')]
        refs[0]['bank_end_frame'] = 1
        with self.assertRaisesRegex(ValueError, 'COMPLETE_BANK_FRAME_END'):
            bank(refs)
        refs[0]['bank_end_frame'] = 100; refs[1]['bank_end_frame'] = 101
        with self.assertRaisesRegex(ValueError, 'COMPLETE_BANK_FRAME_END_MISMATCH'):
            bank(refs)

    def test_primary_is_partition_device_protocol_isolated(self):
        b = bank()
        rows = [row('other-device', device='B'), row('other-partition', partition='DEV'),
                row('other-protocol', protocol=17)]
        answer = own(b, rows)
        self.assertFalse(answer['eligible'].any())
        self.assertEqual(answer['support'].sum(), 0.)

    def test_consumed_three_device_role_remains_partition_isolated(self):
        b = bank([reference('h1', partition='HOLDOUT'), reference('h2', partition='HOLDOUT')])
        answer = own(b, [row('held-query', partition='HOLDOUT'), row('dev-query', partition='DEV')])
        self.assertEqual(answer['support'].tolist(), [1., 0.])
        with self.assertRaisesRegex(ValueError, 'SOURCE_DONORS_ONLY'):
            b.matrix([row('q', partition='HOLDOUT')], vec(1), np.zeros((1, 14)),
                     geometry(), **joined([row('q', partition='HOLDOUT')]))

    def test_diagnostic_donor_requires_explicit_valid_uid_map(self):
        b = bank([reference('r1', device='B'), reference('r2', device='B')])
        self.assertEqual(own(b)['support'][0], 0.)
        answer = own(b, override={('LEARN', 'A', 6): ['r1', 'r2']})
        self.assertEqual(answer['support'][0], 1.)
        with self.assertRaisesRegex(ValueError, 'OVERRIDE_UID'):
            own(b, override={('LEARN', 'A', 6): ['r1', 'absent']})
        with self.assertRaisesRegex(ValueError, 'DONOR_PROTOCOL_PARTITION'):
            own(b, [row('q', partition='DEV')], override={('DEV', 'A', 6): ['r1', 'r2']})

    def test_zero_radius_exact_zero_and_positive_distance(self):
        b = bank()
        self.assertEqual(own(b, geom=geometry(0., 0.))['support'][0], 1.)
        self.assertEqual(own(b, e3=vec(1, axis=1), geom=geometry(0., 0.))['support'][0], 0.)
        self.assertEqual(own(b, q14=np.full((1, 14), 1e-10), geom=geometry(0., 0.))['support'][0], 0.)

    def test_missing_source_geometry_is_explicit_fallback(self):
        b = bank([reference('r1', protocol=17), reference('r2', protocol=17)])
        answer = own(b, [row('q', protocol=17)], geom=geometry(udp=False))
        self.assertTrue(answer['eligible'][0])
        self.assertEqual(answer['support'][0], 0.)
        self.assertEqual(answer['reason'][0], 'NO_SOURCE_GEOMETRY_SUPPORT')
        with self.assertRaisesRegex(ValueError, 'GEOMETRY_PROTOCOL_MISSING'):
            own(b, geom=dict(protocols={}))

    def test_invalid_geometry_is_not_ordinary_fallback(self):
        with self.assertRaisesRegex(ValueError, 'GEOMETRY_RADIUS'):
            own(bank(), geom=geometry(-1., 1.))

    def test_empty_bank_exact_no_support(self):
        answer = own(bank([]))
        self.assertFalse(answer['eligible'][0])
        self.assertEqual(answer['support'][0], 0.)

    def test_corrupt_uid_shape_and_normalized_zero_fail(self):
        refs = [reference('r1'), reference('r2')]
        with self.assertRaisesRegex(ValueError, 'BROKEN_FEATURE_UID_JOIN'):
            m.ReferenceBank(refs, vec(2), np.zeros((2, 14)), (np.zeros(768), np.ones(768)),
                            feature_uids=['r2', 'r1'], q_uids=['r1', 'r2'])
        with self.assertRaisesRegex(ValueError, 'ORDERED_UIDS_REQUIRED'):
            m.ReferenceBank(refs, vec(2), np.zeros((2, 14)), (np.zeros(768), np.ones(768)))
        with self.assertRaisesRegex(ValueError, 'ZERO_NORM'):
            bank(refs, np.zeros((2, 768)))
        with self.assertRaisesRegex(ValueError, 'ZERO_NORM'):
            own(bank([]), e3=np.zeros((1, 768)))
        with self.assertRaisesRegex(ValueError, 'QUERY_IS_REFERENCE'):
            own(bank(refs), [row('r1')])
        with self.assertRaisesRegex(ValueError, 'NONFINITE_FEATURE'):
            own(bank(), q14=np.full((1, 14), np.nan))
        with self.assertRaisesRegex(ValueError, 'Q14_RANGE'):
            own(bank(), q14=np.full((1, 14), 2.))

    def test_duplicate_identity_and_cutoff_disagreement_fail(self):
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_UID'):
            bank([reference('r'), reference('r')])
        refs = [reference('r1'), reference('r2')]
        refs[1]['reference_end'] = 11.
        with self.assertRaisesRegex(ValueError, 'COMPLETE_BANK_END_MISMATCH'):
            bank(refs)


class SourceParameterTests(unittest.TestCase):
    def test_fit_geometry_reweights_eligible_hierarchy(self):
        refs = [reference('a1'), reference('a2'), reference('b1', device='B'),
                reference('b2', device='B'), reference('c1', device='C')]
        b = bank(refs)
        rows = [row('query-a%d' % i) for i in range(20)] + [row('b', device='B'), row('c', device='C')]
        e3 = vec(len(rows)); e3[20] = vec(1, axis=1)[0]
        q = np.zeros((len(rows), 14)); q[20] = .2
        result = m.fit_geometry(rows, e3, q, b, **joined(rows))
        self.assertEqual(result['protocols']['6']['rows'], 21)
        self.assertEqual(result['protocols']['6']['rho_z'], 1.)
        self.assertAlmostEqual(result['protocols']['6']['rho_q'], .2)
        self.assertEqual(result['protocols']['17']['status'], 'NO_SOURCE_GEOMETRY_SUPPORT')
        bad = copy.deepcopy(rows); bad[0]['fit_role'] = 'CAL'
        with self.assertRaisesRegex(ValueError, 'GEOMETRY_FIT_NORMAL_ONLY'):
            m.fit_geometry(bad, e3, q, b, **joined(bad))

    def test_scale_uses_original_class_balanced_fit_weights(self):
        rows = [row('n%d' % i) for i in range(10)] + [row('a', label=1)]
        logits = np.zeros((11, 3)); logits[-1] = [10., 20., 0.]
        result = m.fit_scales(rows, logits)
        self.assertEqual(result['scales'], [10., 20., 0.])
        self.assertAlmostEqual(result['normal_weight'], .5)
        self.assertAlmostEqual(result['attack_weight'], .5)
        rows[0]['fit_role'] = 'CAL'
        with self.assertRaisesRegex(ValueError, 'SCALE_FIT_ONLY'):
            m.fit_scales(rows, logits)

    def test_weighted_quantile_observed_no_interpolation(self):
        self.assertEqual(m.weighted_quantile([0., 10.], [.9, .1], .9), 0.)
        self.assertEqual(m.weighted_quantile([0., 10.], [.9, .1], .91), 10.)


class CorrectionTests(unittest.TestCase):
    def test_noop_preserves_float64_values_and_signed_zero(self):
        logits = np.array([[-0., 1., 2.], [2., -0., 3.]], dtype=np.float32)
        for supports, scales, lam in [([0., 0.], [1., 1., 1.], .25),
                                     ([1., 1.], [1., 1., 1.], 0.),
                                     ([1., 1.], [0., 0., 0.], .25)]:
            answer = m.apply_correction(logits, supports, scales, lam)
            self.assertEqual(answer.tobytes(), logits.astype(np.float64).tobytes())

    def test_bound_and_strict_threshold_boundary(self):
        answer = m.apply_correction(np.array([[.25, .251, 1.]]), [1.], [1., 1., 0.], .25)
        self.assertEqual(answer[0, 0], 0.)
        self.assertEqual((answer > 0).tolist(), [[False, True, True]])
        self.assertTrue(np.all(np.array([[.25, .251, 1.]]) - answer <= np.array([.25, .25, 0.])))

    def test_ordered_float64_ensemble_and_validation(self):
        x = {227: np.array([1.]), 27: np.array([1e16]), 127: np.array([-1e16])}
        self.assertEqual(m.ordered_ensemble(x)[0], 1. / 3.)
        with self.assertRaisesRegex(ValueError, 'FIXED_SEED_ORDER'):
            m.ordered_ensemble(x, seed_order=(227, 127, 27))
        for a, scales, lam in [([1.1], [1.] * 3, .25), ([1.], [-1., 1., 1.], .25),
                               ([1.], [1.] * 3, .2)]:
            with self.assertRaises(ValueError):
                m.apply_correction(np.ones((1, 3)), a, scales, lam)

    def test_ensemble_bitwise_legacy_layout_with_cancellation(self):
        rng = np.random.RandomState(43)
        vectors = [rng.standard_t(1.2, 1003) * 1e12 for _ in range(3)]
        vectors[0][:4] = [1e16, 1e200, -0., 1e-200]
        vectors[1][:4] = [-1e16, -1e200, -0., -1e-200]
        vectors[2][:4] = [1., 1., -0., 1e-300]
        legacy = np.stack(vectors).mean(0, dtype=np.float64)
        for x in (np.column_stack(vectors), np.asfortranarray(np.column_stack(vectors)),
                  {s: vectors[j] for j, s in enumerate(m.SEEDS)}):
            self.assertEqual(m.ordered_ensemble(x).tobytes(), legacy.tobytes())

    def test_finite_logits_with_overflowing_ensemble_are_rejected(self):
        largest = np.finfo(np.float64).max
        with self.assertRaisesRegex(ValueError, 'ENSEMBLE_NONFINITE'):
            m.ordered_ensemble(np.array([[largest, largest, largest]]))


class SourceProtectionTests(unittest.TestCase):
    def choose(self, logits, *, cuts=None, ensemble_cut=0., scales=None, b=None, rows=None):
        rows = [row('attack', label=1, fit_role='CAL')] if rows is None else rows
        return m.choose_lambda(rows, np.asarray(logits), [0.] * 3 if cuts is None else cuts,
                               ensemble_cut, [1.] * 3 if scales is None else scales,
                               bank() if b is None else b, vec(len(rows)),
                               np.zeros((len(rows), 14)), geometry(), **joined(rows))

    def test_one_seed_vetoes_other_safe_seeds(self):
        result = self.choose([[.075, 10., 10.]])
        self.assertEqual(result['selected_lambda'], .05)
        self.assertEqual(result['candidates'][2]['newly_missed_uids']['27'], ['attack'])
        self.assertEqual(result['candidates'][2]['new_miss_count']['127'], 0)

    def test_ensemble_vetoes_individually_safe_seeds(self):
        result = self.choose([[1., 1., 1.]], ensemble_cut=.95)
        self.assertEqual(result['selected_lambda'], 0.)
        self.assertEqual(result['candidates'][1]['new_miss_count'],
                         {'27': 0, '127': 0, '227': 0, 'ensemble': 1})

    def test_all_source_donors_protected_not_only_own(self):
        refs = [reference('r1', device='B'), reference('r2', device='B')]
        result = self.choose([[.075, 10., 10.]], b=bank(refs))
        self.assertEqual(result['selected_lambda'], .05)
        self.assertEqual(result['eligible_pairs'], 1)
        self.assertEqual(result['roster'][0]['device'], 'B')

    def test_saturated_calibration_reports_no_reachable_changes(self):
        result = self.choose([[100., 100., 100.]])
        self.assertEqual(result['selected_lambda'], .25)
        self.assertEqual(result['attack_support_share'], 1.)
        self.assertFalse(result['source_zero_misses_is_target_guarantee'])
        last = result['candidates'][-1]
        self.assertEqual(sum(last['cap_reachable_detected_attack_count'].values()), 0)
        self.assertEqual(last['minimum_positive_support_margin_over_cap']['ensemble'], 400.)

    def test_existing_miss_not_counted_as_added_miss(self):
        result = self.choose([[-1., -1., -1.]])
        self.assertEqual(result['selected_lambda'], .25)
        self.assertEqual(sum(result['candidates'][-1]['new_miss_count'].values()), 0)

    def test_reject_target_rows_reference_role_and_component_leakage(self):
        for kwargs in [dict(partition='DEV'), dict(fit_role='FIT'), dict(label=0)]:
            r = row('a', label=1, fit_role='CAL'); r.update(kwargs)
            with self.assertRaisesRegex(ValueError, 'PROTECTION_CAL_ATTACK_ONLY'):
                self.choose([[1., 1., 1.]], rows=[r])
        with self.assertRaisesRegex(ValueError, 'CAL_REFERENCE_COMPONENT_LEAKAGE'):
            self.choose([[1., 1., 1.]], rows=[row('a', component='r1', label=1, fit_role='CAL')])
        b = bank([reference('r1', partition='DEV'), reference('r2', partition='DEV')])
        with self.assertRaisesRegex(ValueError, 'SOURCE_DONORS_ONLY'):
            self.choose([[1., 1., 1.]], b=b)

    def test_whole_bank_cutoff_and_protocol_filter_source_matrix(self):
        refs = [reference('r1'), reference('r2'), reference('u1', protocol=17),
                reference('u2', protocol=17), reference('b1', device='B'), reference('b2', device='B')]
        for r in refs[-2:]:
            r['reference_end'] = 30.
        result = self.choose([[100., 100., 100.]], b=bank(refs))
        self.assertEqual(result['eligible_pairs'], 1)
        self.assertEqual(result['positive_support_pairs'], 1)
        self.assertEqual(len(result['roster']), 3)
        self.assertEqual(result['bank_coverage'][2]['status'], 'NO_LEGAL_CAL_ATTACK_PAIRS')

    def test_no_legal_pairs_does_not_claim_observed_safety_coverage(self):
        result = self.choose([[.01, .01, .01]], b=bank([]))
        self.assertEqual(result['coverage_status'], 'NO_ELIGIBLE_PAIRS')
        self.assertEqual(result['eligible_pairs'], 0)
        self.assertIn('never coverage', result['candidate_pass_means'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
