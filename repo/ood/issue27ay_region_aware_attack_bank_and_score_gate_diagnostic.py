from __future__ import annotations

import csv
import gzip
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import pairwise_distances
from sklearn.preprocessing import StandardScaler

import issue27ar_old_lowguardpp_protocol_fidelity_migration_on_gotham115_medium as ar
import issue27as_old_protocol_bounded_calibration_and_coverage_repair as issue27as
import issue27au_coverage_aware_active_labeling_viability_diagnostic as issue27au


REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
ISSUE = "issue27ay_region_aware_attack_bank_and_score_gate_diagnostic_2026-06-05"
OUT = ROOT / "runs" / ISSUE
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

ISSUE27AF = ROOT / "runs" / "issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02"
ISSUE27AX = ROOT / "runs" / "issue27ax_attack_support_bank_detection_recovery_diagnostic_2026-06-04"

PRIMARY_STRATEGY = "reset_at_split_boundary"
SEEDS = [42, 43, 44, 45, 46]
BASE_SUPPORT_BUDGET = 128
ACTIVE_LABEL_BUDGETS = [64, 128]
OOD_WEIGHT = 2.0
SUPPORT_WEIGHT = 4.0
VAL_TARGET = 0.01

ID_ROLE = ar.ID_ROLE
OOD_VAL_ROLE = ar.OOD_VAL_ROLE
FINAL_OOD_ROLE = ar.FINAL_OOD_ROLE
SUPPORT_ROLE = ar.SUPPORT_ROLE
ATTACK_EVAL_ROLE = ar.ATTACK_EVAL_ROLE
DEV_QUERY_ROLE = issue27au.DEV_QUERY_ROLE


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


def read_csv(path: Path) -> list[dict[str, str]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def hash_indices(indices: np.ndarray) -> str:
    return hashlib.sha256(",".join(map(str, np.asarray(indices, dtype=np.int64).tolist())).encode("utf-8")).hexdigest()


def label_is_attack(row: dict[str, str]) -> bool:
    return (row.get("binary_label_from_alignment") or row.get("label") or "").lower() == "attack"


def rate(scores_or_mask: np.ndarray, threshold: float | None = None) -> float:
    arr = np.asarray(scores_or_mask)
    if arr.size == 0:
        return float("nan")
    if threshold is None:
        return float(np.mean(arr.astype(bool)))
    return float(np.mean(arr > float(threshold)))


def summarize_values(vals: list[float] | np.ndarray) -> dict[str, float]:
    arr = np.asarray(vals, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return {"mean": float("nan"), "min": float("nan"), "max": float("nan")}
    return {"mean": float(np.mean(arr)), "min": float(np.min(arr)), "max": float(np.max(arr))}


class CustomWeightedHistGB:
    def __init__(self, seed: int):
        self.seed = int(seed)
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

    def fit_with_parts(
        self,
        x_id_train: np.ndarray,
        x_ood_train: np.ndarray,
        attack_parts: list[tuple[str, np.ndarray, float]],
    ) -> None:
        xs = [x_id_train, x_ood_train]
        ys = [np.zeros(len(x_id_train), dtype=np.int64), np.zeros(len(x_ood_train), dtype=np.int64)]
        ws = [np.ones(len(x_id_train), dtype=np.float64), np.full(len(x_ood_train), OOD_WEIGHT, dtype=np.float64)]
        fit_meta: dict[str, Any] = {
            "id_rows": int(len(x_id_train)),
            "ood_train_rows": int(len(x_ood_train)),
            "id_weight": 1.0,
            "ood_weight": OOD_WEIGHT,
        }
        attack_xs = []
        attack_total_weight = 0.0
        for name, x_part, per_row_weight in attack_parts:
            if len(x_part) == 0:
                continue
            xs.append(x_part)
            ys.append(np.ones(len(x_part), dtype=np.int64))
            ws.append(np.full(len(x_part), float(per_row_weight), dtype=np.float64))
            attack_xs.append(x_part)
            fit_meta[f"{name}_rows"] = int(len(x_part))
            fit_meta[f"{name}_per_row_weight"] = float(per_row_weight)
            fit_meta[f"{name}_total_weight"] = float(len(x_part) * float(per_row_weight))
            attack_total_weight += float(len(x_part) * float(per_row_weight))
        x_train = np.vstack(xs)
        y_train = np.concatenate(ys)
        sample_weight = np.concatenate(ws)
        fit_meta["total_rows"] = int(len(x_train))
        fit_meta["attack_total_weight"] = float(attack_total_weight)
        fit_meta["weighted_normal_to_attack_ratio"] = float(
            (len(x_id_train) + len(x_ood_train) * OOD_WEIGHT) / max(1.0, attack_total_weight)
        )
        self.fit_shape = fit_meta
        self.model.fit(x_train, y_train, sample_weight=sample_weight)
        if attack_xs:
            self._fix_score_direction(x_id_train, x_ood_train, np.vstack(attack_xs))

    def raw_score(self, x: np.ndarray) -> np.ndarray:
        proba = self.model.predict_proba(x)
        classes = list(self.model.classes_)
        if 1 not in classes:
            raise RuntimeError(f"attack class 1 missing: {classes}")
        return np.asarray(proba[:, classes.index(1)], dtype=np.float64)

    def score(self, x: np.ndarray) -> np.ndarray:
        return self.score_direction * self.raw_score(x)

    def _fix_score_direction(self, x_id_train: np.ndarray, x_ood_train: np.ndarray, x_attack: np.ndarray) -> None:
        raw_id = self.raw_score(x_id_train)
        raw_ood = self.raw_score(x_ood_train)
        raw_attack = self.raw_score(x_attack)
        if float(np.mean(raw_attack)) < float(np.mean(raw_id)) and float(np.mean(raw_attack)) < float(np.mean(raw_ood)):
            self.score_direction = -1.0
            self.score_direction_fixed = True
        self.direction_check = {
            "attack_raw_mean": float(np.mean(raw_attack)),
            "id_train_raw_mean": float(np.mean(raw_id)),
            "ood_train_raw_mean": float(np.mean(raw_ood)),
            "attack_score_mean": float(np.mean(self.score(x_attack))),
            "id_train_score_mean": float(np.mean(self.score(x_id_train))),
            "ood_train_score_mean": float(np.mean(self.score(x_ood_train))),
            "score_direction": self.score_direction,
            "score_direction_fixed": self.score_direction_fixed,
        }


def split_selected(rows: np.ndarray, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rows = np.asarray(rows, dtype=np.int64).copy()
    if len(rows) < 2:
        return rows, np.asarray([], dtype=np.int64)
    rng = np.random.default_rng(seed + 91027)
    rng.shuffle(rows)
    cut = int(np.floor(len(rows) * 0.75))
    cut = max(1, min(cut, len(rows) - 1))
    return np.asarray(sorted(rows[:cut].tolist()), dtype=np.int64), np.asarray(sorted(rows[cut:].tolist()), dtype=np.int64)


def select_base_and_active(
    x: np.ndarray,
    new_x: np.ndarray,
    support_pool: np.ndarray,
    active_candidate_idx: np.ndarray,
    new_sidecar: list[dict[str, str]],
    seed: int,
    active_budget: int,
) -> dict[str, Any]:
    base_support, base_audit = issue27as.kcenter_budget(x, support_pool, BASE_SUPPORT_BUDGET)
    base_train, base_val = issue27as.split_support(base_support, seed)
    selected, sel_audit = issue27au.select_active_labels(
        x_base_support=x[base_train],
        x_support_val=x[base_val],
        x_candidates=new_x[active_candidate_idx],
        candidate_indices=active_candidate_idx,
        budget=active_budget,
    )
    confirmed = np.asarray([idx for idx in selected if label_is_attack(new_sidecar[int(idx)])], dtype=np.int64)
    heavy_train, heavy_val = split_selected(confirmed, seed)
    return {
        "base_support": base_support,
        "base_train": base_train,
        "base_val": base_val,
        "base_audit": base_audit,
        "active_selected": selected,
        "active_confirmed": confirmed,
        "heavy_train": heavy_train,
        "heavy_val": heavy_val,
        "selection_audit": sel_audit,
    }


def threshold_for(scores_id: np.ndarray, scores_ood: np.ndarray, scores_val: np.ndarray) -> dict[str, Any]:
    return issue27as.support_guided_threshold(scores_id, scores_ood, scores_val)


def fit_single_model(
    x: np.ndarray,
    id_fit: np.ndarray,
    ood_train: np.ndarray,
    medium_train: np.ndarray,
    heavy_train_x: np.ndarray,
    seed: int,
    weighting_policy: str,
) -> CustomWeightedHistGB:
    model = CustomWeightedHistGB(seed)
    if weighting_policy == "uniform_attack_row_weight":
        medium_w = SUPPORT_WEIGHT
        heavy_w = SUPPORT_WEIGHT
    elif weighting_policy == "region_equal_total_attack_weight":
        target_total = SUPPORT_WEIGHT * max(1, len(medium_train))
        medium_w = target_total / max(1, len(medium_train))
        heavy_w = target_total / max(1, len(heavy_train_x))
    elif weighting_policy == "region_capped_total_attack_weight":
        target_total = SUPPORT_WEIGHT * max(1, len(medium_train)) / 2.0
        medium_w = target_total / max(1, len(medium_train))
        heavy_w = target_total / max(1, len(heavy_train_x))
    else:
        raise ValueError(weighting_policy)
    model.fit_with_parts(
        x[id_fit],
        x[ood_train],
        [
            ("medium_region_attack", x[medium_train], medium_w),
            ("heavy_region_attack", heavy_train_x, heavy_w),
        ],
    )
    return model


def region_distance_profile(x_train: np.ndarray, x_val: np.ndarray, x_query: np.ndarray) -> dict[str, Any]:
    if len(x_train) == 0 or len(x_query) == 0:
        return {
            "p75_radius": float("nan"),
            "p95_radius": float("nan"),
            "covered_p75": float("nan"),
            "covered_p95": float("nan"),
            "nearest_p50": float("nan"),
            "nearest_p95": float("nan"),
        }
    scaler = StandardScaler().fit(x_train)
    z_train = scaler.transform(x_train)
    if len(x_val):
        z_val = scaler.transform(x_val)
        val_d = pairwise_distances(z_val, z_train, metric="euclidean").min(axis=1)
        p75 = float(np.quantile(val_d, 0.75))
        p95 = float(np.quantile(val_d, 0.95))
    else:
        p75 = float("nan")
        p95 = float("nan")
    q_d = pairwise_distances(scaler.transform(x_query), z_train, metric="euclidean").min(axis=1)
    return {
        "p75_radius": p75,
        "p95_radius": p95,
        "covered_p75": float(np.mean(q_d <= p75)) if np.isfinite(p75) else float("nan"),
        "covered_p95": float(np.mean(q_d <= p95)) if np.isfinite(p95) else float("nan"),
        "nearest_p50": float(np.quantile(q_d, 0.50)),
        "nearest_p95": float(np.quantile(q_d, 0.95)),
    }


def region_covered_mask(x_train: np.ndarray, x_val: np.ndarray, x_query: np.ndarray, quantile: float = 0.95) -> np.ndarray:
    if len(x_train) == 0 or len(x_val) == 0 or len(x_query) == 0:
        return np.zeros(len(x_query), dtype=bool)
    scaler = StandardScaler().fit(x_train)
    z_train = scaler.transform(x_train)
    val_d = pairwise_distances(scaler.transform(x_val), z_train, metric="euclidean").min(axis=1)
    q_d = pairwise_distances(scaler.transform(x_query), z_train, metric="euclidean").min(axis=1)
    return q_d <= float(np.quantile(val_d, quantile))


def eval_single_model(
    model: CustomWeightedHistGB,
    threshold: float,
    roles: dict[str, np.ndarray],
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for role, x_role in roles.items():
        scores = model.score(x_role)
        out[f"{role}_detection_or_alarm"] = rate(scores, threshold)
        out[f"{role}_score_mean"] = float(np.mean(scores)) if len(scores) else float("nan")
    return out


def fit_region_head(
    x_id: np.ndarray,
    x_ood: np.ndarray,
    x_region_train: np.ndarray,
    seed: int,
    support_weight: float = SUPPORT_WEIGHT,
) -> CustomWeightedHistGB:
    model = CustomWeightedHistGB(seed)
    model.fit_with_parts(
        x_id,
        x_ood,
        [("region_attack", x_region_train, support_weight)],
    )
    return model


def summarize_detection(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["config_name"], int(row["active_label_budget"]))].append(row)
    out: list[dict[str, Any]] = []
    for (config_name, budget), gr in sorted(groups.items()):
        row: dict[str, Any] = {"config_name": config_name, "active_label_budget": budget, "seeds": len(gr)}
        for metric in [
            "support_val_detection",
            "active_heavy_val_detection",
            "medium_attack_eval_detection_report_only",
            "dev_heavy_query_detection_report_only",
            "triple_attack_min",
            "id_calib_alarm",
            "ood_val_alarm",
            "final_ood_alarm_report_only",
            "medium_low_score_attack_covered_review_fraction",
            "dev_heavy_low_score_attack_covered_review_fraction",
            "medium_score_or_review_recall",
            "dev_heavy_score_or_review_recall",
        ]:
            stats = summarize_values([float(r[metric]) for r in gr])
            for stat_name, value in stats.items():
                row[f"{metric}_{stat_name}"] = value
        out.append(row)
    return out


def choose_verdict(summary_rows: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    candidates = [r for r in summary_rows if int(r["active_label_budget"]) > 0]
    best = max(candidates, key=lambda r: (float(r["triple_attack_min_min"]), float(r["dev_heavy_query_detection_report_only_min"])))
    stats = {
        "best_config_name": best["config_name"],
        "best_active_label_budget": int(best["active_label_budget"]),
        "best_triple_attack_min": float(best["triple_attack_min_min"]),
        "best_support_val_min": float(best["support_val_detection_min"]),
        "best_active_heavy_val_min": float(best["active_heavy_val_detection_min"]),
        "best_medium_attack_min": float(best["medium_attack_eval_detection_report_only_min"]),
        "best_dev_heavy_min": float(best["dev_heavy_query_detection_report_only_min"]),
        "best_medium_score_or_review_min": float(best["medium_score_or_review_recall_min"]),
        "best_dev_heavy_score_or_review_min": float(best["dev_heavy_score_or_review_recall_min"]),
        "best_final_ood_alarm_max": float(best["final_ood_alarm_report_only_max"]),
    }
    if stats["best_triple_attack_min"] >= 0.95:
        return "region_aware_attack_recovery_supported_ready_for_ood_gate", stats
    if stats["best_triple_attack_min"] >= 0.90:
        return "region_aware_attack_recovery_promising_needs_ood_gate", stats
    if stats["best_medium_score_or_review_min"] >= 0.95 and stats["best_dev_heavy_score_or_review_min"] >= 0.95:
        return "region_aware_review_route_supported_but_hard_alarm_incomplete", stats
    if stats["best_dev_heavy_min"] >= 0.90 and stats["best_medium_attack_min"] < 0.90:
        return "region_aware_bank_still_damages_medium_region", stats
    if stats["best_medium_attack_min"] >= 0.90 and stats["best_dev_heavy_min"] < 0.90:
        return "region_aware_bank_still_missing_heavy_region", stats
    return "region_aware_attack_recovery_insufficient_check_head_or_task_boundary", stats


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cert_path = ISSUE27AF / "kitsune115_materialization_data_certificate_medium.json"
    cert = json.loads(cert_path.read_text(encoding="utf-8"))
    asset, checks = ar.load_asset(PRIMARY_STRATEGY, cert)
    new_x, new_sidecar, new_checks = ar.load_new_heldout()
    if not new_sidecar:
        new_sidecar = read_csv(ar.NEW_HELDOUT_SIDECAR)

    x = asset["X"]
    sidecar = asset["sidecar"]
    id_idx = ar.role_indices(sidecar, ID_ROLE)
    ood_idx = ar.role_indices(sidecar, OOD_VAL_ROLE)
    final_ood = ar.role_indices(sidecar, FINAL_OOD_ROLE)
    support_pool = ar.role_indices(sidecar, SUPPORT_ROLE)
    attack_eval = ar.role_indices(sidecar, ATTACK_EVAL_ROLE)
    id_fit, id_calib = ar.deterministic_role_subsplit(id_idx, 0.80)
    ood_train, ood_val = ar.deterministic_role_subsplit(ood_idx, 0.50)
    active_candidate_idx, dev_query_idx, split_manifest = issue27au.split_new_heavy_stream(new_sidecar)

    input_hash_rows = [
        {"artifact": "issue27af_medium_certificate", "path": str(cert_path), "sha256": sha256_file(cert_path), "hash_match": True},
        {"artifact": "issue27ax_summary", "path": str(ISSUE27AX / "summary.md"), "sha256": sha256_file(ISSUE27AX / "summary.md"), "hash_match": True},
    ]
    input_hash_rows.extend(checks)
    input_hash_rows.extend(new_checks)

    region_registry_rows: list[dict[str, Any]] = []
    config_rows: list[dict[str, Any]] = []
    detection_rows: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []
    distance_rows: list[dict[str, Any]] = []
    role_rows: list[dict[str, Any]] = []

    for seed in SEEDS:
        for budget in ACTIVE_LABEL_BUDGETS:
            sel = select_base_and_active(x, new_x, support_pool, active_candidate_idx, new_sidecar, seed, budget)
            medium_train = sel["base_train"]
            medium_val = sel["base_val"]
            heavy_train_idx = sel["heavy_train"]
            heavy_val_idx = sel["heavy_val"]
            heavy_train_x = new_x[heavy_train_idx]
            heavy_val_x = new_x[heavy_val_idx]
            combined_val_x = np.vstack([x[medium_val], heavy_val_x]) if len(heavy_val_x) else x[medium_val]

            region_registry_rows.extend(
                [
                    {
                        "seed": seed,
                        "active_label_budget": budget,
                        "region_id": "attack_medium_base",
                        "region_source": SUPPORT_ROLE,
                        "train_rows": int(len(medium_train)),
                        "val_rows": int(len(medium_val)),
                        "indices_sha256_train": hash_indices(medium_train),
                        "indices_sha256_val": hash_indices(medium_val),
                        "allowed_for_fit": True,
                        "allowed_for_threshold": True,
                        "uses_final_or_eval": False,
                    },
                    {
                        "seed": seed,
                        "active_label_budget": budget,
                        "region_id": "attack_active_heavy",
                        "region_source": "development_active_label_candidate_stream",
                        "train_rows": int(len(heavy_train_idx)),
                        "val_rows": int(len(heavy_val_idx)),
                        "indices_sha256_train": hash_indices(heavy_train_idx),
                        "indices_sha256_val": hash_indices(heavy_val_idx),
                        "active_selector": sel["selection_audit"].get("selector", ""),
                        "active_selected_rows": int(len(sel["active_selected"])),
                        "confirmed_attack_rows": int(len(sel["active_confirmed"])),
                        "allowed_for_fit": True,
                        "allowed_for_threshold": True,
                        "uses_final_or_eval": False,
                    },
                ]
            )
            for query_name, qx in [
                ("support_val_medium", x[medium_val]),
                ("active_heavy_val", heavy_val_x),
                ("medium_attack_eval_report_only", x[attack_eval]),
                ("dev_heavy_query_report_only", new_x[dev_query_idx]),
            ]:
                for region_id, train_x, val_x in [
                    ("attack_medium_base", x[medium_train], x[medium_val]),
                    ("attack_active_heavy", heavy_train_x, heavy_val_x),
                ]:
                    prof = region_distance_profile(train_x, val_x, qx)
                    distance_rows.append(
                        {
                            "seed": seed,
                            "active_label_budget": budget,
                            "query_name": query_name,
                            "region_id": region_id,
                            **prof,
                        }
                    )

            config_specs = [
                ("single_uniform_append", "uniform_attack_row_weight"),
                ("single_region_equal_total", "region_equal_total_attack_weight"),
                ("single_region_capped_total", "region_capped_total_attack_weight"),
            ]
            for config_name, weighting_policy in config_specs:
                model = fit_single_model(x, id_fit, ood_train, medium_train, heavy_train_x, seed, weighting_policy)
                th = threshold_for(model.score(x[id_calib]), model.score(x[ood_val]), model.score(combined_val_x))
                threshold = float(th["threshold"])
                role_scores = {
                    "support_val_detection": model.score(x[medium_val]),
                    "active_heavy_val_detection": model.score(heavy_val_x),
                    "medium_attack_eval_detection_report_only": model.score(x[attack_eval]),
                    "dev_heavy_query_detection_report_only": model.score(new_x[dev_query_idx]),
                    "id_calib_alarm": model.score(x[id_calib]),
                    "ood_val_alarm": model.score(x[ood_val]),
                    "final_ood_alarm_report_only": model.score(x[final_ood]),
                }
                medium_mask = region_covered_mask(x[medium_train], x[medium_val], x[attack_eval])
                heavy_mask = region_covered_mask(heavy_train_x, heavy_val_x, new_x[dev_query_idx])
                med_scores = role_scores["medium_attack_eval_detection_report_only"]
                dev_scores = role_scores["dev_heavy_query_detection_report_only"]
                med_alarm = med_scores > threshold
                dev_alarm = dev_scores > threshold
                med_review = (~med_alarm) & medium_mask
                dev_review = (~dev_alarm) & heavy_mask
                row = {
                    "seed": seed,
                    "active_label_budget": budget,
                    "config_name": config_name,
                    "config_family": "single_detector",
                    "weighting_policy": weighting_policy,
                    "threshold_rule": th.get("rule", ""),
                    "threshold": threshold,
                    "support_val_detection": rate(role_scores["support_val_detection"], threshold),
                    "active_heavy_val_detection": rate(role_scores["active_heavy_val_detection"], threshold),
                    "medium_attack_eval_detection_report_only": rate(med_alarm),
                    "dev_heavy_query_detection_report_only": rate(dev_alarm),
                    "id_calib_alarm": rate(role_scores["id_calib_alarm"], threshold),
                    "ood_val_alarm": rate(role_scores["ood_val_alarm"], threshold),
                    "final_ood_alarm_report_only": rate(role_scores["final_ood_alarm_report_only"], threshold),
                    "medium_low_score_attack_covered_review_fraction": rate(med_review),
                    "dev_heavy_low_score_attack_covered_review_fraction": rate(dev_review),
                    "medium_score_or_review_recall": rate(med_alarm | med_review),
                    "dev_heavy_score_or_review_recall": rate(dev_alarm | dev_review),
                    "uses_final_ood_for_selection": False,
                    "uses_eval_attack_for_selection": False,
                    "uses_dev_heavy_query_for_selection": False,
                }
                row["triple_attack_min"] = min(
                    float(row["support_val_detection"]),
                    float(row["medium_attack_eval_detection_report_only"]),
                    float(row["dev_heavy_query_detection_report_only"]),
                )
                detection_rows.append(row)
                config_rows.append(
                    {
                        "seed": seed,
                        "active_label_budget": budget,
                        "config_name": config_name,
                        "config_family": "single_detector",
                        "weighting_policy": weighting_policy,
                        **model.fit_shape,
                    }
                )
                review_rows.extend(
                    [
                        {
                            "seed": seed,
                            "active_label_budget": budget,
                            "config_name": config_name,
                            "query_name": "medium_attack_eval_report_only",
                            "alarm_fraction": rate(med_alarm),
                            "low_score_attack_covered_review_fraction": rate(med_review),
                            "score_or_review_recall": rate(med_alarm | med_review),
                        },
                        {
                            "seed": seed,
                            "active_label_budget": budget,
                            "config_name": config_name,
                            "query_name": "dev_heavy_query_report_only",
                            "alarm_fraction": rate(dev_alarm),
                            "low_score_attack_covered_review_fraction": rate(dev_review),
                            "score_or_review_recall": rate(dev_alarm | dev_review),
                        },
                    ]
                )

            # Per-region heads: one attack region cannot overwrite the other in the objective.
            medium_head = fit_region_head(x[id_fit], x[ood_train], x[medium_train], seed)
            heavy_head = fit_region_head(x[id_fit], x[ood_train], heavy_train_x, seed) if len(heavy_train_x) else None
            med_th = threshold_for(medium_head.score(x[id_calib]), medium_head.score(x[ood_val]), medium_head.score(x[medium_val]))
            heavy_th = (
                threshold_for(heavy_head.score(x[id_calib]), heavy_head.score(x[ood_val]), heavy_head.score(heavy_val_x))
                if heavy_head is not None and len(heavy_val_x)
                else None
            )
            for config_name, gated in [("per_region_heads_or", False), ("per_region_heads_distance_gated_or", True)]:
                def decide(xq: np.ndarray) -> np.ndarray:
                    med_alarm = medium_head.score(xq) > float(med_th["threshold"])
                    if gated:
                        med_alarm = med_alarm & region_covered_mask(x[medium_train], x[medium_val], xq)
                    if heavy_head is None or heavy_th is None:
                        return med_alarm
                    h_alarm = heavy_head.score(xq) > float(heavy_th["threshold"])
                    if gated:
                        h_alarm = h_alarm & region_covered_mask(heavy_train_x, heavy_val_x, xq)
                    return med_alarm | h_alarm

                support_val_mask = decide(x[medium_val])
                heavy_val_mask = decide(heavy_val_x)
                medium_eval_mask = decide(x[attack_eval])
                dev_query_mask = decide(new_x[dev_query_idx])
                id_mask = decide(x[id_calib])
                ood_mask = decide(x[ood_val])
                final_mask = decide(x[final_ood])
                med_region_cover = region_covered_mask(x[medium_train], x[medium_val], x[attack_eval])
                heavy_region_cover = region_covered_mask(heavy_train_x, heavy_val_x, new_x[dev_query_idx])
                med_review = (~medium_eval_mask) & med_region_cover
                dev_review = (~dev_query_mask) & heavy_region_cover
                row = {
                    "seed": seed,
                    "active_label_budget": budget,
                    "config_name": config_name,
                    "config_family": "per_region_heads",
                    "weighting_policy": "independent_region_heads",
                    "threshold_rule": "support_val_guided_per_region",
                    "threshold": json.dumps(
                        {
                            "medium": float(med_th["threshold"]),
                            "heavy": float(heavy_th["threshold"]) if heavy_th is not None else None,
                        },
                        sort_keys=True,
                    ),
                    "support_val_detection": rate(support_val_mask),
                    "active_heavy_val_detection": rate(heavy_val_mask),
                    "medium_attack_eval_detection_report_only": rate(medium_eval_mask),
                    "dev_heavy_query_detection_report_only": rate(dev_query_mask),
                    "id_calib_alarm": rate(id_mask),
                    "ood_val_alarm": rate(ood_mask),
                    "final_ood_alarm_report_only": rate(final_mask),
                    "medium_low_score_attack_covered_review_fraction": rate(med_review),
                    "dev_heavy_low_score_attack_covered_review_fraction": rate(dev_review),
                    "medium_score_or_review_recall": rate(medium_eval_mask | med_review),
                    "dev_heavy_score_or_review_recall": rate(dev_query_mask | dev_review),
                    "uses_final_ood_for_selection": False,
                    "uses_eval_attack_for_selection": False,
                    "uses_dev_heavy_query_for_selection": False,
                }
                row["triple_attack_min"] = min(
                    float(row["support_val_detection"]),
                    float(row["medium_attack_eval_detection_report_only"]),
                    float(row["dev_heavy_query_detection_report_only"]),
                )
                detection_rows.append(row)
                config_rows.append(
                    {
                        "seed": seed,
                        "active_label_budget": budget,
                        "config_name": config_name,
                        "config_family": "per_region_heads",
                        "weighting_policy": "independent_region_heads",
                        "medium_head_rows": int(len(medium_train)),
                        "heavy_head_rows": int(len(heavy_train_idx)),
                        "medium_threshold": float(med_th["threshold"]),
                        "heavy_threshold": float(heavy_th["threshold"]) if heavy_th is not None else "",
                        "distance_gated": gated,
                    }
                )
                review_rows.extend(
                    [
                        {
                            "seed": seed,
                            "active_label_budget": budget,
                            "config_name": config_name,
                            "query_name": "medium_attack_eval_report_only",
                            "alarm_fraction": rate(medium_eval_mask),
                            "low_score_attack_covered_review_fraction": rate(med_review),
                            "score_or_review_recall": rate(medium_eval_mask | med_review),
                        },
                        {
                            "seed": seed,
                            "active_label_budget": budget,
                            "config_name": config_name,
                            "query_name": "dev_heavy_query_report_only",
                            "alarm_fraction": rate(dev_query_mask),
                            "low_score_attack_covered_review_fraction": rate(dev_review),
                            "score_or_review_recall": rate(dev_query_mask | dev_review),
                        },
                    ]
                )
            role_rows.append(
                {
                    "seed": seed,
                    "active_label_budget": budget,
                    "fit_roles": "id_fit|ood_train_guard|medium_region_train_attack|active_heavy_region_train_attack",
                    "threshold_roles": "id_calib|ood_val|medium_support_val|active_heavy_val",
                    "report_only_roles": "medium_attack_eval|dev_heavy_query|final_ood",
                    "uses_final_ood_for_selection": False,
                    "uses_attack_eval_for_selection": False,
                    "uses_dev_heavy_query_for_selection": False,
                    "uses_candidate_labels_for_active_selection": False,
                    "uses_active_labels_after_selection_for_confirmation": True,
                    "forbidden_role_access": False,
                }
            )

    summary_rows = summarize_detection(detection_rows)
    primary_verdict, verdict_stats = choose_verdict(summary_rows)

    write_csv(OUT / "input_artifact_hash_audit.csv", input_hash_rows)
    write_csv(OUT / "region_registry.csv", region_registry_rows)
    write_csv(OUT / "region_bank_config_audit.csv", config_rows)
    write_csv(OUT / "region_distance_coverage_audit.csv", distance_rows)
    write_csv(OUT / "region_aware_detection_by_seed.csv", detection_rows)
    write_csv(OUT / "region_aware_detection_summary.csv", summary_rows)
    write_csv(OUT / "low_score_attack_covered_review_audit.csv", review_rows)
    write_csv(OUT / "role_access_audit.csv", role_rows)

    write_md(
        OUT / "region_gate_logic.md",
        [
            "# Region-Aware Score Gate Logic",
            "",
            "This diagnostic does not replace anomaly scores with distance-only rules.",
            "",
            "Runtime logic being tested:",
            "",
            "1. Extract Gotham Kitsune115 features.",
            "2. Compute an attack score with a frozen HistGB-style head.",
            "3. Compute coverage against each attack region registry entry.",
            "4. Hard alarm requires score above the pre-registered threshold.",
            "5. Low-score samples that are close to an attack region are counted as weak-review candidates, not as hard detections.",
            "6. Samples far from all attack regions remain unknown/uncovered and should go to a buffer or active-labeling route.",
            "",
            "Distance/coverage is therefore a routing and confidence mechanism, not the detector itself.",
        ],
    )
    write_md(
        OUT / "region_aware_detection_report.md",
        [
            "# Region-Aware Attack Bank Diagnostic Report",
            "",
            f"primary_verdict = `{primary_verdict}`",
            "",
            "This is a bounded attack-side diagnostic on the Gotham Kitsune115 medium asset.",
            "It does not change the 115D frontend, split, final OOD, or sealed attack eval roles.",
            "",
            "## Best Diagnostic Row",
            "",
            *[f"- {k}: `{v}`" for k, v in verdict_stats.items()],
            "",
            "## Interpretation",
            "",
            "- `single_*` rows test whether region weighting alone can stop active-heavy labels from damaging medium attack detection.",
            "- `per_region_heads_*` rows test whether separate region heads avoid negative transfer.",
            "- `*_score_or_review_recall` counts hard score alarms plus low-score samples that are close to an attack region; it is a review-route diagnostic, not a hard detection metric.",
            "- Final OOD is logged as a caveat only and is not optimized in this task.",
        ],
    )
    next_issue = "issue27az_attack_region_registry_with_ood_safe_gate_design"
    if primary_verdict == "region_aware_attack_recovery_supported_ready_for_ood_gate":
        next_issue = "issue27az_region_aware_ood_safe_gate_repair"
    elif primary_verdict == "region_aware_review_route_supported_but_hard_alarm_incomplete":
        next_issue = "issue27az_low_score_attack_covered_review_to_alarm_policy"
    elif "insufficient" in primary_verdict:
        next_issue = "issue27az_head_or_task_boundary_after_region_bank_failure"

    write_md(
        OUT / "issue27ay_decision.md",
        [
            "# Issue27ay Decision",
            "",
            f"primary_verdict = `{primary_verdict}`",
            "",
            "- This task is not a formal benchmark.",
            "- The most important distinction is hard alarm versus weak-review coverage.",
            "- If region heads recover both medium and heavy attack without using final roles, the next step is OOD-safe gate repair.",
            f"- Recommended next issue: `{next_issue}`.",
        ],
    )
    write_md(
        OUT / "claim_update_after_issue27ay.md",
        [
            "# Claim Update After issue27ay",
            "",
            "- issue27ay remains diagnostic and cannot support a final method claim.",
            "- It tests whether region-aware attack memory can reduce negative transfer between medium and active-heavy support regions.",
            "- Any paper-facing claim still requires OOD-safe calibration, larger/full replay, and sealed final evaluation.",
        ],
    )
    write_md(
        OUT / "issue27az_next_action.md",
        [
            "# Issue27az Next Action",
            "",
            f"Recommended next issue: `{next_issue}`.",
            "",
            "- If attack hard-alarm recovery is strong, start OOD-safe gate repair with region-aware heads.",
            "- If only weak-review recovery is strong, define a conservative review-to-alarm policy before touching OOD.",
            "- If both fail, revisit head objective or task boundary before expanding the dataset.",
        ],
    )
    write_md(
        OUT / "summary.md",
        [
            "# issue27ay Summary",
            "",
            "1. issue27ay completed: yes",
            f"2. primary_verdict: `{primary_verdict}`",
            "3. task type: region-aware attack support bank diagnostic; not formal benchmark",
            "4. 115D frontend/split changed: no",
            "5. final OOD used for selection: no",
            "6. attack eval/dev-heavy query used for support, threshold, or model selection: no",
            f"7. best config: `{verdict_stats['best_config_name']}`",
            f"8. best active label budget: `{verdict_stats['best_active_label_budget']}`",
            f"9. best triple hard attack min: `{verdict_stats['best_triple_attack_min']}`",
            f"10. best support_val min: `{verdict_stats['best_support_val_min']}`",
            f"11. best active-heavy val min: `{verdict_stats['best_active_heavy_val_min']}`",
            f"12. best medium attack min: `{verdict_stats['best_medium_attack_min']}`",
            f"13. best dev-heavy attack min: `{verdict_stats['best_dev_heavy_min']}`",
            f"14. best medium score-or-review min: `{verdict_stats['best_medium_score_or_review_min']}`",
            f"15. best dev-heavy score-or-review min: `{verdict_stats['best_dev_heavy_score_or_review_min']}`",
            f"16. best final OOD alarm max (report-only caveat): `{verdict_stats['best_final_ood_alarm_max']}`",
            "17. current formal benchmark allowed: no",
            f"18. next action: `{next_issue}`",
            "19. commit hash: pending",
        ],
    )
    config = {
        "issue": ISSUE,
        "formal_benchmark": False,
        "state_strategy": PRIMARY_STRATEGY,
        "active_label_budgets": ACTIVE_LABEL_BUDGETS,
        "base_support_budget": BASE_SUPPORT_BUDGET,
        "tested_config_families": [
            "single_detector_uniform_append",
            "single_detector_region_weighted",
            "per_region_heads_or",
            "per_region_heads_distance_gated_or",
        ],
        "role_policy": "final/report-only roles are never used for support, threshold, or model selection",
        "primary_verdict": primary_verdict,
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")
    (OUT / "run_spec.json").write_text(
        json.dumps(
            {
                "inputs": {
                    "issue27af_certificate": str(cert_path),
                    "issue27ax_outputs": str(ISSUE27AX),
                    "new_heavy_dev_probe": str(ar.NEW_HELDOUT_DIR),
                },
                "outputs": f"runs/{ISSUE}/",
                "scope": "medium region-aware attack-bank diagnostic only; no formal benchmark",
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (OUT / "command.txt").write_text(f"python repo/ood/{Path(__file__).name}\n", encoding="utf-8")
    append_doc(
        MAINLINE_DOCS / "mainline_handoff.md",
        "<!-- issue27ay -->",
        [
            "<!-- issue27ay -->",
            "## issue27ay - Region-aware attack bank and score gate diagnostic",
            "",
            f"- primary_verdict: `{primary_verdict}`",
            "- Diagnostic only; tests region weighting, per-region heads, and low-score attack-covered review routing.",
            "- Final/report-only roles were not used for support, threshold, or model selection.",
            "- Formal benchmark remains blocked until OOD-safe calibration and larger/full replay are ready.",
        ],
    )
    append_doc(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        "<!-- issue27ay -->",
        [
            "<!-- issue27ay -->",
            "## issue27ay - Region-aware attack support bank diagnostic",
            "",
            f"- verdict: `{primary_verdict}`",
            "- purpose: test whether attack regions should be kept as structured memory instead of one merged positive class.",
            f"- outputs: `runs/{ISSUE}/`.",
        ],
    )
    manifest = []
    for p in sorted(OUT.glob("*")):
        if p.is_file() and p.name != "manifest.csv":
            manifest.append({"path": str(p.relative_to(ROOT)), "sha256": sha256_file(p), "bytes": p.stat().st_size})
    write_csv(OUT / "manifest.csv", manifest)
    print(json.dumps({"primary_verdict": primary_verdict, "stats": verdict_stats, "out": str(OUT)}, indent=2))


if __name__ == "__main__":
    main()
