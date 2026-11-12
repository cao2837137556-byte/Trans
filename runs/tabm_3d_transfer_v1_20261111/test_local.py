import ast,json,math,types
from pathlib import Path
import numpy as np
import transfer as t
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def main():
    source=ROOT/'runs/device_context_evaluation_v1_20261105/common.py';env={'np':np}
    for name in ['correction','four']:
        node=next(n for n in ast.parse(source.read_text()).body if isinstance(n,ast.FunctionDef) and n.name==name);exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec'),env)
    raw=env['four'](np.array([[.01,.02,.03],[.5,.8,.9],[.95,.96,.97]],dtype=np.float64));q=np.zeros((3,14));q[1,[0,2]]=1;s=np.array([.9,.5,0]);scales=np.array([.8,.7,.9]);cuts=np.array([.04,.05,.03,.04])
    corrected=env['four'](env['correction'](raw[:,:3],s,q,scales));expected=raw[:,:3]-.25*scales*(1-(1-s[:,None])**3);expected[1]=raw[1,:3]
    assert np.array_equal(corrected[:,:3],expected) and (corrected[0]<0).all()
    assert np.array_equal(corrected[1:],raw[1:]) and not np.any((corrected>cuts)&~(raw>cuts))
    assert np.array_equal(env['four'](env['correction'](raw[:,:3],s,q,np.zeros(3))),raw)
    core=ROOT/'runs/device_context_head_training_v2_20261105/constrained_onboarding_core_v3.py';node=next(n for n in ast.parse(core.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='weighted_quantile')
    def require(ok,msg):assert ok,msg
    e={'np':np,'math':math,'require':require};exec(compile(ast.Module(body=[node],type_ignores=[]),str(core),'exec'),e)
    quant=e['weighted_quantile'];assert quant([.1,.2,.9],[.05,.9,.05],.1)==.2 and quant([.1,.2,.9],[.05,.9,.05],.9)==.2
    assert quant([0.,.5,1.],[.2,.3,.5],.9)-quant([0.,.5,1.],[.2,.3,.5],.1)==1.
    w=t.load('tabm_constructor_test',ROOT/'runs/baseline_remaining_three_v2_20261108/worker.py');import torch
    torch.set_num_threads(1);m=w.model('TabM','cpu');m.eval();x=torch.randn(8,790)
    with torch.inference_mode():
        logits=m(x);expected=logits.softmax(-1)[...,1].mean(1).numpy();actual=w.score(m,'TabM',x)
    assert logits.shape==(8,32,2) and np.array_equal(expected,actual)
    t.equal({'a':[1.,None,True]},{'a':[1.,None,True]})
    try:t.equal({'a':1.},{'a':1.01})
    except AssertionError:pass
    else:raise AssertionError('RAW_METRIC_MISMATCH_ACCEPTED')
    for p in HERE.glob('*.py'):ast.parse(p.read_text())
    result=dict(status='PASS',native_tabm_32_member_mean_probability=True,own_scale_weighted_quantile_semantics=True,zero_scale_identity=True,negative_scores_preserved=True,guard_and_zero_support_exact=True,subtractive_subset=True,metric_mismatch_rejected=True,source_sha256={n:t.sha(HERE/n) for n in ['transfer.py','analysis_core.py']},scope='synthetic/local CPU, not a replacement for full RAW/GPU/source gates')
    (HERE/'LOCAL_VALIDATION.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
