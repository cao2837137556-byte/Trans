"""Pointwise shared metric and causal, protocol-matched reference scoring."""
import hashlib
import numpy as np
import torch
from torch import nn
import legacy_qref_common_v1 as c
from legacy_qref_data_v1 import metadata_valid


def unit(x):
    c.require(x.dtype==torch.float32 and x.ndim==2 and bool(torch.isfinite(x).all()),'VECTOR_DTYPE_SHAPE_FINITE')
    n = torch.linalg.vector_norm(x,dim=1,keepdim=True)
    c.require(bool(torch.isfinite(n).all()) and bool((n>1e-12).all()),'VECTOR_NORM')
    return x/n


class Metric(nn.Module):
    def __init__(self, seed):
        super().__init__()
        c.require(seed in c.SEEDS,'SEED')
        torch.manual_seed(seed)
        self.W = nn.Parameter(torch.empty(64,768,dtype=torch.float32))
        nn.init.orthogonal_(self.W,gain=1)

    def forward(self,z):
        return unit(unit(z) @ self.W.T)


class Raw(nn.Module):
    def forward(self,z):
        return unit(z)


def top_score(query, reference):
    c.require(reference.shape[0]>=1,'EMPTY_REFERENCE')
    cosine = query @ reference.T
    c.require(bool(torch.isfinite(cosine).all()) and bool((cosine.abs()<=1+1e-5).all()),'COSINE_RANGE')
    cosine = cosine.clamp(-1,1)
    # Bank inputs are UID sorted; stable sort enforces the frozen tie rule.
    ix = torch.argsort(cosine,dim=1,descending=True,stable=True)[:,:min(2,len(reference))]
    return cosine.gather(1,ix).mean(1)


class Bank:
    def __init__(self, rows, z, allowed):
        metadata_valid(rows,set(allowed),True)
        c.require(z.shape==(len(rows),768),'REFERENCE_SHAPE')
        self.rows=rows; self.z=z; self.groups={}; self.ends={}; self.by_uid={}
        all_components=set()
        for i,r in enumerate(rows):
            c.require(r['component_id'] not in all_components,'REFERENCE_COMPONENT_DUPLICATE')
            all_components.add(r['component_id']); self.by_uid[r['uid']]=i
            key=(r['device'],r['protocol'])
            self.groups.setdefault(key,[]).append(i)
            c.require(self.ends.setdefault(r['device'],r['reference_end'])==r['reference_end'],'BANK_END_INCONSISTENT')
        self.keys=sorted(self.groups)
        for key,ix in self.groups.items():
            self.groups[key]=sorted(ix,key=lambda i:rows[i]['uid'])

    def subset(self, key, recipe, seed=None, epoch=None, budget=None):
        ix=self.groups.get(key,[])[:]
        if epoch is not None:
            c.require(seed in c.SEEDS and epoch>=0,'SUBSET_SEED_EPOCH')
            budget=recipe['training']['reference_budgets'][epoch%3]
            salt=recipe['training']['reference_subset_salt']
            prefix=salt+'|'+str(seed)+'|'+str(epoch)+'|'+key[0]+'|'+str(key[1])+'|'
        else:
            prefix=recipe['evaluation']['control_salt']+'|'
        if budget is not None and budget!='ALL':
            ix=sorted(ix,key=lambda i:(hashlib.sha256((prefix+self.rows[i]['uid']).encode()).hexdigest(),self.rows[i]['uid']))[:budget]
        return sorted(ix,key=lambda i:self.rows[i]['uid'])

    def matrix(self, z, rows, model, recipe, minimum=2, seed=None, epoch=None, budget=None):
        c.require(z.shape==(len(rows),768),'QUERY_SHAPE')
        q=model(z); values=[]; masks=[]
        for key in self.keys:
            ix=self.subset(key,recipe,seed,epoch,budget)
            mask=torch.tensor([r['protocol']==key[1] and self.ends[key[0]]<r['timestamp'] and len(ix)>=minimum for r in rows])
            if bool(mask.any()):
                # No batch statistics: masked rows cannot contribute gradients or reference updates.
                value=top_score(q,model(self.z[ix]))
            else:
                value=torch.zeros(len(rows),dtype=torch.float32)
            values.append(value.masked_fill(~mask,-torch.inf)); masks.append(mask)
        c.require(bool(values),'EMPTY_BANK')
        return torch.stack(values,1),torch.stack(masks,1)

    def own(self,z,rows,model,recipe,minimum=2,seed=None,epoch=None,budget=None,override=None,empty=False):
        result=torch.zeros(len(rows),dtype=torch.float32); valid=torch.zeros(len(rows),dtype=torch.bool)
        metadata_groups={}
        for i,r in enumerate(rows):
            metadata_groups.setdefault((r['device'],r['protocol']),[]).append(i)
        for key,queries in metadata_groups.items():
            if empty:
                ix=[]
            elif override is None:
                ix=self.subset(key,recipe,seed,epoch,budget)
            else:
                ix=[self.by_uid[u] for u in override.get(key,[])]
                c.require(len(ix)==len(set(ix)),'OVERRIDE_DUPLICATE')
                ix=sorted(ix,key=lambda i:self.rows[i]['uid'])
            if len(ix)<minimum:
                continue
            c.require(all(self.rows[i]['protocol']==key[1] for i in ix),'OVERRIDE_PROTOCOL')
            c.require(len({self.rows[i]['device'] for i in ix})==1,'MIXED_REFERENCE_DEVICE')
            end=max(self.ends[self.rows[i]['device']] for i in ix)
            use=[i for i in queries if end<rows[i]['timestamp']]
            if use:
                result[use]=top_score(model(z[use]),model(self.z[ix])); valid[use]=True
        return result,valid


def evidence_ensemble(scores):
    c.require(len(scores)==3,'THREE_SCORES')
    result=np.stack(scores).mean(axis=0,dtype=np.float64)
    return result


def veto(q_alarm, score, valid, cut):
    q_alarm=np.asarray(q_alarm,dtype=bool); valid=np.asarray(valid,dtype=bool); score=np.asarray(score,dtype=np.float64)
    c.require(q_alarm.shape==score.shape==valid.shape and np.isfinite(cut),'VETO_SHAPE_CUT')
    c.require(np.isfinite(score[valid]).all(),'VETO_NONFINITE')
    return q_alarm & ~(valid & (score>cut))


def protected_cut(scores):
    scores=np.asarray(scores,dtype=np.float64)
    c.require(scores.size>0 and np.isfinite(scores).all() and (np.abs(scores)<=1).all(),'CAL_SCORES')
    cut=max(0.,float(scores.max()))+1e-5
    c.require(not (scores>cut).any(),'CAL_CANCELLED_ATTACK')
    return cut
