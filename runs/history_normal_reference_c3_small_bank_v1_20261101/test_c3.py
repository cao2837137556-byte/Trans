"""Generated checks for selection identity, causal boundaries and adoption gates."""
import copy
import unittest
from common import *
from prepare import walk_capture
import legacy_reference_sample_prepare_v1 as prep
from test_continuous_repair_v3 import packet
from hnr.encoding import physical_batch


def candidate(i):
    return dict(uid=str(i), source_sha256='a'*64, frame=i + 1, owner='aa', component_id='c',
                session_id='s', protocol=6, device='any-device')


def spec(capture='c', source='a'*64, count=2, start=1., end=2.):
    return dict(capture_id=capture, sha256=source, expected_packets=count, first=start, last=end,
                owner='aa', device='any-device', partition='DEV', member_path='normal/LAN_WATCH/generated',
                normality_evidence='synthetic normal fixture')


def pool_fixture():
    def record(rate, fp):
        return dict(corrected={'normal': dict(rows=100, positive=fp, weighted_rate=rate)})
    result = {}
    for pool in ('CIC_DEV', 'UNSW_DEV'):
        views = {}
        for view in ('full', 'post_window_primary'):
            reports = {}
            for head in ('27', '127', '227', 'ensemble'):
                group = dict(group=dict(device=HEIM), **record(.08, 8))
                reports[head] = dict(**record(.08, 8), groups={'device': [group]}, protection={'status': 'PASS'})
            views[view] = dict(retained_uid_sha256='same', weights_sha256='same', reports=reports)
        result[pool] = dict(views=views)
    return result


class SelectionTests(unittest.TestCase):
    def test_complete_small_domain_and_preserve_existing(self):
        rr = [candidate(i) for i in range(6)]
        extra, branch = complete_small_group(rr[::-1], [rr[2]])
        self.assertEqual({r['uid'] for r in extra}, {'0', '1', '3', '4', '5'})
        self.assertEqual(branch, 'COMPLETE_SMALL_GROUP')

    def test_fixed_cap_boundary(self):
        rr = [candidate(i) for i in range(4097)]
        self.assertEqual(len(complete_small_group(rr[:4096], [rr[0]])[0]), 4095)
        self.assertEqual(complete_small_group(rr, [rr[0]])[0], [])

    def test_same_packet_different_uid_cannot_become_extra(self):
        one = candidate(1); twin = dict(one, uid='different')
        with self.assertRaisesRegex(ValueError, 'PHYSICAL'): complete_small_group([one, twin], [])

    def test_old_reference_missing_or_reidentified_stops(self):
        with self.assertRaisesRegex(ValueError, 'NOT_IN_LEGAL'): complete_small_group([candidate(0)], [candidate(1)])
        with self.assertRaisesRegex(ValueError, 'IDENTITY'): complete_small_group([candidate(0)], [dict(candidate(0), uid='new')])


class CausalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.api = prep.old.legacy_runtime()[0]

    def test_all_legal_endpoints_and_current_flags(self):
        rr = [packet(1, 10**9, flags=2), packet(2, 2*10**9, flags=24)]
        ee, meta = walk_capture(rr, spec(), ['aa', 'cc'], self.api, 200.)
        self.assertEqual(len(ee), 2)
        self.assertEqual(ee[0]['q14'][2], 1.)
        self.assertEqual(ee[1]['q14'][5], 1.)
        self.assertEqual(meta['packets'], 2)

    def test_captures_never_share_context_or_session(self):
        a, _ = walk_capture([packet(1, 10**9)], spec('a', count=1, end=1.), ['aa'], self.api, 300.)
        b, _ = walk_capture([packet(1, 200*10**9)], spec('b', 'b'*64, count=1, start=200., end=200.), ['aa'], self.api, 300.)
        self.assertEqual(b[0]['descriptor']['packets'], 1)
        self.assertEqual(a[0]['row']['component_id'], b[0]['row']['component_id'])
        self.assertNotEqual(a[0]['row']['session_id'], b[0]['row']['session_id'])
        self.assertNotEqual(a[0]['uid'], b[0]['uid'])

    def test_missing_packet_and_missing_namespace_fail_closed(self):
        with self.assertRaisesRegex(ValueError, 'NONCONTIGUOUS'):
            walk_capture([packet(2, 10**9)], spec(), ['aa'], self.api, 200.)
        row = packet(1, 10**9); row['tcp.srcport'] = ''
        with self.assertRaisesRegex(RuntimeError, 'MISSING_NAMESPACE'):
            walk_capture([row], spec(count=1, end=1.), ['aa'], self.api, 200.)

    def test_truncation_recorded_not_silently_selected(self):
        row = packet(2, 2*10**9); row['frame.cap_len'] = '1'
        ee, receipt = walk_capture([packet(1, 10**9), row], spec(), ['aa'], self.api, 200.)
        self.assertEqual(len(ee), 1)
        self.assertEqual(receipt['rejected'][0]['reason'], 'PAYLOAD_TRUNCATED_QUERY')


class AdoptionTests(unittest.TestCase):
    def improved(self):
        prior = pool_fixture(); now = copy.deepcopy(prior)
        r = now['CIC_DEV']['views']['post_window_primary']['reports']['ensemble']
        r['corrected']['normal'].update(positive=6, weighted_rate=.06)
        r['groups']['device'][0]['corrected']['normal'].update(positive=6, weighted_rate=.06)
        return now, prior

    def test_safe_partial_gain_adopts_without_claiming_two_percent(self):
        gate = c3_gate(*self.improved())
        self.assertEqual(gate['status'], 'PASS_C3_IMPROVEMENT')
        self.assertFalse(gate['heim_target_met'])

    def test_no_gain_falls_back(self):
        prior = pool_fixture(); self.assertEqual(c3_gate(prior, prior)['frozen_method'], 'C2_QUERY_SYN_NO_ACK_KEEP_RAW')

    def test_full_view_single_head_attack_failure_rejects(self):
        now, prior = self.improved()
        now['CIC_DEV']['views']['full']['reports']['127']['protection']['status'] = 'FAIL'
        self.assertEqual(c3_gate(now, prior)['status'], 'REJECT_C3_KEEP_C2')

    def test_device_normal_regression_cannot_hide_in_pool(self):
        now, prior = self.improved()
        now['UNSW_DEV']['views']['full']['reports']['227']['groups']['device'][0]['corrected']['normal']['positive'] = 9
        self.assertEqual(c3_gate(now, prior)['status'], 'REJECT_C3_KEEP_C2')

    def test_changed_denominator_or_weights_is_error(self):
        now, prior = self.improved(); now['CIC_DEV']['views']['full']['weights_sha256'] = 'different'
        with self.assertRaisesRegex(ValueError, 'WEIGHT_CHANGED'): c3_gate(now, prior)

    def test_guard_and_strict_cut_under_new_support(self):
        from hnr import evaluation as ev
        import constrained_onboarding_core_v3 as core
        raw = np.zeros((3, 3)); support = np.ones(3); guard = np.array([True, False, False])
        support[guard] = 0.
        changed = core.apply_correction(raw, support, {'scales': [4., 4., 4.]}, .25)
        verdict = ev.decisions(changed, {'cuts': {'cuts': [-1., -1., -1.], 'ensemble_cut': -1.}})
        self.assertTrue(verdict[0].all()); self.assertFalse(verdict[1:].any())
        self.assertTrue(np.array_equal(changed[guard], raw[guard]))


if __name__ == '__main__': unittest.main()
