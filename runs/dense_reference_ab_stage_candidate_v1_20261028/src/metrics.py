"""Read-only metrics for the registered dense-reference matrix.

Full-population weights are preserved; the primary post-window population is
weighted again with the original pool-specific nonempty-branch hierarchy.
No thresholds, margins, references, or operating points are selected here.
"""
from collections import Counter, defaultdict
import math

import numpy as np

SUFFIXES = ('27', '127', '227', 'ensemble')
POOLS = ('CIC_DEV', 'UNSW_DEV', 'CIC_THREE_DEVICE_REGRESSION_CONSUMED')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def hierarchy_fields(pool, label):
    require(pool in POOLS and label in (0, 1), 'POOL_OR_LABEL')
    if pool == 'UNSW_DEV':
        return ('device', 'component_id') if label == 0 else ('device', 'annotation_id', 'component_id')
    return ('device', 'activity', 'capture_id', 'session_id')


def hierarchical_weights(rows, pool):
    """Each present class has mass one, using only branches in these rows."""
    out = np.zeros(len(rows), dtype=np.float64)
    for label in (0, 1):
        ix = [i for i, r in enumerate(rows) if r['label'] == label]
        if not ix:
            continue
        fields = hierarchy_fields(pool, label)
        branches, leaves = defaultdict(set), Counter()
        keys = {}
        for i in ix:
            r = rows[i]
            require(all(f in r and r[f] is not None for f in fields), 'WEIGHT_METADATA_REQUIRED')
            key = tuple(str(r[f]) for f in fields)
            keys[i] = key
            for d in range(len(fields)):
                branches[key[:d]].add(key[d])
            leaves[key] += 1
        for i, key in keys.items():
            out[i] = 1 / (leaves[key] * math.prod(len(branches[key[:d]]) for d in range(len(fields))))
        require(math.isclose(math.fsum(out[ix]), 1., abs_tol=1e-12), 'CLASS_WEIGHT_MASS')
    return out


def original_weights(rows):
    require(all(type(r.get('label_metric_weight_denominator')) is int and
                r['label_metric_weight_denominator'] > 0 for r in rows), 'ORIGINAL_WEIGHT_REQUIRED')
    return np.asarray([1 / r['label_metric_weight_denominator'] for r in rows], dtype=np.float64)


def validate_full_weights(rows, pool):
    old, rebuilt = original_weights(rows), hierarchical_weights(rows, pool)
    require(np.array_equal(old, rebuilt), 'FULL_HIERARCHY_DOES_NOT_REPRODUCE_OFFICIAL_WEIGHTS')
    return old


def post_window_mask(rows, windows):
    """Per-device original receipt cutoff; inclusive window is excluded.

    The original capture's bank_end_frame is checked in addition to timestamp.
    A missing window is never inferred from query.reference_end.
    """
    if isinstance(windows, list):
        converted = {}
        for w in windows:
            require(isinstance(w, dict) and 'device' in w and 'reference_end' in w, 'WINDOW_LIST_SCHEMA')
            old = converted.setdefault(w['device'], dict(cutoff=w['reference_end'], bank_end_frames={}))
            require(old['cutoff'] == w['reference_end'], 'DEVICE_WINDOW_END_MISMATCH')
            if 'frame_end' in w:
                old['bank_end_frames'][w['capture_id']] = w['frame_end']
        windows = converted
    require(isinstance(windows, dict) and windows, 'OBSERVATION_WINDOW_REQUIRED')
    out = []
    for r in rows:
        w = windows.get(r['device'], windows.get('*'))
        require(isinstance(w, dict) and math.isfinite(w.get('cutoff', float('nan'))), 'DEVICE_WINDOW_REQUIRED')
        after = r['timestamp'] > w['cutoff']
        frame_ends = w.get('bank_end_frames', {})
        if r['capture_id'] in frame_ends:
            after = after and r['frame'] > frame_ends[r['capture_id']]
        out.append(after)
    return np.asarray(out, dtype=bool)


def measure(rows, pred, weights):
    pred, weights = np.asarray(pred), np.asarray(weights)
    require(pred.dtype == np.bool_ and pred.shape == weights.shape == (len(rows),), 'MEASURE_SHAPE')
    require(np.isfinite(weights).all() and np.all(weights >= 0), 'MEASURE_WEIGHT')
    out = {}
    for label, name in ((0, 'normal'), (1, 'attack')):
        ix = np.asarray([i for i, r in enumerate(rows) if r['label'] == label], dtype=np.int64)
        mass = math.fsum(weights[ix])
        n, positive = len(ix), int(pred[ix].sum())
        out[name] = dict(rows=n, positive=positive, negative=n-positive,
                         rate=positive / n if n else None, weight_mass=mass,
                         weighted_rate=math.fsum(weights[ix][pred[ix]]) / mass if mass else None)
    return out


def _rate_loss(before, after):
    b, a = before['attack']['weighted_rate'], after['attack']['weighted_rate']
    return None if b is None or a is None else 100. * (b-a)


def _attack_loss(rows, before, after, weights):
    mask = np.asarray([r['label'] == 1 for r in rows], dtype=bool)
    mass = math.fsum(weights[mask])
    withdrawn = mask & before & ~after
    return None if mass == 0 else 100. * (math.fsum(weights[withdrawn]) / mass)


def _groups(rows, before, after, weights, fields):
    groups = defaultdict(list)
    for i, row in enumerate(rows):
        key = tuple(str(row.get(f, 'NOT_AVAILABLE')) for f in fields)
        groups[key].append(i)
    result = []
    for key, indices in sorted(groups.items()):
        ix = np.asarray(indices, dtype=np.int64)
        rr = [rows[i] for i in indices]
        b, a = measure(rr, before[ix], weights[ix]), measure(rr, after[ix], weights[ix])
        result.append(dict(group=dict(zip(fields, key)), base=b, corrected=a,
                           attack_recall_loss_pp=_attack_loss(rr, before[ix], after[ix], weights[ix])))
    return result


def report(rows, before, after, weights, eligible, support):
    """A single suffix/view. Group rates condition the same view weights."""
    before, after = np.asarray(before), np.asarray(after)
    eligible, support, weights = np.asarray(eligible), np.asarray(support), np.asarray(weights)
    n = len(rows)
    require(before.dtype == after.dtype == eligible.dtype == np.bool_ and
            before.shape == after.shape == eligible.shape == support.shape == weights.shape == (n,), 'REPORT_SHAPE')
    require(np.isfinite(support).all() and np.all((support >= 0) & (support <= 1)) and
            np.all(support[~eligible] == 0), 'REPORT_SUPPORT')
    require(not np.any(~before & after), 'CORRECTION_CANNOT_ADD_ALARMS')
    base, corrected = measure(rows, before, weights), measure(rows, after, weights)
    normal = np.asarray([r['label'] == 0 for r in rows], dtype=bool)
    added = ~normal & before & ~after
    fixed = normal & before & ~after
    coverage = {}
    for label, name in ((0, 'normal'), (1, 'attack')):
        mask = normal if label == 0 else ~normal
        count, mass = int(mask.sum()), math.fsum(weights[mask])
        coverage[name] = dict(rows=count, eligible_rows=int((mask & eligible).sum()),
            positive_support_rows=int((mask & (support > 0)).sum()),
            eligible_weight_fraction=math.fsum(weights[mask & eligible]) / mass if mass else None,
            positive_support_weight_fraction=math.fsum(weights[mask & (support > 0)]) / mass if mass else None)
    b, a = base['normal']['weighted_rate'], corrected['normal']['weighted_rate']
    return dict(base=base, corrected=corrected, attack_recall_loss_pp=_attack_loss(rows, before, after, weights),
                fpr_reduction_pp=None if b is None or a is None else 100. * (b-a),
                normal_fixed=int(fixed.sum()), added_attack_misses=int(added.sum()),
                added_attack_miss_uids=[rows[i]['uid'] for i in np.flatnonzero(added)],
                coverage=coverage,
                groups={'device': _groups(rows, before, after, weights, ('device',)),
                        'attack_type': _groups(rows, before, after, weights, ('activity',)),
                        'annotation': _groups(rows, before, after, weights, ('annotation_id',)),
                        'device/annotation': _groups(rows, before, after, weights, ('device', 'annotation_id')),
                        'device/protocol': _groups(rows, before, after, weights, ('device', 'protocol'))})


def attack_gate(metric, epsilon_pp):
    """All declared budgets apply; a pool average cannot hide local failure."""
    failures, missing = [], []
    recall = metric['corrected']['attack']['weighted_rate']
    loss = metric['attack_recall_loss_pp']
    if recall is None:
        missing.append('POOL_ATTACK')
    elif recall < .99:
        failures.append('POOL_ATTACK_RECALL_BELOW_99')
    if loss is not None and loss > epsilon_pp:
        failures.append('POOL_ATTACK_LOSS_EXCEEDS_EPSILON')
    for kind, budget in (('device', 1.), ('attack_type', 5.), ('annotation', 5.)):
        for item in metric['groups'][kind]:
            loss = item['attack_recall_loss_pp']
            if loss is not None and loss > budget:
                failures.append(kind.upper() + '_ATTACK_LOSS:' + '|'.join(item['group'].values()))
    return dict(status='FAIL' if failures else 'NOT_EVALUABLE' if missing else 'PASS',
                failures=failures, missing=missing, epsilon_pp=epsilon_pp,
                absolute_recall_floor=.99, device_loss_budget_pp=1., annotation_loss_budget_pp=5.)


def target_gate(metric, epsilon_pp):
    attack = attack_gate(metric, epsilon_pp)
    failures, missing = list(attack['failures']), list(attack['missing'])
    rate = metric['corrected']['normal']['weighted_rate']
    if rate is None:
        missing.append('POOL_NORMAL')
    elif rate > .01:
        failures.append('POOL_FPR_ABOVE_1')
    for item in metric['groups']['device']:
        rate = item['corrected']['normal']['weighted_rate']
        if rate is not None and rate > .02:
            failures.append('DEVICE_FPR_ABOVE_2:' + item['group']['device'])
    return dict(status='FAIL' if failures else 'NOT_EVALUABLE' if missing else 'PASS',
                failures=failures, missing=missing, attack=attack)


def paired_own_wrong(rows, own, wrong, weights, own_eligible, wrong_eligible):
    """Compare on identical common-eligible rows, never head-fallback mixtures."""
    common = np.asarray(own_eligible) & np.asarray(wrong_eligible)
    ix = np.flatnonzero(common)
    subset = [rows[i] for i in ix]
    coverage = {}
    for label, name in ((0, 'normal'), (1, 'attack')):
        mask = np.asarray([r['label'] == label for r in rows], dtype=bool)
        total = math.fsum(weights[mask])
        coverage[name] = dict(total_rows=int(mask.sum()), paired_rows=int((mask & common).sum()),
                              paired_weight_mass=math.fsum(weights[mask & common]),
                              weight_coverage=math.fsum(weights[mask & common]) / total if total else None)
    return dict(status='PAIRED_COMMON_ELIGIBLE' if len(ix) else 'NOT_EVALUABLE',
                denominator='same common eligible query UIDs; condition existing view weights',
                rows=len(ix), uid_sha256=__import__('hashlib').sha256(
                    ('\n'.join(r['uid'] for r in subset)+'\n').encode()).hexdigest(),
                coverage=coverage, own=measure(subset, np.asarray(own)[ix], weights[ix]),
                wrong=measure(subset, np.asarray(wrong)[ix], weights[ix]))
