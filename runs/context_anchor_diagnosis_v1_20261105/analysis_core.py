"""Fixed-input interventions and loss-gradient diagnostics; no parameter updates."""
import hashlib
import numpy as np
import torch

HEADS = ['27', '127', '227', 'ensemble']
TERMS = ['BCE_NORMAL','BCE_ATTACK','TAIL','ANCHOR_NORMAL','ANCHOR_ATTACK']

def quant(x):
    x=np.asarray(x,dtype=np.float64)
    assert np.isfinite(x).all()
    return dict(zip(['min','p01','p10','p50','p90','p99','max'],map(float,np.quantile(x,[0,.01,.1,.5,.9,.99,1])))) if x.size else None

def permutation(rows, seed):
    groups={};mapping=np.arange(len(rows));singletons=0
    for i,r in enumerate(rows):groups.setdefault((r['device'],r['protocol']),[]).append(i)
    for indices in groups.values():
        ix=sorted(indices,key=lambda i:hashlib.sha256((str(seed)+':'+rows[i]['uid']).encode()).digest())
        if len(ix)==1:singletons+=1
        mapping[ix]=np.roll(ix,1)
    assert np.array_equal(np.sort(mapping),np.arange(len(rows)))
    assert all((rows[i]['device'],rows[i]['protocol'])==(rows[j]['device'],rows[j]['protocol']) for i,j in enumerate(mapping))
    return mapping,singletons

def fingerprint(model):
    h=hashlib.sha256()
    for name,v in model.state_dict().items():h.update(name.encode());h.update(v.detach().cpu().numpy().tobytes())
    return h.hexdigest()

def direct(model,x):
    with torch.inference_mode():return model(torch.from_numpy(np.ascontiguousarray(x))).flatten().numpy().astype(np.float64)

def gradients(model,x,y,w,n,neg_x,teacher,scale,objective):
    """Same original weighted objective, split without class re-normalization."""
    parameters=tuple(model.parameters());logits=model(x).flatten();negative=model(neg_x).flatten()
    bce,tail,_=objective(logits,y,w,n,negative)
    weights=torch.as_tensor(w,dtype=torch.float64)
    rows_bce=torch.nn.functional.binary_cross_entropy_with_logits(logits,y,reduction='none')*weights*n/len(y)
    rows_anchor=weights*((logits-torch.as_tensor(teacher,dtype=logits.dtype))/scale).square()*n/len(y)
    losses=[rows_bce[y==0].sum(),rows_bce[y==1].sum(),tail,rows_anchor[y==0].sum(),rows_anchor[y==1].sum()]
    assert torch.allclose(losses[0]+losses[1],bce,rtol=1e-6,atol=1e-12)
    vectors=[]
    for loss in losses:
        g=torch.autograd.grad(loss,parameters,retain_graph=True,allow_unused=False)
        v=np.concatenate([a.detach().numpy().astype(np.float64).ravel() for a in g]);assert np.isfinite(v).all();vectors.append(v)
    total=torch.autograd.grad(bce+tail+rows_anchor.sum(),parameters)
    total=np.concatenate([v.detach().numpy().astype(np.float64).ravel() for v in total])
    assert np.allclose(np.sum(vectors,axis=0),total,rtol=5e-4,atol=1e-6),'GRADIENT_SUM_SANITY'
    return np.stack(vectors),np.asarray([float(v.detach()) for v in losses]),float(np.max(np.abs(np.sum(vectors,axis=0)-total)))

def block_indices(model):
    size=sum(p.numel() for p in model.parameters());first=model[0].weight.numel()
    columns=np.arange(first).reshape(model[0].weight.shape)
    return dict(ALL=np.arange(size),E3=columns[:,:768].ravel(),Q14=columns[:,768:782].ravel(),CONTEXT8=columns[:,782:].ravel(),OTHER=np.arange(first,size))

def relation(a,b):
    na=float(np.linalg.norm(a));nb=float(np.linalg.norm(b));dot=float(np.dot(a,b))
    valid=na>1e-12 and nb>1e-12
    return dict(classification_norm=na,anchor_norm=nb,dot=dot,cosine=dot/(na*nb) if valid else None,
                angle_interpretable=valid,near_zero_floor=1e-12,anchor_to_classification_norm=nb/na if na>1e-12 else None,
                anchor_descent_first_order_classification_change=-dot,
                anchor_opposes_classification=dot<0 if valid else None)

def gradient_summary(vectors,model):
    result={}
    for block,ix in block_indices(model).items():
        v=vectors[:,ix];base=v[0]+v[1]+v[2];anchor=v[3]+v[4]
        result[block]=dict(term_norms={name:float(np.linalg.norm(g)) for name,g in zip(TERMS,v)},
                          classification_vs_anchor=relation(base,anchor),
                          normal_bce_vs_normal_anchor=relation(v[0],v[3]),
                          attack_bce_vs_attack_anchor=relation(v[1],v[4]))
    return result
