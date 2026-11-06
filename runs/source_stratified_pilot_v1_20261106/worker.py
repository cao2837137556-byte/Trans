"""Fixed small source pilot. No external candidate scoring or threshold fitting."""
import argparse, gc, importlib.util, json, math, sys, time, traceback
from pathlib import Path
import numpy as np
import psutil
import torch
import risk_core as r
import sampling_core as sampler
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[1]
PARENT=ROOT/'runs/device_context_head_training_v2_20261105'
sys.path.insert(0,str(PARENT))
import context_core as k
c=k.c
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
parent=module('source_parent',PARENT/'worker.py')
PHASE='DECODE_PREFLIGHT'
def write(n,v): c.write(HERE/n,v,replace=True)
class Progress:
    stage='LOAD_SOURCE'; peak=0; optimizer_updates=0; last=0
    def tick(self,done,total):
        now=time.monotonic()
        if now-self.last<2 and done!=total:return
        self.last=now; self.peak=max(self.peak,psutil.Process().memory_info().rss)
        assert self.peak<7*2**30,'MEMORY_LIMIT'
        write(PHASE+'_PROGRESS.json',dict(stage=self.stage,done=int(done),total=int(total),optimizer_updates=self.optimizer_updates,rss_mib=self.peak/2**20,updated_unix=time.time()))

def verify():
    for n,h in c.read(HERE/'.private.json')['pins'].items():c.pin(HERE/n,h)
    for n,h in c.read(HERE/'INPUT_PINS.json').items():c.pin(ROOT/n,h)
    spec=c.read(HERE/'SPEC.json')
    assert spec['seeds']==[27,127,227] and spec['epochs']==5 and spec['sample_per_class']==8192
    return spec

def load_head(seed):
    result=c.read(PARENT/f'TRAIN_FUSION790_{seed}_RESULT.json'); folder=PARENT/'heads'/f'FUSION790_{seed}'
    c.verify(folder/'train'); c.verify(folder/'calibration')
    model=k.classifier(seed,790)
    with np.load(c.pin(folder/'train/head.npz',result['head_sha256']),allow_pickle=False) as a:
        model.load_state_dict({n:torch.from_numpy(a[n].copy()) for n in a.files})
    model.eval().requires_grad_(False)
    saved={role:np.load(c.pin(folder/f'calibration/{role}_logits.npy',result['calibration']['logits_sha256'][role]),allow_pickle=False) for role in ['fit','cal']}
    return model,result,saved

def zero_scores(model,data,indices,p):
    result=np.empty(len(indices),np.float32)
    with torch.inference_mode():
        for start in range(0,len(indices),1024):
            x=k.normalized(data['values'],data['q'],indices[start:start+1024],data['norm'],790); x[:,782:]=0
            result[start:start+len(x)]=model(x).flatten().numpy()
            p.tick(start+len(x),len(indices))
    assert np.isfinite(result).all(); return result

def measures(rows,base,scores,zero0,zero,cut,scale,upper):
    labels=np.asarray([v['label'] for v in rows]); out={}
    for label,name in [(0,'normal'),(1,'attack')]:
        ix=np.flatnonzero(labels==label); rr=[rows[i] for i in ix]; w=k.class_weights(rr)
        b=base[ix]>cut; a=scores[ix]>cut; delta=(scores[ix]-base[ix])/scale
        entry=dict(rows=len(ix),baseline_alarms=int(b.sum()),candidate_alarms=int(a.sum()),
                   baseline_rate=float(b.mean()),candidate_rate=float(a.mean()),
                   baseline_weighted_rate=float(np.dot(w,b)),candidate_weighted_rate=float(np.dot(w,a)),
                   added=int((a&~b).sum()),removed=int((b&~a).sum()),
                   standardized_score_change=r.quant(delta),margin=r.quant(scores[ix]-cut))
        if label==0:
            entry.update(baseline_tail_risk=float(np.dot(w,np.maximum((base[ix]-upper)/scale,0)**2)),
                         candidate_tail_risk=float(np.dot(w,np.maximum((scores[ix]-upper)/scale,0)**2)))
        else:
            lift0=base[ix]-zero0[ix]; lift=scores[ix]-zero[ix]; positive=lift0>0
            entry.update(attack_slack_violation_fraction=float((delta<-.01).mean()),
                         positive_context_rows=int(positive.sum()),
                         baseline_context_lift=r.quant(lift0),candidate_context_lift=r.quant(lift),
                         context_preservation_violation_fraction=float((lift[positive]<.9*lift0[positive]).mean()) if positive.any() else None,
                         positive_context_retention=float(np.dot(w[positive],lift[positive])/np.dot(w[positive],lift0[positive])) if positive.any() else None)
        # Report cohort losses; do not hide a protocol/activity under pooled recall.
        entry['cohorts']={}
        for field in ['protocol','device','activity']:
            entry['cohorts'][field]={}
            for key in sorted({str(v[field]) for v in rr}):
                take=np.asarray([str(v[field])==key for v in rr]); ww=w[take]/w[take].sum()
                entry['cohorts'][field][key]=dict(rows=int(take.sum()),baseline_rate=float(b[take].mean()),candidate_rate=float(a[take].mean()),baseline_weighted_rate=float(np.dot(ww,b[take])),candidate_weighted_rate=float(np.dot(ww,a[take])),removed=int((b[take]&~a[take]).sum()))
        out[name]=entry
    return out

def criteria(metric):
    n,a=metric['normal'],metric['attack']
    return dict(normal_weighted_nonincrease=n['candidate_weighted_rate']<=n['baseline_weighted_rate']+1e-12,
                normal_unweighted_nonincrease=n['candidate_rate']<=n['baseline_rate']+1e-12,
                attack_weighted_drop_within_0_1pp=a['candidate_weighted_rate']>=a['baseline_weighted_rate']-.001,
                attack_unweighted_drop_within_0_1pp=a['candidate_rate']>=a['baseline_rate']-.001,
                attack_removed_fraction_within_0_1pp=a['removed']/a['rows']<=.001,
                attack_p01_margin_drop_within_slack=a['standardized_score_change']['p01']>=-.01-1e-6,
                positive_context_retention=a['positive_context_retention'] is None or a['positive_context_retention']>=.9,
                protocol_attack_drop_within_0_1pp=all(v['candidate_rate']>=v['baseline_rate']-.001 for v in a['cohorts']['protocol'].values()))

def one(data,seed,p,small,spec):
    started=time.monotonic(); baseline,receipt,saved=load_head(seed); before=r.fingerprint(baseline)
    rr=[data['rows'][int(i)] for i in data['fit']]; labels=np.asarray([v['label'] for v in rr]); n=len(labels)
    selected,sw,sampling_receipt=sampler.draw(rr,data['w'],each=8192,seed=spec['sample_seed']); sy=labels[selected]
    assert len(sampling_receipt['strata'])==105 and all(sum(v['label']==y for v in sampling_receipt['strata'])==expected for y,expected in [(0,94),(1,11)]), 'SOURCE_SEMANTIC_IDENTITY'
    assert len(selected)==16384 and not set(data['fit'][selected])&set(data['cal'])
    x=k.normalized(data['values'],data['q'],data['fit'][selected],data['norm'],790)
    assert np.array_equal(x[:,782:].numpy(),data['values'][1][data['fit'][selected]])
    zx=x.clone(); zx[:,782:]=0
    fullzero={}; parity={}; scale=receipt['calibration']['scale']; cut=receipt['calibration']['cut']
    assert scale>0
    for role in ['fit','cal']:
        p.stage='BASELINE_PARITY_'+str(seed)+'_'+role
        actual=k.scores(baseline,data['values'],data['q'],data[role],data['norm'],790,p)
        parity[role]=float(np.max(np.abs(actual-saved[role])))
        assert parity[role]==0,'FROZEN_BASELINE_SCORE_PARITY'
        p.stage='BASELINE_ZERO_'+str(seed)+'_'+role
        fullzero[role]=zero_scores(baseline,data,data[role],p)
    upper=parent.onboarding.weighted_quantile(saved['fit'][labels==0],2*data['w'][labels==0],.9)
    teacher=torch.from_numpy(saved['fit'][selected].copy()); teacher_zero=torch.from_numpy(fullzero['fit'][selected].copy())
    sample_rows=[rr[i] for i in selected]
    identity=dict(rows=len(selected),normal_rows=8192,attack_rows=8192,uid_sha256=c.uid_sha(v['uid'] for v in sample_rows),
                  source_spec_sha256=c.sha(PARENT/'TRAINING_SPEC_FROZEN.json'),sample_weight_sha256=__import__('hashlib').sha256(sw.tobytes()).hexdigest(),
                  sampling=sampling_receipt,
                  unique_normal_rows=len(set(selected[sy==0])),unique_attack_rows=len(set(selected[sy==1])),
                  normal_active_rows=int(((saved['fit'][selected]>upper)&(sy==0)).sum()),
                  attack_positive_lift_rows=int(((teacher.numpy()>teacher_zero.numpy())&(sy==1)).sum()),
                  coverage={field:{str(y):len({v[field] for v in sample_rows if v['label']==y}) for y in (0,1)} for field in ['device','activity','protocol','capture_id','component_id']})
    model=k.classifier(seed,790); model.load_state_dict(baseline.state_dict()); model.train()
    assert r.fingerprint(model)==before
    folder=HERE/('runtime_smoke' if small else 'heads')/str(seed); folder.mkdir(parents=True,exist_ok=False)
    c.save_arrays(folder/'sample_identity.npz',fit_local_index=selected,uid=np.asarray([v['uid'] for v in sample_rows]),weights=sw)
    optimizer=torch.optim.AdamW(model.parameters(),lr=spec['learning_rate'],betas=(.9,.999),eps=1e-8,weight_decay=0.,foreach=False)
    rng=np.random.default_rng(seed); count=0; epochs=1 if small else spec['epochs']; batches=8 if small else 64
    records=[]; epoch_receipts=[]; train_start=time.monotonic(); first_normal_norm=None
    for epoch in range(epochs):
        order=[rng.permutation(np.flatnonzero(sy==y)) for y in (0,1)]; losses=[]
        for b in range(batches):
            ix=np.r_[order[0][b*128:(b+1)*128],order[1][b*128:(b+1)*128]]
            optimizer.zero_grad(set_to_none=True)
            s=model(x[ix]).flatten(); z=model(zx[ix]).flatten()
            terms=r.components(s,z,teacher[ix],teacher_zero[ix],torch.from_numpy(sy[ix]),sw[ix],upper,scale,8192)
            protection=10*(terms[1]+terms[2]); loss=terms[0]+protection
            assert torch.isfinite(loss)
            if b in (0,31,63):
                a=r.vector(terms[0],model); v=r.vector(protection,model)
                if first_normal_norm is None:first_normal_norm=float(torch.linalg.vector_norm(a))
                records.append(dict(epoch=epoch+1,batch=b+1,relation=r.relation(a,v),losses=[float(t.detach()) for t in terms]))
            loss.backward(); assert all(v.grad is not None and torch.isfinite(v.grad).all() for v in model.parameters())
            optimizer.step(); assert all(torch.isfinite(v).all() for v in model.parameters())
            count+=1; losses.append([float(t.detach()) for t in terms]+[float(loss.detach())])
            p.stage='PILOT_TRAIN_seed'+str(seed)+'_epoch'+str(epoch+1); p.optimizer_updates=count; p.tick(count,epochs*batches)
        c.save_arrays(folder/f'epoch_{epoch+1:02d}.npz',**{n:v.detach().numpy() for n,v in model.state_dict().items()})
        epoch_receipts.append(dict(epoch=epoch+1,updates=count,loss_means=np.mean(losses,axis=0).tolist()))
    train_seconds=time.monotonic()-train_start
    assert count==epochs*batches and r.fingerprint(baseline)==before
    c.save_arrays(folder/'head.npz',**{n:v.detach().numpy() for n,v in model.state_dict().items()})
    model.eval().requires_grad_(False); reloaded=k.classifier(seed,790)
    with np.load(folder/'head.npz',allow_pickle=False) as a:reloaded.load_state_dict({n:torch.from_numpy(a[n].copy()) for n in a.files})
    assert r.fingerprint(reloaded)==r.fingerprint(model),'CHECKPOINT_READBACK'
    metrics={}; arrays={}; fullrows={}
    for role in ['fit','cal']:
        p.stage='SOURCE_ENDPOINT_'+str(seed)+'_'+role
        scores=k.scores(model,data['values'],data['q'],data[role],data['norm'],790,p)
        zz=zero_scores(model,data,data[role],p); role_rows=[data['rows'][int(i)] for i in data[role]]; fullrows[role]=role_rows
        metrics[role]=measures(role_rows,saved[role],scores,fullzero[role],zz,cut,scale,upper)
        if role=='fit':
            take=np.setdiff1d(np.arange(n),selected)
            metrics['fit_not_used_in_pilot']=measures([role_rows[i] for i in take],saved[role][take],scores[take],fullzero[role][take],zz[take],cut,scale,upper)
        path=folder/(role+'_scores.npz')
        c.save_arrays(path,uid=np.asarray([v['uid'] for v in role_rows]),baseline=saved[role],candidate=scores,baseline_zero=fullzero[role],candidate_zero=zz)
        arrays[role]=dict(path=str(path),sha256=c.sha(path))
    gates={role:criteria(metric) for role,metric in metrics.items()}
    result=dict(status='PASS',seed=seed,runtime_gate_only=small,updates=count,epochs=epochs,
                initial_fingerprint=before,final_fingerprint=r.fingerprint(model),model_changed=before!=r.fingerprint(model),
                identity=identity,baseline_parity=parity,scale=scale,cut=cut,normal_upper=upper,
                first_normal_gradient_norm=first_normal_norm,signal_ready=identity['normal_active_rows']>0 and first_normal_norm>1e-12 and before!=r.fingerprint(model),
                train_seconds=train_seconds,seconds=time.monotonic()-started,metrics=metrics,gates=gates,
                source_preservation_pass=all(all(g.values()) for g in gates.values()),gradient_probes=records,trajectory=epoch_receipts,
                arrays=arrays,head_sha256=c.sha(folder/'head.npz'),sample_identity_sha256=c.sha(folder/'sample_identity.npz'))
    write(str(folder.relative_to(HERE))+'/RESULT.json',result); c.seal(folder); c.verify(folder)
    del baseline,model,x,zx,fullzero,saved;gc.collect();return result

def ensemble(data,heads,small):
    cut=c.read(PARENT/'CALIBRATION_RESULT.json')['ensembles']['FUSION790']['cut']; out={}
    # Ensemble scales are diagnostic normalization only; original per-seed C5 scales are untouched.
    scale=sum(heads[str(s)]['scale'] for s in [27,127,227])/3
    upper=sum(heads[str(s)]['normal_upper'] for s in [27,127,227])/3
    for role in ['fit','cal']:
        values={key:[] for key in ['baseline','candidate','baseline_zero','candidate_zero']}
        for seed in [27,127,227]:
            info=heads[str(seed)]['arrays'][role]
            with np.load(c.pin(info['path'],info['sha256']),allow_pickle=False) as a:
                assert a['uid'].tolist()==[data['rows'][int(i)]['uid'] for i in data[role]]
                for key in values:values[key].append(a[key].copy())
        means={key:parent.onboarding.ordered_ensemble(dict(zip([27,127,227],arr))) for key,arr in values.items()}
        rows=[data['rows'][int(i)] for i in data[role]]
        out[role]=measures(rows,means['baseline'],means['candidate'],means['baseline_zero'],means['candidate_zero'],cut,scale,upper)
    gates=criteria(out['cal']); n=out['cal']['normal']
    gates['cal_weighted_fpr_relative_reduction_10pct']=n['baseline_weighted_rate']>0 and n['candidate_weighted_rate']<=.9*n['baseline_weighted_rate']
    go=all(gates.values()) and all(h['source_preservation_pass'] for h in heads.values())
    return dict(cut=cut,metrics=out,gates=gates,source_pilot_go=go,runtime_gate_only=small,
                interpretation='source-only pilot evidence; CAL has prior calibration exposure; not independent external efficacy')

def main():
    start=time.monotonic();spec=verify(); p=Progress()
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    if PHASE=='DECODE_PREFLIGHT':
        # Frozen old engineering replay only. No candidate is loaded/scored on Edge.
        old=ROOT/'runs/fusion_score_anchor_v2_20261105';sys.path.insert(0,str(old))
        aw=module('engineering_gate',old/'worker.py');aw.HERE=HERE
        result=aw.decode(p)
    else:
        torch.set_num_interop_threads(1)
        assert c.read(HERE/'DECODE_PREFLIGHT_RESULT.json')['status']=='PASS'
        if PHASE=='PILOT':
            gate=c.read(HERE/'TRAIN_PREFLIGHT_RESULT.json');assert gate['status']=='PASS' and gate['signal_ready'] and gate['forecast_seconds']<=3600
        module('local_risk_regression',HERE/'test_risk.py').main(HERE/'LINUX_REGRESSION.json')
        module('local_sampling_regression',HERE/'test_sampling.py').main(HERE/'LINUX_SAMPLING_REGRESSION.json')
        data=parent.load(p,False); small=PHASE=='TRAIN_PREFLIGHT'
        heads={str(seed):one(data,seed,p,small,spec) for seed in [27,127,227]}
        ens=ensemble(data,heads,small)
        control=c.read(ROOT/'runs/source_risk_preservation_pilot_v2_20261106/PILOT_RESULT.json')
        assert all(heads[str(s)]['initial_fingerprint']==control['heads'][str(s)]['initial_fingerprint'] and heads[str(s)]['cut']==control['heads'][str(s)]['cut'] and heads[str(s)]['normal_upper']==control['heads'][str(s)]['normal_upper'] for s in [27,127,227]),'CONTROL_IDENTITY'
        assert ens['cut']==control['ensemble']['cut']
        result=dict(status='PASS',historical_control_sha256=c.sha(ROOT/'runs/source_risk_preservation_pilot_v2_20261106/PILOT_RESULT.json'),sampling_only_method_revision=True,heads=heads,ensemble=ens,signal_ready=all(h['signal_ready'] for h in heads.values()),
                    scientific_status='RUNTIME_ONLY' if small else ('SOURCE_PILOT_GO' if ens['source_pilot_go'] else 'SOURCE_PILOT_NO_GO'))
        if small:
            forecast=2*(data['load_seconds']+sum(h['seconds']+39*h['train_seconds'] for h in heads.values()))+60
            result['forecast_seconds']=forecast;write('RUNTIME_FORECAST.json',dict(pilot_seconds=forecast,budget_seconds=3600))
            assert forecast<=3600,'PILOT_RESOURCE_BUDGET'
    result.update(phase=PHASE,seconds=time.monotonic()-start,rss_peak_bytes=p.peak,
                  external_candidate_scoring=False,threshold_refit=False,encoder_finetuned=False,automatic_full_training=False)
    write(PHASE+'_RESULT.json',result);p.stage=PHASE+'_COMPLETE';p.tick(1,1)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['DECODE_PREFLIGHT','TRAIN_PREFLIGHT','PILOT'],required=True);PHASE=parser.parse_args().phase
    try:main()
    except BaseException as e:write(PHASE+'_STOP.json',dict(status='STOP',error=repr(e),traceback=traceback.format_exc()));raise
