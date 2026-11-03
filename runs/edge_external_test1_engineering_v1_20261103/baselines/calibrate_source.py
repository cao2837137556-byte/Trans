"""Bounded local source-only kNN calibration from already saved arrays."""
import os
for _name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[_name] = '2'
import sys
sys.dont_write_bytecode = True
import collections
import gzip
import hashlib
import json
import math
from pathlib import Path
import platform
import threading
import time
import traceback

import numpy as np
import psutil
from threadpoolctl import threadpool_limits

from knn5 import KNN5Bank, decisions, source_cuts

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
CAL=ROOT/'runs/c5_kernel_independent_replay_codex_20261102/source_cal'
BANK=ROOT/'runs/dense_reference_batch_repair_deployment_20261027/result_retrieval_r2_20261027/evidence179602/science/encode/banks/SOURCE_REFS'
PREP=ROOT/'runs/diagnostics_d1_d2_v1_20261022/assets/heads/run/prepared'
START=time.monotonic()
STOP=threading.Event()
STATE=dict(status='STARTING',stage='PREPARE',wall_limit_seconds=600,rss_limit_bytes=1610612736,
           peak_rss_bytes=0,source_only=True,no_training=True,no_external_scores=True)


def write(name,value):
    path=OUT/name; tmp=path.with_name(path.name+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
    os.replace(tmp,path)


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(8*2**20),b''):h.update(chunk)
    return h.hexdigest()


def progress(stage,**kw):
    STATE.update(stage=stage,elapsed_seconds=time.monotonic()-START,**kw)
    write('SOURCE_PROGRESS.json',STATE)


def watch():
    process=psutil.Process()
    while not STOP.wait(.25):
        rss=process.memory_info().rss
        STATE['peak_rss_bytes']=max(STATE['peak_rss_bytes'],rss)
        if rss>STATE['rss_limit_bytes'] or time.monotonic()-START>600:
            STATE.update(status='STOPPED_BUDGET',error='RSS_OR_WALL_BUDGET')
            write('SOURCE_PROGRESS.json',STATE)
            os._exit(27)


def gzrows(path):
    with gzip.open(path,'rt',encoding='utf8') as f:return [json.loads(line) for line in f]


def verify_sidecar(path):
    expected=Path(str(path)+'.sha256').read_text(encoding='utf-8-sig').split()[0].lower()
    actual=sha(path)
    if expected!=actual:raise RuntimeError('INPUT_SHA256:'+str(path))
    return dict(path=str(path.relative_to(ROOT)).replace('\\','/'),bytes=path.stat().st_size,sha256=actual)


def main():
    if (OUT/'SOURCE_CALIBRATION.json').exists():raise RuntimeError('FRESH_RESULT_REQUIRED')
    contract=json.loads((OUT/'CONTRACT.json').read_text(encoding='utf-8-sig'))
    inputs=[CAL/n for n in ('CAL_QUERIES.jsonl.gz','CAL_E3.npy','CAL_FIXED_INPUTS.npz')]
    identities=[]
    for path in inputs:
        progress('VERIFYING_SOURCE_INPUTS',path=str(path))
        identities.append(verify_sidecar(path))
    prior=json.loads((CAL/'INPUT_SEAL.json').read_text(encoding='utf-8-sig'))['inputs']
    for path in [BANK/'references.jsonl.gz',BANK/'bank.npz',PREP/'normalizer.npz']:
        expected=next(x for x in prior if x['path']==str(path.relative_to(ROOT)).replace('\\','/'))
        actual=sha(path)
        if actual!=expected['sha256']:raise RuntimeError('PINNED_SOURCE_SHA:'+str(path))
        identities.append(dict(path=expected['path'],bytes=path.stat().st_size,sha256=actual))
    rows=gzrows(CAL/'CAL_QUERIES.jsonl.gz');refs=gzrows(BANK/'references.jsonl.gz')
    with np.load(CAL/'CAL_FIXED_INPUTS.npz',allow_pickle=False) as z:
        if z['uid'].tolist()!=[r['uid'] for r in rows]:raise RuntimeError('CAL_UID')
        raw=z['raw_decisions'].copy()
        normal_ix=z['normal_indices'].copy();attack_ix=z['attack_indices'].copy()
    if raw.shape!=(len(rows),4):raise RuntimeError('FOUR_RAW_WORKING_POINTS')
    e3=np.load(CAL/'CAL_E3.npy',mmap_mode='r',allow_pickle=False)
    with np.load(PREP/'normalizer.npz',allow_pickle=False) as z:
        normalizer=(z['mean'].copy(),z['scale'].copy())
    with np.load(BANK/'bank.npz',allow_pickle=False) as z:
        bank=KNN5Bank(refs,z['e3'],normalizer,feature_uids=z['uid'].tolist())
    counts=collections.Counter((r['partition'],r['device'],r['protocol']) for r in rows)
    upper=sum(counts[key]*len(ix) for key,ix in bank.groups.items() if len(ix)>=5)
    write('SOURCE_INPUT_SEAL.json',dict(status='LOCKED_BEFORE_DISTANCE',inputs=identities,
          contract_sha256=sha(OUT/'CONTRACT.json'),implementation_sha256=sha(OUT/'knn5.py'),
          calibration_script_sha256=sha(Path(__file__)),static_upper_pairs=upper,
          estimated_wall_seconds_upper=600,runtime=dict(python=platform.python_version(),numpy=np.__version__)))
    if upper>150000000:raise RuntimeError('STATIC_SOURCE_PAIR_LIMIT')
    sys.path.insert(0,str(ROOT/'repo/ood'))
    from constrained_onboarding_core_v3 import class_weights
    nw=class_weights([rows[i] for i in normal_ix]);aw=class_weights([rows[i] for i in attack_ix])
    progress('SOURCE_OWN_BANK_KNN_DISTANCE',static_upper_pairs=upper)
    result=bank.distances(rows,e3,feature_uids=[r['uid'] for r in rows],
             progress=lambda pairs:progress('SOURCE_OWN_BANK_KNN_DISTANCE',distance_pairs=pairs))
    calibrated=source_cuts(result['distance'][normal_ix],raw[normal_ix],nw)
    output=decisions(result['distance'],raw,calibrated['cuts'])
    def rate(ix,weight,arr):
        return [math.fsum(weight[arr[ix,j]])/math.fsum(weight) for j in range(4)]
    normal_rate=rate(normal_ix,nw,output);attack_rate=rate(attack_ix,aw,output)
    source_metrics=dict(normal_raw_weighted_fpr=rate(normal_ix,nw,raw),
        normal_knn_weighted_fpr=normal_rate,attack_raw_weighted_recall=rate(attack_ix,aw,raw),
        attack_knn_weighted_recall=attack_rate,normal_sample_fpr=output[normal_ix].mean(axis=0).tolist(),
        attack_sample_recall=output[attack_ix].mean(axis=0).tolist(),
        normal_fp_count=output[normal_ix].sum(axis=0).tolist(),attack_fn_count=(~output[attack_ix]).sum(axis=0).tolist(),
        raw_source_tp_withdrawal_count=(raw[attack_ix]&~output[attack_ix]).sum(axis=0).tolist())
    if not all(a<=b+1e-15 for a,b in zip(normal_rate,source_metrics['normal_raw_weighted_fpr'])):
        raise RuntimeError('SOURCE_MATCHED_FPR_FAILED')
    np.savez_compressed(OUT/'SOURCE_KNN_ARRAYS.npz',uid=np.asarray([r['uid'] for r in rows]),
                        distance=result['distance'],decisions=output,reason=result['reason'])
    answer=dict(status='SOURCE_CALIBRATED_NO_EXTERNAL_EVALUATION',method=contract['method'],
        single_score_four_source_working_points=True,cuts=calibrated['cuts'],
        working_points=calibrated['working_points'],metrics=source_metrics,
        source_population=dict(normal=len(normal_ix),attack=len(attack_ix),
          normal_finite_knn=int(np.isfinite(result['distance'][normal_ix]).sum()),
          attack_finite_knn=int(np.isfinite(result['distance'][attack_ix]).sum()),
          fallback_reasons=dict(collections.Counter(result['reason'].tolist()))),
        actual_distance_pairs=result['pairs'],static_upper_pairs=upper,resources=dict(
          CPU_threads=2,elapsed_seconds=time.monotonic()-START,peak_rss_bytes=STATE['peak_rss_bytes']),
        contract_sha256=sha(OUT/'CONTRACT.json'),input_seal_sha256=sha(OUT/'SOURCE_INPUT_SEAL.json'),
        arrays_sha256=sha(OUT/'SOURCE_KNN_ARRAYS.npz'),external_scores_read=False,
        interpretation='Source CAL operating-point calibration only; no evidence of external performance or general source test performance.')
    write('SOURCE_CALIBRATION.json',answer)
    progress('COMPLETE',status='PASS',distance_pairs=result['pairs'])


if __name__=='__main__':
    thread=threading.Thread(target=watch,daemon=True);thread.start()
    try:
        with threadpool_limits(limits=2):main()
    except BaseException as exc:
        progress('FAILED',status='FAILED',error=str(exc),traceback=traceback.format_exc())
        raise
    finally:
        STOP.set();thread.join(timeout=1)
