"""Verify finite-step guards and rejected Adam/RNG trajectories, not just scores."""
import copy,importlib.util,json
from pathlib import Path
import numpy as np
import torch
import guard_core as g

def main(path=None):
    tests=[];torch.manual_seed(27)
    model=torch.nn.Linear(2,1);opt=torch.optim.AdamW(model.parameters(),lr=.01,weight_decay=0,foreach=False)
    x=torch.tensor([[1.,2.],[3.,1.]])
    def train():
        opt.zero_grad(set_to_none=True);loss=model(x).square().mean();loss.backward();opt.step();torch.rand(1)
        return dict(updates=1,loss=float(loss.detach()))
    train();saved=g.snapshot(model,opt);before=g.state_hash(saved)
    previous=dict(checks={'safe':True},normal_tail_risk=1.)
    reject=lambda:dict(checks={'safe':False},normal_tail_risk=.5)
    out=g.guarded_block(model,opt,train,reject,previous,.01)
    assert not out['accepted'] and len(out['attempts'])==4 and g.state_hash(g.snapshot(model,opt))==before
    tests.append('all_rejected_restores_parameters_adam_moments_steps_and_rng')
    i=[0]
    def second():i[0]+=1;return dict(checks={'safe':i[0]==2},normal_tail_risk=.5)
    out=g.guarded_block(model,opt,train,second,previous,.01);got=g.state_hash(g.snapshot(model,opt))
    assert out['factor']==.5 and len(out['attempts'])==2
    g.restore(model,opt,saved)
    for group in opt.param_groups:group['lr']=.005
    train();assert g.state_hash(g.snapshot(model,opt))==got
    tests.append('backtrack_replays_from_same_state_matches_direct_smaller_lr')
    before=g.state_hash(g.snapshot(model,opt))
    out=g.guarded_block(model,opt,train,lambda:dict(checks={'safe':True},normal_tail_risk=1.1),previous,.01)
    assert not out['accepted'] and before==g.state_hash(g.snapshot(model,opt))
    tests.append('normal_risk_increase_rejected_even_if_attack_safe')
    # Compact guard must match the existing scientific metric and criteria implementation.
    spec=importlib.util.spec_from_file_location('guard_metric_test',Path(__file__).with_name('worker.py'));w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
    rows=[dict(label=i//4,device='d',activity='a',capture_id='c',session_id=str(i%2),protocol=6+i%2) for i in range(8)]
    base=np.array([2.,1.,0.,-1.,3.,4.,5.,6.],np.float32);zero=np.zeros(8,np.float32);selected=np.array([0,4])
    guard=g.SourceGuard(rows,selected,base,zero,0.,1.,0.,w.k.class_weights,w.criteria)
    for s,z in [(base.copy(),zero),(base-np.float32(.02),zero),(base-10,zero),(base,base+10)]:
        evidence=guard.evaluate(s,z)
        for role,ix in [('fit',np.arange(8)),('fit_not_sampled_for_gradient',np.array([1,2,3,5,6,7]))]:
            metric=w.measures([rows[i] for i in ix],base[ix],s[ix],zero[ix],z[ix],0.,1.,0.)
            expected=w.criteria(metric)
            assert expected=={k.split('/',1)[1]:v for k,v in evidence['checks'].items() if k.startswith(role+'/')}
            assert np.isclose(metric['normal']['candidate_tail_risk'],evidence['metrics'][role]['normal']['tail_risk'],atol=1e-12)
    tests.append('full_and_non_gradient_FIT_guard_matches_frozen_metrics_and_gates')
    assert not guard.evaluate(base-.02,zero)['checks']['fit/attack_p01_margin_drop_within_slack']
    assert not guard.evaluate(base,base+10)['checks']['fit/positive_context_retention']
    tests+=['attack_quantile_failure_rejected','context_collapse_rejected']
    # Exercise the actual round driver and its runtime rollback accounting.
    import tempfile,types
    import guarded_training as gt
    with tempfile.TemporaryDirectory() as td:
        mm=torch.nn.Linear(2,1);oo=torch.optim.AdamW(mm.parameters(),lr=1e-5,weight_decay=0,foreach=False)
        xx=torch.ones(16384,2);zz=torch.zeros_like(xx);yy=np.repeat([0,1],8192);ww=np.full(16384,1/8192)
        with torch.no_grad():tt=mm(xx).flatten();tz=mm(zz).flatten()
        class DummyProgress:
            def tick(self,*args):pass
        class FixedGuard:
            base=np.zeros(4);zero_base=np.zeros(4)
            def evaluate(self,*args):return dict(checks={'test':True},normal_tail_risk=2.)
        cc=types.SimpleNamespace(save_arrays=lambda path,**values:np.savez(path,**values),write=lambda path,value,replace:Path(path).write_text(json.dumps(value)))
        result=gt.run(mm,oo,xx,zz,tt,tz,yy,ww,-10.,1.,27,True,dict(learning_rate=1e-5,guard=dict(lr_factors=[1.,.5,.25,.125])),Path(td),DummyProgress(),cc,FixedGuard(),lambda:dict(checks={'test':True},normal_tail_risk=1.))
        assert result['nominal_updates']==result['retained_optimizer_updates']==8 and result['executed_updates']==12
        assert result['rollback_smoke']['complete_state_restored'] and result['accepted_rounds']==1
        assert all(int(v['step'])==8 for v in oo.state.values())
    tests.append('real_round_driver_proposal_retention_and_forced_rollback_accounting')
    result=dict(status='PASS',tests=tests)
    Path(path or Path(__file__).with_name('GUARD_REGRESSION.json')).write_bytes((json.dumps(result,indent=2)+'\n').encode());print(json.dumps(result))
if __name__=='__main__':main()
