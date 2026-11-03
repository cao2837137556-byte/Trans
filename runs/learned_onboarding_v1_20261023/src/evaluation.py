"""Scalar seed-27 calibration and paired evaluation for learned onboarding V1.

Pure calculations only: callers bind ordered UIDs, bank identities, the sealed
cut, and source/target roles before passing arrays here. No target fitting occurs.
"""

import hashlib
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

from common import LAMBDAS, record, require, uid_hash


def _vector(values, n, name, *, nonnegative=False):
    arr = np.asarray(values, dtype=np.float64)
    require(arr.shape == (n,) and np.isfinite(arr).all(), name)
    if nonnegative:
        require(np.all(arr >= 0), name)
    return arr


def _matrix(values, n, name):
    arr = np.asarray(values, dtype=np.float64)
    require(arr.ndim == 2 and arr.shape[0] == n and np.isfinite(arr).all(), name)
    return arr


def _rows(rows, *, cal=False):
    require(len({r['uid'] for r in rows}) == len(rows) and
            all(isinstance(r['uid'], str) and r['uid'] for r in rows), 'QUERY_UID_SET')
    for row in rows:
        require(row.get('label') in (0, 1) and row.get('use') != 'REFERENCE',
                'QUERY_ROLE')
        if cal:
            require(row.get('partition') == 'LEARN' and row.get('fit_role') == 'CAL' and
                    row['label'] == 1, 'PROTECTION_CAL_ATTACK_ONLY')
        else:
            denominator = row.get('label_metric_weight_denominator')
            require(type(denominator) is int and denominator > 0, 'METRIC_WEIGHT')


def apply_scalar_correction(scores, strengths, eligible, scale, lambda_value):
    """Float64 subtract, with exact array-copy fallback for inactive rows."""
    n = len(scores)
    x = _vector(scores, n, 'SCORE_SCHEMA')
    a = _vector(strengths, n, 'STRENGTH_SCHEMA')
    mask = np.asarray(eligible)
    require(mask.shape == (n,) and mask.dtype == np.bool_ and
            np.all((a >= 0) & (a <= 1)) and np.all(a[~mask] == 0), 'STRENGTH_ELIGIBILITY')
    require(type(scale) in (int, float, np.float64) and math.isfinite(scale) and
            scale >= 0 and lambda_value in LAMBDAS, 'SCALE_OR_LAMBDA')
    out = x.copy()
    if lambda_value == 0 or scale == 0:
        return out
    active = mask & (a > 0)
    out[active] = x[active] - float(lambda_value) * float(scale) * a[active]
    tolerance = 4*np.finfo(np.float64).eps*np.maximum(1., np.abs(x))
    require(np.isfinite(out).all() and np.all(out <= x) and
            np.all(x-out <= lambda_value*scale+tolerance), 'CORRECTION_BOUND')
    return out


def calibrate_lambda(rows, base_scores, cut, strengths_matrix, eligible_matrix,
                     scale, bank_keys=None, *, source_components=None,
                     require_informative=True):
    """Worst legal CAL bank protection, with no normal-benefit selection."""
    _rows(rows, cal=True)
    n = len(rows)
    base = _vector(base_scores, n, 'SCORE_SCHEMA')
    a = _matrix(strengths_matrix, n, 'STRENGTH_MATRIX')
    eligible = np.asarray(eligible_matrix)
    require(eligible.shape == a.shape and eligible.dtype == np.bool_ and
            np.all((a >= 0) & (a <= 1)) and np.all(a[~eligible] == 0),
            'ELIGIBILITY_MATRIX')
    require(math.isfinite(float(cut)) and math.isfinite(float(scale)) and scale >= 0,
            'CUT_OR_SCALE')
    if source_components is not None:
        require(not set(source_components).intersection(r['component_id'] for r in rows),
                'CAL_REFERENCE_COMPONENT_LEAKAGE')
    keys = list(range(a.shape[1])) if bank_keys is None else list(bank_keys)
    require(len(keys) == a.shape[1] and len(set(map(str, keys))) == len(keys),
            'BANK_ROSTER')
    baseline_alarm = base > cut
    informative = bool(np.any(eligible & baseline_alarm[:, None] & (a > 0)))
    receipts = []
    selected = 0.0
    for candidate in LAMBDAS:
        missed = set()
        missed_pairs = 0
        reachable = set()
        positive_pairs = 0
        minima = []
        banks = []
        for j, key in enumerate(keys):
            corrected = apply_scalar_correction(base, a[:, j], eligible[:, j],
                                                scale, candidate)
            changed = eligible[:, j] & baseline_alarm & ~(corrected > cut)
            indices = np.flatnonzero(changed)
            missed.update(indices.tolist())
            missed_pairs += len(indices)
            positive = eligible[:, j] & (a[:, j] > 0)
            positive_pairs += int(positive.sum())
            cap = candidate*scale
            reachable.update(np.flatnonzero(positive & baseline_alarm &
                                             (base-cut <= cap)).tolist())
            if cap > 0 and np.any(positive & baseline_alarm):
                minima.append(float(np.min((base-cut)[positive & baseline_alarm]/cap)))
            banks.append(dict(bank_key=key, legal_pairs=int(eligible[:, j].sum()),
                              positive_pairs=int(positive.sum()),
                              new_miss_pairs=len(indices),
                              new_miss_uids=[rows[int(i)]['uid'] for i in indices]))
        if candidate == 0:
            require(not missed and missed_pairs == 0, 'ZERO_LAMBDA_NOT_EXACT')
        passes = not missed
        if passes and (informative or not require_informative):
            selected = candidate
        receipts.append(dict(lambda_value=candidate, passes=passes,
                             new_miss_count=len(missed), new_miss_pair_count=missed_pairs,
                             new_miss_uids=[rows[i]['uid'] for i in sorted(missed)],
                             legal_pairs=int(eligible.sum()), positive_pairs=positive_pairs,
                             cap_reachable_detected_attack_count=len(reachable),
                             minimum_positive_margin_over_cap=min(minima) if minima else None,
                             banks=banks))
    return record('learned-onboarding-calibration-v1',
                  status=('READY' if informative else 'PROTECTION_UNINFORMATIVE'
                          if require_informative else 'V3_NO_INFORMATION'),
                  selected_lambda=selected, candidates=receipts,
                  cal_attack_rows=n, cal_attack_uid_sha256=uid_hash(
                      [r['uid'] for r in rows], ordered=True),
                  legal_pairs=int(eligible.sum()),
                  positive_pairs=int((a > 0).sum()),
                  baseline_detected_legal_positive_pairs=int((eligible &
                      baseline_alarm[:, None] & (a > 0)).sum()),
                  bank_keys=keys,
                  protection_claim='observed CAL attacks only')


def _measure(rows, decision):
    result = {}
    for label, name in ((0, 'normal'), (1, 'attack')):
        ix = [i for i, r in enumerate(rows) if r['label'] == label]
        if not ix:
            result[name] = dict(rows=0, positive=0, rate=None, weighted_rate=None)
            continue
        weights = [1/rows[i]['label_metric_weight_denominator'] for i in ix]
        result[name] = dict(rows=len(ix), positive=int(decision[ix].sum()),
            rate=float(decision[ix].sum()/len(ix)),
            weighted_rate=math.fsum(w*int(decision[i]) for i, w in zip(ix, weights)) /
                          math.fsum(weights))
    return result


def _group(rows, base_decision, corrected_decision, eligible, keys):
    buckets = defaultdict(list)
    for i, row in enumerate(rows):
        buckets[tuple(str(row.get(k, 'NOT_AVAILABLE')) for k in keys)].append(i)
    output = []
    for key, ix in sorted(buckets.items()):
        sub = [rows[i] for i in ix]
        b = base_decision[ix]
        c = corrected_decision[ix]
        e = eligible[ix]
        y = np.asarray([r['label'] for r in sub])
        output.append(dict(group=dict(zip(keys, key)), rows=len(ix),
                           base=_measure(sub, b), corrected=_measure(sub, c),
                           new_fn_uids=[sub[int(j)]['uid'] for j in np.flatnonzero((y == 1) & b & ~c)],
                           corrected_normal_fp=int(((y == 0) & b & ~c).sum()),
                           eligible_rows=int(e.sum())))
    return output


def _attack_contract(metric, device_groups):
    """Original scalar-head recall floors, separate from added-FN protection."""
    rate = metric['attack']['weighted_rate']
    if rate is None:
        return dict(status='NOT_EVALUABLE', pool_attack_99=None,
                    seed_attack_97=None, device_attack_97={},
                    failing_devices=[], missing_devices=[])
    devices = {}
    missing = []
    for group in device_groups:
        device = group['group']['device']
        value = group['corrected']['attack']['weighted_rate']
        devices[device] = None if value is None else bool(value >= .97)
        if value is None:
            missing.append(device)
    failures = [device for device, passed in devices.items() if passed is False]
    pool_ok, seed_ok = bool(rate >= .99), bool(rate >= .97)
    return dict(status='FAIL' if not pool_ok or not seed_ok or failures else 'PASS',
                pool_attack_99=pool_ok, seed_attack_97=seed_ok,
                device_attack_97=devices, failing_devices=failures,
                missing_devices=missing)


def evaluate_pair(rows, base_scores, corrected_scores, cut, eligible, scale,
                  lambda_value, *, reasons=None, strengths=None,
                  trace=None, pool=None, bank=None, arm=None):
    """Complete-denominator scalar report and replayable per-UID predictions."""
    _rows(rows)
    n = len(rows)
    base = _vector(base_scores, n, 'BASE_SCORE')
    corrected = _vector(corrected_scores, n, 'CORRECTED_SCORE')
    mask = np.asarray(eligible)
    require(mask.shape == (n,) and mask.dtype == np.bool_ and
            math.isfinite(float(cut)) and math.isfinite(float(scale)) and scale >= 0 and
            lambda_value in LAMBDAS, 'PAIR_SCHEMA')
    tolerance = 4*np.finfo(np.float64).eps*np.maximum(1., np.abs(base))
    require(np.all(corrected <= base) and
            np.all(base-corrected <= lambda_value*scale+tolerance) and
            np.array_equal(base[~mask], corrected[~mask]), 'PAIR_CORRECTION_BOUND')
    if lambda_value == 0 or scale == 0:
        require(np.array_equal(base, corrected), 'NOOP_NOT_EXACT')
    reason = ['ELIGIBLE' if value else 'INELIGIBLE' for value in mask] if reasons is None else list(reasons)
    require(len(reason) == n, 'REASON_LENGTH')
    a = np.zeros(n) if strengths is None else _vector(strengths, n, 'STRENGTH_SCHEMA')
    require(np.all((a >= 0) & (a <= 1)) and np.all(a[~mask] == 0),
            'STRENGTH_ELIGIBILITY')
    if strengths is not None:
        require(np.array_equal(base[a == 0], corrected[a == 0]),
                'ZERO_STRENGTH_NOT_EXACT')
    if trace is not None:
        require(np.array_equal(np.asarray(trace['eligible']), mask) and
                np.asarray(trace['matched_reference_uids']).shape == (n, 2) and
                len(trace['legal_component_count']) == n and
                len(trace['bank_end']) == n and len(trace['bank_end_frame']) == n,
                'TRACE_BINDING')
    bd, cd = base > cut, corrected > cut
    y = np.asarray([r['label'] for r in rows])
    normal = y == 0
    attack = y == 1
    fp = normal & bd
    correctable_fp = fp & mask
    outside = fp & ~mask
    cap_unreachable = correctable_fp & (base-cut > lambda_value*scale)
    actual_uncorrected = correctable_fp & cd
    fixed = correctable_fp & ~cd
    added_fn = attack & bd & ~cd
    require(not np.any(normal & ~bd & cd), 'NEW_NORMAL_FP')
    n_normal = int(normal.sum())
    lower = int(outside.sum() + cap_unreachable.sum())
    base_metrics, corrected_metrics = _measure(rows, bd), _measure(rows, cd)
    groups = {}
    for fields in (('device',), ('device', 'protocol'), ('device', 'activity'),
                   ('device', 'capture_id'), ('device', 'annotation_id'),
                   ('device', 'attack_rate')):
        groups['/'.join(fields)] = _group(rows, bd, cd, mask, fields)
    base_device_groups = [dict(group=g['group'], corrected=g['base'])
                          for g in groups['device']]
    per_query = [dict(uid=row['uid'], label=row['label'], device=row['device'],
                      protocol=row.get('protocol'), base_score=float(base[i]),
                      corrected_score=float(corrected[i]), cut=float(cut),
                      base_alarm=bool(bd[i]), corrected_alarm=bool(cd[i]),
                      eligible=bool(mask[i]), reason=str(reason[i]),
                      strength=float(a[i]), decrement=float(base[i]-corrected[i]),
                      lambda_value=lambda_value, scale=float(scale),
                      matched_reference_uids=(list(trace['matched_reference_uids'][i])
                          if trace is not None else None),
                      matched_components=(list(trace['matched_components'][i])
                          if trace is not None else None),
                      legal_component_count=(int(trace['legal_component_count'][i])
                          if trace is not None else None),
                      bank_end=(float(trace['bank_end'][i])
                          if trace is not None and np.isfinite(trace['bank_end'][i]) else None),
                      bank_end_frame=(trace['bank_end_frame'][i]
                          if trace is not None else None),
                      label_metric_weight_denominator=row['label_metric_weight_denominator'])
                 for i, row in enumerate(rows)]
    summary = record('learned-onboarding-paired-cell-v1', status='EVALUATED',
        pool=pool, bank=bank, arm=arm, rows=n,
        ordered_uid_sha256=uid_hash([r['uid'] for r in rows], ordered=True),
        base_score_sha256=hashlib.sha256(base.tobytes(order='C')).hexdigest(),
        cut=float(cut), scale=float(scale), lambda_value=lambda_value,
        base=base_metrics, corrected=corrected_metrics,
        base_true_positives=int((attack & bd).sum()),
        base_false_negatives=int((attack & ~bd).sum()),
        new_fn_count=int(added_fn.sum()),
        new_fn_uids=[rows[int(i)]['uid'] for i in np.flatnonzero(added_fn)],
        corrected_normal_fp=int(fixed.sum()),
        eligible_normal_fp=int(correctable_fp.sum()),
        actual_eligible_normal_fp_remaining=int(actual_uncorrected.sum()),
        normal_fp_lower_bound=dict(ineligible_count=int(outside.sum()),
            cap_unreachable_count=int(cap_unreachable.sum()),
            total_count=lower,
            ineligible_rate=float(outside.sum()/n_normal) if n_normal else None,
            cap_unreachable_rate=float(cap_unreachable.sum()/n_normal) if n_normal else None,
            total_rate=float(lower/n_normal) if n_normal else None),
        fallback=dict(ineligible=int((~mask).sum()),
            eligible_zero_strength=int((mask & (a == 0)).sum()),
            degenerate_scale=int(mask.sum()) if scale == 0 else 0,
            zero_lambda=int(mask.sum()) if lambda_value == 0 else 0,
            reasons={name: reason.count(name) for name in sorted(set(reason))}),
        groups=groups,
        original_attack_contract=dict(
            base=_attack_contract(base_metrics, base_device_groups),
            corrected=_attack_contract(corrected_metrics, groups['device'])),
        pool_normal_fpr_1pct=(corrected_metrics['normal']['weighted_rate'] <= .01
                              if n_normal else None),
        device_normal_fpr_2pct={g['group']['device']:
            (g['corrected']['normal']['weighted_rate'] <= .02
             if g['corrected']['normal']['rows'] else None)
            for g in groups['device']},
        evidence='CONSUMED_DEVELOPMENT_ONLY', automatic_promotion=False)
    return dict(summary=summary, per_query=per_query)


def scalar_v3_fit_scales(rows, scores):
    """Historical v3 scale for one real seed column, using original weights."""
    _old_v3()
    from constrained_onboarding_core_v3 import _rows as v3_rows
    v3_rows(rows)
    require(rows and all(r.get('partition') == 'LEARN' and r.get('fit_role') == 'FIT'
                         for r in rows) and {r['label'] for r in rows} == {0, 1},
            'SCALE_FIT_ONLY')
    x = _vector(scores, len(rows), 'SCORE_SCHEMA')
    from legacy_qref_data_v1 import weights
    from constrained_onboarding_core_v3 import weighted_quantile
    w = weights(rows)
    low, high = weighted_quantile(x, w, .1), weighted_quantile(x, w, .9)
    return record('scalar-v3-scale-v1', status='READY', seed=27, scale=high-low,
                  q10=low, q90=high, fit_rows=len(rows),
                  fit_uid_sha256=uid_hash([r['uid'] for r in rows], ordered=True),
                  weight_rule='legacy_qref_data_v1.weights')


def _old_v3():
    old = Path(__file__).resolve().parents[3] / 'repo' / 'ood'
    require((old / 'constrained_onboarding_core_v3.py').is_file(), 'V3_CODE_MISSING')
    if str(old) not in sys.path:
        sys.path.insert(0, str(old))


class ScalarV3:
    """Original v3 bank geometry/support with scalar correction and protection."""

    def __init__(self, rows, e3, q14, normalizer, *, feature_uids, q_uids,
                 allowed_partitions=None, allow_prebank_history=False):
        _old_v3()
        from constrained_onboarding_core_v3 import ReferenceBank
        self.bank = ReferenceBank(rows, e3, q14, normalizer,
            feature_uids=feature_uids, q_uids=q_uids,
            allowed_partitions=allowed_partitions,
            allow_prebank_history=allow_prebank_history)

    def fit_geometry(self, rows, e3, q14, *, feature_uids, q_uids):
        from constrained_onboarding_core_v3 import fit_geometry
        return fit_geometry(rows, e3, q14, self.bank,
                            feature_uids=feature_uids, q_uids=q_uids)

    def own(self, rows, e3, q14, geometry, *, feature_uids, q_uids, override=None):
        return self.bank.own(rows, e3, q14, geometry,
            feature_uids=feature_uids, q_uids=q_uids, override=override)

    def matrix(self, rows, e3, q14, geometry, *, feature_uids, q_uids):
        return self.bank.matrix(rows, e3, q14, geometry,
            feature_uids=feature_uids, q_uids=q_uids)

    @staticmethod
    def fit_scales(rows, scores):
        return scalar_v3_fit_scales(rows, scores)

    @staticmethod
    def correction(scores, trace, scale, lambda_value):
        return apply_scalar_correction(scores, trace['support'], trace['eligible'],
                                       scale, lambda_value)

    def choose_lambda(self, rows, scores, cut, scale, e3, q14, geometry,
                      *, feature_uids, q_uids):
        trace = self.matrix(rows, e3, q14, geometry,
                            feature_uids=feature_uids, q_uids=q_uids)
        return calibrate_lambda(rows, scores, cut, trace['support'], trace['eligible'],
                                scale, bank_keys=[(r['partition'], r['device'], r['protocol'])
                                                  for r in trace['roster']],
                                source_components=[r['component_id'] for r in self.bank.rows],
                                require_informative=False)


def _cell(matrix, pool, bank, arm):
    key = (pool, bank, arm)
    require(key in matrix, 'MISSING_MATRIX_CELL:'+str(key))
    value = matrix[key]
    return value.get('summary', value)


def _normal_fp(cell):
    return cell['corrected']['normal']['positive']


def _weighted_fpr(cell):
    return cell['corrected']['normal']['weighted_rate']


def _device_normal(cell):
    return {g['group']['device']: g['corrected']['normal']
            for g in cell['groups']['device']}


def _compare_b2(matrix, left, right, pools):
    pairs = []
    for pool in pools:
        a, b = _cell(matrix, pool, 'B2', left), _cell(matrix, pool, 'B2', right)
        left_devices, right_devices = _device_normal(a), _device_normal(b)
        require(left_devices.keys() == right_devices.keys(), 'DEVICE_CELL_MISMATCH')
        require(all(left_devices[d]['rows'] == right_devices[d]['rows'] and
                    (left_devices[d]['weighted_rate'] is None) ==
                    (right_devices[d]['weighted_rate'] is None)
                    for d in left_devices), 'DEVICE_DENOMINATOR_MISMATCH')
        device_deltas = {d: dict(
            raw_fp_gain=right_devices[d]['positive']-left_devices[d]['positive'],
            weighted_fpr_gain=(None if left_devices[d]['weighted_rate'] is None else
                right_devices[d]['weighted_rate']-left_devices[d]['weighted_rate']))
            for d in left_devices}
        pairs.append(dict(pool=pool, left=left, right=right,
            left_fp=_normal_fp(a), right_fp=_normal_fp(b),
            raw_fp_gain=_normal_fp(b)-_normal_fp(a),
            weighted_fpr_gain=_weighted_fpr(b)-_weighted_fpr(a),
            device_deltas=device_deltas,
            no_worse=(_weighted_fpr(a) <= _weighted_fpr(b) and
                      _normal_fp(a) <= _normal_fp(b) and
                      all(left_devices[d]['positive'] <= right_devices[d]['positive'] and
                          (left_devices[d]['weighted_rate'] is None or
                           left_devices[d]['weighted_rate'] <=
                           right_devices[d]['weighted_rate']) for d in left_devices)),
            strict=(_weighted_fpr(a) < _weighted_fpr(b) and
                    _normal_fp(a) < _normal_fp(b))))
    return dict(pools=pairs, no_worse_all=all(p['no_worse'] for p in pairs),
                strict_any=any(p['strict'] for p in pairs))


def scientific_decision(matrix, *, pools=('CIC_DEV', 'UNSW_DEV'),
                        banks=('OLD_BANK', 'B0', 'B1', 'B2'),
                        learned_arms=('L_STANDARD', 'L_HARD', 'L_QUERY_ONLY'),
                        source_coverage=None, source_signal=None,
                        wrong_control=None):
    """Pre-registered science layers over the complete A/B x four-bank matrix."""
    for pool in pools:
        for bank in banks:
            base_cell = _cell(matrix, pool, bank, 'BASE')
            for arm in ('BASE', 'V3') + tuple(learned_arms):
                cell = _cell(matrix, pool, bank, arm)
                require(cell['ordered_uid_sha256'] == base_cell['ordered_uid_sha256'] and
                        cell['base_score_sha256'] == base_cell['base_score_sha256'] and
                        cell['cut'] == base_cell['cut'] and cell['rows'] == base_cell['rows'],
                        'MATRIX_IDENTITY_MISMATCH')
    attack = {}
    for arm in learned_arms:
        bad = [(pool, bank, _cell(matrix, pool, bank, arm)['new_fn_uids'])
               for pool in pools for bank in banks
               if _cell(matrix, pool, bank, arm)['new_fn_count']]
        attack[arm] = dict(status='FAIL' if bad else 'PASS', failing_cells=bad,
                           observed_new_fn_count=sum(len(x[2]) for x in bad))
    original_attack_contract = {}
    for arm in ('BASE', 'V3') + tuple(learned_arms):
        cells = [dict(pool=pool, bank=bank,
                      **_cell(matrix, pool, bank, arm)['original_attack_contract']['corrected'])
                 for pool in pools for bank in banks]
        original_attack_contract[arm] = dict(
            status=('FAIL' if any(item['status'] == 'FAIL' for item in cells) else
                    'NOT_EVALUABLE' if any(item['status'] == 'NOT_EVALUABLE' for item in cells) else
                    'PASS'), cells=cells)
    informative = any(_cell(matrix, pool, bank, 'BASE')['eligible_normal_fp'] > 0
                      for pool in pools for bank in banks)
    benefit = {}
    v3_comparison = {}
    v3_all_cells = {}
    for arm in learned_arms:
        base = _compare_b2(matrix, arm, 'BASE', pools)
        v3 = _compare_b2(matrix, arm, 'V3', pools)
        benefit[arm] = dict(status=('NOT_EVALUABLE' if not informative else
            'PASS' if attack[arm]['status'] == 'PASS' and base['no_worse_all'] and
                      base['strict_any'] else 'FAIL'), comparison=base)
        v3_comparison[arm] = v3
        v3_all_cells[arm] = [dict(pool=pool, bank=bank,
            raw_fp_gain=_normal_fp(_cell(matrix, pool, bank, 'V3')) -
                        _normal_fp(_cell(matrix, pool, bank, arm)),
            weighted_fpr_gain=_weighted_fpr(_cell(matrix, pool, bank, 'V3')) -
                              _weighted_fpr(_cell(matrix, pool, bank, arm)),
            new_fn_difference=_cell(matrix, pool, bank, 'V3')['new_fn_count'] -
                              _cell(matrix, pool, bank, arm)['new_fn_count'])
            for pool in pools for bank in banks]
    hard = _compare_b2(matrix, 'L_HARD', 'L_STANDARD', pools)
    query_only = _compare_b2(matrix, 'L_HARD', 'L_QUERY_ONLY', pools)
    hard_status = ('NOT_EVALUABLE' if not informative else
                   'FAIL' if attack['L_HARD']['status'] != 'PASS' else
                   'PASS' if hard['no_worse_all'] and hard['strict_any'] else
                   'NO_INCREMENTAL_GAIN')
    reference_status = ('NOT_EVALUABLE' if not informative else
        'FAIL' if attack['L_HARD']['status'] != 'PASS' else
        'PASS' if query_only['no_worse_all'] and query_only['strict_any'] else
        'REFERENCE_ATTRIBUTION_FAIL')
    if wrong_control is not None and wrong_control.get('equally_effective'):
        reference_status = 'REFERENCE_ATTRIBUTION_FAIL'
    return record('learned-onboarding-scientific-decision-v1',
        status='EVALUATED', development_evidence_only=True,
        automatic_promotion=False, eligible_base_fp_present=informative,
        attack_protection=attack, original_attack_contract=original_attack_contract,
        learned_benefit=benefit,
        versus_v3=v3_comparison, versus_v3_all_cells=v3_all_cells,
        hard_task_value=dict(status=hard_status, comparison=hard),
        reference_attribution=dict(status=reference_status,
            versus_query_only=query_only, wrong_control=wrong_control),
        source_coverage=source_coverage, source_signal=source_signal)
