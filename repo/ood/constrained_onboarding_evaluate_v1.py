"""Paired onboarding evaluation with fixed full denominators and explicit gaps.

No fitting or target-dependent selection occurs here. Counts are query counts,
not independent trials; weighted rates preserve the supplied official weights.
"""
from collections import Counter, defaultdict
import math
import numpy as np

SEEDS = (27, 127, 227)
SUFFIXES = ('27', '127', '227', 'ensemble')
REQUIRED_POOLS = ('CIC_DEV', 'CIC_THREE_DEVICE_REGRESSION_CONSUMED', 'UNSW_DEV')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def validate_rows(rows):
    require(bool(rows) and len({r['uid'] for r in rows}) == len(rows), 'QUERY_UID_SET')
    for r in rows:
        require(r['label'] in (0, 1) and r['use'] != 'REFERENCE', 'QUERY_ROLE')
        require(type(r['label_metric_weight_denominator']) is int and
                r['label_metric_weight_denominator'] > 0, 'METRIC_WEIGHT')
        require(math.isfinite(r['timestamp']), 'QUERY_TIME')


def measure(rows, pred):
    """Same math.fsum and conditioning as the official legacy evaluator."""
    pred = np.asarray(pred)
    require(pred.dtype == np.bool_ and pred.shape == (len(rows),), 'DECISION_SHAPE')
    result = {}
    for label, name in ((0, 'normal'), (1, 'attack')):
        ix = [i for i, r in enumerate(rows) if r['label'] == label]
        if not ix:
            result[name] = dict(rows=0, positive=0, rate=None, weighted_rate=None)
            continue
        w = [1 / rows[i]['label_metric_weight_denominator'] for i in ix]
        positive = int(pred[ix].sum())
        result[name] = dict(rows=len(ix), positive=positive, rate=positive / len(ix),
                            weighted_rate=math.fsum(v * int(pred[i]) for i, v in zip(ix, w)) / math.fsum(w))
    return result


def paired(rows, head, full):
    y = np.asarray([r['label'] for r in rows])
    added = (y == 1) & head & ~full
    return dict(new_attack_misses=int(added.sum()),
                new_attack_miss_uids=[rows[int(i)]['uid'] for i in np.flatnonzero(added)],
                recovered_attacks=int(((y == 1) & ~head & full).sum()),
                normal_fixed=int(((y == 0) & head & ~full).sum()),
                normal_new_false_positives=int(((y == 0) & ~head & full).sum()))


def coverage(rows, head, eligible, support):
    y = np.asarray([r['label'] for r in rows])
    w = np.asarray([1 / r['label_metric_weight_denominator'] for r in rows], dtype=np.float64)
    out = {}
    masks = {'normal': y == 0, 'attack': y == 1,
             'head_false_positives': (y == 0) & head, 'head_true_positives': (y == 1) & head}
    for name, mask in masks.items():
        mass = math.fsum(w[mask]); n = int(mask.sum())
        out[name] = dict(rows=n, eligible_rows=int((mask & eligible).sum()),
                         raw_eligible_fraction=float((mask & eligible).sum() / n) if n else None,
                         weighted_eligible_fraction=math.fsum(w[mask & eligible]) / mass if mass else None,
                         weighted_positive_support_fraction=math.fsum(w[mask & (support > 0)]) / mass if mass else None)
    return out


def _subset(rows, head, full, ix):
    rr = [rows[int(i)] for i in ix]
    return dict(rows=len(ix), head=measure(rr, head[ix]), full=measure(rr, full[ix]),
                paired=paired(rr, head[ix], full[ix]),
                attack_evidence='PRESENT' if any(r['label'] == 1 for r in rr) else 'NOT_EVALUABLE')


def paired_report(rows, head_logits, full_logits, cuts, ensemble_cut, trace, pool, *, late_cutoff=None):
    """N x 3 logits in seed order 27,127,227; includes all input UIDs."""
    validate_rows(rows)
    h, f = np.asarray(head_logits), np.asarray(full_logits)
    require(h.shape == f.shape == (len(rows), 3) and np.isfinite(h).all() and np.isfinite(f).all(), 'LOGIT_SCHEMA')
    h, f = h.astype(np.float64), f.astype(np.float64)
    require(np.all(f <= h), 'ONBOARDING_MUST_NOT_INCREASE_SCORE')
    cut = np.asarray(cuts, dtype=np.float64)
    require(cut.shape == (3,) and np.isfinite(cut).all() and math.isfinite(ensemble_cut), 'CUT_SCHEMA')
    # Identical arithmetic to np.stack(seed-vectors).mean(0,dtype=float64).
    hh = np.column_stack((h, np.stack([h[:, j] for j in range(3)]).mean(0, dtype=np.float64)))
    ff = np.column_stack((f, np.stack([f[:, j] for j in range(3)]).mean(0, dtype=np.float64)))
    thresholds = np.r_[cut, ensemble_cut]
    before, after = hh > thresholds, ff > thresholds
    support = np.asarray(trace['support'], dtype=np.float64)
    eligible = np.asarray(trace['eligible'])
    same = np.asarray(trace['same_component'])
    require(support.shape == eligible.shape == same.shape == (len(rows),), 'TRACE_SHAPE')
    require(eligible.dtype == same.dtype == np.bool_ and np.isfinite(support).all() and
            np.all((support >= 0) & (support <= 1)) and np.all(support[~eligible] == 0), 'TRACE_VALIDITY')
    require(np.array_equal(h[support == 0], f[support == 0]), 'NO_SUPPORT_MUST_BE_EXACT_NOOP')
    groups = {}
    for fields in (('device',), ('device', 'protocol'), ('device', 'activity'),
                   ('device', 'capture_id'), ('device', 'annotation_id'), ('device', 'attack_rate')):
        buckets = defaultdict(list)
        for i, r in enumerate(rows):
            buckets[tuple(str(r.get(k, 'NOT_AVAILABLE')) for k in fields)].append(i)
        groups['/'.join(fields)] = [(dict(zip(fields, key)), np.asarray(ix, dtype=np.int64))
                                    for key, ix in sorted(buckets.items())]
    report = {}
    for j, suffix in enumerate(SUFFIXES):
        b, a = before[:, j], after[:, j]
        metric = dict(head=measure(rows, b), full=measure(rows, a), paired=paired(rows, b, a),
                      coverage=coverage(rows, b, eligible, support), groups={})
        b_fpr = metric['head']['normal']['weighted_rate']; a_fpr = metric['full']['normal']['weighted_rate']
        metric['module_gain'] = dict(weighted_fpr_difference=b_fpr-a_fpr if b_fpr is not None else None,
                                    relative_reduction=1-a_fpr/b_fpr if b_fpr else None,
                                    positive_gain=bool(b_fpr is not None and a_fpr < b_fpr))
        for name, entries in groups.items():
            metric['groups'][name] = [dict(group=key, **_subset(rows, b, a, ix)) for key, ix in entries]
            if name == 'device':
                for item, (_, ix) in zip(metric['groups'][name], entries):
                    item['coverage'] = coverage([rows[int(i)] for i in ix], b[ix], eligible[ix], support[ix])
        metric['reference_continuation'] = {
            name: _subset(rows, b, a, np.flatnonzero(mask))
            for name, mask in [('eligible_same_component', eligible & same),
                               ('eligible_distinct_component', eligible & ~same), ('fallback', ~eligible)]}
        if late_cutoff is not None:
            require(math.isfinite(late_cutoff), 'LATE_CUTOFF')
            late = np.asarray([r['timestamp'] > late_cutoff for r in rows])
            metric['after_2h_secondary'] = _subset(rows, b, a, np.flatnonzero(late))
            metric['early_retained_primary'] = _subset(rows, b, a, np.flatnonzero(~late))
            metric['after_2h_secondary']['weight_rule'] = 'original weights conditioned within each reported class; full primary unchanged'
        report[suffix] = metric
    return dict(pool=pool, query_rows=len(rows), reports=report,
                evidence='CONSUMED_DEVELOPMENT_ONLY', counts_are_independent_trials=False,
                fallback_reasons=dict(Counter(str(x) for x in trace.get('reason', [])))), before, after


def pool_gate(result):
    """Explicit PENDING for missing normal/attack evidence, never vacuous PASS."""
    pool = result['pool']; reports = result['reports']; why, missing = [], []
    ens = reports['ensemble']
    def check(value, limit, lower, name):
        if value is None:
            missing.append(name)
        elif value < limit if lower else value > limit:
            why.append(name)
    check(ens['full']['attack']['weighted_rate'], .99, True, 'POOL_ATTACK_99')
    check(ens['full']['normal']['weighted_rate'], .01, False, 'POOL_FPR_1')
    for g in ens['groups']['device']:
        device = g['group']['device']
        check(g['full']['attack']['weighted_rate'], .97, True, 'DEVICE_ATTACK_97:'+device)
        check(g['full']['normal']['weighted_rate'], .02, False, 'DEVICE_FPR_2:'+device)
    for suffix in SUFFIXES:
        r = reports[suffix]
        if r['paired']['new_attack_misses']:
            why.append('ADDED_ATTACK_MISSES:'+suffix)
        if suffix != 'ensemble':
            check(r['full']['attack']['weighted_rate'], .97, True, 'SEED_ATTACK_97:'+suffix)
    if pool == 'CIC_DEV':
        check(ens['full']['attack']['rate'], .9998608581258854-.001, True, 'HISTORICAL_Q_RAW_GUARD')
    return dict(status='FAIL' if why else 'PENDING' if missing else 'PASS', reasons=why,
                missing_evidence=missing, module_benefit=ens['module_gain']['positive_gain'],
                OLD_LEVEL_PRESERVED='REPORT_ONLY_NOT_EVALUATED')


def protocol_regressions(rows, baseline, candidate, pool):
    """Fixed source CAL activity/CIC protocol guard versus RECENT for all suffixes."""
    require(pool in ('CAL', 'CIC_DEV'), 'REGRESSION_POOL')
    validate_rows(rows)
    baseline, candidate = np.asarray(baseline), np.asarray(candidate)
    require(baseline.shape == candidate.shape == (len(rows), 4) and
            baseline.dtype == candidate.dtype == np.bool_, 'REGRESSION_DECISIONS')
    attack = [i for i, r in enumerate(rows) if r['label'] == 1]
    w = np.asarray([1/r['label_metric_weight_denominator'] for r in rows])
    if pool == 'CAL':
        from legacy_qref_data_v1 import class_weights
        require(all(r['partition'] == 'LEARN' and r.get('fit_role') == 'CAL' for r in rows), 'CAL_ROLE')
        if attack:
            w[attack] = class_weights([rows[i] for i in attack])
        groups = {name: [i for i in attack if rows[i]['activity'] == name] for name in ('TCP', 'UDP', 'Hydra')}
    else:
        groups = {str(proto): [i for i in attack if rows[i]['protocol'] == proto]
                  for proto in sorted({rows[i]['protocol'] for i in attack})}
    out = []
    for name, ix in groups.items():
        for j, suffix in enumerate(SUFFIXES):
            if not ix:
                out.append(dict(pool=pool, group=name, suffix=suffix, status='PENDING', rows=0))
                continue
            mass = math.fsum(w[ix])
            a = math.fsum(w[i]*int(baseline[i, j]) for i in ix)/mass
            b = math.fsum(w[i]*int(candidate[i, j]) for i in ix)/mass
            out.append(dict(pool=pool, group=name, suffix=suffix, rows=len(ix),
                            baseline_recall=a, candidate_recall=b, drop=a-b,
                            status='PASS' if a-b <= .001 else 'FAIL'))
    return out


def complete_system_gate(pool_results, regressions):
    gates = {pool: pool_gate(result) for pool, result in pool_results.items()}
    missing = [pool for pool in REQUIRED_POOLS if pool not in gates]
    required_source = {(name, suffix) for name in ('TCP', 'UDP', 'Hydra') for suffix in SUFFIXES}
    got_source = {(r['group'], r['suffix']) for r in regressions if r['pool'] == 'CAL'}
    if not required_source <= got_source:
        missing.append('SOURCE_CAL_PROTOCOL_GUARD')
    expected_cic = set()
    if 'CIC_DEV' in pool_results:
        for g in pool_results['CIC_DEV']['reports']['ensemble']['groups']['device/protocol']:
            if g['full']['attack']['rows']:
                expected_cic.add(g['group']['protocol'])
    actual_cic = {(r['group'], r['suffix']) for r in regressions if r['pool'] == 'CIC_DEV'}
    if not expected_cic or not {(p, s) for p in expected_cic for s in SUFFIXES} <= actual_cic:
        missing.append('CIC_PROTOCOL_GUARD')
    statuses = [g['status'] for g in gates.values()] + [r['status'] for r in regressions]
    status = 'FAIL' if 'FAIL' in statuses else 'PENDING' if missing or 'PENDING' in statuses else 'PASS'
    return dict(status=status, pools=gates, missing_evidence=missing, attack_group_protection=regressions,
                independent_confirmation='NOT_RUN', automatic_promotion=False,
                status_scope='Fixed development/regression gates only; not independent confirmation or proof of module benefit')
