"""Existing-artifact diagnostics only: no training, encoder, distance search or fitting."""
import os
for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[key]='1'
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import time
import numpy as np

HERE=Path(__file__).resolve().parent
PINS={}
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,d):
    p=Path(p);tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8');tmp.replace(p)
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
    return h.hexdigest()
def pin(p,expected=None):
    p=Path(p);v=sha(p)
    if expected is not None:assert v==expected,'SHA:'+str(p)
    PINS[str(p)]=v
    return p
def progress(out,stage,done=0,total=1,**kw):
    write(out,dict(stage=stage,done=done,total=total,updated_utc=datetime.now(timezone.utc).isoformat(),**kw))
def ensemble(x):return np.stack([x[:,j] for j in range(3)]).mean(0,dtype=np.float64)
def corrected(raw,s,q,f,p):
    x=raw.copy();g=s.copy() if p==1 else np.where(s>0,1.-np.power(1.-s,3),0.)
    for j,scale in enumerate(f['calibration']['scales']['scales']):
        x[g>0,j]=raw[g>0,j]-(.25*scale)*g[g>0]
    guard=(q[:,0]==1)&(q[:,2]==1)&(q[:,5]==0);x[guard]=raw[guard]
    cuts=f['calibration']['cuts'];pred=np.column_stack((x>cuts['cuts'],ensemble(x)>cuts['ensemble_cut']))
    return x,pred
def quant(x):
    x=np.asarray(x);assert np.isfinite(x).all(),'NONFINITE'
    return dict(zip(('min','p01','p10','p50','p90','p99','max'),map(float,np.quantile(x,[0,.01,.1,.5,.9,.99,1])))) if x.size else None
def auc(negative,positive):
    if not len(negative) or not len(positive):return None
    n=np.sort(negative);left=np.searchsorted(n,positive,'left');right=np.searchsorted(n,positive,'right')
    return float(np.sum((left+right)*.5)/(len(n)*len(positive)))
def strata(q):
    flags=np.sum(q[:,1:10].astype(np.int64)*(1<<np.arange(9)),axis=1)
    return np.asarray(['UDP' if row[0]==0 else 'SYN_NO_ACK' if f&2 and not f&16 else
        'RST' if f&4 else 'FIN' if f&1 else 'PSH_ACK' if f&8 and f&16 else
        'ACK_ONLY' if f==16 else 'OTHER_TCP' for row,f in zip(q,flags)])
def feature_stats(e3,q,norm):
    n=len(q);norms=np.empty(n);maxabs=np.empty(n);extreme=np.empty(n);means=np.zeros(768);squares=np.zeros(768)
    for a in range(0,n,1024):
        z=np.asarray(e3[a:a+1024,:768],dtype=np.float64);assert np.isfinite(z).all()
        means+=z.sum(0);squares+=(z*z).sum(0);v=(z-norm[0])/norm[1]
        norms[a:a+len(z)]=np.linalg.norm(v,axis=1);maxabs[a:a+len(z)]=np.abs(v).max(1)
        extreme[a:a+len(z)]=(np.abs(v)>10).mean(1)
    return dict(normalized_l2=norms,normalized_maxabs=maxabs,normalized_fraction_abs_gt10=extreme,
        e3_mean=means/max(1,n),e3_sd=np.sqrt(np.maximum(0,squares/max(1,n)-(means/max(1,n))**2)))
def summarize(name,rows,q,e3,raw,s,preds,f,norm,keep,extra=None):
    assert q.shape==(len(rows),14) and raw.shape==(len(rows),3) and s.shape==(len(rows),)
    assert np.isfinite(q).all() and np.all((q>=0)&(q<=1)) and np.isfinite(raw).all()
    assert np.isfinite(s).all() and np.all((s>=0)&(s<=1))
    proto=np.asarray([r['protocol'] for r in rows]);assert np.all((proto==6)|(proto==17))
    assert np.array_equal(q[:,0],(proto==6).astype(q.dtype)),'Q_PROTOCOL'
    assert np.all(q[proto==17,1:10]==0),'UDP_TCP_FLAGS'
    recomputed={};corrected_scores={}
    for method,p,support in [('RAW',1,np.zeros(len(s))),('C5_P1',1,s),('C5_P3',3,s)]:
        x,pred=corrected(raw,support,q,f,p);assert np.array_equal(pred,preds[method]),'DECISIONS:'+method
        recomputed[method]=pred;corrected_scores[method]=np.column_stack((x,ensemble(x)))
    assert not np.any(preds['C5_P3']&~preds['RAW']),'ADDED_RAW_ALARM'
    ids=[r['uid'] for r in rows];assert len(set(ids))==len(ids),'DUPLICATE_UID'
    keep=np.asarray(keep,dtype=np.int64);assert len(np.unique(keep))==len(keep)
    roles=np.asarray([r['source_role'] if 'source_role' in r else ('NORMAL' if r['label']==0 else 'ATTACK') for r in rows])
    kinds=strata(q);stats=feature_stats(e3,q,norm)
    result=dict(dataset=name,rows_full=len(rows),rows_primary=len(keep),all_full_decisions_exact=True,
        q14_protocol_consistent=True,new_training=0,new_encoding=0,new_distance=0,new_model_forward=0,
        definitions=dict(rate='Unweighted fixed selected-query descriptive rate; not population HT or event recall',
            strata='UDP, then SYN_NO_ACK, RST, FIN, PSH_ACK, ACK_ONLY, OTHER_TCP; same diagnostic definition across datasets',
            auc='Descriptive existing-score AUROC against same-protocol normal primary queries; no threshold fit',
            input_boundary='Saved encoded inputs audited. Does not independently establish raw-packet-to-encoder semantic correctness.'),
        groups={},extra=extra or {})
    cuts=np.array(f['calibration']['cuts']['cuts']+[f['calibration']['cuts']['ensemble_cut']])
    for role in sorted(set(roles[keep])):
        for kind in ['ALL']+sorted(set(kinds[keep][roles[keep]==role])):
            ix=keep[(roles[keep]==role)&((kinds[keep]==kind) if kind!='ALL' else True)]
            if not len(ix):continue
            v=dict(rows=len(ix),protocol_counts=dict(Counter(map(str,proto[ix]))),
                q14_quantiles=[quant(q[ix,j]) for j in range(14)],support=quant(s[ix]),
                support_zero_rows=int((s[ix]==0).sum()),support_gt_half_rows=int((s[ix]>.5).sum()),
                unique_q14_rows=int(len(np.unique(q[ix],axis=0))),
                component_count=len({rows[int(i)]['component_id'] for i in ix}),
                feature={k:quant(stats[k][ix]) for k in ('normalized_l2','normalized_maxabs','normalized_fraction_abs_gt10')},heads={})
            for j,head in enumerate(('27','127','227','ensemble')):
                r=preds['RAW'][ix,j];p=preds['C5_P3'][ix,j];withdrawn=r&~p
                values=corrected_scores['RAW'][ix,j];margin=values-cuts[j]
                drop=values-corrected_scores['C5_P3'][ix,j]
                normal_ix=keep[(roles[keep]=='NORMAL')&np.isin(proto[keep],np.unique(proto[ix]))]
                v['heads'][head]=dict(raw_alarm_count=int(r.sum()),p1_alarm_count=int(preds['C5_P1'][ix,j].sum()),
                    p3_alarm_count=int(p.sum()),raw_rate=float(r.mean()),p1_rate=float(preds['C5_P1'][ix,j].mean()),p3_rate=float(p.mean()),
                    p3_withdrawn=int(withdrawn.sum()),fraction_raw_alarms_withdrawn=float(withdrawn.sum()/r.sum()) if r.sum() else None,
                    raw_score=quant(values),raw_threshold_margin=quant(margin),p3_score_drop=quant(drop),
                    withdrawn_support=quant(s[ix][withdrawn]),withdrawn_raw_margin=quant(margin[withdrawn]),
                    auc_vs_same_protocol_normal=auc(corrected_scores['RAW'][normal_ix,j],values) if role!='NORMAL' else None)
            result['groups'][role+'/'+kind]=v
    result['feature_mean']=stats['e3_mean'].tolist();result['feature_sd']=stats['e3_sd'].tolist()
    return result

def load_ab(root,pool,out):
    progress(out/'AB_PROGRESS.json','VERIFY_'+pool)
    freeze=read(root/'runs/c5_method_freeze_v1_20261102/METHOD_FREEZE.json')
    spec=read(root/'runs/history_sample_coverage_c4_batch_resume_v1_20261102/config/ASSETS.json')
    def asset(x):return pin(root/x['path'],x['sha256'])
    qspec=spec['pools'][pool]['query']
    with gzip.open(asset(qspec['rows']),'rt',encoding='utf-8') as stream:rows=[json.loads(line) for line in stream]
    ids=[r['uid'] for r in rows]
    assert read(asset(qspec['q_uids']))==read(asset(qspec['feature_uids']))==ids
    q=np.load(asset(qspec['q14']),mmap_mode='r',allow_pickle=False)
    e3=np.load(asset(qspec['e3']),mmap_mode='r',allow_pickle=False)
    rp=root/f'runs/c5_kernel_independent_replay_codex_20261102/ab/{pool}_REPLAY.npz'
    with np.load(pin(rp,freeze['immutable_asset_pins'][rp.relative_to(root).as_posix()]['sha256']),allow_pickle=False) as z:
        assert z['uid'].tolist()==ids;keep=z['primary_indices'].copy();s=z['kernel_support'][0].copy()
        names=z['candidate_names'].tolist();p1=z['decisions'][names.index('1')].copy();p3=z['decisions'][names.index('3')].copy()
    with np.load(asset(qspec['logits']),allow_pickle=False) as z:
        assert z['uid'].tolist()==ids;raw=z['head'].astype(np.float64)
    with np.load(asset(spec['calibration']['normalizer']),allow_pickle=False) as z:norm=(z['mean'].copy(),z['scale'].copy())
    _,rawpred=corrected(raw,np.zeros(len(s)),q,freeze,1)
    progress(out/'AB_PROGRESS.json','COMPARE_'+pool,0,len(keep))
    result=summarize(pool,rows,q,e3,raw,s,dict(RAW=rawpred,C5_P1=p1,C5_P3=p3),freeze,norm,keep,
        dict(evidence_role='CONSUMED_DEVELOPMENT_ONLY',reference_mode='commissioning_plus_historical_references',
             historical_support_source='Saved verified float64 support; distances not recomputed'))
    write(out/(pool+'_DIAGNOSIS.json'),result)
    progress(out/'AB_PROGRESS.json','COMPLETE_'+pool,len(keep),len(keep))

def load_edge(root,source,out,preflight=False):
    state=out/('PREFLIGHT_PROGRESS.json' if preflight else 'EDGE_PROGRESS.json')
    progress(state,'VERIFY_EDGE')
    enc=read(pin(source/'encoded/COMPLETE.json','7b0ffe2288281e8b15d91d8955392710f747604d051ce248b053f7ab9266ca01'))
    report=read(pin(source/'evaluation/METRICS.json','df53579503268da97ef7041102988e61995f3e5356c9200e08678686cdb2c4f8'))
    freeze=read(pin(root/'runs/c5_method_freeze_v1_20261102/METHOD_FREEZE.json','ee11f25079cd03ee8b9d6dbbafd67e7fc96dd4402373808fc1c0b9f53b5c05e7'))
    paths=sorted((source/'evaluation/chunks').glob('q*/MANIFEST.json'))
    assert len(paths)==469,'RESULT_CHUNKS'
    if preflight:paths=paths[:1]
    result_ids=[];all_data={k:[] for k in ('raw_scores','support','RAW','C5_P1','C5_P3')}
    for k,path in enumerate(paths):
        manifest=read(pin(path));payload=pin(path.parent/'RESULT.npz',manifest['sha256'])
        result_ids.extend(manifest['uids'])
        with np.load(payload,allow_pickle=False) as z:
            for name in all_data:all_data[name].append(z[name].copy())
        if k%25==0:progress(state,'VERIFY_SCORES',k+1,len(paths))
    all_data={k:np.concatenate(v) for k,v in all_data.items()};assert len(result_ids)==len(set(result_ids))
    if not preflight:assert set(result_ids)==set(report['ordered_query_uids']) and len(result_ids)==60000
    index={u:i for i,u in enumerate(result_ids)};rows=[None]*len(index)
    e3=np.empty((len(index),768),np.float32);q=np.empty((len(index),14),np.float32)
    reference_protocols=Counter();shapes=Counter();done=0
    plan=read(source/'BATCH_PLAN.json');planitems=plan['batches'] if isinstance(plan,dict) and 'batches' in plan else plan
    # Shape evidence is taken from the saved batch plan when its structure exposes entries.
    shape_by_uid={}
    if isinstance(planitems,list):
        for entry in planitems:
            if isinstance(entry,dict) and 'shape' in entry:
                for uid in entry.get('uids',[]):shape_by_uid[uid]=entry['shape']
    for k,b in enumerate(enc['batches']):
        if preflight and not set(b['uids'])&set(index):continue
        base=source/'encoded/batches'/b['batch_id'];manifest=read(pin(base/'MANIFEST.json',b['manifest_sha256']))
        for name,v in manifest['files'].items():pin(base/name,v['sha256'])
        rr=read(base/'rows.json');assert [r['uid'] for r in rr]==b['uids']
        z=np.load(base/'E3.npy',allow_pickle=False);qq=np.load(base/'q14.npy',allow_pickle=False)
        assert z.shape==(len(rr),768) and qq.shape==(len(rr),14) and np.isfinite(z).all()
        for i,r in enumerate(rr):
            if r['uid'] in index:
                j=index[r['uid']];assert rows[j] is None;rows[j]=r;e3[j]=z[i];q[j]=qq[i];done+=1
                if r['uid'] in shape_by_uid:shapes[(r['source_role'],str(shape_by_uid[r['uid']]))]+=1
            else:reference_protocols[str(r['protocol'])]+=1
        if k%40==0:progress(state,'VERIFY_ENCODING',k+1,len(enc['batches']),queries_loaded=done)
    assert all(r is not None for r in rows),'QUERY_FEATURE_COVERAGE'
    spec=read(root/'runs/history_sample_coverage_c4_batch_resume_v1_20261102/config/ASSETS.json')
    v=spec['calibration']['normalizer']
    with np.load(pin(root/v['path'],v['sha256']),allow_pickle=False) as z:norm=(z['mean'].copy(),z['scale'].copy())
    progress(state,'COMPARE_THREE_LAYERS',done,len(rows))
    result=summarize('EDGE',rows,q,e3,all_data['raw_scores'],all_data['support'],
        {k:all_data[k] for k in ('RAW','C5_P1','C5_P3')},freeze,norm,np.arange(len(rows)),
        dict(evidence_role='POST_FREEZE_EXTERNAL',reference_mode='commissioning_only',
            reference_protocol_counts=dict(reference_protocols),query_shapes={str(k):v for k,v in shapes.items()},preflight=preflight))
    if not preflight:
        for method in ('RAW','C5_P1','C5_P3'):
            for j,head in enumerate(('27','127','227','ensemble')):
                for role in ('NORMAL','HTTP','UDP'):
                    ix=np.array([r['source_role']==role for r in rows])
                    assert int(all_data[method][ix,j].sum())==report['methods'][method]['heads'][head]['roles'][role]['alarm_count'],'METRICS_RECOUNT'
    write(out/('PREFLIGHT_RESULT.json' if preflight else 'EDGE_DIAGNOSIS.json'),result)
    progress(state,'PASS',len(rows),len(rows))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['ab','edge','preflight'],required=True)
    parser.add_argument('--root',type=Path,required=True);parser.add_argument('--source',type=Path);parser.add_argument('--out',type=Path,required=True)
    a=parser.parse_args();a.out.mkdir(parents=True,exist_ok=True);start=time.monotonic()
    try:
        if a.mode=='ab':
            for pool in ('CIC_DEV','UNSW_DEV'):load_ab(a.root,pool,a.out)
        else:load_edge(a.root,a.source,a.out,preflight=a.mode=='preflight')
        # Recheck scientific anchors after reading; per-array hashes are recorded without changing source files.
        write(a.out/(a.mode.upper()+'_INPUT_SHA.json'),dict(files=PINS,seconds=time.monotonic()-start,source_writes=0))
        write(a.out/(a.mode.upper()+'_COMPLETE.json'),dict(status='PASS',seconds=time.monotonic()-start,
            files={p.name:sha(p) for p in a.out.glob('*DIAGNOSIS.json')},model_forward=0,training=0,threshold_fit=0,
            limitations=['Existing-artifact audit does not fully prove raw replay and encoder semantic equivalence.']))
    except Exception as e:
        write(a.out/(a.mode.upper()+'_STOP.json'),dict(status='FAIL',error=repr(e)));raise

if __name__=='__main__':main()
