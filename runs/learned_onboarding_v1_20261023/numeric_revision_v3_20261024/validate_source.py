"""Validate revised inference on existing FIT-only checkpoints, without training."""
import datetime
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading
import time
import traceback

HERE=Path(__file__).resolve().parent
ROOT=HERE/'staging'
PACKAGE=Path('runs/learned_onboarding_v1_20261023')
ORIGINAL=Path('/srv/paper04/learned_onboarding_20261024_v2')/PACKAGE
FIT=ORIGINAL/'results/fit'
CACHE=Path('/srv/paper04/cache/coupon_resume_20261020_v2')
OUT=HERE/'source_validation'
OUT.mkdir(exist_ok=False)
START=time.monotonic()
PEAK=0
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/PACKAGE/'src'))


def write(name,value):
    with (OUT/name).open('x') as stream:
        json.dump(value,stream,indent=2,allow_nan=False)


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()


def guard():
    global PEAK
    import psutil
    process=psutil.Process()
    while True:
        rss=sum(p.memory_info().rss for p in [process]+process.children(recursive=True) if p.is_running())
        PEAK=max(PEAK,rss)
        if rss>8*1024**3 or time.monotonic()-START>900:
            write('RESOURCE_EXCEPTION.json',dict(rss=rss,seconds=time.monotonic()-START))
            os._exit(73)
        time.sleep(.25)


def main():
    import numpy as np
    import torch
    import common
    import learning
    import tasks
    from pipeline import IndexedRows
    threading.Thread(target=guard,daemon=True).start()
    common.check_spec()
    manifest=common.read(ROOT/'NUMERIC_REVISION_MANIFEST.json')
    for name,info in manifest['files'].items():
        assert sha(ROOT/name)==info['sha256'],'REVISION_IDENTITY:'+name
    spec=importlib.util.spec_from_file_location('frozen_learning_v2',ORIGINAL/'src/learning.py')
    old=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    assert sha(ORIGINAL/'src/learning.py')=='4a943da8cefd9e400ba0a50b6689386580c29f4002b01557d5f764e7314cc372'
    indices=np.load(CACHE/'inputs/FIT.npz')['indices']
    keep=('uid','device','label','activity','capture_id','session_id','component_id')
    rows=[]
    with gzip.open(FIT/'source_metadata.jsonl.gz','rt') as stream:
        for line in stream:
            row=json.loads(line)
            assert row['partition']=='LEARN' and row['fit_role']=='FIT'
            rows.append({key:row[key] for key in keep})
    assert len(rows)==len(indices)==617908
    e3=np.load(CACHE/'features/LEARN.npy',mmap_mode='r')[:,:768]
    q=np.load(ORIGINAL/'results/source_assets/run/prepared/LEARN_q.npy',mmap_mode='r')
    assert e3.shape==(766727,768) and q.shape==(766727,14)
    groups=[]
    for name in ('AUX_G0','AUX_G1'):
        tick=time.monotonic()
        isolated=common.read(FIT/name/'isolation.json')
        checkpoint=FIT/name/'final.pt'
        checkpoint_sha=sha(checkpoint)
        train=np.asarray([i for i,r in enumerate(rows) if r['device'] in isolated['train_devices']],np.int64)
        held=np.asarray([i for i,r in enumerate(rows) if r['device'] in isolated['held_devices']],np.int64)
        train_rows=[rows[int(i)] for i in train]
        held_rows=[rows[int(i)] for i in held]
        assert common.uid_hash([r['uid'] for r in train_rows],ordered=True)==isolated['fit_uid_sha256']
        assert common.uid_hash([r['uid'] for r in held_rows],ordered=True)==isolated['held_uid_sha256']
        ztrain,qtrain=IndexedRows(e3,indices[train]),IndexedRows(q,indices[train])
        zheld,qheld=IndexedRows(e3,indices[held]),IndexedRows(q,indices[held])
        original_train=old.score_auxiliary_head(checkpoint,ztrain,qtrain,batch_size=256)
        old_stat=tasks._statistics(train_rows,original_train)
        original_held=old.score_auxiliary_head(checkpoint,zheld,qheld,batch_size=256)
        fitted=learning.score_auxiliary_head(checkpoint,ztrain,qtrain,batch_size=256)
        stat=tasks._statistics(train_rows,fitted)
        primary=learning.score_auxiliary_head(checkpoint,zheld,qheld,batch_size=256)
        split=learning.score_auxiliary_head(checkpoint,zheld,qheld,batch_size=127)
        # Real reload: a distinct checkpoint loading and complete independent pass.
        reloaded=learning.score_auxiliary_head(checkpoint,zheld,qheld,batch_size=256)
        labels=np.asarray([r['label'] for r in held_rows])
        replay=learning._replay_compare(primary,reloaded,split,primary,np.zeros(len(primary)),
            stat['t'],labels,0.,direct_scores=True)
        assert np.array_equal(primary,split),'REVISED_NATIVE_BATCH_NOT_BITWISE'
        original_decision=original_held>old_stat['t']
        new_decision=primary>stat['t']
        decision_changes=np.flatnonzero(original_decision!=new_decision)
        _,_,_,item=learning.load_auxiliary_head(checkpoint)
        assert sha(checkpoint)==checkpoint_sha,'WEIGHTS_CHANGED'
        changes=np.abs(primary-original_held)
        version_close=np.isclose(primary,original_held,rtol=1e-6,atol=1e-6)
        result=dict(schema='paper04-numeric-revision-source-group-v3',status='PASS',
            head=name,source_only=True,target_queries_read=0,production_optimizer_updates=0,
            held_rows=len(held),train_rows=len(train),checkpoint_sha256=checkpoint_sha,
            checkpoint_updates=item['updates'],checkpoint_final_hash=item['final_hash'],
            same_checkpoint_weights=True,score_bitwise_native_256_127=True,
            score_bitwise_reloaded=True,replay=replay,original_fit_statistics=old_stat,
            revised_fit_statistics=stat,old256_bitwise_preservation_claimed=False,
            cross_version_changed_logits=int(np.count_nonzero(changes)),
            cross_version_max_abs_logit_difference=float(changes.max()),
            cross_version_outside_old_tolerance=int(np.count_nonzero(~version_close)),
            cross_version_changed_source_decisions=len(decision_changes),
            cross_version_source_new_fn=int(np.count_nonzero((labels==1)&original_decision&~new_decision)),
            hard_set_and_reference_geometry='NOT_EXECUTED_FULL_CHAIN_STILL_REQUIRED',
            elapsed_seconds=time.monotonic()-tick)
        write(name+'.json',result)
        groups.append(result)
        print(json.dumps({key:result[key] for key in ('head','status','held_rows',
            'score_bitwise_native_256_127','cross_version_changed_source_decisions',
            'cross_version_source_new_fn','elapsed_seconds')}),flush=True)
    for name,info in manifest['files'].items():
        assert sha(ROOT/name)==info['sha256'],'REVISION_CHANGED_AFTER_VALIDATION:'+name
    write('SOURCE_VALIDATION.json',dict(schema='paper04-numeric-revision-source-validation-v3',
        status='PASS_SOURCE_FORWARD_ONLY_NOT_EXPERIMENT_RESTART',
        recorded_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        production_optimizer_updates=0,target_queries_read=0,original_experiment_resumed=False,
        revision_manifest_sha256=sha(ROOT/'NUMERIC_REVISION_MANIFEST.json'),
        runtime=common.environment(),groups=groups,peak_process_tree_rss=PEAK,
        elapsed_seconds=time.monotonic()-START,
        remaining=['full source geometry and H replay','source-signal gate',
                   'three module production training','CAL lambda','A/B target evaluation']))
    print('PASS: saved auxiliary weights and all FIT-only held rows; no experiment resumed',flush=True)


if __name__=='__main__':
    try:
        main()
    except BaseException:
        write('VALIDATION_EXCEPTION.json',dict(traceback=traceback.format_exc(),
            elapsed_seconds=time.monotonic()-START,peak_process_tree_rss=PEAK))
        raise
