"""Describe saved B normal errors and weights; no scoring or model changes."""
import gzip
import hashlib
import importlib.util
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
C3 = ROOT / 'runs/history_normal_reference_c3_progress_repair_v1_20261101'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assets = ROOT / 'runs/history_normal_reference_keyrepair_v1_20261031/config/ASSETS.json'
    spec = read(assets)['pools']['UNSW_DEV']
    rows_path = ROOT / spec['query']['rows']['path']
    saved_path = C3 / 'output/ab/UNSW_DEV/DECISIONS.npz'
    result_path = C3 / 'output/RESULT.json'
    metrics_path = ROOT / 'runs/dense_reference_ab_stage_candidate_v1_20261028/src/metrics.py'
    inputs = {p.relative_to(ROOT).as_posix(): sha(p) for p in (assets, rows_path, saved_path, result_path, metrics_path)}
    assert inputs[rows_path.relative_to(ROOT).as_posix()] == spec['query']['rows']['sha256']
    module_spec = importlib.util.spec_from_file_location('saved_metric_audit', metrics_path)
    metrics = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(metrics)
    with gzip.open(rows_path, 'rt', encoding='utf-8') as stream:
        rows = [json.loads(line) for line in stream if line.strip()]
    with np.load(saved_path, allow_pickle=False) as z:
        assert z['uid'].tolist() == [r['uid'] for r in rows]
        raw, final = z['base'][:, 3], z['corrected'][:, 3]
    ix = np.flatnonzero(metrics.post_window_mask(rows, spec['windows']))
    rr = [rows[int(i)] for i in ix]
    weights = metrics.hierarchical_weights(rr, 'UNSW_DEV')
    normal = np.array([r['label'] == 0 for r in rr])
    before, after = raw[ix], final[ix]
    denominator, fp, raw_fp = int(normal.sum()), int((normal & after).sum()), int((normal & before).sum())
    recorded = read(result_path)['pools']['UNSW_DEV']['views']['post_window_primary']['reports']['ensemble']
    assert (denominator, fp, raw_fp) == (74444, 8494, 29702)
    assert fp / denominator == recorded['corrected']['normal']['rate']
    weighted = math.fsum(weights[normal & after]) / math.fsum(weights[normal])
    assert math.isclose(weighted, recorded['corrected']['normal']['weighted_rate'], abs_tol=1e-14)
    components = defaultdict(lambda: dict(rows=0, fp=0, raw_fp=0, weights=[], fp_weights=[]))
    devices = defaultdict(lambda: dict(rows=0, fp=0, raw_fp=0))
    for i, r in enumerate(rr):
        if r['label'] != 0:
            continue
        g = components[(r['device'], r['component_id'])]
        g['rows'] += 1; g['fp'] += int(after[i]); g['raw_fp'] += int(before[i])
        g['weights'].append(float(weights[i]))
        if after[i]: g['fp_weights'].append(float(weights[i]))
        d = devices[r['device']]
        d['rows'] += 1; d['fp'] += int(after[i]); d['raw_fp'] += int(before[i])
    grouped = []
    for (device, component), g in components.items():
        grouped.append(dict(device=device, component_id=component, rows=g['rows'], fp=g['fp'],
            raw_fp=g['raw_fp'], sample_fpr=g['fp']/g['rows'],
            normal_pool_weight=math.fsum(g['weights']), weighted_pool_fp=math.fsum(g['fp_weights'])))
    grouped.sort(key=lambda g: (-g['fp'], g['device'], g['component_id']))
    cumulative = 0; ninety_count = 0
    for g in grouped:
        cumulative += g['fp']; ninety_count += 1
        if cumulative >= .9 * fp: break
    for d in devices.values():
        d.update(sample_fpr=d['fp']/d['rows'], share_of_all_fp=d['fp']/fp)
    result = dict(status='READONLY_REPLAY_PASS', pool='UNSW_DEV', view='post_window_primary',
        normal_rows=denominator, raw_fp=raw_fp, current_fp=fp, raw_sample_fpr=raw_fp/denominator,
        current_sample_fpr=fp/denominator, current_weighted_fpr=weighted,
        fp_reduction_count=raw_fp-fp, relative_fp_reduction=(raw_fp-fp)/raw_fp,
        normal_component_count=len(grouped), components_with_fp=sum(g['fp']>0 for g in grouped),
        components_covering_90_percent_fp=ninety_count,
        top_component_fp_shares={str(k):sum(g['fp'] for g in grouped[:k])/fp for k in (1,5,10,20)},
        devices=dict(devices), components=grouped,
        interpretation='Saved sampled query rows, not raw packet frequency or de-duplicated operational alarm events.',
        no_new_predictions=True, no_distances=True, no_parameter_changes=True,
        input_sha256=inputs, audit_script_sha256=sha(Path(__file__)))
    for rel, digest in inputs.items(): assert sha(ROOT / rel) == digest
    with (HERE / 'RESULT.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2); stream.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('components','input_sha256')},ensure_ascii=False))


if __name__ == '__main__':
    main()
