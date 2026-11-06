"""Source-only finite-update acceptance and complete Adam/RNG rollback."""
import copy,hashlib,time
import numpy as np
import torch

def state_hash(value):
    h=hashlib.sha256()
    def add(x):
        if torch.is_tensor(x):h.update(str((x.dtype,tuple(x.shape))).encode());h.update(x.detach().cpu().numpy().tobytes())
        elif isinstance(x,dict):
            for key in sorted(x,key=str):h.update(str(key).encode());add(x[key])
        elif isinstance(x,(list,tuple)):
            for v in x:add(v)
        else:h.update(repr(x).encode())
    add(value);return h.hexdigest()

def snapshot(model,opt):return copy.deepcopy(model.state_dict()),copy.deepcopy(opt.state_dict()),torch.get_rng_state().clone()
def restore(model,opt,saved):
    model.load_state_dict(copy.deepcopy(saved[0]));opt.load_state_dict(copy.deepcopy(saved[1]));torch.set_rng_state(saved[2].clone())

def guarded_block(model,opt,train,evaluate,previous,base_lr,factors=(1.,.5,.25,.125)):
    saved=snapshot(model,opt);before=state_hash(saved);attempts=[]
    for factor in factors:
        restore(model,opt,saved)
        for group in opt.param_groups:group['lr']=base_lr*factor
        t=time.monotonic();training=train();train_seconds=time.monotonic()-t
        t=time.monotonic();evidence=evaluate();guard_seconds=time.monotonic()-t
        checks=dict(evidence['checks']);tol=max(1e-14,abs(previous['normal_tail_risk'])*1e-10)
        checks['normal_risk_nonincrease_from_retained']=evidence['normal_tail_risk']<=previous['normal_tail_risk']+tol
        accept=all(checks.values())
        attempts.append(dict(factor=factor,accepted=accept,training=training,train_seconds=train_seconds,
            guard_seconds=guard_seconds,checks=checks,evidence=evidence))
        if accept:return dict(accepted=True,factor=factor,attempts=attempts,evidence=evidence,rollback_verified=True)
    restore(model,opt,saved);assert state_hash(snapshot(model,opt))==before,'FULL_ROLLBACK_MISMATCH'
    return dict(accepted=False,factor=0.,attempts=attempts,evidence=previous,rollback_verified=True)

class SourceGuard:
    def __init__(self,rows,selected,base,zero_base,cut,scale,upper,class_weights,criteria):
        self.base=base;self.zero_base=zero_base;self.cut=cut;self.scale=scale;self.upper=upper;self.criteria=criteria
        self.cohorts={};labels=np.asarray([r['label'] for r in rows]);unused=np.ones(len(rows),bool);unused[np.unique(selected)]=False
        for role,take in [('fit',np.ones(len(rows),bool)),('fit_not_sampled_for_gradient',unused)]:
            self.cohorts[role]={}
            for y,label in [(0,'normal'),(1,'attack')]:
                ix=np.flatnonzero(take&(labels==y));rr=[rows[i] for i in ix];assert len(rr)>0
                weight=class_weights(rr);protocol=np.asarray([str(r['protocol']) for r in rr])
                self.cohorts[role][label]=(ix,weight,{p:protocol==p for p in sorted(set(protocol))})
    def evaluate(self,score,zero):
        assert np.isfinite(score).all() and np.isfinite(zero).all()
        output={};checks={}
        for role,cohorts in self.cohorts.items():
            metric={}
            for label,(ix,w,protocols) in cohorts.items():
                base=self.base[ix];s=score[ix];b=base>self.cut;a=s>self.cut
                v=dict(rows=len(ix),baseline_rate=float(b.mean()),candidate_rate=float(a.mean()),
                    baseline_weighted_rate=float(np.dot(w,b)),candidate_weighted_rate=float(np.dot(w,a)),
                    removed=int((b&~a).sum()))
                if label=='normal':v['tail_risk']=float(np.dot(w,np.maximum((s-self.upper)/self.scale,0)**2))
                else:
                    lift0=base-self.zero_base[ix];lift=s-zero[ix];pos=lift0>0
                    v.update(standardized_score_change=dict(p01=float(np.quantile((s-base)/self.scale,.01))),
                        positive_context_retention=float(np.dot(w[pos],lift[pos])/np.dot(w[pos],lift0[pos])) if pos.any() else None,
                        cohorts=dict(protocol={p:dict(baseline_rate=float(b[t].mean()),candidate_rate=float(a[t].mean())) for p,t in protocols.items()}))
                metric[label]=v
            output[role]=metric;checks.update({role+'/'+name:bool(ok) for name,ok in self.criteria(metric).items()})
        return dict(metrics=output,checks=checks,normal_tail_risk=output['fit']['normal']['tail_risk'],guard_rows=len(score),CAL_used=False)
