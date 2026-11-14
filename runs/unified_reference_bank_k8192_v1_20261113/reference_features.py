"""Build features for sealed reference UIDs using the accepted frontend."""
from collections import defaultdict
from pathlib import Path

import numpy as np

from frozen_selector import need, physical as physical_identity, verify_snapshot_row
from hnr.encoding import _array_hash, encode_batches, new_encoder
from runtime_support import HERE, asset, digest, read, write


def encoder_config(store):
    pin = store.get('history_runtime_manifest')
    contract = read(HERE / 'REFERENCE_SOURCES.json')
    root = store.project
    roots = [root / relative for relative in contract['encoder_runtime_locations']]
    for path in contract['encoder_execution_paths']:
        config = root / path
        if config.is_file():
            candidate = Path(read(config)['encoder']['runtime_root']).resolve()
            if candidate.is_relative_to(root):
                roots.append(candidate)
    for runtime in dict.fromkeys(roots):
        if (runtime / 'vendor/netFound-base/model.safetensors').is_file() and (
                runtime / 'vendor/netFound/src').is_dir():
            return dict(runtime_root=str(runtime), normalizer=str(store.get('e3_normalizer')),
                        normalizer_sha256=store.checked['e3_normalizer']['sha256'],
                        runtime_files_manifest=dict(path=str(pin), sha256=digest(pin)))
    raise FileNotFoundError('NO_PINNED_ENCODER_RUNTIME_TREE')


def caches(store, pool, cfg):
    from reference_assets import context, pack
    from common_round1 import read_rows

    old_rows = []
    encoded = {}
    feature_map = {}
    for entry in cfg['history_packs'][pool]:
        rows, z, q = pack(store.get(entry['rows']), store.get(entry['arrays']))
        for i, row in enumerate(rows):
            need(row['uid'] not in encoded, 'DUPLICATE_CACHED_REFERENCE')
            encoded[row['uid']] = (row, z[i], q[i], entry['rows'])
            if not entry.get('device') or row['device'] == entry['device']:
                old_rows.append(row)
    old_context = context(store.get(pool+':history_context'), old_rows)
    for row, x in zip(old_rows, old_context):
        feature_map[row['uid']] = x
    tensor_pins = read(HERE / 'CACHE_TENSOR_PINS.json')
    receipts = {}
    for entry in cfg['history_packs'][pool]:
        spec = tensor_pins.get(entry['rows'])
        if spec is None:
            continue
        path = HERE / spec['path'] if spec.get('bundled') else store.project / spec['path']
        if not path.is_file():
            # An old vector without input proof is encoded from the new legal snapshot.
            continue
        need(digest(path) == spec['sha256'], 'CACHED_TENSOR_RECEIPT_PIN')
        for row in read_rows(path):
            if row['uid'] in encoded and encoded[row['uid']][-1] == entry['rows']:
                need(row['uid'] not in receipts, 'DUPLICATE_CACHED_TENSOR_RECEIPT')
                receipts[row['uid']] = row
    return encoded, feature_map, receipts


def source_identity_equal(old, new):
    fields = ('uid', 'source_sha256', 'capture_id', 'frame', 'owner', 'timestamp',
              'device', 'partition', 'protocol', 'component_id', 'session_id')
    if not all(old.get(name) == new.get(name) for name in fields):
        return False
    if 'origin_raw_sha256' in old:
        return physical_identity(old) == physical_identity(new)
    return (old['source_sha256'], old['frame'], old['owner']) == physical_identity(new)


def materialize(rows, entries, cached, contexts, tensor_receipts, encoder, identity, progress, output,
                *, require_new=False, selection_sha=None):
    import continuous_input_v3 as inp
    from continuous_features_v3 import tokenize, verify_batch, tensor_hash
    from constrained_onboarding_reference_v2 import reference_descriptor

    embed, _, model, tokenizer, collator = encoder
    output.mkdir(parents=True, exist_ok=False)
    n = len(rows)
    e3 = np.empty((n, 768), dtype=np.float32)
    q14 = np.empty((n, 14), dtype=np.float32)
    missing, examples, groups, reused = [], {}, defaultdict(list), []
    for i, (row, entry) in enumerate(zip(rows, entries)):
        verify_snapshot_row(row, entry)
        q = reference_descriptor(entry['body'], row)[0]
        need(np.array_equal(q, np.asarray(entry['q14'], dtype=np.float32)), 'REFERENCE_Q14_REPLAY')
        q14[i] = q
        example = tokenize(tokenizer, entry['body']['flow'])
        inp.verify_tokenized(entry['body']['flow'], entry['body']['provenance'], example)
        before = cached.get(row['uid'])
        receipt = tensor_receipts.get(row['uid'])
        same = before is not None and source_identity_equal(before[0], row)
        shape = (row['protocol'], max(example['dataset_burst_sizes'])+1, len(example['dataset_burst_sizes']))
        if same and not require_new and receipt is not None and np.array_equal(before[2], q):
            batch = collator([example])
            verify_batch([example], batch)
            expected_tensor = receipt.get('actual_tensor_sha256', receipt.get('tensor_sha256'))
            if list(shape) == receipt['shape'] and tensor_hash(batch, 0) == expected_tensor:
                need(_array_hash(before[1]) == receipt['feature_sha256'], 'CACHED_E3_BYTES_CHANGED')
                e3[i] = before[1]
                reused.append(row['uid'])
                continue
        slot = len(missing)
        missing.append(i)
        examples[slot] = example
        groups[shape].append(slot)
    need(len(entries) == n == len(reused)+len(missing) and n > 0, 'SNAPSHOT_COVERAGE')
    if missing:
        arr, _, counters = encode_batches([rows[i] for i in missing], q14[missing], examples, groups,
            output / 'encoding', progress, collator=collator, verify_batch=verify_batch,
            tensor_hash=tensor_hash, forward=lambda batch: embed.core.e3_forward_batches(model, [batch], 'cpu'),
            encoder_identity=identity, bindings=dict(selection_sha256=selection_sha,
                input_version=inp.VERSION, input_readout='RECENT_CURRENT_INCLUSIVE'))
        e3[missing] = arr
    else:
        counters = {'new_forward_rows': 0}
    need(not require_new or len(missing) > 0, 'NO_REAL_E3_PREFLIGHT')
    need(np.isfinite(e3).all() and np.isfinite(q14).all() and contexts.shape == (n, 8) and
         np.isfinite(contexts).all(), 'CANDIDATE_FEATURE_SCHEMA')
    arrays = output / 'REFERENCES.npz'
    with arrays.open('xb') as stream:
        np.savez(stream, uid=np.asarray([r['uid'] for r in rows], dtype='<U64'), e3=e3,
                 q14=q14, context=contexts)
    write(output / 'FEATURE_RECEIPT.json', dict(arrays=asset(arrays), rows=n,
        cached_e3=len(reused), newly_encoded=len(missing), batch_counters=counters,
        runtime=identity, input_version=inp.VERSION))
    return e3, q14, contexts
