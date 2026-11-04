"""Bounded shape batching over complete-role spools; no scientific selection.

The encoder is injected so transaction/restart tests require neither a model
nor an external score. FrozenBackend is the only model-forward implementation.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import importlib.util
from pathlib import Path
import sys
import time

import numpy as np

from checkpoint import BatchStore, canonical, require

ROOT = Path(__file__).resolve().parents[2]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def make_plan(headers):
    """Exactly the original shape/UID ordering, with physical singleton clones."""
    groups, seen = defaultdict(list), set()
    for header in headers:
        uid = header['uid']
        require(uid not in seen and header['row']['uid'] == uid, 'PLAN_DUPLICATE_OR_ROW_UID')
        seen.add(uid)
        shape = tuple(header['shape'])
        require(len(shape) == 3 and all(type(x) is int for x in shape)
                and shape[0] in (6, 17) and 1 <= shape[2] <= 12
                and shape[1] in tuple(i*(12 if shape[0] == 6 else 6)+1
                                      for i in range(1, 7)), 'PLAN_SHAPE')
        groups[shape].append(uid)
    plan = []
    for shape, uids in sorted(groups.items()):
        uids.sort()
        for start in range(0, len(uids), 16):
            take = uids[start:start+16]
            identity = dict(shape=list(shape), uids=take)
            batch_id = 'b%05d-' % len(plan) + hashlib.sha256(canonical(identity)).hexdigest()[:16]
            plan.append(dict(batch_id=batch_id, shape=list(shape), uids=take,
                             physical_rows=16 if len(take) == 1 else len(take)))
    return plan


def run_encoding(plan, load, backend_factory, root, binding, guard=lambda: None,
                 progress=lambda *a, **k: None, failpoint=None):
    """Committed outputs survive restart; model is loaded only for missing work."""
    store = BatchStore(root, binding)
    backend = None
    reused = new = physical = 0
    timings = []
    require(set(store.records) <= {b['batch_id'] for b in plan}, 'UNEXPECTED_COMMITTED_BATCH')
    for entry in plan:
        guard()
        batch_id, uids = entry['batch_id'], entry['uids']
        if store.has(batch_id, uids):
            reused += len(uids)
            progress('ENCODE_REUSED', batch_id=batch_id, reused_rows=reused, new_rows=new)
            continue
        if backend is None:
            backend = backend_factory()
        # At most sixteen bodies and their tokenized forms are resident here.
        snapshots = [load(uid) for uid in uids]
        require([s['uid'] for s in snapshots] == uids, 'SPOOL_LOAD_ORDER')
        progress('ENCODE_RESERVED', batch_id=batch_id, shape=entry['shape'],
                 logical_rows=len(uids), physical_rows=entry['physical_rows'])
        before = time.monotonic()
        e3, q14, receipt = backend.encode(snapshots, tuple(entry['shape']))
        guard()
        rows = [dict(s['row']) for s in snapshots]
        for row, record in zip(rows, receipt['inputs']):
            require(record['uid'] == row['uid'], 'ENCODER_INPUT_RECEIPT_JOIN')
            row['_input_tensor_sha256'] = record['input_tensor_sha256']
        require(receipt['physical_rows'] == entry['physical_rows'], 'PHYSICAL_BATCH_CONTRACT')
        store.commit(batch_id, uids, e3, q14, rows=rows, failpoint=failpoint)
        new += len(uids)
        physical += entry['physical_rows']
        timings.append(dict(batch_id=batch_id, shape=entry['shape'],
            logical_rows=len(uids), physical_rows=entry['physical_rows'],
            seconds=time.monotonic()-before))
        progress('ENCODE_COMMITTED', batch_id=batch_id, new_rows=new,
                 reused_rows=reused, physical_rows_new=physical)
        del snapshots, e3, q14, rows
    complete = store.finish([(b['batch_id'], b['uids']) for b in plan])
    return store, dict(new_rows=new, reused_rows=reused, physical_rows_new=physical,
                       batches_this_attempt=timings, complete=complete)


class FrozenBackend:
    def __init__(self):
        sys.path.insert(0, str(ROOT/'repo/ood'))
        import torch
        encoder_root = ROOT/'runs/history_normal_reference_keyrepair_v1_20261031'
        sys.path.insert(0, str(encoder_root))
        from hnr.encoding import new_encoder
        import json
        config = json.loads((encoder_root/'config/EXECUTION.json').read_text(encoding='utf-8'))['encoder']
        config['runtime_root'] = str(ROOT/'runs/diagnostics_c5_step2_package_v1_20261025/local_benchmark_v1/runtime')
        config['normalizer'] = str(ROOT/'runs/diagnostics_d1_d2_v1_20261022/assets/heads/run/prepared/normalizer.npz')
        config['runtime_files_manifest']['path'] = str(encoder_root/'config/ENCODER_RUNTIME_FILES.json')
        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)
        torch.use_deterministic_algorithms(True)
        self.encoder, self.identity = new_encoder(config)
        torch.set_num_threads(1)

    def encode(self, entries, expected_shape):
        import continuous_input_v3 as inp
        from continuous_features_v3 import tokenize, verify_batch, tensor_hash
        from constrained_onboarding_reference_v2 import reference_descriptor, query_descriptor
        from hnr.encoding import physical_batch
        embed, _, model, tokenizer, collator = self.encoder
        examples, descriptors = [], []
        for entry in entries:
            row, body = entry['row'], entry['body']
            descriptor = reference_descriptor if row['use'] == 'REFERENCE' else query_descriptor
            q14 = descriptor(body, row)[0]
            require(np.array_equal(q14, np.asarray(entry['q14'], dtype=np.float32)), 'DESCRIPTOR_EXACT')
            example = tokenize(tokenizer, body['flow'])
            inp.verify_tokenized(body['flow'], body['provenance'], example)
            actual_shape = (row['protocol'], max(example['dataset_burst_sizes'])+1,
                            len(example['dataset_burst_sizes']))
            require(actual_shape == expected_shape, 'HEADER_TO_TOKENIZED_SHAPE_PARITY')
            examples.append(example)
            descriptors.append(q14)
        batch = collator(examples)
        verify_batch(examples, batch)
        actual, physical = physical_batch(batch, len(entries), tensor_hash)
        values = embed.core.e3_forward_batches(model, [actual], 'cpu')
        require(values.dtype == np.float32 and values.shape == (physical, 768)
                and np.isfinite(values).all(), 'FROZEN_E3_SCHEMA')
        if len(entries) == 1:
            require(all(v.tobytes() == values[0].tobytes() for v in values),
                    'SINGLETON_CLONES_OUTPUT_BIT_EXACT')
        inputs = [dict(uid=entry['uid'], input_tensor_sha256=tensor_hash(actual, j))
                  for j, entry in enumerate(entries)]
        return (values[:len(entries)].copy(), np.asarray(descriptors, dtype=np.float32),
                dict(physical_rows=physical, inputs=inputs, input_dedup=False))
