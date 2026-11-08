import collections,copy,gc,math,random,subprocess,time
import numpy as np
import torch
from pipeline_parent import HERE,PROJECT,SOURCE,TRAIN,read,write,sha,bootstrap,progress
from readiness import dte_module
from adapters import tabm,tabm_score,slad
OLD=PROJECT/'runs/baseline_training_readiness_v6_20261107'

def arrays():
    spec=read(OLD/'SOURCE_RESULT.json');folder=OLD/'artifacts/source'
    for name,digest in spec['sha256'].items():assert sha(folder/name)==digest,'SOURCE_ARRAY_SHA'
    return np.load(folder/'FIT_X.npy',mmap_mode='r'),np.load(folder/'FIT_y.npy',mmap_mode='r'),np.load(folder/'GROUP_ID.npy',mmap_mode='r')

def split():
    c=bootstrap();import inputs,context_core as k
    proposal=read(HERE/'SOURCE_SPLIT_PROPOSAL.json');old=read(OLD/'SOURCE_RESULT.json');assert sha(OLD/'SOURCE_RESULT.json')==proposal['source_group_sha256']
    x,y,groups=arrays();valid=np.isin(groups,proposal['selected_validation_group_ids']);assert len(y)==617908
    rows,z,q,ctx=inputs.source_role('LEARN');fit=np.load(SOURCE/'metadata/FIT.npy');assert k.c.uid_sha(rows[int(i)]['uid'] for i in fit)==read(TRAIN/'TRAINING_SPEC_FROZEN.json')['data_identity']['FIT']['uid_sha256']
    del z,q,ctx;gc.collect();capture_group={cap:g['group'] for g in old['groups'] for cap in g['captures']};links={};counts=collections.Counter();coverage=collections.defaultdict(lambda:[0,0]);uid=[[],[]]
    for j,i in enumerate(fit):
        r=rows[int(i)];side=int(valid[j]);device=str(r['device']);assert int(r['label'])==y[j]
        assert capture_group[device+'|'+str(r['capture_id'])]==int(groups[j]);uid[side].append(r['uid']);counts[(device,int(y[j]),side)]+=1
        for field in ('capture_id','session_id','component_id'):
            value=str(r.get(field,''))
            if value not in ('','None','nan'):
                key=(device,field,value);assert key not in links or links[key]==side,'GROUP_LEAKAGE:'+field;links[key]=side
        for field in ('activity','protocol'):coverage[(device,int(y[j]),field,str(r.get(field,'')))][side]+=1
    for row in proposal['strata']:
        label=0 if row['label']=='normal' else 1
        assert counts[(row['device'],label,0)]==row['train_rows']>0 and counts[(row['device'],label,1)]==row['validation_rows']>0
    folder=HERE/'artifacts';folder.mkdir(exist_ok=True);np.save(folder/'INNER_VALID.npy',valid)
    # Proposed class-balanced validation measure: normalize the existing hierarchy
    # separately within each class. No metric is used to select a model here.
    val_ix=np.flatnonzero(valid);weights=np.zeros(len(val_ix),dtype=np.float64)
    for label in (0,1):
        take=np.flatnonzero(y[val_ix]==label);rr=[rows[int(fit[int(val_ix[j])])] for j in take];weights[take]=.5*k.class_weights(rr)
    assert abs(weights.sum()-1)<1e-10;np.save(folder/'VALID_WEIGHTS.npy',weights)
    missing=[dict(device=a,label=b,field=f,value=v,train=n[0],validation=n[1]) for (a,b,f,v),n in sorted(coverage.items()) if not all(n)]
    return dict(status='PASS',training_rows=int((~valid).sum()),validation_rows=int(valid.sum()),train_uid_sha256=k.c.uid_sha(uid[0]),validation_uid_sha256=k.c.uid_sha(uid[1]),mask_sha256=sha(folder/'INNER_VALID.npy'),weight_sha256=sha(folder/'VALID_WEIGHTS.npy'),device_class_coverage=True,capture_session_component_disjoint=True,activity_protocol_missing=missing,secondary_coverage_gate='NEEDS_REVIEW' if missing else 'PASS',strata=proposal['strata'],weight_definition='class mass .5 each; existing device/activity/capture/session hierarchy separately within class',target_scores_used=False)

def epoch(name):
    split_result=read(HERE/'SPLIT_RESULT.json');assert split_result['status']=='PASS'
    x,y,_=arrays();valid=np.load(HERE/'artifacts/INNER_VALID.npy');assert sha(HERE/'artifacts/INNER_VALID.npy')==split_result['mask_sha256'];validation=np.flatnonzero(valid)
    # Full refit-size resource probe. Validation timing overlaps its training
    # population, so NO validation metric or hyperparameter ranking is emitted.
    normal=name in ('DTE_EPOCH','SLAD_EPOCH');train=np.flatnonzero(y==0) if normal else np.arange(len(y));folder=HERE/'artifacts'/name;folder.mkdir(exist_ok=True)
    torch.manual_seed(27);np.random.seed(27);random.seed(27);prep=time.monotonic();scaler=None
    if normal:
        from sklearn.preprocessing import StandardScaler
        train_x=np.array(x[train],dtype=np.float32)
        if name=='DTE_EPOCH':scaler=StandardScaler().fit(train_x);train_x=scaler.transform(train_x).astype(np.float32)
    if name=='SLAD_EPOCH':
        model=slad();model.epoch_steps=-1;model.epochs=1;t=time.monotonic();model.fit(train_x);train_seconds=time.monotonic()-t;preparation_seconds=t-prep
        steps=math.ceil(model.n_ensemble*model.sampling_size/model.batch_size);resume='PENDING_AUTHOR_TRANSFORM_RNG_STATE'
        def score(ix):return np.asarray(model.decision_function(np.array(x[ix],dtype=np.float32)))
        net=model.net
    else:
        if name=='DTE_EPOCH':
            module=dte_module();wrapper=module.DTECategorical(device='cpu');wrapper.model=module.MLP([790]+wrapper.hidden_size,num_bins=7);net=wrapper.model;batch=64;opt=torch.optim.Adam(net.parameters(),lr=wrapper.lr,weight_decay=wrapper.weight_decay)
            def loss_for(ix):
                xx=torch.from_numpy(train_x[ix]);tt=torch.randint(0,wrapper.T,(len(ix),));return wrapper.compute_loss(xx,tt)
            def score(ix):return wrapper.predict_score(scaler.transform(np.array(x[ix],dtype=np.float32)).astype(np.float32))
        else:
            net=tabm();batch=256;opt=torch.optim.AdamW(net.parameters(),lr=.002,weight_decay=.0003)
            def loss_for(ix):
                xx=torch.from_numpy(np.array(x[ix]));yy=torch.from_numpy(np.array(y[ix]));return torch.nn.functional.cross_entropy(net(xx).flatten(0,1),yy.repeat_interleave(32))
            def score(ix):return tabm_score(net,torch.from_numpy(np.array(x[ix]))).numpy()
        order=np.random.permutation(len(train));preparation_seconds=time.monotonic()-prep;steps=math.ceil(len(train)/batch);t=time.monotonic();resume=False
        for step,start in enumerate(range(0,len(order),batch)):
            ix=order[start:start+batch];net.train();opt.zero_grad(set_to_none=True)
            if step==2:
                checkpoint=dict(model=net.state_dict(),optimizer=opt.state_dict(),torch_rng=torch.get_rng_state(),numpy_rng=np.random.get_state(),python_rng=random.getstate(),order=order,cursor=start)
                path=folder/'resume_probe.pt';torch.save(checkpoint,path);saved_sha=sha(path)
                loss=loss_for(ix);loss.backward();opt.step();expected={n:v.detach().clone() for n,v in net.state_dict().items()}
                assert sha(path)==saved_sha
                state=torch.load(path,weights_only=False);net.load_state_dict(state['model']);opt.load_state_dict(state['optimizer']);torch.set_rng_state(state['torch_rng']);np.random.set_state(state['numpy_rng']);random.setstate(state['python_rng']);assert state['cursor']==start and np.array_equal(state['order'],order)
                opt.zero_grad(set_to_none=True);loss=loss_for(ix);loss.backward();opt.step();assert all(torch.equal(expected[n],v) for n,v in net.state_dict().items());resume=True
            else:
                loss=loss_for(ix);assert torch.isfinite(loss);loss.backward();opt.step()
            if step%16==0:progress(name+'_FULL_REFIT_EPOCH',step+1,steps)
        train_seconds=time.monotonic()-t
    net.eval();scorefile=np.lib.format.open_memmap(folder/'validation_timing_scores.npy',mode='w+',dtype=np.float64,shape=(len(validation),));t=time.monotonic()
    with torch.inference_mode():
        for start in range(0,len(validation),256):
            ix=validation[start:start+256];scores=score(ix);assert np.isfinite(scores).all();scorefile[start:start+len(ix)]=scores
            if start%8192==0:progress(name+'_VALIDATION_TIMING',start,len(validation))
    scorefile.flush();validation_seconds=time.monotonic()-t;torch.save(net.state_dict(),folder/'model.pt')
    return dict(status='PASS',train_rows=len(train),full_epoch=True,steps=steps,preparation_seconds=preparation_seconds,train_seconds=train_seconds,validation_rows=len(validation),validation_seconds=validation_seconds,checkpoint_sha256=sha(folder/'model.pt'),same_process_optimizer_rng_cursor_replay_exact=resume,fresh_process_resume_gate='PENDING',purpose='RESOURCE_ONLY_FULL_REFIT_SIZE; validation overlap; scores prohibited for tuning or reporting accuracy',formal_training=False)

def review():
    inventory={}
    for name,args in [('partitions',['sinfo','-h','-o','%P|%a|%l|%D|%c|%m|%G']),('limits',['sacctmgr','-n','-P','show','assoc','where','user=jiangxinwei.zr','format=Account,Partition,QOS,MaxWall,MaxTRESPJ'])]:
        try:r=subprocess.run(args,capture_output=True,text=True,timeout=20);inventory[name]=dict(returncode=r.returncode,stdout=r.stdout[:12000],stderr=r.stderr[:1000])
        except Exception as e:inventory[name]=dict(error=type(e).__name__)
    return dict(status='PASS',scope='RESOURCE_GATE_REPORT_NOT_FORMAL_RELEASE',inventory=inventory,epochs={n:read(HERE/(n+'_RESULT.json')) for n in ['DTE_EPOCH','SLAD_EPOCH','TABM_EPOCH']},remaining=['Review activity/protocol coverage and source-only selection weighting','Fresh-process optimizer/RNG/sampler recovery for every method','TabR and DisentAD full epochs on suitable resources','ModernNCA full backward memory qualification','CatBoost steady-state training/quantization separation and resume','Enumerated16-trial constructor and worst-case resource qualification'],formal_training_ready=False,main_model_changed=False)
