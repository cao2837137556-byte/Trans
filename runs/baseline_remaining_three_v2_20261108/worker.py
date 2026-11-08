"""Fixed source-only training. Parent packages and main model are read-only."""
import argparse,copy,gc,json,math,os,random,sys,time,traceback,types,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'baseline_author_defaults_v1_20261108'
sys.path.insert(0,str(OLD))
import formal as f,pipeline_parent as p,adapters
import numpy as np
import torch
CFG=p.read(HERE/'CONFIG.json')

def init(seed=27):
    f.setup(seed)
    p.HERE=HERE;f.HERE=HERE
    torch.set_num_threads(int(os.environ.get('SLURM_CPUS_PER_TASK','1')))
    if torch.cuda.is_available():torch.cuda.manual_seed_all(seed)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    for n,h in p.read(HERE/'PARENT_PINS.json').items():assert p.sha(OLD/n)==h,'PARENT_SHA:'+n
    for n,h in p.read(OLD/'INPUT_PINS.json').items():assert p.sha(p.PROJECT/n)==h,'FROZEN_DEPENDENCY_SHA:'+n
    for n,h in p.read(HERE/'.private.json')['pins'].items():assert p.sha(HERE/n)==h,'PACKAGE_SHA:'+n

def sync():
    if torch.cuda.is_available():torch.cuda.synchronize()

class HostFaissIndex:
    """Exact official CPU FAISS; only tensor transport differs from GPU FAISS.

    Includes ALL candidates, float32 IndexFlatL2, no approximate retrieval.
    The unchanged author Model still owns query self-exclusion and recomputation.
    """
    def __init__(self,resource,d):
        import faiss,faiss.contrib.torch_utils
        self.index=faiss.IndexFlatL2(d)
    def reset(self):self.index.reset()
    def add(self,x):self.index.add(x.detach().cpu().contiguous().numpy())
    def search(self,q,k):
        d,i=self.index.search(q.detach().cpu().contiguous().numpy(),k)
        return torch.as_tensor(d,device=q.device),torch.as_tensor(i,device=q.device)

def model(method,device):
    if method=='TabM':m=adapters.tabm()
    elif method=='DisentAD':
        import importlib.util
        sp=importlib.util.spec_from_file_location('disnet',OLD/'vendor/disent_ad/network__dis_net.py');mod=importlib.util.module_from_spec(sp);sp.loader.exec_module(mod)
        m=mod.DisNet(dim=128,att_dim=1)
    else:
        import faiss,faiss.contrib.torch_utils
        faiss.omp_set_num_threads(torch.get_num_threads())
        bridge=types.SimpleNamespace(IndexFlatL2=faiss.IndexFlatL2,GpuIndexFlatL2=HostFaissIndex,StandardGpuResources=lambda:None)
        m,c=adapters.tabr(bridge);c.update(CFG['methods']['TabR']['architecture']);m=type(m)(**c)
    return m.to(device)

def optimizer(method,m):
    c=CFG['methods'][method]
    # TabR pinned lib/deep.py deliberately preserves all-parameter weight decay
    # for paper compatibility, including biases/norm/label embeddings (issue 19).
    return getattr(torch.optim,c['optimizer'])(m.parameters(),lr=c['lr'],weight_decay=c['weight_decay'])

def state(m,opt):
    return dict(model=m.state_dict(),optimizer=opt.state_dict(),rng=f.rng(),cuda_rng=torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None,config_sha256=p.sha(HERE/'CONFIG.json'))

def restore(m,opt,s):
    assert s['config_sha256']==p.sha(HERE/'CONFIG.json')
    m.load_state_dict(s['model']);opt.load_state_dict(s['optimizer']);f.restore(s['rng'])
    if s['cuda_rng'] is not None:torch.cuda.set_rng_state_all(s['cuda_rng'])

def dataset(method,device,subset=None):
    x,y=f.source(method=='DisentAD')
    if subset is not None:x=x[subset];y=None if y is None else y[subset]
    return torch.as_tensor(np.array(x,copy=True),device=device),None if y is None else torch.as_tensor(np.array(y,copy=True),device=device)

def logits(m,method,x,ix,y):
    if method=='TabM':return m(x[ix])
    if method=='DisentAD':return m(x[ix].unsqueeze(-1))
    take=torch.ones(len(x),device=x.device,dtype=torch.bool);take[ix]=False
    return m(x_={'num':x[ix]},y=y[ix],candidate_x_={'num':x[take]},candidate_y=y[take],context_size=96,is_train=True).flatten()

def step(m,opt,method,x,y,ix):
    m.train();opt.zero_grad(set_to_none=True);v=logits(m,method,x,ix,y)
    if method=='TabM':loss=torch.nn.functional.cross_entropy(v.flatten(0,1),y[ix].repeat_interleave(32))
    elif method=='TabR':loss=torch.nn.functional.binary_cross_entropy_with_logits(v,y[ix].float())
    else:loss=v[0]+v[1]
    assert torch.isfinite(loss),'NONFINITE_LOSS';loss.backward()
    if method=='TabM':torch.nn.utils.clip_grad_norm_(m.parameters(),1.)
    opt.step();return float(loss.detach())

@torch.inference_mode()
def score(m,method,q,x=None,y=None):
    m.eval();out=[];batch=CFG['methods'][method]['score_batch']
    for off in range(0,len(q),batch):
        v=q[off:off+batch]
        if method=='TabM':v=adapters.tabm_score(m,v)
        elif method=='DisentAD':v=m(v.unsqueeze(-1))
        else:v=m(x_={'num':v},y=None,candidate_x_={'num':x},candidate_y=y,context_size=96,is_train=False).flatten().sigmoid()
        out.append(v.cpu().numpy())
    return np.concatenate(out)

def folder(method,seed,phase):
    q=HERE/'artifacts'/method/str(seed)/phase;q.mkdir(parents=True,exist_ok=True);return q

def train(method,seed,phase,epochs=None):
    init(seed);device='cuda';assert torch.cuda.is_available(),'GPU_REQUIRED'
    valid=np.load(HERE/'artifacts/INNER_VALID.npy') if method!='DisentAD' else None
    if valid is not None:assert p.sha(HERE/'artifacts/INNER_VALID.npy')==p.read(HERE/'SPLIT_RESULT.json')['mask_sha256'],'SOURCE_SPLIT_SHA'
    if phase=='select':
        x,y=dataset(method,device,np.flatnonzero(~valid));vx,vy=dataset(method,device,np.flatnonzero(valid))
    else:x,y=dataset(method,device)
    m=model(method,device);opt=optimizer(method,m);dest=folder(method,seed,phase)
    done=dest/'COMPLETE.json'
    if done.exists():return p.read(done)
    checkpoint=dest/'checkpoint.pt';epoch=0;order=None;cursor=0;loss_sum=0.;steps=0;best=None;best_epoch=0;bad=0
    if checkpoint.exists():
        st=torch.load(checkpoint,map_location='cpu',weights_only=False);restore(m,opt,st)
        epoch,order,cursor,loss_sum,steps,best,best_epoch,bad=[st[n] for n in ('epoch','order','cursor','loss_sum','steps','best','best_epoch','bad')]
    batch=CFG['methods'][method]['batch'];t=time.monotonic();limit=epochs or CFG['operational_epoch_cap']
    def save():
        st=state(m,opt);st.update(epoch=epoch,order=order,cursor=cursor,loss_sum=loss_sum,steps=steps,best=best,best_epoch=best_epoch,bad=bad)
        f.save(checkpoint,st)
    while epoch<limit:
        if order is None:order=np.random.permutation(len(x))
        for start in range(cursor,len(order),batch):
            ix=torch.as_tensor(order[start:start+batch],device=device);loss_sum+=step(m,opt,method,x,y,ix);steps+=1;cursor=start+len(ix)
            if steps%16==0:p.progress(f'{method}_{seed}_{phase}_EPOCH_{epoch+1}',cursor,len(order),epoch=epoch+1,best_epoch=best_epoch,bad_epochs=bad)
            if steps%128==0:save()
        sync();epoch+=1
        value=None
        if phase=='select':value=float(((score(m,method,vx,x,y)>.5)==vy.cpu().numpy()).mean())
        elif method=='DisentAD':value=-loss_sum/steps
        else:value=float(epoch)
        if best is None or value>best:
            best=value;best_epoch=epoch;bad=0;f.save(dest/'best.pt',dict(model=m.state_dict(),epoch=epoch,config_sha256=p.sha(HERE/'CONFIG.json')))
        else:bad+=1
        p.write(f'{method}_{seed}_{phase}_LATEST.json',dict(epoch=epoch,best_epoch=best_epoch,source_selection_value=value,bad_epochs=bad,seconds=time.monotonic()-t))
        order=None;cursor=0;loss_sum=0.;steps=0;save()
        if phase=='select' and bad>16:break
    assert phase!='select' or bad>16,'OPERATIONAL_CAP_NOT_CONVERGED_NOT_ACCEPTED'
    r=dict(status='PASS',method=method,seed=seed,phase=phase,epochs=epoch,best_epoch=best_epoch,best_value=best,best_sha256=p.sha(dest/'best.pt'),checkpoint_sha256=p.sha(checkpoint),source_only=True)
    done.write_text(json.dumps(r,indent=2));return r

def predictor(method,seed):
    device='cuda';m=model(method,device);dest=folder(method,seed,'refit');r=p.read(dest/'COMPLETE.json');assert p.sha(dest/'best.pt')==r['best_sha256']
    s=torch.load(dest/'best.pt',weights_only=False,map_location='cpu');assert s['config_sha256']==p.sha(HERE/'CONFIG.json');m.load_state_dict(s['model']);m.eval()
    x,y=dataset(method,device) if method=='TabR' else (None,None)
    def predict(q):return score(m,method,torch.as_tensor(q,device=device),x,y)
    return predict

def resume_child(method):
    init(27);dest=folder(method,27,'qualification');s=torch.load(dest/'resume.pt',weights_only=False,map_location='cpu')
    device='cuda' if torch.cuda.is_available() else 'cpu';x=torch.as_tensor(s['x'],device=device);y=None if s['y'] is None else torch.as_tensor(s['y'],device=device)
    m=model(method,device);opt=optimizer(method,m);restore(m,opt,s);step(m,opt,method,x,y,torch.arange(4,8,device=device))
    f.save(dest/'actual.pt',dict(model=m.state_dict(),optimizer=opt.state_dict(),rng=f.rng(),cuda_rng=torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None))
    # This child constructs directly from state dict; no trainer-created modules
    # or wrappers are required to unpickle the formal predictor.
    np.save(dest/'actual_scores.npy',score(m,method,x[:8],x,y))

def qualify(method):
    init(27);assert torch.cuda.is_available(),'GPU_REQUIRED';device='cuda';torch.cuda.reset_peak_memory_stats()
    dest=folder(method,27,'qualification');x,y=dataset(method,device);m=model(method,device);opt=optimizer(method,m)
    # Fresh-process exact recovery of optimizer, sampler and CPU/CUDA RNG.
    xx=x[:128].clone();yy=None if y is None else y[:128].clone();step(m,opt,method,xx,yy,torch.arange(4,device=device))
    st=state(m,opt);st.update(x=xx.cpu().numpy(),y=None if yy is None else yy.cpu().numpy());f.save(dest/'resume.pt',st)
    step(m,opt,method,xx,yy,torch.arange(4,8,device=device));expected={k:v.detach().cpu().clone() for k,v in m.state_dict().items()};expected_opt=copy.deepcopy(opt.state_dict());expected_scores=score(m,method,xx[:8],xx,yy)
    subprocess.run([sys.executable,'-X','utf8','-B',str(HERE/'worker.py'),'resume',method],check=True,timeout=240)
    actual=torch.load(dest/'actual.pt',weights_only=False,map_location='cpu');assert all(torch.equal(v,actual['model'][k]) for k,v in expected.items()),'FRESH_PROCESS_UPDATE_PARITY'
    for k,v in expected_opt['state'].items():
        for n,a in v.items():assert torch.equal(a.cpu(),actual['optimizer']['state'][k][n]) if torch.is_tensor(a) else a==actual['optimizer']['state'][k][n]
    assert np.array_equal(expected_scores,np.load(dest/'actual_scores.npy')),'CLEAN_SCORE_PARITY'
    del xx,yy,st,actual,expected,expected_opt,m,opt;gc.collect();torch.cuda.empty_cache()
    # Discard the probe model; complete a fresh full-size epoch on real FIT.
    torch.manual_seed(27);torch.cuda.manual_seed_all(27);m=model(method,device);opt=optimizer(method,m)
    if method=='TabR':
        cpu=model(method,'cpu');cpu.load_state_dict(m.state_dict());q=x[:8];pool=x[:128];labels=y[:128]
        with torch.no_grad():
            a=score(cpu,method,q.cpu(),pool.cpu(),labels.cpu());b=score(m,method,q,pool,labels)
        err=float(np.max(np.abs(a-b)));assert err<2e-5,'TABR_TRANSPORT_PARITY';del cpu
    else:err=None
    batch=CFG['methods'][method]['batch'];t=time.monotonic();order=np.random.permutation(len(x))
    for j,start in enumerate(range(0,len(x),batch)):
        step(m,opt,method,x,y,torch.as_tensor(order[start:start+batch],device=device))
        if j%16==0:p.progress(method+'_QUALIFY_FULL_EPOCH',start+min(batch,len(x)-start),len(x))
    sync();epoch_seconds=time.monotonic()-t
    pilot=np.load(HERE/'PILOT_INPUTS.npz');t=time.monotonic();outputs={}
    for pool in ['cal','CIC_DEV','UNSW_DEV','EDGE']:
        outputs[pool]=score(m,method,torch.as_tensor(pilot[pool+'_x'],device=device),x,y);assert np.isfinite(outputs[pool]).all()
    sync();score_seconds=time.monotonic()-t
    p.bootstrap();import context_core as k
    cut=float(k.threshold(outputs['cal'],p.read(HERE/'CAL_ROWS.json'),.01));assert float(pilot['cal_w'][outputs['cal']>cut].sum())<=.010000000001
    n=sum(z['rows'] for z in p.read(HERE/'EVALUATION_INPUTS.json')['pools'].values());eval_est=score_seconds*n/sum(len(a) for a in outputs.values())*3*1.5
    # Measured conservative bound; early-stop methods use a planning horizon,
    # never treat it as completed convergence or truncate accepted training.
    planning=100 if method=='DisentAD' else 100
    estimate=epoch_seconds*planning*3*(1 if method=='DisentAD' else 2)*1.35+eval_est+3600
    r=dict(status='PASS',full_epoch_rows=len(x),epoch_seconds=epoch_seconds,pilot_score_seconds=score_seconds,estimated_seconds=estimate,planning_epochs=planning,peak_gpu_gib=torch.cuda.max_memory_allocated()/2**30,gpu=torch.cuda.get_device_name(),fresh_process_resume_exact=True,pure_prediction_reload_exact=True,tabr_cpu_gpu_transport_error=err,all_candidates=True,scope='ENGINEERING_ONLY_NOT_FORMAL_MODEL')
    assert r['peak_gpu_gib']<torch.cuda.get_device_properties(0).total_memory/2**30*.85,'GPU_HEADROOM_GATE'
    p.write(method+'_QUALIFY.json',r)
    assert estimate<CFG['method_wall_seconds']-7200,'MEASURED_BUDGET_INSUFFICIENT'
    return r

def main():
    a=argparse.ArgumentParser();a.add_argument('action');a.add_argument('method');args=a.parse_args();os.environ['BASELINE_METHOD']=args.method;init()
    if args.action=='resume':return resume_child(args.method)
    if args.action=='qualify':return qualify(args.method)
    if args.action=='evaluate':
        def boot():
            c=p.bootstrap();torch.set_num_threads(int(os.environ.get('SLURM_CPUS_PER_TASK','1')));return c
        f.bootstrap=boot
        f.predictor=predictor;r=f.evaluate(args.method);p.write(args.method+'_EVALUATE.json',r);return r
    if args.action.startswith('train-'):
        seed=int(args.action.split('-')[1]);method=args.method
        epochs=CFG['methods'][method].get('epochs')
        if epochs is None:epochs=train(method,seed,'select')['best_epoch']
        return train(method,seed,'refit',epochs)
    raise ValueError(args.action)

if __name__=='__main__':
    try:main()
    except Exception as e:
        p.HERE=HERE;p.write(os.environ.get('BASELINE_METHOD','WORKER')+'_ERROR.json',dict(status='FAIL',error=str(e),traceback=traceback.format_exc()));raise
