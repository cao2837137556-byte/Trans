"""Frozen query admission, baseline parity and paired reports."""
import numpy as np

from common_round1 import (HEADS, POOL, TOL, artifact, dump, load, read_rows, require,
                           table, temp_path, uid_sha, write_rows)
from reference_inputs import normalized_context, uids
from vendor import analysis_core as production_metrics
from vendor import p4_worker as producer

BASELINE = ('RAW', 'P4_COMMISSION_3D', 'P4_MAIN')
LABELS = ('NORMAL', 'ATTACK')
CATEGORIES = ('REFERENCE_NOT_OPEN', 'NO_LEGAL_REFERENCE', 'ONE_LEGAL_COMPONENT',
              'GEOMETRY_UNAVAILABLE', 'ZERO_JOINT_SUPPORT_2D',
              'ZERO_JOINT_SUPPORT_3D_ONLY', 'GUARD_PREVENTED_WITHDRAWAL', 'DEDUCTION_INSUFFICIENT')


def correction(d, support, method, guard=True):
    return producer.correct(d['raw'], support, d['q'], method['scales'], guard, power=method['p'])


def assert_array(a, b, name):
    require(np.array_equal(a, b), name)


def load_queries(store, config, assets):
    rows = read_rows(store.get('query_rows'))
    original = read_rows(store.get('prepared_rows'))
    ids = np.asarray(uids(rows))
    require(len(ids) == len(set(ids)) == config['query_identity']['rows'] and
            uid_sha(ids.tolist()) == config['query_identity']['uid_sha256'], 'QUERY_UID_ORDER')
    require(len(original) == len(rows) and all(all(row.get(k) == v for k, v in base.items())
            for row, base in zip(rows, original)), 'QUERY_METADATA_ROLE_OR_ORDER_DRIFT')
    del original
    with np.load(store.get('query_context_uids'), allow_pickle=False) as z:
        assert_array(ids, z['uid'].astype('U64'), 'QUERY_CONTEXT_UIDS')
    z = np.load(store.get('query_e3'), mmap_mode='r', allow_pickle=False)[:, :768]
    q = np.load(store.get('query_q'), mmap_mode='r', allow_pickle=False)
    context = np.load(store.get('query_context'), mmap_mode='r', allow_pickle=False)
    require(z.shape == (len(ids), 768) and q.shape == (len(ids), 14) and context.shape == (len(ids), 8),
            'QUERY_FEATURE_SHAPE')
    q = np.asarray(q)
    context = normalized_context(context, assets.context_norm)
    with np.load(store.get('query_arrays'), allow_pickle=False) as a:
        assert_array(ids, a['uid'], 'CONTROLS_QUERY_ARRAY_UID')
        assert_array(q, a['q'], 'Q14_SAVED_ARRAY_MISMATCH')
        require('expansion' not in a.files and config['views'] == ['full', 'post_window_primary'],
                'UNSW_WEIGHTING_SCOPE')
        views = {name: (a[name + '_ix'], a[name + '_weight']) for name in config['views']}
        full_support3 = a['support3']
    require(all(len(w) == len(ids) and np.isfinite(w).all() and (w >= 0).all() and
                (w[ix] > 0).all() for ix, w in views.values()), 'QUERY_WEIGHT_SCHEMA')
    with np.load(store.get('query_view_witness'), allow_pickle=False) as a:
        assert_array(ids, a['uid'], 'REPLAY_WEIGHT_UID_ORDER')
        assert_array(views['full'][0], np.arange(len(ids)), 'FULL_VIEW_INDICES')
        assert_array(views['full'][1], a['full_weights'], 'FULL_VIEW_WEIGHTS')
        ii, w = views['post_window_primary']
        assert_array(ii, a['primary_indices'], 'PRIMARY_VIEW_INDICES')
        assert_array(w[ii], a['primary_weights'], 'PRIMARY_VIEW_WEIGHTS')
        require(np.count_nonzero(w) == len(ii), 'PRIMARY_WEIGHTS_OUTSIDE_VIEW')
    primary = [i for i, r in enumerate(rows)
               if r['timestamp'] > assets.dense_bank.ends[(r['partition'], r['device'])] and
               r['frame'] > assets.dense_bank.frame_ends.get((r['partition'], r['device'], r['capture_id']), -1)]
    assert_array(primary, views['post_window_primary'][0], 'PRIMARY_WINDOW_POLICY')
    with np.load(store.get('accepted_scores'), allow_pickle=False) as a:
        assert_array(ids, a['uid'], 'P4_SCORE_UID_ORDER')
        scores = {name: a[name] for name in BASELINE}
    raw = scores['RAW']
    with np.load(store.get('source_raw_scores'), allow_pickle=False) as a:
        assert_array(ids, a['uid'], 'SOURCE_RAW_UID_ORDER')
        assert_array(raw, a['FUSION790_RAW'], 'SOURCE_RAW_SCORES')
    require(raw.dtype == np.float64 and raw.shape == (len(ids), 4) and
            np.isfinite(raw).all(), 'RAW_SCORE_SCHEMA')
    assert_array(raw, producer.four(raw[:, :3]), 'RAW_ENSEMBLE_ORDER')
    saved = {}
    for name, pin in [('P4_MAIN', 'full_geometry'), ('P4_COMMISSION_3D', 'dense_geometry')]:
        with np.load(store.get(pin), allow_pickle=False) as a:
            assert_array(ids, a['uid'], 'GEOMETRY_UID_ORDER:' + name)
            assert_array(raw, a['RAW'], 'RAW_GEOMETRY_WITNESS:' + name)
            saved[name] = {key: a[key] for key in ['support2', 'support3']}
        support2, support3 = (saved[name][key] for key in ['support2', 'support3'])
        require(support2.shape == support3.shape == (len(ids),) and support2.dtype == support3.dtype == np.float64
                and np.all((support2 >= 0) & (support2 <= 1)) and
                np.all((support3 >= 0) & (support3 <= 1)) and np.all(support3 <= support2 + TOL),
                'GEOMETRY_SCHEMA:' + name)
    assert_array(saved['P4_MAIN']['support3'], full_support3, 'FULL_TRUE_SUPPORT3')
    labels = np.array([r['label'] for r in rows])
    require(set(labels) == {0, 1} and all(r['use'] != 'REFERENCE' for r in rows) and
            int((labels == 0).sum()) == 75763 and
            int((labels[views['post_window_primary'][0]] == 0).sum()) == 74444 and
            int((labels == 1).sum()) == 72553, 'FROZEN_QUERY_COUNTS')
    d = dict(ids=ids, rows=rows, z=z, q=q, context=context, views=views, raw=raw,
             scores=scores, saved=saved, labels=labels)
    require(production_metrics.guard(q)[labels == 1].all(), 'UNSW_ATTACK_GUARD_CONTRACT')
    return d


def subset(d, ix):
    ix = np.asarray(ix)
    new = {key: d[key][ix] for key in ('ids', 'z', 'q', 'context', 'raw', 'labels')}
    new['rows'] = [d['rows'][i] for i in ix]
    new['views'] = {}
    for name, (selected, w) in d['views'].items():
        include = np.isin(ix, selected)
        new['views'][name] = (np.flatnonzero(include), w[ix])
    new['scores'] = {k: v[ix] for k, v in d['scores'].items()}
    new['saved'] = {k: {name: a[ix] for name, a in fields.items()} for k, fields in d['saved'].items()}
    return new


def diagnostics_groups(rows):
    labels = np.array([r['label'] for r in rows])
    device = np.array([r['device'] for r in rows])
    protocols = np.array([r['protocol'] for r in rows])
    groups = production_metrics.groups(rows)
    for proto in (6, 17):
        for value, label in enumerate(LABELS):
            p = (protocols == proto) & (labels == value)
            groups[f'protocol:{proto} / {label}'] = p
            for dev in sorted(set(device)):
                groups[f'device:{dev} / protocol:{proto} / {label}'] = p & (device == dev)
    return {name: mask for name, mask in groups.items() if mask.any()}


def evaluation_rows(d, a, b=None, *, eligibility=None):
    """Same aggregation and weights as the accepted controls, with protocol breakdowns."""
    groups = diagnostics_groups(d['rows'])
    if eligibility is not None:
        grouped = {}
        for name, flag in eligibility.items():
            for group, mask in groups.items():
                if group in LABELS or 'protocol:' in group or group.startswith('device:'):
                    grouped[f'{name} / {group}'] = mask & flag
        groups.update(grouped)
    guard = production_metrics.guard(d['q'])
    guard_groups = {'ALL': np.ones(len(guard), dtype=bool), 'GUARD_ON': guard, 'GUARD_OFF': ~guard}
    out = []
    for view, (ix, weight) in d['views'].items():
        for group, mask in groups.items():
            for stratum, g in guard_groups.items():
                ii = ix[mask[ix] & g[ix]]
                if not len(ii):
                    continue
                w = weight[ii]
                den = float(w.sum())
                require(den > 0, 'NONPOSITIVE_EVALUATION_WEIGHT')
                for j, head in enumerate(HEADS):
                    x = a[ii, j]
                    row = dict(pool=POOL, view=view, head=head, group=group, guard_stratum=stratum,
                               rows=len(ii), weighted_denominator=den)
                    if b is None:
                        num = float(w[x].sum())
                        row.update(alarm_count=int(x.sum()), sample_rate=float(x.mean()),
                                   weighted_numerator=num, hierarchical_rate=num / den)
                    else:
                        y = b[ii, j]
                        for av, bv in [(False, False), (False, True), (True, False), (True, True)]:
                            flag = (x == av) & (y == bv)
                            name = f'n{int(av)}{int(bv)}'
                            row[name], row['weighted_' + name] = int(flag.sum()), float(w[flag].sum())
                        require(sum(row[k] for k in ('n00', 'n01', 'n10', 'n11')) == len(ii),
                                'PAIRED_COUNT_CONSERVATION')
                    out.append(row)
    return out


def metric_key(r):
    return tuple(r[k] for k in ('pool', 'view', 'head', 'group', 'guard_stratum'))


def compare_tables(actual, expected, extra_groups=False):
    lookup = {metric_key(row): row for row in actual}
    require(len(lookup) == len(actual), 'DUPLICATE_METRIC_KEY')
    expected_keys = {metric_key(row) for row in expected}
    require(len(expected_keys) == len(expected) > 0 and expected_keys <= set(lookup) and
            (extra_groups or expected_keys == set(lookup)), 'FROZEN_METRIC_COVERAGE')
    for row in expected:
        a = lookup[metric_key(row)]
        for k in ('rows', 'alarm_count', 'sample_rate', 'weighted_denominator', 'weighted_numerator',
                  'hierarchical_rate', 'n00', 'n01', 'n10', 'n11',
                  'weighted_n00', 'weighted_n01', 'weighted_n10', 'weighted_n11'):
            if k in row:
                require(abs(a[k] - row[k]) <= TOL, f'METRIC_PARITY:{k}:{metric_key(row)}')
    return len(expected)


def parity(a, b, ids, limit=TOL):
    require(a.shape == b.shape and a.shape[0] == len(ids), 'PARITY_SHAPE')
    aa, bb = np.isfinite(a), np.isfinite(b)
    pattern = bool(np.array_equal(aa, bb) and np.array_equal(np.isnan(a), np.isnan(b)) and
                   np.array_equal(np.isposinf(a), np.isposinf(b)) and np.array_equal(np.isneginf(a), np.isneginf(b)))
    valid = aa & bb
    diff = np.zeros_like(a, dtype=np.float64)
    diff[valid] = np.abs(a[valid] - b[valid])
    changed = diff > 0
    above = diff > limit
    row_flag = above if a.ndim == 1 else above.any(axis=1)
    return dict(max_abs_error=float(diff.max(initial=0)), finite_values=int(valid.sum()),
                nonfinite_left=int((~aa).sum()), nonfinite_right=int((~bb).sum()),
                nonfinite_pattern_exact=pattern, changed_values=int(changed.sum()),
                above_tolerance_values=int(above.sum()), above_tolerance_uid_count=int(row_flag.sum()),
                examples=ids[row_flag][:12].tolist())


def baseline(d, full_expected_metrics, full_expected_pairs, config, *, real_slice=False, output=None):
    cuts = config['method']['cuts']
    baseline_scores = {'RAW': d['raw']}
    report = {}
    for name in BASELINE[1:]:
        score = correction(d, d['saved'][name]['support3'], config['method'])
        err = parity(score, d['scores'][name], d['ids'])
        differences = int(np.count_nonzero((score > cuts) != (d['scores'][name] > cuts)))
        require(err['nonfinite_left'] == 0 and err['above_tolerance_values'] == differences == 0,
                'BASELINE_SCORE_OR_DECISION_PARITY:' + name)
        baseline_scores[name] = score
        report[name] = dict(score=err, decision_differences=differences)
    metrics = []
    for name, values in baseline_scores.items():
        pred = values > cuts
        frozen = d['scores'][name] > cuts
        require(not np.any(pred & ~(d['raw'] > cuts)), 'CORRECTION_ADDED_RAW_ALARMS')
        actual = evaluation_rows(d, pred)
        expected = (production_metrics.metrics(POOL, d['rows'], frozen, d['views'], d['q']) if real_slice else
                    [r for r in full_expected_metrics if r['pool'] == POOL and r['config'] == name])
        n = compare_tables(actual, expected, extra_groups=True)
        report.setdefault(name, {})['verified_metric_rows'] = n
        metrics.extend(dict(config=name, **r) for r in actual)
    if not real_slice:
        pairs = []
        for left, right in [('RAW', 'P4_MAIN'), ('P4_MAIN', 'P4_COMMISSION_3D')]:
            actual = evaluation_rows(d, baseline_scores[left] > cuts, baseline_scores[right] > cuts)
            compare_tables(actual,
                           [r for r in full_expected_pairs if r['pool'] == POOL and
                            r['left'] == left and r['right'] == right], extra_groups=True)
            pairs.extend(dict(left=left, right=right, **r) for r in actual)
        if output is not None:
            table(output, 'BASELINE_METRICS', metrics)
            table(output, 'BASELINE_PAIRED_CHANGES', pairs)
    return dict(status='PASS', rows=len(d['rows']), heads=list(HEADS), views=list(d['views']),
                check=report, weights_bound=True, query_uid_order=True,
                frozen_external_metrics_compared=not real_slice,
                both_archived_pair_tables_compared=not real_slice)


def diagnosis(d, geo, config, out):
    method = config['method']
    cuts = np.asarray(method['cuts'])
    comm = d['scores']['P4_COMMISSION_3D']
    no_guard = correction(d, geo['support3'], method, guard=False)
    raw_margin = d['raw'] - cuts
    scales = np.asarray(method['scales'])
    limit = .25 * np.r_[scales, scales.mean(dtype=np.float64)]
    beyond = raw_margin > limit
    guard = production_metrics.guard(d['q'])
    fp = (comm > cuts) & (d['labels'] == 0)[:, None]
    categories = np.full(fp.shape, -1, dtype=np.int8)
    n = len(d['rows'])
    comp, ready = geo['legal_component_count'], geo['geometry_ready']
    rules = (geo['opening'] != '', comp == 0, comp == 1, ~ready,
             (geo['support3'] == 0) & (geo['support2'] == 0),
             (geo['support3'] == 0) & (geo['support2'] > 0))
    for i, rule in enumerate(rules):
        categories[fp & (categories < 0) & rule[:, None]] = i
    blocked = (geo['support3'] > 0)[:, None] & guard[:, None] & (no_guard <= cuts)
    categories[fp & (categories < 0) & blocked] = 6
    categories[fp & (categories < 0)] = 7
    require(np.all((categories[fp] >= 0) & (categories[fp] < len(CATEGORIES))) and
            np.all((categories != 7) | (geo['support3'] > 0)[:, None]), 'D_EXCLUSIVE_PARTITION')
    fallback_test = fp & (categories == 2) & ready[:, None]
    positive = fallback_test & (geo['single'] > 0)[:, None]
    single_scores = correction(d, geo['single'], method)
    repair = positive & (single_scores <= cuts)
    require(not np.any(repair & guard[:, None]), 'D_SINGLE_COMPONENT_GUARD')
    groups = {name: mask for name, mask in diagnostics_groups(d['rows']).items()
              if name == 'NORMAL' or (name.endswith(' / NORMAL') and
                                     ('protocol:' in name or name.startswith('device:')))}
    groups['ALL_QUERIES'] = np.ones(n, dtype=bool)
    groups['ATTACK'] = d['labels'] == 1
    records = []
    for view, (ix, w) in d['views'].items():
        for group, mask in groups.items():
            rows = ix[mask[ix]]
            if not len(rows):
                continue
            for j, head in enumerate(HEADS):
                residual = rows[fp[rows, j]]
                one = rows[fallback_test[rows, j]]
                total_fp = len(residual)
                residual_mass = float(w[residual].sum())
                one_mass = float(w[one].sum())
                query_mass = float(w[rows].sum())
                for k, name in enumerate(CATEGORIES):
                    ii = residual[categories[residual, j] == k]
                    mass = float(w[ii].sum())
                    records.append(dict(view=view, head=head, group=group, kind='FIRST_BLOCKER',
                                        category=name, count=len(ii), weight=mass,
                                        denominator_rows=total_fp, denominator_weight=residual_mass,
                                        fraction=len(ii)/total_fp if total_fp else None,
                                        weighted_fraction=mass/residual_mass if residual_mass else None,
                                        guarded_count=int(guard[ii].sum()),
                                        guarded_weight=float(w[ii][guard[ii]].sum())))
                for name, pool, flags, den, mass in [
                    ('THEORETICAL_LIMIT_ALL', rows, beyond, len(rows), query_mass),
                    ('THEORETICAL_LIMIT_RESIDUAL', residual, beyond, total_fp, residual_mass),
                    ('SINGLE_COMPONENT_POSITIVE_SUPPORT', one, positive, len(one), one_mass),
                    ('SINGLE_COMPONENT_ACTUAL_WITHDRAWAL', one, repair, len(one), one_mass),
                    ('SINGLE_COMPONENT_WITHDRAWAL_OF_ALL_RESIDUAL', residual, repair, total_fp, residual_mass),
                ]:
                    take = pool[flags[pool, j]]
                    num = float(w[take].sum())
                    records.append(dict(view=view, head=head, group=group, kind='OVERLAPPING_DIAGNOSTIC',
                                        category=name, count=len(take), weight=num, denominator_rows=den,
                                        denominator_weight=mass, fraction=len(take)/den if den else None,
                                        weighted_fraction=num/mass if mass else None))
    table(out, 'D_DIAGNOSIS', records)
    detail = out / 'D_QUERY_DIAGNOSIS.jsonl.gz'
    count = write_rows(detail, (dict(
        uid=str(d['ids'][i]), row=i, device=r['device'], protocol=r['protocol'], label=r['label'],
        opening=geo['opening'][i].item(), legal_components=int(comp[i]), legal_rows=int(geo['legal_rows'][i]),
        geometry_ready=bool(ready[i]), guard=bool(guard[i]),
        support2=float(geo['support2'][i]), support3=float(geo['support3'][i]),
        component_joint=float(geo['single_joint'][i]) if np.isfinite(geo['single_joint'][i]) else None,
        single_support=float(geo['single'][i]),
        **{k: float(geo[k][i]) if np.isfinite(geo[k][i]) else None
           for k in ('second_dz', 'second_dq', 'second_dc')},
        raw_margin=raw_margin[i].tolist(), deduction=(d['raw'][i] - comm[i]).tolist(),
        margin_after_correction=(comm[i] - cuts).tolist(),
        no_guard_would_withdraw=(fp[i] & (no_guard[i] <= cuts)).tolist(),
        over_theoretical_limit=beyond[i].tolist(),
        first_blocker=[CATEGORIES[j] if j >= 0 else None for j in categories[i]],
        single_tested=fallback_test[i].tolist(), single_positive=positive[i].tolist(),
        single_actual_withdrawal=repair[i].tolist(),
    ) for i, r in enumerate(d['rows'])))
    report = dict(status='PASS', rows=n, detail=artifact(detail, count), heads=list(HEADS),
                  mutually_exclusive=True, theoretical_limit=limit.tolist(),
                  fallback='DIAGNOSTIC_ONLY_KEEP_GUARD',
                  aggregate=[r for r in records if r['view'] == 'post_window_primary' and
                             r['head'] == 'ensemble' and r['group'] == 'NORMAL'])
    require(sum(r['count'] for r in report['aggregate'] if r['kind'] == 'FIRST_BLOCKER') == 22411,
            'D_PRIMARY_ENSEMBLE_RECONCILIATION')
    dump(out / 'D_SUMMARY.json', report)
    return report


def changed_rows(d, out, name, left, right, pred_left, pred_right, left_values, right_values):
    path = out / (name + '.jsonl.gz')
    ii = np.flatnonzero(np.any(pred_left != pred_right, axis=1))
    count = write_rows(path, (dict(
        uid=str(d['ids'][i]), row=int(i), label=int(d['labels'][i]), device=d['rows'][i]['device'],
        protocol=d['rows'][i]['protocol'], left_config=left, right_config=right,
        left=pred_left[i].astype(int).tolist(), right=pred_right[i].astype(int).tolist(),
        left_scores=left_values[i].tolist(), right_scores=right_values[i].tolist(),
    ) for i in ii))
    return artifact(path, count)


def compare_candidate(d, geo, config, out, name, *, common=None):
    method = config['method']
    cuts = method['cuts']
    scores = correction(d, geo['support3'], method)
    pred = scores > cuts
    full = d['scores']['P4_MAIN']
    full_pred = full > cuts
    require(not np.any(pred & ~(d['raw'] > cuts)), 'CANDIDATE_ADDED_RAW_ALARM')
    full_support = d['saved']['P4_MAIN']['support3']
    monotone = dict(support2_increases=int(np.count_nonzero(
                        geo['support2'] > d['saved']['P4_MAIN']['support2'] + TOL)),
                    support3_increases=int(np.count_nonzero(geo['support3'] > full_support + TOL)),
                    score_decreases=int(np.count_nonzero(scores < full - TOL)),
                    withdrawal_vs_full_by_head=(full_pred & ~pred).sum(axis=0).tolist())
    metrics = evaluation_rows(d, pred, eligibility=common)
    table(out, name + '_METRICS', metrics)
    pair_rows = []
    changes = {}
    lefts = ['P4_MAIN'] if name != 'M' else ['P4_COMMISSION_3D', 'P4_MAIN']
    for left in lefts:
        values = d['scores'][left]
        pred_left = values > cuts
        pair_rows.extend(dict(left=left, right=name, **r)
                         for r in evaluation_rows(d, pred_left, pred, eligibility=common))
        changes[left] = changed_rows(d, out, name + '_CHANGED_VS_' + left, left, name,
                                     pred_left, pred, values, scores)
    table(out, name + '_PAIRED_CHANGES', pair_rows)
    diff = scores - full
    details = out / (name + '_VALUES.npz')
    temporary = temp_path(details)
    with temporary.open('wb') as stream:
        np.savez(stream, uid=d['ids'], support2=geo['support2'], support3=geo['support3'],
                 delta_support2=geo['support2'] - d['saved']['P4_MAIN']['support2'],
                 delta_support3=geo['support3'] - full_support, scores=scores, delta_scores=diff,
                 decisions=pred, legal_component_count=geo['legal_component_count'], opening=geo['opening'])
    temporary.replace(details)
    ver = {k: parity(geo[k], d['saved']['P4_MAIN'][k], d['ids'])
           for k in ('support2', 'support3')}
    ver['scores'] = parity(scores, full, d['ids'])
    ver['scores_by_head'] = {head: parity(scores[:, j], full[:, j], d['ids']) for j, head in enumerate(HEADS)}
    ver['decision_changes_by_head'] = (pred != full_pred).sum(axis=0).tolist()
    decision_same = not np.any(pred != full_pred)
    numeric_same = all(ver[k]['above_tolerance_values'] == 0 and
                       ver[k]['nonfinite_left'] == ver[k]['nonfinite_right'] == 0
                       for k in ('support2', 'support3', 'scores'))
    check_count = 0
    if decision_same and name in ('C0', 'C1'):
        check_count = compare_tables(metrics, evaluation_rows(d, full_pred))
    num_path = out / (name + '_CONTINUOUS_DIFFERENCE_UIDS.jsonl.gz')
    delta2 = geo['support2'] - d['saved']['P4_MAIN']['support2']
    delta3 = geo['support3'] - full_support
    numeric_flag = (delta2 != 0) | (delta3 != 0) | (diff != 0).any(axis=1)
    above = (np.abs(delta2) > TOL) | (np.abs(delta3) > TOL) | (np.abs(diff) > TOL).any(axis=1)
    num_count = write_rows(num_path, (
        dict(uid=str(d['ids'][i]), row=int(i),
             support2_delta=float(delta2[i]), support3_delta=float(delta3[i]),
             score_delta=diff[i].tolist(), exceeds_c0_tolerance=bool(above[i]))
        for i in np.flatnonzero(numeric_flag)
    ))
    same_required = name == 'C0'
    engineering = not (monotone['support2_increases'] or monotone['support3_increases'] or
                       monotone['score_decreases'] or any(monotone['withdrawal_vs_full_by_head']))
    result = dict(status='PASS' if engineering and (not same_required or (decision_same and numeric_same)) else 'FAIL',
                  name=name, rows=len(d['rows']), tolerances=dict(rtol=0, atol=TOL),
                  outcome='DECISION_PRESERVING' if decision_same else 'DECISION_CHANGED',
                  numeric_comparison='NUMERICALLY_EQUIVALENT' if numeric_same else 'NUMERICALLY_DIFFERENT',
                  metric_rows_equal=check_count, paired_changes=changes, numeric=ver,
                  monotonicity=monotone, arrays=artifact(details, len(d['rows'])),
                  continuous_difference_uids=artifact(num_path, num_count),
                  query_uid_order_sha256=uid_sha(d['ids'].tolist()), evaluation_scope='fixed UNSW queries',
                  metrics_headline=[r for r in metrics if r['group'] in LABELS and
                                    r['guard_stratum'] == 'ALL' and r['head'] == 'ensemble'])
    dump(out / (name + '_VERIFICATION.json'), result)
    return result
