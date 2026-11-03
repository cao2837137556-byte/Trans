"""Qualify only five named old-ID captures; no feature/model/scoring APIs."""
from __future__ import annotations

import argparse
import ast
import csv
import gzip
import hashlib
import io
import json
import math
import subprocess
import sys
import time
import types
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import dpkt

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'runs/legacy_id_temporal_qualification_v1_20260916'
PT = 'runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/'
SCOPE = 'runs/legacy_id_test_extension_scope_v1_20260915/metadata_audit.json'
PINS = {
    SCOPE: '38629e21099e42eda9a62cfd8c52b548bbeaf9bcdd00b31bd1a27f019113237e',
    PT + 'ckda_d1_fit_select_target_metadata.csv': 'd6fbba24a1997db24597a800cf952f80f739284e5ca13db5ce04497f1540c36d',
    PT + 'ckda_d1_fit_select_embeddings.npz.metadata.csv.gz': '120ed5ccc752c1210a655dbcb972e08b6263bdeb1e08093d76b3e2f9c1b3d8dd',
    'repo/ood/issue27ckbu_unified_tshark_causal_frontend_v1.py': '127efd212932d9330af790f17a069a84b3ee48205d68bed7e2e9f00778bb2820',
    'repo/ood/issue27ckda_d0_resource_pilot_v1.py': 'ec1cb7be1f47e2ef7862905f3e89c75c0295fb1565fa0820d174a6e11409856a',
}


def require(value, reason):
    if not value:
        raise RuntimeError(reason)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(4 * 1024 ** 2), b''):
            h.update(chunk)
    return h.hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def jsonl(path, rows):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'wt', encoding='utf-8', newline='\n') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')


def project(path, names):
    nodes = []
    for node in ast.parse(path.read_text(encoding='utf-8-sig')).body:
        name = getattr(node, 'name', None)
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
        if name in names:
            nodes.append(node)
    require(len(nodes) == len(names), 'PURE_DECLARATIONS')
    mod = types.ModuleType('_id_' + path.stem)
    sys.modules[mod.__name__] = mod
    mod.__dict__.update(math=math, dataclass=dataclass, Any=Any)
    tree = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0)] + nodes, type_ignores=[])
    exec(compile(ast.fix_missing_locations(tree), str(path), 'exec'), mod.__dict__)
    return mod


def runtime():
    event = project(ROOT / 'repo/ood/issue27ckbu_unified_tshark_causal_frontend_v1.py',
                    {'TSHARK_FIELDS', 'as_float', 'as_int', 'as_bool', 'normalize_port', 'PacketEvent', 'event_from_tshark'})
    trans = project(ROOT / 'repo/ood/issue27ckda_d0_resource_pilot_v1.py', {'TSHARK_FIELDS'})
    fields = tuple(dict.fromkeys(list(event.TSHARK_FIELDS) + list(trans.TSHARK_FIELDS) +
                                 ['frame.cap_len', 'frame.protocols', 'tcp.hdr_len']))
    return event, fields


def canonical(event):
    if event.ip_version not in (4, 6) or event.ip_proto not in (6, 17) or not math.isfinite(event.timestamp):
        return None
    return (event.ip_proto,) + tuple(sorted(((event.src, event.src_port), (event.dst, event.dst_port))))


def integer(value):
    f = float(value)
    require(math.isfinite(f) and f.is_integer(), 'NONINTEGER_POSITION')
    return int(f)


def record_inventory(payload):
    f = io.BytesIO(payload)
    reader = dpkt.pcapng.Reader(f) if payload[:4] == b'\x0a\x0d\x0d\x0a' else dpkt.pcap.Reader(f)
    result = []
    for ts, packet in reader:
        result.append({'timestamp': float(ts), 'captured_bytes': len(packet), 'packet_sha256': digest(packet)})
    return result, reader.datalink()


def decode(path, api, fields, tshark, stderr_path):
    command = [str(tshark), '-n', '-r', str(path), '-T', 'fields', '-E', 'header=y',
               '-E', 'separator=/t', '-E', 'quote=d', '-E', 'occurrence=f']
    for name in fields:
        command += ['-e', name]
    result, sessions = [], {}
    with stderr_path.open('wb') as err:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=err, text=True, encoding='utf-8', errors='strict')
        try:
            reader = csv.DictReader(process.stdout, delimiter='\t', quotechar='"')
            require(tuple(reader.fieldnames or []) == fields, 'TSHARK_HEADER')
            for raw in reader:
                row = {k: '' if v is None or v == 'None' else v for k, v in raw.items()}
                event = api.event_from_tshark(row)
                frame = event.frame_number
                require(frame == len(result) + 1 and math.isfinite(event.timestamp), 'PACKET_ORDER_OR_TIME')
                key = canonical(event)
                complete, regressed = False, False
                if key is not None:
                    needed = ['ip.src','ip.dst','ip.hdr_len','ip.dsfield','ip.len','ip.flags','ip.ttl'] if event.ip_version == 4 else ['ipv6.src','ipv6.dst','ipv6.tclass','ipv6.plen','ipv6.hlim']
                    needed += ['tcp.srcport','tcp.dstport','tcp.flags','tcp.window_size_value','tcp.seq_raw','tcp.ack_raw','tcp.urgent_pointer','tcp.hdr_len'] if event.ip_proto == 6 else ['udp.srcport','udp.dstport','udp.length']
                    complete = all(row.get(k, '') != '' for k in needed)
                    state = sessions.setdefault(key, {'last_time': None, 'poisoned': False, 'first_frame': frame})
                    if state['last_time'] is not None and event.timestamp < state['last_time']:
                        state['poisoned'] = True
                    state['last_time'] = event.timestamp
                    regressed = state['poisoned']
                result.append({'frame_number_1based': frame, 'position_zero_based': frame - 1,
                               'timestamp': event.timestamp, 'captured_bytes': integer(row['frame.cap_len']),
                               'frame_bytes': event.frame_len, 'ip_version': event.ip_version,
                               'ip_proto': event.ip_proto, 'old_key': key,
                               'session_key_sha256': None if key is None else digest(repr(key).encode('utf-8')),
                               'stream': ('tcp:' + row['tcp.stream']) if row['tcp.stream'] else (('udp:' + row['udp.stream']) if row['udp.stream'] else None),
                               'tcp_syn': event.tcp_syn, 'tcp_ack': event.tcp_ack,
                               'legacy_header_complete': complete, 'legacy_prefix_regressed': regressed,
                               'legacy_input_eligible': key is not None and complete and not regressed,
                               'session_first_frame': None if key is None else sessions[key]['first_frame']})
            require(process.wait(timeout=60) == 0, 'TSHARK_EXIT')
        except BaseException:
            process.kill()
            process.wait()
            raise
        finally:
            process.stdout.close()
    return result


def map_exposure(rows, cache, packets, member):
    by_time = defaultdict(list)
    for row in packets:
        by_time[row['timestamp']].append(row)
    mapped, exposed_sessions, exposed_frames = [], set(), set()
    for row in rows:
        uid = row['uid']
        c = cache[uid]
        position = integer(c['event_position'])
        declared_position = integer(row['target_event_position_within_capture'])
        require(0 <= position < len(packets) and position == declared_position, 'ACTUAL_POSITION_MISMATCH:' + uid)
        actual = packets[position]
        require(float(c['timestamp_epoch']) == actual['timestamp'], 'CACHED_TIME_RAW_MISMATCH:' + uid)
        key = actual['old_key']
        if key is not None and not actual['legacy_prefix_regressed']:
            expected_session = digest(repr((row['source_group'], member, key)).encode('utf-8'))
            require(c['session_id'] == expected_session, 'CACHED_SESSION_RAW_MISMATCH:' + uid)
        # Feature-available time may reflect a historical auxiliary emitter
        # identity. It is checked independently, never treated as a packet index.
        semantic_time = float(row['feature_available_time_epoch'])
        matches = by_time.get(semantic_time, [])
        require(len(matches) == 1, 'SEMANTIC_TIMESTAMP_NONUNIQUE_OR_ABSENT:' + uid)
        semantic = matches[0]
        for exposure in (actual, semantic):
            exposed_frames.add(exposure['frame_number_1based'])
            if exposure['session_key_sha256'] is not None:
                exposed_sessions.add(exposure['session_key_sha256'])
        mapped.append({'uid': uid, 'role': row['role'], 'plan_scope': row['plan_scope'],
                       'actual_cached_frame_1based': position + 1,
                       'actual_cached_timestamp': actual['timestamp'],
                       'actual_session_key_sha256': actual['session_key_sha256'],
                       'semantic_timestamp_frame_1based': semantic['frame_number_1based'],
                       'semantic_timestamp': semantic_time,
                       'semantic_session_key_sha256': semantic['session_key_sha256'],
                       'same_actual_and_semantic_frame': position + 1 == semantic['frame_number_1based'],
                       'recorded_index_not_used_as_packet_index': row['recorded_index'],
                       'original_missing_or_ineligible': not actual['legacy_input_eligible']})
    require(mapped, 'EMPTY_OLD_EXPOSURE')
    cutoff_frame = max(exposed_frames)
    cutoff_time = max(packets[i - 1]['timestamp'] for i in exposed_frames)
    return mapped, exposed_sessions, cutoff_frame, cutoff_time


def qualify(packets, exposed_sessions, cutoff_frame, cutoff_time):
    candidates, reasons = [], Counter()
    for row in packets:
        if row['frame_number_1based'] <= cutoff_frame or row['timestamp'] <= cutoff_time:
            reasons['not_after_all_source_fit_select'] += 1
        elif not row['legacy_input_eligible']:
            reasons['later_legacy_input_ineligible'] += 1
        elif row['session_key_sha256'] in exposed_sessions:
            reasons['later_session_shared_with_fit_select'] += 1
        elif row['session_first_frame'] <= cutoff_frame:
            # A new target in an unselected but earlier session is held aside;
            # the current proposal is an entirely new session after the cutoff.
            reasons['later_session_began_before_cutoff'] += 1
        else:
            candidates.append(row)
    require(len(candidates) + sum(reasons.values()) == len(packets), 'CANDIDATE_CONSERVATION')
    return candidates, dict(reasons)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-authorized', action='store_true')
    parser.add_argument('--tshark', type=Path, default=Path('C:/Program Files/Wireshark/tshark.exe'))
    args = parser.parse_args()
    require(args.execute_authorized, 'RAW_METADATA_QUALIFICATION_NOT_AUTHORIZED')
    require(not OUT.exists(), 'ONE_SHOT_OUTPUT_ALREADY_EXISTS')
    OUT.mkdir(parents=True)
    start = time.monotonic()
    dump(OUT / 'status.json', {'status': 'RUNNING', 'model_loads': 0, 'feature_generation': 0})
    try:
        for path, expected in PINS.items():
            require(sha(ROOT / path) == expected, 'SOURCE_PIN:' + path)
        scope = json.loads((ROOT / SCOPE).read_text(encoding='utf-8'))
        specs = scope['id_members']
        require(len(specs) == 5 and [s['exposed_target_count'] for s in specs] == [600,600,270,270,269], 'FIVE_MEMBER_SCOPE')
        allowed = {spec['raw_member'] for spec in specs}
        with (ROOT / PT / 'ckda_d1_fit_select_target_metadata.csv').open('r', encoding='utf-8-sig', newline='') as f:
            targets = [r for r in csv.DictReader(f) if r['raw_source_path'] in allowed]
        require(len(targets) == 2009 and len({r['uid'] for r in targets}) == 2009, 'TARGET_DENOMINATOR')
        wanted = {r['uid'] for r in targets}
        with gzip.open(ROOT / PT / 'ckda_d1_fit_select_embeddings.npz.metadata.csv.gz', 'rt', encoding='utf-8-sig', newline='') as f:
            cache = {r['uid']: r for r in csv.DictReader(f) if r['uid'] in wanted}
        require(set(cache) == wanted, 'CACHE_METADATA_UID_COVERAGE')
        api, fields = runtime()
        version = subprocess.run([str(args.tshark), '--version'], capture_output=True, text=True, encoding='utf-8', check=True).stdout.splitlines()[0]
        archive = Path(scope['archive_path'])
        dump(OUT / 'execution_manifest.json', {'authorization': 'User included independent ID in this enhancement and authorized implementation plus necessary qualification',
             'input_pins': PINS, 'script_sha256': sha(Path(__file__)), 'archive_path': str(archive),
             'archive_bytes_stat': archive.stat().st_size, 'archive_full_rehash': False,
             'archive_identity_method': 'Exact pinned member name/size/CRC plus independently computed complete member SHA256; no other raw members opened',
             'tshark_version': version, 'fields': fields, 'model_loads': 0, 'numerical_feature_arrays_opened': 0,
             'E3_forward_calls': 0, 'optimizer_steps': 0, 'candidate_rule': 'After all original source-local fit/select actual+semantic target cutoffs; wholly new canonical session starting after cutoff; literal old eligible headers/time; no score selection'})
        raw_dir = OUT / 'raw_selected'
        raw_dir.mkdir()
        ledgers, all_candidates, all_mappings = [], [], []
        with zipfile.ZipFile(archive) as z:
            require(all(z.namelist().count(name) == 1 for name in allowed), 'ARCHIVE_MEMBER_AMBIGUOUS')
            for i, spec in enumerate(specs, 1):
                name = spec['raw_member']; info = z.getinfo(name)
                require(info.file_size == spec['bytes'] and format(info.CRC, '08x') == spec['crc32_metadata_only'], 'MEMBER_CENTRAL_IDENTITY')
                payload = z.read(name)
                require(len(payload) == spec['bytes'], 'MEMBER_LENGTH')
                member_sha = digest(payload)
                local = raw_dir / ('%02d.pcap' % i)
                local.write_bytes(payload)
                records, linktype = record_inventory(payload)
                packets = decode(local, api, fields, args.tshark, OUT / ('%02d_tshark.stderr.log' % i))
                require(len(records) == len(packets), 'INDEPENDENT_PACKET_COUNT')
                for packet, rec in zip(packets, records):
                    require(packet['timestamp'] == rec['timestamp'] and packet['captured_bytes'] == rec['captured_bytes'], 'INDEPENDENT_PACKET_IDENTITY')
                    packet['packet_sha256'] = rec['packet_sha256']
                old = [r for r in targets if r['raw_source_path'] == name]
                require(len(old) == spec['exposed_target_count'], 'MEMBER_EXPOSURE_COUNT')
                mapped, exposed, cutoff_frame, cutoff_time = map_exposure(old, cache, packets, name)
                selected, reasons = qualify(packets, exposed, cutoff_frame, cutoff_time)
                for row in mapped:
                    row.update(member=name, member_sha256=member_sha)
                all_mappings += mapped
                for row in selected:
                    all_candidates.append({'uid': 'legacy-id-followup:' + digest((member_sha + ':' + str(row['frame_number_1based'])).encode('ascii')),
                        'raw_member': name, 'member_sha256': member_sha, 'local_raw_path': str(local),
                        'frame_number_1based': row['frame_number_1based'], 'position_zero_based': row['position_zero_based'],
                        'timestamp': row['timestamp'], 'session_key_sha256': row['session_key_sha256'],
                        'source_cutoff_frame_1based': cutoff_frame, 'source_cutoff_time': cutoff_time,
                        'session_first_frame': row['session_first_frame'], 'label': 0,
                        'label_evidence': 'Official Gotham raw/benign ID capture provenance, not attack-GT complement',
                        'role': 'PROPOSED_ID_TEMPORAL_CHECK_NOT_SCORED', 'prior_global_development_exposure': 'NOT_FULLY_RESOLVED',
                        'model_features_materialized': False})
                projected = [{k:v for k,v in r.items() if k != 'old_key'} for r in packets]
                jsonl(OUT / ('%02d_packet_metadata.jsonl.gz' % i), projected)
                sessions = defaultdict(list)
                for row in packets:
                    if row['session_key_sha256'] is not None:
                        sessions[row['session_key_sha256']].append(row)
                jsonl(OUT / ('%02d_session_ledger.jsonl' % i), ({'session_key_sha256': key, 'first_frame': rr[0]['frame_number_1based'],
                      'last_frame': rr[-1]['frame_number_1based'], 'first_time': rr[0]['timestamp'], 'last_time': rr[-1]['timestamp'],
                      'packets': len(rr), 'old_fit_select_exposed': key in exposed,
                      'candidate_targets': sum(r['frame_number_1based'] in {x['frame_number_1based'] for x in selected} for r in rr)} for key,rr in sorted(sessions.items())))
                ledger = {'file_id': i, 'raw_member': name, 'member_sha256': member_sha, 'member_bytes': len(payload),
                          'packets': len(packets), 'linktype': linktype, 'first_time': packets[0]['timestamp'], 'last_time': packets[-1]['timestamp'],
                          'original_fit_select_targets': len(old), 'actual_semantic_frame_mismatches': sum(not r['same_actual_and_semantic_frame'] for r in mapped),
                          'cutoff_frame_1based': cutoff_frame, 'cutoff_time': cutoff_time,
                          'legacy_eligible_packets': sum(r['legacy_input_eligible'] for r in packets), 'sessions': len(sessions),
                          'exposed_sessions': len(exposed), 'candidate_targets': len(selected),
                          'candidate_sessions': len({r['session_key_sha256'] for r in selected}), 'exclusion_counts': reasons}
                ledgers.append(ledger)
                dump(OUT / ('%02d_summary.json' % i), ledger)
                print(json.dumps({'file': i, 'packets':len(packets), 'candidates':len(selected), 'identity_mismatches':ledger['actual_semantic_frame_mismatches']}), flush=True)
        jsonl(OUT / 'original_fit_select_exposure.jsonl', all_mappings)
        jsonl(OUT / 'id_candidate_target_plan.jsonl', all_candidates)
        global_cutoff = max(row['cutoff_time'] for row in ledgers)
        global_late = [r for r in all_candidates if r['timestamp'] > global_cutoff]
        result = {'schema': 'legacy-id-temporal-qualification-v1', 'date': '2026-09-16',
                  'status': 'QUALIFIED_SOURCE_TEMPORAL_NEW_SESSION_CANDIDATES' if all_candidates else 'NO_QUALIFIED_CANDIDATES_UNDER_NEW_SESSION_RULE',
                  'members': ledgers, 'packets': sum(r['packets'] for r in ledgers), 'original_exposure_targets':len(all_mappings),
                  'candidate_targets': len(all_candidates), 'candidate_sessions': len({(r['raw_member'],r['session_key_sha256']) for r in all_candidates}),
                  'global_ID_latest_old_target_time':global_cutoff, 'candidates_also_after_all_five_captures_latest_old_target':len(global_late),
                  'identity_semantics_warning_count':sum(r['actual_semantic_frame_mismatches'] for r in ledgers),
                  'model_loads':0,'feature_arrays_opened':0,'model_forwards':0,'optimizer_steps':0,'raw_members_opened':5,
                  'independence': 'Source-local chronological holdout in entirely unexposed canonical sessions, same original benign ID captures; not independent capture/device/campaign or untouched final.',
                  'limitations':['Other historical predecessor fit/development exposure is not fully eliminated; this is not a half-year untouched test.',
                                 'External E3 pretraining full deduplication unknown.',
                                 'Actual cache and semantic annotation timestamp exposure union is excluded if historical metadata differs.',
                                 'Source-local chronological separation does not itself imply global all-device temporal deployment simulation.',
                                 'Packet targets within a retained session are dependent; do not use packet counts as independent observations.'],
                  'elapsed_seconds':time.monotonic()-start}
        dump(OUT / 'qualification.json',result)
        files=sorted(p for p in OUT.rglob('*') if p.is_file() and p.name not in {'SHA256SUMS','status.json'})
        (OUT / 'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.relative_to(OUT).as_posix()+'\n' for p in files),encoding='utf-8')
        dump(OUT / 'status.json', {'status':'COMPLETE','qualification_status':result['status'],'candidate_targets':len(all_candidates),'exit_code':0,'elapsed_seconds':time.monotonic()-start})
    except Exception as error:
        dump(OUT / 'status.json', {'status':'STOP','reason':str(error),'exit_code':1,'elapsed_seconds':time.monotonic()-start,'retries':0})
        raise


if __name__ == '__main__':
    main()
