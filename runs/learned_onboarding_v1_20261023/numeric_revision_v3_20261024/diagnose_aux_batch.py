"""Bounded FIT-only forward diagnosis; never trains or resumes the stopped chain."""
import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time
import traceback

ROOT = Path('/srv/paper04/learned_onboarding_20261024_v2')
PACKAGE = ROOT / 'runs/learned_onboarding_v1_20261023'
FIT = PACKAGE / 'results/fit'
CACHE = Path('/srv/paper04/cache/coupon_resume_20261020_v2')
OUT = Path(__file__).resolve().parent / 'evidence'
OUT.mkdir(exist_ok=False)
START = time.monotonic()
PEAK = 0
LIMIT = 8 * 1024**3
sys.dont_write_bytecode = True
sys.path.insert(0, str(PACKAGE / 'src'))


def write(name, value):
    with (OUT / name).open('x') as f:
        json.dump(value, f, indent=2, allow_nan=False)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def guard():
    global PEAK
    import psutil
    process = psutil.Process()
    while True:
        rss = sum(p.memory_info().rss for p in [process] + process.children(recursive=True)
                  if p.is_running())
        PEAK = max(PEAK, rss)
        if rss > LIMIT or time.monotonic() - START > 540:
            write('RESOURCE_EXCEPTION.json', dict(rss=rss, seconds=time.monotonic()-START))
            os._exit(73)
        time.sleep(.25)


def main():
    import numpy as np
    import torch
    import learning
    import common
    import tasks
    from pipeline import IndexedRows
    threading.Thread(target=guard, daemon=True).start()
    common.check_spec()
    pinned = {
        'learning.py': '4a943da8cefd9e400ba0a50b6689386580c29f4002b01557d5f764e7314cc372',
        'pipeline.py': 'dfae1b2d277ad2327dbebc3ee2f23c4b725177910d5750f5c9c7deef4cd713df',
    }
    for name, expected in pinned.items():
        assert sha(PACKAGE/'src'/name) == expected, 'FROZEN_CODE_CHANGED:'+name
    isolation = common.read(FIT/'AUX_G1/isolation.json')
    checkpoint = FIT/'AUX_G1/final.pt'
    checkpoint_sha = sha(checkpoint)
    model, mean, scale, item = learning.load_auxiliary_head(checkpoint)
    assert item['epochs'] == 40 and item['updates'] == 79600
    fit_indices = np.load(CACHE/'inputs/FIT.npz')['indices']
    keep = ('uid', 'device', 'label', 'activity', 'capture_id', 'session_id', 'component_id')
    rows = []
    with gzip.open(FIT/'source_metadata.jsonl.gz', 'rt') as stream:
        for line in stream:
            row = json.loads(line)
            assert row['partition'] == 'LEARN' and row['fit_role'] == 'FIT'
            rows.append({key: row[key] for key in keep})
    assert len(rows) == len(fit_indices) == 617908
    train = np.asarray([i for i,r in enumerate(rows) if r['device'] in isolation['train_devices']], np.int64)
    held = np.asarray([i for i,r in enumerate(rows) if r['device'] in isolation['held_devices']], np.int64)
    assert len(train) == 509233 and len(held) == 108675
    assert item['fit_uids'] == [rows[int(i)]['uid'] for i in train]
    assert common.uid_hash([rows[int(i)]['uid'] for i in held], ordered=True) == isolation['held_uid_sha256']
    assert len(set(train.tolist()).intersection(held.tolist())) == 0
    features = np.load(CACHE/'features/LEARN.npy', mmap_mode='r')
    q = np.load(PACKAGE/'results/source_assets/run/prepared/LEARN_q.npy', mmap_mode='r')
    assert features.shape == (766727,794) and q.shape == (766727,14)
    held_z = IndexedRows(features[:,:768], fit_indices[held])
    held_q = IndexedRows(q, fit_indices[held])
    print('FIT-only identity and held order verified', flush=True)

    def trace(batch_size):
        normalized = hashlib.sha256()
        pre = np.empty((len(held),128), np.float32)
        active = np.empty_like(pre)
        scores = np.empty(len(held), np.float64)
        with torch.no_grad():
            for start in range(0,len(held),batch_size):
                sl = slice(start,min(start+batch_size,len(held)))
                x = learning._aux_batch(held_z,held_q,sl,mean,scale)
                normalized.update(x.tobytes(order='C'))
                a = model[0](torch.from_numpy(x))
                b = model[1](a)
                c = model[2](b)
                pre[sl],active[sl],scores[sl] = a.numpy(),b.numpy(),c.flatten().numpy()
        return normalized.hexdigest(), pre, active, scores

    input256,pre256,relu256,score256 = trace(256)
    input127,pre127,relu127,score127 = trace(127)
    reloaded = learning.score_auxiliary_head(checkpoint,held_z,held_q,batch_size=256)
    assert np.array_equal(score256,reloaded), 'TRACE_DIFFERS_FROM_FROZEN_PRODUCTION'
    print('Original native 256/127 scoring and layer traces complete', flush=True)
    train_z = IndexedRows(features[:,:768],fit_indices[train])
    train_q = IndexedRows(q,fit_indices[train])
    train_scores = learning.score_auxiliary_head(checkpoint,train_z,train_q,batch_size=256)
    stat = tasks._statistics([rows[int(i)] for i in train], train_scores)

    def delta(a,b):
        diff = np.abs(a.astype(np.float64)-b.astype(np.float64))
        tolerance = 1e-6+1e-6*np.abs(b)
        return dict(bitwise_equal=bool(np.array_equal(a,b)),max_abs=float(diff.max()),
                    changed_values=int(np.count_nonzero(diff)),
                    outside_original_tolerance=int(np.count_nonzero(diff>tolerance)),
                    max_tolerance_ratio=float(np.max(diff/tolerance)))

    difference = np.abs(score256-score127)
    bad = np.flatnonzero(~np.isclose(score256,score127,rtol=1e-6,atol=1e-6))
    changed = np.flatnonzero((score256>stat['t']) != (score127>stat['t']))
    labels = np.asarray([rows[int(i)]['label'] for i in held])
    attack_fn256 = np.flatnonzero((labels==1)&(score256<=stat['t']))
    attack_fn127 = np.flatnonzero((labels==1)&(score127<=stat['t']))
    added_fn127 = np.flatnonzero((labels==1)&(score256>stat['t'])&(score127<=stat['t']))
    order = sorted(bad.tolist(),key=lambda i:(-difference[i],rows[int(held[i])]['uid']))
    details = [dict(held_slot=i,fit_slot=int(held[i]),cache_slot=int(fit_indices[held[i]]),
                    uid=rows[int(held[i])]['uid'],label=int(labels[i]),
                    native256=float(score256[i]),native127=float(score127[i]),
                    absolute_difference=float(difference[i]),
                    original_tolerance=float(1e-6+1e-6*abs(score127[i]))) for i in order]
    write('native_bad_rows.json',details)
    result = dict(schema='paper04-fit-only-batch-diagnosis-v1',
        status='ORIGINAL_NATIVE_BATCH_FAILURE_REPRODUCED' if len(bad) else 'FAILURE_NOT_REPRODUCED',
        recorded_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        source_only=True,target_queries_read=0,optimizer_updates=0,
        original_experiment_resumed=False,checkpoint_sha256=checkpoint_sha,
        checkpoint_updates=item['updates'],fit_rows=len(rows),held_rows=len(held),train_rows=len(train),
        source_pseudo_statistics=stat,input_bytes_equal=input256==input127,
        input_normalized_sha256_256=input256,input_normalized_sha256_127=input127,
        first_linear=delta(pre256,pre127),relu=delta(relu256,relu127),
        final_logits=delta(score256,score127),reload_bitwise=bool(np.array_equal(score256,reloaded)),
        failed_rows=len(bad),decision_changed_rows=len(changed),
        decision_changed_uids=[rows[int(held[i])]['uid'] for i in changed],
        source_attack_fn_256=len(attack_fn256),source_attack_fn_127=len(attack_fn127),
        source_attack_fn_sets_equal=bool(np.array_equal(attack_fn256,attack_fn127)),
        source_new_fn_127_vs256=len(added_fn127),
        hard_set_equality='NOT_CHECKED_NO_GEOMETRY_OR_TRAINING',
        top_bad_rows=details[:10],runtime=dict(python=sys.version,numpy=np.__version__,
            torch=torch.__version__,threads=torch.get_num_threads(),
            deterministic=torch.are_deterministic_algorithms_enabled(),
            torch_build=torch.__config__.show(),cpu_capability=torch.backends.cpu.get_cpu_capability()),
        protected_code_sha256=pinned)
    assert sha(checkpoint)==checkpoint_sha, 'CHECKPOINT_CHANGED'
    for name,expected in pinned.items():
        assert sha(PACKAGE/'src'/name)==expected, 'FROZEN_CODE_CHANGED_AFTER_DIAGNOSIS'
    np.savez_compressed(OUT/'native_held_scores.npz',native256=score256,native127=score127)
    result.update(elapsed_seconds=time.monotonic()-START,peak_process_tree_rss=PEAK)
    write('DIAGNOSIS.json',result)
    print(json.dumps({k:result[k] for k in ('status','input_bytes_equal','failed_rows','first_linear',
        'final_logits','decision_changed_rows','source_new_fn_127_vs256','elapsed_seconds','peak_process_tree_rss')}),flush=True)


if __name__ == '__main__':
    try:
        main()
    except BaseException:
        write('DIAGNOSTIC_EXCEPTION.json',dict(traceback=traceback.format_exc(),
            elapsed_seconds=time.monotonic()-START,peak_process_tree_rss=PEAK))
        raise
