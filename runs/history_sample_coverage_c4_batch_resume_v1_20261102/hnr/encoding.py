"""Independent history receipt replay with frozen RECENT tokenizer/E3 runtime."""
from collections import defaultdict
import gzip
import hashlib
import json
import os
from pathlib import Path
import tempfile
import uuid

import numpy as np

from .common import VERSION, digest, require, rows, sha


CHECKPOINT_VERSION = 'C4_EXACT_BATCH_CHECKPOINT_V1'
SINGLETON_POLICY = 'B1_TO_16_IDENTICAL_CLONES_KEEP_ONE'


def _sync_directory(path):
    # Windows does not support opening directories for fsync. On the target
    # Linux filesystem both file contents and their directory entries are synced.
    if os.name != 'nt':
        fd = os.open(str(path), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _durable_file(path, writer, *, identical_existing=False):
    """Publish one complete file; scientific I/O failures are always fatal."""
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp-' + uuid.uuid4().hex)
    with temporary.open('xb') as stream:
        writer(stream)
        stream.flush()
        os.fsync(stream.fileno())
    if path.exists():
        require(identical_existing and sha(path) == sha(temporary), 'CHECKPOINT_NO_OVERWRITE:' + path.name)
        temporary.unlink()
    else:
        os.replace(temporary, path)
        _sync_directory(path.parent)


def _durable_json(path, value):
    data = (json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True,
                       separators=(',', ':')) + '\n').encode('utf-8')
    _durable_file(path, lambda stream: stream.write(data))


def _array_hash(array):
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def _example_hash(value):
    """Pin tokenized examples without another collator invocation."""
    def canonical(v):
        if isinstance(v, np.ndarray):
            return dict(array_dtype=str(v.dtype), shape=list(v.shape), sha256=_array_hash(v))
        if isinstance(v, np.generic):
            return v.item()
        if isinstance(v, dict):
            return {k: canonical(v[k]) for k in sorted(v)}
        if isinstance(v, (list, tuple)):
            return [canonical(x) for x in v]
        return v
    return digest(canonical(value))


def _batch_plan(metadata, q14, examples, groups, identity, bindings):
    require(isinstance(identity, dict) and identity and isinstance(bindings, dict) and bindings,
            'CHECKPOINT_MODEL_INPUT_IDENTITY_REQUIRED')
    require(metadata and len({r['uid'] for r in metadata}) == len(metadata) and
            all(isinstance(r['uid'], str) and len(r['uid']) <= 64 for r in metadata), 'CHECKPOINT_UIDS')
    require(q14.shape == (len(metadata), 14) and q14.dtype == np.float32 and
            np.isfinite(q14).all(), 'CHECKPOINT_Q14_SCHEMA')
    require(set(examples) == set(range(len(metadata))), 'CHECKPOINT_EXAMPLE_SLOTS')
    batches = []; covered = []
    for shape, indices in sorted(groups.items()):
        ordered = sorted(indices, key=lambda i: metadata[i]['uid'])
        for start in range(0, len(indices), 16):
            slots = ordered[start:start+16]
            require(all(isinstance(i, int) and 0 <= i < len(metadata) for i in slots), 'CHECKPOINT_SLOT_RANGE')
            uids = [metadata[i]['uid'] for i in slots]
            batches.append(dict(batch=len(batches), shape=list(shape), slots=slots,
                                uids=uids, uid_sha256=digest(uids), logical_rows=len(slots),
                                physical_rows=16 if len(slots) == 1 else len(slots)))
            covered.extend(slots)
    require(sorted(covered) == list(range(len(metadata))), 'CHECKPOINT_EXACT_SLOT_COVERAGE')
    return dict(checkpoint_version=CHECKPOINT_VERSION, version=VERSION,
                singleton_policy=SINGLETON_POLICY, runtime=identity, bindings=bindings,
                metadata_sha256=digest(metadata), q14_sha256=_array_hash(q14),
                examples_sha256=_example_hash([examples[i] for i in range(len(metadata))]),
                batches=batches, rows=len(metadata))


def encode_batches(metadata, q14, examples, groups, output, runtime, *, collator,
                   verify_batch, tensor_hash, forward, encoder_identity, bindings,
                   resume=False, crash_hook=None):
    """Run the unchanged batch plan, committing actual vectors after every batch.

    Resume is opt-in. Legacy ledgers contain no recoverable features and fail
    closed. A batch needs both a finite, exact-schema NPZ and a SHA-linked receipt;
    an ATTEMPT alone is charged again if retried. Checkpoints are validated in
    full before any new forward. The hook is only for synthetic crash tests.
    """
    from .common import read
    output = Path(output)
    plan = _batch_plan(metadata, q14, examples, groups, encoder_identity, bindings)
    plan_sha = digest(plan)
    if output.exists():
        require(resume, 'NO_OVERWRITE_ENCODE')
        require((output/'BATCH_PLAN.json').is_file(), 'NO_DURABLE_BATCH_PLAN_LEGACY_LEDGER_NOT_RECOVERABLE')
        require(read(output/'BATCH_PLAN.json') == plan, 'CHECKPOINT_PLAN_IDENTITY')
        require((output/'batches').is_dir(), 'CHECKPOINT_BATCH_DIRECTORY')
    else:
        output.mkdir(parents=True)
        (output/'batches').mkdir()
        _durable_json(output/'BATCH_PLAN.json', plan)
    ledger = output/'BATCH_LEDGER.jsonl'
    events = list(rows(ledger)) if ledger.exists() else []
    attempts = {}; completed = {}
    for event in events:
        bid = event.get('batch')
        require(isinstance(bid, int) and 0 <= bid < len(plan['batches']), 'CHECKPOINT_LEDGER_BATCH')
        spec = plan['batches'][bid]
        require(event.get('plan_sha256') == plan_sha and
                all(event.get(k) == spec[k] for k in ('shape', 'logical_rows', 'physical_rows', 'uid_sha256')),
                'CHECKPOINT_LEDGER_IDENTITY')
        aid = event.get('attempt_id')
        require(isinstance(aid, str) and aid, 'CHECKPOINT_LEDGER_ATTEMPT_ID')
        if event.get('status') == 'ATTEMPT':
            require(aid not in attempts and bid not in completed, 'CHECKPOINT_LEDGER_ATTEMPT_ORDER')
            attempts[aid] = event
        else:
            require(event.get('status') in ('COMPLETE', 'RECOVERED_COMPLETE') and aid in attempts and
                    attempts[aid]['batch'] == bid and bid not in completed, 'CHECKPOINT_LEDGER_COMPLETION')
            completed[bid] = event
    # A torn ledger is evidence, not permission to erase or truncate it.
    if ledger.exists() and ledger.stat().st_size:
        with ledger.open('rb') as stream:
            stream.seek(-1, os.SEEK_END)
            require(stream.read(1) == b'\n', 'CHECKPOINT_TORN_LEDGER')

    def event_write(value):
        with ledger.open('ab') as stream:
            stream.write((json.dumps(value, sort_keys=True, separators=(',', ':'))+'\n').encode())
            stream.flush(); os.fsync(stream.fileno())
        _sync_directory(output)

    def hook(stage, bid):
        if crash_hook is not None:
            crash_hook(stage, bid)

    def pack(spec):
        ee = [examples[i] for i in spec['slots']]
        batch = collator(ee); verify_batch(ee, batch)
        actual, physical = physical_batch(batch, spec['logical_rows'], tensor_hash)
        require(physical == spec['physical_rows'], 'CHECKPOINT_PHYSICAL_BATCH')
        hashes = [tensor_hash(actual, j) for j in range(physical)]
        require(all(isinstance(x, str) and len(x) == 64 for x in hashes), 'CHECKPOINT_TENSOR_HASH_SCHEMA')
        return actual, hashes

    def paths(bid):
        stem = output/'batches'/('%06d' % bid)
        return stem.with_suffix('.npz'), stem.with_suffix('.json')

    # Unknown committed files cannot silently join a different plan.
    known = {p.name for spec in plan['batches'] for p in paths(spec['batch'])}
    require(all(p.name in known or '.tmp-' in p.name for p in (output/'batches').iterdir()),
            'CHECKPOINT_UNKNOWN_BATCH_FILE')
    e3 = np.empty((len(metadata), 768), dtype=np.float32)
    seen = np.zeros(len(metadata), dtype=bool); receipts = {}; committed = {}

    def accept(spec, values, hashes):
        ix = np.asarray(spec['slots'], dtype=np.int64)
        require(not seen[ix].any(), 'CHECKPOINT_DUPLICATE_SLOT')
        e3[ix] = values[:len(ix)]; seen[ix] = True
        receipts[spec['batch']] = [dict(uid=metadata[index]['uid'], slot=index, batch_id=spec['batch'],
            shape=spec['shape'], actual_tensor_sha256=hashes[j],
            feature_sha256=_array_hash(values[j])) for j, index in enumerate(spec['slots'])]

    def validate_values(values, spec):
        require(isinstance(values, np.ndarray) and values.dtype == np.float32 and
                values.shape == (spec['physical_rows'], 768) and np.isfinite(values).all(), 'RECENT_E3_SCHEMA')
        if spec['logical_rows'] == 1:
            require(all(values[j].tobytes() == values[0].tobytes() for j in range(16)),
                    'CLONE_OUTPUT_EXACT_BYTE_IDENTITY')

    # Validate all durable outputs and their actual input tensors before starting
    # any missing batch. Each committed batch is collated only once on resume.
    recover = []
    for spec in plan['batches']:
        bid = spec['batch']; data_path, receipt_path = paths(bid)
        require(data_path.exists() == receipt_path.exists(), 'CHECKPOINT_ORPHAN_ARRAY_OR_RECEIPT')
        if not receipt_path.exists():
            require(bid not in completed, 'CHECKPOINT_LEDGER_WITHOUT_ARRAYS')
            continue
        receipt = read(receipt_path)
        require(receipt.get('checkpoint_version') == CHECKPOINT_VERSION and
                receipt.get('plan_sha256') == plan_sha and receipt.get('batch_spec') == spec and
                receipt.get('npz_sha256') == sha(data_path), 'CHECKPOINT_RECEIPT_PIN')
        aid = receipt.get('attempt_id')
        require(aid in attempts and attempts[aid]['batch'] == bid, 'CHECKPOINT_RECEIPT_ATTEMPT')
        if bid in completed:
            require(completed[bid]['attempt_id'] == aid and
                    completed[bid].get('receipt_sha256') == sha(receipt_path), 'CHECKPOINT_COMPLETE_RECEIPT_PIN')
        with np.load(data_path, allow_pickle=False) as saved:
            require(set(saved.files) == {'slots', 'uid', 'q14', 'e3_actual', 'tensor_sha256'}, 'CHECKPOINT_ARRAY_FIELDS')
            require(saved['slots'].dtype == np.int64 and
                    np.array_equal(saved['slots'], np.asarray(spec['slots'], dtype=np.int64)) and
                    saved['uid'].dtype == np.dtype('<U64') and
                    np.array_equal(saved['uid'], np.asarray(spec['uids'], dtype='<U64')), 'CHECKPOINT_SLOT_UID_ORDER')
            require(saved['q14'].dtype == np.float32 and
                    saved['q14'].shape == (spec['logical_rows'], 14) and
                    saved['q14'].tobytes() == q14[spec['slots']].tobytes(), 'CHECKPOINT_Q14_PIN')
            values = saved['e3_actual'].copy(); validate_values(values, spec)
            hashes = saved['tensor_sha256'].copy()
            require(hashes.dtype == np.dtype('<U64') and hashes.shape == (spec['physical_rows'],),
                    'CHECKPOINT_TENSOR_ARRAY_SCHEMA')
            _, current_hashes = pack(spec)
            require(hashes.tolist() == current_hashes == receipt.get('actual_tensor_sha256') and
                    attempts[aid].get('actual_tensor_sha256') == current_hashes,
                    'CHECKPOINT_ACTUAL_INPUT_PIN')
            require(receipt.get('feature_sha256') == [_array_hash(v) for v in values], 'CHECKPOINT_FEATURE_PIN')
        accept(spec, values, current_hashes); committed[bid] = receipt
        if bid not in completed:
            recover.append((spec, aid, receipt_path))
    # Recovery only appends evidence; prior ATTEMPT/COMPLETE lines stay intact.
    for spec, aid, receipt_path in recover:
        attempt = attempts[aid]
        event_write(dict(attempt, status='RECOVERED_COMPLETE', receipt_sha256=sha(receipt_path)))
    reused_rows = int(seen.sum()); new_rows = 0; new_physical = 0; new_batches = 0
    physical_positions = sum(plan['batches'][bid]['physical_rows'] for bid in committed)
    if committed:
        runtime.update('HISTORY_E3', completed=reused_rows, total=len(metadata),
                       encoding_batches=len(committed), physical_positions=physical_positions,
                       reused_rows=reused_rows, new_forward_rows=0, singleton_policy=SINGLETON_POLICY)
    for spec in plan['batches']:
        bid = spec['batch']
        if bid in committed:
            continue
        actual, hashes = pack(spec)
        runtime.encoded(spec['logical_rows']); runtime.guard()
        attempt = dict(batch=bid, shape=spec['shape'], logical_rows=spec['logical_rows'],
                       physical_rows=spec['physical_rows'], uid_sha256=spec['uid_sha256'],
                       plan_sha256=plan_sha, attempt_id=uuid.uuid4().hex,
                       actual_tensor_sha256=hashes, status='ATTEMPT')
        event_write(attempt); hook('after_attempt', bid)
        values = forward(actual); validate_values(values, spec)
        data_path, receipt_path = paths(bid)
        _durable_file(data_path, lambda stream: np.savez(stream,
            slots=np.asarray(spec['slots'], dtype=np.int64), uid=np.asarray(spec['uids'], dtype='<U64'),
            q14=q14[spec['slots']], e3_actual=values, tensor_sha256=np.asarray(hashes, dtype='<U64')))
        hook('after_npz', bid)
        receipt = dict(checkpoint_version=CHECKPOINT_VERSION, plan_sha256=plan_sha,
                       batch_spec=spec, attempt_id=attempt['attempt_id'], npz_sha256=sha(data_path),
                       actual_tensor_sha256=hashes, feature_sha256=[_array_hash(v) for v in values])
        _durable_json(receipt_path, receipt); hook('after_receipt', bid)
        event_write(dict(attempt, status='COMPLETE', receipt_sha256=sha(receipt_path)))
        hook('after_complete', bid)
        accept(spec, values, hashes); committed[bid] = receipt
        new_rows += spec['logical_rows']; new_physical += spec['physical_rows']; new_batches += 1
        physical_positions += spec['physical_rows']
        runtime.update('HISTORY_E3', completed=int(seen.sum()), total=len(metadata),
                       encoding_batches=len(committed), physical_positions=physical_positions,
                       reused_rows=reused_rows, new_forward_rows=new_rows, singleton_policy=SINGLETON_POLICY)
    hook('before_merge', None)
    require(seen.all() and len(committed) == len(plan['batches']), 'CHECKPOINT_MISSING_SLOT')
    tensor_receipts = [r for bid in sorted(receipts) for r in receipts[bid]]
    return e3, tensor_receipts, dict(physical_positions=physical_positions, batches=len(committed),
        reused_rows=reused_rows, reused_batches=len(committed)-new_batches,
        new_forward_rows=new_rows, new_forward_physical_positions=new_physical,
        new_forward_batches=new_batches, recovered_commits=len(recover), plan_sha256=plan_sha)


def physical_batch(batch, logical, tensor_hash):
    """Reuse accepted singleton repair: 16 identical physical rows, keep one.

    Logical UID count and bank contents never include clones. Other batches
    keep their original sizes. Input/output clone equality is exact bytes.
    """
    if logical != 1:
        return batch, logical
    prepared = {}
    before = tensor_hash(batch, 0)
    for key, value in batch.items():
        require(hasattr(value, 'shape') and len(value.shape) >= 1 and value.shape[0] == 1
                and hasattr(value, 'repeat'), 'SINGLETON_TENSOR_ONLY')
        prepared[key] = value.repeat((16,) + (1,)*(len(value.shape)-1))
    require(all(tensor_hash(prepared, j) == before for j in range(16)), 'CLONED_INPUT_TENSOR_IDENTITY')
    return prepared, 16


def new_encoder(config):
    from constrained_onboarding_reference_v2 import _pin_runtime_tree, pin
    from .common import read
    from legacy_unsw_archival_runtime_v1 import e3_runtime
    pin(config['normalizer'], config['normalizer_sha256'])
    if 'runtime_files_manifest' in config:
        spec = config['runtime_files_manifest']
        manifest = pin(spec['path'], spec['sha256'])
        root = Path(config['runtime_root']).resolve()
        listed = read(manifest)['files']
        actual = {p.relative_to(root).as_posix() for folder in ('vendor/netFound', 'vendor/netFound-base')
                  for p in (root/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts}
        require(actual == set(listed) and actual, 'EXACT_RUNTIME_VENDOR_TREE')
        require(any(p.startswith('vendor/netFound-base/') and p.endswith(('.safetensors', '.bin'))
                    for p in actual), 'FROZEN_ENCODER_WEIGHTS_REQUIRED')
        for relative, expected in listed.items():
            path = (root/relative).resolve()
            require(path.is_relative_to(root), 'RUNTIME_MANIFEST_ESCAPE')
            pin(path, expected)
        identity = dict(manifest_sha256=spec['sha256'], vendor_files=len(actual))
    else:
        identity = _pin_runtime_tree(config['runtime_root'], config['runtime_manifest_sha256'])
    runtime = e3_runtime(config['runtime_root'])
    return runtime, identity


def encode_member(prepared, output, config, runtime, *, encoder=None, encoder_identity=None,
                  synthetic=False, resume=False):
    """Use role-specific descriptors and independent selection replay, never B2."""
    from constrained_onboarding_reference_v2 import reference_descriptor, query_descriptor
    import continuous_input_v3 as inp
    from continuous_features_v3 import tokenize, verify_batch, tensor_hash
    from .common import read
    from .selection import select_candidates
    prepared, output = Path(prepared), Path(output)
    require(resume or not output.exists(), 'NO_OVERWRITE_ENCODE')
    if output.exists():
        require((output/'BATCH_PLAN.json').is_file(), 'NO_DURABLE_BATCH_PLAN_LEGACY_LEDGER_NOT_RECOVERABLE')
    final_path = output/'ENCODE_RESULT.json'
    final = read(final_path) if final_path.exists() else None
    if final is not None:
        require(final['status'] == ('SYNTHETIC_COMPLETE' if synthetic else 'COMPLETE') and
                final['version'] == VERSION and final['checkpoint_version'] == CHECKPOINT_VERSION,
                'ENCODE_FINAL_STATUS')
        require(all(Path(name).name == name and sha(output/name) == expected
                    for name, expected in final['files'].items()), 'ENCODE_FINAL_FILE_PIN')
    receipt = read(prepared/'PREPARE_RESULT.json')
    require(receipt['version'] == VERSION and receipt['input_readout'] == 'RECENT_CURRENT_INCLUSIVE' and
            receipt['status'] == 'PREPARED' and
            sha(prepared/'selected_snapshots.jsonl.gz') == receipt['snapshots_sha256'] and
            sha(prepared/'candidates.sqlite') == receipt['census_sha256'], 'HISTORY_PREPARATION_PIN')
    require(sha(prepared/'LOGICAL_INPUT.json') == receipt['logical_input_sha256'], 'LOGICAL_SOURCE_MANIFEST_PIN')
    logical = read(prepared/'LOGICAL_INPUT.json')
    require(logical['source_sha256'] == receipt['source_sha256'] and
            logical['source_kind'] == 'BYTE_PRESERVING_CHRONOLOGICAL_PCAPNG', 'ACTUAL_LOGICAL_SOURCE_LINK')
    selected = receipt['selection']
    # Replay the full deterministic census against the same old reference rows.
    # Never overwrite a prior run's prepared/selection_replay. This independent
    # replay is scratch-only; the admitted rows and preparation stay immutable.
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='c4_selection_replay_', dir=output.parent) as scratch:
        replay = select_candidates(prepared/'candidates.sqlite', config['old_rows'], Path(scratch)/'replay',
                                   devices=selected['device_scope'])
        require(replay['status'] == selected['status'] == 'SELECTED', 'SELECTION_REPLAY_STATUS')
        for role in ('ref_rows', 'dev_rows'):
            require(sha(selected[role]['path']) == selected[role]['sha256'] and
                    replay[role]['uid_sha256'] == selected[role]['uid_sha256'] and
                    list(rows(replay[role]['path'])) == list(rows(selected[role]['path'])), 'HISTORY_SELECTION_REPLAY')
    entries = list(rows(prepared/'selected_snapshots.jsonl.gz'))
    metadata = sorted(list(rows(selected['ref_rows']['path'])) + list(rows(selected['dev_rows']['path'])),
                      key=lambda r: r['uid'])
    require([e['uid'] for e in entries] == [r['uid'] for r in metadata] and
            len({r['uid'] for r in metadata}) == len(metadata) > 0, 'HISTORY_UID_SNAPSHOT_JOIN')
    require(encoder is not None or not synthetic, 'SYNTHETIC_ENCODER_REQUIRED')
    if encoder is None:
        encoder, encoder_identity = new_encoder(config)
    embed, _, model, tokenizer, collator = encoder
    groups = defaultdict(list); examples = {}; q14 = np.empty((len(metadata), 14), dtype=np.float32)
    for i, (entry, row) in enumerate(zip(entries, metadata)):
        require(row['source_sha256'] == receipt['source_sha256'] and entry['row'] == row,
                'HISTORY_SNAPSHOT_SOURCE_ROW_LINK')
        descriptor = reference_descriptor if row['use'] == 'REFERENCE' else query_descriptor
        q14[i] = descriptor(entry['body'], row)[0]
        require(np.array_equal(q14[i], np.asarray(entry['q14'], dtype=np.float32)), 'HISTORY_Q14_REPLAY')
        example = tokenize(tokenizer, entry['body']['flow'])
        inp.verify_tokenized(entry['body']['flow'], entry['body']['provenance'], example)
        shape = (row['protocol'], max(example['dataset_burst_sizes'])+1, len(example['dataset_burst_sizes']))
        groups[shape].append(i); examples[i] = example
    bindings = dict(prepared_receipt_sha256=sha(prepared/'PREPARE_RESULT.json'),
                    snapshots_sha256=receipt['snapshots_sha256'], census_sha256=receipt['census_sha256'],
                    logical_input_sha256=receipt['logical_input_sha256'],
                    selection_sha256=digest(selected), synthetic_only=synthetic,
                    input_version=inp.VERSION, input_readout='RECENT_CURRENT_INCLUSIVE')
    e3, tensor_receipts, counters = encode_batches(metadata, q14, examples, groups, output, runtime,
        collator=collator, verify_batch=verify_batch, tensor_hash=tensor_hash,
        forward=lambda actual: embed.core.e3_forward_batches(model, [actual], 'cpu'),
        encoder_identity=encoder_identity, bindings=bindings, resume=resume)

    def write_final_rows(path, values):
        if path.exists():
            require(list(rows(path)) == values, 'ENCODE_FINAL_ROWS_PIN:' + path.name)
            return
        def writer(stream):
            with gzip.GzipFile(filename='', mode='wb', fileobj=stream, mtime=0) as compressed:
                for value in values:
                    compressed.write((json.dumps(value, ensure_ascii=True, allow_nan=False,
                        separators=(',', ':'))+'\n').encode('utf-8'))
        _durable_file(path, writer)
    datasets = {}
    for role, field in (('HIST_REF', 'references'), ('HIST_DEV', 'queries')):
        ii = np.asarray([i for i,r in enumerate(metadata) if r['history_role'] == role], dtype=np.int64)
        rr = [metadata[int(i)] for i in ii]
        # C4 reuses the three existing DEV encodings; saturated REF groups may be empty.
        require(role in ('HIST_REF','HIST_DEV'), 'ENCODED_ROLE')
        write_final_rows(output/(field+'.jsonl.gz'), rr)
        expected = dict(uid=np.asarray([r['uid'] for r in rr], dtype='<U64'), e3=e3[ii], q14=q14[ii])
        array_path = output/(field+'.npz')
        if array_path.exists():
            with np.load(array_path, allow_pickle=False) as saved:
                require(set(saved.files) == set(expected) and all(saved[k].dtype == value.dtype and
                        saved[k].shape == value.shape and saved[k].tobytes() == value.tobytes()
                        for k, value in expected.items()), 'ENCODE_FINAL_ARRAY_PIN:' + field)
        else:
            _durable_file(array_path, lambda stream: np.savez(stream, **expected))
        datasets[role] = dict(rows=rr, e3=e3[ii], q14=q14[ii])
    write_final_rows(output/'tensor_receipts.jsonl.gz', tensor_receipts)
    if final is not None:
        require(final['runtime'] == encoder_identity and final['prepared_receipt_sha256'] ==
                bindings['prepared_receipt_sha256'] and final['batch_counters']['plan_sha256'] ==
                counters['plan_sha256'] and counters['new_forward_rows'] == 0, 'ENCODE_FINAL_IDENTITY')
        return datasets
    _durable_json(final_path, dict(status='SYNTHETIC_COMPLETE' if synthetic else 'COMPLETE',
           version=VERSION, synthetic_only=synthetic, rows=len(metadata), logical_E3_rows=len(metadata),
           physical_positions=counters['physical_positions'], batches=counters['batches'], runtime=encoder_identity,
           singleton_policy=SINGLETON_POLICY, checkpoint_version=CHECKPOINT_VERSION, batch_counters=counters,
           prepared_receipt_sha256=sha(prepared/'PREPARE_RESULT.json'),
           input_version=inp.VERSION, input_readout='RECENT_CURRENT_INCLUSIVE',
           files={name:sha(output/name) for name in ('BATCH_PLAN.json', 'BATCH_LEDGER.jsonl',
                  'references.jsonl.gz', 'references.npz', 'queries.jsonl.gz', 'queries.npz',
                  'tensor_receipts.jsonl.gz')}, model_training=False))
    return datasets


def concatenate(datasets):
    datasets = list(datasets)
    require(datasets, 'EMPTY_DATASETS')
    rr = [r for d in datasets for r in d['rows']]
    require(len({r['uid'] for r in rr}) == len(rr), 'DUPLICATE_DATASET_UID')
    return dict(rows=rr, e3=np.concatenate([d['e3'] for d in datasets]),
                q14=np.concatenate([d['q14'] for d in datasets]))
