"""Causal student and the three fixed loss packages; no real-data I/O."""
import random
import platform
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from torch.nn.utils.rnn import pad_sequence, pack_padded_sequence, pad_packed_sequence
import issue27frontend_transfer_support_v1 as s
from issue27frontend_paired_train_model_v1 import Student as OriginalStudent, state_hash


def configure():
    s.require(platform.python_version() == '3.9.13' and np.__version__ == '2.0.2'
              and torch.__version__ == '2.8.0+cpu', 'RUNTIME_VERSION')
    torch.set_num_threads(4)
    if torch.get_num_interop_threads() != 1:
        torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    random.seed(2705); np.random.seed(2705); torch.manual_seed(2705)


class Student(OriginalStudent):
    def forward(self, sequences, keys, with_hidden=False):
        s.require(len(sequences) == len(keys) > 0 and len(set(keys)) == len(keys), 'BATCH_KEYS')
        for x in sequences:
            s.require(x.dtype == torch.float32 and x.device.type == 'cpu' and x.ndim == 2
                      and x.shape[1] == 131 and 1 <= len(x) <= 256 and bool(torch.isfinite(x).all()), 'INPUT_SCHEMA')
        order = sorted(range(len(keys)), key=lambda i: (-len(sequences[i]), keys[i]))
        lengths = [len(sequences[i]) for i in order]
        x = pad_sequence([sequences[i] for i in order], batch_first=True)
        packed = pack_padded_sequence(self.event_activation(self.event_projection(x)), lengths, batch_first=True, enforce_sorted=True)
        encoded, _ = self.encoder(packed)
        hidden, _ = pad_packed_sequence(encoded, batch_first=True)
        qs, hs = [None]*len(keys), [None]*len(keys)
        for j,i in enumerate(order):
            hs[i] = hidden[j,:lengths[j]]
            qs[i] = self.head_output(self.head_activation(self.head_hidden(hs[i]))).squeeze(-1)
            s.require(bool(torch.isfinite(qs[i]).all()), 'NONFINITE_LOGIT')
        return (qs,hs) if with_hidden else qs


class Projection(nn.Module):
    """Zero parameters without consuming RNG, unlike default nn.Linear init."""
    def __init__(self):
        super().__init__()
        self.weight = nn.Parameter(torch.zeros(128,128))
        self.bias = nn.Parameter(torch.zeros(128))

    def forward(self, x):
        return F.linear(x, self.weight, self.bias)


def optimizer(model, projection, r):
    params = list(model.parameters()) + ([] if projection is None else list(projection.parameters()))
    cfg = r['optimizer']
    keys = ('lr','weight_decay','eps','amsgrad','foreach','fused','maximize','capturable','differentiable')
    return torch.optim.AdamW(params, betas=tuple(cfg['betas']), **{k:cfg[k] for k in keys})


def huber(x):
    return torch.where(x.abs() <= 1, .5*x.square(), x.abs()-.5)


def label_loss(batch, qs):
    return torch.stack([F.binary_cross_entropy_with_logits(q[[t['event'] for t in c['targets']]],
                       q.new_tensor([t['label'] for t in c['targets']])) for c,q in zip(batch,qs)]).sum()


def guard_loss(batch, qs, groups, epoch, scale):
    logits = {t['uid']:q[t['event']] for c,q in zip(batch,qs) for t in c['targets']}
    ps = s.guard_pairs(batch, groups, epoch, scale)
    if not ps:
        return qs[0].sum()*0, 0
    delta = torch.stack([logits[a['uid']]-logits[b['uid']] for a,b,_ in ps])/scale
    margin = delta.new_tensor([v for _,_,v in ps])
    return huber(torch.relu(margin-delta)).mean(), len(ps)


def teacher_loss(batch, hs, projection, cache, denominators, steps):
    terms = []
    for c,h in zip(batch,hs):
        s.require(c['role'] == 'train', 'TEACHER_NONTRAIN')
        for y in (0,1):
            selected = [t for t in c['targets'] if t['uid'] in cache and t['label'] == y]
            if not selected:
                continue
            s.require(all(t['owner'] == 'A' and t['old_hard'] == t['label'] for t in selected), 'TEACHER_SCOPE')
            pred = projection(h[[t['event'] for t in selected]])
            target = torch.stack([cache[t['uid']] for t in selected])
            terms.append(huber(pred-target).mean() * (steps/(2*denominators[y])))
    return torch.stack(terms).sum() if terms else hs[0].sum()*0


def gradient_norm(parameters):
    values = [p.grad.detach().norm(2) for p in parameters if p.grad is not None]
    return float(torch.stack(values).norm(2)) if values else 0.


def update(model, projection, opt, a, b, arm, epoch, guard, cache, r, charge=lambda batch: None):
    opt.zero_grad(set_to_none=True)
    steps = r['schedule']['steps_per_epoch']
    stats = dict(label=0., guard=0., teacher=0., pairs=0)
    for owner,batch in [('A',a),('B',b)]:
        for start in range(0,len(batch),32):
            micro = batch[start:start+32]
            charge(micro)
            qs,hs = model([c['x'] for c in micro],[c['key'] for c in micro], with_hidden=True)
            label = label_loss(micro,qs)*(steps/r['data'][owner]['contexts'])
            total = label; stats['label'] += float(label.detach())
            if owner == 'A' and arm != 'C0':
                penalty,n = guard_loss(micro,qs,guard[0],epoch,guard[1])
                total = total+penalty; stats['guard'] += float(penalty.detach()); stats['pairs'] += n
            if owner == 'A' and arm == 'C2':
                cfg = r['losses']['P2_feature']
                penalty = teacher_loss(micro,hs,projection,cache,{y:cfg['expected_N_T'+str(y)] for y in (0,1)},steps)
                total = total+penalty; stats['teacher'] += float(penalty.detach())
            s.require(bool(torch.isfinite(total)), 'NONFINITE_LOSS')
            total.backward()
    ps = list(model.parameters()); ds = [] if projection is None else list(projection.parameters())
    stats.update(student_gradient_L2=gradient_norm(ps), D_gradient_L2=gradient_norm(ds))
    norm = torch.nn.utils.clip_grad_norm_(ps+ds,1.,norm_type=2.,error_if_nonfinite=True,foreach=False)
    stats['clip_factor'] = float(torch.clamp(1./(norm+1e-6),max=1.))
    opt.step()
    s.require(all(bool(torch.isfinite(p).all()) for p in ps+ds), 'NONFINITE_PARAMETER')
    return stats
