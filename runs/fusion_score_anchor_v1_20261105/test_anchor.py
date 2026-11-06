"""Test zero-penalty parity, objective weighting, trajectories, and teacher immutability."""
import json,sys,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent;PARENT=HERE.parent/'device_context_head_training_v2_20261105'
sys.path.append(str(PARENT))
import numpy as np
import torch
import context_core as k
import context_train as old
import anchor_train as new
class Progress:
    stage='';optimizer_updates=0
    def tick(self,*args):pass
def main():
    torch.set_num_threads(1);rng=np.random.default_rng(91);n=192
    values=(rng.normal(size=(n,794)).astype('f4'),rng.normal(size=(n,8)).astype('f4'))
    q=rng.uniform(size=(n,14)).astype('f4');ix=np.arange(n);st=np.zeros(n,np.uint8)
    rows=[dict(uid=f'{i:064x}',partition='LEARN',fit_role='FIT',use='QUERY',label=i%2,device='d'+str(i%3),activity='a',capture_id='c'+str(i%5),session_id='s'+str(i//4),component_id='k'+str(i//4)) for i in ix]
    spec=json.loads((PARENT/'TRAINING_SPEC_FROZEN.json').read_text())
    design=dict(synthetic_only=True,training=dict(spec['training']['parent_recipe']));design['training'].update(epochs=2,batch_size=64)
    norm=np.zeros(768),np.ones(768);teacher=rng.normal(size=n).astype('f4');original=teacher.copy()
    (HERE/'.private').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=HERE/'.private') as tmp:
        tmp=Path(tmp)
        a=old.train(design,rows,values,q,norm,ix,st,'FUSION790',27,tmp/'parent',Progress(),synthetic=True)
        b=new.train(design,rows,values,q,norm,ix,st,'FUSION790',27,tmp/'zero',Progress(),synthetic=True,teacher_scores=teacher,teacher_scale=3,anchor_lambda=0.)
        assert all(torch.equal(a.state_dict()[key],b.state_dict()[key]) for key in a.state_dict()),'ZERO_LAMBDA_PARITY'
        assert np.array_equal(np.load(tmp/'parent/batch_losses.npy'),np.load(tmp/'zero/batch_losses.npy'))
        trained=new.train(design,rows,values,q,norm,ix,st,'FUSION790',27,tmp/'one',Progress(),synthetic=True,teacher_scores=teacher,teacher_scale=3)
        assert any(not torch.equal(a.state_dict()[key],trained.state_dict()[key]) for key in a.state_dict())
        components=np.load(tmp/'one/objective_components.npy');assert np.allclose(components[:,:3].sum(1),components[:,3],rtol=1e-13,atol=1e-14)
        assert np.array_equal(teacher,original)
        for e in [1,2]:
            f=tmp/'one'/f'epoch_{e:02d}_head.npz';assert f.exists()
            assert np.isfinite(np.load(tmp/'one'/f'epoch_{e:02d}_source_probe.npz')['scores']).all()
        for line in (tmp/'one/fixed_probes.jsonl').read_text().splitlines():assert json.loads(line)['gradient']['backward_sanity']['l2_pass']
    # Weighted minibatch estimator has the prescribed full-FIT reduction in expectation.
    v=torch.tensor([2.,4.,6.,8.],requires_grad=True);target=torch.tensor([1.,3.,5.,7.]);w=torch.tensor([.1,.2,.3,.4],dtype=torch.float64)
    loss=(w*((v-target)/2).square()).sum();loss.backward()
    assert torch.allclose(v.grad,w.float()/2)
    r=dict(status='PASS',zero_lambda_parameters_and_losses_bit_exact=True,anchor_changes_updates=True,combined_gradient_sanity=True,component_sum=True,epoch_heads_and_source_probe_saved=True,teacher_immutable=True,weighted_objective_gradient=True,scope='SYNTHETIC_LOCAL_NOT_REAL_HPC')
    (HERE/'LOCAL_REGRESSION.json').write_bytes((json.dumps(r,indent=2)+'\n').encode());print(json.dumps(r))
if __name__=='__main__':main()
