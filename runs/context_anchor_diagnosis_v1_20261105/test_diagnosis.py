"""Regression checks for donor isolation, gradient sign/sums and immutability."""
import ast,json,sys
from pathlib import Path
import numpy as np
import torch
import analysis_core as ac

def main(output=None):
    here=Path(__file__).resolve().parent
    rows=[dict(uid=str(i),device='A' if i<4 else 'B',protocol=17 if i%2 else 6,label=i%2) for i in range(8)]
    mapping,s=ac.permutation(rows,20261105);assert s==0 and np.all(mapping!=np.arange(8))
    flipped=[dict(r,label=1-r['label']) for r in rows];assert np.array_equal(mapping,ac.permutation(flipped,20261105)[0])
    assert ac.permutation([rows[0]],20261105)[1]==1
    rel=ac.relation(np.array([1.,0]),np.array([-2.,0]));assert rel['cosine']==-1 and rel['anchor_descent_first_order_classification_change']==2
    assert ac.relation(np.zeros(2),np.ones(2))['cosine'] is None
    sys.path.insert(0,str(here.parent/'device_context_head_training_v2_20261105'))
    import context_core as k
    model=k.classifier(27,790);before=ac.fingerprint(model)
    x=torch.randn(8,790);nx=torch.randn(4,790);y=torch.tensor([0.,1.]*4);w=np.ones(8)/8
    v,loss,error=ac.gradients(model,x,y,w,8,nx,np.ones(8,dtype=np.float32)*3,100.,k.objective_components)
    assert v.shape==(5,sum(p.numel() for p in model.parameters())) and np.isfinite(v).all()
    assert ac.fingerprint(model)==before and all(p.grad is None for p in model.parameters())
    blocks=ac.block_indices(model);assert len(blocks['CONTEXT8'])==128*8
    # Fixed-neuron bias derivative: central finite difference checks anchor magnitude.
    grad=v[3,-1]+v[4,-1];eps=.005
    def anchor_value():
        z=model(x).flatten().detach().numpy().astype(np.float64)
        return float(np.mean(((z-3)/100)**2))
    with torch.no_grad():model[2].bias.add_(eps)
    plus=anchor_value()
    with torch.no_grad():model[2].bias.sub_(2*eps)
    minus=anchor_value()
    assert np.isclose(grad,(plus-minus)/(2*eps),rtol=.003,atol=1e-7)
    tree=ast.parse((here/'worker.py').read_text())
    forbidden={'step','backward','set_num_interop_threads','calibration','threshold'}
    assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in forbidden for n in ast.walk(tree))
    r=dict(status='PASS',checks=['device_protocol_donor_isolation','label_blind_derangement','singleton_retained','opposing_gradient_sign','zero_norm_uninterpretable','real_objective_gradient_sum','parameter_immutability','context_block_shape','finite_difference_anchor_gradient','no_optimizer_fit_or_interop_calls'],gradient_sum_error=error)
    path=Path(output) if output else here/'LOCAL_REGRESSION.json';path.write_text(json.dumps(r,indent=2)+'\n')
    print('DIAGNOSIS_REGRESSION_PASS')
if __name__=='__main__':main()
