"""Source-CAL-only budget protection for frozen V3 reference correction.

This module does not load targets, alter geometry/cuts, encode features, or train.
The r1 epsilon values are prepared here as source-only dry-run working points;
the caller separately enforces authorization and the evaluation protocol.
All attack risks use the union of withdrawals over legal source donors (one
count/weight per UID and suffix), retaining V3's conservative donor semantics.
At epsilon=0 the *selection* is exactly the original zero-withdrawal rule,
including zero-weight attacks. Absolute/group acceptance is reported separately:
a baseline below 99% cannot acquire an artificial passing working point.
"""
import hashlib
import math

import numpy as np

import constrained_onboarding_core_v3 as core


EPSILON_PP_CANDIDATES = (0.0, 0.05, 0.1, 0.2)
SUFFIXES = tuple(str(s) for s in core.SEEDS) + ('ensemble',)
_FROZEN_GRID = (0.0, 0.05, 0.1, 0.25)
SCHEMA = 'onboarding-source-budget-preparation-v1'


def _require(condition, message):
    core.require(condition, message)


def _weights(rows, supplied, name):
    w = core.class_weights(rows) if supplied is None else np.asarray(supplied)
    _require(w.dtype.kind in 'fiu' and w.shape == (len(rows),), name + '_WEIGHT_SHAPE_DTYPE')
    w = np.asarray(w, dtype=np.float64)
    _require(np.isfinite(w).all() and np.all(w >= 0), name + '_WEIGHT_FINITE_NONNEGATIVE')
    total = math.fsum(w)
    _require(math.isfinite(total) and total > 0, name + '_WEIGHT_MASS')
    return w.copy()


def _cal_rows(rows, label, name, annotation_field=None):
    _require(bool(rows) and all(r.get('partition') == 'LEARN' and
             r.get('fit_role') == 'CAL' and r.get('label') == label for r in rows),
             name + '_SOURCE_CAL_ONLY')
    core._rows(rows)
    if annotation_field is not None:
        _require(all(isinstance(r.get(annotation_field), str) and r[annotation_field]
                     for r in rows), 'ATTACK_ANNOTATION_REQUIRED')


def _decisions(logits, cuts, ensemble_cut):
    return np.column_stack((logits > cuts, core.ordered_ensemble(logits) > ensemble_cut))


def _risk(base, missed, weights, indices):
    ix = np.asarray(indices, dtype=np.int64)
    total = math.fsum(weights[ix])
    result = dict(rows=len(ix), weight_mass=total, suffixes={})
    for k, name in enumerate(SUFFIXES):
        detected = math.fsum(weights[ix][base[ix, k]])
        lost = math.fsum(weights[ix][missed[ix, k]])
        remaining = math.fsum(weights[ix][base[ix, k] & ~missed[ix, k]])
        result['suffixes'][name] = dict(
            baseline_detected_weight=detected, added_fn_weight=lost,
            remaining_detected_weight=remaining,
            baseline_recall=None if total == 0 else detected / total,
            corrected_recall=None if total == 0 else remaining / total,
            recall_loss_pp=None if total == 0 else 100.0 * (lost / total),
            added_fn_count=int(missed[ix, k].sum()))
    return result


class _CachedSourceBank:
    """Run the unchanged legacy selector against the already computed matrix."""
    def __init__(self, bank, matrix):
        self.rows = bank.rows
        self._matrix = matrix

    def matrix(self, *args, **kwargs):
        return self._matrix


def prepare_budget_calibration(cal_attack_rows, logits, cuts, ensemble_cut, scales,
                               source_bank, e3, q14, geometry, *,
                               cal_normal_rows, normal_logits, normal_e3, normal_q14,
                               feature_uids=None, q_uids=None,
                               normal_feature_uids=None, normal_q_uids=None,
                               attack_weights=None, normal_weights=None,
                               annotation_field='activity', seed_order=core.SEEDS):
    """Compute all frozen lambda candidates once, using source CAL only.

    Default weights are the existing source class_weights hierarchy. Explicit
    nonnegative weights are accepted (positive class total required). Device and
    annotation losses condition these same weights on each nonempty group.
    Normal quality is the equal-suffix mean weighted FP reduction using own
    source references; ties prefer the larger registered lambda. Attack safety
    covers every source donor, not just the own source reference.
    """
    _require(tuple(core.LAMBDAS) == _FROZEN_GRID, 'FROZEN_LAMBDA_GRID_CHANGED')
    _require(isinstance(annotation_field, str) and annotation_field, 'ANNOTATION_FIELD')
    attacks, normals = list(cal_attack_rows), list(cal_normal_rows)
    _cal_rows(attacks, 1, 'ATTACK', annotation_field)
    _cal_rows(normals, 0, 'NORMAL')
    _require(not set(r['uid'] for r in attacks).intersection(r['uid'] for r in normals),
             'CAL_CLASS_UID_OVERLAP')
    _require(bool(source_bank.rows) and all(r.get('partition') == 'LEARN' and
             r.get('use') == 'REFERENCE' and r.get('label') == 0
             for r in source_bank.rows), 'SOURCE_REFERENCE_ONLY')
    ref_components = {r['component_id'] for r in source_bank.rows}
    _require(not ref_components.intersection(r['component_id'] for r in attacks + normals),
             'CAL_REFERENCE_COMPONENT_LEAKAGE')
    x = core._logits(logits, len(attacks), seed_order)
    normal_x = core._logits(normal_logits, len(normals), seed_order)
    cut, scale = core._cuts(cuts), core._scales(scales)
    _require(isinstance(ensemble_cut, (int, float, np.number)) and
             math.isfinite(float(ensemble_cut)), 'ENSEMBLE_CUT')
    w = _weights(attacks, attack_weights, 'ATTACK')
    nw = _weights(normals, normal_weights, 'NORMAL')
    matrix = source_bank.matrix(attacks, e3, q14, geometry,
                               feature_uids=feature_uids, q_uids=q_uids)
    a, eligible = np.asarray(matrix['support']), np.asarray(matrix['eligible'])
    _require(a.ndim == 2 and a.shape[0] == len(attacks) and
             a.shape[1] == len(matrix['roster']) and eligible.shape == a.shape and
             eligible.dtype == np.dtype(bool) and a.dtype.kind == 'f' and
             np.isfinite(a).all() and np.all((a >= 0) & (a <= 1)), 'ATTACK_SUPPORT_MATRIX')
    _require(np.all(a[~eligible] == 0), 'INELIGIBLE_POSITIVE_SUPPORT')
    _require(matrix['query_uid_sha256'] == core._uid_hash([r['uid'] for r in attacks]),
             'ATTACK_SUPPORT_UID_JOIN')
    own = source_bank.own(normals, normal_e3, normal_q14, geometry,
                          feature_uids=normal_feature_uids, q_uids=normal_q_uids)
    normal_a = np.asarray(own['support'], dtype=np.float64)
    _require(normal_a.shape == (len(normals),) and np.isfinite(normal_a).all() and
             np.all((normal_a >= 0) & (normal_a <= 1)), 'NORMAL_SUPPORT')
    # The original function, including its exact float64 score arithmetic,
    # ensemble order and strict cut comparison, remains the epsilon=0 oracle.
    legacy = core.choose_lambda(attacks, logits, cuts, ensemble_cut, scales,
                                _CachedSourceBank(source_bank, matrix), e3, q14, geometry,
                                feature_uids=feature_uids, q_uids=q_uids, seed_order=seed_order)
    base = _decisions(x, cut, ensemble_cut)
    normal_base = _decisions(normal_x, cut, ensemble_cut)
    groups = {field: {value: [i for i, row in enumerate(attacks) if row[field] == value]
                     for value in sorted({r[field] for r in attacks})}
              for field in ('device', annotation_field)}
    candidates = []
    for legacy_item, lam in zip(legacy['candidates'], core.LAMBDAS):
        missed = np.zeros((len(attacks), 4), dtype=bool)
        for j in range(a.shape[1]):
            changed = _decisions(core.apply_correction(x, a[:, j], scale, lam), cut, ensemble_cut)
            missed |= base & ~changed & eligible[:, j, None]
        miss_uids = {name: [attacks[i]['uid'] for i in np.flatnonzero(missed[:, k])]
                     for k, name in enumerate(SUFFIXES)}
        _require(miss_uids == legacy_item['newly_missed_uids'], 'LEGACY_WITHDRAWAL_PARITY')
        changed_normal = _decisions(core.apply_correction(normal_x, normal_a, scale, lam),
                                    cut, ensemble_cut)
        corrected_fp = normal_base & ~changed_normal
        normal_quality = {name: math.fsum(nw[corrected_fp[:, k]]) / math.fsum(nw)
                          for k, name in enumerate(SUFFIXES)}
        candidates.append(dict(
            lambda_value=lam, legacy_zero_withdrawal_pass=legacy_item['passes'],
            newly_missed_uids=miss_uids,
            overall=_risk(base, missed, w, range(len(attacks))),
            devices={v: _risk(base, missed, w, ix) for v, ix in groups['device'].items()},
            annotations={v: _risk(base, missed, w, ix) for v, ix in groups[annotation_field].items()},
            normal_fp_reduction=normal_quality,
            normal_quality=math.fsum(normal_quality.values()) / len(SUFFIXES)))
    return dict(schema=SCHEMA, status='SOURCE_DRY_RUN_PREPARATION',
                approved_for_target_evaluation=False, seed_order=list(core.SEEDS),
                lambda_grid=list(core.LAMBDAS), annotation_field=annotation_field,
                attack_aggregation='union of newly missed UIDs across all legal source donors, per suffix',
                normal_objective='mean of four suffix weighted FP reductions with own source reference',
                weight_rule='existing class_weights unless explicit weights supplied; group conditional mass',
                weight_identity={name: dict(rows=len(rows), total=math.fsum(ws),
                    uid_sha256=core._uid_hash([r['uid'] for r in rows]),
                    float64_sha256=hashlib.sha256(ws.tobytes(order='C')).hexdigest())
                    for name, rows, ws in [('attack', attacks, w), ('normal', normals, nw)]},
                absolute_attack_recall_floor=.99, device_loss_budget_pp=1.0,
                annotation_loss_budget_pp=5.0, legacy_protection=legacy,
                candidates=candidates)


def _budget_acceptance(candidate, epsilon_pp):
    failures = []
    for name, result in candidate['overall']['suffixes'].items():
        total = candidate['overall']['weight_mass']
        if result['corrected_recall'] < .99:
            failures.append('ABSOLUTE_RECALL:' + name)
        # Compare in the declared pp unit. Dividing nextafter(eps, 0) by 100
        # can round back to exactly eps/100, silently accepting an over-budget
        # point. The receipt and the protection compare the same reported loss.
        if result['recall_loss_pp'] > epsilon_pp:
            failures.append('RELATIVE_LOSS:' + name)
    for field, limit_pp in [('devices', 1.0), ('annotations', 5.0)]:
        for group, risk in candidate[field].items():
            total = risk['weight_mass']
            if total == 0:
                continue  # Explicit zero-weight group is reported, not divided by zero.
            for name, result in risk['suffixes'].items():
                if result['recall_loss_pp'] > limit_pp:
                    failures.append(field.upper() + '_LOSS:' + group + ':' + name)
    return dict(passes=not failures, failures=failures)


def select_budget_lambda(preparation, epsilon_pp):
    """Choose a candidate; epsilon is in percentage points (0.1 means .001).

    Positive epsilon has no fallback that masquerades as a pass: when no
    candidate meets the absolute/group contract, selected_lambda is None.
    Epsilon=0 retains the legacy selected_lambda even if acceptance fails; the
    selected_can_evaluate flag then stays false. Do not treat selection as PASS.
    """
    _require(isinstance(epsilon_pp, (int, float, np.number)) and
             not isinstance(epsilon_pp, (bool, np.bool_)) and
             math.isfinite(float(epsilon_pp)) and 0 <= epsilon_pp <= 100, 'EPSILON_PP_RANGE')
    _require(preparation.get('schema') == SCHEMA and
             preparation.get('lambda_grid') == list(_FROZEN_GRID), 'PREPARATION_SCHEMA_GRID')
    eps = float(epsilon_pp)
    decisions = []
    for candidate in preparation['candidates']:
        acceptance = _budget_acceptance(candidate, eps)
        selection_pass = (candidate['legacy_zero_withdrawal_pass'] if eps == 0 else acceptance['passes'])
        decisions.append(dict(lambda_value=candidate['lambda_value'], selection_pass=selection_pass,
                              budget_acceptance=acceptance, normal_quality=candidate['normal_quality']))
    valid = [c for c in decisions if c['selection_pass']]
    selected = (max(valid, key=lambda c: (c['normal_quality'], c['lambda_value']))
                if valid else None)
    if eps == 0:
        _require(selected is not None and selected['lambda_value'] ==
                 preparation['legacy_protection']['selected_lambda'], 'EPS0_SELECTION_PARITY')
    return dict(version='onboarding-budget-selection-v1', epsilon_pp=eps,
                epsilon_fraction=eps / 100.0,
                status='NO_FEASIBLE_WORKPOINT' if selected is None else
                       'SOURCE_DRY_RUN_WORKPOINT' if selected['budget_acceptance']['passes'] else
                       'LEGACY_SELECTION_FAILS_NEW_ACCEPTANCE',
                selected_lambda=None if selected is None else selected['lambda_value'],
                selected_budget_acceptance=None if selected is None else selected['budget_acceptance'],
                selected_can_evaluate=False,
                selection_mode='LEGACY_ZERO_WITHDRAWAL_COMPATIBILITY' if eps == 0 else 'WEIGHTED_BUDGET',
                candidates=decisions,
                epsilon_zero_matches_legacy_selection=eps == 0,
                no_target_scores_used=True, target_evaluation_authorized=False)


def choose_lambda_budget(*args, epsilon_pp, **kwargs):
    """Convenience wrapper; prepare once plus select_budget_lambda for a curve."""
    preparation = prepare_budget_calibration(*args, **kwargs)
    return dict(preparation=preparation, selection=select_budget_lambda(preparation, epsilon_pp))
