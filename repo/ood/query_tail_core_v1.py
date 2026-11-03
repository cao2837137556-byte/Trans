"""QUERY_TAIL frozen math and current-query readout; no real asset access."""
import hashlib
import math
import random
from decimal import Decimal
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
import continuous_common_v3 as c
from legacy_qref_data_v1 import class_weights, metadata_valid
from continuous_model_v3 import weights, threshold

DESIGN_SHA = '8fc236975039773580fef8d40705d205dc382dbc5159c43833928958c62a6ecd'
ARMS = ('QUERY_BCE', 'RECENT_TAIL', 'QUERY_TAIL')
ROLES = ('LEARN', 'CIC_DEV', 'UNSW_DEV')
STAGES = ('UDP', 'TCP_RST', 'TCP_SYN_NO_ACK', 'TCP_SYN_ACK', 'TCP_FIN', 'TCP_OTHER')


def classifier(seed, dimension):
    c.require(seed in c.SEEDS and dimension in (768, 782), 'HEAD_SCOPE')
    torch.manual_seed(seed)
    base = nn.Sequential(nn.Linear(768, 128), nn.ReLU(), nn.Linear(128, 1))
    if dimension == 782:
        target = nn.Sequential(nn.Linear(782, 128), nn.ReLU(), nn.Linear(128, 1))
        with torch.no_grad():
            target[0].weight[:, :768].copy_(base[0].weight)
            target[0].weight[:, 768:].zero_()
            target[0].bias.copy_(base[0].bias)
            target[2].load_state_dict(base[2].state_dict())
        base = target
    c.require(sum(p.numel() for p in base.parameters()) == (98561 if dimension == 768 else 100353), 'PARAMETERS')
    return base


def descriptor(body, row):
    """Locate by frame, verify every retained packet and its flow token join."""
    p, flow = body['provenance'], body['flow']
    proto = row['protocol']
    c.require(proto in (6, 17) and flow['protocol'] == proto, 'QUERY_PROTOCOL')
    c.require(row['use'] != 'REFERENCE' and row['partition'] in ('LEARN', 'DEV', 'EXTERNAL_ARCHIVAL_EVALUATION'), 'QUERY_ROLE')
    c.require(p['version'] == 'continuous-input-core-repair-design-v3-20260929', 'SNAPSHOT_VERSION')
    c.require(p['query_frame'] == row['frame'] and p['namespace_sha256'] == row['session_id'], 'QUERY_IDENTITY')
    now = p['query_time_ns']
    # Original metadata timestamps are floats, while the spool retains exact ns.
    c.require(type(now) is int and float(Decimal(now)/Decimal(10**9)) == row['timestamp'], 'QUERY_TIME')
    bursts = p['bursts']; width = 12 if proto == 6 else 6
    c.require(0 < len(bursts) <= 12 and all(len(flow[k]) == len(bursts) for k in ('counts', 'directions', 'burst_tokens', 'iats', 'bytes')), 'BURST_SCHEMA')
    frames, times, directions, query = [], [], [], []
    for b, burst in enumerate(bursts):
        ff, tt, hh = burst['frames'], burst['times_ns'], burst['headers']
        c.require(0 < len(ff) <= 6 and len(ff) == len(tt) == len(hh) == flow['counts'][b], 'PACKET_SCHEMA')
        c.require(type(flow['directions'][b]) is bool, 'DIRECTION_SCHEMA')
        c.require(all(type(f) is int for f in ff) and all(type(t) is int for t in tt), 'TIME_FRAME_TYPE')
        c.require(all(ff[i] < ff[i+1] and tt[i] <= tt[i+1] for i in range(len(ff)-1)), 'BURST_ORDER')
        packed = []
        for f, t, h in zip(ff, tt, hh):
            c.require(len(h) == width and all(type(v) is int and 0 <= v <= 65535 for v in h), 'HEADER_SCHEMA')
            c.require(0 < f <= row['frame'] and 0 <= now-t <= 60*10**9, 'FUTURE_OR_AGED_PACKET')
            packed.extend(h + [0]*6)
            frames.append(f); times.append(t); directions.append(flow['directions'][b])
            if f == row['frame']:
                c.require(t == now, 'CURRENT_TIME')
                query.append((h, flow['directions'][b]))
        c.require(flow['burst_tokens'][b] == packed, 'FLOW_HEADER_JOIN')
    c.require(len(frames) == len(set(frames)) <= 72 and len(query) == 1, 'CURRENT_UNIQUE')
    order = np.argsort(frames)
    c.require(all(times[int(order[i])] <= times[int(order[i+1])] for i in range(len(order)-1)), 'WINDOW_TIME_ORDER')
    c.require(directions[int(order[0])] is True, 'FIRST_SOURCE_DIRECTION')
    c.require(flow['flow_duration'] == (now-min(times))//1000, 'FLOW_DURATION')
    h, direction = query[0]
    flags = h[5] if proto == 6 else 0
    c.require(flags <= 511, 'UNSUPPORTED_FLAG_BITS')
    q = [float(proto == 6)] + [float(bool(flags & (1 << b))) for b in range(9)]
    q += [math.log1p(h[2])/math.log(65536), math.log1p(h[6])/math.log(65536) if proto == 6 else 0.,
          math.log1p(h[5])/math.log(65536) if proto == 17 else 0., float(direction)]
    stage = ('UDP' if proto == 17 else 'TCP_RST' if flags & 4 else
             'TCP_SYN_NO_ACK' if flags & 2 and not flags & 16 else 'TCP_SYN_ACK' if flags & 2 else
             'TCP_FIN' if flags & 1 else 'TCP_OTHER')
    info = dict(stage=stage, syn_no_ack=bool(proto == 6 and flags & 2 and not flags & 16),
                packets=len(frames), bursts=len(bursts), span_seconds=(now-min(times))/1e9,
                same_direction=sum(d == direction for d in directions),
                opposite_direction=sum(d != direction for d in directions))
    return np.asarray(q, dtype=np.float32), info


def tail_distribution(scores, conditional_weights, mass=.01):
    x, w = np.asarray(scores), np.asarray(conditional_weights, dtype=np.float64)
    c.require(x.ndim == w.ndim == 1 and len(x) == len(w) > 0 and np.isfinite(x).all() and np.isfinite(w).all(), 'TAIL_SHAPE_FINITE')
    c.require(np.all(w > 0) and math.isclose(math.fsum(w), 1., abs_tol=1e-12) and 0 < mass <= 1, 'TAIL_WEIGHT')
    order = np.argsort(-x, kind='stable'); sorted_x = x[order]
    ends = np.r_[np.flatnonzero(sorted_x[:-1] != sorted_x[1:])+1, len(x)]
    h = np.zeros(len(x), dtype=np.float64); remaining = mass; start = 0
    for end in ends:
        ix = order[start:end]; total = math.fsum(w[ix]); take = min(total, remaining)
        h[ix] = w[ix] * (take/total)
        remaining = max(0., remaining-take); start = int(end)
        if remaining == 0.: break
    c.require(math.isclose(math.fsum(h), mass, rel_tol=1e-12, abs_tol=1e-15), 'TAIL_MASS')
    return h/math.fsum(h)


class TailSampler:
    def __init__(self, rows, probabilities, seed, epoch):
        c.require(len(rows) == len(probabilities) and len({r['uid'] for r in rows}) == len(rows), 'TAIL_UID')
        c.require(all(r['partition'] == 'LEARN' and r['fit_role'] == 'FIT' and r['label'] == 0 for r in rows), 'TAIL_FIT_NORMAL_ONLY')
        p = np.asarray(probabilities, dtype=np.float64)
        c.require(np.isfinite(p).all() and np.all(p >= 0) and math.isclose(math.fsum(p), 1., abs_tol=1e-12), 'TAIL_PROBABILITY')
        self.order = np.asarray(sorted((i for i in range(len(rows)) if p[i] > 0), key=lambda i: rows[i]['uid']))
        self.cdf = np.cumsum(p[self.order], dtype=np.float64); self.cdf[-1] = 1.
        self.rng = random.Random(int(hashlib.sha256(('query-tail-v1|%s|%s' % (seed, epoch)).encode()).hexdigest(), 16))

    def draw(self, count=128):
        return self.order[np.searchsorted(self.cdf, [self.rng.random() for _ in range(count)], side='right')]


def objective(logits, labels, batch_weights, full_size, negative_logits=None):
    c.require(len(logits) == len(labels) == len(batch_weights) > 0, 'LOSS_SHAPE')
    w = torch.as_tensor(batch_weights, dtype=torch.float64)
    bce = (F.binary_cross_entropy_with_logits(logits, labels, reduction='none')*w).sum()*(full_size/len(logits))
    if negative_logits is None:
        return bce
    mask = labels == 1
    pair = ((F.softplus(negative_logits[None, :]-logits[mask, None]).mean(1)*2*w[mask]).sum()
            *(full_size/len(logits))) if bool(mask.any()) else logits.sum()*0.
    return (bce+pair)/2


def normalized(values, q, indices, norm, dimension):
    mean, scale = norm
    c.require(mean.shape == scale.shape == (768,) and np.isfinite(mean).all() and np.isfinite(scale).all() and np.all(scale > 0), 'NORMALIZER_SCHEMA')
    x = ((np.asarray(values[indices, :768], dtype=np.float64)-mean)/scale).astype(np.float32)
    if dimension == 782:
        extra = np.asarray(q[indices], dtype=np.float32)
        c.require(extra.shape == (len(x), 14) and np.all((extra >= 0) & (extra <= 1)), 'Q_SCHEMA')
        x = np.concatenate((x, extra), axis=1)
    c.require(np.isfinite(x).all(), 'NORMALIZED_NONFINITE')
    return torch.from_numpy(x)


def scores(model, values, q, indices, norm, dimension, progress=None):
    result = np.empty(len(indices), dtype=np.float32)
    with torch.inference_mode():
        for start in range(0, len(indices), 1024):
            ix = indices[start:start+1024]
            result[start:start+len(ix)] = model(normalized(values, q, ix, norm, dimension)).flatten().numpy()
            if progress is not None: progress.tick(start+len(ix), len(indices))
    c.require(np.isfinite(result).all(), 'SCORES_NONFINITE')
    return result
