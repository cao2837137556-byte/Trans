import ast,hashlib,json,sys,tempfile,types
from pathlib import Path
import numpy as np
import torch
from pipeline_parent import HERE,PROJECT,read,write,sha
from adapters import fidelity_checks,tabr,ExactTorchIndex
from readiness import dte_module

def main():
    torch.set_num_threads(1);torch.manual_seed(27);np.random.seed(27)
    result=fidelity_checks(False)
    m=dte_module();x=torch.randn(32,790);model=m.DTECategorical(epochs=1,device='cpu');model.model=m.MLP([790]+model.hidden_size,num_bins=7)
    t=torch.arange(32)*12;state=torch.get_rng_state();a=model.compute_loss(x,t)
    torch.set_rng_state(state);eps=torch.randn_like(x);alpha=torch.cumprod(1-torch.linspace(.0001,.01,400),0);b=torch.nn.functional.cross_entropy(model.model(x+torch.sqrt(1-alpha[t])[:,None]*eps),torch.clamp(torch.floor(t*7/400),0,6).long());assert torch.equal(a,b)
    before={n:v.clone() for n,v in model.model.state_dict().items()};model.fit(x.numpy());assert any(not torch.equal(before[n],v) for n,v in model.model.state_dict().items())
    model.model.eval();score=model.predict_score(x.numpy());assert np.isfinite(score).all()
    with torch.inference_mode():manual=(model.model(x).numpy()*np.arange(7)).sum(1)
    assert np.allclose(score,manual,atol=1e-6)
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)/'state.npz';np.savez(p,**{n:v.detach().numpy() for n,v in model.model.state_dict().items()})
        with np.load(p) as v:model.model.load_state_dict({n:torch.from_numpy(v[n].copy()) for n in v.files})
        assert np.array_equal(score,model.predict_score(x.numpy()))
    result['DTE']=dict(status='PASS',loss_exact=True,score_parity=True,weight_update=True,reload_exact=True)
    oracle=types.SimpleNamespace(IndexFlatL2=ExactTorchIndex);a,_=tabr(oracle);b,_=tabr(oracle);b.load_state_dict(a.state_dict());a.eval();b.eval();b.memory_efficient=True;b.candidate_encoding_batch_size=17
    q=x[:8];pool=x[8:];yy=torch.arange(len(pool))%2;args=dict(x_={'num':q},y=None,candidate_x_={'num':pool},candidate_y=yy,context_size=8,is_train=False)
    with torch.inference_mode():error=float((a(**args)-b(**args)).abs().max())
    assert error<2e-5
    b.train();v=b(x_={'num':q},y=torch.arange(8)%2,candidate_x_={'num':pool},candidate_y=yy,context_size=8,is_train=True);v.sum().backward();assert all(p.grad is None or torch.isfinite(p.grad).all() for p in b.parameters())
    result['TabR_native_memory_path']=dict(status='PASS',eval_error=error,backward_finite=True,native_faiss_linux_pending=True)
    pins=read(HERE/'DTE_PROVENANCE.json')['sha256']
    for n,h in pins.items():assert sha(HERE/'vendor/dte'/n)==h
    for p in HERE.glob('*.py'):ast.parse(p.read_text(encoding='utf8'))
    spec=read(HERE/'SPEC.json');assert len(spec['phases'])==14 and set(spec['phase_caps_seconds'])==set(spec['phases'])
    assert spec['phases'][:3]==['ENVIRONMENT','FIDELITY','PIPELINE']
    assert "sys.path.insert(0,str(HERE/'runtime/wheels'))" in (HERE/'readiness.py').read_text()
    protocol=read(HERE/'TRAINING_PROTOCOL.json');assert not protocol['author_benchmark_replication_required'] and not protocol['main_model_changed'];assert protocol['thresholds']['target_threshold_fit'] is False
    report=dict(status='PASS',checks=result,source_files_pinned=len(pins),runtime='local Windows torch; CatBoost Linux and full-source checks pending',main_freeze_sha256=sha(PROJECT/'runs/paper_results_freeze_v1_20261107/METHOD_FREEZE.json'))
    write('LOCAL_REGRESSION.json',report);print(json.dumps(report,indent=2))
if __name__=='__main__':main()
