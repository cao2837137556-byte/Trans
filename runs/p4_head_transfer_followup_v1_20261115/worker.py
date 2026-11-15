"""Frozen-head transfer replay. Source forwards calibrate a scale, never a threshold."""
from contextlib import contextmanager
from hashlib import sha256
import math
import os
from pathlib import Path
import sys
import time
import traceback

import numpy as np

import analysis_core as ac
from common_round1 import artifact,dump,load,read_rows,require,sha,table,uid_sha,write_rows

HERE = Path(__file__).resolve().parent
POOLS = ('CIC_DEV','UNSW_DEV','EDGE')
METHODS = ('TabM','CatBoost','SLAD')
SEEDS = (27,127,227)
UNSW_ATTACK = dict(TabM=72412,CatBoost=34422,SLAD=54003)
CAT = 'baseline_author_defaults_v1_20261108'
SLAD = 'baseline_slad_eval_repair_v1_20261108'
TABM = 'tabm_3d_transfer_v1_20261111'
TABM_REPAIR = 'tabm_transfer_eval_repair_v1_20261111'
P4 = 'p4_complete_bank_v1_20261111'
SOURCE = 'baseline_training_readiness_v6_20261107'


def checked(path, pin):
    path = Path(path)
    require(path.is_file() and sha(path)==pin,'ASSET_SHA:'+str(path))
    return path


def join_order(source, target):
    lookup = {uid:i for i,uid in enumerate(source)}
    require(len(lookup)==len(source)==len(target)==len(set(target)) and lookup.keys()==set(target),
            'QUERY_UID_MEMBERSHIP')
    return np.array([lookup[uid] for uid in target],dtype=np.int64)


def fork_scores(a):
    return np.stack([a[:,j] for j in range(3)]).mean(0,dtype=np.float64)


def score_schema(a, n):
    require(a.dtype==np.float64 and a.shape==(n,4) and np.isfinite(a).all() and
            np.array_equal(a[:,3],fork_scores(a)), 'FROZEN_SCORE_AND_ENSEMBLE')


def peak_rss():
    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss


class Progress:
    def __init__(self,out):
        self.out=out
        self.stages=[]
        self.last=0.
        self.start=time.monotonic()

    def __call__(self,stage,done=0,total=1,**fields):
        now=time.monotonic()
        if done and done!=total and now-self.last<2:
            return
        self.last=now
        peak=peak_rss()
        require(peak<=10240*1024,'RSS_HEADROOM_EXCEEDED')
        dump(self.out/'PROGRESS.json',dict(phase='heads',stage=stage,done=int(done),total=int(total),
             job=os.environ['SLURM_JOB_ID'],updated_unix=time.time(),peak_rss_kib=peak,**fields))

    @contextmanager
    def measure(self,stage):
        self(stage)
        t=time.monotonic()
        try:
            yield
        finally:
            self.stages.append(dict(stage=stage,seconds=time.monotonic()-t,
                peak_rss_kib=peak_rss()))
            dump(self.out/'RESOURCES.json',self.stages)


def load_pools(runs,cfg,progress):
    data={}
    for pool in POOLS:
        with progress.measure('PIN_FULL_BANK_AND_QUERIES_'+pool):
            spec=cfg['query'][pool]
            arc=runs/P4/'artifacts'
            rows=read_rows(checked(arc/spec['rows_file'],spec['rows_sha256']))
            ids=[r['uid'] for r in rows]
            require(len(ids)==len(set(ids)), 'QUERY_UIDS_NOT_UNIQUE')
            geometry=cfg['geometry'][pool]
            geom=checked(runs/'same_bank_context_v6_20261106'/geometry['file'],geometry['sha256'])
            with np.load(geom,allow_pickle=False) as o,np.load(
                    checked(arc/spec['array_file'],spec['array_sha256']),allow_pickle=False) as qf:
                require(qf['uid'].tolist()==ids,'FROZEN_QUERY_ARRAY_ORDER')
                ix=join_order(o['uid'].astype('U64').tolist(),ids)
                s2,s3,q=o['support2'][ix],qf['support3'],qf['q']
                require(s2.shape==s3.shape==(len(ids),) and
                        np.array_equal(o['support3'][ix],s3) and
                        np.isfinite(s2).all() and np.isfinite(s3).all() and
                        ((0<=s2)&(s2<=1)&(0<=s3)&(s3<=1)).all() and
                        (s3<=s2+2e-10).all(),'FULL_BANK_SUPPORT_IDENTITY')
                require(q.shape==(len(ids),14) and np.isfinite(q).all(),'QUERY_Q14')
                views={v:(qf[v+'_ix'],qf[v+'_weight']) for v in spec['views']}
                expand=qf['expansion'] if 'expansion' in qf.files else None
            require(np.array_equal(views['full'][0],np.arange(len(ids))), 'FULL_VIEW')
            if 'post_window_primary' in views:
                open_window=np.zeros(len(ids),bool)
                open_window[views['post_window_primary'][0]]=True
                require(not np.any(s2[~open_window]) and not np.any(s3[~open_window]),'PREBANK_SUPPORT')
            data[pool]=dict(rows=rows,ids=ids,q=q,s2=s2,s3=s3,views=views,expansion=expand,
                population=spec['population'])
    return data


def frozen_scores(runs,method,pool,data,cfg):
    if method=='TabM':
        pin=cfg['TabM']['gates'][pool]['score_sha256']
        with np.load(checked(runs/TABM_REPAIR/'p4_artifacts'/(pool+'_TABM_P4.npz'),pin),
                     allow_pickle=False) as a:
            ix=join_order(a['uid'].astype('U64').tolist(),data['ids'])
            raw,prior=a['TABM_RAW'][ix],a['TABM_3D_SELF_P4'][ix]
    else:
        parent=runs/(CAT if method=='CatBoost' else SLAD)
        arc=parent/'artifacts/evaluation'
        spec=cfg['old_evaluation']['pools'][pool]
        receipt=cfg[method]['scores'][pool]
        rows=load(checked(arc/(pool+'_ROWS.json'), spec['rows_sha256']))
        ids=[r['uid'] for r in rows]
        require(uid_sha(sorted(ids))==spec['uid_sha256']==receipt['uid_sha256'],
                'RAW_SCORE_UID_WITNESS')
        ix=join_order(ids,data['ids'])
        require(all(rows[i]['label']==r['label'] for i,r in zip(ix,data['rows'])),'RAW_SCORE_LABEL_JOIN')
        if pool!='EDGE':
            with np.load(arc/(pool+'_VIEWS.npz'),allow_pickle=False) as view:
                for name,prior_name in (('full','full'),('post_window_primary','primary')):
                    vi,weight=data['views'][name]
                    membership=np.zeros(len(ids),bool)
                    membership[view[prior_name+'_ix']]=True
                    require(np.array_equal(np.flatnonzero(membership[ix]),vi) and
                        np.max(np.abs(view[prior_name+'_weight'][ix]-weight))<=2e-12,
                        'RAW_VIEW_WEIGHT_BINDING:'+method+':'+pool+':'+name)
        raw=np.load(checked(arc/(method+'_'+pool+'_scores.npy'),receipt['sha256']),
                    allow_pickle=False)[ix]
        prior=None
    score_schema(raw,len(data['ids']))
    return raw,prior


def grouped_metrics(pool,data,pred):
    return ac.metrics(pool,data['rows'],pred,data['views'],data['q'],
                      data['expansion'],data['population'])


def same_metrics(actual,expected):
    def key(r):
        return tuple(r[k] for k in ('pool','head','view','group','guard_stratum'))
    want={key(r):r for r in expected}
    have={key(r):r for r in actual}
    require(want.keys()==have.keys(),'TABM_PRIOR_METRIC_KEYS')
    for ident,e in want.items():
        a=have[ident]
        require(e['rows']==a['rows'] and e['alarm_count']==a['alarm_count'] and
                abs(e['hierarchical_rate']-a['hierarchical_rate'])<=2e-10 and
                abs(e.get('HT_rate',0.)-a.get('HT_rate',0.))<=2e-10,'TABM_PRIOR_METRIC_PARITY')


def reproduce_raw(method,pool,data,pred,expected,tabm_expected):
    actual=grouped_metrics(pool,data,pred)
    if method=='TabM':
        same_metrics(actual,[x for x in tabm_expected if x['config']=='TABM_RAW' and x['pool']==pool])
        return len(actual)
    index={(a['view'],a['head'],a['group']):a for a in actual if a['guard_stratum']=='ALL'}
    n=0
    for head in ac.HEADS:
        if pool=='EDGE':
            source=expected['EDGE']['methods']['RAW']['heads'][head]['roles']
            for role in ('NORMAL','HTTP','UDP'):
                e=source[role]
                a=index['full',head,role]
                require(a['rows']==e['selected_rows'] and a['alarm_count']==e['alarm_count'] and
                        abs(a['hierarchical_rate']-e['selected_hierarchical_alarm_rate'])<=2e-10 and
                        abs(a['HT_rate']-e['ht_population_alarm_estimate'])<=2e-10,'EDGE_RAW_PARITY')
                n+=1
        else:
            for view,key in (('full','full'),('post_window_primary','primary')):
                source=expected[pool][key][method]['RAW'][head]['groups']['pool']
                for label in ('normal','attack'):
                    e=source[label]
                    a=index[view,head,label.upper()]
                    require(a['rows']==e['rows'] and a['alarm_count']==e['alarm_count'] and
                            abs(a['hierarchical_rate']-e['weighted_rate'])<=2e-10,'AB_RAW_PARITY')
                    n+=1
    return n


def source_data(runs,cfg):
    art = runs/SOURCE/'artifacts/source'
    src=cfg['source']
    witness=cfg['source_weights']
    fit=np.load(checked(art/'FIT_X.npy',src['sha256']['FIT_X.npy']),mmap_mode='r',allow_pickle=False)
    normal=np.load(checked(art/'NORMAL_X.npy',src['sha256']['NORMAL_X.npy']),mmap_mode='r',allow_pickle=False)
    label=np.load(checked(art/'FIT_y.npy',src['sha256']['FIT_y.npy']),allow_pickle=False)
    weights_path=next((runs/name/'artifacts/FIT_WEIGHTS.npy' for name in (TABM,TABM_REPAIR)
                       if (runs/name/'artifacts/FIT_WEIGHTS.npy').is_file()),None)
    require(weights_path is not None,'FROZEN_FIT_WEIGHTS_CACHE')
    w=np.load(checked(weights_path,witness['weight_sha256']),allow_pickle=False)
    meta=runs/'device_context_training_v2_20261105/metadata'
    order=np.load(meta/'FIT.npy',allow_pickle=False)
    with np.load(meta/'LEARN.npz',allow_pickle=False) as all_rows:
        ids=all_rows['uid'][order].astype('U64').tolist()
        require(len(set(ids))==len(ids)==617908 and uid_sha(sorted(ids))==witness['uid_sha256']
             and np.array_equal(all_rows['label'][order],label) and np.all(w>0), 'SOURCE_FIT_UID_OR_WEIGHT')
    require(src['sha256']['FIT_X.npy']==witness['fit_x_sha256'] and fit.shape==(617908,790) and
            normal.shape==(134493,790) and label.shape==w.shape==(617908,), 'SOURCE_ARRAY_IDENTITY')
    require(sha256(w.tobytes()).hexdigest()=='a15d8badee167e8a50dafe6862522413a52e72a67e54b6d895efda5546b710de'
            and all(abs(float(w[label==i].sum())-.5)<1e-12 for i in (0,1)), 'SOURCE_CLASS_WEIGHT_MASS')
    ni=np.flatnonzero(label==0)
    require(len(ni)==len(normal), 'NORMAL_ROLE_SIZE')
    for off in range(0,len(normal),8192):
        require(np.array_equal(normal[off:off+8192],fit[ni[off:off+8192]]), 'NORMAL_FIT_ROW_JOIN')
    return dict(CatBoost=(fit,w,ids),SLAD=(normal,w[ni]*2.,[ids[i] for i in ni]))


def weighted_quantile(x,w,p):
    order=np.argsort(x,kind='stable')
    cdf=np.cumsum(w[order]/math.fsum(w),dtype=np.float64)
    cdf[-1]=1.
    return float(x[order[np.searchsorted(cdf,p,side='left')]])


def native_heads(runs,method,cfg):
    import torch
    base=runs/CAT
    wheel=base/'runtime/wheels'
    require(load(wheel/'INSTALLED.json')['asset_manifest_sha256']==sha(base/'ASSETS.json'),
            'FROZEN_WHEEL_IMPORT_ROOT')
    sys.path[:0]=[str(wheel),str(base),str(base/'vendor/slad')]
    import formal
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    formal.HERE=base if method=='CatBoost' else runs/SLAD
    parent=formal.HERE
    pins={}
    for seed in SEEDS:
        if method=='CatBoost':
            receipt=load(base/f'train_CatBoost_{seed}_RESULT.json')
            require(receipt['status']=='PASS' and receipt['train_rows']==617908,'CATBOOST_TRAIN_RECEIPT')
            path=parent/'artifacts/CatBoost'/str(seed)/'model.cbm'
        else:
            receipt=cfg['slad_reload']['seeds'][str(seed)]
            path=parent/'artifacts/SLAD'/str(seed)/'checkpoint.pt'
            require(receipt['reload_scores_exact'],'ORIGINAL_SLAD_RELOAD')
        checked(path,receipt['checkpoint_sha256'])
        pins[str(seed)]=receipt['checkpoint_sha256']
    return formal,pins


def native_probe(runs,method,source,cfg,cuts):
    import torch
    formal,pins=native_heads(runs,method,cfg)
    parent=formal.HERE
    arc=parent/'artifacts/evaluation'
    cal=np.load(checked(arc/'CAL_X.npy',cfg['old_evaluation']['pools']['CAL']['x_sha256']),
                mmap_mode='r',allow_pickle=False)
    saved=np.load(checked(arc/(method+'_CAL_scores.npy'),cfg[method]['scores']['CAL']['sha256']),
                  allow_pickle=False)
    expected=load(HERE/(method+'_METRICS.json'))['CAL']
    score_schema(saved,33147)
    with np.load(arc/'CAL_VIEWS.npz',allow_pickle=False) as p:
        w=p['full_weight'];ix=p['full_ix']
        require(np.array_equal(ix,np.arange(len(cal))) and w.shape==(len(cal),) and
                np.isfinite(w).all() and (w>0).all() and abs(w.sum()-1.)<=1e-12,'ORIGINAL_CAL_VIEW')
        got=np.array([w[saved[:,i]>cuts[i]].sum() for i in range(4)])
        require(np.max(np.abs(got-expected['weighted_fpr']))<=2e-10,'ORIGINAL_SOURCE_THRESHOLD')
    forwards=[]
    samples={}
    source_rows,source_weights,_=source
    pilot_scale=[]
    for j,seed in enumerate(SEEDS):
        fn=formal.predictor(method,seed)
        with torch.inference_mode():
            sample=np.array(cal[:256],copy=True)
            first=np.asarray(fn(sample),dtype=np.float64)
            require(first.shape==(256,) and np.isfinite(first).all() and
                    np.max(np.abs(first-saved[:256,j]))<=2e-7 and
                    np.array_equal(first>cuts[j],saved[:256,j]>cuts[j]),'REAL_NATIVE_CAL_PROBE:'+method)
            if method=='SLAD':
                restored=np.asarray(formal.predictor(method,seed)(sample),dtype=np.float64)
                require(np.array_equal(restored,first),'CLEAN_SLAD_RELOAD')
            pilot=np.asarray(fn(np.array(source_rows[:256],copy=True)),dtype=np.float64)
            require(pilot.shape==(256,) and np.isfinite(pilot).all(),'REAL_SOURCE_INPUT_SLICE')
        forwards.append(fn)
        samples[str(seed)]=dict(rows=len(first),cache_difference=float(np.max(np.abs(first-saved[:256,j]))))
        pilot_scale.append(weighted_quantile(pilot,source_weights[:256],.9)-
                           weighted_quantile(pilot,source_weights[:256],.1))
    return forwards,pins,samples,np.asarray(pilot_scale)


def source_scales(method,source,out,cuts,progress,probe):
    import torch
    forwards,pins,samples,_=probe
    x,w,ids=source
    a=np.lib.format.open_memmap(out/(method+'_SOURCE_SCORES.npy'),mode='w+',dtype=np.float64,shape=(len(x),3))
    q10,q90=[],[]
    for j,fn in enumerate(forwards):
        with torch.inference_mode():
            for off in range(0,len(x),256):
                xbatch=np.array(x[off:off+256],copy=True)
                v=np.asarray(fn(xbatch),dtype=np.float64)
                require(v.shape==(len(xbatch),) and np.isfinite(v).all(),'NATIVE_SOURCE_FORWARD')
                a[off:off+len(v),j]=v
                if off%8192==0:
                    progress(method+'_SOURCE_FORWARD',j*len(x)+off,3*len(x),seed=SEEDS[j])
        q10.append(weighted_quantile(a[:,j],w,.1))
        q90.append(weighted_quantile(a[:,j],w,.9))
    a.flush()
    return dict(q10=q10,q90=q90,scales=(np.asarray(q90)-q10).tolist(),cuts=cuts.tolist(),
                rows=len(x),uid_sha256=uid_sha(ids),fit_weights_sha256=sha256(w.tobytes()).hexdigest(),
                checkpoints=pins,source_forward=artifact(out/(method+'_SOURCE_SCORES.npy')),
                native_preflight=samples)


def score_pair(raw,s2,s3,q,scale,cut):
    two=ac.scores(raw,s2,q,scale,'P4')
    three=ac.scores(raw,s3,q,scale,'P4')
    pred=tuple(x>cut for x in (raw,two,three))
    require(not np.any(pred[1]&~pred[2]) and not np.any(pred[2]&~pred[0]), 'PAIRED_ALERT_SUBSET')
    guard=ac.guard(q)
    require(np.array_equal(two[guard],raw[guard]) and np.array_equal(three[guard],raw[guard]),
            'SYN_BYPASS_EXACT')
    return two,three,pred


def emit_uid_changes(out,method,pool,d,pred):
    changed=np.flatnonzero(np.any((pred[0]!=pred[1])|(pred[0]!=pred[2]),axis=1))
    path=out/(method+'_'+pool+'_CHANGED_UIDS.jsonl.gz')
    count=write_rows(path,(dict(uid=d['ids'][j],label=d['rows'][j]['label'],
           raw=pred[0][j].tolist(),two=pred[1][j].tolist(),three=pred[2][j].tolist())
           for j in changed))
    return artifact(path,count)


def transfer(runs,out,progress):
    cfg=load(HERE/'HEAD_ASSETS.json')
    data=load_pools(runs,cfg,progress)
    tabm=load(HERE/'TABM_METRICS.json')
    cached={}
    gates={}
    for method in METHODS:
        expected=None if method=='TabM' else load(HERE/(method+'_METRICS.json'))
        cuts=np.asarray(cfg['TabM']['tabm_source_calibration']['cuts'] if method=='TabM' else expected['CAL']['cuts'])
        raw={}
        total=0
        with progress.measure(method+'_BASELINE_AND_REAL_SLICE'):
            for pool in POOLS:
                d=data[pool]
                score,prior=frozen_scores(runs,method,pool,d,cfg)
                total+=reproduce_raw(method,pool,d,score>cuts,expected,tabm)
                if method=='TabM':
                    scale=np.asarray(cfg['TabM']['tabm_source_calibration']['scales'])
                    result=ac.scores(score,d['s3'],d['q'],scale,'P4')
                    require(np.array_equal(result,prior),'REPRODUCE_TABM_3D_CACHE')
                    same_metrics(grouped_metrics(pool,d,prior>cuts),
                                 [x for x in tabm if x['config']=='TABM_3D_SELF_P4' and x['pool']==pool])
                raw[pool]=score
            cached[method]=cuts,raw
            gates[method]=dict(raw_metric_checks=total)
    scales,changed={},{}
    metrics,pairs=[],[]
    with progress.measure('PIN_ORDERED_SOURCE_FIT_AND_NORMAL_WEIGHTS'):
        source=source_data(runs,cfg)
    probes={}
    for method in METHODS:
        cuts,raw=cached[method]
        with progress.measure(method+'_REAL_P4_PREFLIGHT'):
            if method=='TabM':
                pilot=np.asarray(cfg['TabM']['tabm_source_calibration']['scales'])
            else:
                probes[method]=native_probe(runs,method,source[method],cfg,cuts)
                pilot=probes[method][3]
            for pool in POOLS:
                d=data[pool]
                idx=np.unique(np.linspace(0,len(d['ids'])-1,num=256,dtype=np.int64))
                _,_,alerts=score_pair(raw[pool][idx],d['s2'][idx],d['s3'][idx],d['q'][idx],pilot,cuts)
                # Exercise the metric entry point on the identical real query slice.
                weights=d['views']['full'][1][idx]
                full={'full':(np.arange(len(idx)),weights)}
                rows=[d['rows'][j] for j in idx]
                require(ac.metrics(pool,rows,alerts[2],full,d['q'][idx]),'REAL_SLICE_EVALUATION')
    dump(out/'PREFLIGHT.json',dict(status='PASS',scope='ACTUAL_COMPUTE_NODE_REAL_INPUT',
        cached_baseline=gates,native={m:probes[m][2] for m in METHODS[1:]}))
    for method in METHODS:
        cuts,raw=cached[method]
        if method=='TabM':
            info=cfg['TabM']['tabm_source_calibration']
            scales[method]={k:info[k] for k in ('q10','q90','scales','cuts','scale_role','threshold_role')}
        else:
            with progress.measure(method+'_SOURCE_SCALE'):
                scales[method]=source_scales(method,source[method],out,cuts,progress,probes[method])
        scale=np.asarray(scales[method]['scales'])
        require(scale.shape==(3,) and np.isfinite(scale).all() and (scale>=0).all(),
                'SOURCE_SPAN_SCHEMA')
        for pool in POOLS:
            d=data[pool]
            with progress.measure(method+'_'+pool+'_PAIRED_REPLAY'):
                two,three,pred=score_pair(raw[pool],d['s2'],d['s3'],d['q'],scale,cuts)
                if pool=='UNSW_DEV':
                    attack=np.asarray([r['label']==1 for r in d['rows']])
                    require(attack.sum()==72553 and ac.guard(d['q'])[attack].all() and
                            all(int(x[attack,3].sum())==UNSW_ATTACK[method] for x in pred),'UNSW_ATTACK_REPLAY')
                masks=ac.groups(d['rows'])
                for proto,kind in ((6,'TCP'),(17,'UDP')):
                    mask=np.asarray([r['protocol']==proto for r in d['rows']])
                    for label in ('NORMAL','ATTACK'):
                        if (mask&masks[label]).any():
                            masks['protocol:'+kind+' / '+label]=mask&masks[label]
                        for device in sorted({r['device'] for r in d['rows']}):
                            group=mask&masks.get('device:'+device+' / '+label,False)
                            if group.any():
                                masks['device:'+device+' / protocol:'+kind+' / '+label]=group
                for mode,alerts in zip(('RAW','2D','3D'),pred):
                    metrics.extend(dict(method=method,configuration=mode,**x) for x in
                      ac.metrics(pool,d['rows'],alerts,d['views'],d['q'],d['expansion'],
                                 d['population'],group_masks=masks))
                for left,right,a,b in (('RAW','2D',0,1),('RAW','3D',0,2),('2D','3D',1,2)):
                    pairs.extend(dict(method=method,left=left,right=right,**x) for x in
                      ac.paired(pool,d['rows'],pred[a],pred[b],d['views'],d['q'],d['expansion'],
                                group_masks=masks))
                changed[method+'/'+pool]=emit_uid_changes(out,method,pool,d,pred)
                np.savez(out/(method+'_'+pool+'_TRANSFER.npz'),uid=np.asarray(d['ids'],dtype='U64'),
                         raw=raw[pool],two=two,three=three)
    dump(out/'CALIBRATION.json',scales)
    table(out,'METRICS',metrics)
    table(out,'PAIRED',pairs)
    dump(out/'CHANGED_UID_INDEX.json',changed)
    summary=[m for m in metrics if m['head']=='ensemble' and m['guard_stratum']=='ALL' and
             (m['view']=='post_window_primary' and m['group'] in ('NORMAL','ATTACK') or
              m['pool']=='EDGE' and m['group'] in ('NORMAL','HTTP','UDP'))]
    dump(out/'RESULT_INDEX.json',summary)
    dump(out/'ACCEPTANCE.json',dict(status='PASS',method_configurations=5,retraining=False,
          job_id=os.environ['SLURM_JOB_ID'],preflight=artifact(out/'PREFLIGHT.json'),
          metrics=artifact(out/'METRICS.json'),paired=artifact(out/'PAIRED.json'),
          calibration=artifact(out/'CALIBRATION.json')))


def main():
    project,out=map(Path,sys.argv[1:])
    p=Progress(out)
    try:
        require(os.environ['SLURM_JOB_ID'].isdigit() and os.environ['SLURMD_NODENAME'] and
             sys.version_info[:2]==(3,11) and np.__version__=='2.0.1' and not sys.flags.optimize,
             'ACTUAL_FROZEN_COMPUTE_RUNTIME')
        for name,pin in load(HERE/'PACKAGE_MANIFEST.json')['files'].items():
            checked(HERE/name,pin)
        transfer(project/'runs',out,p)
        p('COMPLETE',1,1)
    except Exception as e:
        dump(out/'FAILURE_heads.json',dict(status='ENGINEERING_STOP',error=str(e),
                traceback=traceback.format_exc()))
        raise


if __name__=='__main__':
    main()
