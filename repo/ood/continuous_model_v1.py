"""One attack score and an explicit normal-reference verifier; no asset I/O."""
import hashlib
import math
import numpy as np
import torch
from torch import nn
import continuous_common_v1 as c
from legacy_qref_data_v1 import class_weights
from legacy_qref_model_v1 import top_score


def classifier(seed, dimension):
    c.require(seed in c.SEEDS and dimension in (768, 794), 'HEAD_SCOPE')
    torch.manual_seed(seed)
    base = nn.Sequential(nn.Linear(768, 128), nn.ReLU(), nn.Linear(128, 1))
    if dimension == 794:
        target = nn.Sequential(nn.Linear(794, 128), nn.ReLU(), nn.Linear(128, 1))
        with torch.no_grad():
            target[0].weight[:, :768].copy_(base[0].weight)
            target[0].weight[:, 768:].zero_()
            target[0].bias.copy_(base[0].bias)
            target[2].load_state_dict(base[2].state_dict())
        base = target
    c.require(sum(p.numel() for p in base.parameters()) == (98561 if dimension == 768 else 101889), 'PARAMETERS')
    return base


def unit(x):
    c.require(bool(torch.isfinite(x).all()), 'NONFINITE_UNIT_INPUT')
    return x / x.norm(dim=-1, keepdim=True).clamp_min(1e-12)


def metric_input(x):
    c.require(x.ndim == 2 and x.shape[1] == 794, 'METRIC_DIMENSION')
    return unit(torch.cat((unit(x[:, :768]), unit(x[:, 768:])), 1) / math.sqrt(2))


class Metric(nn.Module):
    def __init__(self, seed):
        super().__init__()
        c.require(seed in c.SEEDS, 'METRIC_SEED')
        torch.manual_seed(seed)
        self.W = nn.Parameter(torch.empty(64, 794))
        nn.init.orthogonal_(self.W, gain=1)
        self.zero_counts = dict(e3=0,state=0,projection=0,invocation_rows=0)

    def forward(self, x):
        projection=metric_input(x) @ self.W.T
        for key,value in [('e3',x[:,:768]),('state',x[:,768:]),('projection',projection)]:
            self.zero_counts[key]+=int((value.norm(dim=1)==0).sum().detach())
        self.zero_counts['invocation_rows']+=len(x)
        return unit(projection)


class Raw(nn.Module):
    def forward(self, x):
        return metric_input(x)


def fit_normalizer(values, metadata, indices):
    c.require(len(indices) and len(set(indices)) == len(indices), 'NORMALIZER_INDICES')
    c.require(all(metadata[i]['partition'] == 'LEARN' and metadata[i]['fit_role'] == 'FIT' for i in indices), 'NORMALIZER_FIT_ONLY')
    # Parallel-variance merge in float64, bounded blocks; no CAL or reference reads.
    count = 0; mean = np.zeros(values.shape[1]); m2 = np.zeros_like(mean)
    for start in range(0, len(indices), 4096):
        block = np.asarray(values[np.asarray(indices[start:start+4096])], dtype=np.float64)
        c.require(np.isfinite(block).all(), 'NORMALIZER_NONFINITE')
        n = len(block); bm = block.mean(0); delta = bm - mean
        m2 += ((block-bm)**2).sum(0) + delta**2 * count*n/(count+n)
        mean += delta*n/(count+n); count += n
    return mean, np.maximum(np.sqrt(m2/count), 1e-6)


def normalized(values, indices, norm):
    mean, scale = norm
    result = ((np.asarray(values[indices], dtype=np.float64)-mean)/scale).astype(np.float32)
    c.require(np.isfinite(result).all(), 'NORMALIZED_NONFINITE')
    return torch.from_numpy(result)


def weights(rows):
    c.require(all(r['partition'] == 'LEARN' and r['fit_role'] == 'FIT' for r in rows), 'TRAIN_FIT_ONLY')
    result = np.zeros(len(rows), dtype=np.float64)
    for label in (0, 1):
        ix = [i for i, r in enumerate(rows) if r['label'] == label]
        c.require(ix, 'TRAIN_CLASS_MISSING')
        result[ix] = .5 * class_weights([rows[i] for i in ix])
    c.require(math.isclose(math.fsum(result), 1, abs_tol=1e-12), 'WEIGHT_MASS')
    return result


class Bank:
    def __init__(self, rows, values, allowed):
        c.require(len(rows) == len(values) and values.shape[1] == 794, 'BANK_SHAPE')
        self.rows, self.values, self.groups, self.ends, self.by_uid = rows, values, {}, {}, {}
        components = set()
        for i, r in enumerate(rows):
            c.require(r['partition'] in allowed and r['use'] == 'REFERENCE' and r['label'] == 0, 'BANK_ROLE')
            c.require(r['timestamp'] <= r['reference_end'] and math.isfinite(r['reference_end']), 'BANK_TIME')
            c.require(r['uid'] not in self.by_uid and r['component_id'] not in components, 'BANK_DUPLICATE')
            components.add(r['component_id']); self.by_uid[r['uid']] = i
            key = (r['device'], r['protocol'])
            self.groups.setdefault(key, []).append(i)
            c.require(self.ends.setdefault(r['device'], r['reference_end']) == r['reference_end'], 'BANK_FULL_END')
        self.keys = sorted(self.groups)
        for key in self.keys:
            self.groups[key].sort(key=lambda i: rows[i]['uid'])

    def subset(self, key, design, seed=None, epoch=None):
        ix = self.groups.get(key, [])[:]
        if epoch is not None:
            budget = design['training']['reference_budgets'][epoch % 3]
            if budget != 'ALL':
                prefix = design['training']['reference_subset_salt'] + '|%s|%s|%s|%s|' % (seed, epoch, *key)
                ix.sort(key=lambda i: (hashlib.sha256((prefix+self.rows[i]['uid']).encode()).hexdigest(), self.rows[i]['uid']))
                ix = ix[:budget]
        return sorted(ix, key=lambda i: self.rows[i]['uid'])

    def matrix(self, z, rows, model, design, minimum=2, seed=None, epoch=None):
        query = model(z); scores = []; masks = []
        for key in self.keys:
            ix = self.subset(key, design, seed, epoch)
            mask = torch.tensor([r['protocol'] == key[1] and self.ends[key[0]] < r['timestamp'] and len(ix) >= minimum for r in rows])
            score = top_score(query, model(self.values[ix])) if bool(mask.any()) else torch.zeros(len(rows))
            scores.append(score.masked_fill(~mask, -torch.inf)); masks.append(mask)
        c.require(scores, 'EMPTY_BANK')
        return torch.stack(scores, 1), torch.stack(masks, 1)

    def own(self, z, rows, model, design, minimum=2, seed=None, epoch=None, override=None):
        scores = torch.zeros(len(rows)); masks = torch.zeros(len(rows), dtype=torch.bool)
        groups = {}
        for i, r in enumerate(rows):
            groups.setdefault((r['device'], r['protocol']), []).append(i)
        for key, query_ix in groups.items():
            ix = self.subset(key, design, seed, epoch) if override is None else [self.by_uid[u] for u in override.get(key, [])]
            c.require(len(ix) == len(set(ix)), 'OVERRIDE_DUPLICATE')
            if len(ix) < minimum:
                continue
            c.require(all(self.rows[i]['protocol'] == key[1] for i in ix), 'OVERRIDE_PROTOCOL')
            c.require(len({self.rows[i]['device'] for i in ix}) == 1, 'MIXED_DONOR_BANK')
            ix = sorted(ix, key=lambda i: self.rows[i]['uid'])
            end = self.ends[self.rows[ix[0]]['device']]
            use = [i for i in query_ix if end < rows[i]['timestamp']]
            if use:
                scores[use] = top_score(model(z[use]), model(self.values[ix])); masks[use] = True
        return scores, masks


def threshold(logits, normal_rows, budget=.01):
    c.require(len(logits) == len(normal_rows) and len(logits) and np.isfinite(logits).all(), 'CAL_LOGITS')
    c.require(all(r['partition'] == 'LEARN' and r['fit_role'] == 'CAL' and r['label'] == 0 for r in normal_rows), 'CAL_NORMAL_ONLY')
    w = class_weights(normal_rows)
    order = np.argsort(logits, kind='stable'); x = np.asarray(logits)[order]; ww = w[order]
    # Sum strict upper tails rather than subtract a nearly-one cumulative sum.
    tail = np.cumsum(ww[::-1], dtype=np.float64)[::-1]
    ends = np.r_[np.flatnonzero(x[:-1] != x[1:]), len(x)-1]
    for end in ends:
        fp = float(tail[end+1]) if end+1 < len(x) else 0.
        if fp <= budget:
            return float(x[end])
    raise RuntimeError('CAL_THRESHOLD_UNREACHABLE')
