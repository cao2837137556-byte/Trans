"""Synthetic geometry checks only: no real heads, cache, queries or references."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lg.geometry import DualBank, _ratio_columns
from lg.legacy import get_core


CORE = get_core()
NORMALIZER = (np.zeros(768), np.ones(768))


def geometry(z=.07, q=.07):
    return {'protocols': {str(p): {'status': 'READY', 'rho_z': z, 'rho_q': q}
                          for p in (6, 17)}}


def rows(count=16, components=1, device='A', partition='LEARN'):
    answer = []
    for i in range(count):
        answer.append(dict(uid='r%03d' % i, device=device, partition=partition,
                           protocol=6, component_id='c%d' % (i % components),
                           capture_id='capture', timestamp=float(i + 1), frame=i + 1,
                           reference_end=100., bank_end_frame=100,
                           use='REFERENCE', label=0))
    return answer


def query(uid='q', **kw):
    answer = dict(uid=uid, device='A', partition='LEARN', protocol=6,
                  component_id='query', capture_id='later', timestamp=200., frame=200,
                  use='QUERY', label=1)
    answer.update(kw)
    return answer


def features(values):
    values = np.asarray(values, dtype=np.float64)
    z = np.zeros((len(values), 768), dtype=np.float64)
    z[:, 0], z[:, 1] = np.cos(values), np.sin(values)
    return z, np.repeat(values[:, None], 14, axis=1)


def bank(refs=None, values=None, geom=None, **kw):
    refs = rows() if refs is None else refs
    values = np.linspace(0., .3, len(refs)) if values is None else values
    z, q = features(values)
    return DualBank(refs, z, q, NORMALIZER,
                    geometry() if geom is None else geom, core=CORE, **kw)


class GeometryTests(unittest.TestCase):
    def test_exact_zero_radius_semantics(self):
        actual = _ratio_columns(np.array([[0., 1., 2.], [1., 0., 0.]]), [0., 0., 2.])
        np.testing.assert_array_equal(actual, [[0., np.inf, 1.], [np.inf, 0., 0.]])

    def test_scale_audit_arrays_are_fixed_unicode_and_pickle_free(self):
        b = bank()
        arrays = b.scale_arrays()
        self.assertEqual(arrays['neighbor_uids'].shape, (16, 5))
        self.assertEqual(arrays['uid'].tolist(), [r['uid'] for r in b.rows])
        self.assertEqual(arrays['neighbor_uids'].dtype.kind, 'U')
        for i in np.flatnonzero(arrays['ready']):
            self.assertEqual(arrays['neighbor_uids'][i].tolist(), list(b.local_neighbor_uids[i]))
        not_ready = bank(values=np.zeros(16)).scale_arrays()
        self.assertTrue(np.all(not_ready['neighbor_uids'] == ''))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'scale.npz'
            np.savez_compressed(path, **arrays)
            with np.load(path, allow_pickle=False) as restored:
                for name in restored.files:
                    self.assertNotEqual(restored[name].dtype.kind, 'O')

    def test_new_one_component_attack_eligibility_and_shared_pair_count(self):
        counts = []
        b = bank(counter=counts.append)
        self.assertEqual(sum(counts), 16 * 15 // 2)
        self.assertGreater(b.local_ready.sum(), 1)
        z, q = features([.15])
        answer = b.own([query()], z, q)
        self.assertEqual(sum(counts), 16 * 15 // 2 + 16)
        self.assertFalse(answer['eligible_d0'][0])
        self.assertTrue(answer['eligible_local'][0])
        self.assertEqual(answer['branch'][0], '1C')
        self.assertEqual(answer['d0'][0], 0.)
        self.assertGreater(answer['local'][0], 0.)
        # An attack can be withdrawn only on L: this must reach the risk caller.
        self.assertGreater(.001, 0.)
        self.assertLess(.001 - .25 * answer['local'][0], 0.)

    def test_d0_exact_parity_with_frozen_core_and_one_distance_pass(self):
        refs = rows(16, components=2)
        values = np.linspace(0., .3, 16)
        z, q = features(values)
        geom = geometry()
        counts = []
        b = DualBank(refs, z, q, NORMALIZER, geom, core=CORE, counter=counts.append)
        frozen = CORE.ReferenceBank(refs, z, q, NORMALIZER,
                                    feature_uids=[r['uid'] for r in refs], q_uids=[r['uid'] for r in refs])
        queries = [query('q%d' % i) for i in range(3)]
        query_z, query_q = features([.02, .15, .8])
        before = sum(counts)
        result = b.own(queries, query_z, query_q)
        old = frozen.own(queries, query_z, query_q, geom,
                         feature_uids=[r['uid'] for r in queries], q_uids=[r['uid'] for r in queries])
        self.assertEqual(sum(counts) - before, 3 * 16)
        np.testing.assert_array_equal(result['d0'], old['support'])
        np.testing.assert_array_equal(result['eligible_d0'], old['eligible'])
        np.testing.assert_array_equal(result['second_joint'], old['second_joint'])
        np.testing.assert_array_equal(result['matched_reference_uids'], old['matched_reference_uids'])
        self.assertTrue(np.all(result['local'] >= result['d0']))

    def test_time_blocks_duplicates_and_zero_axes(self):
        b = bank(values=np.zeros(16), geom=geometry(0., 0.))
        self.assertFalse(b.local_ready.any())
        z, q = features([0.])
        result = b.own([query()], z, q)
        self.assertFalse(result['localready'][0])
        self.assertEqual(result['local'][0], 0.)
        self.assertFalse(result['eligible_local'][0])

    def test_same_five_neighbors_used_in_both_axes_and_radius_caps(self):
        b = bank()
        for i in np.flatnonzero(b.local_ready):
            neighbor = np.asarray(b.local_dependencies[i])
            self.assertEqual(len(neighbor), 5)
            dz = np.clip(1. - b.z[i:i+1] @ b.z[neighbor].T, 0., 2.).ravel()
            dq = np.sqrt(np.mean((b.q14[i] - b.q14[neighbor]) ** 2, axis=1))
            self.assertAlmostEqual(b.local_rho_z[i], min(dz.max(), .14, 2.))
            self.assertAlmostEqual(b.local_rho_q[i], min(dq.max(), .14))
            self.assertLessEqual(b.local_rho_z[i], .14)
            self.assertLessEqual(b.local_rho_q[i], .14)

    def test_reference_streaming_matches_independent_small_dense_oracle(self):
        # More than 64 positions crosses the triangular streaming tile boundary.
        refs = rows(67, components=3)
        values = np.linspace(0., .3, len(refs))
        values[[11, 31, 61]] = values[3]  # exact repeated vectors across blocks
        calls = []
        b = bank(refs, values=values, counter=calls.append)
        self.assertEqual(sum(calls), 67 * 66 // 2)
        blocks = {}
        for component in {r['component_id'] for r in refs}:
            ordered = sorted([i for i, r in enumerate(refs) if r['component_id'] == component],
                             key=lambda i: (refs[i]['timestamp'], refs[i]['frame'], refs[i]['uid']))
            for rank, i in enumerate(ordered):
                blocks[i] = (component, min(8, len(ordered)) * rank // len(ordered))
        # Deliberately implement the reference definition directly per center,
        # independently of the streaming update and fingerprint code.
        for center in range(len(refs)):
            dz = np.clip(1. - b.z[center] @ b.z.T, 0., 2.)
            dq = np.sqrt(np.mean((b.q14[center] - b.q14) ** 2, axis=1))
            by_block = {}
            for j in range(len(refs)):
                if blocks[j] == blocks[center]:
                    continue
                key = (max(dz[j] / .07, dq[j] / .07), refs[j]['uid'])
                previous = by_block.get(blocks[j])
                if previous is None or key < previous[0]:
                    by_block[blocks[j]] = (key, j)
            unique = []
            for _, j in sorted(by_block.values(), key=lambda pair: refs[pair[1]]['uid']):
                if np.array_equal(b.z[j], b.z[center]) and np.array_equal(b.q14[j], b.q14[center]):
                    continue
                if any(np.array_equal(b.z[j], b.z[k]) and np.array_equal(b.q14[j], b.q14[k])
                       for k in unique):
                    continue
                unique.append(j)
            unique.sort(key=lambda j: (max(dz[j] / .07, dq[j] / .07), refs[j]['uid']))
            ready = len(unique) >= 5 and max(dz[unique[4]] / .07, dq[unique[4]] / .07) <= 2
            self.assertEqual(b.local_ready[center], ready)
            if ready:
                selected = unique[:5]
                self.assertEqual(b.local_neighbor_uids[center], tuple(refs[j]['uid'] for j in selected))
                self.assertAlmostEqual(b.local_rho_z[center], min(max(dz[selected]), .14, 2.))
                self.assertAlmostEqual(b.local_rho_q[center], min(max(dq[selected]), .14))

    def test_bank_cutoff_frame_and_scale_dependency_delivery(self):
        b = bank()
        z, q = features([.15])
        for row in (query(timestamp=100.), query(capture_id='capture', frame=100)):
            answer = b.own([row], z, q)
            self.assertFalse(answer['eligible_local'][0])
            self.assertFalse(answer['eligible_d0'][0])
        # Without frame-end metadata, per-reference dependency checks still stop
        # a scale whose selected neighbor has not arrived in the query capture.
        refs = rows()
        for r in refs:
            r.pop('bank_end_frame')
            r['frame'] *= 20
        delayed = bank(refs)
        answer = delayed.own([query(capture_id='capture', frame=3)], z, q)
        self.assertFalse(answer['eligible_local'][0])

    def test_true_two_components_cannot_fall_back_to_one_component_rule(self):
        b = bank(rows(16, components=2))
        # Simulate the algorithm's quality outcome: only one component ready.
        for i, row in enumerate(b.rows):
            if row['component_id'] == 'c1':
                b.local_ready[i] = False
        z, q = features([.15])
        answer = b.own([query()], z, q)
        self.assertTrue(answer['eligible_d0'][0])
        self.assertFalse(answer['localready'][0])
        np.testing.assert_array_equal(answer['local'], answer['d0'])

        # An originally 2C bank cannot become true 1C merely because one
        # component's frames have not arrived yet (even without end-frame tags).
        refs = rows(24, components=2)
        for r in refs:
            r.pop('bank_end_frame')
            if r['component_id'] == 'c1':
                r['frame'] += 1000
        b = bank(refs)
        answer = b.own([query(capture_id='capture', frame=100)], z, q)
        self.assertEqual(answer['legal_component_count'][0], 1)
        self.assertGreaterEqual(answer['legal_position_count'][0], 8)
        self.assertFalse(answer['eligible_d0'][0])
        self.assertFalse(answer['eligible_local'][0])
        self.assertEqual(answer['branch'][0], 'OTHER')

    def test_uid_join_and_nonfinite_identity_failures(self):
        with self.assertRaisesRegex(ValueError, 'BROKEN_FEATURE_UID_JOIN'):
            bank(feature_uids=['wrong'] * 16)
        b = bank()
        z, q = features([.15])
        q[0, 0] = np.nan
        with self.assertRaisesRegex(ValueError, 'NONFINITE_FEATURE'):
            b.own([query()], z, q)
        with self.assertRaisesRegex(ValueError, 'EMPTY_OR_DUPLICATE_UID'):
            b.own([query(), query()], *features([.1, .2]))

    def test_source_donor_matrix_includes_new_one_component_and_raw_adapter(self):
        b = bank()
        z, q = features([.15])
        result = b.matrix([query(device='unseen')], z, q)
        self.assertEqual(result['d0'].shape, (1, 1))
        self.assertFalse(result['eligible_d0'][0, 0])
        self.assertTrue(result['eligible_local'][0, 0])
        self.assertEqual(result['branch'][0, 0], '1C')
        self.assertEqual(len(result['roster']), 1)
        refs = rows(16, components=2)
        ref_z, ref_q = features(np.linspace(0., .3, 16))
        counts = []
        raw_bank = DualBank(refs, ref_z, ref_q, NORMALIZER, None, core=CORE, counter=counts.append)
        old = CORE.ReferenceBank(refs, ref_z, ref_q, NORMALIZER,
                                 feature_uids=[r['uid'] for r in refs], q_uids=[r['uid'] for r in refs])
        actual = raw_bank.own([query()], z, q, _raw_distances=True)
        expected = old.own([query()], z, q, None, feature_uids=['q'], q_uids=['q'], _raw_distances=True)
        np.testing.assert_array_equal(actual['second_dz'], expected['second_dz'])
        np.testing.assert_array_equal(actual['second_dq'], expected['second_dq'])
        self.assertEqual(sum(counts), 16)

    def test_missing_protocol_geometry_falls_back_and_noexpand_certificate(self):
        geom = geometry()
        geom['protocols']['6'] = {'status': 'NO_SOURCE_GEOMETRY_SUPPORT'}
        b = bank(rows(16, components=2), geom=geom)
        self.assertFalse(b.has_2c_expansion)
        z, q = features([.15])
        answer = b.own([query()], z, q)
        self.assertTrue(answer['eligible_d0'][0])
        self.assertFalse(answer['localready'][0])
        self.assertEqual(answer['local'][0], 0.)
        dense = bank(rows(16, components=2), geom=geometry(1., 1.))
        self.assertTrue(dense.local_ready.any())
        self.assertFalse(dense.has_2c_expansion)

    def test_history_replay_remains_head_only_for_both_paths(self):
        refs = rows(partition='DEV')
        for r in refs:
            r.update(source_sha256='a' * 64, owner='owner', session_id='session')
        b = bank(refs)
        historical = copy.deepcopy(refs[0])
        historical['use'] = 'QUERY'
        z, q = features([0.])
        answer = b.own([historical], z, q)
        self.assertFalse(answer['eligible_d0'][0])
        self.assertFalse(answer['eligible_local'][0])
        self.assertEqual(answer['d0'][0], 0.)
        self.assertEqual(answer['local'][0], 0.)
        historical['frame'] += 1
        with self.assertRaisesRegex(ValueError, 'HISTORY_REPLAY_IDENTITY_MISMATCH'):
            b.own([historical], z, q)


if __name__ == '__main__':
    unittest.main()
