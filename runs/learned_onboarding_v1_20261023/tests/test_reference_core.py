import importlib.util
import unittest
from pathlib import Path

import numpy as np


SPEC = importlib.util.spec_from_file_location(
    'reference_core', Path(__file__).resolve().parents[1] / 'src' / 'reference_core.py')
core = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(core)


def row(uid, *, device='own', component='a', capture='old', frame=1,
        timestamp=1.0, end=2.0, protocol=6, partition='LEARN',
        use='REFERENCE', frame_end=None):
    result = dict(uid=uid, device=device, component_id=component,
                  capture_id=capture, frame=frame, timestamp=timestamp,
                  protocol=protocol, partition=partition, use=use,
                  label=0, source_sha256='sha', owner='owner', session_id='s')
    if use == 'REFERENCE':
        result['reference_end'] = end
        if frame_end is not None:
            result['bank_end_frame'] = frame_end
    return result


def data(rows, q_values=None):
    n = len(rows)
    e3 = np.zeros((n, 768), dtype=np.float64)
    e3[:, 0] = 1
    q = np.zeros((n, 14), dtype=np.float64)
    if q_values is not None:
        q[:, 0] = q_values
    uids = [r['uid'] for r in rows]
    return e3, q, uids


def bank(rows, q_values=None, **kwargs):
    e3, q, uids = data(rows, q_values)
    return core.ReferenceBank(rows, e3, q, (np.zeros(768), np.ones(768)),
                              feature_uids=uids, q_uids=uids, **kwargs)


def trace(refs, queries, *, q_values=None, donor_keys=None,
          reference_uids=None, **kwargs):
    b = bank(refs, **kwargs)
    e3, q, uids = data(queries, q_values)
    return b.trace(queries, e3, q, feature_uids=uids, q_uids=uids,
                   donor_keys=donor_keys, reference_uids=reference_uids)


class ReferenceCoreTests(unittest.TestCase):
    def setUp(self):
        self.refs = [row('r1', component='a'), row('r2', component='b')]
        self.query = row('q', use='QUERY', timestamp=3.0, frame=3,
                         capture='new')

    def test_causal_cutoff_and_component_rules(self):
        result = trace(self.refs, [self.query])
        self.assertTrue(result['eligible'][0])
        self.assertEqual(result['legal_component_count'][0], 2)
        self.assertEqual(result['matched_reference_uids'][0].tolist(),
                         ['r1', 'r2'])
        equal = dict(self.query, timestamp=2.0)
        self.assertEqual(trace(self.refs, [equal])['reason'][0],
                         'BANK_NOT_YET_AVAILABLE')
        same = [dict(r, capture_id='new', frame=3) for r in self.refs]
        self.assertEqual(trace(same, [self.query])['reason'][0],
                         'FEWER_THAN_TWO_LEGAL_COMPONENTS')
        earlier = [dict(r, capture_id='new', frame=2) for r in self.refs]
        self.assertTrue(trace(earlier, [self.query])['eligible'][0])
        single = [dict(r, component_id='a') for r in self.refs]
        self.assertFalse(trace(single, [self.query])['eligible'][0])
        same_frame = [dict(r, capture_id='new', frame=3) for r in self.refs]
        self.assertFalse(trace(same_frame, [self.query])['eligible'][0])

    def test_complete_cutoff_survives_subset_and_frame_end(self):
        refs = [row('a', component='a', end=5), row('b', component='b', end=5),
                row('c', component='c', end=5)]
        early = dict(self.query, timestamp=4)
        out = trace(refs, [early], reference_uids=[('a', 'b')])
        self.assertEqual(out['reason'][0], 'BANK_NOT_YET_AVAILABLE')
        same_capture = [row('a', component='a', capture='new', frame=1,
                            frame_end=4),
                        row('b', component='b', capture='new', frame=2,
                            frame_end=4)]
        self.assertEqual(trace(same_capture, [self.query])['reason'][0],
                         'BANK_FRAME_NOT_YET_AVAILABLE')
        with self.assertRaisesRegex(ValueError, 'FRAME_END_MISMATCH'):
            bank([dict(same_capture[0]), dict(same_capture[1], bank_end_frame=5)])

    def test_complete_device_cutoff_cross_protocol_and_earlier_same_component(self):
        refs = [row('a1', component='a', capture='new', frame=1, end=5),
                row('a2', component='a', capture='new', frame=2, end=5),
                row('b1', component='b', capture='old', frame=1, end=5),
                row('p17', component='z', protocol=17, end=5)]
        early = dict(self.query, timestamp=4, capture_id='new', frame=3,
                     component_id='a')
        self.assertEqual(trace(refs, [early])['reason'][0],
                         'BANK_NOT_YET_AVAILABLE')
        later = dict(early, timestamp=6)
        out = trace(refs, [later])
        self.assertTrue(out['eligible'][0])
        self.assertEqual(out['legal_component_count'][0], 2)
        self.assertEqual(out['matched_components'][0].tolist(), ['a', 'b'])
        self.assertEqual(out['bank_end'][0], 5)
        with self.assertRaisesRegex(ValueError, 'COMPLETE_BANK_END_MISMATCH'):
            bank([dict(r, reference_end=6) if r['uid'] == 'p17' else r
                  for r in refs])

    def test_uid_ties_and_distance(self):
        refs = [row('z', component='a'), row('a', component='a'),
                row('m', component='b'), row('b', component='c')]
        out = trace(refs, [self.query])
        self.assertEqual(out['matched_reference_uids'][0].tolist(), ['a', 'b'])
        shuffled = list(reversed(refs))
        other = trace(shuffled, [self.query])
        self.assertEqual(out['matched_reference_uids'][0].tolist(),
                         other['matched_reference_uids'][0].tolist())
        self.assertEqual(out['d'][0].tolist(), [0, 0])

    def test_wrong_bank_exact_subset_and_fallback(self):
        refs = self.refs + [row('d1', device='donor', component='x'),
                            row('d2', device='donor', component='x'),
                            row('d3', device='donor', component='y'),
                            row('d4', device='donor', component='z')]
        b = bank(refs)
        e3, q, uids = data([self.query])
        own = b.trace([self.query], e3, q, feature_uids=uids, q_uids=uids)
        plan = b.plan_wrong([self.query], own)
        self.assertEqual(plan['donor_keys'][0], ('LEARN', 'donor', 6))
        self.assertEqual(plan['reference_uids'][0], ('d1', 'd3'))
        wrong = b.trace([self.query], e3, q, feature_uids=uids,
                        q_uids=uids, donor_keys=plan['donor_keys'],
                        reference_uids=plan['reference_uids'])
        self.assertTrue(wrong['eligible'][0])
        self.assertEqual(wrong['legal_reference_count'][0], 2)
        impossible = bank(self.refs + [row('d1', device='donor', component='x'),
                                       row('d2', device='donor', component='x')])
        own2 = impossible.trace([self.query], e3, q, feature_uids=uids,
                                q_uids=uids)
        self.assertEqual(impossible.plan_wrong([self.query], own2)['reason'][0],
                         'NO_EXACT_WRONG_BANK')
        unmatched = impossible.trace([self.query], e3, q,
                                     feature_uids=uids, q_uids=uids,
                                     donor_keys=[None], reference_uids=[None])
        self.assertEqual(unmatched['reason'][0], 'NO_EXACT_WRONG_BANK')
        with self.assertRaisesRegex(ValueError, 'DONOR_PROTOCOL_PARTITION'):
            b.trace([self.query], e3, q, feature_uids=uids, q_uids=uids,
                    donor_keys=[('DEV', 'missing', 6)])

    def test_wrong_donor_frame_end_and_per_query_keys(self):
        refs = self.refs + [row('x', device='a_donor', component='x',
                                capture='new', frame=1, frame_end=4),
                            row('y', device='a_donor', component='y',
                                capture='new', frame=2, frame_end=4),
                            row('u', device='b_donor', component='u'),
                            row('v', device='b_donor', component='v')]
        queries = [self.query, dict(self.query, uid='q2', frame=5)]
        b = bank(refs)
        e3, q, uids = data(queries)
        own = b.trace(queries, e3, q, feature_uids=uids, q_uids=uids)
        plan = b.plan_wrong(queries, own)
        self.assertEqual(plan['donor_keys'],
                         [('LEARN', 'b_donor', 6), ('LEARN', 'a_donor', 6)])
        out = b.trace(queries, e3, q, feature_uids=uids, q_uids=uids,
                      donor_keys=plan['donor_keys'],
                      reference_uids=plan['reference_uids'])
        self.assertTrue(out['eligible'].all())
        self.assertIsNone(out['bank_end_frame'][0])
        self.assertEqual(out['bank_end_frame'][1], 4)
        self.assertEqual(out['legal_component_count'].tolist(), [2, 2])

    def test_prebank_source_stop_and_target_whitelist(self):
        with self.assertRaisesRegex(ValueError, 'QUERY_IS_REFERENCE'):
            trace(self.refs, [dict(self.refs[0], use='QUERY')],
                  allow_target_prebank=True)
        target = [row('history', partition='DEV', component='a',
                      capture='c', frame=1, timestamp=1, frame_end=3),
                  row('other', partition='DEV', component='b',
                      capture='c', frame=2, timestamp=1, frame_end=3)]
        query = dict(target[0], use='QUERY')
        out = trace(target, [query], allow_target_prebank=True)
        self.assertEqual(out['reason'][0], 'PREBANK_HISTORY_HEAD_ONLY')
        self.assertFalse(out['eligible'][0])
        self.assertIsNotNone(out['prebank_audit'][0])
        with self.assertRaisesRegex(ValueError, 'HISTORY_REPLAY_IDENTITY_MISMATCH'):
            trace(target, [dict(query, source_sha256='bad')],
                  allow_target_prebank=True)
        with self.assertRaisesRegex(ValueError, 'HISTORY_REPLAY_ROLE_OR_SOURCE'):
            trace(target, [dict(query, partition='DEV', label=1)],
                  allow_target_prebank=True)
        source_elsewhere = [row('cross', device='other', component='x'),
                            row('other', device='other', component='y')]
        with self.assertRaisesRegex(ValueError, 'QUERY_IS_REFERENCE'):
            trace(source_elsewhere, [dict(source_elsewhere[0], use='QUERY',
                                          device='own')])

    def test_empty_and_single_query(self):
        b = bank(self.refs)
        e3, q, uids = data([])
        out = b.trace([], e3, q, feature_uids=uids, q_uids=uids)
        self.assertEqual(out['eligible'].shape, (0,))
        self.assertEqual(core.make_features([], q, np.array([]), 0, 1, out).shape,
                         (0, 50))
        e3, q, uids = data([self.query])
        out = b.trace([self.query], e3, q, feature_uids=uids, q_uids=uids)
        self.assertEqual(out['eligible'].shape, (1,))

    def test_input_slots_mask_and_correction(self):
        q = dict(self.query, protocol=17)
        refs = [dict(r, protocol=17) for r in self.refs]
        out = trace(refs, [q], q_values=[0.5])
        inputs = core.make_features([q], np.array([[0.5] + [0] * 13]),
                                    np.array([3.]), 1., 2., out)
        self.assertEqual(inputs.shape, (1, 50))
        self.assertEqual(inputs.dtype, np.float32)
        self.assertAlmostEqual(float(inputs[0, 0]), 0.5)
        self.assertAlmostEqual(float(inputs[0, 14]), 0.5)
        self.assertAlmostEqual(float(inputs[0, 28]), 0.5)
        self.assertAlmostEqual(float(inputs[0, 44]), 0.5 / np.sqrt(14))
        self.assertAlmostEqual(float(inputs[0, 46]), 0.125)
        self.assertAlmostEqual(float(inputs[0, 47]), 1 / 6)
        self.assertEqual(inputs[0, 48:].tolist(), [0, 1])
        masked = core.make_features([q], np.array([[0.5] + [0] * 13]),
                                    np.array([3.]), 1., 2., out, query_only=True)
        self.assertTrue(np.all(masked[:, 14:46] == 0))
        self.assertEqual(masked[0, 47], 0)
        self.assertEqual(masked[0, 46], inputs[0, 46])
        source = np.array([1.0, -0.0, 3.0], dtype=np.float64)
        a = np.array([0.5, 0.5, 0.5])
        eligible = np.array([True, True, False])
        scales = np.array([2., 0., 2.])
        zero = core.apply_correction(source, a, eligible, scales, 0)
        self.assertTrue(np.array_equal(zero.view(np.uint64),
                                       source.view(np.uint64)))
        result = core.apply_correction(source, a, eligible, scales, 0.25)
        self.assertEqual(result[0], 0.75)
        self.assertTrue(np.array_equal(result[1:].view(np.uint64),
                                       source[1:].view(np.uint64)))

    def test_invalid_join_and_zero_norm(self):
        e3, q, uids = data(self.refs)
        with self.assertRaisesRegex(ValueError, 'BROKEN_FEATURE_UID_JOIN'):
            core.ReferenceBank(self.refs, e3, q,
                               (np.zeros(768), np.ones(768)),
                               feature_uids=list(reversed(uids)), q_uids=uids)
        with self.assertRaisesRegex(ValueError, 'NONFINITE_OR_ZERO_NORM_E3'):
            core.ReferenceBank(self.refs, np.zeros_like(e3), q,
                               (np.zeros(768), np.ones(768)),
                               feature_uids=uids, q_uids=uids)


if __name__ == '__main__':
    unittest.main()
