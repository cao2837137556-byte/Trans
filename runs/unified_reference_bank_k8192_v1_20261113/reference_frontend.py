"""Frozen RECENT endpoint enumeration for long history and admitted CIC clips."""
from collections import Counter
from contextlib import contextmanager
import csv
from decimal import Decimal
import json
from pathlib import Path
import sqlite3
import subprocess

import numpy as np

from decoder_guard import audit_packet, diagnostic_signature
from frozen_selector import from_census, need
from hnr.common import digest as semantic_digest
from hnr.contexts import Contexts
from hnr.history import chronological_copy, create_census, role_binding, walk_decoded
from runtime_support import TSHARK_SHA, asset, digest, read, write


@contextmanager
def decoded(path, tshark, fields, log, *, limit=None):
    command = [str(tshark), '-n', '-r', str(path), '-T', 'fields', '-E', 'header=y',
               '-E', 'separator=/t', '-E', 'quote=d', '-E', 'occurrence=f']
    if limit is not None:
        command.extend(('-c', str(limit)))
    for field in fields:
        command.extend(('-e', field))
    with log.open('x', encoding='utf-8') as err:
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=err, text=True,
                              encoding='utf-8', errors='strict') as process:
            try:
                reader = csv.DictReader(process.stdout, delimiter='\t', quotechar='"')
                need(reader.fieldnames == fields, 'FROZEN_DECODER_FIELDS')
                def checked():
                    for row in reader:
                        need(None not in row and None not in row.values(), 'DECODER_SCHEMA')
                        yield row
                yield checked()
                need(process.wait(timeout=60) == 0, 'DECODER_EXIT')
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=60)


def schema(api):
    from legacy_unsw_archival_runtime_v1 import fields
    return fields(api)


def admission(spec, binding):
    key = (spec['device'], spec['raw']['sha256'], spec['owner'], spec['capture_id'])
    return key, dict(partition=spec['partition'], reference_end_us=binding['reference_end_us'],
                     bank_end_frame=binding['bank_end_frame'], raw_packet_count=binding['packets'])


def admit_long(spec, folder, tshark, pins, progress, *, prior_probe=None):
    folder.mkdir(parents=True, exist_ok=False)
    index = np.load(spec['packet_index']['path'], mmap_mode='r', allow_pickle=False)
    order = np.load(spec['chronological_order']['path'], mmap_mode='r', allow_pickle=False)
    binding = role_binding(index, order, spec)
    first_primary_us = 1527465600000000  # UTC start of the first admitted 2018 source date
    need(binding['last_time_us'] < first_primary_us, 'HISTORY_PRECEDES_UNSW_2018')
    witness = pins.get('logical')
    known = pins.get('netatmo')
    if known is not None:
        for name, sha in known['files'].items():
            if name in ('LOGICAL_INPUT.json', 'ROLE_BINDING.json', 'decoder_pass1.stderr.log'):
                need(digest(known['path'].parent / name) == sha, 'NETATMO_CHECKPOINT:' + name)
        logical = read(known['path'].parent / 'LOGICAL_INPUT.json')
        known_binding = read(known['path'].parent / 'ROLE_BINDING.json')
        need(all(known_binding[k] == v for k, v in binding.items()) and
             logical['source_sha256'] == witness['source_sha256'], 'NETATMO_LOGICAL_CENSUS_BINDING')
        db = sqlite3.connect(known['path'].resolve().as_uri()+'?mode=ro', uri=True)
        with db:
            need(db.execute('SELECT count(*) FROM physical_origins').fetchone()[0] ==
                 sum(known['counts'].values()), 'NETATMO_CENSUS_PHYSICAL_COUNT')
        db.close()
    frozen_sha = witness['source_sha256'] if witness is not None else None
    old_chron = known['path'].parent / 'chronological.pcapng' if known is not None else None
    if prior_probe is not None:
        old = read(prior_probe/'LOGICAL_INPUT.json')
        old_chron = prior_probe/'chronological.pcapng'
        need(Path(old['chron']) == old_chron and old['role_binding'] == binding and
             old['tshark_sha256'] == TSHARK_SHA and
             all(old[key]['sha256'] == spec[key]['sha256'] for key in
                 ('raw','packet_index','chronological_order')), 'REUSE_CHRONOLOGY_INPUT_BINDING')
        if frozen_sha is None:
            frozen_sha = old['source_sha256']
    if prior_probe is not None and not old_chron.is_file():
        raise FileNotFoundError('PREDECESSOR_CHRONOLOGY_MISSING:' + spec['key'])
    if old_chron is not None and old_chron.is_file():
        chron = old_chron
        source_sha = digest(chron)
    else:
        chron = folder / 'chronological.pcapng'
        source_sha = chronological_copy(spec['raw']['path'], index, order, chron, progress,
                                        offset_seconds=spec.get('timestamp_offset_seconds', 0))
    need(frozen_sha is None or source_sha == frozen_sha, 'FROZEN_LOGICAL_SOURCE:' + spec['key'])
    record = dict(role_binding=binding, source_sha256=source_sha, chron=str(chron),
                  raw=spec['raw'], packet_index=spec['packet_index'],
                  chronological_order=spec['chronological_order'], tshark_sha256=TSHARK_SHA,
                  netatmo_census_reused=known is not None)
    write(folder / 'LOGICAL_INPUT.json', record)
    return binding, index, order, chron, source_sha


def walk_long(spec, folder, material, api, tshark, progress, *,
              selected=None, known=None, prefix=None):
    binding, index, order, chron, source_sha = material
    stop = binding['bank_end_frame'] if prefix is None else min(prefix, binding['bank_end_frame'])
    phase = 'snapshot' if selected is not None else 'census'
    if prefix is not None:
        phase += '_probe'
    log = folder / (phase + '.stderr')
    census_path = folder / (phase + '.sqlite')
    census = create_census(census_path) if selected is None else None
    contexts = Contexts(spec['capture_id'], spec['known_macs'], api[0], required_owners={spec['owner']},
                        storage_path=folder / (phase + '_contexts.sqlite'), resident_contexts=256)
    entries, audited = [], {}
    prior = Counter()
    if known is not None:
        prior = diagnostic_signature((known['path'].parent / 'decoder_pass1.stderr.log').read_bytes(),
                                     packets=binding['packets'])
        prior = Counter({k: v for k, v in prior.items() if k[1] <= stop})
    warn_frames = {frame for _, frame in prior}
    try:
        with Path(spec['raw']['path']).open('rb') as raw, decoded(
                chron, tshark, schema(api), log, limit=stop) as stream:
            def packets():
                for row in stream:
                    frame = int(row['frame.number'])
                    if frame in warn_frames:
                        audited[frame] = audit_packet(row, raw, index[int(order[frame-1])])
                    yield row
            observation = walk_decoded(packets(), spec, dict(binding, packets=stop),
                                       index, order[:stop], source_sha, contexts, progress,
                                       census=census, selected=selected, snapshots=entries)
    finally:
        contexts.close()
        if census is not None:
            census.close()
    stderr = log.read_bytes()
    need((not stderr if known is None else
          diagnostic_signature(stderr, packets=stop) == prior and set(audited) == warn_frames),
         'DECODER_DIAGNOSTIC_DRIFT:' + spec['key'])
    need(set(observation['legal_endpoints']).issubset({'HIST_REF'}), 'HIST_DEV_DECODED')
    if known is not None and prefix is None:
        need(observation['legal_endpoints'] == {'HIST_REF': known['counts']['HIST_REF']},
             'NETATMO_REFERENCE_POPULATION_REPLAY')
    write(folder / (phase + '_receipt.json'),
          dict(observation, stderr_sha256=digest(log), diagnostics_audited=len(audited),
               **({'census': asset(census_path)} if census is not None else {})))
    return (census_path, observation['legal_endpoints']) if census is not None else entries


def iter_long_census(spec, binding, index, order, source_sha, path, counts):
    for row in from_census(path, counts):
        frame = row['frame']
        need(type(frame) is int and 0 < frame <= binding['bank_end_frame'], 'CENSUS_FRAME')
        item = index[int(order[frame-1])]
        need(int(item['original_packet_ordinal']) == row['origin_packet_ordinal'] and
             int(item['timestamp_us']) == row['timestamp_us'] and row['source_sha256'] == source_sha and
             row['uid'] == semantic_digest([source_sha, frame, spec['owner']]) and
             row['component_id'] == semantic_digest([spec['owner'], row['canonical_key']]),
             'CENSUS_PHYSICAL_AND_CAUSAL_JOIN')
        yield row


def short_capture(spec, folder, api, tshark, known_macs):
    import continuous_input_v3 as inp
    from constrained_onboarding_reference_v2 import reference_descriptor

    end = int(Decimal(str(spec['last'])) * 1000000)
    start = int(Decimal(str(spec['first'])) * 1000000)
    need(spec['use'] == 'REFERENCE' and spec['provenance'] == 'normal' and
         end < spec['first_query_us'], 'CIC_NORMAL_REFERENCE_ADMISSION')
    log = folder / (spec['capture_id'] + '.stderr')
    fields = list(dict.fromkeys([f for f in api[2] if f not in ('tcp.payload', 'rtsp.url', 'rtsp.cseq')]
                                + list(inp.FIELDS)))
    context = inp.Contexts(spec['capture_id'], known_macs, api[0], required_owners=[spec['owner']])
    entries = []
    first = last = None
    with decoded(spec['raw']['path'], tshark, fields, log) as stream:
        for packet in stream:
            frame = inp.integer(packet['frame.number'])
            ns = inp.nanos(packet['frame.time_epoch'])
            need(frame == context.frame+1 and ns % 1000 == 0, 'CIC_ORIGINAL_FRAME_AND_CLOCK')
            now = ns//1000
            first = now if first is None else first
            last = now
            owner, namespace, event = context.append(packet)
            if not context.query_allowed:
                continue
            need(owner == spec['owner'] and event.ip_proto in (6, 17) and now <= end, 'CIC_ENDPOINT')
            flow, state, provenance = context.states[namespace].snapshot()
            canonical = namespace[-1]
            row = dict(uid=inp.digest([spec['sha256'], frame, owner]), source_sha256=spec['sha256'],
                capture_id=spec['capture_id'], frame=frame, timestamp=float(Decimal(ns)/10**9),
                timestamp_us=now, timestamp_ns=ns, owner=owner, device=spec['device'],
                partition=spec['partition'], label=0, use='REFERENCE', history_role='HIST_REF',
                protocol=event.ip_proto, canonical_key=canonical, component_id=inp.digest([owner, canonical]),
                session_id=inp.digest(namespace), activity=spec['mode'], activity_verified=True,
                activity_evidence=spec['member_path'], normality_evidence=spec['normality_evidence'],
                reference_end=float(Decimal(end)/10**6), reference_end_us=end,
                bank_end_frame=spec['expected_packets'], origin_raw_sha256=spec['sha256'],
                origin_packet_ordinal=frame, origin='CIC_ADMITTED_NORMAL_REFERENCE')
            body = dict(flow=flow, state=state, provenance=provenance, source_sha256=spec['sha256'])
            q, info = reference_descriptor(body, row)
            # Materialize immediately because the mutable causal state advances on the next row.
            entries.append(json.loads(json.dumps(dict(uid=row['uid'], row=row, body=body,
                                                       q14=q.tolist(), info=info), allow_nan=False)))
    need(context.frame == spec['expected_packets'] and first == start and last == end and
         not log.stat().st_size, 'CIC_CAPTURE_COMPLETENESS')
    binding = dict(reference_end_us=end, bank_end_frame=context.frame, packets=context.frame)
    return entries, admission(spec, binding)
