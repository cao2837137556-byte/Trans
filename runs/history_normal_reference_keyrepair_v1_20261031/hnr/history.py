"""Whole-member stable chronological adapter; no hourly or role-boundary reset.

Real execution makes one byte-preserving chronological PCAPNG, then traverses
the complete unfiltered frozen decoder twice. Pass 1 stores endpoint identities
only; pass 2 materializes RECENT snapshots at the selected identities only.
"""
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sqlite3
import struct
import subprocess

import numpy as np

from .common import VERSION, SALT, TARGETS, digest, require, sha, write, rows, write_rows


def pin(spec):
    path = Path(spec['path'])
    require(path.is_file() and sha(path) == spec['sha256'], 'INPUT_SHA256:' + str(path))
    return path


def role_binding(index, order, target, *, frozen=True):
    """Raw observed dates, including rows the frontend later cannot accept."""
    require(index.ndim == order.ndim == 1 and len(index) == len(order) > 1, 'INDEX_LENGTH')
    require(order.dtype.kind in 'iu', 'INDEX_ORDER_TYPE')
    # Identity ordinal is dense in raw order. Permutation and stable chronology
    # independently guard duplicate origin ingestion, not packet byte equality.
    require(np.array_equal(index['original_packet_ordinal'], np.arange(1, len(index)+1)), 'RAW_ORDINALS')
    require(np.array_equal(np.sort(order), np.arange(len(index))), 'ORDER_NOT_PERMUTATION')
    tt = index['timestamp_us'][order]
    require(np.all(tt[1:] >= tt[:-1]), 'NONCHRONOLOGICAL_INDEX')
    equal = tt[1:] == tt[:-1]
    require(np.all(order[1:][equal] > order[:-1][equal]), 'UNSTABLE_EQUAL_TIMESTAMP')
    day = tt // 86400000000
    observed = np.unique(day)
    nref = len(observed)*4//5
    require(0 < nref < len(observed), 'STOP_EMPTY_RAW_DATE_ROLE')
    end = int(np.searchsorted(day, observed[nref-1], side='right'))
    def utc_date(d):
        return datetime.fromtimestamp(int(d)*86400, timezone.utc).date().isoformat()
    result = dict(observed_utc_dates=[utc_date(x) for x in observed],
                  ref_dates=[utc_date(x) for x in observed[:nref]],
                  dev_dates=[utc_date(x) for x in observed[nref:]],
                  reference_end_us=int(tt[end-1]), bank_end_frame=end,
                  first_dev_time_us=int(tt[end]), first_dev_frame=end+1,
                  packets=len(index), first_time_us=int(tt[0]), last_time_us=int(tt[-1]))
    require(result['reference_end_us'] < result['first_dev_time_us'], 'ROLE_TIME_OVERLAP')
    if frozen:
        require(all(result[k] == target[k] for k in
                    ('reference_end_us', 'bank_end_frame', 'first_dev_time_us', 'packets')), 'FROZEN_ROLE_BINDING')
    return result


def _block(stream, endian=None):
    head = stream.read(8)
    require(len(head) == 8, 'PCAPNG_BLOCK_HEADER')
    if head[:4] == b'\x0a\x0d\x0d\x0a':
        bom = stream.read(4)
        require(bom in (b'\x4d\x3c\x2b\x1a', b'\x1a\x2b\x3c\x4d'), 'PCAPNG_BOM')
        endian = '<' if bom == b'\x4d\x3c\x2b\x1a' else '>'
        size = struct.unpack(endian+'I', head[4:])[0]
        require(28 <= size <= 16*1024**2 and size % 4 == 0, 'PCAPNG_SECTION_SIZE')
        body = bom + stream.read(size-12)
    else:
        require(endian in ('<', '>'), 'PCAPNG_SECTION_REQUIRED')
        size = struct.unpack(endian+'I', head[4:])[0]
        require(12 <= size <= 16*1024**2 and size % 4 == 0, 'PCAPNG_BLOCK_SIZE')
        body = stream.read(size-8)
    require(len(head+body) == size and struct.unpack(endian+'I', body[-4:])[0] == size, 'PCAPNG_BLOCK_TRAILER')
    return struct.unpack(endian+'I', head[:4])[0], head+body, endian


def chronological_copy(raw, index, order, output, runtime, *, offset_seconds=0):
    """Copy SHB/IDB and every indexed EPB verbatim, preserving all packet bytes."""
    output = Path(output)
    require(not output.exists(), 'NO_OVERWRITE_CHRONOLOGICAL_INPUT')
    h = hashlib.sha256()
    with Path(raw).open('rb') as source, output.open('xb') as dest:
        kind, shb, endian = _block(source)
        require(kind == 0x0a0d0d0a, 'ONE_SECTION_REQUIRED')
        kind, idb, _ = _block(source, endian)
        require(kind == 1, 'SINGLE_INTERFACE_REQUIRED')
        require(struct.unpack_from(endian+'H', idb, 8)[0] == 1, 'ETHERNET_INTERFACE_REQUIRED')
        for value in (shb, idb):
            dest.write(value); h.update(value)
        for frame, row_index in enumerate(order, 1):
            item = index[int(row_index)]
            source.seek(int(item['block_offset']))
            kind, value, _ = _block(source, endian)
            require(kind == 6, 'INDEX_NOT_EPB')
            interface, hi, lo, caplen, wirelen = struct.unpack_from(endian+'IIIII', value, 8)
            require(interface == int(item['interface_id']) == 0 and
                    (hi << 32)+lo+offset_seconds*1000000 == int(item['timestamp_us']) and
                    caplen == int(item['captured_bytes']) and wirelen == int(item['wire_bytes']), 'INDEX_RAW_JOIN')
            dest.write(value); h.update(value)
            if frame % 8192 == 0:
                runtime.update('CHRONOLOGICAL_COPY', raw_packets=frame, total=len(order), traversal='raw block copy')
        runtime.update('CHRONOLOGICAL_COPY', raw_packets=len(order), total=len(order))
    return h.hexdigest()


def create_census(path):
    db = sqlite3.connect(path)
    db.execute('PRAGMA journal_mode=DELETE')
    db.execute('PRAGMA synchronous=FULL')
    db.execute('PRAGMA cache_size=-32768')
    db.execute('PRAGMA temp_store=MEMORY')
    db.execute('CREATE TABLE candidates (uid TEXT PRIMARY KEY, device TEXT, protocol INTEGER, '
               'component_id TEXT, timestamp REAL, frame INTEGER, role TEXT, rank TEXT, body TEXT)')
    return db


def endpoint_row(spec, binding, source_sha, frame, now_us, owner, namespace, event, origin_ordinal):
    role = 'HIST_REF' if frame <= binding['bank_end_frame'] else 'HIST_DEV'
    key = namespace[-1]
    row = dict(uid=digest([source_sha, frame, owner]), frame=frame,
               timestamp=float(Decimal(now_us)/Decimal(1000000)), timestamp_us=now_us,
               source_sha256=source_sha, capture_id=spec['capture_id'], owner=owner,
               partition=spec['partition'], device=spec['device'], display_name=spec['display_name'],
               protocol=event.ip_proto, canonical_key=key, component_id=digest([owner, key]),
               session_id=digest(namespace), label=0, use='REFERENCE' if role == 'HIST_REF' else 'QUERY',
               history_role=role, origin='HIST_B_2016_2017',
               origin_raw_sha256=spec['raw']['sha256'], origin_packet_ordinal=origin_ordinal,
               activity='UNKNOWN', activity_verified=False,
               normality_evidence=spec['normality_evidence'])
    if role == 'HIST_REF':
        row.update(reference_end=float(Decimal(binding['reference_end_us'])/Decimal(1000000)),
                   reference_end_us=binding['reference_end_us'], bank_end_frame=binding['bank_end_frame'])
    return row


def walk_decoded(decoded, spec, binding, index, order, source_sha, contexts, runtime,
                 *, census=None, selected=None, snapshots=None):
    """Both passes append EVERY decoder row, before any endpoint eligibility test."""
    import continuous_input_v3 as inp
    from constrained_onboarding_reference_v2 import reference_descriptor, query_descriptor
    n = 0; matched = 0; legal = Counter(); seen_selected = set()
    selected = {} if selected is None else selected
    for packet in decoded:
        frame = inp.integer(packet['frame.number'])
        now = inp.nanos(packet['frame.time_epoch'])
        require(frame == n+1 and frame <= len(order), 'CONTIGUOUS_LOGICAL_FRAME')
        item = index[int(order[frame-1])]
        require(now == int(item['timestamp_us'])*1000, 'DECODER_INDEX_TIMESTAMP')
        # No role-specific Contexts instance or pre-filter is permitted here.
        owner, namespace, event = contexts.append(packet)
        n = frame
        if contexts.query_allowed and namespace is not None:
            require(owner == spec['owner'], 'UNEXPECTED_HISTORY_OWNER')
            row = endpoint_row(spec, binding, source_sha, frame, now//1000, owner, namespace,
                               event, int(item['original_packet_ordinal']))
            legal[row['history_role']] += 1
            if census is not None:
                rank = hashlib.sha256((SALT+'|'+row['uid']).encode()).hexdigest()
                census.execute('INSERT INTO candidates VALUES (?,?,?,?,?,?,?,?,?)',
                               (row['uid'], row['device'], row['protocol'], row['component_id'],
                                row['timestamp'], row['frame'], row['history_role'], rank,
                                json.dumps(row, ensure_ascii=True, separators=(',', ':'), allow_nan=False)))
            if row['uid'] in selected:
                expected = selected[row['uid']]
                require(digest(row) == digest(expected), 'SELECTED_IDENTITY_REPLAY')
                flow, state, provenance = contexts.states[namespace].snapshot()
                body = dict(flow=flow, state=state, provenance=provenance, source_sha256=source_sha)
                descriptor = reference_descriptor if row['use'] == 'REFERENCE' else query_descriptor
                q14, info = descriptor(body, row)
                snapshots.append(dict(uid=row['uid'], row=row, body=body, q14=q14.tolist(), info=info))
                require(row['uid'] not in seen_selected, 'DUPLICATE_ORIGIN_INGESTION')
                seen_selected.add(row['uid']); matched += 1
        if frame % 8192 == 0:
            if census is not None:
                census.commit()
            runtime.update('ENDPOINT_CENSUS' if census is not None else 'SELECTED_SNAPSHOTS',
                           device=spec['display_name'], raw_packets=frame, total=len(order),
                           decoder_pass=1 if census is not None else 2, legal_endpoints=dict(legal),
                           selected_snapshots=matched)
    require(n == len(order) == binding['packets'], 'INCOMPLETE_HISTORY_STREAM')
    require(seen_selected == set(selected), 'SELECTED_SNAPSHOT_COVERAGE')
    if census is not None:
        census.commit()
    runtime.update('ENDPOINT_CENSUS' if census is not None else 'SELECTED_SNAPSHOTS',
                   device=spec['display_name'], raw_packets=n, total=n,
                   decoder_pass=1 if census is not None else 2, legal_endpoints=dict(legal), selected_snapshots=matched)
    return dict(packets=n, legal_endpoints=dict(legal), selected_snapshots=matched,
                frontend_reasons=dict(contexts.reasons))


def prepare_member(spec, output, old_rows, runtime, tshark):
    """Explicit real-data stage. Callers must authorize execute before entering."""
    import legacy_reference_sample_prepare_v1 as prep
    from .contexts import Contexts
    from legacy_unsw_archival_runtime_v1 import decode, fields
    from .selection import select_candidates
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    runtime.update('INPUT_IDENTITY', device=spec['display_name'])
    raw = pin(spec['raw']); before = (raw.stat().st_size, raw.stat().st_mtime_ns)
    index = np.load(pin(spec['packet_index']), mmap_mode='r', allow_pickle=False)
    order = np.load(pin(spec['chronological_order']), mmap_mode='r', allow_pickle=False)
    binding = role_binding(index, order, spec)
    binding.update(raw_sha256=spec['raw']['sha256'], packet_index_sha256=spec['packet_index']['sha256'],
                   chronological_order_sha256=spec['chronological_order']['sha256'])
    write(output/'ROLE_BINDING.json', binding)
    chron = output/'chronological.pcapng'
    source_sha = chronological_copy(raw, index, order, chron, runtime,
                                     offset_seconds=spec.get('timestamp_offset_seconds', 0))
    # Actual derived object SHA is the source identity, not an invented raw SHA.
    api = prep.old.legacy_runtime()
    version = subprocess.run([str(tshark), '--version'], capture_output=True, text=True, check=True, timeout=30).stdout
    decoder_id = dict(name='tshark', version=version, executable_sha256=sha(tshark),
                      fields=fields(api), unfiltered=True, occurrence='f')
    source_manifest = dict(version=VERSION, capture_id=spec['capture_id'], source_sha256=source_sha,
                           source_kind='BYTE_PRESERVING_CHRONOLOGICAL_PCAPNG',
                           logical_frames='1..N, stable timestamp/original ordinal',
                           raw=spec['raw'], packet_index=spec['packet_index'],
                           chronological_order=spec['chronological_order'], decoder=decoder_id,
                           original_locator='(raw_sha256, original_packet_ordinal)', role_binding=binding)
    write(output/'LOGICAL_INPUT.json', source_manifest)
    dbpath = output/'candidates.sqlite'
    db = create_census(dbpath)
    observations = []
    for pass_id in (1, 2):
        selection = None; selected = None; snapshots = []
        if pass_id == 2:
            selection = select_candidates(dbpath, old_rows, output/'selection', devices=[spec['device']])
            if selection['status'] != 'SELECTED':
                write(output/'PREPARE_RESULT.json', selection)
                return selection
            rr = list(rows(selection['ref_rows']['path'])) + list(rows(selection['dev_rows']['path']))
            selected = {r['uid']: r for r in rr}
            require(len(selected) == len(rr), 'REF_DEV_UID_OVERLAP')
            runtime.update('DETERMINISTIC_SELECTION', device=spec['display_name'],
                           selected_ref=selection['ref_rows']['rows'], selected_dev=selection['dev_rows']['rows'],
                           component_coverage=selection['groups'])
        contexts = Contexts(spec['capture_id'], spec['known_macs'], api[0],
                            required_owners={spec['owner']}, storage_path=output/('contexts_%d.sqlite'%pass_id),
                            resident_contexts=256)
        try:
            with decode(chron, dict(), api, runtime, output/('decoder_pass%d.stderr.log'%pass_id), tshark) as decoded:
                observations.append(walk_decoded(decoded, spec, binding, index, order, source_sha,
                                                contexts, runtime, census=db if pass_id == 1 else None,
                                                selected=selected, snapshots=snapshots))
        finally:
            contexts.close()
        if pass_id == 1:
            db.execute('CREATE INDEX component_time ON candidates(device,role,protocol,component_id,timestamp,rank,uid)')
            db.commit()
            db.close()
        else:
            require(observations[0]['legal_endpoints'] == observations[1]['legal_endpoints'] and
                    observations[0]['frontend_reasons'] == observations[1]['frontend_reasons'], 'CENSUS_REPLAY_CHANGED')
            snapshots.sort(key=lambda x: x['uid'])
            write_rows(output/'selected_snapshots.jsonl.gz', snapshots)
    require(before == (raw.stat().st_size, raw.stat().st_mtime_ns), 'RAW_MUTATED_DURING_PREPARATION')
    receipt = dict(status='PREPARED', version=VERSION, source_sha256=source_sha,
                   selection=selection, role_binding=binding, logical_input_sha256=sha(output/'LOGICAL_INPUT.json'),
                   census_sha256=sha(dbpath), snapshots_sha256=sha(output/'selected_snapshots.jsonl.gz'),
                   observations=observations, raw_packet_copy_traversals=1, raw_integrity_full_reads=1,
                   complete_decoder_traversals=2,
                   input_readout='RECENT_CURRENT_INCLUSIVE', real_E3_forwards=0)
    write(output/'PREPARE_RESULT.json', receipt)
    return receipt
