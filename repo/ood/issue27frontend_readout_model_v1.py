"""Original C0 numerics with an immutable AB encoder and the full MLP trainable."""
import hashlib
import torch
import issue27frontend_readout_support_v1 as s
import issue27frontend_transfer_model_v1 as original
from issue27frontend_transfer_model_v1 import Student, configure, state_hash

HEAD = ('head_hidden.', 'head_output.')
FROZEN = ('event_projection.', 'encoder.')


def tensor_hashes(model, prefixes=FROZEN):
    result = {}
    for name, value in sorted(model.state_dict().items()):
        if name.startswith(prefixes):
            a = value.detach().cpu().contiguous().numpy()
            result[name] = hashlib.sha256(str(a.dtype).encode()+str(a.shape).encode()+a.tobytes()).hexdigest()
    return result


def freeze(model):
    for name, p in model.named_parameters():
        s.require(name.startswith(HEAD+FROZEN), 'UNEXPECTED_PARAMETER:'+name)
        p.requires_grad_(name.startswith(HEAD))
        p.grad = None
    check_layout(model)
    return tensor_hashes(model)


def check_layout(model, optimizer=None):
    head, frozen = [], []
    for name, p in model.named_parameters():
        s.require(name.startswith(HEAD+FROZEN), 'UNEXPECTED_PARAMETER')
        expected = name.startswith(HEAD)
        s.require(p.requires_grad == expected, 'FREEZE_LAYOUT')
        (head if expected else frozen).append(p)
        if not expected:
            s.require(p.grad is None, 'FROZEN_GRADIENT')
    s.require(sum(p.numel() for p in head) == 8321 and sum(p.numel() for p in frozen) == 82944, 'PARAMETER_COUNTS')
    if optimizer is not None:
        actual = [p for g in optimizer.param_groups for p in g['params']]
        s.require([id(p) for p in actual] == [id(p) for p in head], 'OPTIMIZER_PARAMETER_SCOPE')
        s.require(all(p not in optimizer.state for p in frozen), 'FROZEN_OPTIMIZER_STATE')
    return head


def make_optimizer(parameters, r):
    cfg = r['optimizer']
    keys = ('lr','weight_decay','eps','amsgrad','foreach','fused','maximize','capturable','differentiable')
    return torch.optim.AdamW(parameters, betas=tuple(cfg['betas']), **{k:cfg[k] for k in keys})


def optimizer(model, r):
    opt = make_optimizer(check_layout(model), r)
    check_layout(model, opt)
    return opt


def numerical_update(model, opt, a, b, epoch, r, charge=lambda batch: None):
    # The original C0 branch never invokes guard/teacher routines. Frozen .grad
    # values are None, so its full-model clipping selects exactly the head grads.
    stats = original.update(model, None, opt, a, b, 'C0', epoch, None, None, r, charge)
    s.require(stats['guard'] == stats['teacher'] == stats['pairs'] == stats['D_gradient_L2'] == 0, 'AUXILIARY_CALL')
    return dict(label=stats['label'], head_gradient_L2=stats['student_gradient_L2'], clip_factor=stats['clip_factor'])


def update(model, opt, a, b, epoch, r, charge=lambda batch: None):
    check_layout(model, opt)
    s.require(all(not c['x'].requires_grad for c in a+b), 'INPUT_GRADIENT')
    stats = numerical_update(model, opt, a, b, epoch, r, charge)
    check_layout(model, opt)
    return stats


def verify_frozen(model, expected, opt=None):
    check_layout(model, opt)
    s.require(tensor_hashes(model) == expected, 'FROZEN_TENSOR_CHANGED')
