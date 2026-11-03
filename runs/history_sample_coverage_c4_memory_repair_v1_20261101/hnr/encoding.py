"""Independent history receipt replay with frozen RECENT tokenizer/E3 runtime."""
from collections import defaultdict
import hashlib
from pathlib import Path

import numpy as np

from .common import VERSION, digest, require, rows, sha, write, write_rows


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
                  synthetic=False):
    """Use role-specific descriptors and independent selection replay, never B2."""
    from constrained_onboarding_reference_v2 import reference_descriptor, query_descriptor
    import continuous_input_v3 as inp
    from continuous_features_v3 import tokenize, verify_batch, tensor_hash
    from .common import read
    from .selection import select_candidates
    prepared, output = Path(prepared), Path(output)
    require(not output.exists(), 'NO_OVERWRITE_ENCODE')
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
    replay = select_candidates(prepared/'candidates.sqlite', config['old_rows'], prepared/'selection_replay',
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
    output.mkdir(parents=True)
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
    e3 = np.empty((len(metadata), 768), dtype=np.float32)
    tensor_receipts = []; physical_positions = 0; batch_id = 0
    ledger = output/'BATCH_LEDGER.jsonl'
    with ledger.open('x', encoding='utf-8') as stream:
        import json
        for shape, indices in sorted(groups.items()):
            ordered = sorted(indices, key=lambda i: metadata[i]['uid'])
            for start in range(0, len(indices), 16):
                ix = ordered[start:start+16]
                examples_batch = [examples[i] for i in ix]
                batch = collator(examples_batch); verify_batch(examples_batch, batch)
                actual, physical = physical_batch(batch, len(ix), tensor_hash)
                # Reserve real work before the forward; no retry on errors.
                runtime.encoded(len(ix)); runtime.guard()
                attempt = dict(batch=batch_id, shape=list(shape), logical_rows=len(ix), physical_rows=physical,
                               uid_sha256=digest([metadata[i]['uid'] for i in ix]), status='ATTEMPT')
                stream.write(json.dumps(attempt)+'\n'); stream.flush()
                values = embed.core.e3_forward_batches(model, [actual], 'cpu')
                require(isinstance(values, np.ndarray) and values.shape == (physical, 768) and
                        values.dtype == np.float32 and np.isfinite(values).all(), 'RECENT_E3_SCHEMA')
                if len(ix) == 1:
                    require(all(values[j].tobytes() == values[0].tobytes() for j in range(16)), 'CLONE_OUTPUT_EXACT_BYTE_IDENTITY')
                for j, index in enumerate(ix):
                    e3[index] = values[j]
                    tensor_receipts.append(dict(uid=metadata[index]['uid'], slot=index, batch_id=batch_id,
                                                shape=list(shape), actual_tensor_sha256=tensor_hash(actual, j),
                                                feature_sha256=hashlib.sha256(values[j].tobytes()).hexdigest()))
                physical_positions += physical; batch_id += 1
                stream.write(json.dumps(dict(attempt, status='COMPLETE'))+'\n'); stream.flush()
                runtime.update('HISTORY_E3', completed=len(tensor_receipts), total=len(metadata),
                               encoding_batches=batch_id, physical_positions=physical_positions,
                               singleton_policy='B1_TO_16_IDENTICAL_CLONES_KEEP_ONE')
    datasets = {}
    for role, field in (('HIST_REF', 'references'), ('HIST_DEV', 'queries')):
        ii = np.asarray([i for i,r in enumerate(metadata) if r['history_role'] == role], dtype=np.int64)
        rr = [metadata[int(i)] for i in ii]
        # C4 reuses the three existing DEV encodings; saturated REF groups may be empty.
        require(role in ('HIST_REF','HIST_DEV'), 'ENCODED_ROLE')
        write_rows(output/(field+'.jsonl.gz'), rr)
        with (output/(field+'.npz')).open('xb') as stream:
            np.savez(stream, uid=np.asarray([r['uid'] for r in rr], dtype='<U64'), e3=e3[ii], q14=q14[ii])
        datasets[role] = dict(rows=rr, e3=e3[ii], q14=q14[ii])
    write_rows(output/'tensor_receipts.jsonl.gz', tensor_receipts)
    write(output/'ENCODE_RESULT.json', dict(status='SYNTHETIC_COMPLETE' if synthetic else 'COMPLETE',
           version=VERSION, synthetic_only=synthetic, rows=len(metadata), logical_E3_rows=len(metadata),
           physical_positions=physical_positions, batches=batch_id, runtime=encoder_identity,
           singleton_policy='B1_TO_16_IDENTICAL_CLONES_KEEP_ONE',
           prepared_receipt_sha256=sha(prepared/'PREPARE_RESULT.json'),
           input_version=inp.VERSION, input_readout='RECENT_CURRENT_INCLUSIVE',
           files={p.name:sha(p) for p in output.iterdir() if p.is_file()}, model_training=False))
    return datasets


def concatenate(datasets):
    datasets = list(datasets)
    require(datasets, 'EMPTY_DATASETS')
    rr = [r for d in datasets for r in d['rows']]
    require(len({r['uid'] for r in rr}) == len(rr), 'DUPLICATE_DATASET_UID')
    return dict(rows=rr, e3=np.concatenate([d['e3'] for d in datasets]),
                q14=np.concatenate([d['q14'] for d in datasets]))
