"""Fixed-parameter gradient geometry and training-side teacher readout errors."""
import math
import torch
import issue27frontend_transfer_model_v1 as m
import issue27frontend_transfer_support_v1 as s


def parameter_groups(model, projection):
    return dict(event_projection=list(model.event_projection.parameters()),
                encoder=list(model.encoder.parameters()),
                head=list(model.head_hidden.parameters())+list(model.head_output.parameters()),
                projection=list(projection.parameters()))


def task_gradients(losses, groups):
    params=[p for ps in groups.values() for p in ps]
    s.require(len({id(p) for p in params})==len(params),'OVERLAPPING_PARAMETER_GROUPS')
    s.require(params and all(p.requires_grad for p in params),'GRADIENT_PARAMETERS')
    result={}
    for task,loss in losses.items():
        s.require(loss.numel()==1 and bool(torch.isfinite(loss)),'NONFINITE_OR_NONSCALAR_LOSS')
        grad=torch.autograd.grad(loss,params,retain_graph=True,allow_unused=True) if loss.requires_grad else [None]*len(params)
        offset=0; result[task]={}
        for name,ps in groups.items():
            parts=[]
            for p,g in zip(ps,grad[offset:offset+len(ps)]):
                value=torch.zeros_like(p) if g is None else g.detach()
                s.require(bool(torch.isfinite(value).all()),'NONFINITE_TASK_GRADIENT')
                parts.append(value.reshape(-1).to(dtype=torch.float64))
            result[task][name]=torch.cat(parts) if parts else torch.zeros(0,dtype=torch.float64)
            offset+=len(ps)
    return result


def vector_metrics(a,b):
    s.require(a.shape==b.shape and a.ndim==1,'VECTOR_SHAPE')
    a=a.detach().to(torch.float64); b=b.detach().to(torch.float64)
    s.require(bool(torch.isfinite(a).all() and torch.isfinite(b).all()),'NONFINITE_VECTOR')
    na,nb=float(a.norm()),float(b.norm()); dot=float(torch.dot(a,b))
    return dict(norm_a=na,norm_b=nb,dot=dot,cosine=None if na==0 or nb==0 else max(-1.,min(1.,dot/(na*nb))))


def row_diagnostics(batch,qs,hs,projection,cache,teacher_index,scale):
    s.require(math.isfinite(scale) and scale>0,'TEACHER_SCALE')
    s.require(len(batch)==len(qs)==len(hs),'ROW_BATCH_SHAPE')
    rows=[]; seen=set()
    with torch.no_grad():
        for c,q,h in zip(batch,qs,hs):
            s.require(c['role']=='train','DIAGNOSTIC_NONTRAIN')
            for t in c['targets']:
                if t['uid'] not in cache:
                    continue
                s.require(t['owner']=='A' and t['old_hard']==t['label'],'ILLEGAL_TEACHER_TARGET')
                s.require(t['uid'] not in seen,'DUPLICATE_TEACHER_TARGET');seen.add(t['uid'])
                item=teacher_index[t['uid']]
                s.require(item['context_key']==c['key']==t['context_key'] and item['label']==t['label'],'TEACHER_INDEX_JOIN')
                pred=projection(h[t['event']]).to(torch.float64)
                target=cache[t['uid']].to(torch.float64)
                s.require(pred.shape==target.shape==(128,),'TEACHER_VECTOR_SHAPE')
                residual=pred-target
                value=dict(uid=t['uid'],context_key=c['key'],label=t['label'],
                           source_group=t.get('source_group','unknown'),attack_family=t.get('attack_family','unknown'),
                           student_logit=float(q[t['event']]),teacher_logit=float(item['canonical_logit']),
                           coordinate_huber=float(m.huber(residual).mean()),
                           coordinate_rmse=float(residual.square().mean().sqrt()),
                           task_residual=scale*float(residual.sum()))
                s.require(all(math.isfinite(value[k]) for k in ('student_logit','teacher_logit','coordinate_huber','coordinate_rmse','task_residual')),'NONFINITE_READOUT')
                rows.append(value)
    return rows
