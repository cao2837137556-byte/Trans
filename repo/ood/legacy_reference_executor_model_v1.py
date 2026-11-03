"""Frozen R and prospectively specified Q/M/C residual heads; no file I/O."""
from __future__ import annotations
import numpy as np
import torch
from torch import nn
from legacy_reference_executor_common_v1 import require,STATE_KEYS
import legacy_cic2022_enhancement_train_v1 as old
PARAMETERS={'Q':14385,'M':38961,'C':27201}
class FrozenR:
    def __init__(self,state):
        old._dimensions(state)
        self.state={k:state[k].copy() for k in STATE_KEYS}
        self.identity=old.state_digest(self.state)
        self.net=old.build_model(self.state).eval()
        self.net.requires_grad_(False)
    def inputs(self,features):
        x=torch.from_numpy(old.normalize_features(features,self.state))
        with torch.no_grad():
            h=self.net[1](self.net[0](x)); b=self.net(x).reshape(-1)
        return x[:,:-1],h,b
    def unchanged(self):
        require(old.state_digest(self.state)==self.identity,'R_STATE_MUTATED')
        for k,v in self.net.state_dict().items():
            require(np.array_equal(v.numpy(),self.state['p2__'+k]),'R_WEIGHTS_MUTATED')
class Residual(nn.Module):
    def __init__(self,arm):
        super().__init__(); require(arm in PARAMETERS,'ARM'); self.arm=arm
        if arm=='C':
            self.pair=nn.Linear(1536,16); self.hidden=nn.Linear(161,16)
        else: self.hidden=nn.Linear(897 if arm=='Q' else 2433,16)
        self.last=nn.Linear(16,1); nn.init.zeros_(self.last.weight); nn.init.zeros_(self.last.bias)
        require(sum(p.numel() for p in self.parameters())==PARAMETERS[arm],'PARAMETER_COUNT')
    def forward(self,z,h,b,refs,mask):
        require(z.shape[1]==768 and h.shape==(len(z),128) and b.shape==(len(z),),'R_INPUT_SHAPE')
        require(refs.ndim==3 and refs.shape[0]==len(z) and refs.shape[2]==768 and mask.shape==refs.shape[:2] and mask.dtype==torch.bool,'REFERENCE_SHAPE')
        active=mask.any(1); safe=torch.where(mask[:,:,None],refs,torch.zeros_like(refs))
        count=mask.sum(1,keepdim=True).clamp_min(1)
        if self.arm=='Q': v=torch.cat((z,h,b[:,None]),1)
        elif self.arm=='M':
            mean=safe.sum(1)/count
            delta=torch.where(mask[:,:,None],safe-mean[:,None,:],torch.zeros_like(safe))
            std=torch.sqrt(delta.square().sum(1)/count)
            v=torch.cat((z,mean,std,h,b[:,None]),1)
        else:
            d=z[:,None,:]-safe
            pair=torch.relu(self.pair(torch.cat((d,d.abs()),2)))
            mean=torch.where(mask[:,:,None],pair,torch.zeros_like(pair)).sum(1)/count
            maximum=pair.masked_fill(~mask[:,:,None],-torch.inf).max(1).values
            maximum=torch.where(active[:,None],maximum,torch.zeros_like(maximum))
            v=torch.cat((h,b[:,None],mean,maximum),1)
        delta=self.last(torch.relu(self.hidden(v))).reshape(-1)
        result=torch.where(active,b+delta,b)
        require(bool(torch.isfinite(result).all()),'NONFINITE_LOGITS')
        return result
class ReferenceBank:
    def __init__(self,metadata,features,baseline):
        require(len(metadata)==len(features),'REFERENCE_LENGTH')
        self.rows=metadata; self.by_device={}; self.by_uid={}
        z=baseline.inputs(np.asarray(features,dtype=np.float32))[0]
        for i,r in enumerate(metadata):
            require(r['label']==0 and r['use']=='REFERENCE','REFERENCE_NORMAL_ONLY')
            self.by_device.setdefault(r['device'],[]).append(i); self.by_uid[r['uid']]=i
        self.z=z
    def batch(self,metadata,uid_override=None,budget=None):
        groups=[]
        for row in metadata:
            indices=self.by_device.get(row['device'],[]) if uid_override is None else [self.by_uid[u] for u in uid_override]
            if budget is not None: indices=indices[:budget]
            if uid_override is None:
                for i in indices:
                    ref=self.rows[i]
                    require(ref['partition']==row['partition'] and ref['timestamp']<row['timestamp'],'REFERENCE_ROLE_OR_TIME')
            groups.append(indices)
        width=max(1,max(map(len,groups),default=0))
        refs=torch.zeros((len(groups),width,768),dtype=torch.float32); mask=torch.zeros((len(groups),width),dtype=torch.bool)
        for i,indices in enumerate(groups):
            if indices: refs[i,:len(indices)]=self.z[indices]; mask[i,:len(indices)]=True
        return refs,mask
def probability(logits):
    return torch.from_numpy(np.asarray(logits,dtype=np.float32)).sigmoid().numpy().astype(np.float64)

