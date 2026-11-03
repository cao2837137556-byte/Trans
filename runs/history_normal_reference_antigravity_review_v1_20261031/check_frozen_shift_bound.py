"""Arithmetic audit of saved logits only; no model/PCAP/distance execution."""
from collections import defaultdict
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'repo/ood'))
import constrained_onboarding_core_v3 as core

METRIC_FILE = ROOT / 'runs/dense_reference_ab_stage_candidate_v1_20261028/src/metrics.py'
spec = importlib.util.spec_from_file_location('hnr_review_original_metrics', METRIC_FILE)
metrics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metrics)
pins = {}


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def pinned(item):
    path = (ROOT / item['path']).resolve()
    assert path.is_relative_to(ROOT)
    assert sha(path) == item['sha256'], str(path)
    if 'bytes' in item:
        assert path.stat().st_size == item['bytes']
    pins[str(path.relative_to(ROOT))] = item['sha256']
    return path


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def decisions(x, cuts):
    return np.column_stack((x > core._cuts(cuts['cuts']),
                            core.ordered_ensemble(x) > cuts['ensemble_cut']))


def rates(indices, weights, before, lower):
    ix = np.asarray(indices, dtype=np.int64)
    mass = math.fsum(weights[ix])
    return {suffix: dict(rows=len(ix), raw_fp=int(before[ix, j].sum()),
                        unavoidable_fp_at_max_shift=int(lower[ix, j].sum()),
                        raw_weighted_fpr=math.fsum(weights[ix][before[ix, j]]) / mass,
                        optimistic_fpr_floor=math.fsum(weights[ix][lower[ix, j]]) / mass)
            for j, suffix in enumerate(metrics.SUFFIXES)}


def main():
    manifest_path = ROOT / 'runs/history_normal_reference_keyrepair_v1_20261031/config/ASSETS.json'
    assets = load(manifest_path)
    cuts = load(pinned(assets['calibration']['cuts']))
    scales = load(pinned(assets['calibration']['scales']))
    result_path = ROOT / 'runs/history_normal_reference_keyrepair_deployment_20261031/completion/RESULT.json'
    assert sha(result_path) == 'a6fcc46c8e5d62c0b029c09f0b4619b3d842648ecdca6b795ee41fd5adaf3d60'
    terminal = load(result_path)
    result = dict(schema='hnr-review-frozen-shift-normal-bound-v1', lambda_value=.25,
                  evidence='CONSUMED_DEVELOPMENT_ONLY',
                  interpretation='Optimistic lower bound: support=1 for all normal rows; ignores eligibility and attack protection. Not an achievable operating point.',
                  model_forwards=0, raw_decodes=0, distance_pairs=0, calibration_refits=0,
                  remote_operations=0, pools={})
    for pool, item in assets['pools'].items():
        with gzip.open(pinned(item['query']['rows']), 'rt', encoding='utf-8') as stream:
            rows = [json.loads(line) for line in stream if line.strip()]
        uids = [r['uid'] for r in rows]
        with np.load(pinned(item['query']['logits']), allow_pickle=False) as saved:
            assert saved['uid'].tolist() == uids
            x = core._logits(saved[item['query']['logits']['key']], len(rows), core.SEEDS)
        before = decisions(x, cuts)
        with np.load(pinned(item['baseline_decisions']), allow_pickle=False) as old:
            assert old['uid'].tolist() == uids
            assert np.array_equal(old['raw_logits'], x)
            assert np.array_equal(old['base'], before)
        full_weights = metrics.validate_full_weights(rows, pool)
        normal_ix = np.flatnonzero([r['label'] == 0 for r in rows])
        lower = before.copy()
        lower[normal_ix] = decisions(core.apply_correction(
            x[normal_ix], np.ones(len(normal_ix)), scales, .25), cuts)
        assert not np.any(lower[normal_ix] & ~before[normal_ix])
        keep = np.flatnonzero(metrics.post_window_mask(rows, item['windows']))
        result['pools'][pool] = {'views': {}, 'window_seconds':
                                 sorted({w['reference_end'] - w['start'] for w in item['windows']})}
        for view, ix in [('full', np.arange(len(rows))), ('post_window_primary', keep)]:
            rr = [rows[int(i)] for i in ix]
            w = full_weights if view == 'full' else metrics.hierarchical_weights(rr, pool)
            b, p = before[ix], lower[ix]
            published = terminal['pools'][pool]['views'][view]
            assert core._uid_hash([r['uid'] for r in rr]) == published['retained_uid_sha256']
            assert hashlib.sha256(w.tobytes()).hexdigest() == published['weights_sha256']
            normal = [i for i, r in enumerate(rr) if r['label'] == 0]
            overall = rates(normal, w, b, p)
            for suffix in metrics.SUFFIXES:
                assert abs(overall[suffix]['raw_weighted_fpr'] - published['reports'][suffix]['base']['normal']['weighted_rate']) < 1e-14
            groups, protocols = defaultdict(list), defaultdict(list)
            for i in normal:
                groups[rr[i]['device']].append(i)
                protocols[(rr[i]['device'], rr[i]['protocol'])].append(i)
            result['pools'][pool]['views'][view] = dict(
                pool=overall,
                devices={name: rates(indices, w, b, p) for name, indices in sorted(groups.items())},
                device_protocol=[dict(device=name, protocol=protocol, rates=rates(indices, w, b, p))
                                 for (name, protocol), indices in sorted(protocols.items())])
    for path, checksum in pins.items():
        assert sha(ROOT / path) == checksum
    result['pins'] = pins
    result['code_sha256'] = {str(p.relative_to(ROOT)): sha(p) for p in
                              [Path(__file__), METRIC_FILE, Path(core.__file__), manifest_path]}
    result['status'] = 'ARITHMETIC_BOUND_VERIFIED_NO_CANDIDATE_EVALUATION'
    target = OUT / 'D1_FROZEN_SHIFT_BOUND.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    for pool, value in result['pools'].items():
        view = value['views']['post_window_primary']
        print(pool, 'pool floor %', view['pool']['ensemble']['optimistic_fpr_floor'] * 100)
        for device, record in view['devices'].items():
            print(device, record['ensemble'])


if __name__ == '__main__':
    main()
