"""One bounded raw preparation and one immutable N3 inference; explicit gate only."""
from __future__ import annotations

import csv
import io
import json
import os
import struct
import subprocess
import threading
import zipfile
from pathlib import Path

import numpy as np
import torch
import issue27frontend_f5_unified_student_v1 as f5
import issue27frontend_f0_zero_training_semantics_v1 as engine
import issue27frontend_f0_zero_training_semantics_real_v1 as zt
import issue27frontend_f1_d1_train_v1 as f1
import issue27frontend_f3_conflict_field_sufficiency_v1 as f3
import issue27frontend_f3_full_fit_l1_identifiability_v1 as f3b
import issue27frontend_f4_fieldwise_input_v1 as f4
import issue27frontend_inheritance_n3_runner_v1 as n3
import issue27frontend_inheritance_outer_support_v1 as s
import issue27frontend_inheritance_outer_metadata_v1 as meta


def decoder_rows(tshark, identity, limit, fields, check=lambda: None):
    """Same frozen TShark arguments/normalization; bounded pipes, owned cleanup."""
    archive, process, producer = None, None, None
    errors, stderr_bytes = [], [0]
    kind = identity['dataset_kind']
    s.require(kind in ('direct_pcap', 'gotham_zip') and limit > 0, 'DECODER_SCOPE')
    zipped = kind == 'gotham_zip'
    try:
        if zipped:
            archive = zipfile.ZipFile(identity['container_path'])
            info = archive.getinfo(identity['raw_source_path'])
            s.require(info.file_size == int(identity['member_uncompressed_bytes_if_archive'])
                      and '%08x' % info.CRC == identity['member_crc32_if_archive'].lower(), 'ZIP_MEMBER_IDENTITY')
        process = subprocess.Popen(f3.tshark_command(Path(tshark), '-' if zipped else identity['container_path'], limit, fields),
            stdin=subprocess.PIPE if zipped else subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
        def drain():
            while True:
                chunk = process.stderr.read(4096)
                if not chunk:
                    break
                stderr_bytes[0] += len(chunk)
                if stderr_bytes[0] > 65536:
                    errors.append('DECODER_STDERR_CAP'); process.kill(); break
        stderr_thread = threading.Thread(target=drain, daemon=True); stderr_thread.start()
        if zipped:
            def feed():
                try:
                    with archive.open(identity['raw_source_path']) as stream:
                        while True:
                            chunk = stream.read(65536)
                            if not chunk:
                                break
                            process.stdin.write(chunk)
                except BrokenPipeError:
                    pass
                except Exception:
                    errors.append('ARCHIVE_FEED')
                finally:
                    try: process.stdin.close()
                    except BrokenPipeError: pass
            producer = threading.Thread(target=feed, daemon=True); producer.start()
        def lines():
            while True:
                check()
                line = process.stdout.readline(65537)
                if not line:
                    break
                s.require(len(line) <= 65536, 'DECODER_LINE_CAP')
                yield line.decode('utf-8', errors='strict')
        reader = csv.DictReader(lines(), delimiter='\t', quotechar='"', strict=True)
        s.require(reader.fieldnames == fields, 'DECODER_HEADER')
        count = 0
        for row in reader:
            s.require(count < limit and None not in row, 'DECODER_CUTOFF_OR_WIDTH')
            normalized = {k: f3.normalize_tshark_cell(row[k]) for k in fields}
            normalized['frame.number'] = f3.normalize_reset_frame_number(normalized['frame.number'], count)
            count += 1
            yield normalized
        s.require(count == limit, 'DECODER_SHORT_READ')
        s.require(process.wait(timeout=10) == 0, 'DECODER_EXIT')
        stderr_thread.join(timeout=2)
        if producer is not None:
            producer.join(timeout=2)
        s.require(not errors and not stderr_thread.is_alive() and (producer is None or not producer.is_alive()),
                  'DECODER_FEED_OR_STDERR_STOP')
    finally:
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    try: stream.close()
                    except (OSError, ValueError): pass
        if producer is not None:
            producer.join(timeout=2)
        if archive is not None:
            archive.close()


def merge_semantics(contexts, semantic, l0):
    expected = {t['uid']: (c, t) for c in contexts for t in c['targets']}
    s.require(len(semantic) == len(expected) and len({r['uid'] for r in semantic}) == len(expected), 'SEMANTIC_UID_COUNT')
    by_context, target_receipts = {}, []
    for row in semantic:
        s.require(row['uid'] in expected, 'SEMANTIC_UNKNOWN_UID')
        c, t = expected[row['uid']]
        length = t['event'] + 1
        s.require(row['scope'] == 'outer_internal_val' and row['context_key'] == c['key']
                  and row['source_group'] == c['source'] and row['event_index'] == t['event'], 'SEMANTIC_ATTACHMENT')
        s.require(row['l0_signatures'] == l0[c['key']][:length]
                  and len(row['l1_signatures']) == length, 'L0_PREFIX_IDENTITY')
        old = by_context.get(c['key'])
        if old is None or len(old) < length:
            by_context[c['key']] = row['l1_signatures']
    values, payload, cursor = [], bytearray(), 0
    for c in contexts:
        signatures = by_context[c['key']]
        s.require(len(signatures) == c['length'], 'LONGEST_PREFIX')
        for row in semantic:
            if row['context_key'] == c['key']:
                s.require(signatures[:row['event_index']+1] == row['l1_signatures'], 'NESTED_L1_PREFIX')
        x = f4.encode_context(signatures)
        raw = np.ascontiguousarray(x, dtype='<f4').tobytes()
        s.require(np.isfinite(x).all() and x.shape == (c['length'], 131), 'F4_SHAPE_FINITE')
        values.append({**c, 'x': torch.from_numpy(x), 'byte_offset': cursor})
        for t in c['targets']:
            target_receipts.append({'uid': t['uid'], 'context': c['key'], 'event': t['event'],
                'feature_prefix_sha256': s.digest(f4.prefix_bytes(x, t['event'])),
                'l0_prefix_sha256': f3b.sha256_value(l0[c['key']][:t['event']+1]),
                'l1_prefix_sha256': f3b.sha256_value(signatures[:t['event']+1])})
        payload.extend(raw); cursor += len(raw)
    return values, bytes(payload), target_receipts


def prepare(metadata, budget, writer, progress):
    # Raw identity hashing is opaque byte access; decoding is limited to five selected members.
    seen = set()
    for member in metadata['members']:
        identity = member['identity']; path = Path(identity['container_path'])
        s.require(identity['is_report'].lower() == identity['is_final'].lower() == 'false', 'FORBIDDEN_MEMBER')
        if str(path) not in seen:
            s.require(path.stat().st_size == int(identity['container_bytes']), 'RAW_CONTAINER_SIZE')
            s.require(s.sha_file(path, budget.check) == identity['container_sha256'], 'RAW_CONTAINER_HASH')
            budget.charge(raw_identity_bytes=path.stat().st_size, raw_identity_files=1)
            seen.add(str(path))
    ts = metadata['tshark_identity']
    budget.charge(decoder_version_calls=1)
    executable = Path(ts['executable_path'])
    version = subprocess.run([str(executable), '--version'], check=True, capture_output=True,
        text=True, encoding='utf-8', errors='replace', creationflags=subprocess.CREATE_NO_WINDOW).stdout.strip()
    observed = {'executable_path': str(executable.resolve()), 'executable_bytes': executable.stat().st_size,
        'executable_sha256': s.sha_file(executable), 'version_output': version,
        'version_output_sha256': s.digest(version.encode('utf-8'))}
    s.require(observed == ts, 'DECODER_RUNTIME_IDENTITY')
    fields = list(zt.TSHARK_FIELDS) + [k for k in ('tcp.flags', 'tcp.len', 'udp.length') if k not in zt.TSHARK_FIELDS]
    rows, member_receipts = [], []
    for index, member in enumerate(metadata['members']):
        budget.charge(decoder_calls=1)
        targets = {r['position']: r for r in member['targets']}
        identity = member['identity']
        def decoded():
            for position, raw in enumerate(decoder_rows(ts['executable_path'], identity, member['packets'], fields, budget.check)):
                budget.charge(raw_packets=1)
                target = targets.get(position)
                event = zt.raw_to_event(engine, raw, identity['source_group'], identity['raw_source_path'], position,
                                        None if target is None else target['uid'])
                if position % 2000 == 0:
                    progress('PREPARING_INPUTS', packets=budget.counts['raw_packets'], packet_total=metadata['raw_packets'],
                             members_complete=index, members_total=5)
                yield raw, event
        source = decoded()
        try:
            semantic, lifecycle = f3b.replay_member_once(engine, zt, f1, f3, source, targets, member['maximum'])
            s.require(next(source, None) is None, 'DECODER_NOT_EXHAUSTED')
        finally:
            source.close()
        s.require(lifecycle['packets'] == member['packets'] and lifecycle['targets'] == len(targets), 'MEMBER_COUNTS')
        rows.extend(semantic)
        budget.charge(members=1)
        member_receipts.append({'member': identity['raw_source_path'], 'maximum': member['maximum'], **lifecycle})
        progress('PREPARING_INPUTS', packets=budget.counts['raw_packets'], packet_total=metadata['raw_packets'],
                 members_complete=index + 1, members_total=5)
    access = {}
    corpus = meta.corpus(s.read_pinned(s.ROOT, meta.CORPUS, meta.PINS[meta.CORPUS]), access, True, budget.check)
    l0 = {c['key']: c['signatures'] for c in corpus if c['split'] == 'internal_val'}
    values, payload, receipts = merge_semantics(metadata['contexts'], rows, l0)
    s.require(len(payload) == metadata['feature_bytes'], 'PREPARED_BYTES')
    budget.charge(prepared_events=sum(c['length'] for c in values))
    writer.write('outer_features.f32le', payload)
    writer.json('input_target_receipts.json', receipts)
    writer.json('prepared_input_receipt.json', {'status': 'INPUT_PREPARED', 'members': member_receipts,
        'targets': len(receipts), 'contexts': len(values), 'events': metadata['events'],
        'features_sha256': s.digest(payload), 'feature_bytes': len(payload), 'L0_prefix_mismatches': 0,
        'numeric_access': access, 'archive_read_ahead': 'selected members only; 64 KiB feed chunks',
        'whole_container_identity_hashing': True})
    return values


def canonical_pass(model, contexts, budget, progress=lambda *a, **k: None):
    s.require([c['key'] for c in contexts] == sorted({c['key'] for c in contexts}), 'FORWARD_ORDER')
    s.require(all(c['split'] == 'internal_val' and tuple(c['x'].shape) == (c['length'], 131)
                  for c in contexts), 'FORWARD_SCOPE')
    predictions = {}
    model.eval(); budget.charge(passes=1)
    with torch.no_grad():
        for start in range(0, len(contexts), 32):
            batch = contexts[start:start+32]
            budget.charge(batches=1, contexts=len(batch), targets=sum(len(c['targets']) for c in batch),
                          events=sum(c['length'] for c in batch), padded_slots=len(batch) * max(c['length'] for c in batch))
            logits, _, _ = model([c['x'] for c in batch], [c['key'] for c in batch])
            s.require(len(logits) == len(batch), 'FORWARD_CONTEXTS')
            for c, q in zip(batch, logits):
                s.require(c['split'] == 'internal_val' and q.dtype == torch.float32
                          and q.shape == (c['length'],) and bool(torch.isfinite(q).all()), 'FORWARD_SHAPE_FINITE')
                for t in c['targets']:
                    s.require(t['uid'] not in predictions, 'FORWARD_DUPLICATE_UID')
                    predictions[t['uid']] = float(q[t['event']])
            progress('EVALUATING', targets_complete=len(predictions), targets_total=4400,
                     batches_complete=budget.counts['batches'], batches_total=112)
    return predictions


def worker(output, config, started):
    budget = s.base.Budget(caps=config['caps'], start=started)
    writer = s.Writer(output, budget)
    audit = {'optimizer_steps': 0, 'backward_steps': 0, 'LP_calls': 0, 'teacher_forwards': 0,
             'historical_model_replays': 0, 'retries': 0}
    verdict = {'status': 'INPUT_OR_EXECUTION_STOP', 'reason': 'UNFINISHED'}
    def progress(phase, **counts):
        s.atomic_json(output / 'progress.json', {'status': phase, 'updated_unix': __import__('time').time(), **counts})
    try:
        runtime = n3.configure_runtime()
        writer.json('runtime_receipt.json', runtime)
        metadata = json.loads(s.read_pinned(s.ROOT, s.METADATA + '/qualified_metadata.json', config['metadata_sha256']))
        s.validate_population(metadata['contexts'])
        progress('PREPARING_INPUTS', packets=0, packet_total=metadata['raw_packets'])
        loaded = prepare(metadata, budget, writer, progress)
        model_pins = config['model_inputs']
        f5root = s.base.F5
        identities = json.loads(s.read_pinned(s.ROOT, f5root + '/preflight/identities.json', model_pins[f5root + '/preflight/identities.json']))
        terminal = json.loads(s.read_pinned(s.ROOT, f5root + '/training/terminal.json', model_pins[f5root + '/training/terminal.json']))
        receipt = json.loads(s.read_pinned(s.ROOT, s.base.CHECKPOINT + '.receipt.json', model_pins[s.base.CHECKPOINT + '.receipt.json']))
        s.require(receipt['sha256'] == model_pins[s.base.CHECKPOINT] and receipt['identities'] == identities, 'CHECKPOINT_RECEIPT')
        state, _ = n3.restricted_checkpoint(s.read_pinned(s.ROOT, s.base.CHECKPOINT, model_pins[s.base.CHECKPOINT], 1712912),
                        model_pins[s.base.CHECKPOINT], identities, terminal, audit, budget)
        head_path = config['head_path']
        model, before = n3.assemble(state, s.read_pinned(s.ROOT, head_path, config['assembly']['head_float32_le_sha256'], 260),
                                   config['assembly'], budget)
        s.require(before['assembled_state'] == config['candidate_state_sha256'], 'N3_CANDIDATE_IDENTITY')
        writer.json('candidate_before.json', before)
        del state
        predictions = canonical_pass(model, loaded, budget, progress)
        after = f5.tensor_hash(model.state_dict())
        s.require(after == before['assembled_state'], 'CANDIDATE_CHANGED')
        writer.json('candidate_after.json', {'assembled_state': after})
        result, rows = s.measurements(metadata['contexts'], predictions)
        s.require(all(budget.counts.get(k, 0) == value for k, value in config['expected_actions'].items()), 'ACTION_COUNTS')
        writer.json('all_target_predictions.json', rows)
        writer.json('comparison.json', result)
        writer.json('access_receipt.json', audit)
        verdict = {k: result[k] for k in ('status', 'complete', 'targets', 'contexts', 'A_retention', 'B_utility')}
        verdict.update(s.CLAIMS)
        budget.check()
    except Exception as exc:
        verdict = {'status': 'INPUT_OR_EXECUTION_STOP', 'reason': str(exc) if isinstance(exc, s.Stop)
                   else 'WORKER_' + type(exc).__name__, **s.CLAIMS}
    s.atomic_json(output / 'worker_terminal.json', {'verdict': verdict, 'resource': budget.receipt(),
                  'access': audit, 'output_hashes': writer.members})
    return verdict
