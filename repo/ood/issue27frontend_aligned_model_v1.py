"""Q/R numerical changes only; retain original causal student and base objectives."""
import torch
import issue27frontend_aligned_support_v1 as s
from issue27frontend_transfer_model_v1 import (
    Student, Projection, configure, state_hash, optimizer, huber,
    label_loss, guard_loss, gradient_norm)


def teacher_terms(batch, qs, hs, projection, cache, denominators, steps):
    """One global class/context measure; R projects BEFORE coordinate Huber."""
    qterms, rterms = [], []
    stats = dict(teacher_targets=0, raw_error_abs_sum=0., normalized_error_abs_sum=0.,
                 task_hard_agree=0, residual_huber_sum=0.)
    for c,q,h in zip(batch,qs,hs):
        s.require(c['role'] == 'train', 'TEACHER_NONTRAIN')
        for y in (0,1):
            selected = [t for t in c['targets'] if t['uid'] in cache and t['label'] == y]
            if not selected:
                continue
            s.require(all(t['owner']=='A' and t['old_hard']==t['label'] for t in selected), 'TEACHER_SCOPE')
            entries = [cache[t['uid']] for t in selected]
            target = torch.stack([v['margin'] for v in entries])
            scale = entries[0]['scale']
            scores = q[[t['event'] for t in selected]]
            error = scores-target
            normalized = error/scale
            weight = steps/(2*denominators[y])
            qterms.append(huber(normalized).mean()*weight)
            with torch.no_grad():
                stats['teacher_targets'] += len(selected)
                stats['raw_error_abs_sum'] += float(error.abs().sum())
                stats['normalized_error_abs_sum'] += float(normalized.abs().sum())
                stats['task_hard_agree'] += int(((scores>=0)==(target>=0)).sum())
            if projection is not None:
                pred = projection(h[[t['event'] for t in selected]])
                e = pred-torch.stack([v['target'] for v in entries])
                residual = e-e.mean(dim=-1,keepdim=True)
                per_target = huber(residual).sum(dim=-1)/127
                rterms.append(per_target.mean()*weight)
                stats['residual_huber_sum'] += float(per_target.detach().sum())
    zero = qs[0].sum()*0
    return (torch.stack(qterms).sum() if qterms else zero,
            torch.stack(rterms).sum() if rterms else zero,stats)


def update(model, projection, opt, a, b, arm, epoch, guard, cache, r, charge=lambda batch: None):
    s.require(arm in ('Q','R') and (projection is not None)==(arm=='R'), 'ARM_PROJECTION')
    opt.zero_grad(set_to_none=True)
    steps = r['schedule']['steps_per_epoch']
    stats = dict(label=0.,guard=0.,task_score=0.,residual=0.,pairs=0,
                 teacher_targets=0,raw_error_abs_sum=0.,normalized_error_abs_sum=0.,
                 task_hard_agree=0,residual_huber_sum=0.)
    # Original A buckets have at most32 contexts, so guard is a whole-bucket loss.
    s.require(len(a)<=32,'A_BUCKET_EXCEEDS_FROZEN_MICROBATCH')
    for owner,batch in [('A',a),('B',b)]:
        for start in range(0,len(batch),32):
            micro=batch[start:start+32]; charge(micro)
            qs,hs=model([c['x'] for c in micro],[c['key'] for c in micro],with_hidden=True)
            label=label_loss(micro,qs)*(steps/r['data'][owner]['contexts'])
            total=label;stats['label']+=float(label.detach())
            if owner=='A':
                penalty,n=guard_loss(micro,qs,guard[0],epoch,guard[1])
                total=total+penalty;stats['guard']+=float(penalty.detach());stats['pairs']+=n
                qloss,rloss,observed=teacher_terms(micro,qs,hs,projection,cache,
                    {y:r['teacher_cache']['expected_N_T'+str(y)] for y in (0,1)},steps)
                total=total+qloss
                if projection is not None:
                    total=total+rloss
                stats['task_score']+=float(qloss.detach());stats['residual']+=float(rloss.detach())
                for k,v in observed.items():stats[k]+=v
            s.require(bool(torch.isfinite(total)),'NONFINITE_LOSS')
            total.backward()
    ps=list(model.parameters());ds=[] if projection is None else list(projection.parameters())
    stats.update(student_gradient_L2=gradient_norm(ps),D_gradient_L2=gradient_norm(ds))
    norm=torch.nn.utils.clip_grad_norm_(ps+ds,1.,norm_type=2.,error_if_nonfinite=True,foreach=False)
    stats['clip_factor']=float(torch.clamp(1./(norm+1e-6),max=1.))
    opt.step()
    s.require(all(bool(torch.isfinite(p).all()) for p in ps+ds),'NONFINITE_PARAMETER')
    return stats
