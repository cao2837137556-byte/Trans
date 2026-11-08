"""Source-only full-size preparation and bounded training resource probes.

Author benchmark datasets are deliberately not required. No target metrics select
configurations. Probe checkpoints are never promoted to formal results.
"""
import gc, hashlib, importlib.util, math, os, pickle, sys, time, zipfile
import numpy as np
import torch
from pipeline_parent import HERE, PROJECT, SOURCE, TRAIN, read, write, sha, bootstrap, progress, model_factory
from adapters import tabm, tabm_score, tabr, slad, fidelity_checks

def install_assets():
    target=HERE/'runtime/wheels';target.mkdir(parents=True,exist_ok=True)
    for name,spec in read(HERE/'ASSETS.json').items():
        p=HERE/'assets'/name
        assert p.stat().st_size==spec['bytes'] and sha(p)==spec['sha256']
        with zipfile.ZipFile(p) as z:
            assert all(not n.startswith('/') and '..' not in n.split('/') for n in z.namelist())
            z.extractall(target)
    sys.path.insert(0,str(target))
    import faiss
    faiss.omp_set_num_threads(1)
    return target

def dte_module():
    p=HERE/'vendor/dte/diffusion/dte.py'
    s=importlib.util.spec_from_file_location('author_dte',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def fidelity():
    install_assets();r=fidelity_checks(True);m=dte_module();torch.manual_seed(27)
    model=m.DTECategorical(device='cpu');model.model=m.MLP([790]+model.hidden_size,num_bins=7)
    x=torch.randn(8,790);t=torch.arange(8)*50
    state=torch.get_rng_state();actual=model.compute_loss(x,t)
    torch.set_rng_state(state);noise=torch.randn_like(x);ab=torch.cumprod(1-torch.linspace(.0001,.01,400),0)
    noisy=x+torch.sqrt(1-ab[t])[:,None]*noise
    expected=torch.nn.functional.cross_entropy(model.model(noisy),torch.clamp(torch.floor(t*7/400),0,6).long())
    assert torch.equal(actual,expected),'DTE_AUTHOR_LOSS_PARITY'
    model.model.eval()
    with torch.inference_mode():expected=(model.model(x).numpy()*np.arange(7)).sum(1)
    assert np.allclose(expected,model.predict_score(x.numpy()),atol=1e-6)
    r['DTE']=dict(status='PASS',loss='author CE on softmax probabilities preserved',noise='variance only, no drift',score='expected bin index',loss_exact=True)
    # Native memory-efficient TabR path, author implementation, no custom retrieval.
    a,_=tabr();b,_=tabr();b.load_state_dict(a.state_dict());a.eval();b.eval();b.memory_efficient=True;b.candidate_encoding_batch_size=17
    pool=torch.randn(97,790);labels=torch.arange(97)%2
    args=dict(x_={'num':x},y=None,candidate_x_={'num':pool},candidate_y=labels,context_size=16,is_train=False)
    with torch.inference_mode():err=float((a(**args)-b(**args)).abs().max())
    assert err<2e-5
    r['TabR_native_memory_efficient']=dict(status='PASS',eval_max_abs_error=err,training_path='original author recomputation')
    return dict(status='PASS',checks=r,author_dataset_replication_required=False)

def source_prepare():
    c=bootstrap();import inputs,context_core as k
    rows,z,q,raw=inputs.source_role('LEARN');fit=np.load(SOURCE/'metadata/FIT.npy');spec=read(TRAIN/'TRAINING_SPEC_FROZEN.json')
    assert len(fit)==617908 and k.c.uid_sha(rows[int(i)]['uid'] for i in fit)==spec['data_identity']['FIT']['uid_sha256']
    _,norm,arms=c.models();del arms;gc.collect()
    out=HERE/'artifacts/source';out.mkdir(parents=True,exist_ok=True)
    x=np.lib.format.open_memmap(out/'FIT_X.npy',mode='w+',dtype='float32',shape=(len(fit),790))
    y=np.asarray([int(rows[int(i)]['label']) for i in fit],dtype='int64');np.save(out/'FIT_y.npy',y)
    assert set(y)=={0,1} and int((y==0).sum())==134493
    # Whole captures, joined by any shared session/component. Never random-row
    # fallback if the resulting grouped source split is not usable.
    captures={};parents=[];counts=[];links={};row_group=np.empty(len(fit),dtype=np.int32)
    def root(a):
        while parents[a]!=a:parents[a]=parents[parents[a]];a=parents[a]
        return a
    for j,i in enumerate(fit):
        r=rows[int(i)];key=(str(r.get('device','')),str(r.get('capture_id','')))
        assert all(key),'MISSING_SOURCE_CAPTURE_ID'
        if key not in captures:captures[key]=len(parents);parents.append(len(parents));counts.append([0,0])
        g=captures[key];row_group[j]=g;counts[g][int(y[j])]+=1
        for field in ('session_id','component_id'):
            value=str(r.get(field,''))
            if value not in ('','None','nan'):
                lk=(key[0],field,value)
                if lk in links:parents[root(g)]=root(links[lk])
                else:links[lk]=g
    roots=np.asarray([root(g) for g in row_group],dtype=np.int32);groups=[];validation=set()
    for g in sorted(set(roots.tolist())):
        members=sorted('|'.join(key) for key,v in captures.items() if root(v)==g)
        digest=hashlib.sha256(('baseline-source-group-v3|'+'\n'.join(members)).encode()).hexdigest()
        isval=int(digest[:8],16)%5==0
        if isval:validation.add(g)
        mask=roots==g;groups.append(dict(group=g,captures=members,normal=int(((y==0)&mask).sum()),attack=int(((y==1)&mask).sum()),validation=isval))
    split=np.isin(roots,list(validation));np.save(out/'INNER_VALID.npy',split);np.save(out/'GROUP_ID.npy',roots)
    split_counts={n:dict(normal=int(((y==0)&mask).sum()),attack=int(((y==1)&mask).sum())) for n,mask in [('train',~split),('validation',split)]}
    split_ok=all(v['normal']>0 and v['attack']>0 for v in split_counts.values())
    del rows,links,roots,row_group;gc.collect()
    start=time.monotonic()
    for off in range(0,len(fit),1024):
        ix=fit[off:off+1024];x[off:off+len(ix)]=k.normalized((z[ix],c.extra_normalized(raw[ix])),q[ix],np.arange(len(ix)),norm,790).numpy()
        if off%16384==0:progress('MATERIALIZE_FULL_SOURCE_FIT',off,len(fit))
    x.flush();del z,q,raw;gc.collect()
    ni=np.flatnonzero(y==0);normal=np.lib.format.open_memmap(out/'NORMAL_X.npy',mode='w+',dtype='float32',shape=(len(ni),790))
    for off in range(0,len(ni),1024):normal[off:off+1024]=x[ni[off:off+1024]]
    normal.flush();del x,normal;gc.collect()
    pins={p.name:sha(p) for p in out.glob('*.npy')}
    return dict(status='PASS',full_fit_rows=len(fit),normal_fit_rows=len(ni),feature_count=790,materialize_seconds=time.monotonic()-start,sha256=pins,inner_split_gate='PASS' if split_ok else 'NEEDS_SPLIT_DESIGN',split_counts=split_counts,groups=groups,grouping='capture union shared device/session and device/component; fixed SHA modulo 5',source_cal_used_for_tuning=False)

def source_arrays(normal=False):
    result=read(HERE/'SOURCE_RESULT.json');assert result['status']=='PASS'
    folder=HERE/'artifacts/source';names=['NORMAL_X.npy'] if normal else ['FIT_X.npy','FIT_y.npy']
    for n in names:assert sha(folder/n)==result['sha256'][n]
    arrays=[np.load(folder/n,mmap_mode='r') for n in names]
    return arrays[0] if normal else arrays

def save_reload(model,path,probe):
    model.eval()
    with torch.inference_mode():before=probe()
    np.savez(path,**{n:v.detach().numpy() for n,v in model.state_dict().items()})
    with np.load(path) as a:model.load_state_dict({n:torch.from_numpy(a[n].copy()) for n in a.files})
    with torch.inference_mode():after=probe()
    assert np.array_equal(before,after),'CHECKPOINT_PARITY'
    return sha(path)

def dte_pilot():
    bootstrap();import context_core as k
    from sklearn.preprocessing import StandardScaler
    a=np.load(HERE/'PILOT_INPUTS.npz');x=a['fit_x'][a['fit_y']==0];scaler=StandardScaler().fit(x);x=scaler.transform(x).astype('float32')
    torch.manual_seed(27);np.random.seed(27);m=dte_module();model=m.DTECategorical(epochs=1,device='cpu');model.fit(x)
    scores={p:model.predict_score(scaler.transform(a['cal_x' if p=='CAL' else p+'_x']).astype('float32')) for p in ('CAL','CIC_DEV','UNSW_DEV','EDGE')}
    assert all(np.isfinite(v).all() for v in scores.values());cut=k.threshold(scores['CAL'],read(HERE/'CAL_ROWS.json'),.01)
    folder=HERE/'artifacts/DTE_PILOT';folder.mkdir(parents=True,exist_ok=True)
    probe=lambda:model.predict_score(x[:8]);h=save_reload(model.model,folder/'checkpoint.npz',probe)
    np.savez(folder/'scaler.npz',mean=scaler.mean_,scale=scaler.scale_);np.savez(folder/'scores.npz',**scores)
    return dict(status='PASS',train_normal_rows=len(x),epochs=1,source_cal_cut=cut,source_cal_weighted_fpr=float(a['cal_w'][scores['CAL']>cut].sum()),checkpoint_sha256=h,formal_training=False)

def catboost_pilot():
    install_assets();bootstrap();import context_core as k
    from catboost import CatBoostClassifier
    a=np.load(HERE/'PILOT_INPUTS.npz');model=CatBoostClassifier(iterations=16,depth=6,learning_rate=.05,loss_function='Logloss',thread_count=1,random_seed=27,verbose=False,allow_writing_files=False)
    model.fit(a['fit_x'],a['fit_y']);score=lambda x:np.asarray(model.predict(x,prediction_type='RawFormulaVal'))
    out={p:score(a['cal_x' if p=='CAL' else p+'_x']) for p in ('CAL','CIC_DEV','UNSW_DEV','EDGE')};assert all(np.isfinite(v).all() for v in out.values())
    assert np.allclose(model.predict_proba(a['cal_x'])[:,1],1/(1+np.exp(-out['CAL'])))
    cut=k.threshold(out['CAL'],read(HERE/'CAL_ROWS.json'),.01);folder=HERE/'artifacts/CAT_PILOT';folder.mkdir(parents=True,exist_ok=True);path=folder/'model.cbm';model.save_model(str(path));expected=out['CAL'];model=CatBoostClassifier();model.load_model(str(path));assert np.array_equal(expected,score(a['cal_x']))
    np.savez(folder/'scores.npz',**out)
    return dict(status='PASS',version=__import__('catboost').__version__,source_cal_cut=cut,source_cal_weighted_fpr=float(a['cal_w'][out['CAL']>cut].sum()),checkpoint_sha256=sha(path),reload_exact=True,formal_training=False)

def profile(name):
    torch.set_num_threads(1);torch.manual_seed(27);np.random.seed(27)
    folder=HERE/'artifacts'/name;folder.mkdir(parents=True,exist_ok=True);times=[];start=time.monotonic()
    if name=='CAT_FULL':
        install_assets();from catboost import CatBoostClassifier
        x,y=source_arrays();model=CatBoostClassifier(iterations=8,depth=6,learning_rate=.05,thread_count=1,random_seed=27,verbose=False,allow_writing_files=False)
        model.fit(x,y);elapsed=time.monotonic()-start;model.save_model(str(folder/'model.cbm'))
        return dict(status='PASS',full_training_input_rows=len(y),iterations=8,fit_seconds=elapsed,forecast_2000_iterations_seconds=elapsed/8*2000*1.5,forecast_only=True,formal_training=False)
    if name=='SLAD_FULL':
        x=source_arrays(True);model=slad();model.fit(x);elapsed=time.monotonic()-start
        assert all(torch.isfinite(v).all() for v in model.net.state_dict().values())
        return dict(status='PASS',full_normal_input_rows=len(x),author_transformed_rows=model.n_ensemble*model.sampling_size,author_preprocessing_complete=True,updates=16,fit_seconds=elapsed,full_epoch_training_qualified=False,formal_training=False)
    if name=='DTE_FULL':
        from sklearn.preprocessing import StandardScaler
        x=source_arrays(True);scaler=StandardScaler().fit(x);x=scaler.transform(x).astype('float32');m=dte_module();model=m.DTECategorical(epochs=1,device='cpu')
        progress('DTE_FULL_NORMAL_EPOCH',0,len(x));model.fit(x);elapsed=time.monotonic()-start
        h=save_reload(model.model,folder/'checkpoint.npz',lambda:model.predict_score(x[:8]))
        return dict(status='PASS',full_normal_input_rows=len(x),epochs=1,steps=math.ceil(len(x)/64),fit_seconds=elapsed,forecast_400_epochs_seconds=elapsed*400*1.5,forecast_only=True,checkpoint_sha256=h,formal_training=False)
    if name=='NCA_RESOURCE':
        x,y=source_arrays();m,cfg=model_factory('ModernNCA');dim=m.d_in;rate=m.sample_rate
        # Measure genuine backwards at two manageable source pool sizes. Never
        # claim this is full-pool training or silently cap formal candidates.
        measured=[]
        for n in (1024,4096):
            model,_=model_factory('ModernNCA');opt=torch.optim.AdamW(model.parameters(),lr=.001);xx=torch.from_numpy(np.array(x[:n]));yy=torch.from_numpy(np.array(y[:n]));t=time.monotonic()
            loss=torch.nn.functional.nll_loss(model(xx[:16],yy[:16],xx[16:],yy[16:],True),yy[:16]);loss.backward();opt.step();elapsed=time.monotonic()-t
            measured.append(dict(pool_rows=n,sampled_candidates=int((n-16)*rate),backward_step_seconds=elapsed,loss=float(loss.detach())))
            del model,opt,xx,yy,loss;gc.collect()
        count=int((len(y)-512)*rate);single_activation=count*dim*4
        return dict(status='NEEDS_RESOURCES',reason='FULL_TRAINING_NOT_QUALIFIED',full_fit_rows=len(y),author_sample_rate=rate,default_sampled_candidates=count,embedded_dim=dim,single_expanded_activation_gib=single_activation/2**30,measured=measured,default_full_step_linear_estimate_seconds=measured[-1]['backward_step_seconds']*count/measured[-1]['sampled_candidates'],estimate_excludes_batch_and_memory_nonlinearity=True,full_pool_backward_executed=False,formal_candidate_cap=None)
    normal=name=='DISENT_FULL';data=source_arrays(normal);x=data if normal else data[0];y=None if normal else data[1]
    if name=='TABM_FULL':model=tabm();batch=256;steps=16;lr=.002
    elif name=='TABR_FULL':
        install_assets();model,_=tabr();model.memory_efficient=True;model.candidate_encoding_batch_size=2048;batch=64;steps=2;lr=.0001
        candidates=torch.from_numpy(np.array(x[:-batch]));labels=torch.from_numpy(np.array(y[:-batch]));query=torch.from_numpy(np.array(x[-batch:]));qy=torch.from_numpy(np.array(y[-batch:]))
    else:model,_=model_factory('DisentAD');batch=4;steps=16;lr=.0001
    opt=(torch.optim.Adam if normal else torch.optim.AdamW)(model.parameters(),lr=lr,weight_decay=0. if normal or name=='TABR_FULL' else .0003)
    for step in range(steps):
        t=time.monotonic();model.train();opt.zero_grad(set_to_none=True)
        if name=='TABR_FULL':v=model(x_={'num':query},y=qy,candidate_x_={'num':candidates},candidate_y=labels,context_size=96,is_train=True).flatten();loss=torch.nn.functional.binary_cross_entropy_with_logits(v,qy.float())
        else:
            ix=np.random.choice(len(x),batch,replace=False);xx=torch.from_numpy(np.array(x[ix]))
            if normal:r,d=model(xx.unsqueeze(-1));loss=r+d
            else:yy=torch.from_numpy(np.array(y[ix]));v=model(xx);loss=torch.nn.functional.cross_entropy(v.flatten(0,1),yy.repeat_interleave(32))
        assert torch.isfinite(loss);loss.backward();assert all(p.grad is None or torch.isfinite(p.grad).all() for p in model.parameters());opt.step();times.append(time.monotonic()-t);progress(name+'_BACKWARD',step+1,steps)
    np.savez(folder/'checkpoint.npz',**{n:v.detach().numpy() for n,v in model.state_dict().items()})
    return dict(status='PASS',training_input_rows=len(x),steps=steps,batch=batch,step_seconds=times,conservative_epoch_seconds=max(times)*math.ceil(len(x)/batch)*1.5,full_candidate_backward=name=='TABR_FULL',native_memory_efficient=name=='TABR_FULL',full_epoch_executed=False,formal_training=False)

def seal():
    phases=read(HERE/'SPEC.json')['phases'];results={p:read(HERE/(p+'_RESULT.json')) for p in phases if p!='SEAL'}
    protocol=read(HERE/'TRAINING_PROTOCOL.json');source=results['SOURCE'];resource={p:{k:r[k] for k in ('status','seconds','rss_peak_mib','conservative_epoch_seconds','forecast_400_epochs_seconds','forecast_2000_iterations_seconds','reason','error') if k in r} for p,r in results.items() if p.endswith('_FULL') or p=='NCA_RESOURCE'}
    pending=['Formal adequately converged training and three-seed evaluation have not run.', 'ModernNCA full backward needs a larger-memory execution contract.', 'SLAD full-epoch timing and all-method source validation cost still require measurement.']
    if source['inner_split_gate']!='PASS':pending.append('Source group split lacks class coverage; no tuning may start.')
    body=dict(status='FROZEN_PROTOCOL_WITH_RESOURCE_GATES',protocol_sha256=sha(HERE/'TRAINING_PROTOCOL.json'),source_identity=source['sha256'],source_split_gate=source['inner_split_gate'],resources=resource,pending=pending,automatic_formal_training=False,main_model_changed=False,author_benchmark_datasets_required=False)
    write('FORMAL_PLAN_SEALED.json',body)
    return dict(status='PASS',scope='PROTOCOL_AND_MEASURED_RESOURCE_REPORT',plan_sha256=sha(HERE/'FORMAL_PLAN_SEALED.json'),formal_training_ready=False,pending=pending)
