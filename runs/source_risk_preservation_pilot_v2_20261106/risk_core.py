"""One-sided source risk and detection-preservation objectives, not logit imitation."""
import hashlib
import numpy as np
import torch


def fingerprint(model):
    h = hashlib.sha256()
    for name, value in model.state_dict().items():
        h.update(name.encode()); h.update(value.detach().cpu().numpy().tobytes())
    return h.hexdigest()


def sample(labels, seed=20261106, each=8192):
    rng = np.random.default_rng(seed)
    groups = [rng.permutation(np.flatnonzero(labels == y))[:each] for y in (0, 1)]
    assert all(len(g) == each for g in groups), 'INSUFFICIENT_SOURCE_CLASS'
    return np.concatenate(groups)


def batch_weights(weights, labels):
    """Within fixed pilot, preserve original stratum ratios and balance classes."""
    out = np.zeros(len(weights), np.float64)
    for y in (0, 1):
        mask = labels == y
        assert mask.any() and weights[mask].sum() > 0
        out[mask] = weights[mask] / weights[mask].sum()
    return out


def components(scores, zero_scores, teacher, teacher_zero, labels, weights,
               normal_upper, scale, class_rows, attack_slack=.01, retain=.9):
    assert scale > 0 and scores.ndim == 1
    w = torch.as_tensor(weights, dtype=torch.float64)
    normal = labels == 0; attack = labels == 1
    # Each batch contains equal class counts. n_class / batch_class estimates
    # the fixed pilot's normalized per-class weighted expectation.
    def mean(value, mask):
        assert bool(mask.any())
        return (value[mask] * w[mask]).sum() * class_rows / int(mask.sum())
    normal_loss = mean(torch.relu((scores-normal_upper)/scale).square(), normal)
    attack_loss = mean(torch.relu((teacher-scores)/scale-attack_slack).square(), attack)
    teacher_lift = torch.relu(teacher-teacher_zero)
    # Only positive baseline uplift is protected. This synthetic intervention
    # is a regularizer, never a real traffic sample or deployment score.
    context_loss = mean(torch.relu((retain*teacher_lift-(scores-zero_scores))/scale).square()
                        * (teacher_lift > 0), attack)
    return normal_loss, attack_loss, context_loss


def vector(loss, model):
    return torch.cat([g.reshape(-1) for g in torch.autograd.grad(loss, tuple(model.parameters()), retain_graph=True)]).detach().double()


def relation(a, b):
    na = float(torch.linalg.vector_norm(a)); nb = float(torch.linalg.vector_norm(b))
    dot = float(torch.dot(a, b))
    return dict(normal_norm=na, protection_norm=nb, dot=dot,
                cosine=dot/(na*nb) if min(na, nb) > 1e-12 else None)


def quant(values):
    values = np.asarray(values)
    return dict(zip(['min','p01','p10','p50','p90','p99','max'],
                    map(float, np.quantile(values,[0,.01,.1,.5,.9,.99,1])))) if len(values) else None
