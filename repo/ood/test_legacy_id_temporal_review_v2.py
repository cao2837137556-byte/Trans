import unittest

import legacy_id_temporal_review_v2 as review


def packet(frame, session, digest):
    return {'frame_number_1based': frame, 'session_key_sha256': session, 'packet_sha256': digest}


def candidate(member, frame, session):
    return {'raw_member': member, 'frame_number_1based': frame, 'session_key_sha256': session,
            'uid': member + ':' + str(frame)}


class CrossCaptureTests(unittest.TestCase):
    def test_prefix_overlap_removes_whole_candidate_session(self):
        packets = {'old': [packet(1, 's0', 'prefix'), packet(2, 's0', 'target')],
                   'new': [packet(1, 'new-key', 'prefix'), packet(2, 'new-key', 'different-target')]}
        exposure = [{'member': 'old', 'actual_cached_frame_1based': 2, 'semantic_timestamp_frame_1based': 2,
                     'actual_session_key_sha256': 's0', 'semantic_session_key_sha256': 's0'}]
        kept, excluded, stats = review.separate([candidate('new', 2, 'new-key')], packets, exposure)
        self.assertEqual(kept, [])
        self.assertIn('CAUSAL_PREFIX', excluded[0]['exclusion_reason'])

    def test_representative_keeps_all_targets_of_one_capture(self):
        packets = {'a': [packet(1, 's1', 'a1'), packet(2, 's1', 'a2')],
                   'b': [packet(1, 's1', 'b1'), packet(2, 's1', 'b2')]}
        candidates = [candidate(m, f, 's1') for m in ('b', 'a') for f in (2, 1)]
        kept, excluded, stats = review.separate(candidates, packets, [])
        self.assertEqual([(c['raw_member'], c['frame_number_1based']) for c in kept], [('a', 1), ('a', 2)])
        self.assertEqual(len(excluded), 2)
        self.assertTrue(all(c['retained_member'] == 'a' for c in excluded))

    def test_raw_session_overlap_is_rejected_despite_different_bytes(self):
        packets = {'old': [packet(1, 'same', 'old')], 'new': [packet(1, 'same', 'new')]}
        exposure = [{'member': 'old', 'actual_cached_frame_1based': 1, 'semantic_timestamp_frame_1based': 1,
                     'actual_session_key_sha256': 'same', 'semantic_session_key_sha256': 'same'}]
        kept, excluded, _ = review.separate([candidate('new', 1, 'same')], packets, exposure)
        self.assertEqual(len(kept), 0)
        self.assertIn('CANONICAL_SESSION_EXPOSED', excluded[0]['exclusion_reason'])


if __name__ == '__main__':
    unittest.main()
