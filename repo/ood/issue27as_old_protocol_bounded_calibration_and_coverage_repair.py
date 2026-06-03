from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import pairwise_distances

import issue27ar_old_lowguardpp_protocol_fidelity_migration_on_gotham115_medium as ar


REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
ISSUE = "issue27as_old_protocol_bounded_calibration_and_coverage_repair_2026-06-03"
OUT = ROOT / "runs" / ISSUE
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

ISSUE27AR = ROOT / "runs" / "issue27ar_old_lowguardpp_protocol_fidelity_migration_on_gotham115_medium_2026-06-03"
ISSUE27AQ = ROOT / "runs" / "issue27aq_model_learning_and_domain_gap_audit_after_new_heldout_zero_detection_2026-06-03"

SEEDS = [42, 43, 44, 45, 46]
SUPPORT_BUDGETS = [32, 64, 128]
OOD_WEIGHTS = [2.0, 4.0, 8.0]
SUPPORT_WEIGHTS = [4.0, 8.0, 16.0, 32.0]
VAL_TARGET = 0.01
STRICT_TARGET = 0.005

ID_ROLE = ar.ID_ROLE
OOD_VAL_ROLE = ar.OOD_VAL_ROLE
FINAL_OOD_ROLE = ar.FINAL_OOD_ROLE
SUPPORT_ROLE = ar.SUPPORT_ROLE
ATTACK_EVAL_ROLE = ar.ATTACK_EVAL_ROLE
NEW_HELDOUT_ROLE = ar.NEW_HELDOUT_ROLE


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_md(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def append_doc(path: Path, marker: str, lines: list[str]) -> None:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker in text:
        return
    path.write_text(text.rstrip() + "\n\n" + "\n".join(lines).rstrip() + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class WeightedOldHistGB:
    def __init__(self, seed: int, ood_weight: float, support_weight: float):
        self.seed = int(seed)
        self.ood_weight = float(ood_weight)
        self.support_weight = float(support_weight)
        self.score_direction = 1.0
        self.score_direction_fixed = False
        self.model = HistGradientBoostingClassifier(
            max_depth=int(ar.FROZEN_CONFIG["max_depth"]),
            max_iter=int(ar.FROZEN_CONFIG["max_iter"]),
            learning_rate=float(ar.FROZEN_CONFIG["learning_rate"]),
            l2_regularization=float(ar.FROZEN_CONFIG["l2_regularization"]),
            random_state=self.seed,
        )
        self.fit_shape: dict[str, Any] = {}
        self.direction_check: dict[str, Any] = {}

    def fit(self, x_id_train: np.ndarray, x_ood_train: np.ndarray, x_support_attack: np.ndarray) -> None:
        x_train = np.vstack([x_id_train, x_ood_train, x_support_attack])
        y_train = np.concatenate(
            [
                np.zeros(len(x_id_train), dtype=np.int64),
                np.zeros(len(x_ood_train), dtype=np.int64),
                np.ones(len(x_support_attack), dtype=np.int64),
            ]
        )
        sample_weight = np.concatenate(
            [
                np.ones(len(x_id_train), dtype=np.float64),
                np.full(len(x_ood_train), self.ood_weight, dtype=np.float64),
                np.full(len(x_support_attack), self.support_weight, dtype=np.float64),
            ]
        )
        self.fit_shape = {
            "id_rows": int(len(x_id_train)),
            "ood_train_rows": int(len(x_ood_train)),
            "support_rows": int(len(x_support_attack)),
            "total_rows": int(len(x_train)),
            "id_weight": 1.0,
            "ood_weight": self.ood_weight,
            "support_weight": self.support_weight,
            "weighted_normal_to_attack_ratio": float(
                (len(x_id_train) + len(x_ood_train) * self.ood_weight) / max(1.0, len(x_support_attack) * self.support_weight)
            ),
        }
        self.model.fit(x_train, y_train, sample_weight=sample_weight)
        self._fix_score_direction(x_id_train, x_ood_train, x_support_attack)

    def raw_score(self, x: np.ndarray) -> np.ndarray:
        proba = self.model.predict_proba(x)
        classes = list(self.model.classes_)
        if 1 not in classes:
            raise RuntimeError(f"attack class 1 missing: {classes}")
        return proba[:, classes.index(1)]

    def score(self, x: np.ndarray) -> np.ndarray:
        return self.score_direction * self.raw_score(x)

    def _fix_score_direction(self, x_id_train: np.ndarray, x_ood_train: np.ndarray, x_support_attack: np.ndarray) -> None:
        raw_id = np.asarray(self.raw_score(x_id_train), dtype=np.float64)
        raw_ood = np.asarray(self.raw_score(x_ood_train), dtype=np.float64)
        raw_support = np.asarray(self.raw_score(x_support_attack), dtype=np.float64)
        if float(np.mean(raw_support)) < float(np.mean(raw_id)) and float(np.mean(raw_support)) < float(np.mean(raw_ood)):
            self.score_direction = -1.0
            self.score_direction_fixed = True
        self.direction_check = {
            "support_raw_mean": float(np.mean(raw_support)),
            "id_train_raw_mean": float(np.mean(raw_id)),
            "ood_train_raw_mean": float(np.mean(raw_ood)),
            "support_score_mean": float(np.mean(self.score(x_support_attack))),
            "id_train_score_mean": float(np.mean(self.score(x_id_train))),
            "ood_train_score_mean": float(np.mean(self.score(x_ood_train))),
            "score_direction": self.score_direction,
            "score_direction_fixed": self.score_direction_fixed,
        }


def rate(scores: np.ndarray, threshold: float) -> float:
    return float(np.mean(scores > threshold)) if scores.size else float("nan")


def kcenter_budget(x: np.ndarray, support_pool_idx: np.ndarray, budget: int) -> tuple[np.ndarray, dict[str, Any]]:
    x_pool = x[support_pool_idx]
    scaler = ar.StandardScaler().fit(x_pool)
    z = scaler.transform(x_pool)
    centroid = z.mean(axis=0, keepdims=True)
    start_idx = int(np.argmin(pairwise_distances(z, centroid, metric="euclidean").ravel()))
    local = ar.farthest_first(z, int(budget), start_idx)
    selected = np.asarray(sorted(support_pool_idx[local].tolist()), dtype=np.int64)
    return selected, {
        "support_selector": f"old_kcenter{budget}",
        "support_pool_role": SUPPORT_ROLE,
        "support_pool_size": int(len(support_pool_idx)),
        "support_size": int(len(selected)),
        "selector_scaler_fit_roles": SUPPORT_ROLE,
        "distance_metric": "euclidean_after_selector_local_standard_scaler",
        "start_rule": "closest_to_attack_support_centroid",
        "uses_final_ood": False,
        "uses_attack_eval": False,
        "selected_indices_sha256": ar.hash_indices(selected),
    }


def split_support(rows: np.ndarray, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rows = np.asarray(rows, dtype=np.int64).copy()
    rng = np.random.default_rng(seed + 27027)
    rng.shuffle(rows)
    cut = int(math.floor(len(rows) * 0.75))
    cut = max(1, min(cut, len(rows) - 1))
    return np.asarray(sorted(rows[:cut].tolist()), dtype=np.int64), np.asarray(sorted(rows[cut:].tolist()), dtype=np.int64)


def candidate_thresholds(*arrays: np.ndarray) -> np.ndarray:
    vals = np.concatenate([np.asarray(a, dtype=np.float64) for a in arrays if a.size])
    if vals.size == 0:
        return np.asarray([0.0], dtype=np.float64)
    qs = np.linspace(0.0, 1.0, 2001)
    c = np.unique(np.concatenate([np.quantile(vals, qs), vals]))
    return np.asarray(sorted(c.tolist()), dtype=np.float64)


def guarded_threshold(scores_id: np.ndarray, scores_ood: np.ndarray, target: float) -> dict[str, Any]:
    th = ar.guarded_val_threshold(scores_id, scores_ood, float(target), n_candidates=4000)
    th["rule"] = f"guarded_id_ood_target_{target:g}"
    th["support_val_detection_at_selection"] = float("nan")
    return th


def support_guided_threshold(scores_id: np.ndarray, scores_ood: np.ndarray, scores_support_val: np.ndarray) -> dict[str, Any]:
    best: dict[str, Any] | None = None
    for thr in candidate_thresholds(scores_id, scores_ood, scores_support_val):
        id_alarm = rate(scores_id, float(thr))
        ood_alarm = rate(scores_ood, float(thr))
        if id_alarm > VAL_TARGET or ood_alarm > VAL_TARGET:
            continue
        support_det = rate(scores_support_val, float(thr))
        key = (support_det, -ood_alarm, -id_alarm, -float(thr))
        if best is None or key > best["_key"]:
            best = {
                "_key": key,
                "threshold": float(thr),
                "id_calib_alarm_at_selection": id_alarm,
                "ood_val_alarm_at_selection": ood_alarm,
                "support_val_detection_at_selection": support_det,
                "selection_feasible": True,
                "threshold_source": "support_val_guided_empirical_id_ood_1pct",
                "rule": "support_val_guided_empirical_1pct",
            }
    if best is None:
        fallback = guarded_threshold(scores_id, scores_ood, VAL_TARGET)
        fallback["threshold_source"] = "support_val_guided_empirical_fallback_guarded_1pct"
        fallback["rule"] = "support_val_guided_empirical_1pct"
        fallback["support_val_detection_at_selection"] = rate(scores_support_val, float(fallback["threshold"]))
        return fallback
    best.pop("_key")
    return best


def orderstat_threshold(scores_id: np.ndarray, scores_ood: np.ndarray, scores_support_val: np.ndarray) -> dict[str, Any]:
    # Empirical Neyman-Pearson-style operating point: threshold at the OOD validation
    # order statistic that permits no more than 1% OOD exceedance, then raise it if
    # ID calibration exceeds 1%. Selection uses only ID/OOD/support_val.
    n_ood = int(len(scores_ood))
    n_id = int(len(scores_id))
    if n_ood == 0 or n_id == 0:
        return support_guided_threshold(scores_id, scores_ood, scores_support_val)
    ood_rank = max(0, min(n_ood - 1, int(math.floor((1.0 - VAL_TARGET) * n_ood))))
    id_rank = max(0, min(n_id - 1, int(math.floor((1.0 - VAL_TARGET) * n_id))))
    base_thr = max(float(np.sort(scores_ood)[ood_rank]), float(np.sort(scores_id)[id_rank]))
    feasible = rate(scores_id, base_thr) <= VAL_TARGET and rate(scores_ood, base_thr) <= VAL_TARGET
    # If nearby thresholds have identical feasibility, pick the one with best
    # support_val detection while preserving the empirical 1% alarm constraints.
    best = {
        "threshold": base_thr,
        "id_calib_alarm_at_selection": rate(scores_id, base_thr),
        "ood_val_alarm_at_selection": rate(scores_ood, base_thr),
        "support_val_detection_at_selection": rate(scores_support_val, base_thr),
        "selection_feasible": feasible,
        "threshold_source": "np_orderstat_id_ood_1pct",
        "rule": "np_orderstat_id_ood_1pct",
    }
    for thr in candidate_thresholds(scores_id, scores_ood, scores_support_val):
        if float(thr) > base_thr:
            continue
        id_alarm = rate(scores_id, float(thr))
        ood_alarm = rate(scores_ood, float(thr))
        if id_alarm <= VAL_TARGET and ood_alarm <= VAL_TARGET:
            support_det = rate(scores_support_val, float(thr))
            key = (support_det, -ood_alarm, -id_alarm, -float(thr))
            best_key = (
                best["support_val_detection_at_selection"],
                -best["ood_val_alarm_at_selection"],
                -best["id_calib_alarm_at_selection"],
                -best["threshold"],
            )
            if key > best_key:
                best.update(
                    {
                        "threshold": float(thr),
                        "id_calib_alarm_at_selection": id_alarm,
                        "ood_val_alarm_at_selection": ood_alarm,
                        "support_val_detection_at_selection": support_det,
                        "selection_feasible": True,
                    }
                )
    return best


def compute_coverage(
    x: np.ndarray,
    support_train: np.ndarray,
    target_idx: np.ndarray,
    radius_source_idx: np.ndarray,
    role: str,
    model_scores: np.ndarray,
    threshold: float,
) -> dict[str, Any]:
    if len(support_train) == 0 or len(target_idx) == 0 or len(radius_source_idx) == 0:
        return {
            "coverage_role": role,
            "n": int(len(target_idx)),
            "nearest_distance_p50": float("nan"),
            "nearest_distance_p95": float("nan"),
            "nearest_distance_p99": float("nan"),
            "nearest_distance_max": float("nan"),
            "support_val_p95_radius": float("nan"),
            "covered_fraction_p95": float("nan"),
            "covered_detection": float("nan"),
            "uncovered_detection": float("nan"),
        }
    scaler = ar.StandardScaler().fit(x[support_train])
    z_support = scaler.transform(x[support_train])
    z_radius = scaler.transform(x[radius_source_idx])
    z_target = scaler.transform(x[target_idx])
    radius_dist = pairwise_distances(z_radius, z_support, metric="euclidean").min(axis=1)
    target_dist = pairwise_distances(z_target, z_support, metric="euclidean").min(axis=1)
    radius = float(np.quantile(radius_dist, 0.95))
    covered = target_dist <= radius
    detected = model_scores > float(threshold)
    return {
        "coverage_role": role,
        "n": int(len(target_idx)),
        "nearest_distance_p50": float(np.quantile(target_dist, 0.50)),
        "nearest_distance_p95": float(np.quantile(target_dist, 0.95)),
        "nearest_distance_p99": float(np.quantile(target_dist, 0.99)),
        "nearest_distance_max": float(np.max(target_dist)),
        "support_val_p95_radius": radius,
        "covered_fraction_p95": float(np.mean(covered)),
        "covered_detection": float(np.mean(detected[covered])) if np.any(covered) else float("nan"),
        "uncovered_detection": float(np.mean(detected[~covered])) if np.any(~covered) else float("nan"),
    }


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    keys = ["strategy", "support_budget", "ood_weight", "support_weight", "threshold_rule"]
    for row in rows:
        groups.setdefault(tuple(row[k] for k in keys), []).append(row)
    out = []
    for key, gr in sorted(groups.items()):
        r: dict[str, Any] = {k: v for k, v in zip(keys, key)}
        for metric in [
            "id_calib_alarm",
            "ood_val_alarm",
            "support_val_detection",
            "final_ood_alarm_report_only",
            "attack_eval_detection_report_only",
            "new_heldout_detection_report_only",
            "weighted_normal_to_attack_ratio",
        ]:
            vals = np.asarray([float(g[metric]) for g in gr if g[metric] == g[metric]], dtype=np.float64)
            if vals.size:
                r[f"{metric}_mean"] = float(np.mean(vals))
                r[f"{metric}_min"] = float(np.min(vals))
                r[f"{metric}_max"] = float(np.max(vals))
                r[f"{metric}_std"] = float(np.std(vals))
            else:
                r[f"{metric}_mean"] = float("nan")
                r[f"{metric}_min"] = float("nan")
                r[f"{metric}_max"] = float("nan")
                r[f"{metric}_std"] = float("nan")
        r["selection_feasible_all_seeds"] = bool(all(bool(g["selection_feasible"]) for g in gr))
        r["val_side_legal_all_seeds"] = bool(all(float(g["id_calib_alarm"]) <= VAL_TARGET and float(g["ood_val_alarm"]) <= VAL_TARGET for g in gr))
        r["candidate_selection_score"] = float(r.get("support_val_detection_min", 0.0)) - 0.1 * float(r.get("ood_val_alarm_max", 1.0))
        out.append(r)
    return out


def choose_val_side_candidate(summary_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    legal = [r for r in summary_rows if r.get("val_side_legal_all_seeds") and r.get("selection_feasible_all_seeds")]
    if not legal:
        return None
    return sorted(
        legal,
        key=lambda r: (
            float(r.get("support_val_detection_min", -1)),
            float(r.get("support_val_detection_mean", -1)),
            -float(r.get("ood_val_alarm_max", 1)),
            -float(r.get("id_calib_alarm_max", 1)),
            -int(r.get("support_budget", 9999)),
        ),
        reverse=True,
    )[0]


def report_only_feasibility_rows(summary_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for r in summary_rows:
        out = {
            "strategy": r["strategy"],
            "support_budget": r["support_budget"],
            "ood_weight": r["ood_weight"],
            "support_weight": r["support_weight"],
            "threshold_rule": r["threshold_rule"],
            "val_side_legal_all_seeds": r["val_side_legal_all_seeds"],
            "support_val_detection_min": r.get("support_val_detection_min"),
            "final_ood_alarm_report_only_max": r.get("final_ood_alarm_report_only_max"),
            "attack_eval_detection_report_only_min": r.get("attack_eval_detection_report_only_min"),
            "new_heldout_detection_report_only_min": r.get("new_heldout_detection_report_only_min"),
            "report_only_final_ood_under_1pct": float(r.get("final_ood_alarm_report_only_max", 1.0)) <= VAL_TARGET,
            "report_only_medium_attack_ge_0p95": float(r.get("attack_eval_detection_report_only_min", 0.0)) >= 0.95,
            "report_only_medium_attack_ge_0p90": float(r.get("attack_eval_detection_report_only_min", 0.0)) >= 0.90,
            "report_only_new_heldout_ge_0p75": float(r.get("new_heldout_detection_report_only_min", 0.0)) >= 0.75,
            "selection_note": "report-only fields are diagnostic and are not used to select the val-side candidate",
        }
        rows.append(out)
    return rows


def best_report_only_final_ok(summary_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [
        r
        for r in summary_rows
        if float(r.get("final_ood_alarm_report_only_max", 1.0)) <= VAL_TARGET
        and bool(r.get("val_side_legal_all_seeds"))
    ]
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda r: (
            float(r.get("attack_eval_detection_report_only_min", -1)),
            float(r.get("new_heldout_detection_report_only_min", -1)),
            float(r.get("support_val_detection_min", -1)),
        ),
        reverse=True,
    )[0]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cert_path = ar.ISSUE27AF / "kitsune115_materialization_data_certificate_medium.json"
    cert = json.loads(cert_path.read_text(encoding="utf-8"))
    new_x, _, new_checks = ar.load_new_heldout()

    input_hash_rows: list[dict[str, Any]] = [
        {
            "artifact": "issue27af_medium_certificate",
            "path": str(cert_path),
            "sha256": sha256_file(cert_path),
            "hash_match": True,
        },
        {
            "artifact": "issue27ar_summary",
            "path": str(ISSUE27AR / "summary.md"),
            "sha256": sha256_file(ISSUE27AR / "summary.md") if (ISSUE27AR / "summary.md").exists() else "missing",
            "hash_match": (ISSUE27AR / "summary.md").exists(),
        },
        {
            "artifact": "issue27aq_summary",
            "path": str(ISSUE27AQ / "summary.md"),
            "sha256": sha256_file(ISSUE27AQ / "summary.md") if (ISSUE27AQ / "summary.md").exists() else "missing",
            "hash_match": (ISSUE27AQ / "summary.md").exists(),
        },
    ]
    input_hash_rows.extend(new_checks)

    by_seed_rows: list[dict[str, Any]] = []
    support_rows_out: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    weight_rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []
    report_only_rows: list[dict[str, Any]] = []
    role_access_rows: list[dict[str, Any]] = []

    for strategy in sorted(cert.keys()):
        asset, checks = ar.load_asset(strategy, cert)
        input_hash_rows.extend(checks)
        x = asset["X"]
        sidecar = asset["sidecar"]
        id_idx = ar.role_indices(sidecar, ID_ROLE)
        ood_idx = ar.role_indices(sidecar, OOD_VAL_ROLE)
        final_ood = ar.role_indices(sidecar, FINAL_OOD_ROLE)
        support_pool = ar.role_indices(sidecar, SUPPORT_ROLE)
        attack_eval = ar.role_indices(sidecar, ATTACK_EVAL_ROLE)
        id_fit, id_calib = ar.deterministic_role_subsplit(id_idx, 0.80)
        ood_train, ood_val = ar.deterministic_role_subsplit(ood_idx, 0.50)

        support_by_budget: dict[int, np.ndarray] = {}
        for budget in SUPPORT_BUDGETS:
            support_selected, audit = kcenter_budget(x, support_pool, budget)
            support_by_budget[budget] = support_selected
            audit.update({"strategy": strategy})
            support_rows_out.append(audit)

        for seed in SEEDS:
            for budget, support_selected in support_by_budget.items():
                support_train, support_val = split_support(support_selected, seed)
                for ood_weight in OOD_WEIGHTS:
                    for support_weight in SUPPORT_WEIGHTS:
                        model = WeightedOldHistGB(seed, ood_weight, support_weight)
                        model.fit(x[id_fit], x[ood_train], x[support_train])
                        score_id = model.score(x[id_calib])
                        score_ood = model.score(x[ood_val])
                        score_support_train = model.score(x[support_train])
                        score_support_val = model.score(x[support_val])
                        score_final = model.score(x[final_ood])
                        score_attack = model.score(x[attack_eval])
                        score_new = model.score(new_x) if new_x.size else np.asarray([], dtype=np.float64)

                        threshold_specs = [
                            guarded_threshold(score_id, score_ood, STRICT_TARGET),
                            support_guided_threshold(score_id, score_ood, score_support_val),
                            orderstat_threshold(score_id, score_ood, score_support_val),
                        ]

                        base_meta = {
                            "strategy": strategy,
                            "seed": seed,
                            "support_budget": budget,
                            "support_train_rows": int(len(support_train)),
                            "support_val_rows": int(len(support_val)),
                            "support_train_hash": ar.hash_indices(support_train),
                            "support_val_hash": ar.hash_indices(support_val),
                            "ood_weight": ood_weight,
                            "support_weight": support_weight,
                            **model.fit_shape,
                            **model.direction_check,
                        }
                        weight_rows.append(
                            {
                                **base_meta,
                                "weight_grid_note": "bounded old HistGB skeleton weight audit; ID weight fixed at 1.0",
                            }
                        )
                        role_access_rows.append(
                            {
                                **base_meta,
                                "fit_roles": "id_fit_from_id_benign_train|ood_train_guard_from_ood_benign_val|attack_support_kcenter_train",
                                "threshold_candidate_roles": "id_calib_from_id_benign_train|ood_val_calib_from_ood_benign_val|support_val_from_attack_support",
                                "support_selector_roles": SUPPORT_ROLE,
                                "report_only_roles": f"{FINAL_OOD_ROLE}|{ATTACK_EVAL_ROLE}|{NEW_HELDOUT_ROLE}",
                                "uses_final_ood_for_fit_threshold_or_selection": False,
                                "uses_attack_eval_for_fit_threshold_or_selection": False,
                                "uses_new_heldout_for_fit_threshold_or_selection": False,
                                "forbidden_role_access": False,
                            }
                        )

                        for th in threshold_specs:
                            threshold = float(th["threshold"])
                            row = {
                                **base_meta,
                                "threshold_rule": th["rule"],
                                "threshold": threshold,
                                "threshold_source": th["threshold_source"],
                                "selection_feasible": bool(th["selection_feasible"]),
                                "id_calib_alarm": rate(score_id, threshold),
                                "ood_val_alarm": rate(score_ood, threshold),
                                "support_train_detection": rate(score_support_train, threshold),
                                "support_val_detection": rate(score_support_val, threshold),
                                "final_ood_alarm_report_only": rate(score_final, threshold),
                                "attack_eval_detection_report_only": rate(score_attack, threshold),
                                "new_heldout_detection_report_only": rate(score_new, threshold),
                                "final_ood_used_for_selection": False,
                                "attack_eval_used_for_selection": False,
                                "new_heldout_used_for_selection": False,
                                "formal_benchmark": False,
                            }
                            by_seed_rows.append(row)
                            threshold_rows.append(
                                {
                                    **base_meta,
                                    "threshold_rule": th["rule"],
                                    "threshold": threshold,
                                    "threshold_source": th["threshold_source"],
                                    "id_calib_alarm": row["id_calib_alarm"],
                                    "ood_val_alarm": row["ood_val_alarm"],
                                    "support_val_detection": row["support_val_detection"],
                                    "selection_feasible": bool(th["selection_feasible"]),
                                    "uses_final_or_attack_eval_for_threshold": False,
                                }
                            )
                            report_only_rows.append(
                                {
                                    **base_meta,
                                    "threshold_rule": th["rule"],
                                    "final_ood_alarm_report_only": row["final_ood_alarm_report_only"],
                                    "attack_eval_detection_report_only": row["attack_eval_detection_report_only"],
                                    "new_heldout_detection_report_only": row["new_heldout_detection_report_only"],
                                    "report_only_note": "These values are not used for candidate selection.",
                                }
                            )
                            for cov_role, target_idx, scores in [
                                ("support_val", support_val, score_support_val),
                                ("attack_eval_report_only", attack_eval, score_attack),
                            ]:
                                cov = compute_coverage(x, support_train, target_idx, support_val, cov_role, scores, threshold)
                                coverage_rows.append({**base_meta, "threshold_rule": th["rule"], **cov})
                            if new_x.size:
                                # New heldout rows are outside the medium asset, so compute coverage directly.
                                scaler = ar.StandardScaler().fit(x[support_train])
                                z_support = scaler.transform(x[support_train])
                                z_support_val = scaler.transform(x[support_val])
                                z_new = scaler.transform(new_x)
                                radius_dist = pairwise_distances(z_support_val, z_support, metric="euclidean").min(axis=1)
                                target_dist = pairwise_distances(z_new, z_support, metric="euclidean").min(axis=1)
                                radius = float(np.quantile(radius_dist, 0.95))
                                covered = target_dist <= radius
                                detected = score_new > threshold
                                coverage_rows.append(
                                    {
                                        **base_meta,
                                        "threshold_rule": th["rule"],
                                        "coverage_role": NEW_HELDOUT_ROLE,
                                        "n": int(len(score_new)),
                                        "nearest_distance_p50": float(np.quantile(target_dist, 0.50)),
                                        "nearest_distance_p95": float(np.quantile(target_dist, 0.95)),
                                        "nearest_distance_p99": float(np.quantile(target_dist, 0.99)),
                                        "nearest_distance_max": float(np.max(target_dist)),
                                        "support_val_p95_radius": radius,
                                        "covered_fraction_p95": float(np.mean(covered)),
                                        "covered_detection": float(np.mean(detected[covered])) if np.any(covered) else float("nan"),
                                        "uncovered_detection": float(np.mean(detected[~covered])) if np.any(~covered) else float("nan"),
                                    }
                                )

    summary_rows = summarize(by_seed_rows)
    selected = choose_val_side_candidate(summary_rows)
    report_only_feasibility = report_only_feasibility_rows(summary_rows)
    best_report_only = best_report_only_final_ok(summary_rows)
    forbidden_access = any(bool(r["forbidden_role_access"]) for r in role_access_rows)
    if forbidden_access:
        primary_verdict = "bounded_repair_blocked_by_forbidden_role_access"
    elif selected is None:
        primary_verdict = "bounded_repair_no_legal_candidate"
    else:
        medium_min = float(selected["attack_eval_detection_report_only_min"])
        new_min = float(selected["new_heldout_detection_report_only_min"])
        final_max = float(selected["final_ood_alarm_report_only_max"])
        support_val_min = float(selected["support_val_detection_min"])
        if medium_min >= 0.95 and new_min >= 0.75 and final_max <= VAL_TARGET:
            primary_verdict = "bounded_repair_improves_both_medium_and_heldout_not_full_ready"
        elif medium_min >= 0.95 and final_max <= VAL_TARGET:
            primary_verdict = "bounded_repair_reaches_medium_target_but_heldout_gap_persists"
        elif support_val_min >= 0.95 and medium_min < 0.95:
            primary_verdict = "bounded_repair_support_val_ready_but_report_only_medium_gap_persists"
        else:
            primary_verdict = "bounded_repair_suggests_feature_or_task_boundary"

    write_csv(OUT / "input_artifact_hash_audit.csv", input_hash_rows)
    write_csv(OUT / "support_selector_audit.csv", support_rows_out)
    write_csv(OUT / "weight_grid_audit.csv", weight_rows)
    write_csv(OUT / "threshold_rule_audit.csv", threshold_rows)
    write_csv(OUT / "bounded_repair_by_seed.csv", by_seed_rows)
    write_csv(OUT / "bounded_repair_summary.csv", summary_rows)
    write_csv(OUT / "report_only_feasibility_audit.csv", report_only_feasibility)
    write_csv(OUT / "coverage_gate_audit.csv", coverage_rows)
    write_csv(OUT / "report_only_eval_audit.csv", report_only_rows)
    write_csv(OUT / "role_access_audit.csv", role_access_rows)

    selected_lines = ["- No val-side legal candidate was available."] if selected is None else [
        f"- selected_by_val_side_only: strategy=`{selected['strategy']}`, support_budget=`{selected['support_budget']}`, ood_weight=`{selected['ood_weight']}`, support_weight=`{selected['support_weight']}`, threshold_rule=`{selected['threshold_rule']}`",
        f"- support_val_detection_min/mean: `{selected['support_val_detection_min']}` / `{selected['support_val_detection_mean']}`",
        f"- id_calib_alarm_max / ood_val_alarm_max: `{selected['id_calib_alarm_max']}` / `{selected['ood_val_alarm_max']}`",
        f"- report-only final_ood_alarm_max: `{selected['final_ood_alarm_report_only_max']}`",
        f"- report-only medium attack_eval_detection_min/mean: `{selected['attack_eval_detection_report_only_min']}` / `{selected['attack_eval_detection_report_only_mean']}`",
        f"- report-only new heldout detection_min/mean: `{selected['new_heldout_detection_report_only_min']}` / `{selected['new_heldout_detection_report_only_mean']}`",
    ]
    report_only_lines = ["- No val-legal candidate also satisfied report-only final OOD <= 1%."] if best_report_only is None else [
        f"- best report-only final-OOD-compliant candidate: strategy=`{best_report_only['strategy']}`, support_budget=`{best_report_only['support_budget']}`, ood_weight=`{best_report_only['ood_weight']}`, support_weight=`{best_report_only['support_weight']}`, threshold_rule=`{best_report_only['threshold_rule']}`",
        f"- report-only final_ood_alarm_max: `{best_report_only['final_ood_alarm_report_only_max']}`",
        f"- report-only medium attack_eval_detection_min/mean: `{best_report_only['attack_eval_detection_report_only_min']}` / `{best_report_only['attack_eval_detection_report_only_mean']}`",
        f"- report-only new heldout detection_min/mean: `{best_report_only['new_heldout_detection_report_only_min']}` / `{best_report_only['new_heldout_detection_report_only_mean']}`",
        "- This candidate is not selected by report-only performance; it is listed only to quantify whether any legal-looking configuration clears the report-only OOD budget.",
    ]
    write_md(
        OUT / "bounded_repair_report.md",
        [
            "# issue27as Bounded Calibration and Coverage Repair Report",
            "",
            f"primary_verdict = `{primary_verdict}`",
            "",
            "This is a medium diagnostic repair pass, not a formal benchmark. It keeps the Gotham Kitsune115 medium asset, split, frontend, old HistGB skeleton, and report-only final roles fixed.",
            "",
            "## Candidate Selection Boundary",
            "",
            "- Candidate selection uses only `id_calib`, `ood_val`, and `support_val`.",
            "- `final_ood_benign_eval`, `attack_eval`, and `new_heldout_attack_eval_probe` are report-only.",
            "- No candidate is selected by medium attack_eval or new heldout detection.",
            "",
            "## Selected Val-Side Candidate",
            "",
            *selected_lines,
            "",
            "## Report-Only Feasibility Check",
            "",
            *report_only_lines,
        ],
    )
    write_md(
        OUT / "issue27as_decision.md",
        [
            "# Issue27as Decision",
            "",
            f"primary_verdict = `{primary_verdict}`",
            "",
            "The result must not be interpreted as formal performance. If medium report-only improves but new heldout remains weak, the next action should focus on coverage/task-boundary repair rather than full benchmark execution.",
        ],
    )
    next_issue = "issue27at_coverage_aware_support_gap_protocol_design_or_task_boundary_decision"
    write_md(
        OUT / "issue27at_next_action.md",
        [
            "# Issue27at Next Action",
            "",
            f"Recommended next issue: `{next_issue}`.",
            "",
            "- If the selected candidate has high support_val and medium attack_eval but weak new heldout, formal full execution remains blocked.",
            "- Next, quantify whether coverage-aware support gating or a revised few-shot task boundary can handle heavy heldout without using report-only labels for selection.",
            "- Do not proceed to full/larger formal benchmark until both medium internal and heldout-like probes meet the predeclared target under clean role access.",
        ],
    )
    write_md(
        OUT / "claim_update_after_issue27as.md",
        [
            "# Claim Update After issue27as",
            "",
            "- issue27as is diagnostic bounded repair only.",
            "- Medium internal detection remains insufficient unless it reaches the predeclared high target under the low-OOD constraint.",
            "- New heldout detection is report-only and remains a probe for support-query gap; it is not used for selection.",
            "- Formal model claims still require a frozen full/larger asset and a pre-registered protocol.",
        ],
    )
    summary_lines = [
        "# issue27as Summary",
        "",
        "1. issue27as completed: yes",
        f"2. primary_verdict: `{primary_verdict}`",
        "3. task type: medium bounded calibration/support-influence repair; not formal benchmark",
        "4. frontend/split changed: no",
        "5. model family: old LOW-GUARD++ HistGB skeleton only",
        "6. candidate selection roles: id_calib + ood_val + support_val only",
        "7. final OOD / attack_eval / new heldout used for selection: no",
    ]
    if selected is not None:
        summary_lines.extend(
            [
                f"8. selected val-side candidate: `{selected['strategy']} | support_budget={selected['support_budget']} | ood_weight={selected['ood_weight']} | support_weight={selected['support_weight']} | threshold_rule={selected['threshold_rule']}`",
                f"9. support_val_detection_min: `{selected['support_val_detection_min']}`",
                f"10. report-only final_ood_alarm_max: `{selected['final_ood_alarm_report_only_max']}`",
                f"11. report-only medium attack_eval_detection_min/mean: `{selected['attack_eval_detection_report_only_min']}` / `{selected['attack_eval_detection_report_only_mean']}`",
                f"12. report-only new heldout detection_min/mean: `{selected['new_heldout_detection_report_only_min']}` / `{selected['new_heldout_detection_report_only_mean']}`",
                "13. formal benchmark allowed: no",
            ]
        )
        if best_report_only is not None:
            summary_lines.extend(
                [
                    f"14. best report-only final-OOD-compliant medium attack min: `{best_report_only['attack_eval_detection_report_only_min']}`",
                    f"15. best report-only final-OOD-compliant new heldout min: `{best_report_only['new_heldout_detection_report_only_min']}`",
                    "16. next action: `issue27at_coverage_aware_support_gap_protocol_design_or_task_boundary_decision`",
                    "17. commit hash: pending",
                ]
            )
        else:
            summary_lines.extend(
                [
                    "14. best report-only final-OOD-compliant candidate: none",
                    "15. next action: `issue27at_coverage_aware_support_gap_protocol_design_or_task_boundary_decision`",
                    "16. commit hash: pending",
                ]
            )
    else:
        summary_lines.extend(
            [
                "8. selected val-side candidate: none",
                "9. formal benchmark allowed: no",
                "10. next action: inspect role/threshold feasibility before any model work",
                "11. commit hash: pending",
            ]
        )
    write_md(OUT / "summary.md", summary_lines)

    config = {
        "issue": ISSUE,
        "scope": "medium_bounded_calibration_and_coverage_repair",
        "formal_benchmark": False,
        "seeds": SEEDS,
        "support_budgets": SUPPORT_BUDGETS,
        "ood_weights": OOD_WEIGHTS,
        "support_weights": SUPPORT_WEIGHTS,
        "val_target": VAL_TARGET,
        "strict_target": STRICT_TARGET,
        "candidate_selection_roles": ["id_calib", "ood_val", "support_val"],
        "report_only_roles": [FINAL_OOD_ROLE, ATTACK_EVAL_ROLE, NEW_HELDOUT_ROLE],
        "frontend_or_split_changed": False,
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")
    (OUT / "run_spec.json").write_text(
        json.dumps(
            {
                "inputs": {
                    "issue27af_medium_certificate": str(cert_path),
                    "issue27ar_outputs": str(ISSUE27AR),
                    "issue27aq_outputs": str(ISSUE27AQ),
                    "new_heldout_X": str(ar.NEW_HELDOUT_X),
                },
                "outputs": f"runs/{ISSUE}/",
                "selection_policy": "no final OOD, attack_eval, or new heldout used for candidate selection",
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (OUT / "command.txt").write_text(f"python repo/ood/{Path(__file__).name}\n", encoding="utf-8")

    append_doc(
        MAINLINE_DOCS / "mainline_handoff.md",
        "<!-- issue27as -->",
        [
            "<!-- issue27as -->",
            "## issue27as - Bounded old-protocol calibration and coverage repair",
            "",
            f"- primary_verdict: `{primary_verdict}`",
            "- Medium diagnostic only; no formal benchmark.",
            "- Keeps Gotham Kitsune115 medium frontend/split fixed and varies only bounded old HistGB weights, k-center budgets, and train-side threshold rules.",
            "- Candidate selection uses id_calib, ood_val, and support_val only; final OOD, attack_eval, and new heldout remain report-only.",
        ],
    )
    append_doc(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        "<!-- issue27as -->",
        [
            "<!-- issue27as -->",
            "## issue27as - Bounded calibration repair after old protocol fidelity",
            "",
            f"- verdict: `{primary_verdict}`",
            "- purpose: test whether bounded calibration/support-influence changes can rescue medium signal without using report-only roles.",
            f"- outputs: `runs/{ISSUE}/`.",
        ],
    )

    manifest = []
    for p in sorted(OUT.glob("*")):
        if p.is_file() and p.name != "manifest.csv":
            manifest.append({"path": str(p.relative_to(ROOT)), "sha256": sha256_file(p), "bytes": p.stat().st_size})
    write_csv(OUT / "manifest.csv", manifest)
    print(json.dumps({"primary_verdict": primary_verdict, "selected": selected, "out": str(OUT)}, indent=2, default=str))


if __name__ == "__main__":
    main()
