"""Calibrate thresholds with target normal references only."""
from collections import Counter, defaultdict
from math import fsum

import numpy as np

from analysis_core import guard
from common_round1 import require

RAW = 'RAW'
P4 = 'P4_MAIN'
WITH_GUARD = 'RECAL_WITH_GUARD'
NO_GUARD = 'RECAL_NO_GUARD'
ARMS = (RAW, P4, WITH_GUARD, NO_GUARD)
FIELDS = ('device', 'capture_id', 'component_id')


def four(scores):
    require(scores.ndim == 2 and scores.shape[1] == 3 and np.isfinite(scores).all(), 'HEAD_SCORES')
    scores = scores.astype(np.float64, copy=False)
    return np.column_stack((scores, np.stack([scores[:, j] for j in range(3)]).mean(0, dtype=np.float64)))


def hierarchical_weights(rows):
    require(rows and all(r.get('use') == 'REFERENCE' and r.get('label') == 0 for r in rows),
            'TARGET_REFERENCE_NORMAL_ONLY')
    require(all(all(isinstance(r.get(k), str) and r[k] for k in FIELDS) for r in rows),
            'REFERENCE_WEIGHT_FIELDS')
    keys = [tuple(row[k] for k in FIELDS) for row in rows]
    leaves = Counter(keys)
    branches = defaultdict(set)
    for key in leaves:
        for i, value in enumerate(key):
            branches[key[:i]].add(value)
    weight = {k: 1 / (leaves[k] * len(branches[()]) * len(branches[k[:1]]) * len(branches[k[:2]]))
              for k in leaves}
    result = np.asarray([weight[k] for k in keys], dtype=np.float64)
    require(abs(fsum(result) - 1.) <= 1e-12, 'REFERENCE_WEIGHT_MASS')
    return result, keys


def weighted_cut(scores, weights, budget):
    """Same discrete strict upper-tail rule as the frozen source CAL."""
    require(scores.shape == weights.shape and scores.ndim == 1 and len(scores) and
            np.isfinite(scores).all() and np.isfinite(weights).all() and (weights > 0).all() and
            abs(fsum(weights) - 1.) <= 1e-12 and budget == .01, 'CALIBRATION_INPUT')
    order = np.argsort(scores, kind='stable')
    x, w = scores[order], weights[order]
    tail = np.r_[np.cumsum(w[::-1], dtype=np.float64)[::-1], 0.]
    end = np.r_[np.flatnonzero(x[:-1] != x[1:]), len(x)-1]
    i = int(end[np.flatnonzero(tail[end+1] <= budget)[0]])
    value = float(x[i])
    strict_mass = fsum(weights[scores > value])
    require(strict_mass <= budget + 1e-14, 'STRICT_TAIL_BUDGET')
    return dict(cut=value, strict_tail_mass=strict_mass, tied_mass=fsum(weights[scores == value]),
                tail_count=int(np.count_nonzero(scores > value)), distinct_scores=len(end))


def fit(rows, scores, q, source_cuts, budget=.01):
    w, keys = hierarchical_weights(rows)
    g = guard(q)
    require(len(rows) == len(q) == len(scores) and scores.shape[1] == len(source_cuts) == 4, 'CAL_SHAPE')
    fits = {}
    for name, ix in [(NO_GUARD, np.ones(len(g), dtype=bool)), (WITH_GUARD, ~g)]:
        mass = fsum(w[ix])
        require(mass > 0, 'NO_UNPROTECTED_NORMAL_REFERENCE')
        conditional = w[ix] / mass
        result = []
        for col, src in enumerate(source_cuts):
            row = weighted_cut(scores[ix, col], conditional, budget)
            row['delta_from_source'] = row['cut'] - src
            retained = g & (scores[:, col] > src) if name == WITH_GUARD else np.zeros(len(g), dtype=bool)
            row['protected_source_tail_mass'] = fsum(w[retained])
            row['full_reference_alarm_mass'] = row['protected_source_tail_mass'] + row['strict_tail_mass'] * mass
            result.append(row)
        fits[name] = dict(heads=result, fitted_rows=int(ix.sum()), fitted_weight_mass=mass,
                          fitted_components=len({keys[i] for i in np.flatnonzero(ix)}))
    return dict(rows=len(rows), protected_rows=int(g.sum()), protected_weight_mass=fsum(w[g]),
                weight_fields=list(FIELDS), threshold_budget=budget, fits=fits)


def predictions(raw, p4, q, active, source_cuts, fitted):
    base = raw > source_cuts
    primary = p4 > source_cuts
    g = guard(q)
    require(np.array_equal(primary[~active | g], base[~active | g]), 'P4_FROZEN_FALLBACK')
    result = {RAW: base, P4: primary}
    for name, mask in [(WITH_GUARD, active & ~g), (NO_GUARD, active)]:
        choice = base.copy()
        choice[mask] = raw[mask] > [v['cut'] for v in fitted['fits'][name]['heads']]
        require(np.array_equal(choice[~mask], base[~mask]), 'RECAL_RAW_FALLBACK:' + name)
        result[name] = choice
    return result
