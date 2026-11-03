"""Causal normal-reference preparation, independent of heads and target scores.

Only generated tests are run in the initial delivery. Real execution is explicit:
``decoded`` consumes a pinned complete decoder export; ``old-bank`` consumes a
pinned parent RECENT snapshot database. Neither command makes E3 vectors.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from decimal import Decimal
import gzip
import hashlib
import json
import math
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys

import numpy as np
import continuous_input_v3 as inp

VERSION = 'constrained-onboarding-reference-v1-20261015'
SALT = 'commissioning-reference-v1-20260924'
PARTITIONS = ('LEARN', 'DEV', 'EXTERNAL_ARCHIVAL_EVALUATION')
POLICIES = {'B0': (3600, False), 'B1': (3600, True), 'B2': (7200, True)}
require = inp.require
digest = inp.digest


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024**2), b''):
            value.update(chunk)
    return value.hexdigest()


def pin(path, expected):
    path = Path(path)
    require(path.is_file() and sha(path) == expected, 'IDENTITY:' + str(path))
    return path


def _safe_output(output, *, protected_paths=(), protected_files=()):
    """Resolve links before any mkdir/model load; files do not protect siblings."""
    target = Path(output).resolve()
    for source in protected_paths:
        protected = Path(source).resolve()
        require(not target.is_relative_to(protected), 'OUTPUT_INSIDE_PROTECTED_INPUT:'+str(protected))
    for source in protected_files:
        protected = Path(source).resolve()
        require(target != protected and not target.is_relative_to(protected),
                'OUTPUT_OVERLAPS_PROTECTED_FILE:'+str(protected))
    return target


def _sealed_input_roots(files):
    """Only an adjacent manifest identifies a sealed tree; never guess parents."""
    return [Path(p).resolve().parent for p in files
            if (Path(p).resolve().parent/'SHA256SUMS').is_file()]


def _hex(value):
    return isinstance(value, str) and len(value) == 64 and all(x in '0123456789abcdef' for x in value)


def _row_identity(row, expected_source=None, *, require_canonical=False):
    """Original UID/component/namespace definitions, independently rechecked."""
    require(row['partition'] in PARTITIONS and row['protocol'] in (6, 17), 'REFERENCE_PARTITION_PROTOCOL')
    require(type(row['frame']) is int and row['frame'] > 0, 'REFERENCE_FRAME')
    require(isinstance(row['timestamp'], (int, float)) and math.isfinite(row['timestamp']), 'REFERENCE_TIME')
    require(_hex(row['source_sha256']), 'SOURCE_SHA256')
    require(expected_source is not None and row['source_sha256'] == expected_source, 'SNAPSHOT_SOURCE')
    owner = row['owner']
    require(isinstance(owner, str) and owner and owner == owner.lower(), 'OWNER_IDENTITY')
    require(_hex(row['component_id']) and _hex(row['session_id']), 'COMPONENT_NAMESPACE_DIGEST')
    require(row['uid'] == digest([row['source_sha256'], row['frame'], owner]), 'SOURCE_FRAME_OWNER_UID')
    require(isinstance(row['device'], str) and bool(row['device']), 'DEVICE_IDENTITY')
    # Historical UNSW metadata deliberately omitted the full canonical tuple.
    # Its independently pinned producer/UID/namespace remain the authority;
    # do not invent a tuple from hash strings or raw flow-header tokens.
    if 'canonical_key' not in row:
        require(not require_canonical, 'CANONICAL_KEY_REQUIRED_FOR_NEW_CANDIDATE')
        return
    key = row['canonical_key']
    require(isinstance(key, (list, tuple)) and len(key) == 3 and key[0] == row['protocol'], 'CANONICAL_KEY')
    for endpoint in key[1:]:
        require(isinstance(endpoint, (list, tuple)) and len(endpoint) == 2 and
                isinstance(endpoint[0], str) and bool(endpoint[0]) and
                type(endpoint[1]) is int and 0 <= endpoint[1] <= 65535, 'CANONICAL_ENDPOINT')
    require(list(map(tuple, key[1:])) == sorted(map(tuple, key[1:])), 'NONCANONICAL_ENDPOINT_ORDER')
    require(row['component_id'] == digest([owner, key]), 'OWNER_COMPONENT_IDENTITY')
    require(row['session_id'] == digest([owner, row['capture_id'], key]), 'CAPTURE_NAMESPACE_IDENTITY')


def _snapshot_descriptor(body, row):
    """Frozen q14 transform; role and source guards live in public adapters.

    The packet/header/token validation and transformation intentionally follow
    query_tail_core_v2.descriptor. Reference roles never pass through that API.
    """
    p, flow = body['provenance'], body['flow']
    proto = row['protocol']
    require(proto in (6, 17) and flow['protocol'] == proto, 'QUERY_PROTOCOL')
    require(p['version'] == inp.VERSION, 'SNAPSHOT_VERSION')
    require(p['query_frame'] == row['frame'] and p['namespace_sha256'] == row['session_id'], 'QUERY_IDENTITY')
    now = p['query_time_ns']
    require(type(now) is int and float(Decimal(now)/Decimal(10**9)) == row['timestamp'], 'QUERY_TIME')
    bursts = p['bursts']; width = 12 if proto == 6 else 6
    require(0 < len(bursts) <= 12 and all(len(flow[k]) == len(bursts) for k in ('counts', 'directions', 'burst_tokens', 'iats', 'bytes')), 'BURST_SCHEMA')
    frames, times, directions, query = [], [], [], []
    previous_burst = None
    for b, burst in enumerate(bursts):
        ff, tt, hh = burst['frames'], burst['times_ns'], burst['headers']
        require(0 < len(ff) <= 6 and len(ff) == len(tt) == len(hh) == flow['counts'][b], 'PACKET_SCHEMA')
        require(type(flow['directions'][b]) is bool, 'DIRECTION_SCHEMA')
        require(all(type(f) is int for f in ff) and all(type(t) is int for t in tt), 'TIME_FRAME_TYPE')
        require(all(ff[i] < ff[i+1] and tt[i] <= tt[i+1] for i in range(len(ff)-1)), 'BURST_ORDER')
        packed = []
        for f, t, h in zip(ff, tt, hh):
            require(len(h) == width and all(type(v) is int and 0 <= v <= 65535 for v in h), 'HEADER_SCHEMA')
            require(0 < f <= row['frame'] and 0 <= now-t <= 60*10**9, 'FUTURE_OR_AGED_PACKET')
            packed.extend(h + [0]*6)
            frames.append(f); times.append(t); directions.append(flow['directions'][b])
            if f == row['frame']:
                require(t == now, 'CURRENT_TIME')
                query.append((h, flow['directions'][b]))
        require(flow['burst_tokens'][b] == packed, 'FLOW_HEADER_JOIN')
        # IPv6 total length can exceed one token; compare modulo 2**16 while
        # preserving original untruncated bytes in the E3 flow.
        require(type(flow['bytes'][b]) is int and flow['bytes'][b] >= sum(h[2] for h in hh) and
                (flow['bytes'][b]-sum(h[2] for h in hh)) % 65536 == 0, 'FLOW_BYTES_JOIN')
        require(flow['iats'][b] == (0 if previous_burst is None else tt[0]-previous_burst), 'FLOW_IAT_JOIN')
        previous_burst = tt[0]
    require(len(frames) == len(set(frames)) <= 72 and len(query) == 1, 'CURRENT_UNIQUE')
    order = np.argsort(frames)
    require(all(times[int(order[i])] <= times[int(order[i+1])] for i in range(len(order)-1)), 'WINDOW_TIME_ORDER')
    require(directions[int(order[0])] is True, 'FIRST_SOURCE_DIRECTION')
    require(flow['flow_duration'] == (now-min(times))//1000, 'FLOW_DURATION')
    h, direction = query[0]
    flags = h[5] if proto == 6 else 0
    require(flags <= 511, 'UNSUPPORTED_FLAG_BITS')
    q = [float(proto == 6)] + [float(bool(flags & (1 << b))) for b in range(9)]
    q += [math.log1p(h[2])/math.log(65536), math.log1p(h[6])/math.log(65536) if proto == 6 else 0.,
          math.log1p(h[5])/math.log(65536) if proto == 17 else 0., float(direction)]
    stage = ('UDP' if proto == 17 else 'TCP_RST' if flags & 4 else
             'TCP_SYN_NO_ACK' if flags & 2 and not flags & 16 else 'TCP_SYN_ACK' if flags & 2 else
             'TCP_FIN' if flags & 1 else 'TCP_OTHER')
    info = dict(stage=stage, syn_no_ack=bool(proto == 6 and flags & 2 and not flags & 16),
                packets=len(frames), bursts=len(bursts), span_seconds=(now-min(times))/1e9,
                same_direction=sum(d == direction for d in directions),
                opposite_direction=sum(d != direction for d in directions))
    return np.asarray(q, dtype=np.float32), info


def reference_descriptor(body, row, *, source_sha256=None):
    require(row.get('use') == 'REFERENCE' and type(row.get('label')) is int and row['label'] == 0,
            'REFERENCE_ROLE')
    require(math.isfinite(row['reference_end']) and row['timestamp'] <= row['reference_end'], 'REFERENCE_TIME_CUTOFF')
    expected = source_sha256 if source_sha256 is not None else body.get('source_sha256')
    require('source_sha256' not in body or body['source_sha256'] == expected, 'BODY_SOURCE')
    _row_identity(row, expected, require_canonical=source_sha256 is None)
    if 'bank_end_frame' in row:
        require(type(row['bank_end_frame']) is int and row['frame'] <= row['bank_end_frame'], 'REFERENCE_FRAME_CUTOFF')
    return _snapshot_descriptor(body, row)


def query_descriptor(body, row, *, source_sha256=None):
    require(row.get('use') != 'REFERENCE' and row['partition'] in PARTITIONS, 'QUERY_ROLE')
    expected = source_sha256 if source_sha256 is not None else body.get('source_sha256')
    require('source_sha256' not in body or body['source_sha256'] == expected, 'BODY_SOURCE')
    _row_identity(row, expected, require_canonical=source_sha256 is None)
    return _snapshot_descriptor(body, row)


def _hash_order(row):
    return hashlib.sha256((SALT + '|' + row['component_id']).encode()).hexdigest(), row['component_id']


def _activity(row):
    value = row.get('activity')
    if row.get('activity_verified') is not True or value in (None, '', 'ACTIVE_UNANNOTATED', 'UNKNOWN', 'UNKNOWN_PASSIVE'):
        return 'UNKNOWN'
    require(isinstance(value, str) and bool(row.get('activity_evidence')), 'ACTIVITY_EVIDENCE')
    return value


def _round_robin(groups, count):
    """Stable lexicographic stratum order, skip exhausted groups."""
    keys = sorted(groups); positions = {key: 0 for key in keys}; result = []
    while len(result) < count:
        changed = False
        for key in keys:
            if positions[key] < len(groups[key]) and len(result) < count:
                result.append(groups[key][positions[key]])
                positions[key] += 1; changed = True
        if not changed:
            break
    return result


def plan_banks(candidates, census_receipt, *, t0, policy, max_total_components=64):
    """Select only from a complete, receipt-bound last-endpoint census.

    No candidate score/label changes the policy. B1 derives its quotas from the
    *same* B0 candidate universe, rather than from a caller's suggested budget.
    """
    require(policy in POLICIES and max_total_components == 64, 'FIXED_REFERENCE_POLICY')
    duration, stratified = POLICIES[policy]
    rows = list(candidates); receipt = census_receipt
    require(receipt.get('generator_version') == VERSION and receipt.get('status') == 'COMPLETE' and
            receipt.get('enumeration') == 'ALL_LEGAL_ENDPOINTS_LAST_PER_COMPONENT' and
            receipt.get('window_closed') is True, 'COMPLETE_CENSUS_REQUIRED')
    require(receipt.get('duration_seconds') == duration and receipt.get('t0') == t0 and
            receipt.get('cutoff') == t0 + duration, 'CENSUS_WINDOW')
    require(receipt.get('candidate_rows') == len(rows) and receipt.get('candidates_sha256') == digest(rows), 'CENSUS_CANDIDATE_PIN')
    require(isinstance(receipt.get('decoder_identity'), dict) and receipt['decoder_identity'], 'DECODER_IDENTITY_REQUIRED')
    source = receipt['source_sha256']
    require(_hex(source) and isinstance(receipt.get('normality_evidence'), str) and receipt['normality_evidence'], 'NORMAL_SOURCE_REQUIRED')
    registry = receipt['device_registry']; registry_by = {r['device']: r for r in registry}
    require(len(registry_by) == len(registry) and len({r['owner'] for r in registry}) == len(registry), 'REGISTRY_DUPLICATE')
    groups = defaultdict(list); identities = set(); uids = set()
    for original in rows:
        r = dict(original)
        require(not any(k in r for k in ('sample_count', 'candidate_rank', 'selection_rank')), 'SPARSE_HISTORICAL_CANDIDATES_REJECTED')
        _row_identity(r, source, require_canonical=True)
        require(r['use'] == 'REFERENCE' and r['label'] == 0 and r['capture_id'] == receipt['capture_id'], 'CANDIDATE_ROLE_SOURCE')
        require(t0 <= r['timestamp'] <= t0+duration and r['reference_end'] == t0+duration and
                r['bank_end_frame'] == receipt['cutoff_frame'] and r['frame'] <= receipt['cutoff_frame'], 'WHOLE_BANK_CUTOFF')
        require(r['device'] in registry_by and all(r[k] == registry_by[r['device']][k] for k in ('owner', 'partition')), 'DEVICE_REGISTRY_JOIN')
        identity = r['owner'], r['component_id']
        require(identity not in identities and r['uid'] not in uids, 'CANDIDATE_COMPONENT_DUPLICATE')
        identities.add(identity); uids.add(r['uid']); groups[(r['device'], r['protocol'])].append(r)
    selected, banks = [], []
    for device in sorted(registry_by):
        available = {proto: sorted(groups[(device, proto)], key=_hash_order) for proto in (6, 17)}
        # TCP=6 sorts before UDP=17, preserving the frozen allocation rule.
        base = _round_robin(available, max_total_components)
        quotas = Counter(r['protocol'] for r in base)
        chosen = []
        for proto in (6, 17):
            if stratified:
                strata = defaultdict(list)
                for r in available[proto]:
                    quartile = min(3, math.floor(4*(r['timestamp']-t0)/duration))
                    strata[(_activity(r), quartile)].append(r)
                chosen.extend(_round_robin(strata, quotas[proto]))
            else:
                chosen.extend(available[proto][:quotas[proto]])
        chosen.sort(key=lambda r: (r['protocol'], _hash_order(r)))
        require(len(chosen) == len(base) and Counter(r['protocol'] for r in chosen) == quotas, 'MATCHED_B0_BUDGET')
        for proto in (6, 17):
            rr = [r for r in chosen if r['protocol'] == proto]
            banks.append(dict(device=device, protocol=proto, reference_end=t0+duration,
                              bank_end_frame=receipt['cutoff_frame'], count=len(rr),
                              status='AVAILABLE' if len(rr) >= 2 else 'INSUFFICIENT_DISTINCT_COMPONENTS',
                              uids=[r['uid'] for r in rr]))
        selected.extend(chosen)
    result = dict(rows=selected, banks=banks,
                  receipt=dict(version=VERSION, policy=policy, status='PREPARATION_REQUIRED',
                               reference_metadata='COMPLETE', q14='REQUIRES_MATCHED_SNAPSHOTS',
                               E3='PREPARATION_REQUIRED_RECENT_ENCODER', t0=t0, cutoff=t0+duration,
                               max_total_components=max_total_components, source_sha256=source,
                               census_sha256=digest(receipt), selected_rows=len(selected),
                               selected_uid_sha256=digest([r['uid'] for r in selected]),
                               bank_roster_sha256=digest(banks)))
    return result


def prepare_decoded_capture(decoded_rows, capture_spec, device_registry, *, t0,
                            duration_seconds=7200, decoder_identity, event_api=None):
    """Enumerate complete causal windows from an unfiltered contiguous prefix.

    Stops at the first frame beyond the requested cutoff. Later malformed
    headers/timestamps cannot change or invalidate an already closed bank.
    The reader must cover through that boundary (or the recorded capture end).
    The returned 1h and 2h censuses use their own last legal representatives.
    """
    require(duration_seconds in (3600, 7200), 'FIXED_OBSERVATION_DURATION')
    require(capture_spec.get('provenance') == 'normal' and capture_spec.get('normality_evidence'), 'NORMAL_CAPTURE_REQUIRED')
    require(capture_spec.get('t0') == t0 and _hex(capture_spec['sha256']), 'CAPTURE_START_SOURCE')
    require(isinstance(decoder_identity, dict) and decoder_identity and
            decoder_identity.get('unfiltered') is True and decoder_identity.get('occurrence') == 'f', 'COMPLETE_DECODER_REQUIRED')
    registry = sorted((dict(r) for r in device_registry), key=lambda r: r['device'])
    require(registry and len({r['owner'] for r in registry}) == len(registry) and
            len({r['device'] for r in registry}) == len(registry), 'REGISTRY_DUPLICATE')
    for r in registry:
        require(r['owner'] == r['owner'].lower() and r['partition'] in ('DEV', 'EXTERNAL_ARCHIVAL_EVALUATION'), 'TARGET_REFERENCE_REGISTRY')
    known = set(capture_spec['known_macs']); wanted = {r['owner'] for r in registry}
    require(wanted <= known, 'INCOMPLETE_OWNER_REGISTRY')
    if event_api is None:
        import legacy_reference_sample_prepare_v1 as prep
        event_api = prep.old.legacy_runtime()[0]
    contexts = inp.Contexts(capture_spec['capture_id'], known, event_api, required_owners=wanted)
    by_owner = {r['owner']: r for r in registry}
    durations = (3600,) if duration_seconds == 3600 else (3600, 7200)
    ends = {d: inp.nanos(t0) + d*inp.NS for d in durations}
    candidates = {d: {} for d in durations}; snapshots = {d: {} for d in durations}
    counts = Counter(); cutframes = {d: 0 for d in durations}; closed = {}; count = 0
    for packet in decoded_rows:
        frame, now = inp.integer(packet['frame.number']), inp.nanos(packet['frame.time_epoch'])
        require(frame == count+1, 'NONCONTIGUOUS_CAPTURE_FRAME')
        if count == 0:
            require(float(Decimal(now)/Decimal(inp.NS)) == t0, 'CAPTURE_T0_FIRST_FRAME')
        for d in durations:
            if d not in closed and now > ends[d]:
                closed[d] = dict(reason='FIRST_FRAME_AFTER_CUTOFF', boundary_frame=frame, boundary_time_ns=now)
        if all(d in closed for d in durations):
            break
        owner, namespace, event = contexts.append(packet)
        count = frame
        for d in durations:
            if d not in closed:
                cutframes[d] = frame
        if not contexts.query_allowed or namespace is None:
            continue
        require(owner in by_owner, 'TARGET_OWNER')
        if now < inp.nanos(t0):
            continue
        meta = by_owner[owner]
        flow, state, provenance = contexts.states[namespace].snapshot()
        body = dict(flow=flow, state=state, provenance=provenance, source_sha256=capture_spec['sha256'])
        key = namespace[-1]
        row = dict(uid=digest([capture_spec['sha256'], frame, owner]), device=meta['device'], owner=owner,
                   partition=meta['partition'], use='REFERENCE', label=0, protocol=event.ip_proto,
                   component_id=digest([owner, key]), capture_id=capture_spec['capture_id'],
                   source_sha256=capture_spec['sha256'], session_id=digest(namespace), canonical_key=key,
                   frame=frame, timestamp=event.timestamp,
                   activity=capture_spec.get('activity', 'UNKNOWN'),
                   activity_verified=capture_spec.get('activity_verified', False),
                   activity_evidence=capture_spec.get('activity_evidence'))
        for d in durations:
            if d in closed:
                continue
            counts[d] += 1
            r = dict(row, reference_end=t0+d)
            identity = owner, r['component_id']
            old = candidates[d].get(identity)
            if old is None or (r['timestamp'], r['capture_id'], r['frame'], r['uid']) > (old['timestamp'], old['capture_id'], old['frame'], old['uid']):
                candidates[d][identity] = r
                snapshots[d][identity] = body
    for d in durations:
        if d not in closed:
            require(count == capture_spec.get('expected_packets') and
                    capture_spec.get('recorded_capture_end', -math.inf) >= t0+d, 'PREPARATION_REQUIRED_INCOMPLETE_WINDOW')
            closed[d] = dict(reason='VERIFIED_CAPTURE_END', last_frame=count)
    result = {}
    for d in durations:
        rr = sorted(candidates[d].values(), key=lambda r: (r['device'], r['protocol'], r['component_id']))
        for r in rr:
            r['bank_end_frame'] = cutframes[d]
        bodies = {r['uid']: snapshots[d][(r['owner'], r['component_id'])] for r in rr}
        receipt = dict(generator_version=VERSION, status='COMPLETE', enumeration='ALL_LEGAL_ENDPOINTS_LAST_PER_COMPONENT',
                       window_closed=True, boundary=closed[d], t0=t0, duration_seconds=d, cutoff=t0+d,
                       cutoff_frame=cutframes[d], candidate_rows=len(rr), legal_endpoint_count=counts[d],
                       candidates_sha256=digest(rr), capture_id=capture_spec['capture_id'],
                       source_sha256=capture_spec['sha256'], normality_evidence=capture_spec['normality_evidence'],
                       decoder_identity=decoder_identity, device_registry=registry,
                       input_version=inp.VERSION, e3_status='PREPARATION_REQUIRED',
                       rule='First observed boundary closes window permanently; no later events enter bank')
        result[d] = dict(rows=rr, snapshots=bodies, receipt=receipt)
    return result


def extract_old_bank_q14(snapshot_db, rows, expected_db_sha256):
    """Read original UID identities, including arbitrary parent role subsets.

    Caller must pin the parent metadata manifest separately. SQL slots belong
    to the full parent role, not to the supplied subset's enumeration.
    """
    rows = list(rows)
    require(len({r['uid'] for r in rows}) == len(rows), 'REFERENCE_UID_DUPLICATE')
    path = pin(snapshot_db, expected_db_sha256).resolve()
    output = np.empty((len(rows), 14), dtype=np.float32)
    db = sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1', uri=True)
    try:
        db.execute('PRAGMA query_only=ON')
        for i, row in enumerate(rows):
            found = db.execute('SELECT uid,role,slot,protocol,body FROM snapshots WHERE uid=?', (row['uid'],)).fetchall()
            require(len(found) == 1, 'REFERENCE_SNAPSHOT_UID')
            uid, role, slot, proto, body = found[0]
            expected_role = 'UNSW_REFS' if row['partition'] == 'EXTERNAL_ARCHIVAL_EVALUATION' else 'SOURCE_REFS'
            require(role == expected_role and proto == row['protocol'] and type(slot) is int and slot >= 0,
                    'REFERENCE_SNAPSHOT_ROLE')
            require('parent_slot' not in row or row['parent_slot'] == slot, 'REFERENCE_PARENT_SLOT')
            output[i] = reference_descriptor(json.loads(body), row, source_sha256=row['source_sha256'])[0]
    finally:
        db.close()
    return output


def _read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def _write_json(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=True, indent=2, allow_nan=False)
        stream.write('\n')


def _rows(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt', encoding='utf-8') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _write_rows(path, rows):
    with gzip.open(path, 'xt', encoding='utf-8', newline='\n') as stream:
        for row in rows:
            stream.write(json.dumps(row, separators=(',', ':'), allow_nan=False)+'\n')


def save_prepared(output, prepared, *, protected_paths=()):
    """Publish real selected flow snapshots/q14 for later pinned E3 encoding."""
    output = _safe_output(output, protected_paths=protected_paths)
    output.mkdir(parents=True, exist_ok=False)
    for policy, (duration, _) in POLICIES.items():
        if duration not in prepared:
            continue
        item = prepared[duration]
        plan = plan_banks(item['rows'], item['receipt'], t0=item['receipt']['t0'], policy=policy)
        folder = output/policy; folder.mkdir()
        _write_rows(folder/'candidates.jsonl.gz', item['rows'])
        _write_json(folder/'census_receipt.json', item['receipt'])
        _write_rows(folder/'references.jsonl.gz', plan['rows'])
        _write_json(folder/'banks.json', plan['banks'])
        q14 = np.empty((len(plan['rows']), 14), dtype=np.float32)
        selected = []
        for i, row in enumerate(plan['rows']):
            body = item['snapshots'][row['uid']]
            q14[i] = reference_descriptor(body, row)[0]
            selected.append(dict(uid=row['uid'], role='UNSW_REFS' if row['partition']=='EXTERNAL_ARCHIVAL_EVALUATION' else 'SOURCE_REFS',
                                 slot=i, protocol=row['protocol'], body=body))
        _write_rows(folder/'selected_snapshots.jsonl.gz', selected)
        np.save(folder/'reference_q14.npy', q14, allow_pickle=False)
        plan['receipt'].update(q14='COMPLETE_REAL_CAUSAL_SNAPSHOT', snapshots='COMPLETE',
                               files={p.name: sha(p) for p in sorted(folder.iterdir()) if p.is_file()})
        _write_json(folder/'receipt.json', plan['receipt'])
    _write_json(output/'receipt.json', dict(version=VERSION, status='PREPARATION_REQUIRED',
                reference_preparation='COMPLETE', E3='PREPARATION_REQUIRED_RECENT_ENCODER',
                real_E3_forwards=0, model_training=False, target_scoring=False))


def prepare_raw_capture(config, output, *, decoder_factory=None, event_runtime=None,
                        progress_factory=None, decoder_identity=None):
    """Real raw entry: pin source, reuse frozen full decoder and owner contexts.

    Decoder output after the bank closes is drained only for subprocess exit
    and source packet-count verification. It cannot enter saved bank snapshots.
    Injection points are reserved for explicitly synthetic generated tests.
    """
    raw_input = config['capture']['path']
    output = _safe_output(output, protected_paths=list(config.get('protected_paths', []))+
                          _sealed_input_roots([raw_input]), protected_files=[raw_input])
    from legacy_unsw_archival_runtime_v1 import decode, fields, Progress
    import legacy_reference_sample_prepare_v1 as prep
    synthetic = config.get('synthetic_only') is True
    if any(x is not None for x in (decoder_factory, event_runtime, progress_factory, decoder_identity)):
        require(synthetic, 'SYNTHETIC_ADAPTER_IN_REAL_PREPARATION')
    api = prep.old.legacy_runtime() if event_runtime is None else event_runtime
    decoder = decode if decoder_factory is None else decoder_factory
    spec = config['capture']; path = pin(spec['path'], spec['sha256'])
    require(type(spec.get('expected_packets')) is int and spec['expected_packets'] > 0, 'RAW_PACKET_COUNT_REQUIRED')
    before = (path.stat().st_size, path.stat().st_mtime_ns)
    require(spec.get('bytes', before[0]) == before[0], 'RAW_BYTES')
    if decoder_identity is None:
        tshark = Path(config['tshark'])
        executable_hash = sha(tshark)
        version = subprocess.run([str(tshark), '--version'], check=True, capture_output=True,
                                 text=True, timeout=30).stdout
        decoder_identity = dict(name='tshark', executable_sha256=executable_hash,
                                version=version, fields=fields(api), unfiltered=True,
                                occurrence='f', continuous_input_version=inp.VERSION)
    require(not output.exists(), 'NO_OVERWRITE:'+str(output))
    output.mkdir(parents=True)
    _write_json(output/'environment.json', _environment())
    limits = config.get('limits', dict(wall_seconds=172800, memory_gib=150, disk_gib=100))
    require(0 < limits['memory_gib'] <= 150, 'PREPARATION_MEMORY_LIMIT')
    factory = Progress if progress_factory is None else progress_factory
    progress = factory(output/'progress', limits)
    progress.stage = 'P_COMPLETE_NORMAL_DECODE'
    try:
        with decoder(path, spec, api, progress, output/'decoder.stderr.log', config.get('tshark')) as source:
            n = [0]
            def counted():
                for row in source:
                    n[0] += 1
                    if n[0] % 8192 == 0:
                        progress.tick(n[0], spec['expected_packets'])
                    yield row
            stream = counted()
            prepared = prepare_decoded_capture(stream, spec, config['device_registry'],
                        t0=spec['t0'], decoder_identity=decoder_identity, event_api=api[0])
            # Do not terminate the inherited decoder while its stdout pipe is
            # full; consume it and verify its successful, zero-stderr exit.
            for _ in stream:
                pass
        require(n[0] == spec['expected_packets'], 'RAW_COMPLETE_PACKET_COUNT')
        require(before == (path.stat().st_size, path.stat().st_mtime_ns), 'RAW_CHANGED_DURING_READ')
        for item in prepared.values():
            item['receipt'].update(raw_bytes=before[0], raw_complete_packets=n[0],
                                   synthetic_only=synthetic)
        save_prepared(output/'prepared', prepared)
        _write_json(output/'raw_receipt.json', dict(version=VERSION, status='COMPLETE',
                    source_sha256=spec['sha256'], raw_bytes=before[0], packets=n[0],
                    decoder_identity=decoder_identity, synthetic_only=synthetic,
                    environment_sha256=sha(output/'environment.json'),
                    preparation='prepared', E3='PREPARATION_REQUIRED'))
        progress.stop('COMPLETE')
        return output/'prepared'
    except BaseException as exc:
        progress.stop('STOPPED_NO_RETRY', error=repr(exc))
        raise


def _pin_runtime_tree(root, expected_manifest):
    """Bind the actual vendor directory used by e3_runtime, not an unused file."""
    root = Path(root).resolve()
    manifest = pin(root/'SHA256SUMS', expected_manifest)
    listed = set()
    for line in manifest.read_text(encoding='utf-8').splitlines():
        checksum, relative = line.split('  ', 1)
        p = (root/relative).resolve()
        try:
            p.relative_to(root)
        except ValueError:
            raise RuntimeError('RUNTIME_MANIFEST_ESCAPE')
        require(relative not in listed, 'RUNTIME_MANIFEST_DUPLICATE')
        listed.add(relative); pin(p, checksum)
    actual = {p.relative_to(root).as_posix() for folder in ('vendor/netFound', 'vendor/netFound-base')
              for p in (root/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    require(actual and actual <= listed, 'RUNTIME_VENDOR_TREE_NOT_PINNED')
    require(any(x.startswith('vendor/netFound-base/') and x.endswith(('.safetensors', '.bin')) for x in actual),
            'FROZEN_ENCODER_WEIGHTS_REQUIRED')
    return dict(manifest_sha256=expected_manifest, vendor_files=len(actual))


def _environment():
    import contextlib
    import io
    import warnings
    import torch
    info = dict(platform=platform.platform(), machine=platform.machine(), processor=platform.processor(),
                python=sys.version, numpy=np.__version__, torch=torch.__version__,
                torch_cpu_capability=torch.backends.cpu.get_cpu_capability(),
                torch_threads=torch.get_num_threads(), torch_config=torch.__config__.show())
    buf = io.StringIO()
    with warnings.catch_warnings(record=True) as captured, contextlib.redirect_stdout(buf):
        warnings.simplefilter('always')
        np.show_config()
    info['numpy_blas_config'] = buf.getvalue()
    info['numpy_config_warnings'] = [str(item.message) for item in captured]
    if sys.platform.startswith('linux'):
        result = subprocess.run(['lscpu'], capture_output=True, text=True, timeout=30)
        info['lscpu'] = result.stdout if result.returncode == 0 else 'UNAVAILABLE:'+result.stderr
    else:
        info['lscpu'] = 'NOT_APPLICABLE'
    return info


def encode_selected(prepared_policy, output, config, *, runtime_factory=None):
    """Encode exact selected RECENT snapshots using frozen shape-matched E3.

    Output bank.npz contains uid, raw e3 (N,768), q14 (N,14). The fixed source
    normalizer is pinned and recorded; normalization remains the geometry
    module's responsibility. No classifier, threshold, or target label is read.
    """
    synthetic = config.get('synthetic_only') is True
    protected = [prepared_policy] + list(config.get('protected_paths', []))
    if not synthetic:
        protected.append(config['runtime_root'])
    output = _safe_output(output, protected_paths=protected, protected_files=[config['normalizer']])
    from legacy_unsw_archival_runtime_v1 import e3_runtime
    from continuous_features_v3 import tokenize, verify_batch, tensor_hash
    require(runtime_factory is None or synthetic, 'SYNTHETIC_ENCODER_IN_REAL_PREPARATION')
    require(not synthetic or runtime_factory is not None, 'SYNTHETIC_ENCODER_FACTORY_REQUIRED')
    prepared = Path(prepared_policy)
    receipt = _read_json(pin(prepared/'receipt.json', config['prepared_receipt_sha256']))
    require(receipt.get('q14') == 'COMPLETE_REAL_CAUSAL_SNAPSHOT' and receipt.get('snapshots') == 'COMPLETE',
            'MATCHED_REFERENCE_SNAPSHOTS_REQUIRED')
    for name, checksum in receipt['files'].items():
        require(Path(name).name == name, 'PREPARED_PATH_ESCAPE')
        pin(prepared/name, checksum)
    rows = _rows(prepared/'references.jsonl.gz')
    entries = _rows(prepared/'selected_snapshots.jsonl.gz')
    census = _read_json(prepared/'census_receipt.json')
    require(not census.get('synthetic_only', False) or synthetic, 'SYNTHETIC_CENSUS_IN_REAL_ENCODER')
    replay_plan = plan_banks(_rows(prepared/'candidates.jsonl.gz'), census,
                            t0=census['t0'], policy=receipt['policy'])
    require(digest(rows) == digest(replay_plan['rows']) and
            digest(_read_json(prepared/'banks.json')) == replay_plan['receipt']['bank_roster_sha256'] and
            receipt['census_sha256'] == digest(census), 'SELECTED_REFERENCE_PLAN_REPLAY')
    q14 = np.load(prepared/'reference_q14.npy', allow_pickle=False)
    require(q14.shape == (len(rows), 14) and q14.dtype == np.float32 and np.isfinite(q14).all(), 'REFERENCE_Q14_SCHEMA')
    require(len(entries) == len(rows) and len({r['uid'] for r in rows}) == len(rows) and
            digest([r['uid'] for r in rows]) == receipt['selected_uid_sha256'], 'REFERENCE_ORDER_IDENTITY')
    normalizer = pin(config['normalizer'], config['normalizer_sha256'])
    with np.load(normalizer, allow_pickle=False) as norm:
        require(norm['mean'].shape == norm['scale'].shape == (768,) and np.isfinite(norm['mean']).all() and
                np.isfinite(norm['scale']).all() and np.all(norm['scale'] > 0), 'SOURCE_NORMALIZER_SCHEMA')
    runtime_identity = dict(synthetic_only=True) if synthetic else _pin_runtime_tree(config['runtime_root'], config['runtime_manifest_sha256'])
    factory = e3_runtime if runtime_factory is None else runtime_factory
    embed, _, model, tokenizer, collator = factory(config['runtime_root'])
    output.mkdir(parents=True, exist_ok=False)
    _write_json(output/'environment.json', _environment())
    groups = defaultdict(list); examples = {}
    for i, (row, entry) in enumerate(zip(rows, entries)):
        require(entry['uid'] == row['uid'] and entry['slot'] == i and entry['protocol'] == row['protocol'], 'SELECTED_SNAPSHOT_JOIN')
        require(np.array_equal(q14[i], reference_descriptor(entry['body'], row)[0]), 'SELECTED_Q14_REPLAY')
        example = tokenize(tokenizer, entry['body']['flow'])
        inp.verify_tokenized(entry['body']['flow'], entry['body']['provenance'], example)
        key = (row['protocol'], max(example['dataset_burst_sizes'])+1, len(example['dataset_burst_sizes']))
        groups[key].append(i); examples[i] = example
    e3 = np.empty((len(rows), 768), dtype=np.float32)
    tensor_receipts = []; batch_id = 0
    for shape, indices in sorted(groups.items()):
        ordered = sorted(indices, key=lambda i: rows[i]['uid'])
        for start in range(0, len(ordered), 16):
            ix = ordered[start:start+16]; batch_examples = [examples[i] for i in ix]
            batch = collator(batch_examples); verify_batch(batch_examples, batch)
            values = embed.core.e3_forward_batches(model, [batch], 'cpu')
            require(isinstance(values, np.ndarray) and values.shape == (len(ix), 768) and values.dtype == np.float32 and
                    np.isfinite(values).all(), 'RECENT_E3_SCHEMA')
            for j, i in enumerate(ix):
                e3[i] = values[j]
                tensor_receipts.append(dict(uid=rows[i]['uid'], slot=i, batch_id=batch_id,
                        shape=list(shape), actual_tensor_sha256=tensor_hash(batch, j),
                        feature_sha256=hashlib.sha256(values[j].tobytes()).hexdigest()))
            batch_id += 1
    with (output/'bank.npz').open('xb') as stream:
        np.savez(stream, uid=np.asarray([x['uid'] for x in rows], dtype='<U64'), e3=e3, q14=q14)
    _write_rows(output/'references.jsonl.gz', rows)
    _write_rows(output/'tensor_receipts.jsonl.gz', tensor_receipts)
    _write_json(output/'receipt.json', dict(version=VERSION,
                status='SYNTHETIC_COMPLETE' if synthetic else 'COMPLETE',
                synthetic_only=synthetic, policy=receipt['policy'],
                real_recent_features=not synthetic, complete_candidate_census=True,
                input_version=inp.VERSION, input_readout='RECENT_CURRENT_INCLUSIVE',
                e3_dimensions=768, q14_dimensions=14, rows=len(rows), batches=batch_id,
                prepared_receipt_sha256=config['prepared_receipt_sha256'], runtime=runtime_identity,
                census_receipt_sha256=sha(prepared/'census_receipt.json'),
                census_sha256=receipt['census_sha256'], source_sha256=census['source_sha256'],
                decoder_identity=census['decoder_identity'],
                t0=census['t0'], cutoff=census['cutoff'], cutoff_frame=census['cutoff_frame'],
                bank_roster_sha256=receipt['bank_roster_sha256'],
                selected_uid_sha256=receipt['selected_uid_sha256'],
                normalizer_sha256=config['normalizer_sha256'],
                bank_npz_sha256=sha(output/'bank.npz'), metadata_sha256=sha(output/'references.jsonl.gz'),
                tensor_receipts_sha256=sha(output/'tensor_receipts.jsonl.gz'), environment_sha256=sha(output/'environment.json'),
                model_training=False, classifier_scoring=False))
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest='mode', required=True)
    decoded = modes.add_parser('decoded', help='Use complete unfiltered pinned normal decoder export')
    decoded.add_argument('--config', required=True)
    decoded.add_argument('--output', required=True)
    old = modes.add_parser('old-bank', help='Extract real q14 from a pinned parent RECENT snapshot database')
    old.add_argument('--config', required=True)
    old.add_argument('--output', required=True)
    raw = modes.add_parser('raw', help='Pin and decode a complete normal PCAP, then prepare reference snapshots')
    raw.add_argument('--config', required=True)
    raw.add_argument('--output', required=True)
    encode = modes.add_parser('encode', help='Encode selected RECENT flow snapshots with the pinned frozen E3 runtime')
    encode.add_argument('--config', required=True)
    encode.add_argument('--prepared-policy', required=True)
    encode.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    config = _read_json(args.config)
    input_files = [args.config]
    for field in ('metadata', 'snapshot_db', 'decoder_receipt', 'decoded_tsv'):
        if field in config:
            input_files.append(config[field])
    _safe_output(args.output, protected_paths=list(config.get('protected_paths', []))+
                 _sealed_input_roots(input_files), protected_files=input_files)
    if args.mode == 'raw':
        prepare_raw_capture(config, args.output)
    elif args.mode == 'encode':
        encode_selected(args.prepared_policy, args.output, config)
    elif args.mode == 'old-bank':
        manifest = pin(config['metadata'], config['metadata_sha256'])
        rows = _rows(manifest)
        # Optional source-only subset; parent slots are intentionally not rebuilt.
        if 'partition' in config:
            rows = [r for r in rows if r['partition'] == config['partition']]
        q = extract_old_bank_q14(config['snapshot_db'], rows, config['snapshot_db_sha256'])
        out = Path(args.output); out.mkdir(parents=True, exist_ok=False)
        _write_rows(out/'references.jsonl.gz', rows)
        np.save(out/'reference_q14.npy', q, allow_pickle=False)
        _write_json(out/'receipt.json', dict(version=VERSION, status='PREPARATION_REQUIRED',
                    q14='COMPLETE_REAL_CAUSAL_SNAPSHOT', E3='REQUIRES_PINNED_PARENT_RECENT_E3',
                    rows=len(rows), metadata_sha256=config['metadata_sha256'],
                    snapshot_db_sha256=config['snapshot_db_sha256'],
                    q14_sha256=sha(out/'reference_q14.npy'), source_role_unchanged=True))
    else:
        export_receipt = _read_json(pin(config['decoder_receipt'], config['decoder_receipt_sha256']))
        require(export_receipt.get('status') == 'COMPLETE' and export_receipt.get('unfiltered') is True and
                export_receipt.get('source_sha256') == config['capture']['sha256'], 'COMPLETE_DECODER_EXPORT_REQUIRED')
        require(export_receipt.get('input_version') == inp.VERSION and
                export_receipt.get('decoder_identity', {}).get('unfiltered') is True, 'DECODER_INPUT_VERSION')
        decoded_path = pin(config['decoded_tsv'], export_receipt['decoded_tsv_sha256'])
        # Raw bytes and the export receipt must refer to the same original source.
        pin(config['capture']['path'], config['capture']['sha256'])
        opener = gzip.open if str(decoded_path).endswith('.gz') else open
        with opener(decoded_path, 'rt', encoding='utf-8', newline='') as stream:
            reader = csv.DictReader(stream, delimiter='\t', quotechar='"')
            require(reader.fieldnames == export_receipt['fields'], 'DECODER_HEADER_IDENTITY')
            prepared = prepare_decoded_capture(reader, config['capture'], config['device_registry'],
                        t0=config['capture']['t0'], decoder_identity=export_receipt['decoder_identity'])
        save_prepared(args.output, prepared)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
