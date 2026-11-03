"""Fixed final-epoch helpers and metric endpoints; all optimizer inputs are FIT."""
from pathlib import Path
import hashlib
import math
import numpy as np
import torch
import torch.nn.functional as F
import legacy_qref_common_v1 as c
from legacy_qref_data_v1 import weights
from legacy_qref_model_v1 import Metric
from legacy_reference_executor_model_v1 import Residual, probability


def q_forward(model,z,h,b,registered=None):
    # Q never uses reference values, only its original outer registration predicate.
    n=len(z)
    mask=torch.ones((n,1),dtype=torch.bool) if registered is None else registered[:,None]
    return model(z,h,b,torch.zeros((n,1,768)),mask)


def save_endpoint(out, model, receipt):
    out=Path(out)
    with (out/'head.npz').open('xb') as f:
        np.savez(f,**{k:v.detach().numpy() for k,v in model.state_dict().items()})
    with np.load(out/'head.npz',allow_pickle=False) as arrays:
        c.require(set(arrays.files)==set(model.state_dict()),'ENDPOINT_KEYS')
        for k,v in model.state_dict().items():
            c.require(np.array_equal(arrays[k],v.detach().numpy()),'ENDPOINT_READBACK')
    receipt['head_sha256']=c.sha(out/'head.npz')
    c.write(out/'endpoint.json',receipt); c.seal(out); c.verify(out)


def train(recipe, rows, z, h, b, bank, arm, seed, out, progress, hard=None, held_devices=(), synthetic=False):
    c.require(arm in ('HELPER','FULL','NO_CF') and seed in c.SEEDS,'TRAIN_SCOPE')
    c.require(z.shape==(len(rows),768) and h.shape==(len(rows),128) and b.shape==(len(rows),),'TRAIN_SHAPES')
    c.require(not set(r['device'] for r in rows)&set(held_devices),'HELPER_HELD_DEVICE_LEAK')
    if not synthetic:
        c.require(c.digest(recipe)==c.digest(c.load_recipe(Path(__file__).resolve().parents[2])),'RECIPE_DRIFT')
    else:
        c.require(recipe.get('synthetic_only') is True and len(rows)<=256 and recipe['training']['hyperparameters']['epochs']<=2,'SYNTHETIC_BOUND')
    c.require(all(r['partition']=='LEARN' for r in bank.rows),'TRAIN_REFERENCE_ROLE')
    c.require(all(r['device'] in bank.ends and bank.ends[r['device']]<r['timestamp'] for r in rows),'HELPER_REGISTRATION_CAUSALITY')
    w=weights(rows,None if arm=='HELPER' else hard)
    c.require(arm=='HELPER' or hard is not None,'H_REQUIRED')
    out=Path(out); out.mkdir(exist_ok=False)
    torch.set_num_threads(4); torch.use_deterministic_algorithms(True)
    torch.manual_seed(seed)
    model=Residual('Q') if arm=='HELPER' else Metric(seed)
    hp=recipe['training']['hyperparameters']
    optimizer=torch.optim.AdamW(model.parameters(),lr=hp['lr'],weight_decay=hp['weight_decay'],betas=tuple(hp['betas']),eps=hp['eps'],amsgrad=False,foreach=False)
    generator=torch.Generator(device='cpu').manual_seed(seed)
    n=len(rows); updates=0; order_hashes=[]; subset_hashes=[]
    for epoch in range(hp['epochs']):
        order=torch.randperm(n,generator=generator).numpy()
        order_hashes.append(hashlib.sha256(order.tobytes()).hexdigest())
        subset_hashes.append(c.digest({str(k):[bank.rows[i]['uid'] for i in bank.subset(k,recipe,seed,epoch)] for k in bank.keys}))
        epoch_loss=0.
        for start in range(0,n,hp['batch_size']):
            ix=order[start:start+hp['batch_size']]; rr=[rows[int(i)] for i in ix]
            zz=z[ix]; yy=torch.tensor([r['label'] for r in rr],dtype=torch.float32)
            optimizer.zero_grad(set_to_none=True)
            if arm=='HELPER':
                logits=q_forward(model,zz,h[ix],b[ix])
                loss_i=F.binary_cross_entropy_with_logits(logits,yy,reduction='none')
            else:
                own,valid=bank.own(zz,rr,model,recipe,minimum=1,seed=seed,epoch=epoch)
                c.require(bool(valid.all()),'TRAIN_OWN_REFERENCE_MISSING')
                attack=own
                if arm=='FULL':
                    mat,mask=bank.matrix(zz,rr,model,recipe,minimum=1,seed=seed,epoch=epoch)
                    c.require(bool(mask.any(1).all()),'TRAIN_ATTACK_CONTEXT_MISSING')
                    attack=mat.max(1).values
                loss_i=torch.where(yy==0,F.softplus(-10*own),F.softplus(10*attack))
            loss=(loss_i*torch.from_numpy(w[ix])).sum()*(n/len(ix))
            c.require(bool(torch.isfinite(loss)),'LOSS_NONFINITE')
            loss.backward()
            c.require(all(p.grad is not None and bool(torch.isfinite(p.grad).all()) for p in model.parameters()),'GRADIENT_NONFINITE')
            optimizer.step()
            c.require(all(bool(torch.isfinite(p).all()) for p in model.parameters()),'PARAMETER_NONFINITE')
            updates+=1; epoch_loss+=float(loss.detach())*len(ix)/n
            progress.tick(1,epoch=epoch+1,seed=seed,arm=arm)
        c.write(out/('epoch_%02d.json'%(epoch+1)),dict(epoch=epoch+1,loss=epoch_loss,updates=updates))
    c.require(updates==hp['epochs']*math.ceil(n/hp['batch_size']),'UPDATE_COUNT')
    receipt=dict(status='COMPLETE',arm=arm,seed=seed,recipe_digest=c.digest(recipe),updates=updates,
        epochs=hp['epochs'],rows=n,uid_sha256=c.uid_sha(r['uid'] for r in rows),
        weight_sha256=hashlib.sha256(w.tobytes()).hexdigest(),order_hashes=order_hashes,subset_hashes=subset_hashes,
        held_devices=list(held_devices),synthetic_only=synthetic)
    save_endpoint(out,model,receipt)
    return model.eval(),receipt


def helper_predictions(models, rows, z,h,b,theta,progress):
    c.require(len(models)==3 and all(r['label']==0 and r['partition']=='LEARN' and r['fit_role']=='FIT' for r in rows),'OOF_FIT_NORMAL_ONLY')
    values=[]
    with torch.inference_mode():
        for start in range(0,len(rows),256):
            end=start+256
            logits=np.stack([q_forward(m,z[start:end],h[start:end],b[start:end]).numpy() for m in models]).mean(0,dtype=np.float32)
            values.extend((probability(logits)>=theta).tolist()); progress.tick()
    return {r['uid'] for r,flag in zip(rows,values) if flag}
