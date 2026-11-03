"""Streaming raw-header qualification only: no network, model, q14, or E3.

Usage: python -B scan_raw.py --input capture.pcap --output AUDIT.json
       python -B scan_raw.py --self-test
Counters with bounded key populations explicitly report overflow/incompleteness.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import heapq
import json
from pathlib import Path
import socket
import struct
import tempfile
import time

import dpkt

NS = 1_000_000_000
HTTP_SOURCES = {'192.168.0.170', '216.58.198.74'}
UDP_SOURCES = {'190.123.219.128', '16.226.184.201', '153.125.214.15', '91.184.12.91'}
TARGETS = {'192.168.0.128', '192.168.0.101'}
MAX_RECORD_BYTES = 16 * 1024 * 1024


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def utc(ns):
    if ns is None:
        return None
    d = datetime.fromtimestamp(ns // NS, timezone.utc)
    return d.strftime('%Y-%m-%dT%H:%M:%S') + f'.{ns % NS:09d}Z'


def read_exact(f, n):
    b = f.read(n)
    if len(b) != n:
        raise ValueError(f'truncated container at offset {f.tell()}: need {n}, got {len(b)}')
    return b


class RawRecords:
    """Classic PCAP and PCAPNG EPB/obsolete PB/SPB, preserving integer clocks."""
    def __init__(self, path):
        self.path = Path(path)
        self.meta = {'timestamp_fraction_invalid': 0, 'subnanosecond_records': 0,
                     'blocks': Counter(), 'interfaces': [], 'packet_blocks_missing_time': 0}

    def __iter__(self):
        with self.path.open('rb') as f:
            magic = read_exact(f, 4)
            choices = {b'\xd4\xc3\xb2\xa1': ('<', 1_000_000), b'\xa1\xb2\xc3\xd4': ('>', 1_000_000),
                       b'\x4d\x3c\xb2\xa1': ('<', NS), b'\xa1\xb2\x3c\x4d': ('>', NS)}
            if magic in choices:
                endian, divisor = choices[magic]
                major, minor, zone, sigfigs, snaplen, network = struct.unpack(endian + 'HHiIII', read_exact(f, 20))
                link = network & 0xffff
                self.meta.update(format='pcap', endian=endian, version=[major, minor], snaplen=snaplen,
                                 linktype=link, network_field=network, timestamp_units_per_second=divisor)
                if (major, minor) != (2, 4):
                    raise ValueError(f'unsupported PCAP version {major}.{minor}')
                while True:
                    h = f.read(16)
                    if not h:
                        break
                    if len(h) != 16:
                        raise ValueError('truncated classic-PCAP record header')
                    sec, fraction, caplen, wirelen = struct.unpack(endian + 'IIII', h)
                    if caplen > MAX_RECORD_BYTES:
                        raise ValueError('record exceeds 16MiB audit bound')
                    if fraction >= divisor:
                        self.meta['timestamp_fraction_invalid'] += 1
                    ns = sec * NS + fraction * (NS // divisor)
                    yield ns, read_exact(f, caplen), caplen, wirelen, link, 0, snaplen
                self.meta['bytes_consumed'] = f.tell()
                return
            if magic != b'\x0a\x0d\x0d\x0a':
                raise ValueError('not classic PCAP or PCAPNG')
            self.meta['format'] = 'pcapng'
            f.seek(0)
            endian = None
            interfaces = []
            section = -1
            while True:
                block_type_raw = f.read(4)
                if not block_type_raw:
                    break
                if len(block_type_raw) != 4:
                    raise ValueError('truncated PCAPNG block type')
                length_raw = read_exact(f, 4)
                if block_type_raw == b'\x0a\x0d\x0d\x0a':
                    bom = read_exact(f, 4)
                    endian = {b'\x4d\x3c\x2b\x1a': '<', b'\x1a\x2b\x3c\x4d': '>'}.get(bom)
                    if endian is None:
                        raise ValueError('invalid PCAPNG byte-order magic')
                    length = struct.unpack(endian + 'I', length_raw)[0]
                    if length < 28 or length % 4 or length > MAX_RECORD_BYTES:
                        raise ValueError('invalid/oversize PCAPNG section block')
                    rest = read_exact(f, length - 12)
                    if struct.unpack(endian + 'I', rest[-4:])[0] != length:
                        raise ValueError('PCAPNG section trailing length mismatch')
                    section += 1
                    interfaces = []
                    self.meta['blocks']['section_header'] += 1
                    continue
                if endian is None:
                    raise ValueError('PCAPNG data precedes section header')
                typ = struct.unpack(endian + 'I', block_type_raw)[0]
                length = struct.unpack(endian + 'I', length_raw)[0]
                if length < 12 or length % 4 or length > MAX_RECORD_BYTES:
                    raise ValueError('invalid/oversize PCAPNG block')
                rest = read_exact(f, length - 8)
                if struct.unpack(endian + 'I', rest[-4:])[0] != length:
                    raise ValueError('PCAPNG trailing block length mismatch')
                body = rest[:-4]
                self.meta['blocks'][str(typ)] += 1
                if typ == 1:
                    if len(body) < 8:
                        raise ValueError('short PCAPNG interface block')
                    link, reserved, snap = struct.unpack(endian + 'HHI', body[:8])
                    item = {'section': section, 'interface_id': len(interfaces), 'linktype': link,
                            'snaplen': snap, 'timestamp_denominator': 1_000_000, 'timestamp_offset_seconds': 0}
                    pos = 8
                    while pos + 4 <= len(body):
                        code, size = struct.unpack(endian + 'HH', body[pos:pos+4]); pos += 4
                        if code == 0:
                            break
                        if pos + size > len(body):
                            raise ValueError('truncated PCAPNG interface option')
                        value = body[pos:pos+size]; pos += (size + 3) & ~3
                        if code == 9 and size == 1:
                            item['timestamp_denominator'] = (2 ** (value[0] & 127)) if value[0] & 128 else (10 ** value[0])
                        if code == 14 and size == 8:
                            item['timestamp_offset_seconds'] = struct.unpack(endian + 'q', value)[0]
                    interfaces.append(item)
                    self.meta['interfaces'].append(item)
                    continue
                if typ not in (2, 3, 6):
                    continue
                if typ == 3:
                    if len(body) < 4 or not interfaces:
                        raise ValueError('invalid PCAPNG simple packet block')
                    wirelen = struct.unpack(endian + 'I', body[:4])[0]
                    interface = interfaces[0]
                    caplen = min(wirelen, interface['snaplen'] or wirelen)
                    offset, ns, ident = 4, None, 0
                    self.meta['packet_blocks_missing_time'] += 1
                else:
                    if len(body) < 20:
                        raise ValueError('short PCAPNG packet block')
                    if typ == 6:
                        ident, hi, lo, caplen, wirelen = struct.unpack(endian + 'IIIII', body[:20])
                    else:
                        ident, drops, hi, lo, caplen, wirelen = struct.unpack(endian + 'HHIIII', body[:20])
                    if ident >= len(interfaces):
                        raise ValueError('PCAPNG packet references missing interface')
                    interface = interfaces[ident]
                    ticks = (hi << 32) | lo
                    num = ticks * NS
                    denominator = interface['timestamp_denominator']
                    ns = num // denominator + interface['timestamp_offset_seconds'] * NS
                    if num % denominator:
                        self.meta['subnanosecond_records'] += 1
                    offset = 20
                if caplen > MAX_RECORD_BYTES or offset + ((caplen + 3) & ~3) > len(body):
                    raise ValueError('truncated/oversize PCAPNG packet payload')
                yield ns, body[offset:offset+caplen], caplen, wirelen, interface['linktype'], f'{section}:{ident}', interface['snaplen']
            self.meta['bytes_consumed'] = f.tell()


class BoundedCounter:
    def __init__(self, limit=100_000):
        self.values = Counter()
        self.limit = limit
        self.overflow_observations = 0

    def add(self, key, n=1):
        if key in self.values or len(self.values) < self.limit:
            self.values[key] += n
        else:
            self.overflow_observations += n

    def result(self, top=40):
        return {'top': [{'key': k, 'count': n} for k, n in self.values.most_common(top)],
                'retained_distinct_keys': len(self.values), 'key_limit': self.limit,
                'overflow_observations': self.overflow_observations,
                'complete': self.overflow_observations == 0,
                'total_observations': sum(self.values.values()) + self.overflow_observations}


def mac(b):
    return ':'.join(f'{v:02x}' for v in b)


def packet_header(buf, linktype):
    smac = dmac = None
    if linktype == 1:
        eth = dpkt.ethernet.Ethernet(buf)
        smac, dmac = mac(eth.src), mac(eth.dst)
        ip = eth.data
    elif linktype == 113:
        ip = dpkt.sll.SLL(buf).data
    elif linktype in (101, 228, 229):
        if not buf:
            return None
        ip = dpkt.ip.IP(buf) if buf[0] >> 4 == 4 else dpkt.ip6.IP6(buf)
    else:
        return {'unsupported_linktype': linktype}
    if isinstance(ip, dpkt.ip.IP):
        src = socket.inet_ntop(socket.AF_INET, ip.src); dst = socket.inet_ntop(socket.AF_INET, ip.dst)
        proto, noninitial = ip.p, bool(ip.off & dpkt.ip.IP_OFFMASK)
    elif isinstance(ip, dpkt.ip6.IP6):
        src = socket.inet_ntop(socket.AF_INET6, ip.src); dst = socket.inet_ntop(socket.AF_INET6, ip.dst)
        proto, noninitial = getattr(ip, 'p', ip.nxt), False
    else:
        return {'non_ip': True, 'src_mac': smac, 'dst_mac': dmac}
    row = {'src': src, 'dst': dst, 'protocol': proto, 'src_mac': smac, 'dst_mac': dmac,
           'sport': None, 'dport': None, 'flags': None, 'payload': b'', 'noninitial_fragment': noninitial}
    if noninitial:
        return row
    transport = ip.data
    if proto == 6 and isinstance(transport, dpkt.tcp.TCP):
        row.update(sport=transport.sport, dport=transport.dport, flags=transport.flags, payload=transport.data)
    elif proto == 17 and isinstance(transport, dpkt.udp.UDP):
        row.update(sport=transport.sport, dport=transport.dport, payload=transport.data)
    return row


def strata(row):
    if row['protocol'] == 17:
        return 'UDP'
    if row['protocol'] != 6 or row['flags'] is None:
        return 'OTHER_OR_UNPARSED'
    f = row['flags']
    if f & 2 and not f & 16:
        return 'TCP_SYN_NO_ACK'
    if f == 16:
        return 'TCP_ACK_ONLY'
    if f == 24:
        return 'TCP_PSH_ACK'
    if f & 16 and not f & 2:
        return 'TCP_OTHER_ACK_NO_SYN'
    return 'TCP_OTHER'


def scan(path):
    path = Path(path).resolve()
    started = time.monotonic()
    before_stat, before_sha = path.stat(), sha(path)
    reader = RawRecords(path)
    counts, flags, protocols, links, interfaces, hours = Counter(), Counter(), Counter(), Counter(), Counter(), Counter()
    ips, ip_mac, flows = BoundedCounter(), BoundedCounter(30_000), BoundedCounter()
    source_destinations = {k: BoundedCounter() for k in ('HTTP', 'UDP')}
    directions = {k: Counter() for k in ('HTTP', 'UDP')}
    direction_strata = {k: Counter() for k in ('HTTP', 'UDP')}
    http_methods = BoundedCounter(1000)
    target_stats = {t: {'counts': Counter(), 'macs': Counter(), 'protocols': Counter(), 'strata': Counter(),
                        'first_ns': None, 'last_ns': None, 'components': {6: BoundedCounter(), 17: BoundedCounter()},
                        'onboarding_components': {6: BoundedCounter(), 17: BoundedCounter()}} for t in sorted(TARGETS)}
    first_ns = min_ns = max_ns = previous_ns = None
    segments, backtrack_examples, largest_gaps = [], [], []
    segment = None
    error = None
    try:
        for frame, (ts, buf, caplen, wirelen, link, iface, snaplen) in enumerate(reader, 1):
            counts['records'] += 1
            counts['captured_bytes'] += caplen
            counts['wire_bytes'] += wirelen
            counts['truncated_records_caplen_lt_wirelen'] += int(caplen < wirelen)
            counts['caplen_gt_wirelen'] += int(caplen > wirelen)
            counts['caplen_gt_snaplen'] += int(bool(snaplen) and caplen > snaplen)
            links[str(link)] += 1; interfaces[str(iface)] += 1
            if ts is None:
                counts['records_without_timestamp'] += 1
            else:
                if first_ns is None:
                    first_ns = ts
                min_ns = ts if min_ns is None else min(min_ns, ts)
                max_ns = ts if max_ns is None else max(max_ns, ts)
                hours[str(ts // (3600 * NS))] += 1
                if ts > first_ns + 7200 * NS:
                    counts['records_after_first_frame_plus_7200s'] += 1
                if previous_ns is not None:
                    delta = ts - previous_ns
                    if delta < 0:
                        counts['timestamp_backtracks'] += 1
                        if len(backtrack_examples) < 20:
                            backtrack_examples.append({'frame': frame, 'previous_ns': previous_ns, 'current_ns': ts, 'delta_ns': delta})
                    if delta > 0:
                        item = (delta, frame, previous_ns, ts)
                        if len(largest_gaps) < 20:
                            heapq.heappush(largest_gaps, item)
                        elif item > largest_gaps[0]:
                            heapq.heapreplace(largest_gaps, item)
                    if delta > 3600 * NS:
                        if segment:
                            segments.append(segment)
                        segment = None
                if segment is None:
                    segment = {'first_frame': frame, 'last_frame': frame, 'min_ns': ts, 'max_ns': ts, 'records': 0}
                segment['last_frame'] = frame; segment['records'] += 1
                segment['min_ns'] = min(segment['min_ns'], ts); segment['max_ns'] = max(segment['max_ns'], ts)
                previous_ns = ts
            try:
                row = packet_header(buf, link)
            except (ValueError, dpkt.Error, struct.error, IndexError) as exc:
                counts['header_parse_errors'] += 1
                continue
            if not row:
                counts['empty_or_unparsed'] += 1
                continue
            if row.get('unsupported_linktype') is not None:
                counts['unsupported_linktype_records'] += 1
                continue
            if row.get('non_ip'):
                counts['non_ip_records'] += 1
                continue
            counts['IP_records'] += 1
            src, dst, proto = row['src'], row['dst'], row['protocol']
            ips.add(('src', src)); ips.add(('dst', dst)); protocols[str(proto)] += 1
            for role, ip, ethmac in [('src', src, row['src_mac']), ('dst', dst, row['dst_mac'])]:
                if ethmac:
                    ip_mac.add((role, ip, ethmac))
            if row['flags'] is not None:
                flags[str(row['flags'])] += 1
            counts['noninitial_fragment_records'] += int(row['noninitial_fragment'])
            flowkey = (src, dst, proto, row['sport'], row['dport'], row['flags'])
            flows.add(flowkey)
            layer = strata(row)
            for group, documented in [('HTTP', HTTP_SOURCES), ('UDP', UDP_SOURCES)]:
                direction = 'from_documented_source' if src in documented else 'to_documented_source' if dst in documented else 'neither_documented_endpoint'
                directions[group][direction] += 1
                direction_strata[group][direction + '|' + layer] += 1
                if direction == 'from_documented_source':
                    source_destinations[group].add((src, dst, proto, row['dport'], row['flags']))
            payload = row['payload']
            if proto == 6 and payload:
                first_word = payload[:16].split(b' ', 1)[0]
                if first_word in (b'GET', b'POST', b'HEAD', b'PUT', b'DELETE', b'OPTIONS', b'CONNECT', b'TRACE', b'PATCH'):
                    counts['HTTP_request_method_packets'] += 1
                    http_methods.add((src, dst, row['dport'], first_word.decode('ascii'), 'from_documented_HTTP_source' if src in HTTP_SOURCES else 'other_source'))
                elif payload.startswith(b'HTTP/'):
                    counts['HTTP_response_start_packets'] += 1
            for target in TARGETS.intersection((src, dst)):
                st = target_stats[target]
                direction = 'outbound' if src == target else 'inbound'
                st['counts']['records'] += 1; st['counts'][direction] += 1
                st['protocols'][str(proto)] += 1; st['strata'][direction + '|' + layer] += 1
                ethmac = row['src_mac'] if src == target else row['dst_mac']
                if ethmac:
                    st['macs'][ethmac] += 1
                if ts is not None:
                    st['first_ns'] = ts if st['first_ns'] is None else min(st['first_ns'], ts)
                    st['last_ns'] = ts if st['last_ns'] is None else max(st['last_ns'], ts)
                    if first_ns is not None and ts > first_ns + 7200 * NS:
                        st['counts']['records_after_capture_first_frame_plus_7200s'] += 1
                if proto in (6, 17) and row['sport'] is not None:
                    key = (proto, *sorted(((src, row['sport']), (dst, row['dport']))))
                    st['components'][proto].add(key)
                    if ts is not None and first_ns is not None and ts <= first_ns + 7200 * NS:
                        st['onboarding_components'][proto].add(key)
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'
    if segment:
        segments.append(segment)
    after_sha, after_stat = sha(path), path.stat()
    for target, st in target_stats.items():
        st['first_utc'], st['last_utc'] = utc(st['first_ns']), utc(st['last_ns'])
        for name in ('components', 'onboarding_components'):
            st[name] = {str(k): v.result(20) for k, v in st[name].items()}
    for s in segments:
        s.update(min_utc=utc(s['min_ns']), max_utc=utc(s['max_ns']), span_seconds=(s['max_ns'] - s['min_ns']) / NS)
    parsed_conservation = sum(counts.get(k, 0) for k in ('IP_records', 'non_ip_records', 'header_parse_errors', 'empty_or_unparsed', 'unsupported_linktype_records'))
    result = {'schema': 'EDGE_RAW_HEADER_QUALIFICATION_SCAN_V1', 'input': str(path),
              'input_bytes': before_stat.st_size, 'input_sha256': before_sha, 'input_sha256_after': after_sha,
              'input_unchanged': before_sha == after_sha and before_stat.st_size == after_stat.st_size and before_stat.st_mtime_ns == after_stat.st_mtime_ns,
              'complete_container': error is None, 'container_error': error, 'container': reader.meta,
              'counts': dict(counts), 'first_record_ns': first_ns, 'min_ns': min_ns, 'max_ns': max_ns,
              'first_record_utc': utc(first_ns), 'min_utc': utc(min_ns), 'max_utc': utc(max_ns),
              'span_seconds': None if min_ns is None else (max_ns - min_ns) / NS,
              'onboarding_cutoff_ns_from_first_record': None if first_ns is None else first_ns + 7200 * NS,
              'segments': segments, 'segment_rule': 'capture-order positive gap >3600s; descriptive, not proof of continuity',
              'largest_capture_order_gaps': [{'delta_ns': a, 'next_frame': b, 'from_ns': c, 'to_ns': d} for a, b, c, d in sorted(largest_gaps, reverse=True)],
              'backtrack_examples': backtrack_examples, 'records_by_UTC_hour_epoch': dict(hours),
              'linktype_counts': dict(links), 'interface_counts': dict(interfaces),
              'IP_protocol_counts': dict(protocols), 'TCP_flags_counts': dict(flags),
              'IP_addresses': ips.result(), 'IP_MAC_observations': ip_mac.result(100), 'flows': flows.result(100),
              'documented_source_directions': {k: dict(v) for k, v in directions.items()},
              'documented_source_direction_strata': {k: dict(v) for k, v in direction_strata.items()},
              'documented_source_destinations': {k: v.result(100) for k, v in source_destinations.items()},
              'HTTP_request_method_observations': http_methods.result(100), 'targets': target_stats,
              'verification': {'record_decode_conservation': parsed_conservation == counts['records'],
                               'IP_protocol_conservation': sum(protocols.values()) == counts['IP_records'],
                               'linktype_count_conservation': sum(links.values()) == counts['records'],
                               'HTTP_direction_count_conservation': sum(directions['HTTP'].values()) == counts['IP_records'],
                               'UDP_direction_count_conservation': sum(directions['UDP'].values()) == counts['IP_records'],
                               'segment_timestamp_record_conservation': sum(x['records'] for x in segments) + counts['records_without_timestamp'] == counts['records']},
              'elapsed_seconds': time.monotonic() - started,
              'interpretation_limits': ['Header observations are not model input encoding or attack truth.',
                'Documented source membership does not itself label every packet as an attack.',
                'Reverse response ACK is separate from direct attack traffic.',
                'IP/L2 MAC observations do not prove persistent physical identity across files.',
                'Component counts are raw canonical header pairs; legal reference admission is not certified.',
                'No global packet-content duplicate audit in this scanner; complete-container counts do not establish deduplication.',
                'No model, E3, q14, support, distance, or performance evaluation was run.']}
    return result


def self_test():
    def eth(src, dst, proto, payload, flags=16):
        if proto == 6:
            transport = dpkt.tcp.TCP(sport=1234, dport=80, flags=flags, data=payload)
            transport.off = 5
        else:
            transport = dpkt.udp.UDP(sport=5555, dport=9999, data=payload)
            transport.ulen = len(transport)
        ip = dpkt.ip.IP(src=socket.inet_aton(src), dst=socket.inet_aton(dst), p=proto, data=transport)
        ip.len = len(ip)
        return bytes(dpkt.ethernet.Ethernet(src=b'\x00\x01\x02\x03\x04\x05', dst=b'\x10\x11\x12\x13\x14\x15', type=0x800, data=ip))
    records = [(1000, eth('192.168.0.170', '192.168.0.128', 6, b'GET / HTTP/1.1\r\n\r\n', 24)),
               (999, eth('192.168.0.128', '192.168.0.170', 6, b'', 16)),
               (9001, eth('190.123.219.128', '192.168.0.128', 17, b'attack'))]
    tests = []
    with tempfile.TemporaryDirectory(prefix='scanner_selftest_', dir=Path(__file__).resolve().parent) as d:
        root = Path(d)
        p = root / 'fixture.pcap'
        with p.open('wb') as f:
            f.write(b'\xd4\xc3\xb2\xa1' + struct.pack('<HHiIII', 2, 4, 0, 0, 65535, 1))
            for sec, b in records:
                f.write(struct.pack('<IIII', sec, 123456, len(b), len(b)) + b)
        r = scan(p)
        assert r['complete_container'] and r['counts']['records'] == 3
        assert r['counts']['timestamp_backtracks'] == 1
        assert r['counts']['records_after_first_frame_plus_7200s'] == 1
        assert r['counts']['HTTP_request_method_packets'] == 1
        assert r['documented_source_direction_strata']['HTTP']['from_documented_source|TCP_PSH_ACK'] == 1
        assert r['documented_source_direction_strata']['HTTP']['to_documented_source|TCP_ACK_ONLY'] == 1
        assert r['documented_source_direction_strata']['UDP']['from_documented_source|UDP'] == 1
        assert all(r['verification'].values()) and r['input_unchanged']
        tests.append('classic_pcap_clock_direction_HTTP_and_conservation')
        for endian in ('<', '>'):
            def block(t, b):
                size = len(b) + 12
                return struct.pack(endian + 'II', t, size) + b + struct.pack(endian + 'I', size)
            p = root / ('fixture_' + ('le' if endian == '<' else 'be') + '.pcapng')
            with p.open('wb') as f:
                f.write(block(0x0a0d0d0a, struct.pack(endian + 'IHHq', 0x1a2b3c4d, 1, 0, -1)))
                f.write(block(1, struct.pack(endian + 'HHI', 1, 0, 65535)))
                for sec, b in records:
                    ticks = sec * 1_000_000 + 123456
                    body = struct.pack(endian + 'IIIII', 0, ticks >> 32, ticks & 0xffffffff, len(b), len(b))
                    f.write(block(6, body + b + b'\0' * ((-len(b)) % 4)))
            rr = scan(p)
            assert rr['complete_container'] and rr['min_ns'] == r['min_ns'] and rr['max_ns'] == r['max_ns']
            assert rr['counts'] == r['counts'] and all(rr['verification'].values())
            tests.append('pcapng_EPΒ_' + endian)
        p = root / 'truncated.pcap'; p.write_bytes((root / 'fixture.pcap').read_bytes()[:-2])
        bad = scan(p)
        assert not bad['complete_container'] and 'truncated' in bad['container_error']
        tests.append('truncated_record_is_reported_not_silently_accepted')
        bc = BoundedCounter(1); bc.add('a'); bc.add('b'); bc.add('a')
        assert bc.result()['overflow_observations'] == 1 and not bc.result()['complete']
        tests.append('bounded_counter_explicit_incompleteness')
    return {'status': 'PASS', 'tests': tests, 'count': len(tests)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test(), ensure_ascii=False))
        return
    if args.input is None or args.output is None:
        parser.error('--input and --output required')
    if args.input.resolve() == args.output.resolve():
        parser.error('output overlaps raw input')
    result = scan(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(args.output), 'records': result['counts'].get('records', 0),
                      'complete_container': result['complete_container'], 'error': result['container_error'],
                      'elapsed_seconds': result['elapsed_seconds']}, ensure_ascii=False))
    if not result['complete_container'] or not result['input_unchanged'] or not all(result['verification'].values()):
        raise SystemExit(2)


if __name__ == '__main__':
    main()
