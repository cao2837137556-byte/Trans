"""Dimension adapters around the byte-pinned parent objective and sampler."""
from query_tail_core_v2 import *
import query_tail_core_v2 as parent

ARMS = ('REFIT782', 'STATS8', 'FUSION790')
DIMENSIONS = dict(REFIT782=782, STATS8=8, FUSION790=790)


def classifier(seed, dimension):
    c.require(seed in c.SEEDS and dimension in (8, 782, 790), 'CONTEXT_HEAD_SCOPE')
    if dimension == 782:
        return parent.classifier(seed, 782)
    if dimension == 8:
        torch.manual_seed(seed)
        return nn.Sequential(nn.Linear(8, 128), nn.ReLU(), nn.Linear(128, 1))
    base = parent.classifier(seed, 782)
    target = nn.Sequential(nn.Linear(790, 128), nn.ReLU(), nn.Linear(128, 1))
    with torch.no_grad():
        target[0].weight[:, :782].copy_(base[0].weight)
        target[0].weight[:, 782:].zero_()
        target[0].bias.copy_(base[0].bias)
        target[2].load_state_dict(base[2].state_dict())
    return target


def normalized(values, q, indices, norm, dimension):
    original, context = values
    if dimension == 8:
        result = np.asarray(context[indices], dtype=np.float32)
    else:
        result = parent.normalized(original, q, indices, norm, 782).numpy()
        if dimension == 790:
            result = np.concatenate((result, context[indices]), axis=1)
    c.require(result.shape == (len(indices), dimension) and np.isfinite(result).all(), 'CONTEXT_INPUT')
    return torch.from_numpy(result)


def scores(model, values, q, indices, norm, dimension, progress=None):
    result = np.empty(len(indices), dtype=np.float32)
    with torch.inference_mode():
        for start in range(0, len(indices), 1024):
            ix = indices[start:start+1024]
            result[start:start+len(ix)] = model(normalized(values, q, ix, norm, dimension)).flatten().numpy()
            if progress is not None:
                progress.tick(start+len(ix), len(indices))
    c.require(np.isfinite(result).all(), 'CONTEXT_SCORE_FINITE')
    return result
