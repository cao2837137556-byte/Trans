"""Narrow MPEG diagnostic exception and independent packet-header audit.

This module neither changes TShark options nor drops packets. Application-layer
diagnostics are accepted only by the exact parser below, with a separate raw
header audit. Unknown capture/header layouts fail closed.
"""
from collections import Counter
from contextlib import nullcontext
from decimal import Decimal, InvalidOperation
import hashlib
import ipaddress
from pathlib import Path
import re
import struct


# Exact diagnostic observed with the pinned 4.6.6 binary. Only process ID,
# wall-clock timestamp and the reported packet number vary between traversals.
_MPEG_LINE = re.compile(
    r' \*\* \(tshark:[1-9][0-9]*\) '
    r'(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]\.[0-9]{6} '
    r'\[Epan WARNING\] -- Dissector bug, protocol (?P<protocol>MPEG (?:SECT|PES)), '
    r'in packet (?P<frame>[1-9][0-9]*): '
    r'/share/software/build/wireshark-4\.6\.6/epan/packet\.c:984: '
    r'failed assertion "saved_layers_len < prefs\.gui_max_tree_depth"')


def diagnostic_signature(data, packets=None):
    """Return Counter((protocol, frame)) for the two observed exact records.

    This parser alone is not acceptance: caller must pin the decoder binary,
    compare both traversal Counters, and independently audit every warned row.
    The MPEG PES template is restricted to its one observed frame, 4058042.
    """
    require(isinstance(data, (str, bytes)), 'DIAGNOSTIC_TEXT_OR_BYTES_REQUIRED')
    if isinstance(data, bytes):
        try:
            data = data.decode('utf-8', errors='strict')
        except UnicodeDecodeError as exc:
            raise RuntimeError('DIAGNOSTIC_INVALID_UTF8') from exc
    require(packets is None or type(packets) is int and packets > 0,
            'DIAGNOSTIC_PACKET_BOUND')
    result = Counter()
    for line in data.splitlines():
        if not line.strip():
            continue
        match = _MPEG_LINE.fullmatch(line)
        require(match is not None, 'UNAPPROVED_DECODER_STDERR')
        frame = int(match['frame'])
        require(packets is None or frame <= packets, 'DIAGNOSTIC_FRAME_RANGE')
        protocol = match['protocol']
        require(protocol != 'MPEG PES' or frame == 4058042,
                'UNAPPROVED_DECODER_STDERR:PES_FRAME')
        result[protocol, frame] += 1
    return result


def parse_stderr(data, *, packets=None):
    """Return the frame Counter; signature comparison must retain protocol too."""
    result = Counter()
    for (protocol, frame), count in diagnostic_signature(data, packets).items():
        result[frame] += count
    return result


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def _number(row, field):
    value = str(row.get(field, '')).strip()
    require(bool(value), 'AUDIT_MISSING_FIELD:' + field)
    try:
        return int(value, 16) if value.lower().startswith('0x') else int(value)
    except ValueError as exc:
        raise RuntimeError('AUDIT_INVALID_INTEGER:' + field) from exc


def _equal_number(row, field, expected, checked):
    require(_number(row, field) == expected, 'AUDIT_FIELD_MISMATCH:' + field)
    checked.append(field)


def _equal_address(row, field, expected, checked):
    try:
        actual = ipaddress.ip_address(str(row.get(field, '')).strip())
    except ValueError as exc:
        raise RuntimeError('AUDIT_INVALID_ADDRESS:' + field) from exc
    require(actual == ipaddress.ip_address(expected), 'AUDIT_FIELD_MISMATCH:' + field)
    checked.append(field)


def _block(stream, endian):
    head = stream.read(8)
    require(len(head) == 8, 'AUDIT_PCAPNG_BLOCK_HEADER')
    kind, size = struct.unpack(endian + 'II', head)
    require(12 <= size <= 16 * 1024**2 and size % 4 == 0,
            'AUDIT_PCAPNG_BLOCK_SIZE')
    body = stream.read(size - 8)
    require(len(body) == size - 8 and
            struct.unpack_from(endian + 'I', body, len(body) - 4)[0] == size,
            'AUDIT_PCAPNG_BLOCK_TRAILER')
    return kind, head + body


def _interface(stream):
    stream.seek(0)
    prefix = stream.read(12)
    require(len(prefix) == 12 and prefix[:4] == b'\x0a\x0d\x0d\x0a',
            'AUDIT_PCAPNG_SECTION')
    require(prefix[8:] in (b'\x4d\x3c\x2b\x1a', b'\x1a\x2b\x3c\x4d'),
            'AUDIT_PCAPNG_BYTE_ORDER')
    endian = '<' if prefix[8:] == b'\x4d\x3c\x2b\x1a' else '>'
    stream.seek(0)
    _, section = _block(stream, endian)
    require(len(section) >= 28, 'AUDIT_PCAPNG_SECTION_SIZE')
    kind, interface = _block(stream, endian)
    require(kind == 1 and len(interface) >= 20, 'AUDIT_PCAPNG_INTERFACE')
    require(struct.unpack_from(endian + 'H', interface, 8)[0] == 1,
            'AUDIT_ETHERNET_ONLY')
    resolution, offset = 6, 0
    position = 16
    while position < len(interface) - 4:
        require(position + 4 <= len(interface) - 4, 'AUDIT_INTERFACE_OPTION')
        code, length = struct.unpack_from(endian + 'HH', interface, position)
        position += 4
        require(position + length <= len(interface) - 4, 'AUDIT_INTERFACE_OPTION')
        value = interface[position:position + length]
        position += (length + 3) // 4 * 4
        if code == 0:
            require(length == 0, 'AUDIT_INTERFACE_OPTION_END')
            break
        if code == 9:
            require(length == 1 and value[0] < 128, 'AUDIT_DECIMAL_TIMESTAMP_ONLY')
            resolution = value[0]
            require(resolution <= 9, 'AUDIT_TIMESTAMP_RESOLUTION')
        elif code == 14:
            require(length == 8, 'AUDIT_TIMESTAMP_OFFSET')
            offset = struct.unpack(endian + 'q', value)[0]
    return endian, resolution, offset, len(section) + len(interface)


def _packet(stream, index_item):
    endian, resolution, offset, minimum_offset = _interface(stream)
    position = int(index_item['block_offset'])
    require(position >= minimum_offset, 'AUDIT_INDEX_BLOCK_OFFSET')
    stream.seek(position)
    kind, block = _block(stream, endian)
    require(kind == 6 and len(block) >= 32, 'AUDIT_INDEX_NOT_EPB')
    interface, hi, lo, captured, wire = struct.unpack_from(endian + 'IIIII', block, 8)
    require(interface == int(index_item['interface_id']) == 0,
            'AUDIT_SINGLE_INTERFACE_ID')
    require(captured == int(index_item['captured_bytes']) and
            wire == int(index_item['wire_bytes']) and captured <= wire and
            28 + ((captured + 3) // 4 * 4) + 4 <= len(block),
            'AUDIT_INDEX_LENGTHS')
    timestamp = Decimal((hi << 32) + lo) * (Decimal(10) ** (6 - resolution))
    timestamp += Decimal(offset) * 1000000
    require(timestamp == int(index_item['timestamp_us']), 'AUDIT_INDEX_TIMESTAMP')
    return block[28:28 + captured], captured, wire, timestamp


def audit_packet(row, raw, index_item):
    """Audit a warned decoder row against its indexed original PCAPNG EPB.

    ``raw`` may be a path or an already-open seekable binary stream. The caller
    supplies the original packet index item corresponding to this logical row.
    Capture/hash and logical-frame/index binding remain the caller's contract.
    """
    opened = nullcontext(raw) if hasattr(raw, 'read') and hasattr(raw, 'seek') else Path(raw).open('rb')
    with opened as stream:
        packet, captured, wire, timestamp = _packet(stream, index_item)
    checked = []
    _equal_number(row, 'frame.cap_len', captured, checked)
    _equal_number(row, 'frame.len', wire, checked)
    _equal_number(row, 'frame.encap_type', 1, checked)
    try:
        value = Decimal(str(row.get('frame.time_epoch', ''))) * 1000000
    except InvalidOperation as exc:
        raise RuntimeError('AUDIT_INVALID_TIMESTAMP') from exc
    require(value.is_finite() and value == timestamp, 'AUDIT_FIELD_MISMATCH:frame.time_epoch')
    checked.append('frame.time_epoch')
    require(len(packet) >= 14, 'AUDIT_TRUNCATED_ETHERNET')
    for field, value in (('eth.dst', packet[:6]), ('eth.src', packet[6:12])):
        expected = ':'.join(format(x, '02x') for x in value)
        require(str(row.get(field, '')).lower() == expected,
                'AUDIT_FIELD_MISMATCH:' + field)
        checked.append(field)
    ethertype = struct.unpack_from('!H', packet, 12)[0]
    network = 14
    vlans = 0
    while ethertype in (0x8100, 0x88a8):
        require(vlans < 2 and len(packet) >= network + 4, 'AUDIT_UNSUPPORTED_VLAN')
        ethertype = struct.unpack_from('!H', packet, network + 2)[0]
        network += 4
        vlans += 1
    require(ethertype in (0x0800, 0x86dd), 'AUDIT_UNSUPPORTED_ETHERTYPE')
    if ethertype == 0x0800:
        require(len(packet) >= network + 20, 'AUDIT_TRUNCATED_IPV4')
        first, tos, length, ident, fragment, ttl, protocol = struct.unpack_from('!BBHHHBB', packet, network)
        ihl = (first & 15) * 4
        require(first >> 4 == 4 and ihl >= 20 and len(packet) >= network + ihl,
                'AUDIT_IPV4_HEADER')
        require(fragment & 0x3fff == 0, 'AUDIT_FRAGMENT_REASSEMBLY_UNSUPPORTED')
        require(length >= ihl, 'AUDIT_IPV4_LENGTH')
        _equal_address(row, 'ip.src', packet[network + 12:network + 16], checked)
        _equal_address(row, 'ip.dst', packet[network + 16:network + 20], checked)
        for field, expected in (('ip.hdr_len', ihl),
                ('ip.dsfield', tos), ('ip.len', length),
                ('ip.flags', fragment >> 13), ('ip.ttl', ttl), ('ip.proto', protocol)):
            _equal_number(row, field, expected, checked)
        transport, payload = network + ihl, length - ihl
        version = 4
    else:
        require(len(packet) >= network + 40, 'AUDIT_TRUNCATED_IPV6')
        bits, payload, protocol, hop = struct.unpack_from('!IHBB', packet, network)
        require(bits >> 28 == 6 and payload > 0, 'AUDIT_IPV6_HEADER')
        require(not row.get('ip.src') and not row.get('ip.dst'), 'AUDIT_NESTED_IP_AMBIGUITY')
        _equal_address(row, 'ipv6.src', packet[network + 8:network + 24], checked)
        _equal_address(row, 'ipv6.dst', packet[network + 24:network + 40], checked)
        for field, expected in (('ipv6.tclass', (bits >> 20) & 255),
                ('ipv6.plen', payload), ('ipv6.nxt', protocol), ('ipv6.hlim', hop)):
            _equal_number(row, field, expected, checked)
        require(not str(row.get('ip.proto', '')).strip(), 'AUDIT_NESTED_IP_PROTOCOL')
        transport, version = network + 40, 6
    require(protocol in (6, 17), 'AUDIT_UNSUPPORTED_TRANSPORT_OR_EXTENSION')
    require(wire >= transport + payload, 'AUDIT_WIRE_IP_LENGTH')
    if protocol == 17:
        require(payload >= 8 and len(packet) >= transport + 8, 'AUDIT_TRUNCATED_UDP')
        source, destination, length = struct.unpack_from('!HHH', packet, transport)
        require(8 <= length <= payload, 'AUDIT_UDP_LENGTH')
        require(not str(row.get('tcp.srcport', '')).strip() and
                not str(row.get('tcp.dstport', '')).strip(), 'AUDIT_NESTED_TRANSPORT_AMBIGUITY')
        for field, expected in (('udp.srcport', source), ('udp.dstport', destination), ('udp.length', length)):
            _equal_number(row, field, expected, checked)
    else:
        require(payload >= 20 and len(packet) >= transport + 20, 'AUDIT_TRUNCATED_TCP')
        source, destination, seq, ack, data_flags, flags, window, checksum, urgent = struct.unpack_from('!HHIIBBHHH', packet, transport)
        header = (data_flags >> 4) * 4
        flags |= (data_flags & 1) << 8
        require(data_flags & 14 == 0 and 20 <= header <= payload and
                len(packet) >= transport + header, 'AUDIT_TCP_HEADER')
        require(not str(row.get('udp.srcport', '')).strip() and
                not str(row.get('udp.dstport', '')).strip(), 'AUDIT_NESTED_TRANSPORT_AMBIGUITY')
        for field, expected in (('tcp.srcport', source), ('tcp.dstport', destination),
                ('tcp.seq_raw', seq), ('tcp.ack_raw', ack), ('tcp.flags', flags),
                ('tcp.window_size_value', window), ('tcp.urgent_pointer', urgent),
                ('tcp.hdr_len', header),
                ('tcp.flags.syn', int(bool(flags & 2))),
                ('tcp.flags.ack', int(bool(flags & 16))),
                ('tcp.flags.reset', int(bool(flags & 4))),
                ('tcp.flags.fin', int(bool(flags & 1)))):
            _equal_number(row, field, expected, checked)
    return dict(status='RAW_HEADER_AUDIT_PASS', frame=_number(row, 'frame.number'),
                original_packet_ordinal=int(index_item['original_packet_ordinal']),
                protocol=protocol, ip_version=version, checked_fields=checked,
                captured_packet_sha256=hashlib.sha256(packet).hexdigest())
