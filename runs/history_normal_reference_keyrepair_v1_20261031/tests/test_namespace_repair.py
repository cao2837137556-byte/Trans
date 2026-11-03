"""Generated namespace failures: causal isolation, recovery, and exact replay."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hnr.common import digest
from hnr.contexts import Contexts
from hnr.history import create_census, walk_decoded
from continuous_input_engineering_v1 import Contexts as FrozenContexts
import legacy_reference_sample_prepare_v1 as prep

if __package__:
    from .test_history import packet, index_for, Progress
else:
    from test_history import packet, index_for, Progress


def udp(frame, us, *, port=1234, peer='2.2.2.2'):
    row = packet(frame, us, port=port)
    for name in list(row):
        if name.startswith('tcp.'):
            del row[name]
    row.update({'ip.proto': '17', 'ip.dst': peer,
                'frame.protocols': 'eth:ethertype:ip:udp',
                'udp.srcport': str(port), 'udp.dstport': '80', 'udp.length': '20'})
    return row


def reverse(row):
    row = copy.deepcopy(row)
    for left, right in (('eth.src', 'eth.dst'), ('ip.src', 'ip.dst'),
                        ('tcp.srcport', 'tcp.dstport'), ('udp.srcport', 'udp.dstport')):
        if left in row and right in row:
            row[left], row[right] = row[right], row[left]
    return row


def unknown_ports(row, *, offset=185, more_fragments=False):
    row = copy.deepcopy(row)
    for name in ('tcp.srcport', 'tcp.dstport', 'udp.srcport', 'udp.dstport'):
        if name in row:
            row[name] = ''
    row.update({'frame.protocols': 'eth:ethertype:ip:data', 'frame.len': '193',
                'frame.cap_len': '193', 'ip.frag_offset': str(offset),
                'ip.flags.mf': '1' if more_fragments else '0',
                'ip.flags': '1' if more_fragments else '0'})
    return row


def encoded(snapshot):
    return json.dumps(snapshot, sort_keys=True, separators=(',', ':'),
                      allow_nan=False).encode('ascii')


class NamespaceRepairTests(unittest.TestCase):
    def contexts(self, folder, *, name='repaired', frozen=False, resident=2):
        cls = FrozenContexts if frozen else Contexts
        return cls('generated-namespace-repair', {'aa'}, prep.old.legacy_runtime()[0],
                   storage_path=folder/(name+'.sqlite'), resident_contexts=resident)

    def trace(self, contexts, packets):
        result = []
        for row in packets:
            owner, namespace, event = contexts.append(copy.deepcopy(row))
            snapshot = contexts.states[namespace].snapshot() if contexts.query_allowed else None
            result.append((owner, namespace, vars(event), contexts.query_allowed,
                           contexts.query_reason, None if snapshot is None else encoded(snapshot)))
        return result

    def test_complete_valid_and_known_header_taint_match_frozen_bytes(self):
        packets = [packet(1, 0), packet(2, 0, port=4321),
                   reverse(packet(3, 200000)), udp(4, 300000),
                   udp(5, 400000, peer='3.3.3.3'), packet(6, 500000),
                   packet(7, 1000000), packet(8, 62000001)]
        packets[5]['tcp.window_size_value'] = ''
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            repaired = self.contexts(folder, resident=1)
            frozen = self.contexts(folder, name='frozen', frozen=True, resident=1)
            try:
                self.assertEqual(self.trace(repaired, packets), self.trace(frozen, packets))
                self.assertEqual(dict(repaired.reasons), dict(frozen.reasons))
                self.assertEqual(repaired.last_seen, frozen.last_seen)
                self.assertEqual(repaired.tainted, frozen.tainted)
            finally:
                repaired.close(); frozen.close()

    def test_unknown_ports_block_new_keys_and_reverse_but_isolate_pair_and_protocol(self):
        other = packet(5, 4000000); other['ip.dst'] = '3.3.3.3'
        packets = [packet(1, 0), unknown_ports(packet(2, 1000000)),
                   packet(3, 2000000, port=4321), reverse(packet(4, 3000000)),
                   other, udp(6, 5000000)]
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            repaired = self.contexts(folder, resident=1)
            try:
                trace = self.trace(repaired, packets)
                self.assertEqual([item[3] for item in trace], [True, False, False, False, True, True])
                self.assertIsNone(trace[1][1])
                self.assertNotIn(0, [endpoint[1] for ns in repaired.last_seen for endpoint in ns[2][1:]])
                # Replay the unaffected frames against the frozen implementation,
                # with owner-outside placeholders retaining every frame position.
                controls = copy.deepcopy(packets)
                for i in (0, 1, 2, 3):
                    controls[i]['eth.src'] = 'outside'; controls[i]['eth.dst'] = 'outside'
                frozen = self.contexts(folder, name='isolated-frozen', frozen=True, resident=1)
                try:
                    reference = self.trace(frozen, controls)
                finally:
                    frozen.close()
                self.assertEqual(trace[4][5], reference[4][5])
                self.assertEqual(trace[5][5], reference[5][5])
            finally:
                repaired.close()

    def test_ongoing_compatible_rows_extend_taint_exact_sixty_does_not_reset(self):
        packets = [packet(1, 0), unknown_ports(packet(2, 1000000)),
                   packet(3, 60000000, port=4321), reverse(packet(4, 119000000)),
                   packet(5, 179000000, port=4321), packet(6, 239000001),
                   packet(7, 239001000, port=4321)]
        with tempfile.TemporaryDirectory() as directory:
            contexts = self.contexts(Path(directory), resident=1)
            try:
                trace = self.trace(contexts, packets)
                self.assertEqual([item[3] for item in trace], [True, False, False, False, False, True, True])
                for position in (5, 6):
                    provenance = json.loads(trace[position][5])[2]
                    frames = [frame for burst in provenance['bursts'] for frame in burst['frames']]
                    self.assertEqual(frames, [position+1])
                    self.assertEqual(provenance['episode_first_frame'], position+1)
                self.assertEqual(contexts.reasons['MISSING_NAMESPACE_GROUP_IDLE_RESET'], 1)
                self.assertEqual(contexts.frame, len(packets))
            finally:
                contexts.close()

    def test_unknown_fragments_extend_taint_and_never_create_a_zero_port_namespace(self):
        packets = [udp(1, 0),
                   unknown_ports(udp(2, 1000000), offset=0, more_fragments=True),
                   unknown_ports(udp(3, 60000000), offset=185), udp(4, 120000000),
                   udp(5, 180000001)]
        with tempfile.TemporaryDirectory() as directory:
            contexts = self.contexts(Path(directory), resident=1)
            try:
                trace = self.trace(contexts, packets)
                self.assertEqual([item[3] for item in trace], [True, False, False, False, True])
                self.assertIsNone(trace[1][1]); self.assertIsNone(trace[2][1])
                self.assertEqual(len(contexts.last_seen), 1)
                self.assertEqual(contexts.reasons['MISSING_NAMESPACE_HEADERS_TAINT'], 2)
                provenance = json.loads(trace[-1][5])[2]
                self.assertEqual([f for b in provenance['bursts'] for f in b['frames']], [5])
            finally:
                contexts.close()

    def test_partial_missing_ip_is_a_hard_stop(self):
        for field in ('ip.src', 'ip.dst'):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                contexts = self.contexts(Path(directory))
                row = unknown_ports(udp(1, 0)); row[field] = ''
                try:
                    with self.assertRaisesRegex(RuntimeError, 'MISSING_NAMESPACE_IP_HEADERS'):
                        contexts.append(row)
                    self.assertFalse(contexts.query_allowed)
                    self.assertEqual(len(contexts.states), 0)
                finally:
                    contexts.close()

    def test_timestamp_regression_is_fail_closed_even_with_unknown_namespace(self):
        for bad in (udp(2, 1000000), unknown_ports(udp(2, 1000000))):
            with self.subTest(unknown=not bad['udp.srcport']), tempfile.TemporaryDirectory() as directory:
                contexts = self.contexts(Path(directory))
                try:
                    contexts.append(udp(1, 2000000))
                    with self.assertRaisesRegex(RuntimeError, 'NAMESPACE_GROUP_TIMESTAMP_REGRESSION'):
                        contexts.append(bad)
                    self.assertFalse(contexts.query_allowed)
                    group = next(iter(contexts.namespace_groups.values()))
                    self.assertEqual(group['last'], 2000000000)
                finally:
                    contexts.close()

    def test_namespace_idle_reset_cannot_rehabilitate_a_permanently_poisoned_key(self):
        with tempfile.TemporaryDirectory() as directory:
            contexts = self.contexts(Path(directory), resident=1)
            try:
                _, namespace, _ = contexts.append(udp(1, 0))
                # Model a pre-existing frozen poison ledger; repair may reset
                # missing-header state, but must never remove this decision.
                contexts.poisoned.add(namespace)
                contexts.append(unknown_ports(udp(2, 1000000)))
                contexts.append(udp(3, 62000001))
                self.assertFalse(contexts.query_allowed)
                self.assertEqual(contexts.query_reason, 'POISONED_PREFIX')
                self.assertIn(namespace, contexts.poisoned)
                self.assertEqual(contexts.last_seen[namespace], 0)
                self.assertEqual(contexts.reasons['MISSING_NAMESPACE_GROUP_IDLE_RESET'], 1)
                contexts.append(udp(4, 63000001))
                self.assertEqual(contexts.query_reason, 'POISONED_PREFIX')
            finally:
                contexts.close()

    def test_census_and_selected_replay_match_across_spill_capacities(self):
        times = [0, 1000000, 2000000, 3000000, 4000000, 5000000, 65000001, 66000000]
        packets = [packet(1, times[0]), unknown_ports(packet(2, times[1])),
                   packet(3, times[2]), udp(4, times[3]), packet(5, times[4], port=4321),
                   packet(6, times[5]), packet(7, times[6], port=4321), packet(8, times[7])]
        packets[2]['ip.dst'] = packets[5]['ip.dst'] = '3.3.3.3'
        spec = dict(capture_id='generated-namespace-repair', partition='EXTERNAL_ARCHIVAL_EVALUATION',
                    device='generated', display_name='generated', owner='aa',
                    raw=dict(sha256='b'*64), normality_evidence='generated')
        binding = dict(bank_end_frame=4, reference_end_us=times[3], packets=len(packets))
        index = index_for(times); order = np.arange(len(times), dtype=np.uint32)
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            db = create_census(folder/'census.sqlite')
            contexts = self.contexts(folder, name='census-context', resident=1)
            try:
                census = walk_decoded(copy.deepcopy(packets), spec, binding, index, order,
                                      'a'*64, contexts, Progress(), census=db)
            finally:
                contexts.close()
            selected = {uid: json.loads(body) for uid, body in db.execute('SELECT uid,body FROM candidates')}
            self.assertEqual([r[0] for r in db.execute('SELECT frame FROM candidates ORDER BY frame')],
                             [1, 3, 4, 6, 7, 8])
            db.close()
            replays = []
            for resident in (1, 2):
                contexts = self.contexts(folder, name='replay-%d'%resident, resident=resident)
                snapshots = []
                try:
                    result = walk_decoded(copy.deepcopy(packets), spec, binding, index, order,
                                          'a'*64, contexts, Progress(), selected=selected, snapshots=snapshots)
                finally:
                    contexts.close()
                self.assertEqual(result['frontend_reasons'], census['frontend_reasons'])
                self.assertEqual(result['legal_endpoints'], census['legal_endpoints'])
                self.assertEqual(result['selected_snapshots'], len(selected))
                replays.append(digest(snapshots))
            self.assertEqual(replays[0], replays[1])


if __name__ == '__main__':
    unittest.main()
