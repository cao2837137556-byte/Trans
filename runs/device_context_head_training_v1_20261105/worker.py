"""Real-source training gate and fixed sequential heads; no external evaluation reads."""
import argparse
import gc
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
import traceback
import numpy as np
import psutil
import torch
import context_core as k
import context_train as train
import constrained_onboarding_core_v3 as onboarding

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / 'device_context_training_v2_20261105'
c = k.c
PHASE = 'PREFLIGHT'


def write(name, value):
    c.write(HERE / name, value, replace=True)


class Progress:
    def __init__(self):
        self.stage = 'LOAD_SOURCE'
        self.last = 0
        self.optimizer_updates = 0
        self.peak = 0

    def tick(self, done, total):
        now = time.monotonic()
        if now - self.last < 2 and done != total:
            return
        self.peak = max(self.peak, psutil.Process().memory_info().rss)
        c.require(self.peak < 7 * 1024**3, 'TRAIN_PROCESS_MEMORY_LIMIT')
        write(PHASE + '_PROGRESS.json', dict(stage=self.stage, done=int(done), total=int(total),
              optimizer_updates=self.optimizer_updates, rss_mib=self.peak/1024**2, updated_unix=time.time()))
        self.last = now


def verify_delivery():
    for name, digest in c.read(HERE / '.private.json')['pins'].items():
        c.pin(HERE / name, digest)
    for name, digest in c.read(HERE / 'PARENT_SOURCE_PINS.json').items():
        c.pin(HERE / name, digest)
    acceptance = c.read(HERE / 'FINAL_ACCEPTANCE.json')
    c.require(acceptance['result'] == 'PASS' and acceptance['scope'] == 'SOURCE_FEATURES_ONLY', 'SOURCE_ACCEPTANCE')
    for name, digest in acceptance['receipt_sha256'].items():
        c.pin(SOURCE / name, digest)
    return acceptance


def load(progress, gate):
    started = time.monotonic()
    acceptance = verify_delivery()
    spec = c.read(HERE / 'TRAINING_SPEC_FROZEN.json')
    plan = c.read(HERE / 'ASSET_PLAN.json')
    resolved = c.read(SOURCE / 'RESOLVED_ASSETS.json')
    paths = {}
    wanted = {('prepared', 'LEARN.jsonl.gz'), ('e3', 'LEARN.npy'), ('prepared', 'LEARN_q.npy'), ('prepared', 'normalizer.npz')}
    for key, item in plan.items():
        pair = (item['kind'], item['name'])
        if pair in wanted:
            paths[pair] = c.pin(resolved[key], item['sha256'])
    c.require(set(paths) == wanted, 'SOURCE_ASSETS')
    fit = np.load(SOURCE / 'metadata/FIT.npy', allow_pickle=False)
    cal = np.load(SOURCE / 'metadata/CAL.npy', allow_pickle=False)
    c.require(len(fit) == 617908 and len(cal) == 148819 and len(np.unique(np.r_[fit, cal])) == 766727, 'SOURCE_SPLIT')
    rows = []
    fields = ('uid', 'partition', 'fit_role', 'label', 'use', 'device', 'activity', 'capture_id', 'session_id', 'component_id', 'protocol')
    pools = {key: {} for key in fields if key not in ('uid', 'label', 'protocol')}
    with gzip.open(paths['prepared', 'LEARN.jsonl.gz'], 'rt') as stream:
        for line in stream:
            item = json.loads(line)
            row = {key: item[key] for key in fields}
            for key, pool in pools.items():
                row[key] = pool.setdefault(row[key], row[key])
            rows.append(row)
    c.require(len(rows) == 766727, 'LEARN_ROWS')
    for name, indices in [('FIT', fit), ('CAL', cal)]:
        c.require(c.uid_sha(rows[int(i)]['uid'] for i in indices) == spec['data_identity'][name]['uid_sha256'], 'ROLE_UID')
        c.require(all(rows[int(i)]['fit_role'] == name and rows[int(i)]['partition'] == 'LEARN' for i in indices), 'ROLE_CONTENT')
    meta = np.load(SOURCE / 'metadata/LEARN.npz', allow_pickle=False)
    c.require(np.array_equal(meta['uid'], np.asarray([r['uid'] for r in rows], dtype='S64')), 'ORDERED_LEARN_UID')
    values = np.load(paths['e3', 'LEARN.npy'], mmap_mode='r')
    q = np.load(paths['prepared', 'LEARN_q.npy'], mmap_mode='r')
    normfile = np.load(paths['prepared', 'normalizer.npz'])
    norm = normfile['mean'], normfile['scale']
    contextfile = c.pin(SOURCE / 'features8/LEARN.npy', acceptance['arrays']['LEARN']['sha256'])
    context = np.load(contextfile, mmap_mode='r')
    c.require(context.shape == (len(rows), 8) and context.dtype == np.float64, 'CONTEXT_SHAPE')
    if gate:
        block = np.log1p(context[fit])
        mean = block.mean(axis=0, dtype=np.float64)
        std = block.std(axis=0, dtype=np.float64, ddof=0)
        std[std == 0] = 1
        del block
        c.save_arrays(HERE / 'context_normalizer.npz', mean=mean, scale=std)
        write('NORMALIZER.json', dict(status='PASS', source='LEARN/FIT', rows=len(fit),
              fit_uid_sha256=spec['data_identity']['FIT']['uid_sha256'], sha256=c.sha(HERE / 'context_normalizer.npz'),
              transform='log1p; float64 population mean/std; exact-zero std=1; cast result to float32'))
    else:
        receipt = c.read(HERE / 'NORMALIZER.json')
        c.pin(HERE / 'context_normalizer.npz', receipt['sha256'])
        a = np.load(HERE / 'context_normalizer.npz')
        mean, std = a['mean'], a['scale']
    extra = ((np.log1p(context) - mean) / std).astype(np.float32)
    c.require(np.isfinite(extra).all(), 'CONTEXT_NORMALIZATION_FINITE')
    fitrows = [rows[int(i)] for i in fit]
    w = k.weights(fitrows)
    c.require(hashlib.sha256(w.tobytes()).hexdigest() == 'a15d8badee167e8a50dafe6862522413a52e72a67e54b6d895efda5546b710de', 'FIT_WEIGHT_SHA')
    stages = np.select([q[:, 0] == 0, q[:, 3] == 1, (q[:, 2] == 1) & (q[:, 5] == 0), q[:, 2] == 1, q[:, 1] == 1], [0, 1, 2, 3, 4], default=5).astype(np.uint8)
    progress.tick(len(rows), len(rows))
    return dict(rows=rows, values=(values, extra), q=q, norm=norm, fit=fit, cal=cal, w=w, stages=stages,
                spec=spec, load_seconds=time.monotonic()-started)


def calibration(model, data, arm, folder, progress):
    started = time.monotonic()
    folder.mkdir(exist_ok=False)
    scores = {}
    for role in ('fit', 'cal'):
        progress.stage = 'CALIBRATE_' + arm + '_' + role.upper()
        scores[role] = k.scores(model, data['values'], data['q'], data[role], data['norm'], k.DIMENSIONS[arm], progress)
        np.save(folder / (role + '_logits.npy'), scores[role], allow_pickle=False)
    calrows = [data['rows'][int(i)] for i in data['cal']]
    normal = np.asarray([r['label'] == 0 for r in calrows])
    nr = [r for r in calrows if r['label'] == 0]
    threshold = k.threshold(scores['cal'][normal], nr, .01)
    weights = k.class_weights(nr)
    fpr = float(math.fsum(weights[scores['cal'][normal] > threshold]))
    c.require(fpr <= .01 + 1e-14, 'SOURCE_CAL_FPR')
    low = onboarding.weighted_quantile(scores['fit'], data['w'], .1)
    high = onboarding.weighted_quantile(scores['fit'], data['w'], .9)
    # Reload the saved checkpoint and verify its predictions at the same batch shape.
    reloaded = k.classifier(27, k.DIMENSIONS[arm])
    saved = np.load(folder.parent / 'train/head.npz', allow_pickle=False)
    reloaded.load_state_dict({key: torch.from_numpy(saved[key].copy()) for key in saved.files})
    reloaded.eval()
    indices = data['cal'][:1024]
    repeated = k.scores(reloaded, data['values'], data['q'], indices, data['norm'], k.DIMENSIONS[arm])
    c.require(np.array_equal(repeated, scores['cal'][:1024]), 'CHECKPOINT_SCORE_READBACK')
    result = dict(status='PASS', arm=arm, cut=threshold, comparison='>', weighted_normal_fpr=fpr,
                  unweighted_normal_fpr=float((scores['cal'][normal] > threshold).mean()), normal_rows=len(nr),
                  scale=high-low, q10=low, q90=high, scale_source='FIT', threshold_source='CAL_NORMAL',
                  logits_sha256={role: c.sha(folder / (role + '_logits.npy')) for role in scores},
                  cal_uid_sha256=c.uid_sha(r['uid'] for r in calrows), checkpoint_score_readback=True,
                  seconds=time.monotonic()-started)
    c.write(folder / 'RESULT.json', result)
    c.seal(folder)
    return result


def one(data, arm, seed, progress, gate):
    started = time.monotonic()
    folder = HERE / ('runtime_smoke' if gate else 'heads') / (arm + '_' + str(seed))
    folder.mkdir(parents=True, exist_ok=False)
    design = dict(training=data['spec']['training']['parent_recipe'])
    model = train.train(design, data['rows'], data['values'], data['q'], data['norm'], data['fit'],
                        data['stages'], arm, seed, folder / 'train', progress, runtime_batches=128 if gate else None)
    endpoint = c.read(folder / 'train/endpoint.json')
    c.require(endpoint['weight_sha256'] == 'a15d8badee167e8a50dafe6862522413a52e72a67e54b6d895efda5546b710de', 'ENDPOINT_WEIGHT')
    cal = calibration(model, data, arm, folder / 'calibration', progress)
    result = dict(status='PASS', arm=arm, seed=seed, runtime_gate_only=gate, updates=endpoint['updates'],
                  epochs=endpoint['epochs'], calibration=cal, profile=endpoint['profile'],
                  head_sha256=endpoint['head_sha256'], initial_sha256=endpoint['initial_sha256'],
                  seconds=time.monotonic()-started, rss_peak_bytes=progress.peak,
                  endpoint_sha256=c.sha(folder / 'train/endpoint.json'))
    if gate:
        profile = endpoint['profile'][0]
        batch_time = profile['batch_seconds'] / profile['batches']
        train_estimate = 40 * (profile['tail_seconds'] + 2414 * batch_time)
        overhead = data['load_seconds'] + cal['seconds'] + max(0, result['seconds']-sum((profile['tail_seconds'], profile['batch_seconds'], cal['seconds'])))
        result['forecast_seconds'] = 1.5 * (train_estimate + overhead) + 30
        result['forecast_rule'] = '1.5*(40*(full normal tail refresh + measured mean batch time*2414) + actual load/calibration/save overhead)+30'
    c.write(folder / 'RESULT.json', result)
    del model
    gc.collect()
    return result


def ensembles(data, gate):
    results = {}
    root = HERE / ('runtime_smoke' if gate else 'heads')
    calrows = [data['rows'][int(i)] for i in data['cal']]
    normal = np.asarray([r['label'] == 0 for r in calrows])
    nr = [r for r in calrows if r['label'] == 0]
    weights = k.class_weights(nr)
    for arm in k.ARMS:
        logits = []
        for seed in c.SEEDS:
            folder = root / (arm + '_' + str(seed)) / 'calibration'
            c.verify(folder)
            logits.append(np.load(folder / 'cal_logits.npy'))
        ensemble = onboarding.ordered_ensemble(dict(zip(c.SEEDS, logits)))
        cut = k.threshold(ensemble[normal], nr, .01)
        fpr = math.fsum(weights[ensemble[normal] > cut])
        c.require(fpr <= .01+1e-14, 'ENSEMBLE_SOURCE_CAL_FPR')
        results[arm] = dict(status='PASS', cut=cut, weighted_normal_fpr=fpr,
                            unweighted_normal_fpr=float((ensemble[normal] > cut).mean()),
                            seeds=list(c.SEEDS), normal_rows=len(nr), comparison='>', runtime_gate_only=gate)
    return results


def main():
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    progress = Progress()
    started = time.monotonic()
    gate = PHASE == 'PREFLIGHT'
    if gate:
        verify_delivery()
        (HERE / '.private').mkdir(exist_ok=True)
        progress.stage = 'LINUX_ADAPTER_INVARIANCE'
        progress.tick(0, 1)
        import test_training_adapter
        test_training_adapter.main('LINUX_ADAPTER_REGRESSION.json')
    if not gate:
        c.require(c.read(HERE / 'PREFLIGHT_RESULT.json')['status'] == 'PASS', 'REAL_RUNTIME_GATE_REQUIRED')
    data = load(progress, gate)
    if gate:
        results = {}
        for arm in k.ARMS:
            for seed in c.SEEDS:
                results[arm+'_'+str(seed)] = one(data, arm, seed, progress, True)
        ensemble = ensembles(data, True)
        forecasts = {key: v['forecast_seconds'] for key, v in results.items()}
        write('RUNTIME_FORECAST.json', dict(forecasts=forecasts, budget_seconds=1800, all_fit=max(forecasts.values()) <= 1800))
        c.require(max(forecasts.values()) <= 1800, 'SEALED_1800_SECOND_BUDGET_NOT_MET')
        result = dict(status='PASS', runtime_gate_only=True, heads=results, ensembles=ensemble,
                      forecasts=forecasts, normalizer_sha256=c.sha(HERE / 'context_normalizer.npz'))
    elif PHASE == 'CALIBRATION':
        result = dict(status='PASS', ensembles=ensembles(data, False), new_heads=9, evaluation_pending=True)
    else:
        _, arm, seed = PHASE.split('_')
        result = one(data, arm, int(seed), progress, False)
        c.require(result['updates'] == 96560 and result['epochs'] == 40, 'FORMAL_ENDPOINT')
    result.update(seconds=time.monotonic()-started, cpu_threads=torch.get_num_threads(), rss_peak_bytes=progress.peak,
                  torch_version=torch.__version__, numpy_version=np.__version__, external_data_read=False)
    write(PHASE + '_RESULT.json', result)
    progress.stage = 'PASS'
    progress.tick(1, 1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', required=True)
    PHASE = parser.parse_args().phase
    try:
        main()
    except Exception as error:
        write(PHASE + '_STOP.json', dict(status='FAIL', error=repr(error), traceback=traceback.format_exc()))
        raise
