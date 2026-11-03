"""Frozen FIT task grouping, statistics, ranking, and sampling for V1."""
from collections import defaultdict
import hashlib
import math

import numpy as np


def require(ok, message):
    if not ok:
        raise ValueError(message)


def _fit_rows(rows):
    require(bool(rows), 'EMPTY_FIT')
    uids = [r['uid'] for r in rows]
    require(len(set(uids)) == len(uids), 'DUPLICATE_UID')
    require(all(r.get('partition') == 'LEARN' and r.get('fit_role') == 'FIT'
                and r.get('label') in (0, 1) for r in rows), 'FIT_ONLY')


def dependency_folds(rows):
    """Map UID to deterministic transitive dependency group and fold."""
    _fit_rows(rows)
    parent = list(range(len(rows)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    first = {}
    for i, row in enumerate(rows):
        for key in (('component', row['component_id']),
                    ('session', row['source_sha256'], row['session_id'])):
            if key in first:
                parent[find(i)] = find(first[key])
            else:
                first[key] = i
    groups = defaultdict(list)
    for i, row in enumerate(rows):
        groups[find(i)].append(row['uid'])
    result = {}
    for members in groups.values():
        group = min(members)
        digest = hashlib.sha256(('learned-onboarding-v1|' + group).encode('utf-8')).hexdigest()
        fold = 'F' + str(int(digest, 16) % 2)
        for uid in members:
            result[uid] = {'group': group, 'fold': fold}
    return result


def hierarchical_weights(rows, include_component=True):
    """Single-class conditional hierarchy; each nonempty branch has equal mass."""
    require(bool(rows) and len({r['label'] for r in rows}) == 1, 'SINGLE_CLASS_REQUIRED')
    require(len({r['uid'] for r in rows}) == len(rows), 'DUPLICATE_UID')
    fields = ('device', 'activity', 'capture_id', 'session_id')
    if include_component:
        fields += ('component_id',)
    children = defaultdict(set)
    leaves = defaultdict(int)
    for row in rows:
        key = tuple(row[f] for f in fields)
        for depth, value in enumerate(key):
            children[key[:depth]].add(value)
        leaves[key] += 1
    weights = []
    for row in rows:
        key = tuple(row[f] for f in fields)
        denom = leaves[key] * math.prod(len(children[key[:depth]]) for depth in range(len(fields)))
        weights.append(1.0 / denom)
    out = np.asarray(weights, dtype=np.float64)
    require(math.isclose(math.fsum(out), 1.0, abs_tol=1e-12), 'WEIGHT_MASS')
    return out


def weighted_quantile(values, weights, probability):
    """Exact v3 rule: first observed value attaining cumulative weight."""
    x, w = np.asarray(values, dtype=np.float64), np.asarray(weights, dtype=np.float64)
    require(x.ndim == w.ndim == 1 and len(x) == len(w) > 0 and
            np.isfinite(x).all() and np.isfinite(w).all() and np.all(w > 0)
            and 0 <= probability <= 1, 'QUANTILE_INPUT')
    order = np.argsort(x, kind='stable')
    cumulative = np.cumsum(w[order] / math.fsum(w), dtype=np.float64)
    cumulative[-1] = 1.0
    return float(x[order[min(int(np.searchsorted(cumulative, probability, side='left')), len(x)-1)]])


def _statistics(rows, scores):
    require(len(rows) == len(scores), 'SCORE_LENGTH')
    score = np.asarray(scores, dtype=np.float64)
    require(np.isfinite(score).all(), 'NONFINITE_SCORE')
    normal = [i for i, r in enumerate(rows) if r['label'] == 0]
    attack = [i for i, r in enumerate(rows) if r['label'] == 1]
    require(normal and attack, 'SOURCE_TASK_NOT_EVALUABLE')
    wn = hierarchical_weights([rows[i] for i in normal])
    wa = hierarchical_weights([rows[i] for i in attack])
    t = weighted_quantile(score[normal], wn, .99)
    w = np.zeros(len(rows), dtype=np.float64)
    w[normal], w[attack] = .5 * wn, .5 * wa
    s = weighted_quantile(score, w, .9) - weighted_quantile(score, w, .1)
    require(s >= 0, 'NEGATIVE_SCALE')
    return {'t': t, 's': float(s), 'degenerate_scale': bool(s == 0),
            'normal_count': len(normal), 'attack_count': len(attack)}


def fit_statistics(rows, scores, folds=None):
    """Full FIT deployment t/s and complementary FIT estimates for F0/F1."""
    _fit_rows(rows)
    score = np.asarray(scores, dtype=np.float64)
    result = {'full': _statistics(rows, score)}
    if folds is None:
        folds = dependency_folds(rows)
    require(set(folds) == {r['uid'] for r in rows}, 'FOLD_UIDS')
    for fold in ('F0', 'F1'):
        indices = [i for i, r in enumerate(rows) if folds[r['uid']]['fold'] != fold]
        result[fold] = _statistics([rows[i] for i in indices], score[indices])
    return result


def _eligible(tasks):
    require(len({(t['view'], t['uid']) for t in tasks}) == len(tasks), 'DUPLICATE_TASK')
    return [t for t in tasks if t.get('eligible', True)]


def coverage_precheck(tasks):
    """Metadata-only source gate; donor candidates never count as own-bank attacks."""
    tasks = _eligible(tasks)
    normal = {t['device'] for t in tasks if t['label'] == 0 and
              t.get('own_eligible', t.get('own_bank', True))}
    attack = {t['device'] for t in tasks if t['label'] == 1 and
              t.get('own_eligible', t.get('own_bank', False))}
    return {'status': 'READY' if len(normal) >= 2 and len(attack) >= 2 else 'NOT_EVALUABLE',
            'normal_devices': sorted(normal), 'attack_own_bank_devices': sorted(attack)}


def residual_signal(tasks):
    """Auxiliary view must contain residual-positive normals on two devices."""
    eligible = _eligible(tasks)
    by_view = {}
    for view, aliases in (('formal', (0, 'formal')), ('auxiliary', (1, 'auxiliary'))):
        subset = [t for t in eligible if t['view'] in aliases and t['label'] == 0]
        positive = [t for t in subset if t.get('own_eligible', t.get('own_bank', True)) and
                    t['s'] > 0 and t['score'] > t['t']]
        mass = 0.0
        hard_mass = 0.0
        if subset:
            weights = hierarchical_weights(subset)
            ids = {(t['view'], t['uid']) for t in positive}
            mass = float(math.fsum(float(w) for t, w in zip(subset, weights)
                                   if (t['view'], t['uid']) in ids))
            hard_mass = float(math.fsum(float(w) for t, w in zip(subset, weights)
                                        if t.get('hard') and (t['view'], t['uid']) in ids))
        hard_rows = [t for t in subset if t.get('hard')]
        hard_positive = [t for t in positive if t.get('hard')]
        hard_conditional = 0.0
        if hard_rows:
            hard_ids = {(t['view'], t['uid']) for t in hard_positive}
            hard_conditional = float(math.fsum(float(w) for t, w in
                zip(hard_rows, hierarchical_weights(hard_rows))
                if (t['view'], t['uid']) in hard_ids))
        by_view[view] = {'count': len(positive), 'devices': sorted({t['device'] for t in positive}),
                         'protocols': sorted({t['protocol'] for t in positive}),
                         'components': len({t['component_id'] for t in positive}), 'weight_mass': mass,
                         'hard_count': len(hard_positive),
                         'hard': {'task_count': len(hard_rows), 'positive_count': len(hard_positive),
                                  'positive_weight_mass_in_full_class': hard_mass,
                                  'positive_weight_mass_within_hard': hard_conditional,
                                  'devices': sorted({t['device'] for t in hard_positive}),
                                  'protocols': sorted({t['protocol'] for t in hard_positive}),
                                  'components': len({t['component_id'] for t in hard_positive})}}
    status = 'READY' if len(by_view['auxiliary']['devices']) >= 2 else 'SOURCE_SIGNAL_INSUFFICIENT'
    return {'status': status, 'views': by_view}


def mine_hard_tasks(tasks):
    """Top weighted 20% per view/fold/device/protocol/class, stable UID ties."""
    eligible = _eligible(tasks)
    groups = defaultdict(list)
    for task in eligible:
        require(task['label'] in (0, 1), 'TASK_LABEL')
        key = (task['view'], task['fold'], task['device'], task['protocol'], task['label'])
        groups[key].append(task)
    selected = set()
    receipt = []
    for key in sorted(groups):
        rows = groups[key]
        viable = [r for r in rows if r['s'] > 0]
        if not viable:
            for row in rows:
                row['hard_difficulty'] = None
                row['hard_worst_bank_key'] = None
            receipt.append({'group': key, 'status': 'DEGENERATE_SCALE', 'count': 0, 'mass': 0.0})
            continue
        weights = hierarchical_weights(viable)
        def difficulty(row):
            m = (row['score'] - row['t']) / row['s']
            if row['label'] == 0:
                row['hard_worst_bank_key'] = None
                return m
            banks = row.get('banks', [])
            require(bool(banks), 'ATTACK_BANKS_REQUIRED')
            ranked_banks = sorted(banks, key=lambda b: b.get('bank_key', ()))
            worst = max(ranked_banks, key=lambda b: (1.0 - b['d2']) * math.exp(-abs(m)))
            row['hard_worst_bank_key'] = worst.get('bank_key')
            return (1.0 - worst['d2']) * math.exp(-abs(m))
        for row in viable:
            row['hard_difficulty'] = float(difficulty(row))
        ranked = sorted(zip(viable, weights),
                        key=lambda pair: (-pair[0]['hard_difficulty'], pair[0]['uid']))
        mass = 0.0
        for task, weight in ranked:
            selected.add((task['view'], task['uid']))
            mass += float(weight)
            if mass >= .20:
                break
        receipt.append({'group': key, 'status': 'READY', 'count': sum((r['view'], r['uid']) in selected for r in rows),
                        'mass': mass, 'boundary_uid': task['uid'],
                        'boundary_difficulty': task['hard_difficulty']})
    return selected, receipt


def build_task_distribution(tasks, hard_uids=None):
    """P0/PH over sorted (view, UID), preserving view and class mass."""
    ordered = sorted(_eligible(tasks), key=lambda t: (0 if t['view'] in (0, 'formal') else 1, t['uid']))
    require(all(t['view'] in (0, 1, 'formal', 'auxiliary') for t in ordered), 'TASK_VIEW')
    hard = set() if hard_uids is None else set(hard_uids)
    p0, ph = np.zeros(len(ordered), np.float64), np.zeros(len(ordered), np.float64)
    for view in (0, 1):
        for label in (0, 1):
            aliases = (view, 'formal' if view == 0 else 'auxiliary')
            indices = [i for i, t in enumerate(ordered) if t['view'] in aliases and t['label'] == label]
            require(bool(indices), 'SOURCE_TASK_NOT_EVALUABLE')
            basic = hierarchical_weights([ordered[i] for i in indices])
            p0[indices] = .25 * basic
            h_indices = [i for i in indices if (ordered[i]['view'], ordered[i]['uid']) in hard]
            if h_indices:
                ph[indices] = .125 * basic
                ph[h_indices] += .125 * hierarchical_weights([ordered[i] for i in h_indices])
            else:
                ph[indices] = .25 * basic
    require(math.isclose(math.fsum(p0), 1, abs_tol=1e-12) and
            math.isclose(math.fsum(ph), 1, abs_tol=1e-12), 'SAMPLING_MASS')
    return ordered, p0, ph


def uniform_stream(steps=4000, batch_size=256):
    return np.random.Generator(np.random.PCG64(27)).random(steps * batch_size, dtype=np.float64)


def sample_indices(probabilities, uniforms):
    p = np.asarray(probabilities, np.float64)
    require(p.ndim == 1 and len(p) and np.isfinite(p).all() and np.all(p >= 0), 'SAMPLING_PROBABILITY')
    require(math.isclose(math.fsum(p), 1.0, abs_tol=1e-12), 'SAMPLING_MASS')
    cdf = np.cumsum(p, dtype=np.float64)
    cdf[-1] = 1.0
    u = np.asarray(uniforms, dtype=np.float64)
    require(np.isfinite(u).all() and np.all((u >= 0) & (u < 1)), 'UNIFORM_RANGE')
    return np.searchsorted(cdf, u, side='right')
