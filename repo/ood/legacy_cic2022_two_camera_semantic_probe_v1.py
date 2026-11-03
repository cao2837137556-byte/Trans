"""Read only the 23 pinned CIC2022 captures; no model, features or label assignment.

Python 3.9. TShark provides packet/RTSP dissection; dpkt independently counts
capture records and exact captured-byte repetitions. Application bytes stay in
memory: only method/status and aggregate authorization/resource counts persist.
"""
from __future__ import annotations

import argparse
import ast
import csv
import gzip
import hashlib
import json
import math
import re
import subprocess
import sys
import tarfile
import time
import types
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import dpkt

ROOT = Path(__file__).resolve().parents[2]
SCOPE = ROOT / 'runs/legacy_cic2022_interactions_acquisition_v1_20260915/proposed_two_camera_semantic_probe_scope.json'
LEGACY_EVENT = ROOT / 'repo/ood/issue27ckbu_unified_tshark_causal_frontend_v1.py'
LEGACY_PREFIX = ROOT / 'repo/ood/issue27ckda_d1_e3_embed_v1.py'
LEGACY_TRANSLATOR = ROOT / 'repo/ood/issue27ckda_d0_resource_pilot_v1.py'
ROSTER = ROOT / 'runs/legacy_cic2022_support_inventory_v1_20260915/support_inventory.json'
EXTRA_FIELDS = (
    'frame.cap_len', 'frame.encap_type', 'frame.protocols', 'eth.src', 'eth.dst',
    'ip.version', 'ip.id', 'ip.frag_offset', 'ip.flags.mf', 'tcp.hdr_len',
    'tcp.len', 'tcp.payload', 'rtsp.method', 'rtsp.status', 'rtsp.url', 'rtsp.cseq',
    'arp.src.hw_mac', 'arp.src.proto_ipv4', 'arp.dst.hw_mac', 'arp.dst.proto_ipv4',
)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=True, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def declarations(path, names):
    """Load only exact pure legacy declarations, excluding drivers and assets."""
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    picked = []
    for node in tree.body:
        name = getattr(node, 'name', None)
        if isinstance(node, ast.Assign):
            name = node.targets[0].id if isinstance(node.targets[0], ast.Name) else None
        if name in names:
            picked.append(node)
    if len(picked) != len(names):
        raise RuntimeError('Missing/duplicate legacy declarations')
    module = types.ModuleType('cic_probe_' + path.stem)
    sys.modules[module.__name__] = module
    module.__dict__.update(math=math, dataclass=dataclass, Any=Any)
    tree = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0)] + picked, type_ignores=[])
    exec(compile(ast.fix_missing_locations(tree), str(path), 'exec'), module.__dict__)
    return module


def legacy_runtime():
    event = declarations(LEGACY_EVENT, {'TSHARK_FIELDS', 'as_float', 'as_int', 'as_bool', 'normalize_port', 'PacketEvent', 'event_from_tshark'})
    prefix = declarations(LEGACY_PREFIX, {'SessionTimestampRegression', 'BoundedNetfoundPrefix'})
    trans = declarations(LEGACY_TRANSLATOR, {'TSHARK_FIELDS'})
    fields = tuple(dict.fromkeys(list(event.TSHARK_FIELDS) + list(trans.TSHARK_FIELDS) + list(EXTRA_FIELDS)))
    return event, prefix, fields


def number(value, default=0):
    try:
        text = str(value).strip()
        return int(text, 16) if text.startswith('0x') else int(text)
    except (ValueError, TypeError):
        return default


def old_key(event):
    if event.ip_version not in (4, 6) or event.ip_proto not in (6, 17) or not math.isfinite(event.timestamp):
        return None
    return (event.ip_proto,) + tuple(sorted(((event.src, event.src_port), (event.dst, event.dst_port))))


def rtsp_markers(row):
    """No credentials or literal URLs leave this function. Hashes stay private."""
    payload = bytes.fromhex(row.get('tcp.payload', '').replace(':', ''))
    auth = re.findall(br'(?:^|\r\n)Authorization:[ \t]*([^\r\n]+)', payload, re.I)
    urls = [row['rtsp.url'].encode('utf-8')] if row.get('rtsp.url') else []
    return {
        'method': row.get('rtsp.method', ''),
        'status': row.get('rtsp.status', ''),
        'authorization_line_count': len(auth),
        '_auth_hashes': {hashlib.sha256(x).hexdigest() for x in auth},
        '_url_hashes': {hashlib.sha256(x).hexdigest() for x in urls},
    }


def extract_selected(scope, output):
    """Only explicitly listed members are materialized under generated filenames."""
    raw = output / 'raw_selected'
    raw.mkdir()
    grouped = defaultdict(list)
    for i, m in enumerate(scope['members'], 1):
        grouped[m['archive_path']].append((i, m))
    results = []
    for archive_name, members in grouped.items():
        archive = (ROOT / archive_name).resolve()
        if not archive.is_relative_to(ROOT):
            raise RuntimeError('Archive outside workspace')
        expected_hashes = {m['archive_sha256'] for _, m in members}
        if len(expected_hashes) != 1 or sha(archive) not in expected_hashes:
            raise RuntimeError('Archive SHA mismatch')
        by_name = {m['member_path']: (i, m) for i, m in members}
        if len(by_name) != len(members):
            raise RuntimeError('Duplicate requested member')
        found = set()
        with tarfile.open(archive, 'r|gz') as tar:
            for member in tar:
                if member.name not in by_name:
                    tar.members.clear()
                    continue
                if member.name in found or not member.isfile():
                    raise RuntimeError('Duplicate/nonregular selected member')
                index, spec = by_name[member.name]
                if member.size != spec['member_bytes']:
                    raise RuntimeError('Selected size mismatch')
                destination = raw / ('%02d.pcap' % index)
                h = hashlib.sha256()
                with tar.extractfile(member) as fin, destination.open('xb') as fout:
                    total = 0
                    for block in iter(lambda: fin.read(1024 * 1024), b''):
                        total += len(block)
                        if total > spec['member_bytes']:
                            raise RuntimeError('Selected member byte overrun')
                        h.update(block)
                        fout.write(block)
                if total != spec['member_bytes']:
                    raise RuntimeError('Selected member incomplete')
                found.add(member.name)
                results.append(dict(spec, file_id=index, local_path=str(destination), member_sha256=h.hexdigest()))
                tar.members.clear()
        if found != set(by_name):
            raise RuntimeError('Selected members missing')
    if sum(r['member_bytes'] for r in results) != scope['total_member_bytes']:
        raise RuntimeError('Selected total byte mismatch')
    return sorted(results, key=lambda r: r['file_id'])


def capture_records(path):
    counts = Counter()
    seen = {}
    times = []
    with path.open('rb') as f:
        magic = f.read(4)
        f.seek(0)
        reader = dpkt.pcapng.Reader(f) if magic == b'\x0a\x0d\x0d\x0a' else dpkt.pcap.Reader(f)
        linktype = reader.datalink()
        for ts, packet in reader:
            counts['records'] += 1
            counts['captured_bytes'] += len(packet)
            now = float(ts)
            key = hashlib.sha256(packet).digest()
            if key in seen:
                counts['exact_captured_bytes_repeat'] += 1
                delta = now - seen[key]
                if 0 <= delta <= .001:
                    counts['exact_repeat_within_1ms'] += 1
                if delta == 0:
                    counts['exact_repeat_same_timestamp'] += 1
            seen[key] = now
            times.append(now)
    return dict(counts, format='pcapng' if magic == b'\x0a\x0d\x0d\x0a' else 'pcap', magic=magic.hex(), linktype=linktype,
                first_timestamp=times[0] if times else None, last_timestamp=times[-1] if times else None)


def analyze_file(spec, output, tshark, runtime, roster_macs):
    event_api, prefix_api, fields = runtime
    path = Path(spec['local_path'])
    independent = capture_records(path)
    counters = Counter()
    protocols, endpoints, mac_ip, arp_ip = Counter(), Counter(), Counter(), Counter()
    rtsp_methods, rtsp_status = Counter(), Counter()
    auth_set, url_set = set(), set()
    sessions, streams = {}, {}
    counts_by_mac = Counter()
    file_id = spec['file_id']
    command = [str(tshark), '-n', '-r', str(path), '-T', 'fields', '-E', 'header=y', '-E', 'separator=/t', '-E', 'quote=d', '-E', 'occurrence=f']
    for field in fields:
        command.extend(['-e', field])
    log = output / ('%02d_tshark.stderr.log' % file_id)
    audit = output / ('%02d_packet_audit.jsonl.gz' % file_id)
    previous = None
    with log.open('w', encoding='utf-8') as err, gzip.open(audit, 'wt', encoding='utf-8') as out:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=err, text=True, encoding='utf-8', errors='strict')
        try:
            reader = csv.DictReader(process.stdout, delimiter='\t', quotechar='"')
            if tuple(reader.fieldnames or ()) != fields:
                raise RuntimeError('TShark schema drift')
            for raw in reader:
                if None in raw:
                    raise RuntimeError('Unexpected TShark column')
                row = {k: '' if v is None or v == 'None' else v for k, v in raw.items()}
                counters['packets'] += 1
                n = number(row['frame.number'])
                if n != counters['packets']:
                    raise RuntimeError('Noncontiguous packet positions')
                event = event_api.event_from_tshark(row)
                now = event.timestamp
                if math.isfinite(now):
                    if previous is not None and now < previous:
                        counters['capture_time_regressions'] += 1
                    previous = now
                else:
                    counters['nonfinite_timestamp'] += 1
                proto = row.get('frame.protocols', '').split(':')[-1]
                protocols[proto] += 1
                cap = number(row['frame.cap_len'])
                truncated = cap < event.frame_len
                counters['captured_bytes'] += cap
                counters['truncated_packets'] += int(truncated)
                counters['ipv4_packets'] += int(event.ip_version == 4)
                counters['ipv6_packets'] += int(event.ip_version == 6)
                src, dst = event.src, event.dst
                smac, dmac = row['eth.src'].lower(), row['eth.dst'].lower()
                for mac, ip in [(smac, src), (dmac, dst)]:
                    if mac and not ip.startswith('missing-'):
                        mac_ip[(mac, ip)] += 1
                for side in ['src', 'dst']:
                    mac, ip = row['arp.' + side + '.hw_mac'].lower(), row['arp.' + side + '.proto_ipv4']
                    if mac and ip:
                        arp_ip[(mac, ip)] += 1
                matches = sorted({mac for mac in (smac, dmac) if mac in roster_macs})
                for mac in matches:
                    counts_by_mac[mac] += 1
                key = old_key(event)
                alive, complete, regressed = False, False, False
                if key is not None:
                    counters['legacy_protocol_time_gate_packets'] += 1
                    st = sessions.setdefault(key, {'prefix': prefix_api.BoundedNetfoundPrefix(), 'poisoned': False, 'packets': 0, 'eligible_packets': 0, 'header_complete_packets': 0, 'first_frame': n, 'last_frame': n, 'directions': Counter(), 'streams': set(), 'regressions': 0})
                    st['packets'] += 1
                    st['last_frame'] = n
                    st['directions'][(src, event.src_port)] += 1
                    if not st['poisoned']:
                        try:
                            # No numeric feature translation: retain only identity/time for prefix validation.
                            st['prefix'].append({k: row[k] for k in ('frame.number', 'frame.time_epoch', 'ip.src', 'ipv6.src')}, now)
                        except prefix_api.SessionTimestampRegression:
                            st['poisoned'] = True
                            st['regressions'] += 1
                            regressed = True
                    alive = not st['poisoned']
                    counters['legacy_prefix_eligible_packets'] += int(alive)
                    counters['legacy_poisoned_prefix_packets'] += int(not alive)
                    counters['session_time_regressions'] += int(regressed)
                    required = ['ip.src','ip.dst','ip.hdr_len','ip.dsfield','ip.len','ip.flags','ip.ttl'] if event.ip_version == 4 else ['ipv6.src','ipv6.dst','ipv6.tclass','ipv6.plen','ipv6.hlim']
                    required += ['tcp.srcport','tcp.dstport','tcp.flags','tcp.window_size_value','tcp.seq_raw','tcp.ack_raw','tcp.urgent_pointer','tcp.hdr_len'] if event.ip_proto == 6 else ['udp.srcport','udp.dstport','udp.length']
                    complete = all(row.get(k, '') != '' for k in required)
                    counters['legacy_gate_headers_complete'] += int(complete)
                    counters['legacy_gate_headers_missing'] += int(not complete)
                    st['eligible_packets'] += int(alive)
                    st['header_complete_packets'] += int(complete)
                    endpoints[(src, event.src_port, dst, event.dst_port, event.ip_proto)] += 1
                stream = ('tcp', row['tcp.stream']) if row['tcp.stream'] else (('udp', row['udp.stream']) if row['udp.stream'] else None)
                markers = rtsp_markers(row)
                method, status = markers['method'], markers['status']
                auth_set.update(markers['_auth_hashes'])
                url_set.update(markers['_url_hashes'])
                counters['segment_authorization_lines'] += markers['authorization_line_count']
                if method:
                    rtsp_methods[method] += 1
                if status:
                    rtsp_status[status] += 1
                if stream is not None:
                    if key is not None:
                        sessions[key]['streams'].add(stream)
                    flow = streams.setdefault(stream, {'stream_id': ':'.join(stream), 'src': src, 'src_port': event.src_port, 'dst': dst, 'dst_port': event.dst_port, 'first_frame': n, 'last_frame': n, 'first_timestamp': now, 'last_timestamp': now, 'first_syn_without_ack': bool(event.tcp_syn and not event.tcp_ack) if stream[0] == 'tcp' else None, 'packets': 0, 'directions': Counter(), 'syn': 0, 'fin': 0, 'rst': 0, 'retransmissions': 0, 'lost_segment_indications': 0, 'truncated': 0, 'rtsp_methods': Counter(), 'rtsp_status': Counter(), 'auth_lines': 0, '_auth': set(), '_url': set(), 'roster_macs': set()})
                    flow['packets'] += 1
                    flow['last_frame'], flow['last_timestamp'] = n, now
                    flow['directions'][(src, event.src_port)] += 1
                    for field, value in [('syn', event.tcp_syn), ('fin', event.tcp_fin), ('rst', event.tcp_rst), ('retransmissions', event.retransmission), ('lost_segment_indications', event.lost_segment), ('truncated', truncated)]:
                        flow[field] += int(value)
                    if method:
                        flow['rtsp_methods'][method] += 1
                    if status:
                        flow['rtsp_status'][status] += 1
                    flow['auth_lines'] += markers['authorization_line_count']
                    flow['_auth'].update(markers['_auth_hashes'])
                    flow['_url'].update(markers['_url_hashes'])
                    flow['roster_macs'].update(matches)
                record = {'frame': n, 'timestamp': now if math.isfinite(now) else None, 'src': src, 'dst': dst, 'src_port': event.src_port, 'dst_port': event.dst_port, 'ip_version': event.ip_version, 'legacy_ip_proto': event.ip_proto, 'eth_src': smac, 'eth_dst': dmac, 'frame_len': event.frame_len, 'captured_len': cap, 'protocols': row['frame.protocols'], 'stream': ':'.join(stream) if stream else None, 'legacy_prefix_eligible': alive, 'headers_complete': complete, 'session_regression_here': regressed, 'tcp_syn': event.tcp_syn, 'tcp_ack': event.tcp_ack, 'tcp_fin': event.tcp_fin, 'tcp_rst': event.tcp_rst, 'tcp_payload_bytes': number(row['tcp.len']), 'rtsp_method': method, 'rtsp_status': status, 'rtsp_cseq': row['rtsp.cseq'], 'authorization_lines_in_segment': markers['authorization_line_count'], 'target_label': None}
                out.write(json.dumps(record, separators=(',', ':'), allow_nan=False) + '\n')
            code = process.wait(timeout=30)
            if code != 0:
                raise RuntimeError('TShark failed; see ' + str(log))
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdout.close()
    if counters['packets'] != independent.get('records', 0) or counters['captured_bytes'] != independent.get('captured_bytes', 0):
        raise RuntimeError('Independent capture record/byte count disagrees with TShark')
    serial_streams = []
    for flow in streams.values():
        flow['directions'] = [{'src': k[0], 'src_port': k[1], 'packets': v} for k, v in sorted(flow['directions'].items())]
        flow['distinct_authorization_values_segment_lower_bound'] = len(flow.pop('_auth'))
        flow['distinct_rtsp_urls_first_occurrence_lower_bound'] = len(flow.pop('_url'))
        flow['roster_macs'] = sorted(flow['roster_macs'])
        flow['target_label'] = None
        serial_streams.append(flow)
    session_rows = []
    for key, st in sessions.items():
        prefix = st.pop('prefix')
        st['retained_prefix_packets_bound'] = sum(len(b) for bs in prefix.bursts.values() for b in bs)
        st['directions'] = [{'src': k[0], 'src_port': k[1], 'packets': v} for k, v in sorted(st['directions'].items())]
        st['streams'] = sorted(':'.join(x) for x in st['streams'])
        session_rows.append(dict(st, protocol=key[0], endpoints=key[1:]))
    result = {'file_id': file_id, 'member_path': spec['member_path'], 'provenance_kind': spec['provenance_kind'], 'member_sha256': spec['member_sha256'], 'independent_capture_check': independent, 'counts': dict(counters), 'protocol_leaf_counts': dict(protocols), 'roster_mac_packet_counts': dict(counts_by_mac), 'eth_mac_ip_observations': [{'mac': mac, 'ip': ip, 'packets': n} for (mac, ip), n in sorted(mac_ip.items())], 'arp_mac_ip_observations': [{'mac': mac, 'ip': ip, 'packets': n} for (mac, ip), n in sorted(arp_ip.items())], 'directed_endpoint_counts': [{'src': k[0], 'src_port': k[1], 'dst': k[2], 'dst_port': k[3], 'protocol': k[4], 'packets': n} for k, n in endpoints.most_common()], 'rtsp_methods_first_occurrence_packet_counts': dict(rtsp_methods), 'rtsp_status_first_occurrence_packet_counts': dict(rtsp_status), 'distinct_authorization_values_segment_lower_bound': len(auth_set), 'distinct_rtsp_urls_first_occurrence_lower_bound': len(url_set), 'transport_streams': serial_streams, 'legacy_canonical_sessions': session_rows, 'packet_audit': audit.name, 'target_labels_assigned': False, 'model_features_generated': False, 'limitations': ['Literal legacy event protocol uses ip.proto; no new ipv6 fallback added.', 'Legacy gate/prefix availability is not model forward success or proof of complete real-world connection.', 'SYN/midstream and record repetition are audit signals, not new eligibility gates.', 'TShark RTSP first occurrence is at most one method/status per packet; auth counts examine complete lines within segments, without credential reconstruction.', 'Application markers and later responses are audit evidence only; not retroactive attack labels or deployed features.']}
    dump(output / ('%02d_summary.json' % file_id), result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--tshark', type=Path, default=Path('C:/Program Files/Wireshark/tshark.exe'))
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if not output.is_relative_to(ROOT):
        raise RuntimeError('Output must be in workspace')
    output.mkdir(parents=True, exist_ok=False)
    start = time.time()
    status = {'status': 'RUNNING', 'authorized_action': 'User confirmed checking the23 pinned captures after explanation of raw material versus usable training samples.', 'completed_files': 0, 'total_files': 23, 'training_runs': 0, 'model_features_generated': False}
    dump(output / 'status.json', status)
    try:
        scope = json.loads(SCOPE.read_text(encoding='utf-8'))
        assessment_path = SCOPE.parent / 'metadata_assessment.json'
        seal = (SCOPE.parent / 'metadata_assessment.json.sha256').read_text(encoding='utf-8').split()[0]
        if sha(assessment_path) != seal:
            raise RuntimeError('Frozen scope parent seal mismatch')
        pin = next(p for p in json.loads(assessment_path.read_text(encoding='utf-8'))['source_pins'] if p['path'].endswith(SCOPE.name))
        if sha(SCOPE) != pin['sha256'] or len(scope['members']) != 23 or scope['total_member_bytes'] != 82607797:
            raise RuntimeError('Scope identity/count drift')
        runtime = legacy_runtime()
        version = subprocess.run([str(args.tshark), '--version'], capture_output=True, text=True, encoding='utf-8', errors='replace', check=True).stdout.splitlines()[0]
        roster = json.loads(ROSTER.read_text(encoding='utf-8'))['device_roster']['devices']
        roster_macs = {r['mac'].lower(): r['name'] for r in roster}
        dump(output / 'execution_manifest.json', {'scope_sha256': sha(SCOPE), 'scope_source': str(SCOPE), 'legacy_sources': [{'path': str(p), 'sha256': sha(p)} for p in [LEGACY_EVENT, LEGACY_PREFIX, LEGACY_TRANSLATOR]], 'script_sha256': sha(Path(__file__)), 'roster_sha256': sha(ROSTER), 'tshark_version': version, 'fields': runtime[2], 'notes': 'No torch, model, tokenizer, feature translation, fitting, data split or target labels. New user authorization supersedes proposed/not-executed scope status; original scope is preserved.'})
        selected = extract_selected(scope, output)
        dump(output / 'selected_members.json', selected)
        summaries = []
        for spec in selected:
            result = analyze_file(spec, output, args.tshark, runtime, roster_macs)
            summaries.append({'file_id': spec['file_id'], 'member_path': spec['member_path'], 'counts': result['counts'], 'roster_mac_packet_counts': result['roster_mac_packet_counts'], 'rtsp_methods': result['rtsp_methods_first_occurrence_packet_counts'], 'rtsp_status': result['rtsp_status_first_occurrence_packet_counts'], 'streams': len(result['transport_streams'])})
            status['completed_files'] += 1
            status['last_completed_member'] = spec['member_path']
            dump(output / 'status.json', status)
            print(json.dumps({'completed': status['completed_files'], 'total': 23, 'file_id': spec['file_id'], 'packets': result['counts']['packets']}, ensure_ascii=True), flush=True)
        dump(output / 'file_index.json', summaries)
        status.update(status='COMPLETE_PACKET_SEMANTIC_AUDIT', elapsed_seconds=round(time.time() - start, 3), scientific_qualification='REQUIRES_EVIDENCE_REVIEW', target_labels_assigned=False)
    except Exception as exc:
        status.update(status='FAILED', error_type=type(exc).__name__, error=str(exc), elapsed_seconds=round(time.time() - start, 3))
        raise
    finally:
        dump(output / 'status.json', status)


if __name__ == '__main__':
    main()
