"""Bounded, read-only raw qualification. No model imports or feature generation.

Only the 277 new members in the pinned design scope are decoded. The other
18 members reuse sealed prior summaries and packet metadata, never raw replays.
Directional flood counts are screening candidates, not assigned attack labels.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
import tarfile
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from pathlib import Path

import dpkt
import legacy_cic2022_two_camera_semantic_probe_v1 as old

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / 'runs/legacy_reference_conditioned_joint_design_v1_20260916'
PRIOR = ROOT / 'runs/legacy_cic2022_two_camera_semantic_probe_v1_20260915/execution'
ROSTER = ROOT / 'runs/legacy_cic2022_support_inventory_v1_20260915/support_inventory.json'


def dump(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def source_hash(path):
    return old.sha(Path(path))


def stream_key(row):
    if row.get('tcp.stream'):
        return 'tcp:' + row['tcp.stream']
    if row.get('udp.stream'):
        return 'udp:' + row['udp.stream']
    return None


def candidate_kind(spec, expected_mac, row, event, valid):
    """Counts evidence categories without promoting directory labels to truth."""
    if not valid:
        return None
    sm, dm = row.get('eth.src', '').lower(), row.get('eth.dst', '').lower()
    if spec['provenance'] == 'normal':
        return 'normal_provenance_candidate' if expected_mac in (sm, dm) else None
    if dm != expected_mac:
        return None
    mode = spec['member_path'].split('/')[-2]
    if mode == 'UDP' and event.ip_proto == 17 and old.number(row.get('udp.length')) > 8:
        return 'flood_inbound_udp_data_screen'
    if mode == 'TCP' and event.ip_proto == 6:
        if old.number(row.get('tcp.len')) > 0:
            return 'flood_inbound_tcp_data_screen'
        if event.tcp_syn and not event.tcp_ack:
            return 'flood_inbound_tcp_syn_screen'
    if mode == 'HTTP' and event.ip_proto == 6 and row.get('http.request.method'):
        return 'flood_inbound_http_request_screen'
    return None


def independent_records(path, normal):
    counts = Counter()
    seen = {}
    previous = None
    minimum, maximum = math.inf, -math.inf
    first, last = None, None
    with path.open('rb') as fin:
        magic = fin.read(4)
        fin.seek(0)
        reader = dpkt.pcapng.Reader(fin) if magic == b'\x0a\x0d\x0d\x0a' else dpkt.pcap.Reader(fin)
        linktype = reader.datalink()
        for timestamp, packet in reader:
            ts = float(timestamp)
            counts['packets'] += 1
            counts['captured_bytes'] += len(packet)
            if first is None:
                first = ts
            last = ts
            minimum, maximum = min(minimum, ts), max(maximum, ts)
            if previous is not None and ts < previous:
                counts['capture_time_regressions'] += 1
            previous = ts
            # Exact-byte repeats are audit evidence, not an automatic deletion.
            key = hashlib.sha256(packet).digest()
            if key in seen:
                counts['byte_repeat_packets'] += 1
                if abs(ts - seen[key][0]) <= .001:
                    counts['byte_repeat_within_1ms'] += 1
                if ts == seen[key][0]:
                    counts['byte_repeat_same_timestamp'] += 1
            else:
                seen[key] = (ts, counts['packets'])
    result = {'counts': dict(counts), 'magic': magic.hex(), 'linktype': linktype,
              'first_timestamp': first, 'last_timestamp': last,
              'min_timestamp': minimum if first is not None else None,
              'max_timestamp': maximum if first is not None else None,
              'exact_unique_captured_bytes': len(seen)}
    # Normal-only fingerprints permit cross-capture duplicate/temporal review.
    fingerprints = [{'sha256': key.hex(), 'first_timestamp': value[0], 'first_frame': value[1]} for key, value in seen.items()] if normal else []
    return result, fingerprints


def analyze(spec, expected_mac, raw_path, output, tshark, runtime):
    event_api, prefix_api, legacy_fields = runtime
    forbidden = {'tcp.payload', 'rtsp.url', 'rtsp.cseq'}
    fields = tuple(dict.fromkeys([x for x in legacy_fields if x not in forbidden] +
                                 ['http.request.method', 'http.response.code', 'frame.interface_id']))
    file_id = spec['file_id']
    independent, fingerprints = independent_records(raw_path, spec['provenance'] == 'normal')
    if fingerprints:
        dump(output / ('%03d_normal_fingerprints.json' % file_id), fingerprints)
    counts, protocols, mac_pairs, mac_ips, ports, interfaces = [Counter() for _ in range(6)]
    flows, prefixes, source_seconds = {}, {}, Counter()
    command = [str(tshark), '-n', '-r', str(raw_path), '-T', 'fields', '-E', 'header=y', '-E', 'separator=/t', '-E', 'quote=d', '-E', 'occurrence=f']
    for field in fields:
        command.extend(['-e', field])
    log = output / ('%03d_tshark.stderr.log' % file_id)
    with log.open('w', encoding='utf-8') as err:
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=err, text=True, encoding='utf-8', errors='strict')
        try:
            reader = csv.DictReader(proc.stdout, delimiter='\t', quotechar='"')
            if tuple(reader.fieldnames or ()) != fields:
                raise RuntimeError('TShark schema mismatch')
            for raw in reader:
                if None in raw:
                    raise RuntimeError('TShark column mismatch')
                row = {k: '' if v is None or v == 'None' else v for k, v in raw.items()}
                counts['packets'] += 1
                frame = old.number(row['frame.number'])
                if frame != counts['packets']:
                    raise RuntimeError('Noncontiguous frame identity')
                event = event_api.event_from_tshark(row)
                ts = event.timestamp
                if not math.isfinite(ts):
                    raise RuntimeError('Nonfinite timestamp')
                caplen = old.number(row['frame.cap_len'])
                counts['captured_bytes'] += caplen
                counts['truncated'] += int(caplen < event.frame_len)
                sm, dm = row['eth.src'].lower(), row['eth.dst'].lower()
                counts['expected_mac_present'] += int(expected_mac in (sm, dm))
                counts['expected_mac_inbound'] += int(dm == expected_mac)
                counts['expected_mac_outbound'] += int(sm == expected_mac)
                mac_pairs[(sm, dm)] += 1
                interfaces[row.get('frame.interface_id', '')] += 1
                if event.ip_version:
                    mac_ips[(sm, event.src)] += 1
                    mac_ips[(dm, event.dst)] += 1
                protocols[(event.ip_version, event.ip_proto, row['frame.protocols'].split(':')[-1])] += 1
                key = old.old_key(event)
                alive, complete, retained = False, False, False
                if key is not None:
                    counts['legacy_gate'] += 1
                    state = prefixes.setdefault(key, {'prefix': prefix_api.BoundedNetfoundPrefix(), 'poisoned': False})
                    prefix = state['prefix']
                    if not state['poisoned']:
                        try:
                            prefix.append({k: row[k] for k in ('frame.number', 'frame.time_epoch', 'ip.src', 'ipv6.src')}, ts)
                            retained = prefix.bursts[event.src == prefix.first_src][-1][-1]['frame.number'] == row['frame.number']
                        except prefix_api.SessionTimestampRegression:
                            state['poisoned'] = True
                            counts['session_regressions'] += 1
                    alive = not state['poisoned']
                    required = ['ip.src','ip.dst','ip.hdr_len','ip.dsfield','ip.len','ip.flags','ip.ttl'] if event.ip_version == 4 else ['ipv6.src','ipv6.dst','ipv6.tclass','ipv6.plen','ipv6.hlim']
                    required += ['tcp.srcport','tcp.dstport','tcp.flags','tcp.window_size_value','tcp.seq_raw','tcp.ack_raw','tcp.urgent_pointer','tcp.hdr_len'] if event.ip_proto == 6 else ['udp.srcport','udp.dstport','udp.length']
                    complete = all(row.get(k, '') != '' for k in required)
                    counts['legacy_prefix_alive'] += int(alive)
                    counts['header_complete'] += int(complete)
                    counts['header_missing'] += int(not complete)
                    counts['legacy_valid'] += int(alive and complete and caplen >= event.frame_len)
                    counts['retained_prefix_changed'] += int(retained)
                    counts['fragment_indications'] += int(old.number(row['ip.frag_offset']) > 0 or row['ip.flags.mf'] == '1')
                valid = alive and complete and caplen >= event.frame_len
                category = candidate_kind(spec, expected_mac, row, event, valid)
                if category:
                    counts[category] += 1
                    counts['candidate_targets'] += 1
                    counts['candidate_retained_prefix_changed'] += int(retained)
                    source_seconds[(event.src, event.dst, event.dst_port, int(ts))] += 1
                if expected_mac in (sm, dm) and key is not None:
                    direction = 'inbound' if dm == expected_mac else 'outbound'
                    ports[(event.ip_proto, event.src_port, event.dst_port, direction)] += 1
                stream = stream_key(row)
                if stream is None or key is None:
                    continue
                flow = flows.setdefault(stream, {'stream': stream, 'canonical_key': list(key), 'first_timestamp': ts, 'last_timestamp': ts,
                    'first_frame': frame, 'last_frame': frame, 'packets': 0, 'valid_targets': 0, 'candidate_targets': 0,
                    'candidate_retained_prefix_changed': 0, 'inbound': 0, 'outbound': 0, 'syn': 0, 'fin': 0, 'rst': 0,
                    'first_syn_without_ack': bool(event.tcp_syn and not event.tcp_ack) if event.ip_proto == 6 else None,
                    'payload_packets': 0, 'http_requests': 0, 'http_responses': 0, 'candidate_kinds': Counter(),
                    'http_methods': Counter(), 'http_status': Counter(), 'peer_macs': Counter(),
                    'protocol': event.ip_proto, 'expected_mac_seen': False, 'candidate_first_time': None, 'candidate_last_time': None})
                flow['packets'] += 1
                flow['valid_targets'] += int(valid)
                flow['last_timestamp'], flow['last_frame'] = ts, frame
                flow['inbound'] += int(dm == expected_mac)
                flow['outbound'] += int(sm == expected_mac)
                flow['expected_mac_seen'] |= expected_mac in (sm, dm)
                if expected_mac in (sm, dm):
                    flow['peer_macs'][sm if dm == expected_mac else dm] += 1
                for name, value in [('syn', event.tcp_syn), ('fin', event.tcp_fin), ('rst', event.tcp_rst)]:
                    flow[name] += int(value)
                flow['payload_packets'] += int(old.number(row['tcp.len']) > 0 or (event.ip_proto == 17 and old.number(row['udp.length']) > 8))
                if row['http.request.method']:
                    flow['http_requests'] += 1
                    flow['http_methods'][row['http.request.method']] += 1
                if row['http.response.code']:
                    flow['http_responses'] += 1
                    flow['http_status'][row['http.response.code']] += 1
                if category:
                    flow['candidate_targets'] += 1
                    flow['candidate_retained_prefix_changed'] += int(retained)
                    flow['candidate_kinds'][category] += 1
                    if flow['candidate_first_time'] is None:
                        flow['candidate_first_time'] = ts
                    flow['candidate_last_time'] = ts
            rc = proc.wait(timeout=30)
            if rc:
                raise RuntimeError('TShark exit %s; %s' % (rc, log))
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
            proc.stdout.close()
    if counts['packets'] != independent['counts'].get('packets', 0) or counts['captured_bytes'] != independent['counts'].get('captured_bytes', 0):
        raise RuntimeError('Independent record/byte tally mismatch')
    if sum(f['candidate_targets'] for f in flows.values()) != counts['candidate_targets']:
        raise RuntimeError('Candidate targets lacking transport stream')
    values = list(flows.values())
    dump(output / ('%03d_flows.json' % file_id), values)
    result = {'file_id': file_id, 'member_path': spec['member_path'], 'member_sha256': spec['member_sha256'],
              'device_label': spec['device_label'], 'expected_mac': expected_mac, 'provenance': spec['provenance'],
              'proposed_device_partition': spec['proposed_device_partition'], 'role_assigned': None, 'labels_assigned': False,
              'independent': independent, 'counts': dict(counts), 'transport_streams': len(flows),
              'candidate_streams': sum(f['candidate_targets'] > 0 for f in values),
              'canonical_sessions': len(prefixes),
              'candidate_canonical_sessions': len({json.dumps(f['canonical_key']) for f in values if f['candidate_targets']}),
              'candidate_stream_cap32': sum(min(32, f['candidate_targets']) for f in values),
              'candidate_per_second_max': max(source_seconds.values(), default=0),
              'candidate_active_seconds': len(source_seconds),
              'protocol_counts': [{'ip_version': k[0], 'ip_proto': k[1], 'leaf': k[2], 'packets': v} for k, v in protocols.most_common()],
              'mac_pairs': [{'src': k[0], 'dst': k[1], 'packets': v} for k, v in mac_pairs.most_common()],
              'mac_ip_observations': [{'mac': k[0], 'ip': k[1], 'packets': v} for k, v in mac_ips.most_common()],
              'ports': [{'protocol': k[0], 'src_port': k[1], 'dst_port': k[2], 'direction': k[3], 'packets': v} for k, v in ports.most_common()],
              'interface_counts': dict(interfaces), 'flows_file': '%03d_flows.json' % file_id,
              'limitations': ['Flood categories are directional semantic screens, not final target labels.',
                  'Transport streams are not independent attack runs.',
                  'Retained-prefix changes exclude flow_duration changes, and are not distinct-embedding counts.',
                  'Legacy prefix gate is reused without IPv6/SYN policy changes; no model forward.']}
    dump(output / ('%03d_summary.json' % file_id), result)
    return {'file_id': file_id, 'member_path': spec['member_path'], 'counts': dict(counts), 'summary': '%03d_summary.json' % file_id}


def extract(scope, output, status):
    selected = [dict(m, file_id=i) for i, m in enumerate(scope['members'], 1) if m['intended_next_action'].startswith('NEW_')]
    grouped = defaultdict(dict)
    for spec in selected:
        grouped[spec['archive_path']][spec['member_path']] = spec
    raw = output / 'raw_selected'
    raw.mkdir()
    for archive_name, requested in grouped.items():
        archive = (ROOT / archive_name).resolve()
        if not archive.is_relative_to(ROOT):
            raise RuntimeError('Archive escapes workspace')
        expected = {m['archive_sha256_from_verified_acquisition'] for m in requested.values()}
        if len(expected) != 1 or source_hash(archive) not in expected:
            raise RuntimeError('Archive SHA mismatch')
        found = set()
        with tarfile.open(archive, 'r|gz') as tf:
            for member in tf:
                if member.name not in requested:
                    tf.members.clear()
                    continue
                spec = requested[member.name]
                if member.name in found or not member.isfile() or member.size != spec['member_bytes']:
                    raise RuntimeError('Selected member identity mismatch')
                path = raw / ('%03d.pcap' % spec['file_id'])
                h, total = hashlib.sha256(), 0
                with tf.extractfile(member) as fin, path.open('xb') as fout:
                    for chunk in iter(lambda: fin.read(1024 * 1024), b''):
                        total += len(chunk)
                        if total > spec['member_bytes']:
                            raise RuntimeError('Selected byte overrun')
                        fout.write(chunk)
                        h.update(chunk)
                if total != spec['member_bytes']:
                    raise RuntimeError('Selected member truncated')
                spec['member_sha256'], spec['local_path'] = h.hexdigest(), str(path)
                found.add(member.name)
                status.update(extracted=len(found) + status.get('previous_archive_extracted', 0), last_extracted=member.name)
                dump(output / 'status.json', status)
                tf.members.clear()
        if found != set(requested):
            raise RuntimeError('Missing selected members')
        status['previous_archive_extracted'] = status['extracted']
    dump(output / 'selected_new_members.json', selected)
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--tshark', type=Path, default=Path('C:/Program Files/Wireshark/tshark.exe'))
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if not output.is_relative_to(ROOT):
        raise RuntimeError('Output outside workspace')
    output.mkdir(parents=True, exist_ok=False)
    started = time.time()
    status = {'status': 'RUNNING', 'stage': 'VERIFY_AND_EXTRACT', 'new_raw_total': 277, 'completed': 0, 'reuse': 18,
              'training': False, 'model_features': False, 'retries': 0, 'started_epoch': started}
    dump(output / 'status.json', status)
    try:
        for line in (DESIGN / 'SHA256SUMS').read_text(encoding='utf-8').splitlines():
            expected, name = line.split('  ', 1)
            if source_hash(DESIGN / name) != expected:
                raise RuntimeError('Design seal mismatch')
        scope = json.loads((DESIGN / 'proposed_material_scope.json').read_text(encoding='utf-8'))
        if len(scope['members']) != 295 or scope['new_decode_count'] != 277:
            raise RuntimeError('Frozen material scope changed')
        normal_meta = json.loads((ROOT / 'runs/legacy_cic2022_interactions_acquisition_v1_20260915/metadata_assessment.json').read_text(encoding='utf-8'))
        roster = json.loads(ROSTER.read_text(encoding='utf-8'))['device_roster']['devices']
        by_row = {x['source_row']: x for x in roster}
        macs = {p['attack_device_label']: by_row[p['roster_candidate_rows'][0]]['mac'].lower() for p in normal_meta['attack_normal_name_correspondence'] if len(p['roster_candidate_rows']) == 1}
        manifest = {'authorization': 'User explicitly authorized next data review and requested sufficient reasonable data quantities; includes the concrete bounded raw qualification previously proposed.',
                    'scope_sha256': source_hash(DESIGN / 'proposed_material_scope.json'), 'script_sha256': source_hash(Path(__file__)),
                    'legacy_source_pins': [{'path': str(p), 'sha256': source_hash(p)} for p in [Path(old.__file__), old.LEGACY_EVENT, old.LEGACY_PREFIX, old.LEGACY_TRANSLATOR]],
                    'roster_sha256': source_hash(ROSTER), 'tshark': subprocess.run([str(args.tshark), '--version'], capture_output=True, text=True, check=True).stdout.splitlines()[0],
                    'parallel_file_workers': 2, 'model_calls': 0, 'new_downloads': 0, 'hpc': False, 'retry_policy': 'STOP_NO_AUTOMATIC_RETRY', 'start_epoch': started}
        dump(output / 'execution_manifest.json', manifest)
        selected = extract(scope, output, status)
        runtime = old.legacy_runtime()
        status.update(stage='RAW_QUALIFICATION')
        dump(output / 'status.json', status)
        results = []
        with ThreadPoolExecutor(max_workers=2) as executor:
            iterator = iter(selected)
            pending = {}
            for _ in range(2):
                spec = next(iterator, None)
                if spec:
                    pending[executor.submit(analyze, spec, macs[spec['device_label']], Path(spec['local_path']), output, args.tshark, runtime)] = spec
            while pending:
                done, _ = wait(pending, return_when=FIRST_COMPLETED)
                for future in done:
                    spec = pending.pop(future)
                    result = future.result()
                    results.append(result)
                    status.update(completed=len(results), last_completed=spec['member_path'], elapsed_seconds=round(time.time()-started, 2))
                    dump(output / 'status.json', status)
                    if len(results) % 10 == 0 or len(results) == 277:
                        print(json.dumps({'completed': len(results), 'total':277, 'elapsed_seconds':status['elapsed_seconds']}, ensure_ascii=True), flush=True)
                    spec = next(iterator, None)
                    if spec:
                        pending[executor.submit(analyze, spec, macs[spec['device_label']], Path(spec['local_path']), output, args.tshark, runtime)] = spec
        dump(output / 'file_index.json', sorted(results, key=lambda x: x['file_id']))
        status.update(status='COMPLETE_RAW_AUDIT_REQUIRES_REVIEW', stage='COMPLETE', elapsed_seconds=round(time.time()-started, 2))
    except Exception as exc:
        status.update(status='FAILED', error_type=type(exc).__name__, error=str(exc), elapsed_seconds=round(time.time()-started, 2))
        raise
    finally:
        dump(output / 'status.json', status)


if __name__ == '__main__':
    main()
