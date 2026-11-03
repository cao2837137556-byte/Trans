"""Synthetic capture/header tests; no models or real capture traversal."""
from collections import Counter
import io
import ipaddress
import struct
import unittest

from decoder_guard import audit_packet, diagnostic_signature, parse_stderr


def warning(frame=7):
    return (' ** (tshark:1290527) 20:17:21.188112 [Epan WARNING] -- '
            'Dissector bug, protocol MPEG SECT, in packet ' + str(frame) +
            ': /share/software/build/wireshark-4.6.6/epan/packet.c:984: '
            'failed assertion "saved_layers_len < prefs.gui_max_tree_depth"')


def block(kind, body, endian='<'):
    size = len(body) + 12
    return struct.pack(endian + 'II', kind, size) + body + struct.pack(endian + 'I', size)


def fixture(*, ipv6=False, tcp=False, endian='<', fragment=0x4000,
            protocol_override=None, truncate=0):
    macs = bytes.fromhex('00112233445566778899aabb')
    protocol = 6 if tcp else 17
    data = b'test'
    if tcp:
        transport = struct.pack('!HHIIBBHHH', 12345, 443, 123456, 987654,
                                0x51, 0x12, 8192, 0, 12) + data
    else:
        transport = struct.pack('!HHHH', 12345, 50920, 8 + len(data), 0) + data
    protocol = protocol if protocol_override is None else protocol_override
    if ipv6:
        src, dst = '2001:db8::1', '2001:db8::2'
        header = struct.pack('!IHBB16s16s', (6 << 28) | (0xab << 20) | 123,
                             len(transport), protocol, 63,
                             ipaddress.ip_address(src).packed,
                             ipaddress.ip_address(dst).packed)
        packet = macs + struct.pack('!H', 0x86dd) + header + transport
        row = {'ip.src': '', 'ip.dst': '', 'ip.proto': '',
               'ipv6.src': src, 'ipv6.dst': dst, 'ipv6.tclass': '0xab',
               'ipv6.plen': str(len(transport)), 'ipv6.nxt': str(protocol),
               'ipv6.hlim': '63'}
    else:
        header = struct.pack('!BBHHHBBH4s4s', 0x45, 0x2e,
                             20 + len(transport), 0x1234, fragment, 64,
                             protocol, 0, b'\xc0\x00\x02\x01', b'\xc0\x00\x02\x02')
        packet = macs + struct.pack('!H', 0x0800) + header + transport
        row = {'ip.src': '192.0.2.1', 'ip.dst': '192.0.2.2',
               'ip.version': '4', 'ip.proto': str(protocol), 'ip.hdr_len': '20',
               'ip.dsfield': '0x2e', 'ip.len': str(20 + len(transport)),
               'ip.id': '0x1234', 'ip.flags': hex(fragment >> 13),
               'ip.frag_offset': str(fragment & 0x1fff),
               'ip.flags.mf': str(int(bool(fragment & 0x2000))), 'ip.ttl': '64'}
    if tcp:
        row.update({'tcp.srcport': '12345', 'tcp.dstport': '443',
                    'tcp.seq_raw': '123456', 'tcp.ack_raw': '987654',
                    'tcp.flags': '0x0112', 'tcp.window_size_value': '8192',
                    'tcp.urgent_pointer': '12', 'tcp.hdr_len': '20', 'tcp.len': '4',
                    'tcp.flags.syn': '1', 'tcp.flags.ack': '1',
                    'tcp.flags.reset': '0', 'tcp.flags.fin': '0',
                    'udp.srcport': '', 'udp.dstport': ''})
    else:
        row.update({'udp.srcport': '12345', 'udp.dstport': '50920',
                    'udp.length': '12', 'tcp.srcport': '', 'tcp.dstport': ''})
    wire = len(packet)
    if truncate:
        packet = packet[:-truncate]
    row.update({'frame.number': '7', 'frame.time_epoch': '12.345678',
                'frame.len': str(wire), 'frame.cap_len': str(len(packet)),
                'frame.encap_type': '1', 'eth.dst': '00:11:22:33:44:55',
                'eth.src': '66:77:88:99:aa:bb'})
    section = block(0x0a0d0d0a, struct.pack(endian + 'IHHq', 0x1a2b3c4d, 1, 0, -1), endian)
    options = struct.pack(endian + 'HH', 9, 1) + b'\x06\x00\x00\x00' + struct.pack(endian + 'HH', 0, 0)
    interface = block(1, struct.pack(endian + 'HHI', 1, 0, 65535) + options, endian)
    epb = block(6, struct.pack(endian + 'IIIII', 0, 0, 12345678,
                              len(packet), wire) + packet + b'\0' * (-len(packet) % 4), endian)
    index = dict(block_offset=len(section) + len(interface), interface_id=0,
                 timestamp_us=12345678, captured_bytes=len(packet),
                 wire_bytes=wire, original_packet_ordinal=43)
    return row, io.BytesIO(section + interface + epb), index


class DiagnosticParserTests(unittest.TestCase):
    def test_only_exact_records_count_repeated_frames(self):
        text = warning(7) + '\n' + warning(7) + '\r\n\n' + warning(9) + '\n'
        self.assertEqual(parse_stderr(text.encode(), packets=10), Counter({7: 2, 9: 1}))
        self.assertEqual(parse_stderr(b''), Counter())

    def test_other_protocol_path_assertion_or_extra_text_rejected(self):
        for text in (warning().replace('MPEG SECT', 'MPEG'),
                     warning().replace('packet.c:984', 'packet.c:985'),
                     warning().replace('4.6.6', '4.6.5'),
                     warning().replace(' < ', ' <= '),
                     warning() + ' extra', warning() + '\nnew warning',
                     warning().replace('20:17:21', '25:17:21')):
            with self.subTest(text=text):
                with self.assertRaisesRegex(RuntimeError, 'UNAPPROVED_DECODER_STDERR'):
                    parse_stderr(text)

    def test_invalid_text_and_frame_bounds_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'DIAGNOSTIC_INVALID_UTF8'):
            parse_stderr(b'\xff')
        with self.assertRaisesRegex(RuntimeError, 'DIAGNOSTIC_FRAME_RANGE'):
            parse_stderr(warning(11), packets=10)
        for value in (0, -1, True, 1.5):
            with self.subTest(value=value):
                with self.assertRaisesRegex(RuntimeError, 'DIAGNOSTIC_PACKET_BOUND'):
                    parse_stderr(warning(), packets=value)
        with self.assertRaisesRegex(RuntimeError, 'UNAPPROVED_DECODER_STDERR'):
            parse_stderr(warning(0))

    def test_pes_is_limited_to_observed_frame_and_protocol_signature_preserved(self):
        pes = warning(4058042).replace('MPEG SECT', 'MPEG PES')
        sect = warning(4058042)
        self.assertEqual(parse_stderr(pes + '\n' + sect), Counter({4058042: 2}))
        self.assertEqual(diagnostic_signature(pes + '\n' + sect),
                         Counter({('MPEG PES', 4058042): 1, ('MPEG SECT', 4058042): 1}))
        self.assertNotEqual(diagnostic_signature(pes), diagnostic_signature(sect))
        with self.assertRaisesRegex(RuntimeError, 'UNAPPROVED_DECODER_STDERR:PES_FRAME'):
            diagnostic_signature(warning(4058043).replace('MPEG SECT', 'MPEG PES'))


class RawHeaderAuditTests(unittest.TestCase):
    def test_ipv4_udp_exact_fields_and_source_identity(self):
        row, raw, index = fixture()
        result = audit_packet(row, raw, index)
        self.assertEqual(result['status'], 'RAW_HEADER_AUDIT_PASS')
        self.assertEqual((result['frame'], result['original_packet_ordinal']), (7, 43))
        self.assertEqual((result['ip_version'], result['protocol']), (4, 17))
        self.assertIn('udp.length', result['checked_fields'])
        self.assertFalse(raw.closed)

    def test_tcp_all_nine_flags_and_token_headers(self):
        row, raw, index = fixture(tcp=True)
        result = audit_packet(row, raw, index)
        self.assertEqual(result['protocol'], 6)
        self.assertIn('tcp.flags', result['checked_fields'])
        self.assertIn('tcp.seq_raw', result['checked_fields'])

    def test_ipv6_direct_udp_and_big_endian_pcapng(self):
        for ipv6, endian in ((True, '<'), (False, '>'), (True, '>')):
            with self.subTest(ipv6=ipv6, endian=endian):
                row, raw, index = fixture(ipv6=ipv6, endian=endian)
                result = audit_packet(row, raw, index)
                self.assertEqual(result['ip_version'], 6 if ipv6 else 4)

    def test_all_header_mismatches_are_fatal(self):
        for field in ('eth.src', 'ip.src', 'ip.proto', 'ip.len', 'ip.flags',
                      'ip.ttl', 'udp.length', 'udp.srcport', 'frame.len',
                      'frame.cap_len', 'frame.time_epoch'):
            with self.subTest(field=field):
                row, raw, index = fixture()
                row[field] = {'eth.src': '00:00:00:00:00:00',
                              'ip.src': '192.0.2.3', 'frame.time_epoch': '12.345679'}.get(field, '999')
                with self.assertRaises(RuntimeError):
                    audit_packet(row, raw, index)

    def test_missing_required_tcp_header_is_fatal(self):
        row, raw, index = fixture(tcp=True)
        del row['tcp.window_size_value']
        with self.assertRaisesRegex(RuntimeError, 'AUDIT_MISSING_FIELD:tcp.window_size_value'):
            audit_packet(row, raw, index)

    def test_index_lengths_timestamp_and_trailer_are_checked(self):
        for field in ('captured_bytes', 'wire_bytes', 'timestamp_us', 'interface_id'):
            with self.subTest(field=field):
                row, raw, index = fixture()
                index[field] += 1
                with self.assertRaises(RuntimeError):
                    audit_packet(row, raw, index)
        row, raw, index = fixture()
        corrupt = bytearray(raw.getvalue())
        corrupt[-1] ^= 1
        with self.assertRaisesRegex(RuntimeError, 'AUDIT_PCAPNG_BLOCK_TRAILER'):
            audit_packet(row, io.BytesIO(corrupt), index)

    def test_fragment_extension_and_truncated_transport_fail_closed(self):
        row, raw, index = fixture(fragment=0x2000)
        with self.assertRaisesRegex(RuntimeError, 'AUDIT_FRAGMENT_REASSEMBLY_UNSUPPORTED'):
            audit_packet(row, raw, index)
        row, raw, index = fixture(ipv6=True, protocol_override=0)
        with self.assertRaisesRegex(RuntimeError, 'AUDIT_UNSUPPORTED_TRANSPORT_OR_EXTENSION'):
            audit_packet(row, raw, index)
        row, raw, index = fixture(truncate=8)
        with self.assertRaisesRegex(RuntimeError, 'AUDIT_TRUNCATED_UDP'):
            audit_packet(row, raw, index)

    def test_nested_transport_cannot_change_legacy_endpoint_ports(self):
        row, raw, index = fixture()
        row['tcp.srcport'] = '80'
        with self.assertRaisesRegex(RuntimeError, 'AUDIT_NESTED_TRANSPORT_AMBIGUITY'):
            audit_packet(row, raw, index)
        row, raw, index = fixture(ipv6=True)
        row['ip.src'] = '192.0.2.1'
        with self.assertRaisesRegex(RuntimeError, 'AUDIT_NESTED_IP_AMBIGUITY'):
            audit_packet(row, raw, index)


if __name__ == '__main__':
    unittest.main()
