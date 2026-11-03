"""One fixed endpoint; optimizer is structurally confined to LEARN rows."""
from __future__ import annotations
import hashlib, math
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
import legacy_reference_executor_common_v1 as c
from legacy_reference_executor_model_v1 import FrozenR,Residual,ReferenceBank
def validate_training(rows):
    c.require(rows and all(r['partition']=='LEARN' and r['use']!='REFERENCE' for r in rows),'OPTIMIZER_LEARN_ONLY')
    c.require(len({r['uid'] for r in rows})==len(rows),'TRAIN_UID_DUPLICATE')
    from legacy_reference_sample_finalize_v1 import weight_rows
    expected=[dict(r) for r in rows]; weight_rows(expected)
    for a,b in zip(rows,expected):
        c.require(a['balanced_bce_weight_denominator']==b['balanced_bce_weight_denominator'],'WEIGHT_HIERARCHY_DRIFT')
    return np.array([1/r['balanced_bce_weight_denominator'] for r in rows],dtype=np.float64)
def loss_value(logits,labels,weights,n):
    c.require(len(logits)>0,'EMPTY_BATCH')
    return (F.binary_cross_entropy_with_logits(logits,labels,reduction='none')*weights).sum()*(n/len(logits))
def train_endpoint(recipe,state,features,metadata,ref_features,ref_rows,arm,seed,out,synthetic=False):
    out=Path(out); out.mkdir(exist_ok=False)
    weights=validate_training(metadata); n=len(metadata); opt=recipe['optimization']
    c.require(seed in opt['seeds'] and arm in opt['arms'],'ENDPOINT_SCOPE')
    c.require(n==opt['rows'] and len(features)==n,'TRAIN_COUNT')
    if synthetic: c.require(n<=128 and opt['epochs']<=2 and recipe.get('synthetic_only') is True,'SYNTHETIC_BUDGET')
    else: c.require(recipe==c.recipe(),'FROZEN_RECIPE_DRIFT')
    torch.set_num_threads(4); torch.use_deterministic_algorithms(True)
    base=FrozenR(state); bank=ReferenceBank(ref_rows,ref_features,base)
    c.require(all(r['partition']=='LEARN' for r in ref_rows),'LEARN_REFERENCE_ONLY')
    torch.manual_seed(seed); model=Residual(arm)
    optimizer=torch.optim.AdamW(model.parameters(),lr=opt['lr'],weight_decay=opt['weight_decay'],betas=tuple(opt['betas']),eps=opt['eps'],amsgrad=opt['amsgrad'],foreach=False)
    generator=torch.Generator(device='cpu').manual_seed(seed); exposure=hashlib.sha256(); epoch_hashes=[]; updates=0
    expected_updates=opt['epochs']*math.ceil(n/opt['batch_size'])
    for epoch in range(opt['epochs']):
        order=torch.randperm(n,generator=generator).numpy(); eh=hashlib.sha256(order.tobytes()).hexdigest(); epoch_hashes.append(eh)
        exposure.update(order.tobytes()); epoch_loss=0.
        for start in range(0,n,opt['batch_size']):
            ix=order[start:start+opt['batch_size']]; rows=[metadata[int(i)] for i in ix]
            z,h,b=base.inputs(np.array(features[ix],dtype=np.float32)); refs,mask=bank.batch(rows)
            model.train(); optimizer.zero_grad(set_to_none=True)
            logits=model(z,h,b,refs,mask)
            labels=torch.tensor([r['label'] for r in rows],dtype=torch.float32)
            loss=loss_value(logits,labels,torch.from_numpy(weights[ix]),n)
            c.require(bool(torch.isfinite(loss)),'LOSS_NONFINITE'); loss.backward()
            c.require(all(p.grad is not None and bool(torch.isfinite(p.grad).all()) for p in model.parameters()),'GRAD_NONFINITE')
            optimizer.step(); updates+=1; epoch_loss+=float(loss.detach())*len(ix)/n
            c.require(all(bool(torch.isfinite(p).all()) for p in model.parameters()),'PARAMETER_NONFINITE')
            if updates==1 or updates%100==0: c.emit(out,'TRAIN_'+arm,updates,expected_updates,epoch=epoch+1,seed=seed,status='RUNNING')
        with (out/'epochs.jsonl').open('a',encoding='utf8') as f:
            import json
            f.write(json.dumps(dict(epoch=epoch+1,loss=epoch_loss,order_sha256=eh,updates=updates))+'\n')
    base.unchanged(); c.require(updates==expected_updates==opt['updates_per_model'],'UPDATE_COUNT')
    path=out/'head.npz'
    with path.open('xb') as f: np.savez(f,**{k:v.detach().numpy() for k,v in model.state_dict().items()})
    with np.load(path,allow_pickle=False) as saved:
        c.require(set(saved.files)==set(model.state_dict()),'HEAD_SAVE_SCHEMA')
        for k,v in model.state_dict().items(): c.require(np.array_equal(saved[k],v.detach().numpy()),'HEAD_SAVE_READBACK')
    receipt=dict(status='COMPLETE',arm=arm,seed=seed,recipe_digest=c.digest(recipe),head_sha256=c.sha(path),R_identity=base.identity,
        updates=updates,epochs=opt['epochs'],row_exposures=n*opt['epochs'],permutation_sha256=exposure.hexdigest(),epoch_order_sha256=epoch_hashes,
        uid_sha256=c.uid_sha(r['uid'] for r in metadata),weight_sha256=hashlib.sha256(weights.tobytes()).hexdigest(),synthetic_only=synthetic)
    c.atomic_json(out/'endpoint.json',receipt); c.emit(out,'ENDPOINT_COMPLETE',updates,updates,status='COMPLETE'); c.seal(out)
    return receipt
def load_head(path,arm):
    model=Residual(arm)
    with np.load(path,allow_pickle=False) as values:
        model.load_state_dict({k:torch.from_numpy(values[k].copy()) for k in values.files},strict=True)
    model.eval(); return model

