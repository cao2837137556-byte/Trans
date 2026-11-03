"""One N1 LP and independently checked exact witnesses; no input-file access."""
from __future__ import annotations

import time
import warnings
from fractions import Fraction

import numpy as np

import issue27frontend_inheritance_n1_support_v1 as s

OPTIONS = {"presolve": True, "time_limit": 600.0, "maxiter": 100000,
           "primal_feasibility_tolerance": 1e-9, "dual_feasibility_tolerance": 1e-9,
           "simplex_dual_edge_weight_strategy": "dantzig"}


class ExactStop(RuntimeError):
    pass


class ExactBudget:
    def __init__(self, global_check=lambda: None, clock=time.monotonic, seconds=120, bits=16384):
        self.global_check, self.clock, self.seconds, self.bits = global_check, clock, seconds, bits
        self.start = clock()

    def check(self):
        self.global_check()
        if self.clock() - self.start > self.seconds:
            raise ExactStop("EXACT_TIME_STOP")

    def bounded(self, value):
        if max(value.numerator.bit_length(), value.denominator.bit_length()) > self.bits:
            raise ExactStop("EXACT_BIT_STOP")
        return value

    def add(self, a, b):
        self.bounded(a)
        self.bounded(b)
        return self.bounded(a + b)

    def mul(self, a, b):
        self.bounded(a)
        self.bounded(b)
        return self.bounded(a * b)

    def div(self, a, b):
        self.bounded(a)
        self.bounded(b)
        return self.bounded(a / b)


def rational(value):
    return Fraction(*float(value).as_integer_ratio())


def fraction_json(value):
    return {"numerator": str(value.numerator), "denominator": str(value.denominator)}


def validate_arrays(features, labels):
    s.require(features.dtype == np.float32 and features.ndim == 2 and features.shape[1] == 64,
              "HEAD_FEATURE_SHAPE_DTYPE")
    s.require(labels.shape == (len(features),) and len(features) > 0
              and np.isfinite(features).all() and np.isin(labels, [0, 1]).all(), "HEAD_FEATURE_LABEL_DRIFT")


def problem(features, labels):
    validate_arrays(features, labels)
    x = np.column_stack((features.astype(np.float64), np.ones(len(features))))
    a = x * (2 * labels.astype(np.float64) - 1)[:, None]
    return a


def finite_or_none(value):
    return float(value) if value is not None and np.isfinite(value) else None


def solve_once(features, labels, budget, solver=None):
    if solver is None:
        from scipy.optimize import linprog
        solver = linprog
    a = problem(features, labels)
    c = np.zeros(66, dtype=np.float64)
    c[-1] = -1
    matrix = np.column_stack((-a, np.ones(len(a))))
    budget.charge(lp_calls=1)
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        result = solver(c, A_ub=matrix, b_ub=np.zeros(len(a)), bounds=[(-1, 1)] * 65 + [(None, None)],
                        method="highs-ds", options=dict(OPTIONS))
    budget.check()
    status = int(result.status)
    x = getattr(result, "x", None)
    marginal = getattr(getattr(result, "ineqlin", None), "marginals", None)
    receipt = {"status": status, "message": str(result.message), "iterations": int(result.nit),
               "method": "highs-ds", "options": OPTIONS,
               "warnings": [{"category": w.category.__name__, "message": str(w.message)} for w in captured],
               "coefficients_float64": None if x is None else [finite_or_none(v) for v in x],
               "inequality_marginals": None if marginal is None else [finite_or_none(v) for v in marginal]}
    return a, result, receipt


def sole_candidate(result):
    status = int(result.status)
    s.require(status not in {2, 3}, "LP_INFEASIBLE_OR_UNBOUNDED")
    if status not in {0, 1} or getattr(result, "x", None) is None:
        return None
    vector = np.asarray(result.x, dtype=np.float64)
    if vector.shape != (66,) or not np.isfinite(vector[:65]).all():
        return None
    with np.errstate(over="ignore", invalid="ignore"):
        theta = vector[:65].astype(np.float32)
    s.require(np.isfinite(theta).all() and (np.abs(theta) <= 1).all(), "SOLE_CANDIDATE_CAST_RANGE")
    return theta


def exact_signs(features, labels, theta, stage):
    validate_arrays(features, labels)
    s.require(theta.dtype == np.float32 and theta.shape == (65,) and np.isfinite(theta).all(),
              "EXACT_CANDIDATE_IDENTITY")
    weights = [rational(v) for v in theta]
    wrong, ties, minimum, benign_slack = [], 0, None, None
    try:
        for i, row in enumerate(features):
            stage.check()
            q = weights[-1]
            for weight, value in zip(weights[:-1], row):
                q = stage.add(q, stage.mul(weight, rational(value)))
            attack = bool(labels[i])
            if (q >= 0) != attack:
                wrong.append(i)
            signed = q if attack else -q
            minimum = signed if minimum is None else min(minimum, signed)
            if attack and q == 0:
                ties += 1
            if not attack:
                benign_slack = -q if benign_slack is None else min(benign_slack, -q)
        stage.check()
        return {"status": "VERIFIED", "pass": not wrong, "wrong_row_indices": wrong,
                "minimum_signed_margin": fraction_json(minimum),
                "minimum_benign_slack": None if benign_slack is None else fraction_json(benign_slack),
                "zero_margin_attack_ties": ties}
    except ExactStop as exc:
        return {"status": str(exc), "pass": False, "verified_rows": i if "i" in locals() else 0}


def reconstruct(a, support, stage):
    # Fixed-column rational RREF, then free variables zero; no support search.
    matrix = [[rational(a[index, coordinate]) for index in support] + [Fraction(0)]
              for coordinate in range(65)]
    matrix.append([Fraction(1)] * len(support) + [Fraction(1)])
    pivots, pivot_row = [], 0
    for column in range(len(support)):
        stage.check()
        found = next((r for r in range(pivot_row, 66) if matrix[r][column]), None)
        if found is None:
            continue
        matrix[pivot_row], matrix[found] = matrix[found], matrix[pivot_row]
        scale = matrix[pivot_row][column]
        matrix[pivot_row] = [stage.div(v, scale) for v in matrix[pivot_row]]
        for row in range(66):
            stage.check()
            if row == pivot_row or not matrix[row][column]:
                continue
            factor = matrix[row][column]
            matrix[row] = [stage.add(v, -stage.mul(factor, p))
                           for v, p in zip(matrix[row], matrix[pivot_row])]
        pivots.append((pivot_row, column))
        pivot_row += 1
    if any(not any(row[:-1]) and row[-1] for row in matrix):
        return None
    values = [Fraction(0)] * len(support)
    for row, column in pivots:
        values[column] = matrix[row][-1]
    return values


def verify_certificate(a, support, values, stage):
    if not (0 < len(support) <= 66 and len(values) == len(support)
            and len(set(support)) == len(support) and all(0 <= i < len(a) for i in support)):
        return False
    total = Fraction(0)
    for value in values:
        stage.check()
        if value < 0:
            return False
        total = stage.add(total, value)
    if total != 1:
        return False
    for coordinate in range(65):
        stage.check()
        total = Fraction(0)
        for index, value in zip(support, values):
            total = stage.add(total, stage.mul(rational(a[index, coordinate]), value))
        if total != 0:
            return False
    return True


def certificate(a, result, exact_pass, stage):
    if exact_pass:
        return {"status": "SKIPPED_EXACT_THRESHOLD_WITNESS", "verified": False}
    if int(result.status) != 0:
        return {"status": "UNAVAILABLE_NONOPTIMAL", "verified": False}
    marginals = getattr(getattr(result, "ineqlin", None), "marginals", None)
    if marginals is None or np.shape(marginals) != (len(a),):
        return {"status": "UNAVAILABLE_MARGINALS", "verified": False}
    raw = -np.asarray(marginals, dtype=np.float64)
    support = np.flatnonzero(np.isfinite(raw) & (raw > 0)).tolist()
    if not 0 < len(support) <= 66:
        return {"status": "UNAVAILABLE_SUPPORT", "support_count": len(support), "verified": False}
    try:
        stage.check()
        values = reconstruct(a, support, stage)
        if values is None:
            return {"status": "INCONSISTENT_SUPPORT", "verified": False, "support": support}
        passed = verify_certificate(a, support, values, stage)
        stage.check()
        return {"status": "VERIFIED" if passed else "RECONSTRUCTION_NOT_CERTIFICATE", "verified": passed,
                "support": support, "lambda": [fraction_json(v) for v in values],
                "scope": "EXACT_REAL_AFFINE_FIXED_TERMINAL_64D_ONLY"}
    except ExactStop as exc:
        return {"status": str(exc), "verified": False, "support": support}


def verdict(exact_pass, replay_pass, negative, stop=None):
    if stop is not None:
        return {"status": "N1_ENGINEERING_STOP", "reason": stop}
    s.require(not (exact_pass and negative), "VERIFIER_INTEGRITY_CONTRADICTION")
    descriptor = ("JOINT_EXACT_FLOAT32_FIT" if exact_pass and replay_pass else
                  "EXACT_AFFINE_WITNESS_FLOAT32_REPLAY_MISMATCH" if exact_pass else
                  "FLOAT32_ONLY_FIT" if replay_pass else "NO_VERIFIED_FIT")
    status = ("N1_JOINT_HEAD_WITNESS" if exact_pass and replay_pass else
              "N1_EXACT_AFFINE_NONSEPARABLE" if negative else "N1_NUMERICAL_UNKNOWN")
    return {"status": status, "fit_descriptor": descriptor,
            "inheritance": "NOT_PROVED", "F5_eligible": False, "deployment": False,
            "B_utility": "NOT_EVALUATED", "K": "NOT_AUTHORIZED"}
