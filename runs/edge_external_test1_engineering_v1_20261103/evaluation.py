"""Pre-registered external metrics. No fitting, I/O, or dataset selection.

This is an external reporting adapter, not a change to the frozen C5 core.
Only enumerated legal populations are accepted; exclusions belong in census.
"""
from collections import Counter, defaultdict
import math

import numpy as np

HEADS = ('27', '127', '227', 'ensemble')
NORMAL_FIELDS = ('device', 'capture_id', 'component_id')
ATTACK_FIELDS = ('device', 'scenario', 'component_id')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def class_weights(rows):
    """Equal mass per nonempty child; each observed label sums to one.

    Scenario is a known capture group, never a fabricated independent event.
    Weights are rebuilt separately for each declared view before conditioning
    group rates. They are deliberately not named A/B weights.
    """
    out = np.zeros(len(rows), dtype=np.float64)
    for label, fields in ((0, NORMAL_FIELDS), (1, ATTACK_FIELDS)):
        keys = {}
        branches, leaves = defaultdict(set), Counter()
        for i, row in enumerate(rows):
            require(row.get('label') in (0, 1), 'BINARY_TRUTH_REQUIRED')
            if row['label'] != label:
                continue
            require(all(row.get(f) not in (None, '') for f in fields), 'MISSING_WEIGHT_IDENTITY')
            key = tuple(str(row[f]) for f in fields)
            keys[i] = key
            leaves[key] += 1
            for depth, value in enumerate(key):
                branches[key[:depth]].add(value)
        for i, key in keys.items():
            out[i] = 1 / (leaves[key] * math.prod(len(branches[key[:d]]) for d in range(len(key))))
        if keys:
            require(math.isclose(math.fsum(out[list(keys)]), 1, abs_tol=1e-12), 'WEIGHT_MASS')
    return out


def measure(rows, prediction, weights):
    prediction, weights = np.asarray(prediction), np.asarray(weights)
    require(prediction.dtype == np.bool_ and prediction.shape == weights.shape == (len(rows),), 'METRIC_SHAPE')
    require(np.isfinite(weights).all() and (weights >= 0).all(), 'METRIC_WEIGHTS')
    result = {}
    for label, name in ((0, 'normal'), (1, 'attack_associated')):
        mask = np.asarray([r['label'] == label for r in rows], dtype=bool)
        n, pos = int(mask.sum()), int(prediction[mask].sum())
        mass = math.fsum(weights[mask])
        result[name] = dict(rows=n, alarm_count=pos, no_alarm_count=n-pos,
                           packet_alarm_rate=pos/n if n else None,
                           weight_mass=mass,
                           weighted_alarm_rate=math.fsum(weights[mask & prediction])/mass if mass else None)
    return result


def paired_safety(rows, raw, candidate, weights):
    """RAW-cumulative TP withdrawals; no external tuning on a failed gate."""
    raw, candidate, weights = np.asarray(raw), np.asarray(candidate), np.asarray(weights)
    require(raw.dtype == candidate.dtype == np.bool_ and raw.shape == candidate.shape == (len(rows),), 'SAFETY_SHAPE')
    require(not np.any(~raw & candidate), 'C5_CANNOT_ADD_RAW_ALARMS')
    groups = {}
    for field, budget in (('device', 1.0), ('scenario', 5.0)):
        entries = defaultdict(list)
        for i, row in enumerate(rows):
            if row['label'] == 1:
                require(row.get(field) not in (None, ''), 'MISSING_SAFETY_GROUP')
                entries[str(row[field])].append(i)
        for value, indices in sorted(entries.items()):
            ix = np.asarray(indices, dtype=np.int64)
            mass = math.fsum(weights[ix])
            require(mass > 0, 'ZERO_ATTACK_WEIGHT')
            before = math.fsum(weights[ix][raw[ix]]) / mass
            withdrawn = raw[ix] & ~candidate[ix]
            loss = 100 * math.fsum(weights[ix][withdrawn]) / mass
            failures = []
            if loss > budget:
                failures.append('WITHDRAWAL_BUDGET')
            if before < .99 and withdrawn.any():
                failures.append('LOW_RAW_RECALL_ANY_WITHDRAWAL')
            groups[field + ':' + value] = dict(rows=len(ix), raw_recall=before,
                withdrawals=int(withdrawn.sum()), weighted_loss_pp=loss,
                budget_pp=budget, status='FAIL' if failures else 'PASS', failures=failures)
    return dict(status=('NOT_EVALUABLE' if not groups else
                       'FAIL' if any(x['status'] == 'FAIL' for x in groups.values()) else 'PASS'),
                groups=groups,
                independent_official_event_gate='NOT_EVALUABLE_NO_EVENT_LEDGER')


def report_view(rows, predictions, raw, *, raw_uids, prediction_uids,
                independent_methods=(), c5_name='C5_P3'):
    """Four-head rates and loss gates on exactly the same ordered query UIDs.

    KNN is explicitly marked independent: a single distance score at four
    matched source workpoints, not four independently trained heads. It may add
    RAW-negative alarms and is not forced through a suppression-only gate.
    """
    uids = [r['uid'] for r in rows]
    require(len(uids) == len(set(uids)), 'DUPLICATE_QUERY_UID')
    require(list(raw_uids) == uids and set(prediction_uids) == set(predictions), 'BROKEN_RAW_UID_JOIN')
    require(all(list(prediction_uids[name]) == uids for name in predictions), 'BROKEN_PREDICTION_UID_JOIN')
    require(set(independent_methods) <= set(predictions) and c5_name not in independent_methods, 'METHOD_KIND')
    raw = np.asarray(raw)
    require(raw.dtype == np.bool_ and raw.shape == (len(rows), 4), 'RAW_HEADS')
    weights = class_weights(rows)
    out = {}
    for name, prediction in predictions.items():
        prediction = np.asarray(prediction)
        require(prediction.dtype == np.bool_ and prediction.shape == raw.shape, 'PREDICTION_HEADS')
        heads = {}
        for j, head in enumerate(HEADS):
            metric = measure(rows, prediction[:, j], weights)
            if name in independent_methods:
                attack = np.asarray([r['label'] == 1 for r in rows], dtype=bool)
                metric['safety'] = dict(status='DESCRIPTIVE_INDEPENDENT_DETECTOR',
                    withdrawn_RAW_TP=int(np.sum(attack & raw[:, j] & ~prediction[:, j])),
                    added_RAW_negative_alarms=int(np.sum(~raw[:, j] & prediction[:, j])),
                    suppression_only_gate_applies=False)
                metric['score_identity'] = 'One distance score at a matched source workpoint; not an independent trained head'
            else:
                metric['safety'] = paired_safety(rows, raw[:, j], prediction[:, j], weights)
            metric['descriptive_targets'] = dict(
                packet_FPR_le_2pct=(None if metric['normal']['rows'] == 0 else metric['normal']['packet_alarm_rate'] <= .02),
                packet_recall_ge_99pct=(None if metric['attack_associated']['rows'] == 0 else metric['attack_associated']['packet_alarm_rate'] >= .99))
            heads[head] = metric
        out[name] = heads
    require(c5_name in out, 'C5_RESULT_REQUIRED')
    return dict(rows=len(rows), methods=out,
        uncertainty='Finite captured-population descriptive rates; no independent-packet/Wilson CI. Report normal segments/days and two attack scenarios separately. No population-generalization interval is claimed.',
        external_weight_schema=dict(normal=NORMAL_FIELDS, attack=ATTACK_FIELDS),
        external_quality_used_for_selection=False)


def view_indices(rows, cutoff_ns, bank_capture_id, bank_end_frame):
    """Inclusive prefix is excluded from the primary view; bank never updated."""
    require(type(cutoff_ns) is int and type(bank_end_frame) is int, 'INTEGER_BOUNDARIES')
    primary = np.asarray([r['timestamp_ns'] > cutoff_ns and
        (r['capture_id'] != bank_capture_id or r['frame'] > bank_end_frame) for r in rows], dtype=bool)
    return dict(full=np.arange(len(rows), dtype=np.int64), post_window_primary=np.flatnonzero(primary))
