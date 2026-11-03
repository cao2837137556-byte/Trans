"""Synthetic checks for scientific accounting and bounded input interpretation."""
import json
import tempfile
import unittest
from pathlib import Path

import dpkt

import legacy_cic2022_two_camera_semantic_probe_v1 as probe


class SemanticProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = probe.legacy_runtime()

    def test_literal_legacy_protocol_gate(self):
        api = self.runtime[0]
        base = {'ip.src': '10.0.0.1', 'ip.dst': '10.0.0.2', 'frame.time_epoch': '1', 'tcp.srcport': '1234', 'tcp.dstport': '554'}
        self.assertIsNotNone(probe.old_key(api.event_from_tshark(dict(base, **{'ip.proto': '6'}))))
        self.assertIsNone(probe.old_key(api.event_from_tshark(dict(base, **{'ip.proto': '1'}))))
        # Audit actual old behavior: ipv6.nxt must not silently become ip.proto.
        self.assertIsNone(probe.old_key(api.event_from_tshark({'ipv6.src': '::1', 'ipv6.dst': '::2', 'ipv6.nxt': '6', 'frame.time_epoch': '1'})))

    def test_one_packet_prefix_and_regression(self):
        api = self.runtime[1]
        state = api.BoundedNetfoundPrefix()
        state.append({'frame.number': '1', 'ip.src': '10.0.0.1'}, 2.)
        self.assertEqual(sum(len(b) for bs in state.bursts.values() for b in bs), 1)
        with self.assertRaises(api.SessionTimestampRegression):
            state.append({'frame.number': '2', 'ip.src': '10.0.0.1'}, 1.)

    def test_credentials_and_resource_not_emitted(self):
        payload = b'DESCRIBE rtsp://test/private RTSP/1.0\r\nAuthorization: Basic YWJj\r\n\r\n'
        markers = probe.rtsp_markers({'tcp.payload': payload.hex(), 'rtsp.url': 'rtsp://test/private', 'rtsp.method': 'DESCRIBE'})
        self.assertEqual(markers['authorization_line_count'], 1)
        self.assertNotIn('YWJj', repr(markers))
        self.assertNotIn('private', repr(markers))

    def test_real_dissector_synthetic_pcap_accounting(self):
        tshark = Path('C:/Program Files/Wireshark/tshark.exe')
        with tempfile.TemporaryDirectory(prefix='cic_probe_synthetic_') as temporary:
            root = Path(temporary)
            capture = root / 'fixture.pcap'
            mac1, mac2 = bytes.fromhex('000000000001'), bytes.fromhex('000000000002')
            ip1, ip2 = bytes([10, 0, 0, 1]), bytes([10, 0, 0, 2])
            request = b'DESCRIBE rtsp://10.0.0.2/live RTSP/1.0\r\nCSeq: 1\r\nAuthorization: Basic YWJj\r\n\r\n'
            response = b'RTSP/1.0 401 Unauthorized\r\nCSeq: 1\r\nContent-Length: 0\r\n\r\n'
            packets = [(False, dpkt.tcp.TH_SYN, 100, 0, b''), (True, dpkt.tcp.TH_SYN | dpkt.tcp.TH_ACK, 500, 101, b''), (False, dpkt.tcp.TH_ACK, 101, 501, b''), (False, dpkt.tcp.TH_ACK | dpkt.tcp.TH_PUSH, 101, 501, request), (True, dpkt.tcp.TH_ACK | dpkt.tcp.TH_PUSH, 501, 101 + len(request), response)]
            with capture.open('wb') as f:
                writer = dpkt.pcap.Writer(f)
                for index, (reverse, flags, seq, ack, payload) in enumerate(packets):
                    tcp = dpkt.tcp.TCP(sport=554 if reverse else 1234, dport=1234 if reverse else 554, seq=seq, ack=ack, flags=flags, off=5, win=8192, data=payload)
                    ip = dpkt.ip.IP(src=ip2 if reverse else ip1, dst=ip1 if reverse else ip2, p=6, ttl=64, data=tcp)
                    ip.len = len(ip)
                    frame = dpkt.ethernet.Ethernet(src=mac2 if reverse else mac1, dst=mac1 if reverse else mac2, type=dpkt.ethernet.ETH_TYPE_IP, data=ip)
                    writer.writepkt(bytes(frame), ts=1 + index * .01)
            output = root / 'output'
            output.mkdir()
            spec = {'file_id': 1, 'local_path': str(capture), 'member_path': 'synthetic.pcap', 'provenance_kind': 'synthetic', 'member_sha256': probe.sha(capture)}
            result = probe.analyze_file(spec, output, tshark, self.runtime, {})
            self.assertEqual(result['counts']['packets'], 5)
            self.assertEqual(result['counts']['legacy_prefix_eligible_packets'], 5)
            self.assertEqual(result['rtsp_methods_first_occurrence_packet_counts'].get('DESCRIBE'), 1)
            self.assertEqual(result['rtsp_status_first_occurrence_packet_counts'].get('401'), 1)
            self.assertFalse(result['target_labels_assigned'])
            serialized = json.dumps(result)
            self.assertNotIn('YWJj', serialized)
            self.assertNotIn('rtsp://', serialized)


if __name__ == '__main__':
    unittest.main()
