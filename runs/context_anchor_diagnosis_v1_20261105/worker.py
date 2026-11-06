"""Read-only context contribution and source-FIT objective conflict diagnosis."""
import argparse,gc,hashlib,importlib.util,json,sys,time,traceback
from pathlib import Path
import numpy as np
import psutil
import torch
import analysis_core as ac
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
EVAL=ROOT/'runs/fusion_anchor_evaluation_v1_20261105'
TRAIN=ROOT/'runs/fusion_score_anchor_v2_20261105'
PHASE='PREFLIGHT';PEAK=0

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
    return h.hexdigest()
def write(n,v):
    p=HERE/n;t=p.with_suffix('.tmp');t.write_text(json.dumps(v,indent=2,allow_nan=False));t.replace(p)
def progress(stage,done=0,total=1,**kw):
    global PEAK
    PEAK=max(PEAK,psutil.Process().memory_info().rss);assert PEAK<7*2**30,'MEMORY_LIMIT'
    write(PHASE+'_PROGRESS.json',dict(stage=stage,done=int(done),total=int(total),rss_mib=PEAK/2**20,updated_unix=time.time(),**kw))
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def initialize():
    for n,h in read(HERE/'.private.json')['pins'].items():assert sha(HERE/n)==h,'DELIVERY:'+n
    for n,h in read(HERE/'INPUT_PINS.json').items():assert sha(ROOT/n)==h,'INPUT:'+n
    ev=module('frozen_evaluation',EVAL/'worker.py');ev.progress=progress
    c,k,norm,arms,inputs,context,metrics,reporting=ev.initialize()
    context.progress=inputs.progress=c.progress=progress
    return ev,c,k,norm,arms,inputs,context,metrics,reporting

def cohort_indices(rows,keep):
    result={'pool':np.asarray(keep)}
    for field in ['label','protocol','device','source_role']:
        for value in sorted({str(rows[i][field]) for i in keep}):
            result[field+':'+value]=np.asarray([i for i in keep if str(rows[i][field])==value],dtype=np.int64)
    # Role/label split avoids hiding benign UDP inside the protocol group.
    for key in sorted({(str(rows[i]['label']),str(rows[i]['protocol']),rows[i]['source_role']) for i in keep}):
        result['cohort:'+':'.join(key)]=np.asarray([i for i in keep if (str(rows[i]['label']),str(rows[i]['protocol']),rows[i]['source_role'])==key],dtype=np.int64)
    return result

def contribution(env,small=False):
    ev,c,k,norm,arms,inputs,context,metrics,reporting=env;out={}
    for pool in ['CIC_DEV','UNSW_DEV','EDGE']:
        d,old,uids,ix=ev.load(pool,c,inputs,context,small);old.close()
        receipt=read(EVAL/('EDGE_RESULT.json' if pool=='EDGE' else 'AB_RESULT.json'))
        saved_info=receipt['scores'] if pool=='EDGE' else receipt['pools'][pool]['scores']
        saved=np.load(c.pin(saved_info['path'],saved_info['sha256']),allow_pickle=False)
        assert saved['uid'].tolist()==uids
        n=len(d['rows']);keep=d['views']['primary'][0] if 'views' in d else np.arange(n)
        groups=cohort_indices(d['rows'],keep);mappings={};mapping_receipts={}
        for seed in [20261105,20261106]:
            mapping,single=ac.permutation(d['rows'],seed);mappings['SHUFFLE_'+str(seed)]=mapping
            mapping_receipts[str(seed)]=dict(singletons=single,sha256=hashlib.sha256(mapping.tobytes()).hexdigest())
        arrays={};poolout=dict(rows=n,primary_rows=len(keep),mapping=mapping_receipts,arms={})
        for name in ['FUSION790','ANCHOR790']:
            a=arms[name];before=[ac.fingerprint(model) for model in a['models']]
            scores={v:np.empty((n,3)) for v in ['ACTUAL','ZERO',*mappings]}
            for start in range(0,n,1024):
                take=np.arange(start,min(start+1024,n));x=k.normalized((d['z'],d['context']),d['q'],take,norm,790).numpy()
                assert np.array_equal(x[:,782:],d['context'][take]),'CONTEXT_CONCAT'
                for variant,target in scores.items():
                    batch=x.copy()
                    if variant=='ZERO':batch[:,782:]=0
                    elif variant in mappings:batch[:,782:]=d['context'][mappings[variant][take]]
                    for j,model in enumerate(a['models']):target[take,j]=ac.direct(model,batch)
                if start%8192==0:progress(pool+'_'+name+'_CONTEXT',start,n)
            scores={v:c.four(x) for v,x in scores.items()};base=scores['ACTUAL'];expected=saved[name+'_RAW']
            if ix is not None:expected=expected[ix]
            error=float(np.max(np.abs(base-expected)));assert error<=.002,'ACCEPTED_SCORE_PARITY'
            assert np.array_equal(base>a['cuts'],expected>a['cuts']),'ACCEPTED_DECISION_PARITY'
            assert before==[ac.fingerprint(model) for model in a['models']],'MODEL_MUTATED'
            detail=dict(score_parity_max_error=error,model_fingerprint=before,variants={})
            for variant,x in scores.items():
                arrays[name+'_'+variant]=x;detail['variants'][variant]={}
                for group,take in groups.items():
                    detail['variants'][variant][group]={}
                    for j,h in enumerate(ac.HEADS):
                        old_dec=base[take,j]>a['cuts'][j];new_dec=x[take,j]>a['cuts'][j]
                        detail['variants'][variant][group][h]=dict(rows=len(take),alarm_count=int(new_dec.sum()),
                            margin=ac.quant(x[take,j]-a['cuts'][j]),score_delta_from_actual=ac.quant(x[take,j]-base[take,j]),
                            added_alarms=int((~old_dec&new_dec).sum()),removed_alarms=int((old_dec&~new_dec).sum()))
            poolout['arms'][name]=detail
        if not small:
            p=HERE/(pool+'_INTERVENTIONS.npz');np.savez(p,uid=np.asarray([r['uid'] for r in d['rows']]),**arrays)
            poolout['arrays']=dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
        out[pool]=poolout;saved.close();del d,arrays,scores;gc.collect()
    return out

class SourceProgress:
    stage='LOAD_SOURCE'
    def tick(self,done,total):progress(self.stage,done,total)

def source_diagnosis(env,small=False):
    _,c,k,_,arms,*_=env
    sys.path.insert(0,str(TRAIN));aw=module('anchor_training_readonly',TRAIN/'worker.py')
    start=time.monotonic();data=aw.parent.load(SourceProgress(),False);load_seconds=time.monotonic()-start
    fit=data['fit'];rows=[data['rows'][int(i)] for i in fit];n=len(fit);w=data['w']
    assert n==617908
    labels=np.asarray([r['label'] for r in rows],dtype=np.float32);normal=np.flatnonzero(labels==0)
    normal_rows=[rows[int(i)] for i in normal]
    order=np.random.default_rng(20261105).permutation(n)[:16384];batches=2 if small else 64
    selected=order[:batches*256]
    identity=dict(rows=len(selected),normal_rows=int((labels[selected]==0).sum()),attack_rows=int((labels[selected]==1).sum()),
                  ordered_uid_sha256=k.c.uid_sha(rows[int(i)]['uid'] for i in selected),
                  sampling='fixed uniform FIT without replacement; original n/batch weights; not reweighted by sampled class')
    snapshots=[('ANCHOR790',40)] if small else [('FUSION790',40)]+[('ANCHOR790',e) for e in [0,1,5,10,20,40]]
    out=dict(load_seconds=load_seconds,query_sample=identity,snapshots={},scope='SOURCE_FIT_ONLY_NO_OPTIMIZER',
             tail_scope='current snapshot full FIT-normal tail, fixed 128 draws/batch; not reconstruction of historical optimizer state')
    seeds=[27] if small else [27,127,227];total=len(snapshots)*len(seeds);finished=0
    for seed in seeds:
        targets,teacher_scale=aw.teacher(data,seed)
        folder=TRAIN/'heads'/f'ANCHOR790_{seed}'/'train';k.c.verify(folder)
        contract=read(folder/'anchor_contract.json');assert contract['lambda_value']==1. and contract['teacher_scale']==teacher_scale
        original_components=np.load(folder/'objective_components.npy',allow_pickle=False)
        assert original_components.shape==(96560,4) and np.isfinite(original_components).all()
        assert np.allclose(original_components[:,0]+original_components[:,1]+original_components[:,2],original_components[:,3],rtol=1e-5,atol=1e-9)
        out.setdefault('recorded_objective_trajectory',{})[str(seed)]=[dict(epoch=e+1,mean=dict(zip(['BCE','TAIL','ANCHOR','TOTAL'],map(float,original_components[e*2414:(e+1)*2414].mean(0))))) for e in range(40)]
        for name,epoch in snapshots:
            begun=time.monotonic();model=k.classifier(seed,790)
            if name=='FUSION790':model.load_state_dict(arms[name]['models'][[27,127,227].index(seed)].state_dict());path=None
            else:
                path=folder/('initial.npz' if epoch==0 else f'epoch_{epoch:02d}_head.npz')
                with np.load(path,allow_pickle=False) as saved:model.load_state_dict({n:torch.from_numpy(saved[n].copy()) for n in saved.files})
                if epoch==40:assert ac.fingerprint(model)==ac.fingerprint(arms['ANCHOR790']['models'][[27,127,227].index(seed)])
            model.eval().requires_grad_(True);fingerprint=ac.fingerprint(model)
            tail_start=time.monotonic()
            scores=k.scores(model,data['values'],data['q'],fit[normal],data['norm'],790)
            h=k.tail_distribution(scores,2*w[normal],data['spec']['training']['parent_recipe']['negative_tail_mass'])
            sampler=k.TailSampler(normal_rows,h,seed,epoch)
            tail_seconds=time.monotonic()-tail_start;gradient_start=time.monotonic()
            sums=None;losses=[];perbatch=[];errors=[]
            for b in range(batches):
                local=order[b*256:(b+1)*256];neg=normal[sampler.draw(128)]
                x=k.normalized(data['values'],data['q'],fit[local],data['norm'],790)
                nx=k.normalized(data['values'],data['q'],fit[neg],data['norm'],790)
                vectors,values,error=ac.gradients(model,x,torch.from_numpy(labels[local]),w[local],n,nx,targets[local],teacher_scale,k.objective_components)
                sums=vectors.copy() if sums is None else sums+vectors;losses.append(values);errors.append(error)
                perbatch.append(dict(batch=b+1,gradients=ac.gradient_summary(vectors,model)))
                if b%8==0:progress('FIT_GRADIENT_'+name+'_'+str(seed)+'_epoch'+str(epoch),finished*batches+b,total*batches)
            assert fingerprint==ac.fingerprint(model),'MODEL_MUTATED'
            gradient_seconds=time.monotonic()-gradient_start
            key=name+'_'+str(seed)+'_epoch'+str(epoch)
            detail=dict(seed=seed,arm=name,epoch=epoch,model_fingerprint=fingerprint,head_sha256=sha(path) if path else None,
                        loss_means=dict(zip(ac.TERMS,map(float,np.mean(losses,axis=0)))),
                        mean_gradient=ac.gradient_summary(sums/batches,model),
                        gradient_sum_max_abs_error=max(errors),tail_seconds=tail_seconds,gradient_seconds=gradient_seconds,
                        seconds=time.monotonic()-begun,context_weight_norm=float(torch.linalg.norm(model[0].weight[:,782:]).detach()))
            detail['batch_relations']={}
            for block in ac.block_indices(model):
                rel=[p['gradients'][block]['classification_vs_anchor'] for p in perbatch]
                valid=[v for v in rel if v['angle_interpretable']]
                detail['batch_relations'][block]=dict(total_batches=batches,interpretable_batches=len(valid),
                    negative_dot_batches=sum(v['anchor_opposes_classification'] for v in valid),
                    cosine=ac.quant([v['cosine'] for v in valid]),
                    classification_norm=ac.quant([v['classification_norm'] for v in rel]),anchor_norm=ac.quant([v['anchor_norm'] for v in rel]))
            if not small:
                write(key+'_BATCH_GRADIENTS.json',perbatch);detail['batch_receipt_sha256']=sha(HERE/(key+'_BATCH_GRADIENTS.json'))
            out['snapshots'][key]=detail;finished+=1;del model,sums;gc.collect()
    if small:
        last=list(out['snapshots'].values())[-1]
        forecast=1.75*(load_seconds+21*(last['tail_seconds']+last['gradient_seconds']*32+2))+60
        out['gradient_forecast_seconds']=forecast;assert forecast<=3600,'GRADIENT_BUDGET'
    return out

def main():
    start=time.monotonic();env=initialize();progress('IDENTITY_VERIFIED')
    import test_diagnosis
    if PHASE=='PREFLIGHT':
        ev,c,k,norm,arms,inputs,context,metrics,reporting=env
        import preflight_encoder
        preflight_encoder.progress=progress
        d=inputs.edge();encoder=preflight_encoder.run(d,norm);del d;gc.collect()
        test_diagnosis.main(HERE/'LINUX_REGRESSION.json')
        result=dict(status='PASS',real_encoder_distance=encoder,small_contribution=contribution(env,True),source_gradient_gate=source_diagnosis(env,True))
        write('RUNTIME_FORECAST.json',dict(gradient_seconds=result['source_gradient_gate']['gradient_forecast_seconds'],budget_seconds=3600))
    else:
        assert read(HERE/'PREFLIGHT_RESULT.json')['status']=='PASS'
        result=dict(status='PASS',diagnosis=contribution(env) if PHASE=='CONTRIBUTION' else source_diagnosis(env))
    result.update(phase=PHASE,seconds=time.monotonic()-start,rss_peak_bytes=PEAK,training=False,optimizer_updates=0,
                  threshold_fitting=False,model_selection=False,interpretation='Frozen-head intervention and FIT gradient evidence; no new efficacy claim')
    write(PHASE+'_RESULT.json',result);progress(PHASE+'_COMPLETE',1,1)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['PREFLIGHT','CONTRIBUTION','GRADIENT'],required=True);PHASE=p.parse_args().phase
    try:main()
    except BaseException as e:write(PHASE+'_STOP.json',dict(status='STOP',error=repr(e),traceback=traceback.format_exc()));raise
