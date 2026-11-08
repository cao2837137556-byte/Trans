"""Local contract regression; CUDA/full-size release remains a compute-node gate."""
import copy,json,os,subprocess,sys,types,collections
from pathlib import Path
HERE=Path(__file__).resolve().parent
def oracle():
    import numpy as np,torch
    class Index:
        def __init__(self,d):pass
        def reset(self):pass
        def add(self,x):self.x=torch.as_tensor(x).clone()
        def search(self,q,k):
            is_numpy=isinstance(q,np.ndarray);q=torch.as_tensor(q);d=(q[:,None,:]-self.x[None,:,:]).square().sum(-1);v,i=d.topk(k,largest=False,sorted=True)
            return (v.numpy(),i.numpy()) if is_numpy else (v,i)
    mod=types.ModuleType('faiss');mod.IndexFlatL2=Index;mod.omp_set_num_threads=lambda n:None;mod.contrib=types.ModuleType('faiss.contrib');mod.contrib.torch_utils=types.ModuleType('faiss.contrib.torch_utils')
    sys.modules.update({'faiss':mod,'faiss.contrib':mod.contrib,'faiss.contrib.torch_utils':mod.contrib.torch_utils})

def main():
    oracle();import worker as w,preflight
    w.torch.set_num_threads(1);results={}
    for method in ['TabM','TabR','DisentAD']:
        w.torch.manual_seed(27);w.np.random.seed(27);w.random.seed(27)
        m=w.model(method,'cpu');opt=w.optimizer(method,m);x=w.torch.randn(128,790);y=None if method=='DisentAD' else w.torch.arange(128)%2
        w.step(m,opt,method,x,y,w.torch.arange(4));dest=w.folder(method,27,'qualification');st=w.state(m,opt);st.update(x=x.numpy(),y=None if y is None else y.numpy());w.f.save(dest/'resume.pt',st)
        w.step(m,opt,method,x,y,w.torch.arange(4,8));expected={k:v.detach().clone() for k,v in m.state_dict().items()};scores=w.score(m,method,x[:8],x,y)
        code="import test_regression as t;t.oracle();import worker as w;w.init=lambda *a: w.torch.set_num_threads(1);w.resume_child("+repr(method)+")"
        r=subprocess.run([sys.executable,'-X','utf8','-B','-c',code],cwd=HERE,capture_output=True,text=True,timeout=120);assert r.returncode==0,r.stderr
        actual=w.torch.load(dest/'actual.pt',map_location='cpu',weights_only=False);assert all(w.torch.equal(v,actual['model'][k]) for k,v in expected.items());assert w.np.array_equal(scores,w.np.load(dest/'actual_scores.npy'))
        results[method]=dict(fresh_process_updated_weights_exact=True,clean_process_score_exact=True,shape=list(scores.shape),finite=bool(w.np.isfinite(scores).all()),faiss='local exhaustive oracle only' if method=='TabR' else None)
    counts=collections.defaultdict(collections.Counter)
    for label in [0,1]:
        for g in [0,1,2]:
            counts[('D',label,'ALL')][g]=10;counts[('D',label,'UDP')][g]=10
    counts[('D',0,'TCP')][0]=1
    chosen,report=preflight.solve(counts,[0,1,2]);assert 0 not in chosen and len(chosen)==1
    try:preflight.solve({('D',1,'ALL'):{0:10}},[0])
    except RuntimeError:pass
    else:raise AssertionError('SINGLE_GROUP_MUST_FAIL')
    results['source_split']=dict(feasible_protocol_coverage=True,singleton_kept_train=True,indivisible_class_fails_closed=True,uses_no_model_scores=True)
    result=dict(status='PASS',scope='LOCAL_CPU_REGRESSION_NOT_LINUX_RELEASE',checks=results,main_model_changed=False)
    (HERE/'LOCAL_REGRESSION.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
