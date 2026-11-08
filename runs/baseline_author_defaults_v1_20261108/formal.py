"""Fixed official configurations, full legal FIT, independent CAL and fixed targets.

No target score participates in configuration, training, or stopping decisions.
"""
import argparse,copy,gc,importlib.util,json,os,pickle,random,sys,time,traceback
from pathlib import Path
import numpy as np
import torch
from pipeline_parent import HERE,PROJECT,SOURCE,EVAL,read,write,sha,bootstrap,progress
from readiness import install_assets,dte_module
OLD=PROJECT/'runs/baseline_training_readiness_v6_20261107'

def setup(seed):
    install_assets();torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    torch.manual_seed(seed);np.random.seed(seed);random.seed(seed)

def save(path,state):
    temp=path.with_suffix('.tmp');torch.save(state,temp);temp.replace(path)

def rng():return dict(torch=torch.get_rng_state(),numpy=np.random.get_state(),python=random.getstate())
def restore(r):
    torch.set_rng_state(r['torch']);np.random.set_state(r['numpy']);random.setstate(r['python'])

def source(normal):
    result=read(OLD/'SOURCE_RESULT.json');name='NORMAL_X.npy' if normal else 'FIT_X.npy'
    p=OLD/'artifacts/source'/name;assert sha(p)==result['sha256'][name]
    x=np.load(p,mmap_mode='r');y=None
    if not normal:
        p=p.with_name('FIT_y.npy');assert sha(p)==result['sha256'][p.name];y=np.load(p,mmap_mode='r')
    return x,y

def construct(method,seed,x):
    from torch.utils.data import DataLoader
    if method=='DTE-C':
        from sklearn.preprocessing import StandardScaler
        scaler=StandardScaler().fit(x);xx=scaler.transform(x).astype('float32')
        mod=dte_module();m=mod.DTECategorical(seed=seed,device='cpu')
        m.model=mod.MLP([790]+m.hidden_size,num_bins=m.num_bins)
        loader=DataLoader(torch.from_numpy(xx),batch_size=m.batch_size,shuffle=True,drop_last=False)
        opt=torch.optim.Adam(m.model.parameters(),lr=m.lr,weight_decay=m.weight_decay)
        return m,scaler,loader,opt
    assert method=='SLAD'
    sys.path.insert(0,str(HERE/'vendor/slad'));from algorithms.slad import SLAD
    m=SLAD(device='cpu',verbose=0,random_state=seed);m.n_samples,m.n_features=x.shape
    m.train_loader,m.net,m.criterion=m.training_prepare(x)
    opt=torch.optim.Adam(m.net.parameters(),lr=m.lr,weight_decay=1e-5)
    return m,None,m.train_loader,opt

def network(method,m):return m.model if method=='DTE-C' else m.net
def loss(method,m,batch):
    if method=='DTE-C':return m.compute_loss(batch,torch.randint(0,m.T,(len(batch),)))
    return m.training_forward(batch,m.net,m.criterion)

def snapshot(method,m,scaler,opt,epoch):
    # DTE wrapper holds an unpicklable closure. Reconstruct it from pinned author code.
    slad_state=copy.copy(m) if method=='SLAD' else None
    if slad_state is not None:slad_state.train_loader=None
    return dict(method=method,model=network(method,m).state_dict(),slad=slad_state,
                scaler=scaler,optimizer=opt.state_dict(),rng=rng(),epoch=epoch,config_sha256=sha(HERE/'CONFIG.json'))

def load_state(method,m,scaler,opt,path):
    st=torch.load(path,weights_only=False,map_location='cpu');assert st['config_sha256']==sha(HERE/'CONFIG.json')
    if method=='SLAD':
        m=st['slad'];opt=torch.optim.Adam(m.net.parameters(),lr=m.lr,weight_decay=1e-5)
    network(method,m).load_state_dict(st['model']);opt.load_state_dict(st['optimizer']);restore(st['rng'])
    return m,st['scaler'],opt,st

def one_epoch(method,m,loader,opt,label):
    net=network(method,m);net.train();total=0.;count=0;t=time.monotonic()
    for j,batch in enumerate(loader):
        opt.zero_grad(set_to_none=True);v=loss(method,m,batch);assert torch.isfinite(v);v.backward();opt.step()
        total+=float(v.detach());count+=1
        if j%64==0:progress(label,j,len(loader))
    if method=='SLAD':m.epoch_update()
    return dict(seconds=time.monotonic()-t,loss=total/count,steps=count)

def resume_probe(method,seed,folder):
    # Separate Python process replays the same next epoch from the same checkpoint.
    setup(seed);x,_=source(True);x=np.array(x[:512],copy=True)
    m,s,loader,opt=construct(method,seed,x)
    p=folder/'resume.pt';m,s,opt,st=load_state(method,m,s,opt,p)
    loader=loader
    one_epoch(method,m,loader,opt,'RESUME_CHILD')
    save(folder/'resume_actual.pt',network(method,m).state_dict())

def qualify(method,seed):
    import subprocess
    folder=HERE/'artifacts'/method/str(seed);folder.mkdir(parents=True,exist_ok=True)
    x,_=source(method!='CatBoost');start=time.monotonic()
    if method=='CatBoost':
        from catboost import CatBoostClassifier
        xx,y=source(False)
        # Keep official 1000-iteration auto learning rate; stop only this resource probe.
        class ProbeStop:
            def after_iteration(self,info):
                progress('CATBOOST_RESOURCE_ITERATION',info.iteration,32)
                return info.iteration<32
        m=CatBoostClassifier(iterations=1000,loss_function='Logloss',random_seed=seed,thread_count=1,verbose=False,allow_writing_files=False)
        m.fit(xx,y,callbacks=[ProbeStop()]);elapsed=time.monotonic()-start
        m.save_model(str(folder/'probe.cbm'));before=m.predict(xx[:16],prediction_type='RawFormulaVal')
        m.load_model(str(folder/'probe.cbm'));assert np.array_equal(before,m.predict(xx[:16],prediction_type='RawFormulaVal'))
        return dict(status='PASS',train_rows=len(y),probe_iterations=m.tree_count_,seconds=elapsed,
                    estimated_train_seconds=elapsed/max(1,m.tree_count_)*1000*1.5,
                    resolved_parameters=m.get_all_params(),resume='native snapshot enabled in formal; no init_model continuation')
    small=np.array(x[:512],copy=True);m,s,loader,opt=construct(method,seed,small)
    one_epoch(method,m,loader,opt,'RESUME_WARMUP');save(folder/'resume.pt',snapshot(method,m,s,opt,1))
    one_epoch(method,m,loader,opt,'RESUME_EXPECTED');expected={k:v.detach().clone() for k,v in network(method,m).state_dict().items()}
    subprocess.run([sys.executable,'-X','utf8','-B',str(HERE/'formal.py'),'--action','resume','--method',method,'--seed',str(seed)],check=True,timeout=600)
    actual=torch.load(folder/'resume_actual.pt',weights_only=True);assert all(torch.equal(expected[k],actual[k]) for k in expected),'FRESH_PROCESS_RESUME'
    del m,s,loader,opt;gc.collect();setup(seed)
    m,s,loader,opt=construct(method,seed,np.array(x,copy=True));r=one_epoch(method,m,loader,opt,'FULL_RESOURCE_EPOCH')
    # Inference on a bounded real slice proves scoring and estimates evaluation overhead.
    t=time.monotonic();score=m.predict_score(s.transform(x[:1024]).astype('float32')) if method=='DTE-C' else m.decision_function(x[:1024]);assert np.isfinite(score).all()
    return dict(status='PASS',train_rows=len(x),full_epoch=r,fresh_process_resume_exact=True,
                score_1024_seconds=time.monotonic()-t,estimated_train_seconds=r['seconds']*(400 if method=='DTE-C' else 100)*1.5)

def train(method,seed):
    folder=HERE/'artifacts'/method/str(seed);folder.mkdir(parents=True,exist_ok=True)
    if method=='CatBoost':
        from catboost import CatBoostClassifier
        x,y=source(False)
        class Track:
            def after_iteration(self,info):
                progress('CatBoost_'+str(seed)+'_TRAIN',info.iteration,1000);return True
        m=CatBoostClassifier(iterations=1000,loss_function='Logloss',random_seed=seed,thread_count=1,verbose=False,
                             train_dir=str(folder/'native'),save_snapshot=True,snapshot_interval=60)
        t=time.monotonic();m.fit(x,y,callbacks=[Track()]);assert m.tree_count_==1000
        m.save_model(str(folder/'model.cbm'))
        return dict(status='PASS',train_rows=len(y),iterations=m.tree_count_,parameters=m.get_all_params(),seconds=time.monotonic()-t,checkpoint_sha256=sha(folder/'model.cbm'))
    x,_=source(True);m,s,loader,opt=construct(method,seed,np.array(x,copy=True));epochs=400 if method=='DTE-C' else 100;start=0
    checkpoint=folder/'checkpoint.pt'
    if checkpoint.exists():
        m,s,opt,st=load_state(method,m,s,opt,checkpoint);start=st['epoch'];loader=loader
    history=[];t=time.monotonic()
    for epoch in range(start,epochs):
        r=one_epoch(method,m,loader,opt,method+'_'+str(seed)+'_EPOCH_'+str(epoch+1)+'/'+str(epochs));history.append(r)
        save(checkpoint,snapshot(method,m,s,opt,epoch+1));write(method+'_'+str(seed)+'_TRAIN_PROGRESS.json',dict(epoch=epoch+1,epochs=epochs,last_epoch=r,elapsed_seconds=time.monotonic()-t))
    return dict(status='PASS',train_rows=len(x),epochs=epochs,seconds=time.monotonic()-t,epoch_seconds=[r['seconds'] for r in history],checkpoint_sha256=sha(checkpoint))

def predictor(method,seed):
    folder=HERE/'artifacts'/method/str(seed)
    if method=='CatBoost':
        from catboost import CatBoostClassifier
        m=CatBoostClassifier();m.load_model(str(folder/'model.cbm'))
        return lambda x:np.asarray(m.predict(x,prediction_type='RawFormulaVal'))
    st=torch.load(folder/'checkpoint.pt',weights_only=False,map_location='cpu')
    assert st['config_sha256']==sha(HERE/'CONFIG.json') and st['epoch']==(400 if method=='DTE-C' else 100)
    if method=='SLAD':m=st['slad'];m.net.eval();return m.decision_function
    mod=dte_module();m=mod.DTECategorical(device='cpu');m.model=mod.MLP([790]+m.hidden_size,num_bins=m.num_bins);m.model.load_state_dict(st['model']);m.model.eval()
    return lambda x:m.predict_score(st['scaler'].transform(x).astype('float32'))

def prepare_evaluation():
    c=bootstrap();c.verify();k,norm,arms=c.models();del arms;gc.collect()
    import inputs,edge_context
    folder=HERE/'artifacts/evaluation';folder.mkdir(parents=True,exist_ok=True);manifest={}
    for pool in ['CAL','CIC_DEV','UNSW_DEV','EDGE']:
        if pool=='CAL':
            rows,z,q,ctx=inputs.source_role('LEARN');ix=np.load(SOURCE/'metadata/CAL.npy');ix=ix[[rows[int(i)]['label']==0 for i in ix]]
            rr=[rows[int(i)] for i in ix];assert len(rr)==33147
            z=z[ix];q=q[ix];ctx=c.extra_normalized(ctx[ix]);data=dict(rows=rr,z=z,q=q,context=ctx,views={'full':(np.arange(len(rr)),k.class_weights(rr))})
        elif pool=='EDGE':
            data=inputs.edge();ix,data['context']=edge_context.join(data['rows']);assert np.array_equal(ix,np.arange(60000))
        else:data=inputs.ab(pool)
        rows=data['rows']
        for r in rows:r.setdefault('scenario',r.get('activity',r.get('source_role','UNKNOWN')));r.setdefault('source_role','NORMAL' if r['label']==0 else r['scenario'])
        xx=np.lib.format.open_memmap(folder/(pool+'_X.npy'),mode='w+',dtype='float32',shape=(len(rows),790))
        for off in range(0,len(rows),1024):
            ix=np.arange(off,min(len(rows),off+1024));xx[ix]=k.normalized((data['z'][ix],data['context'][ix]),data['q'][ix],np.arange(len(ix)),norm,790).numpy()
        xx.flush();write('artifacts/evaluation/'+pool+'_ROWS.json',rows)
        if pool!='EDGE':np.savez(folder/(pool+'_VIEWS.npz'),**{v+'_'+s:pair[j] for v,pair in data['views'].items() for j,s in enumerate(['ix','weight'])})
        manifest[pool]=dict(rows=len(rows),uid_sha256=k.c.uid_sha(r['uid'] for r in rows),x_sha256=sha(folder/(pool+'_X.npy')),rows_sha256=sha(folder/(pool+'_ROWS.json')))
        del data,rows,xx;gc.collect();progress('EVALUATION_INPUTS_'+pool,1,1)
    write('EVALUATION_INPUTS.json',dict(status='PASS',pools=manifest));return dict(status='PASS',pools=manifest)

def evaluate(method):
    c=bootstrap();import context_core as k,metrics,reporting
    from sklearn.metrics import roc_auc_score,average_precision_score
    folder=HERE/'artifacts/evaluation';scores={};summary={};cuts=None
    for pool in ['CAL','CIC_DEV','UNSW_DEV','EDGE']:
        spec=read(HERE/'EVALUATION_INPUTS.json')['pools'][pool];assert sha(folder/(pool+'_X.npy'))==spec['x_sha256'];assert sha(folder/(pool+'_ROWS.json'))==spec['rows_sha256']
        x=np.load(folder/(pool+'_X.npy'),mmap_mode='r');rows=read(folder/(pool+'_ROWS.json'));v=[]
        for seed in [27,127,227]:
            fn=predictor(method,seed);out=[];t=time.monotonic()
            with torch.inference_mode():
                for off in range(0,len(x),256):
                    s=np.asarray(fn(np.array(x[off:off+256],copy=True)),dtype='float64');assert s.shape==(min(256,len(x)-off),) and np.isfinite(s).all();out.append(s)
                    if off%8192==0:progress(method+'_'+str(seed)+'_SCORE_'+pool,off,len(x))
            v.append(np.concatenate(out));del fn;gc.collect()
        raw=c.four(np.column_stack(v));np.save(folder/(method+'_'+pool+'_scores.npy'),raw)
        if pool=='CAL':
            cuts=np.asarray([k.threshold(raw[:,j],rows,.01) for j in range(4)]);weights=k.class_weights(rows)
            fpr=[float(weights[raw[:,j]>cuts[j]].sum()) for j in range(4)];assert max(fpr)<=.010000000001
            summary[pool]=dict(cuts=cuts.tolist(),normal_rows=len(rows),weighted_fpr=fpr)
        elif pool=='EDGE':
            pop=c.read(c.ROOT/'runs/edge_formal_execution_v4_20261104/POPULATION_TEMPORAL_CENSUS.json')
            r=reporting.summarise(rows,{'RAW':raw>cuts},population=pop,prediction_uids={'RAW':[r['uid'] for r in rows]},raw_name='RAW',independent_methods=());r.pop('ordered_query_uids',None);summary[pool]=r
        else:
            a=np.load(folder/(pool+'_VIEWS.npz'));views={n:(a[n+'_ix'],a[n+'_weight']) for n in ['full','primary']};summary[pool]=metrics.summarize(rows,{method:{'RAW':raw>cuts}},views)
        if pool!='CAL':
            labels=np.asarray([r['label'] for r in rows]);summary[pool]['ranking_full_ordinary']={str(h):dict(auroc=float(roc_auc_score(labels,raw[:,j])),auprc=float(average_precision_score(labels,raw[:,j])),prevalence=float(labels.mean())) for j,h in enumerate([27,127,227,'ensemble'])}
        scores[pool]=dict(sha256=sha(folder/(method+'_'+pool+'_scores.npy')),uid_sha256=spec['uid_sha256']);write(method+'_METRICS.json',summary)
    return dict(status='PASS',method=method,metrics_sha256=sha(HERE/(method+'_METRICS.json')),scores=scores,scope='shared790 RAW; main system has additional normal-reference access',targets_consumed=True)

def main():
    a=argparse.ArgumentParser();a.add_argument('--action',required=True);a.add_argument('--method',default='');a.add_argument('--seed',type=int,default=27);args=a.parse_args();setup(args.seed)
    if args.action=='resume':return resume_probe(args.method,args.seed,HERE/'artifacts'/args.method/str(args.seed))
    name=args.action+'_'+args.method+'_'+str(args.seed);t=time.monotonic()
    try:
        result={'qualify':lambda:qualify(args.method,args.seed),'train':lambda:train(args.method,args.seed),'evaluate':lambda:evaluate(args.method),'inputs':prepare_evaluation}[args.action]()
        result['wall_seconds']=time.monotonic()-t;write(name+'_RESULT.json',result)
    except Exception as e:write(name+'_STOP.json',dict(status='FAIL',error=str(e),traceback=traceback.format_exc()));raise
if __name__=='__main__':main()
