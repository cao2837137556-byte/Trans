"""Regression gates for scientific direction, class weighting and frozen teachers."""
import json
from pathlib import Path
import numpy as np
import torch
import risk_core as r


def main(path=None):
    tests=[]
    labels=np.array([0,0,1,1]); w=r.batch_weights(np.array([1.,3.,2.,2.]),labels)
    assert np.allclose(w,[.25,.75,.5,.5]); tests.append('original_weight_ratios_per_class')
    s=torch.tensor([2.,0.,3.,3.],requires_grad=True); z=torch.tensor([1.,0.,1.,1.],requires_grad=True)
    t=torch.tensor([2.,0.,4.,3.]); tz=torch.tensor([1.,0.,1.,4.]); y=torch.from_numpy(labels)
    n,a,c=r.components(s,z,t,tz,y,w,1.,1.,2)
    gn=torch.autograd.grad(n,s,retain_graph=True)[0]
    ga=torch.autograd.grad(a,s,retain_graph=True)[0]
    gc=torch.autograd.grad(c,(s,z),retain_graph=True)
    assert gn[0]>0 and gn[1]==0 and torch.equal(gn[2:],torch.zeros(2))
    assert ga[2]<0 and ga[3]==0 and torch.equal(ga[:2],torch.zeros(2))
    assert gc[0][2]<0 and gc[1][2]>0 and gc[0][3]==0
    tests+=['normal_descent_lowers_high_scores','attack_descent_restores_dropped_scores','positive_context_lift_preserved_only']
    s2=torch.tensor([0.,0.,5.,5.],requires_grad=True)
    _,a2,c2=r.components(s2,torch.zeros(4),t,tz,y,w,1.,1.,2)
    assert float(a2.detach())==0 and float(c2.detach())==0; tests.append('no_two_sided_teacher_imitation')
    # Exact weighted full-pilot objective equals average equal-size balanced batches.
    full=r.components(s,z,t,tz,y,w,1.,1.,2)
    halves=[r.components(s[ix],z[ix],t[ix],tz[ix],y[ix],w[ix],1.,1.,2) for ix in ([0,2],[1,3])]
    for j in range(3):assert torch.allclose(full[j],sum(v[j] for v in halves)/2)
    tests.append('batch_expectation_matches_full_pilot')
    chosen=r.sample(np.repeat([0,1],100),each=16)
    assert len(set(chosen))==32 and np.array_equal(chosen,r.sample(np.repeat([0,1],100),each=16))
    tests.append('deterministic_disjoint_class_sample')
    # Finite-difference check protects hinge scaling and signs.
    eps=1e-3
    for j in (0,2):
        ss=s.detach().clone(); ss[j]+=eps
        plus=sum(r.components(ss,z.detach(),t,tz,y,w,1.,1.,2))
        ss[j]-=2*eps; minus=sum(r.components(ss,z.detach(),t,tz,y,w,1.,1.,2))
        analytic=torch.autograd.grad(n+a+c,s,retain_graph=True)[0][j]
        assert abs(float((plus-minus)/(2*eps)-analytic))<.001
    tests.append('finite_difference_gradient')
    # Execute an actual 790-column optimization and ensure only the candidate changes.
    torch.manual_seed(27)
    model=torch.nn.Sequential(torch.nn.Linear(790,128),torch.nn.ReLU(),torch.nn.Linear(128,1))
    teacher_model=__import__('copy').deepcopy(model).eval().requires_grad_(False)
    before=r.fingerprint(teacher_model); x=torch.randn(16,790); zx=x.clone();zx[:,782:]=0
    y=torch.tensor([0]*8+[1]*8); ww=r.batch_weights(np.ones(16),y.numpy())
    with torch.no_grad():tt=teacher_model(x).flatten();tz2=teacher_model(zx).flatten()
    opt=torch.optim.AdamW(model.parameters(),lr=1e-5,weight_decay=0,foreach=False)
    terms=r.components(model(x).flatten(),model(zx).flatten(),tt,tz2,y,ww,-2.,1.,8)
    loss=terms[0]+10*(terms[1]+terms[2]);loss.backward()
    assert model[0].weight.grad[:,782:].abs().sum()>0
    opt.step(); assert r.fingerprint(model)!=before and r.fingerprint(teacher_model)==before
    tests.append('real_790_optimizer_update_teacher_frozen_context_gradient')
    import worker
    rows=[dict(label=i//2,device='d',activity='a',capture_id='c',session_id='s',protocol=17) for i in range(4)]
    base=np.array([1.,-1.,2.,3.]); cand=np.array([-1.,-2.,2.,3.]); zero=np.zeros(4)
    metric=worker.measures(rows,base,cand,zero,zero,0.,1.,0.)
    assert metric['normal']['baseline_rate']==.5 and metric['normal']['candidate_rate']==0
    assert metric['attack']['removed']==0 and all(worker.criteria(metric).values())
    bad=cand.copy();bad[2]=-1
    assert not worker.criteria(worker.measures(rows,base,bad,zero,zero,0.,1.,0.))['attack_removed_fraction_within_0_1pp']
    tests.append('metric_receipt_counts_and_preservation_failure_gate')
    result=dict(status='PASS',tests=tests)
    Path(path or Path(__file__).with_name('LOCAL_REGRESSION.json')).write_text(json.dumps(result,indent=2))
    print(json.dumps(result))


if __name__=='__main__':main()
