"""Frozen-plan score arithmetic, weighted accounting, and progression gates.

This module never rebuilds a hierarchy of weights.  Every rate conditions the
supplied parent-population weights on the requested fixed subset.  Arrays have
columns 27, 127, 227, ensemble; prediction is always strictly score > cut.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from fractions import Fraction

import numpy as np

SUFFIXES = ("27", "127", "227", "ensemble")
BRANCHES = ("1C", "2C_ZERO", "2C_POS", "OTHER")
LAMBDA_GRID = (0.0, 0.05, 0.1, 0.25)


class _ExactWeights:
    """Keep display weights and exact inverse-integer weights side by side.

    Ratios cancel a population-wide common denominator.  Histograms count each
    original denominator, avoiding a Fraction allocation for every row/event.
    """
    def __init__(self, weights, denominators):
        den = np.asarray(denominators)
        if den.shape != weights.shape or den.dtype.kind not in "iu" or np.any(den <= 0):
            raise ValueError("denominators must be the positive original integer vector")
        if not np.array_equal(weights, 1.0 / den.astype(np.float64)):
            raise ValueError("display weights disagree with original integer denominators")
        self.values = weights
        unique, self.inverse = np.unique(den, return_inverse=True)
        common = math.lcm(*(int(value) for value in unique))
        self.units = tuple(common // int(value) for value in unique)

    def __array__(self, dtype=None, copy=None):
        array = np.asarray(self.values, dtype=dtype)
        return array.copy() if copy else array

    def mass(self, mask):
        counts = np.bincount(self.inverse[np.asarray(mask, dtype=bool)], minlength=len(self.units))
        return sum(int(counts[i]) * self.units[i] for i in np.flatnonzero(counts))

    def ratio(self, numerator, denominator, scale=1, subtract=None):
        den = self.mass(denominator)
        if den == 0:
            return None
        num = self.mass(numerator)
        if subtract is not None:
            num -= self.mass(subtract)
        ratio = Fraction(scale * num, den)
        return {"numerator": ratio.numerator, "denominator": ratio.denominator}


def _comparison(record, key, threshold):
    """Exact for supplied original denominators; no tolerance or rounding."""
    rational = record.get("exact", {}).get(key)
    value = (Fraction(rational["numerator"], rational["denominator"])
             if rational is not None else record[key])
    boundary = Fraction(str(threshold)) if rational is not None else threshold
    return (value > boundary) - (value < boundary)


def _finite(value, name, ndim=None):
    out = np.asarray(value, dtype=np.float64)
    if (ndim is not None and out.ndim != ndim) or not np.isfinite(out).all():
        raise ValueError(f"{name}: finite {ndim}-dimensional array required")
    return out


def ensemble(logits, mode="source"):
    """Preserve the two historical floating-point execution paths."""
    values = _finite(logits, "logits", 2)
    if values.shape[1] != 3:
        raise ValueError("ensemble requires the three ordered seed columns")
    if mode == "source":
        result = np.zeros(len(values), dtype=np.float64)
        for index in range(3):
            result += values[:, index]
        result /= 3.0
    elif mode == "target":
        result = np.stack([values[:, index] for index in range(3)]).mean(0, dtype=np.float64)
    else:
        raise ValueError("mode must be source or target")
    if not np.isfinite(result).all():
        raise ValueError("nonfinite ensemble")
    return result


def score_columns(raw, mode="source"):
    values = _finite(raw, "scores", 2)
    if values.shape[1] == 3:
        return np.column_stack((values, ensemble(values, mode)))
    if values.shape[1] != 4:
        raise ValueError("scores require three seeds or three seeds and ensemble")
    return values.copy()


def apply_correction(raw, support, scales, lambda_value, mode="source"):
    values = score_columns(raw, mode)
    a = _finite(support, "support", 1)
    scale = _finite(scales, "scales", 1)
    if len(a) != len(values) or np.any((a < 0) | (a > 1)):
        raise ValueError("support must have one [0,1] value per query")
    if scale.shape != (3,) or np.any(scale < 0):
        raise ValueError("three nonnegative scales required")
    if float(lambda_value) not in LAMBDA_GRID:
        raise ValueError("lambda outside the frozen grid")
    corrected = values[:, :3].copy()
    active = a > 0
    for index in range(3):
        if float(lambda_value) > 0 and scale[index] > 0:
            corrected[active, index] = (
                values[active, index] - float(lambda_value) * scale[index] * a[active]
            )
    return np.column_stack((corrected, ensemble(corrected, mode)))


def scenario_scores(raw, support, eligible, scales, lambda_value, mode="source"):
    """All donor scenarios with explicit RAW fallback, including new L donors.

    Call separately with D0's mask and L's mask.  The donor axis must retain the
    same identity/order for paired arms; old ineligibility must never filter L.
    """
    base = score_columns(raw, mode)
    support = _finite(support, "donor support")
    mask = np.asarray(eligible, dtype=bool)
    if support.ndim == 1:
        support, mask = support[:, None], mask[:, None]
    if support.ndim != 2 or mask.shape != support.shape or len(support) != len(base):
        raise ValueError("support and eligible must have shape (queries, donors)")
    if np.any((support < 0) | (support > 1)):
        raise ValueError("donor support outside [0,1]")
    donor = np.empty((len(base), support.shape[1], 4), dtype=np.float64)
    for index in range(support.shape[1]):
        donor[:, index] = apply_correction(
            base, np.where(mask[:, index], support[:, index], 0.0), scales,
            lambda_value, mode,
        )
        donor[~mask[:, index], index] = base[~mask[:, index]]
    safety = base.copy()
    if donor.shape[1]:
        safety = np.minimum(safety, donor.min(axis=1))
    return {"raw": base, "donor": donor, "safety": safety, "eligible": mask.copy()}


def donor_scores(raw, support, eligible, scales, lambda_value, mode="source"):
    return scenario_scores(raw, support, eligible, scales, lambda_value, mode)["donor"]


def worst_donor_scores(raw, donor, eligible, mode="source"):
    base = score_columns(raw, mode)
    scenarios = _finite(donor, "donor scores", 3)
    mask = np.asarray(eligible, dtype=bool)
    if scenarios.shape != (len(base), mask.shape[1], 4) or mask.shape[0] != len(base):
        raise ValueError("donor/eligible shape mismatch")
    answer = base.copy()
    for index in range(scenarios.shape[1]):
        answer = np.minimum(answer, np.where(mask[:, index, None], scenarios[:, index], base))
    return answer


def paired_donor_risk(raw, d0_donor, local_donor, eligible_d0, eligible_local, cuts):
    """UID-once union and donor-paired changes; never pair different donors.

    `new_scenarios` can include a UID already lost under another D0 donor.
    `new_uid_withdrawals` is the disjoint increment for the cumulative UID ledger.
    """
    base = score_columns(raw)
    d0 = _finite(d0_donor, "D0 donors", 3)
    local = _finite(local_donor, "L donors", 3)
    old = np.asarray(eligible_d0, dtype=bool)
    new = np.asarray(eligible_local, dtype=bool)
    cut = _cuts(cuts)
    if d0.shape != local.shape or d0.shape != (*old.shape, 4) or old.shape != new.shape:
        raise ValueError("paired donor identity/shape mismatch")
    if len(base) != len(d0):
        raise ValueError("paired donor query count mismatch")
    union = old | new
    d0 = np.where(old[..., None], d0, base[:, None, :])
    local = np.where(new[..., None], local, base[:, None, :])
    raw_tp = base > cut
    old_lost = raw_tp[:, None, :] & union[..., None] & (d0 <= cut)
    new_lost = raw_tp[:, None, :] & union[..., None] & (local <= cut)
    old_uid, local_uid = old_lost.any(axis=1), new_lost.any(axis=1)
    return {
        "union_eligible": union,
        "raw_to_d0": old_uid,
        "raw_to_local": local_uid,
        "new_uid_withdrawals": local_uid & ~old_uid,
        "new_scenarios": ((d0 > cut) & (local <= cut) & union[..., None]).any(axis=1),
        "recovered_scenarios": ((d0 <= cut) & (local > cut) & union[..., None]).any(axis=1),
    }


def _cuts(cuts):
    cut = _finite(cuts, "cuts", 1)
    if cut.shape != (4,):
        raise ValueError("four cuts required")
    return cut


def calibration_check(raw, corrected, cuts, mode="source"):
    """Inputs contain CAL attacks only; exact zero RAW-TP withdrawal required."""
    base, adjusted = score_columns(raw, mode), score_columns(corrected, mode)
    if base.shape != adjusted.shape:
        raise ValueError("CAL score shape mismatch")
    cut = _cuts(cuts)
    counts = np.count_nonzero((base > cut) & (adjusted <= cut), axis=0)
    return {"pass": bool(np.all(counts == 0)), "rows": len(base),
            "withdrawals": {suffix: int(counts[j]) for j, suffix in enumerate(SUFFIXES)}}


def calibrate_lambda(raw, support, eligible, scales, cuts, mode="source"):
    """Select D0 lambda once on CAL attacks, all donors, all four suffixes."""
    base = score_columns(raw, mode)
    if not len(base):
        raise ValueError("empty CAL attack population cannot calibrate lambda")
    checks = []
    selected = None
    for value in LAMBDA_GRID:
        scenarios = scenario_scores(base, support, eligible, scales, value, mode)
        check = calibration_check(base, scenarios["safety"], cuts, mode)
        checks.append({"lambda": value, **check})
        if check["pass"]:
            selected = value
    if selected is None:
        raise ValueError("zero correction failed CAL parity")
    return {"selected_lambda": selected, "grid": checks, "mode": mode,
            "rule": "maximum grid value with zero RAW TP withdrawal in every suffix"}


def _mass(weights, mask):
    return float(math.fsum(np.asarray(weights)[np.asarray(mask, dtype=bool)].tolist()))


def _ratio_mass(numerator, denominator):
    return None if denominator == 0 else float(numerator / denominator)


def _event(weights, event, denominator, denominator_mask=None):
    mass = _mass(weights, event)
    result = {"count": int(np.count_nonzero(event)), "weight": mass,
              "pp": None if denominator == 0 else 100.0 * mass / denominator}
    if isinstance(weights, _ExactWeights) and denominator_mask is not None:
        result["exact"] = {"pp": weights.ratio(event, denominator_mask, scale=100)}
    return result


def _rates(labels, weights, decisions, mask):
    normal, attack = mask & (labels == 0), mask & (labels == 1)
    n_mass, a_mass = _mass(weights, normal), _mass(weights, attack)
    fp, tp = _mass(weights, normal & decisions), _mass(weights, attack & decisions)
    fpr, recall = _ratio_mass(fp, n_mass), _ratio_mass(tp, a_mass)
    result = {"normal_count": int(normal.sum()), "attack_count": int(attack.sum()),
            "normal_weight": n_mass, "attack_weight": a_mass,
            "fp_count": int(np.count_nonzero(normal & decisions)),
            "tp_count": int(np.count_nonzero(attack & decisions)),
            "fn_count": int(np.count_nonzero(attack & ~decisions)),
            "fp_weight": fp, "tp_weight": tp, "fn_weight": _mass(weights, attack & ~decisions),
            "fpr": fpr, "recall": recall,
            "fpr_pct": None if fpr is None else 100.0 * fpr,
            "recall_pct": None if recall is None else 100.0 * recall}
    if isinstance(weights, _ExactWeights):
        result["exact"] = {"fpr": weights.ratio(normal & decisions, normal),
                           "recall": weights.ratio(attack & decisions, attack)}
    return result


def _ledger(labels, weights, raw, d0, local, mask):
    attack = mask & (labels == 1)
    denominator = _mass(weights, attack)
    return {"attack_count": int(attack.sum()), "attack_weight": denominator,
            "raw_fn": _event(weights, attack & ~raw, denominator, attack),
            "raw_to_d0": _event(weights, attack & raw & ~d0, denominator, attack),
            "d0_to_local": _event(weights, attack & d0 & ~local, denominator, attack),
            "raw_to_local": _event(weights, attack & raw & ~local, denominator, attack),
            "recovered_raw_fn": _event(weights, attack & ~raw & local, denominator, attack),
            "recovered_d0_fn": _event(weights, attack & ~d0 & local, denominator, attack),
            "local_fn": _event(weights, attack & ~local, denominator, attack)}


def _repair(labels, weights, d0, local, mask):
    normal = mask & (labels == 0)
    den = _mass(weights, normal)
    fp = _mass(weights, normal & d0)
    repaired = _mass(weights, normal & d0 & ~local)
    introduced = _mass(weights, normal & ~d0 & local)
    result = {"normal_weight": den, "d0_fp_weight": fp,
            "repaired_count": int(np.count_nonzero(normal & d0 & ~local)),
            "repaired_weight": repaired, "introduced_fp_weight": introduced,
            "relative_repair": _ratio_mass(repaired, fp),
            "absolute_gain_pp": None if den == 0 else 100.0 * (repaired - introduced) / den}
    if isinstance(weights, _ExactWeights):
        result["exact"] = {
            "relative_repair": weights.ratio(normal & d0 & ~local, normal & d0),
            "absolute_gain_pp": weights.ratio(normal & d0 & ~local, normal, scale=100,
                                               subtract=normal & ~d0 & local)}
    return result


def _group_masks(rows, phases):
    n = len(rows)
    groups, missing = {}, {}
    for field in ("device", "activity", "annotation"):
        values = [row.get(field, row.get("annotation_id") if field == "annotation" else None)
                  for row in rows]
        missing[field] = sum(value is None or str(value) == "" for value in values)
        groups[field] = {str(value): np.array([v == value for v in values], dtype=bool)
                         for value in sorted({v for v in values if v is not None and str(v) != ""}, key=str)}
    phase_values = list(phases) if phases is not None else [row.get("phase") for row in rows]
    if len(phase_values) != n:
        raise ValueError("phase count mismatch")
    missing["phase"] = sum(value is None or str(value) == "" for value in phase_values)
    groups["phase"] = {str(value): np.array([v == value for v in phase_values], dtype=bool)
                       for value in sorted({v for v in phase_values if v is not None and str(v) != ""}, key=str)}
    for field in ("device", "activity"):
        pairs = [(phase_values[i], rows[i].get(field)) for i in range(n)]
        groups[f"phase_{field}"] = {
            repr((str(phase), str(value))): np.array([p == (phase, value) for p in pairs], dtype=bool)
            for phase, value in sorted(set(pairs), key=str)
            if phase is not None and value is not None and str(phase) != "" and str(value) != ""
        }
    return groups, missing


def evaluate_population(*, name, rows, weights, raw, d0, local, cuts, phases=None,
                        branches=None, safety_d0=None, safety_local=None,
                        exposure=None, exposure_branches=None, safety_branch_scores=None,
                        normal_cap=None, mode="source", denominators=None, **metadata):
    """Report a complete fixed population; never drop unexposed rows from rates.

    Exposure is the legal maximum-correction envelope, not observed loss.
    `exposure_branches` supplies donor-union exposure masks when normal own-branch
    labels cannot describe an attack's several legal donor scenarios.
    """
    n = len(rows)
    weight = _finite(weights, "weights", 1)
    if len(weight) != n or np.any(weight <= 0):
        raise ValueError("one strictly positive inherited weight per row required")
    if denominators is not None:
        weight = _ExactWeights(weight, denominators)
    original_labels = np.asarray([row["label"] for row in rows])
    if np.any((original_labels != 0) & (original_labels != 1)):
        raise ValueError("binary labels required")
    labels = original_labels.astype(np.int64)
    scores = {"RAW": score_columns(raw, mode), "D0": score_columns(d0, mode), "L": score_columns(local, mode)}
    if any(value.shape != (n, 4) for value in scores.values()):
        raise ValueError("population score shape mismatch")
    safe = {"RAW": scores["RAW"],
            "D0": scores["D0"] if safety_d0 is None else score_columns(safety_d0, mode),
            "L": scores["L"] if safety_local is None else score_columns(safety_local, mode)}
    if any(value.shape != (n, 4) for value in safe.values()):
        raise ValueError("population safety score shape mismatch")
    cut = _cuts(cuts)
    own_pred = {arm: value > cut for arm, value in scores.items()}
    safety_pred = {arm: value > cut for arm, value in safe.items()}
    all_rows = np.ones(n, dtype=bool)
    groups, missing = _group_masks(rows, phases)
    branch_values = np.asarray(branches if branches is not None else ["OTHER"] * n, dtype=str)
    if branch_values.shape != (n,) or not set(branch_values).issubset(BRANCHES):
        raise ValueError("branch must be 1C, 2C_ZERO, 2C_POS, or OTHER")
    branch_masks = {branch: branch_values == branch for branch in BRANCHES}
    branch_safety = {}
    if safety_branch_scores is not None:
        for branch, pair in safety_branch_scores.items():
            if branch not in BRANCHES:
                raise ValueError("unknown safety donor branch")
            branch_safety[branch] = {key: score_columns(pair[key], mode) for key in ("d0", "local")}
            if any(value.shape != (n, 4) for value in branch_safety[branch].values()):
                raise ValueError("branch donor safety shape mismatch")
            if np.any(branch_safety[branch]["d0"] > scores["RAW"]) or np.any(branch_safety[branch]["local"] > branch_safety[branch]["d0"]):
                raise ValueError("branch donor safety must preserve monotone RAW fallback")
    out = {"name": str(name), "rows": n, "mode": mode, "suffixes": list(SUFFIXES),
           "gate_arithmetic": "exact inverse-integer weights" if denominators is not None else "float64 weights",
           "weights_rule": "inherited parent weights, condition on fixed subset mass",
           "metrics": {}, "safety_metrics": {}, "group_metrics": {},
           "protection": {}, "repairs": {}, "missing_group_fields": missing,
           "monotonic_scores": {
               "own": bool(np.all(scores["D0"] <= scores["RAW"]) and np.all(scores["L"] <= scores["D0"])),
               "safety": bool(np.all(safe["D0"] <= safe["RAW"]) and np.all(safe["L"] <= safe["D0"]))},
           "baseline_monotonic_scores": bool(np.all(scores["D0"] <= scores["RAW"]) and np.all(safe["D0"] <= safe["RAW"]))}
    for arm in scores:
        out["metrics"][arm] = {suffix: _rates(labels, weight, own_pred[arm][:, j], all_rows)
                               for j, suffix in enumerate(SUFFIXES)}
        out["safety_metrics"][arm] = {suffix: _rates(labels, weight, safety_pred[arm][:, j], all_rows)
                                      for j, suffix in enumerate(SUFFIXES)}
        out["group_metrics"][arm] = {
            field: {key: {suffix: _rates(labels, weight, own_pred[arm][:, j], mask)
                          for j, suffix in enumerate(SUFFIXES)} for key, mask in masks.items()}
            for field, masks in groups.items()}
    for view, predictions in (("own", own_pred), ("safety", safety_pred)):
        out["protection"][view] = {}
        for j, suffix in enumerate(SUFFIXES):
            raw_p, d0_p, local_p = (predictions[arm][:, j] for arm in ("RAW", "D0", "L"))
            out["protection"][view][suffix] = {
                "ledger": _ledger(labels, weight, raw_p, d0_p, local_p, all_rows),
                "groups": {field: {key: _ledger(labels, weight, raw_p, d0_p, local_p, mask)
                                   for key, mask in masks.items()} for field, masks in groups.items()},
                "branches": {branch: _ledger(labels, weight, raw_p, d0_p, local_p, mask)
                             for branch, mask in branch_masks.items()},
                "branch_scope": "own-query branch partition"}
            if view == "safety" and safety_branch_scores is not None:
                out["protection"][view][suffix]["branches"] = {
                    branch: _ledger(labels, weight, raw_p,
                                    branch_safety[branch]["d0"][:, j] > cut[j],
                                    branch_safety[branch]["local"][:, j] > cut[j], all_rows)
                    for branch in branch_safety}
                out["protection"][view][suffix]["branch_scope"] = "all legal donors in each branch; UID counted once; full attack denominator"
    for j, suffix in enumerate(SUFFIXES):
        repair = _repair(labels, weight, own_pred["D0"][:, j], own_pred["L"][:, j], all_rows)
        repair["branches"] = {branch: _repair(labels, weight, own_pred["D0"][:, j], own_pred["L"][:, j], mask)
                              for branch, mask in branch_masks.items()}
        repair["devices"] = {key: _repair(labels, weight, own_pred["D0"][:, j], own_pred["L"][:, j], mask)
                             for key, mask in groups["device"].items()}
        repair["repaired_devices"] = sorted(key for key, value in repair["devices"].items() if value["repaired_weight"] > 0)
        out["repairs"][suffix] = repair
    out["normal_capacity"] = {"provided": normal_cap is not None, "suffixes": {}}
    if normal_cap is not None:
        capacity = np.asarray(normal_cap, dtype=bool)
        if capacity.shape != (n, 4) or np.any(capacity & ~((labels == 0)[:, None] & own_pred["D0"])):
            raise ValueError("normal cap must be a subset of normal D0 FP decisions")
        for j, suffix in enumerate(SUFFIXES):
            cap_predictions = own_pred["D0"][:, j] & ~capacity[:, j]
            entry = _repair(labels, weight, own_pred["D0"][:, j], cap_predictions, all_rows)
            entry["branches"] = {
                branch: _repair(labels, weight, own_pred["D0"][:, j], cap_predictions, mask)
                for branch, mask in branch_masks.items()}
            entry["repairable_devices"] = sorted(
                key for key, mask in groups["device"].items()
                if np.any(capacity[:, j] & mask))
            out["normal_capacity"]["suffixes"][suffix] = entry
    exposure_masks = {} if exposure_branches is None else exposure_branches
    out["exposure"] = {"provided": exposure is not None, "suffixes": {}, "branches": {}}
    if exposure is not None:
        exposed = np.asarray(exposure, dtype=bool)
        if exposed.shape != (n, 4):
            raise ValueError("exposure must contain four suffix masks")
        for j, suffix in enumerate(SUFFIXES):
            # Donor-paired D0 TP exposure may coexist with another donor's D0
            # FN.  The union need not be a TP under the minimum D0 score.
            if np.any(exposed[:, j] & (labels == 1) & ~own_pred["RAW"][:, j]):
                raise ValueError("exposure includes an original RAW attack FN")
            attack = labels == 1
            entry = _event(weight, exposed[:, j] & attack, _mass(weight, attack))
            entry["groups"] = {field: {key: _event(weight, exposed[:, j] & attack & mask,
                                                   _mass(weight, attack & mask))
                                       for key, mask in masks.items()} for field, masks in groups.items()}
            out["exposure"]["suffixes"][suffix] = entry
        for branch in BRANCHES:
            mask = np.asarray(exposure_masks.get(branch, exposed & branch_masks[branch][:, None]), dtype=bool)
            if mask.shape != (n, 4) or np.any(mask & ~exposed):
                raise ValueError("branch exposure must be a subset of union exposure")
            out["exposure"]["branches"][branch] = {
                suffix: _event(weight, mask[:, j] & (labels == 1), _mass(weight, labels == 1))
                for j, suffix in enumerate(SUFFIXES)}
        out["exposure"]["branches_without_pressure"] = [
            branch for branch in BRANCHES[:3]
            if not any(value["count"] for value in out["exposure"]["branches"][branch].values())]
        out["exposure"]["branch_evidence"] = {
            branch: ("PROTECTION_EVIDENCE_INSUFFICIENT" if branch in out["exposure"]["branches_without_pressure"]
                     else "CAP_PRESSURE_OBSERVED_NOT_A_SAFETY_CERTIFICATE")
            for branch in BRANCHES[:3]}
    out.update(metadata)
    return out


def evaluate_source_fold(*, lambda_value=None, cal_pass=None, **kwargs):
    return evaluate_population(**kwargs, lambda_value=lambda_value, cal_pass=cal_pass)


def evaluate_target_pool(**kwargs):
    kwargs.setdefault("mode", "target")
    return evaluate_population(**kwargs)


def _guard_failures(report, arm, *, source):
    failures = []
    field_limits = {"device": 1.0, "activity": 5.0}
    if source:
        field_limits.update(phase_device=1.0, phase_activity=5.0)
    else:
        field_limits["annotation"] = 5.0
    event = "raw_to_d0" if arm == "D0" else "raw_to_local"
    for view in ("own", "safety"):
        for suffix in SUFFIXES:
            protection = report["protection"][view][suffix]
            for field, limit in field_limits.items():
                for key, ledger in protection["groups"][field].items():
                    pp = ledger[event]["pp"]
                    if pp is not None and _comparison(ledger[event], "pp", limit) > 0:
                        failures.append(f"{view}/{suffix}/{field}/{key}: cumulative withdrawal {pp:.12g}pp > {limit}pp")
            if source:
                rates = report["metrics"] if view == "own" else report["safety_metrics"]
                raw_recall, new_recall = rates["RAW"][suffix]["recall"], rates[arm][suffix]["recall"]
                if raw_recall is None or new_recall is None:
                    failures.append(f"{view}/{suffix}: missing attack population")
                elif _comparison(rates["RAW"][suffix], "recall", .99) >= 0 and _comparison(rates[arm][suffix], "recall", .99) < 0:
                    failures.append(f"{view}/{suffix}: recall below 99%")
                elif _comparison(rates["RAW"][suffix], "recall", .99) < 0 and protection["ledger"][event]["count"] > 0:
                    failures.append(f"{view}/{suffix}: RAW recall below 99%; further TP withdrawal forbidden")
    return failures


def _report_list(reports):
    return list(reports.values()) if isinstance(reports, Mapping) else list(reports)


def _decision(status, reasons, **extra):
    return {"pass": status == "PASS", "status": status, "reasons": reasons, **extra}


def source_gate(folds, cal_pass=None, lambdas=None):
    reports = _report_list(folds)
    if len(reports) != 2 or len({r["name"] for r in reports}) != 2:
        return _decision("DIAGNOSTIC_COVERAGE_INSUFFICIENT", ["two distinct fold reports required"])
    if cal_pass is False or any(r.get("cal_pass") is False for r in reports):
        return _decision("CAL_GUARD_FAIL", ["D0 and L must retain every RAW CAL TP in all suffixes"])
    if cal_pass is not True and not all(r.get("cal_pass") is True for r in reports):
        return _decision("DIAGNOSTIC_COVERAGE_INSUFFICIENT", ["explicit CAL protection result required"])
    values = list(lambdas.values()) if isinstance(lambdas, Mapping) else lambdas
    if values is None:
        values = [r.get("lambda_value") for r in reports]
    if len(values) != 2 or any(value is None for value in values):
        return _decision("DIAGNOSTIC_COVERAGE_INSUFFICIENT", ["both calibrated lambda values required"])
    if any(float(value) not in LAMBDA_GRID for value in values):
        return _decision("TECHNICAL_LAMBDA_FAIL", ["calibrated lambda outside frozen grid"])
    if any(value == 0 for value in values):
        return _decision("NO_CORRECTION_BUDGET", ["at least one fold selected lambda=0"])
    if any(not r["baseline_monotonic_scores"] for r in reports):
        return _decision("TECHNICAL_SCORE_ORDER_FAIL", ["D0 must not exceed RAW scores"])
    baseline = [f"{r['name']}: {reason}" for r in reports for reason in _guard_failures(r, "D0", source=True)]
    if baseline:
        return _decision("BASELINE_TRANSFER_GUARD_FAIL", baseline)
    if any(not all(r["monotonic_scores"].values()) for r in reports):
        return _decision("TECHNICAL_SCORE_ORDER_FAIL", ["L must not exceed D0; recovered FN cannot offset withdrawals"])
    failures = [f"{r['name']}: {reason}" for r in reports for reason in _guard_failures(r, "L", source=True)]
    if failures:
        return _decision("SAFETY_FAIL", failures)
    missing = []
    for report in reports:
        for field in ("device", "activity", "phase"):
            if report["missing_group_fields"][field]:
                missing.append(f"{report['name']}: missing {field} labels")
        repair = report["repairs"]["ensemble"]
        if repair["d0_fp_weight"] <= 0:
            missing.append(f"{report['name']}: no D0 normal FP mass")
        pressure = report["exposure"]
        if not pressure["provided"] or not any(v["count"] > 0 for v in pressure["suffixes"].values()):
            missing.append(f"{report['name']}: no legal cap-exposed D0 TP pressure")
    repairs = [r["repairs"]["ensemble"] for r in reports]
    if not any(r["branches"]["2C_ZERO"]["d0_fp_weight"] > 0 for r in repairs):
        missing.append("no original eligible 2C zero-support normal FP mass")
    if not any(r["branches"]["1C"]["d0_fp_weight"] > 0 for r in repairs):
        missing.append("no true 1C normal FP mass")
    if not all(r["normal_capacity"]["provided"] for r in reports):
        missing.append("legal maximum-correction normal repair capacity missing")
    else:
        capacities = [r["normal_capacity"]["suffixes"]["ensemble"] for r in reports]
        for report, capacity in zip(reports, capacities):
            if capacity["relative_repair"] is None or _comparison(capacity, "relative_repair", .20) < 0:
                missing.append(f"{report['name']}: even the legal normal cap cannot repair 20% of D0 weighted FP")
        if not any(c["absolute_gain_pp"] is not None and _comparison(c, "absolute_gain_pp", .5) >= 0 for c in capacities):
            missing.append("legal normal cap cannot supply 0.5pp absolute FPR improvement in either fold")
        if len({device for c in capacities for device in c["repairable_devices"]}) < 2:
            missing.append("legal normal cap cannot repair FP on two source devices")
        if not any(c["branches"]["2C_ZERO"]["relative_repair"] is not None and
                   _comparison(c["branches"]["2C_ZERO"], "relative_repair", .10) >= 0 for c in capacities):
            missing.append("legal normal cap cannot repair 10% of original 2C zero-support FP")
        if not any(c["branches"]["1C"]["repaired_weight"] > 0 for c in capacities):
            missing.append("no legal normal cap can cross the cut in the true-1C branch")
    if missing:
        return _decision("DIAGNOSTIC_COVERAGE_INSUFFICIENT", missing)
    reasons = []
    for report, repair in zip(reports, repairs):
        if _comparison(repair, "relative_repair", .20) < 0:
            reasons.append(f"{report['name']}: repairs less than 20% of D0 weighted FP")
    if not any(_comparison(r, "absolute_gain_pp", .5) >= 0 for r in repairs):
        reasons.append("no fold improves absolute FPR by at least 0.5pp")
    devices = {device for repair in repairs for device in repair["repaired_devices"]}
    if len(devices) < 2:
        reasons.append("fewer than two source devices have actual FP repair")
    if not any(r["branches"]["2C_ZERO"]["relative_repair"] is not None and
               _comparison(r["branches"]["2C_ZERO"], "relative_repair", .10) >= 0 for r in repairs):
        reasons.append("no fold repairs 10% of original 2C zero-support weighted FP")
    if not any(r["branches"]["1C"]["repaired_weight"] > 0 for r in repairs):
        reasons.append("no actual true-1C FP crossing")
    return _decision("PRACTICAL_GAIN_GATE_NOT_MET" if reasons else "PASS", reasons,
                     repaired_devices=sorted(devices), independent_confirmation=False)


def target_gate(poolreports, cal_pass=True, required_groups=None):
    reports = _report_list(poolreports)
    if not cal_pass:
        return _decision("CAL_GUARD_FAIL", ["main-head L CAL protection failed"])
    if len(reports) != 2 or len({r["name"] for r in reports}) != 2:
        return _decision("TARGET_COVERAGE_INSUFFICIENT", ["both target pool reports required"])
    reasons, missing = [], []
    for report in reports:
        name = report["name"]
        if not all(report["monotonic_scores"].values()):
            reasons.append(f"{name}: correction score monotonicity violated")
        rate = report["metrics"]["L"]["ensemble"]
        if rate["fpr"] is None or rate["recall"] is None:
            missing.append(f"{name}: missing class denominator")
        else:
            if _comparison(rate, "fpr", .02) > 0:
                reasons.append(f"{name}: ensemble pool FPR exceeds 2%")
            if _comparison(rate, "recall", .99) < 0:
                reasons.append(f"{name}: ensemble pool recall below 99%")
        for device, suffixes in report["group_metrics"]["L"]["device"].items():
            fpr = suffixes["ensemble"]["fpr"]
            if fpr is not None and _comparison(suffixes["ensemble"], "fpr", .02) > 0:
                reasons.append(f"{name}/{device}: ensemble device FPR exceeds 2%")
        fields = (required_groups.get(name) if isinstance(required_groups, Mapping) else required_groups)
        if fields is None:
            fields = ("device", "annotation") if name.upper() in ("B", "UNSW_DEV") else ("device", "activity")
        for field in fields:
            if report["missing_group_fields"][field]:
                missing.append(f"{name}: missing required {field} labels")
        reasons.extend(f"{name}: {reason}" for reason in _guard_failures(report, "L", source=False))
    if missing:
        return _decision("TARGET_COVERAGE_INSUFFICIENT", missing, observed_failures=reasons)
    return _decision("TARGET_CONTRACT_NOT_MET" if reasons else "PASS", reasons,
                     independent_confirmation=False, evaluation_role="development pools")
