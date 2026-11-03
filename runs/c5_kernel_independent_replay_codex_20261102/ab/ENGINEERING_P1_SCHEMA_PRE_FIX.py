"""Isolated C5 arithmetic audit of saved C4 arrays; no encoder or production writes."""
import os
for _k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[_k]='1'
import gc
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
from collections import Counter
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
C4=ROOT/'runs/history_sample_coverage_c4_batch_resume_v1_20261102'
HEADS=('27','127','227','ensemble')
CANDIDATES=(1,2,3,4,'saturation')
PINS={}

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for b in iter(lambda:stream.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def pin(path,expected=None):
    path=Path(path);actual=sha(path)
    if expected is not None:assert actual==expected,(str(path),actual,expected)
    PINS[str(path.relative_to(ROOT)).replace('\\','/')]=actual
    return path

def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def write(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,allow_nan=False,indent=2)+'\n',encoding='utf-8')
    temp.replace(path)

def progress(stage,**extra):
    value=dict(stage=stage,elapsed_seconds=time.monotonic()-START);value.update(extra)
    write(HERE/'PROGRESS.json',value)
    print(stage,json.dumps(extra,ensure_ascii=False),flush=True)

FIELDS=('uid','label','device','activity','annotation_id','protocol','capture_id','session_id',
        'component_id','label_metric_weight_denominator','timestamp','frame')
def metadata(path):
    with gzip.open(path,'rt',encoding='utf-8') as stream:
        return [{k:r[k] for k in FIELDS if k in r} for r in map(json.loads,stream)]

def support_map(s,p):
    s=np.asarray(s,dtype=np.float64)
    assert np.isfinite(s).all() and np.all((s>=0)&(s<=1))
    # p=1 is the exact identity; avoid needless cancellation at tiny support.
    if p==1:return s.copy()
    g=np.zeros_like(s);active=s>0
    g[active]=1. if p=='saturation' else 1.-np.power(1.-s[active],p)
    assert np.all(g>=s) and np.all(g<=1) and np.all(g[~active]==0)
    return g

def calculate(raw,s,guard,scales,cuts,p):
    g=support_map(s,p);x=np.asarray(raw,dtype=np.float64).copy();active=g>0
    for j in range(3):
        x[active,j]=raw[active,j]-(.25*scales[j])*g[active]
    x[guard]=raw[guard]
    # Frozen ordered ensemble uses seed-major mean, not N x 3 row reduction.
    ens=np.stack([x[:,j] for j in range(3)]).mean(0,dtype=np.float64)
    pred=np.column_stack([x>np.asarray(cuts['cuts']),ens>cuts['ensemble_cut']])
    return x,pred,g

def protection(report):
    failures=[];missing=[]
    for kind,budget in (('device',1.),('attack_type',5.),('annotation',5.)):
        for item in report['groups'][kind]:
            b=item['base']['attack'];a=item['corrected']['attack']
            if b['rows']==0:continue
            identity='|'.join(item['group'].values())
            raw_recall=b['weighted_rate'];loss=item['attack_recall_loss_pp']
            if raw_recall is None or loss is None:
                missing.append(kind+':'+identity);continue
            if loss>budget+1e-12:failures.append(kind+'_WITHDRAWAL_BUDGET:'+identity)
            if raw_recall<.99 and b['positive']>a['positive']:
                failures.append(kind+'_RAW_BELOW_99_REQUIRES_ZERO_WITHDRAWAL:'+identity)
    return dict(schema='history-normal-reference-protection-v1',
        status='FAIL' if failures else 'NOT_EVALUABLE' if missing else 'PASS',
        failures=failures,missing=missing,pool_epsilon_enforced=False,
        device_loss_budget_pp=1.,activity_annotation_loss_budget_pp=5.,
        low_raw_recall_zero_tp_withdrawal=True,
        group_fields={'device':['device'],'attack_type':['activity'],'annotation':['annotation_id']})

def macro(report):
    n=[g['corrected']['normal']['rate'] for g in report['groups']['device']
       if g['corrected']['normal']['rows']]
    a=[g['corrected']['attack']['rate'] for g in report['groups']['device']
       if g['corrected']['attack']['rows']]
    return dict(device_macro_sample_fpr=float(np.mean(n)) if n else None,
                device_macro_sample_recall=float(np.mean(a)) if a else None)

def flags(q):return np.sum(q[:,1:10].astype(np.int64)*(1<<np.arange(9)),axis=1)

def breakdown(rr,ix,weights,q,raw,old,new,g,p):
    records=[]
    for i in np.flatnonzero(ix):
        r=rr[int(i)];f=int(flags(q[int(i):int(i)+1])[0])
        records.append(dict(**r,tcp_flags=f,guard=bool(q[i,0]==1 and q[i,2]==1 and q[i,5]==0),
            normal_reference_support=float(SUPPORT[i]),kernel_support=float(g[i]),
            raw_logits=raw[i].tolist(),c4_detected=old[i].tolist(),
            candidate_detected=new[i].tolist(),primary_weight=float(weights[i]),candidate=str(p)))
    groups={k:dict(Counter(str(r.get(k,'NOT_AVAILABLE')) for r in records))
            for k in ('device','activity','protocol','tcp_flags','capture_id','annotation_id')}
    return records,dict(rows=len(records),weighted_attack_mass=math.fsum(weights[ix]),groups=groups)

def main():
    global START,SUPPORT
    START=time.monotonic()
    assert not (HERE/'RESULT.json').exists(),'OUTPUT_EXISTS'
    pin(Path(__file__))
    for name in ('20261102_c5_kernel_decision_claude.md','20261102_unweighted_fpr_convergence_claude.md'):
        pin(ROOT/'runs/mainline_docs/collab'/name)
    spec=read(pin(C4/'config/ASSETS.json'))
    def asset(item):return pin(ROOT/item['path'],item['sha256'])
    cuts=read(asset(spec['calibration']['cuts']));scale_spec=read(asset(spec['calibration']['scales']))
    scales=np.asarray(scale_spec['scales'],dtype=np.float64)
    assert cuts['seeds']==[27,127,227] and scale_spec['seed_order']==[27,127,227]
    assert cuts['moved'] is False
    metric_path=pin(ROOT/'runs/dense_reference_ab_stage_candidate_v1_20261028/src/metrics.py')
    loader=importlib.util.spec_from_file_location('_c5_frozen_metrics_only',metric_path)
    metrics=importlib.util.module_from_spec(loader);loader.loader.exec_module(metrics)
    saved_result=read(pin(C4/'outputs/evaluation/RESULT.json'))
    pin(C4/'FINAL_ACCEPTANCE.json')
    result={'schema':'C5_INDEPENDENT_C4_ARRAY_REPLAY_V1','evidence':'CONSUMED_DEVELOPMENT_DIAGNOSTIC_ONLY',
        'candidate_order':list(CANDIDATES),'lambda':.25,'support_source':'saved C4 support; second_joint absent in DECISIONS',
        'p1_identity_special_case':True,'new_model_forwards':0,'new_AB_distances':0,'remote_calls':0,
        'production_assets_modified':False,'pools':{},'dev':{},'p_selection':'Report only; no A/B-based p selection'}
    for pool in ('CIC_DEV','UNSW_DEV'):
        progress('LOAD_POOL',pool=pool)
        ps=spec['pools'][pool];rr=metadata(asset(ps['query']['rows']))
        qp=asset(ps['query']['q14']);q=np.load(qp,mmap_mode='r',allow_pickle=False)
        ids=read(asset(ps['query']['q_uids']))
        assert ids==[r['uid'] for r in rr]
        with np.load(pin(C4/f'outputs/evaluation/ab/{pool}/DECISIONS.npz'),allow_pickle=False) as z:
            fields=z.files;z={k:z[k].copy() for k in fields}
        assert z['uid'].tolist()==ids and len(set(ids))==len(ids)
        assert 'second_joint' not in fields
        raw=z['raw_logits'];SUPPORT=z['support']
        eligible=z['eligible'];guard=(q[:,0]==1)&(q[:,2]==1)&(q[:,5]==0)
        assert np.array_equal(guard,z['guard']) and np.all(SUPPORT[~eligible]==0)
        raw_dec=calculate(raw,np.zeros(len(rr)),guard,scales,cuts,1)[1]
        assert np.array_equal(raw_dec,z['base'])
        keep=np.flatnonzero(metrics.post_window_mask(rr,ps['windows']))
        normal=np.asarray([r['label']==0 for r in rr]);attack=~normal
        full_w=metrics.validate_full_weights(rr,pool)
        primary_rows=[rr[int(i)] for i in keep];primary_w=metrics.hierarchical_weights(primary_rows,pool)
        primary_full_weights=np.zeros(len(rr));primary_full_weights[keep]=primary_w
        views={'full':(np.arange(len(rr)),rr,full_w),
               'post_window_primary':(keep,primary_rows,primary_w)}
        for view,(ix,subset,w) in views.items():
            saved=saved_result['pools'][pool]['views'][view]
            uh=hashlib.sha256(('\n'.join(r['uid'] for r in subset)+'\n').encode()).hexdigest()
            assert uh==saved['retained_uid_sha256']
            assert hashlib.sha256(w.tobytes()).hexdigest()==saved['weights_sha256']
        pool_result={'rows':len(rr),'npz_fields':fields,'guarded_attack_rows':int((attack&guard).sum()),
                     'unguarded_attack_rows':int((attack&~guard).sum()),'candidates':{}}
        candidate_preds=[];candidate_support=[]
        for p in CANDIDATES:
            progress('REPLAY',pool=pool,candidate=str(p))
            x,pred,g=calculate(raw,SUPPORT,guard,scales,cuts,p)
            assert not np.any(~z['corrected']&pred),'NEW_NORMAL_OR_ATTACK_ALARM_IMPOSSIBLE'
            if p==1:
                assert np.array_equal(x,z['corrected_logits']) and x.tobytes()==z['corrected_logits'].tobytes(),'P1_LOGITS_NOT_EXACT'
                assert np.array_equal(pred,z['corrected']),'P1_DECISIONS_NOT_EXACT'
            cr={'views':{},'added_attack_vs_C4':{},'new_normal_alarms_vs_C4':int((normal[:,None]&~z['corrected']&pred).sum())}
            for view,(ix,subset,w) in views.items():
                reports={}
                for j,head in enumerate(HEADS):
                    rep=metrics.report(subset,z['base'][ix,j],pred[ix,j],w,eligible[ix],g[ix])
                    rep['protection']=protection(rep)
                    rep['macro_sample']=macro(rep)
                    if p==1:
                        old=saved_result['pools'][pool]['views'][view]['reports'][head]
                        assert all(rep[k]==old[k] for k in old),'P1_METRIC_REPLAY:'+pool+view+head
                    added=attack[ix]&z['corrected'][ix,j]&~pred[ix,j]
                    rep['new_attack_misses_vs_C4']=int(added.sum())
                    rep['new_attack_misses_weight_vs_C4']=math.fsum(w[added])
                    reports[head]=rep
                cr['views'][view]={'rows':len(ix),'reports':reports}
            for j,head in enumerate(HEADS):
                ix=attack&z['corrected'][:,j]&~pred[:,j]
                records,summary=breakdown(rr,ix,primary_full_weights,q,raw,z['corrected'],pred,g,p)
                cr['added_attack_vs_C4'][head]=summary
                if records:
                    with gzip.open(HERE/f'{pool}_p{p}_{head}_new_attack_misses.jsonl.gz','wt',encoding='utf-8') as f:
                        for record in records:f.write(json.dumps(record,ensure_ascii=False)+'\n')
            candidate_preds.append(pred);candidate_support.append(g)
            pool_result['candidates'][str(p)]=cr
        np.savez_compressed(HERE/f'{pool}_REPLAY.npz',uid=z['uid'],candidate_names=np.asarray([str(p) for p in CANDIDATES]),
            decisions=np.stack(candidate_preds),kernel_support=np.stack(candidate_support),guard=guard,
            full_weights=full_w,primary_indices=keep,primary_weights=primary_w)
        pool_result['p1_logits_decisions_and_reports_bit_exact']=True
        result['pools'][pool]=pool_result
        write(HERE/'PARTIAL_RESULT.json',result)
        del rr,q,z,raw,ids,primary_rows,pred,x,g,candidate_preds,candidate_support,views
        gc.collect()
    progress('HIST_DEV')
    rr=metadata(pin(C4/'outputs/evaluation/dev/QUERIES.jsonl.gz'))
    with np.load(pin(C4/'outputs/evaluation/dev/DECISIONS.npz'),allow_pickle=False) as zz:z={k:zz[k].copy() for k in zz.files}
    assert z['uid'].tolist()==[r['uid'] for r in rr]
    raw=z['raw_logits'];q=z['q14'];guard=(q[:,0]==1)&(q[:,2]==1)&(q[:,5]==0)
    assert np.array_equal(guard,z['guard']) and all(r['label']==0 for r in rr)
    dev={}
    for p in CANDIDATES:
        x,pred,g=calculate(raw,z['support'],guard,scales,cuts,p)
        if p==1:assert np.array_equal(pred,z['corrected']) and np.array_equal(x,z['corrected_logits'])
        by_device={}
        for d in sorted({r['device'] for r in rr}):
            ix=np.asarray([r['device']==d for r in rr])
            by_device[d]={'rows':int(ix.sum()),'fp_by_head':dict(zip(HEADS,pred[ix].sum(0).astype(int).tolist()))}
        dev[str(p)]={'rows':len(rr),'fp_by_head':dict(zip(HEADS,pred.sum(0).astype(int).tolist())),
                     'sample_fpr_by_head':dict(zip(HEADS,(pred.mean(0)).tolist())),'devices':by_device}
    gap=dev['1']['fp_by_head']['ensemble']-dev['saturation']['fp_by_head']['ensemble']
    result['dev']={'candidates':dev,'p1_to_saturation_ensemble_recoverable_rows':gap,
                  'successive_ensemble_improvements':[
                      {'from':p,'to':p+1,'fp_removed':dev[str(p)]['fp_by_head']['ensemble']-dev[str(p+1)]['fp_by_head']['ensemble'],
                       'fraction_of_p1_to_saturation_gap':(dev[str(p)]['fp_by_head']['ensemble']-dev[str(p+1)]['fp_by_head']['ensemble'])/gap if gap else None}
                      for p in (1,2,3)],
                  'rule_provenance':'5% stopping rule was introduced after A/B outcomes were already known; report every registered p.'}
    summary={}
    for p in CANDIDATES:
        gates=[];pools={}
        for pool in ('CIC_DEV','UNSW_DEV'):
            cr=result['pools'][pool]['candidates'][str(p)]
            for view,vr in cr['views'].items():
                for head,rep in vr['reports'].items():
                    gates.append({'pool':pool,'view':view,'head':head,**rep['protection']})
            main=cr['views']['post_window_primary']['reports']['ensemble']
            pools[pool]={'normal':main['corrected']['normal'],'attack':main['corrected']['attack'],
                         'macro_sample':main['macro_sample'],'new_misses_vs_C4':main['new_attack_misses_vs_C4']}
        summary[str(p)]={'gate_passes':sum(g['status']=='PASS' for g in gates),'gate_count':len(gates),
            'all_16_gates_pass':all(g['status']=='PASS' for g in gates),'gates':gates,'primary_ensemble':pools}
    result['summary']=summary
    for rel,digest in PINS.items():assert sha(ROOT/rel)==digest,'INPUT_MODIFIED:'+rel
    result['input_sha256']=PINS;result['elapsed_seconds']=time.monotonic()-START
    result['status']='PASS_INDEPENDENT_REPLAY_COMPLETED'
    write(HERE/'RESULT.json',result)
    write(HERE/'SUMMARY.json',{'status':result['status'],'summary':summary,'dev':result['dev'],
        'p1_bit_exact_both_pools':True,'input_files_unchanged':True,'input_sha256':PINS})
    progress('COMPLETE',elapsed_seconds=result['elapsed_seconds'])
    print('C5_AB_REPLAY_COMPLETE',flush=True)

if __name__=='__main__':main()
