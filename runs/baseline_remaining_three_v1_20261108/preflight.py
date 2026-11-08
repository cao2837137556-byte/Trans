"""Metadata-only source split, immutable inputs and actual causal pipeline."""
import collections,gc,json,os,sys,time,traceback
from pathlib import Path
import worker as w
p=w.p;np=w.np;HERE=w.HERE;OLD=w.OLD

def solve(counts,group_ids):
    from scipy.optimize import milp,LinearConstraint,Bounds
    # Exact whole-group assignment; model outputs are never consulted.
    keys=sorted(counts);a=np.asarray([[counts[k].get(g,0) for g in group_ids] for k in keys],dtype=float)
    n=len(group_ids);r=len(keys);total=a.sum(1);b=(a>0).astype(float)
    mat=[];lo=[];hi=[]
    for j,k in enumerate(keys):
        row=np.zeros(n+r);row[:n]=b[j];ng=int(b[j].sum())
        # Every device/class appears on both sides. Protocol strata with only
        # one independent group remain in training and are explicitly reported.
        if ng>=2:mat.append(row);lo.append(1);hi.append(ng-1)
        elif k[2]!='ALL':mat.append(row);lo.append(0);hi.append(0)
        else:raise RuntimeError('DEVICE_CLASS_SINGLE_GROUP:'+str(k))
        row=np.zeros(n+r);row[:n]=a[j]/total[j];row[n+j]=-1;mat.append(row);lo.append(-np.inf);hi.append(.2)
        row=np.zeros(n+r);row[:n]=-a[j]/total[j];row[n+j]=-1;mat.append(row);lo.append(-np.inf);hi.append(-.2)
    objective=np.r_[np.arange(1,n+1)*1e-9,np.ones(r)]
    result=milp(objective,integrality=np.r_[np.ones(n),np.zeros(r)],bounds=Bounds(np.zeros(n+r),np.r_[np.ones(n),np.full(r,np.inf)]),constraints=LinearConstraint(np.asarray(mat),lo,hi),options={'time_limit':120,'mip_rel_gap':1e-7})
    assert result.x is not None and result.success,'SOURCE_GROUP_COVERAGE_INFEASIBLE:'+str(result.message)
    chosen={group_ids[i] for i in range(n) if result.x[i]>.5}
    report=[]
    for k,row in zip(keys,a):
        valid=int(sum(v for g,v in counts[k].items() if g in chosen));train=int(row.sum()-valid)
        assert train>0 and (valid>0 or len(counts[k])==1)
        report.append(dict(device=k[0],label=k[1],protocol=k[2],groups=len(counts[k]),train=train,validation=valid,unavoidable_single_group=len(counts[k])==1))
    return chosen,report

def split():
    p.bootstrap();import inputs,context_core as k
    rows,z,q,ctx=inputs.source_role('LEARN');fit=np.load(p.SOURCE/'metadata/FIT.npy');del z,q,ctx;gc.collect()
    assert k.c.uid_sha(rows[int(i)]['uid'] for i in fit)==p.read(p.TRAIN/'TRAINING_SPEC_FROZEN.json')['data_identity']['FIT']['uid_sha256']
    spec=p.read(w.f.OLD/'SOURCE_RESULT.json');source=w.f.OLD/'artifacts/source';assert p.sha(source/'GROUP_ID.npy')==spec['sha256']['GROUP_ID.npy'];groups=np.load(source/'GROUP_ID.npy');x,y=w.f.source(False)
    counts=collections.defaultdict(collections.Counter);links={}
    for j,i in enumerate(fit):
        r=rows[int(i)];g=int(groups[j]);d=str(r['device']);label=int(r['label']);assert label==int(y[j])
        for proto in ('ALL',str(r.get('protocol',''))):counts[(d,label,proto)][g]+=1
        for f in ('capture_id','session_id','component_id'):
            v=str(r.get(f,''))
            if v not in ('','None','nan'):
                key=(d,f,v);assert key not in links or links[key]==g,'SOURCE_GROUP_IDENTITY';links[key]=g
    chosen,report=solve(counts,sorted(set(map(int,groups))));valid=np.isin(groups,sorted(chosen));dest=HERE/'artifacts';dest.mkdir(exist_ok=True);np.save(dest/'INNER_VALID.npy',valid)
    result=dict(status='PASS',group_ids=sorted(chosen),train_rows=int((~valid).sum()),valid_rows=int(valid.sum()),strata=report,mask_sha256=p.sha(dest/'INNER_VALID.npy'),capture_session_component_disjoint=True,selection='ordinary source validation accuracy; same patience16 for TabM/TabR; final refit entire FIT',train_uid_sha256=k.c.uid_sha(rows[int(fit[j])]['uid'] for j in np.flatnonzero(~valid)),valid_uid_sha256=k.c.uid_sha(rows[int(fit[j])]['uid'] for j in np.flatnonzero(valid)),targets_used=False)
    p.write('SPLIT_RESULT.json',result);return result

def prepare():
    w.init();p.progress('REAL_CAUSAL_PIPELINE');r=p.pipeline();p.write('PIPELINE_RESULT.json',r)
    src=OLD/'artifacts/evaluation';dest=HERE/'artifacts/evaluation';dest.mkdir(parents=True,exist_ok=True);spec=p.read(OLD/'EVALUATION_INPUTS.json')
    for pool,v in spec['pools'].items():
        for suffix,key in [('_X.npy','x_sha256'),('_ROWS.json','rows_sha256')]:
            a=src/(pool+suffix);assert p.sha(a)==v[key];b=dest/a.name
            if not b.exists():b.symlink_to(a)
        if pool!='EDGE':
            a=src/(pool+'_VIEWS.npz');b=dest/a.name
            if not b.exists():b.symlink_to(a)
    p.write('EVALUATION_INPUTS.json',spec)
    # Disent is independent of supervised early stopping; do not hold its
    # resource/training chain behind a later split failure.
    import controller
    controller.submit('DisentAD')
    p.progress('SOURCE_GROUP_SPLIT');split()
    controller.submit('TabM');controller.submit('TabR')
    p.write('PREFLIGHT_COMPLETE.json',dict(status='PASS',main_model_changed=False))

if __name__=='__main__':
    try:prepare()
    except Exception as e:p.HERE=HERE;p.write('PREFLIGHT_STOP.json',dict(status='STOP',error=str(e),traceback=traceback.format_exc()));raise
