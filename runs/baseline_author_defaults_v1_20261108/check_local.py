import ast,hashlib,json,os,subprocess,sys,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import numpy as np,torch
import formal as f
torch.set_num_threads(1)

def resume(method,path):
    torch.manual_seed(27);np.random.seed(27);f.random.seed(27)
    x=np.random.RandomState(1).normal(size=(512,790)).astype('float32')
    m,s,loader,opt=f.construct(method,27,x)
    m,s,opt,_=f.load_state(method,m,s,opt,path/'resume.pt')
    f.one_epoch(method,m,loader,opt,'CHILD');f.save(path/'actual.pt',f.network(method,m).state_dict())

def main():
    if len(sys.argv)>1:return resume(sys.argv[1],Path(sys.argv[2]))
    checks=[]
    for p in HERE.glob('*.py'):ast.parse(p.read_text());checks.append('syntax:'+p.name)
    for method in ['DTE-C','SLAD']:
        torch.manual_seed(27);np.random.seed(27);f.random.seed(27)
        x=np.random.RandomState(1).normal(size=(512,790)).astype('float32')
        m,s,loader,opt=f.construct(method,27,x)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);f.one_epoch(method,m,loader,opt,'WARMUP');f.save(p/'resume.pt',f.snapshot(method,m,s,opt,1))
            f.one_epoch(method,m,loader,opt,'EXPECTED');expected={k:v.clone() for k,v in f.network(method,m).state_dict().items()}
            subprocess.run([sys.executable,'-X','utf8','-B',__file__,method,str(p)],check=True,timeout=120)
            actual=torch.load(p/'actual.pt',weights_only=True);assert all(torch.equal(v,actual[k]) for k,v in expected.items());checks.append('fresh_process_epoch_exact:'+method)
            assert (p/'resume.pt').stat().st_size<20*1024**2,'SLAD_MUST_NOT_SERIALIZE_TRANSFORMED_DATA';checks.append('bounded_checkpoint:'+method)
    cfg=f.read(HERE/'CONFIG.json');assert cfg['hyperparameter_search'] is False and cfg['seeds']==[27,127,227]
    assert set(cfg['released_candidates'])=={'DTE-C','SLAD','CatBoost'};checks.append('fixed_scope')
    f.write('LOCAL_REGRESSION.json',dict(status='PASS',checks=checks,linux_real_gate_pending=True));print('PASS',len(checks))
if __name__=='__main__':main()
