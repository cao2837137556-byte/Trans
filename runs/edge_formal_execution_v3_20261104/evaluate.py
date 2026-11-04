"""Read-only frozen external scoring, in restartable query chunks.

This module is called only after the worker's bound authorization gate. It
never chooses queries/references, refits thresholds, or changes a saved encoder.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid

import numpy as np

from checkpoint import atomic_json, bind_directory, canonical, fsync_directory, require, sha, write_bytes
from streaming import ROOT, module


class ResultStore:
    def __init__(self, root, binding):
        self.root, self.binding = bind_directory(root, dict(schema='EDGE_RESULT_CHUNKS_V1', identity=binding))

    def load(self, name, uids):
        target = self.root/name
        if not target.exists():
            return None
        manifest = json.loads((target/'MANIFEST.json').read_text(encoding='utf-8'))
        require(manifest['binding_sha256'] == self.binding and manifest['uids'] == uids,
                'RESULT_CHUNK_BINDING_ORDER')
        require(sha(target/'RESULT.npz') == manifest['sha256']
                and (target/'RESULT.npz').stat().st_size == manifest['bytes'], 'RESULT_CHUNK_SHA_SIZE')
        with np.load(target/'RESULT.npz', allow_pickle=False) as saved:
            data = {key: saved[key].copy() for key in saved.files}
        n = len(uids)
        required = dict(raw_scores=(n, 3), support=(n,), knn_distance=(n,),
                        RAW=(n, 4), C5_P3=(n, 4), C5_P1=(n, 4), STANDARD_KNN5=(n, 4))
        require(set(data) == set(required), 'RESULT_CHUNK_KEYS')
        for key, shape in required.items():
            array = data[key]
            require(array.shape == shape, 'RESULT_CHUNK_SHAPE')
            if key in ('RAW', 'C5_P3', 'C5_P1', 'STANDARD_KNN5'):
                require(array.dtype == bool, 'RESULT_CHUNK_BOOLEAN')
            else:
                require(array.dtype == np.float64 and
                        (np.isfinite(array).all() if key != 'knn_distance' else
                         np.all(np.isfinite(array) | np.isnan(array))), 'RESULT_CHUNK_FLOAT')
        return data

    def commit(self, name, uids, arrays):
        target = self.root/name
        require(not target.exists(), 'RESULT_CHUNK_ALREADY_COMMITTED')
        attempt = self.root/('.'+name+'.'+uuid.uuid4().hex)
        attempt.mkdir()
        with (attempt/'RESULT.npz').open('xb') as stream:
            np.savez(stream, **arrays)
            stream.flush()
            os.fsync(stream.fileno())
        payload = attempt/'RESULT.npz'
        write_bytes(attempt/'MANIFEST.json', canonical(dict(binding_sha256=self.binding,
            uids=uids, bytes=payload.stat().st_size, sha256=sha(payload))))
        fsync_directory(attempt)
        os.rename(attempt, target)
        fsync_directory(self.root)
        require(self.load(name, uids) is not None, 'RESULT_COMMIT_READBACK')


class FrozenHeads:
    def __init__(self, spec, normalizer):
        import torch
        import query_tail_core_v2 as heads
        import constrained_onboarding_query_tail_adapter_v2 as adapter
        self.heads, self.norm, self.models = heads, normalizer, []
        design = json.loads((ROOT/spec['heads']['design']['path']).read_text(encoding='utf-8'))
        for seed in (27, 127, 227):
            path = ROOT/spec['heads']['endpoints'][str(seed)]['head.npz']['path']
            adapter._endpoint(path.parent, 'QUERY_TAIL', seed, design, normalizer)
            model = heads.classifier(seed, 782)
            with np.load(path, allow_pickle=False) as saved:
                require(set(saved.files) == set(model.state_dict()), 'FROZEN_HEAD_KEYS')
                model.load_state_dict({key: torch.from_numpy(saved[key].copy()) for key in saved.files})
            model.eval().requires_grad_(False)
            self.models.append(model)

    def scores(self, e3, q14):
        return np.column_stack([self.heads.scores(model, e3, q14,
            np.arange(len(e3)), self.norm, 782) for model in self.models]).astype(np.float64)


def evaluate(store, plan, output, binding, population, pair_limit,
             guard=lambda: None, progress=lambda *a, **k: None):
    """At most 128 query features plus the 4,124-point bank are materialized."""
    sys.path.insert(0, str(ROOT/'repo/ood'))
    import constrained_onboarding_core_v3 as core
    engine = module('_edge_formal_frozen_engine', ROOT/'runs/edge_external_test1_engineering_v1_20261103/preflight/engine.py')
    baseline = module('_edge_formal_knn5', ROOT/'runs/edge_external_test1_engineering_v1_20261103/baselines/knn5.py')
    from reporting import summarise
    freeze, spec, normalizer, pins = engine.frozen_assets()
    calibration_path = ROOT/'runs/edge_external_test1_engineering_v1_20261103/baselines/SOURCE_CALIBRATION.json'
    require(sha(calibration_path) == 'a47221412ee24096a9827ad9cdaf45b63306e3b15afe137c720b99a564deed54', 'KNN_SOURCE_CUTS_PIN')
    calibration = json.loads(calibration_path.read_text(encoding='utf-8'))
    reference_rows, reference_e3, reference_q14, queries, feature_index = [], [], [], [], {}
    for entry in plan:
        chunk = store.load(entry['batch_id'], entry['uids'])
        for i, row in enumerate(chunk['rows']):
            if row['use'] == 'REFERENCE':
                reference_rows.append(row)
                reference_e3.append(chunk['e3'][i].copy())
                reference_q14.append(chunk['q14'][i].copy())
            else:
                queries.append(row)
                feature_index[row['uid']] = entry['batch_id'], i
    require(len(reference_rows) == 4124 and len(queries) == 60000, 'SEALED_BASE_ROLE_COUNTS')
    # Evaluate in encoded-batch order, avoiding a shared-disk random reload for
    # every query. Only small final predictions are reordered for the report.
    order = {'NORMAL': 0, 'HTTP': 1, 'UDP': 2}
    ref_order = sorted(range(len(reference_rows)), key=lambda i: reference_rows[i]['uid'])
    rr = [reference_rows[i] for i in ref_order]
    rz = np.asarray([reference_e3[i] for i in ref_order], dtype=np.float32)
    rq = np.asarray([reference_q14[i] for i in ref_order], dtype=np.float32)
    ref_uids = [r['uid'] for r in rr]
    query_uids = [r['uid'] for r in queries]
    require(not set(ref_uids) & set(query_uids), 'REFERENCE_QUERY_DISJOINT')
    bank = core.ReferenceBank(rr, rz, rq, normalizer, feature_uids=ref_uids, q_uids=ref_uids)
    knn_bank = baseline.KNN5Bank(rr, rz, normalizer, feature_uids=ref_uids)
    heads = FrozenHeads(spec, normalizer)
    target = Path(output)
    target.mkdir(exist_ok=True)
    chunks = ResultStore(target/'chunks', binding)
    predictions = {name: np.empty((len(queries), 4), dtype=bool)
                   for name in ('RAW', 'C5_P3', 'C5_P1', 'STANDARD_KNN5')}
    refs_by_proto = {proto: sum(r['protocol'] == proto for r in rr) for proto in (6, 17)}
    total_pairs = 2*sum(refs_by_proto[r['protocol']] for r in queries)
    require(total_pairs <= pair_limit, 'FORMAL_PAIR_LIMIT')
    new_pairs = reused_rows = 0
    for start in range(0, len(queries), 128):
        guard()
        rows = queries[start:start+128]
        uids = [r['uid'] for r in rows]
        name = 'q%06d' % start
        data = chunks.load(name, uids)
        if data is None:
            z, q = np.empty((len(rows), 768), dtype=np.float32), np.empty((len(rows), 14), dtype=np.float32)
            grouped = {}
            for j, uid in enumerate(uids):
                batch_id, i = feature_index[uid]
                grouped.setdefault(batch_id, []).append((j, i))
            for batch_id, take in grouped.items():
                encoded = store.load(batch_id)
                for j, i in take:
                    z[j], q[j] = encoded['e3'][i], encoded['q14'][i]
            reservation = 2*sum(refs_by_proto[row['protocol']] for row in rows)
            progress('EVALUATE_RESERVED', query_start=start, distance_pairs_this_chunk=reservation)
            support = bank.own(rows, z, q, freeze['calibration']['geometry'], feature_uids=uids, q_uids=uids)['support']
            raw = heads.scores(z, q)
            _, raw_pred = engine.c5(raw, np.zeros(len(rows)), q, freeze)
            corrected, c5_pred = engine.c5(raw, support, q, freeze, p=3)
            _, p1_pred = engine.c5(raw, support, q, freeze, p=1)
            guarded = (q[:, 0] == 1) & (q[:, 2] == 1) & (q[:, 5] == 0)
            require(np.array_equal(corrected[guarded], raw[guarded]) and
                    np.array_equal(corrected[support == 0], raw[support == 0]), 'FROZEN_RAW_FALLBACK_EXACT')
            knn = knn_bank.distances(rows, z, feature_uids=uids)
            knn_pred = baseline.decisions(knn['distance'], raw_pred, calibration['cuts'])
            data = dict(raw_scores=raw, support=support.astype(np.float64),
                        knn_distance=knn['distance'], RAW=raw_pred, C5_P3=c5_pred,
                        C5_P1=p1_pred, STANDARD_KNN5=knn_pred)
            guard()
            chunks.commit(name, uids, data)
            new_pairs += reservation
        else:
            reused_rows += len(rows)
        for method in predictions:
            predictions[method][start:start+len(rows)] = data[method]
        progress('EVALUATE_COMMITTED', completed_queries=start+len(rows),
                 reused_query_rows=reused_rows, distance_pairs_new_reserved=new_pairs,
                 distance_pairs_full_upper=total_pairs)
    report_order = sorted(range(len(queries)), key=lambda i: (order[queries[i]['source_role']], queries[i]['uid']))
    queries = [queries[i] for i in report_order]
    query_uids = [r['uid'] for r in queries]
    predictions = {method: values[report_order] for method, values in predictions.items()}
    report = summarise(queries, predictions, population,
        prediction_uids={method: query_uids for method in predictions},
        seed=20261103, repetitions=2000)
    atomic_json(target/'METRICS.json', report)
    atomic_json(target/'COMPLETE.json', dict(schema='EDGE_FORMAL_EVALUATION_COMPLETE_V1',
        methods=list(predictions), query_rows=len(queries), reference_rows=len(rr),
        ordered_query_uids_sha256=hashlib.sha256(canonical(query_uids)).hexdigest(),
        metrics_sha256=sha(target/'METRICS.json'), pairs_full_upper=total_pairs,
        pairs_new_reserved_this_attempt=new_pairs, queries_reused_this_attempt=reused_rows,
        fixed_asset_pins=pins, training=False))
    return target/'METRICS.json'
