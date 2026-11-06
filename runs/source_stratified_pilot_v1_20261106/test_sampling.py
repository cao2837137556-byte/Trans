"""Estimator direction and coverage checks; fixed scores are never sampling inputs."""
import json
from pathlib import Path
import numpy as np
import torch
import sampling_core as s
import risk_core as r

def main(path=None):
    rows=[dict(label=y,device='d',activity=str(g),protocol=6) for y in (0,1) for g in (0,1) for j in (0,1)]
    weights=np.array([.1,.2,.05,.15,.2,.05,.15,.1]);labels=np.array([x['label'] for x in rows])
    ix,w,info=s.draw(rows,weights,each=8)
    ix2,w2,_=s.draw(rows,weights,each=8)
    assert np.array_equal(ix,ix2) and np.array_equal(w,w2)
    assert len(ix)==16 and info['unique_rows']<16 and all(x['draws']>=1 for x in info['strata'])
    tests=['deterministic_with_replacement_fixed_draw_budget','every_semantic_stratum_present']
    # Analytically sum all possible outcomes of each independent draw; verify
    # both a nonlinear loss and its parameter derivative, not just weight sums.
    x=torch.arange(1,9,dtype=torch.float64);theta=torch.tensor(.7,dtype=torch.float64,requires_grad=True)
    value=(theta*x-1).square();exact=sum((value[labels==y]*torch.tensor(weights[labels==y]/weights[labels==y].sum())).sum() for y in (0,1))
    expected=theta*0
    for group in info['strata']:
        members=np.array([i for i,v in enumerate(rows) if v['label']==group['label'] and [str(v[f]) for f in s.FIELDS]==group['key']])
        prob=weights[members]/weights[members].sum()
        expected+=group['draws']*group['per_draw_weight']*(value[members]*torch.tensor(prob)).sum()
    assert torch.allclose(exact,expected,atol=1e-12)
    assert torch.allclose(torch.autograd.grad(exact,theta,retain_graph=True)[0],torch.autograd.grad(expected,theta)[0],atol=1e-12)
    tests+=['exact_expected_nonlinear_loss_matches_full_source','exact_expected_parameter_gradient_matches_full_source']
    # Wrong old-row reweighting after PPS sampling must disagree with target.
    p=weights[:2]/weights[:2].sum();assert not np.allclose(p,p*p/(p*p).sum())
    tests.append('double_weighting_negative_control')
    score=torch.arange(16,dtype=torch.float64)/10;zero=torch.zeros(16);teacher=score+.1;teacherzero=zero
    y=torch.from_numpy(labels[ix]);full=r.components(score,zero,teacher,teacherzero,y,w,0.,1.,8)
    batches=[np.array([j,j+1,j+8,j+9]) for j in range(0,8,2)]
    parts=[r.components(score[b],zero[b],teacher[b],teacherzero[b],y[b],w[b],0.,1.,8) for b in batches]
    for j in range(3):assert torch.allclose(full[j],sum(t[j] for t in parts)/4,atol=1e-12)
    tests.append('balanced_minibatch_mean_equals_fixed_draw_objective')
    changed=[dict(v,unused_score=10000*i,unused_CAL_label=1) for i,v in enumerate(rows)]
    ix3,w3,_=s.draw(changed,weights,each=8);assert np.array_equal(ix,ix3) and np.array_equal(w,w3)
    tests.append('unrelated_score_fields_do_not_affect_selection')
    try:s.draw(rows,weights,each=1)
    except AssertionError:pass
    else:raise AssertionError('quota overflow not rejected')
    tests.append('insufficient_quota_budget_rejected')
    result=dict(status='PASS',tests=tests)
    Path(path or Path(__file__).with_name('SAMPLING_REGRESSION.json')).write_bytes((json.dumps(result,indent=2)+'\n').encode());print(json.dumps(result))
if __name__=='__main__':main()
