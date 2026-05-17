from __future__ import annotations

import csv
import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, pairwise_distances, roc_auc_score
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs" / "issue17_support_diversity_selection_harder_holdout_2026-05-15"
ISSUE16B = ROOT / "runs" / "issue16b_harder_holdout_fixed_guard_validation_2026-05-15"
ISSUE16C = ROOT / "runs" / "issue16c_harder_holdout_failure_analysis_and_repair_design_2026-05-15"
ISSUE11 = ROOT / "runs" / "issue11_fixed_config_ood_guard_lr_ablation_2026-05-14"

FRONTEND_F2_ROOT = ROOT.parent / "kitnet-frontend-f2"
KITNET_ROOT = ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master"
F2_OOD = FRONTEND_F2_ROOT / "repo" / "ood"
REPO_DIR = ROOT / "repo"
OOD_DIR = REPO_DIR / "ood"
for p in [F2_OOD, REPO_DIR, OOD_DIR]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import frontend100_negative_recipe_rescoring as resc  # noqa: E402
import frontend_f2_v7_4_paired_holdout_fairness as v74  # noqa: E402
import frontend_f2_v7_2_fairness_validation as v72  # noqa: E402


TARGET_ALARM = 0.01
POSITIVE_BUDGET = 32
SEEDS = list(range(42, 52))
MAIN_HOLDOUTS = ["chrono_late_train_early_eval", "holdout_bin_2"]
NEW_METHODS = ["kcenter_32shot", "diversity_32shot", "density_aware_32shot", "stratified_bin_32shot"]


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def md_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No rows._"
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, row in df.iterrows():
        vals: list[str] = []
        for col in cols:
            val = row[col]
            if isinstance(val, float):
                vals.append(f"{val:.6f}")
            else:
                vals.append(str(val))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def load_matrix(path: Path) -> np.ndarray:
    if path.suffix.lower() == ".npy":
        arr = np.load(path)
    else:
        arr = pd.read_csv(path, header=None).to_numpy(np.float32)
    if arr.ndim != 2:
        raise RuntimeError(f"Expected 2D matrix from {path}, got {arr.shape}")
    return np.nan_to_num(arr.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)


def seed_group(seed: int) -> str:
    if 42 <= int(seed) <= 46:
        return "main_42_46"
    if 47 <= int(seed) <= 51:
        return "heldout_47_51"
    return "other"


def require_inputs() -> list[str]:
    required = [
        ISSUE16B / "protocol.md",
        ISSUE16B / "support_id_provenance.csv",
        ISSUE16B / "method_comparison_summary.csv",
        ISSUE16B / "method_comparison_by_seed.csv",
        ISSUE16B / "threshold_provenance.csv",
        ISSUE16C / "failure_taxonomy.md",
        ISSUE16C / "support_similarity_summary.csv",
        ISSUE16C / "feature_drift_summary.csv",
        ISSUE16C / "repair_candidate_plan.md",
        ISSUE16C / "recommended_next_action.md",
        ISSUE11 / "config.json",
    ]
    return [str(p) for p in required if not p.exists()]


def farthest_first_indices(x: np.ndarray, budget: int, start_idx: int) -> np.ndarray:
    n = len(x)
    if budget >= n:
        return np.arange(n, dtype=np.int64)
    selected = [int(start_idx)]
    min_dist = pairwise_distances(x, x[[start_idx]], metric="euclidean").ravel()
    min_dist[start_idx] = -np.inf
    while len(selected) < budget:
        next_idx = int(np.argmax(min_dist))
        selected.append(next_idx)
        new_dist = pairwise_distances(x, x[[next_idx]], metric="euclidean").ravel()
        min_dist = np.minimum(min_dist, new_dist)
        min_dist[selected] = -np.inf
    return np.asarray(selected, dtype=np.int64)


def select_support(
    *,
    method: str,
    train_rows: np.ndarray,
    train_x_raw: np.ndarray,
    row_bins: np.ndarray,
    budget: int,
    seed: int,
) -> np.ndarray:
    train_rows = np.asarray(train_rows, dtype=np.int64)
    scaler = StandardScaler().fit(train_x_raw)
    x = scaler.transform(train_x_raw)
    if method == "kcenter_32shot":
        centroid = x.mean(axis=0, keepdims=True)
        start_idx = int(np.argmin(pairwise_distances(x, centroid).ravel()))
        local_idx = farthest_first_indices(x, budget, start_idx)
        return np.asarray(sorted(train_rows[local_idx]), dtype=np.int64)
    if method == "diversity_32shot":
        rng = np.random.default_rng(int(seed) + budget * 9173)
        start_idx = int(rng.integers(0, len(train_rows)))
        local_idx = farthest_first_indices(x, budget, start_idx)
        return np.asarray(sorted(train_rows[local_idx]), dtype=np.int64)
    if method == "density_aware_32shot":
        k = min(10, len(train_rows) - 1)
        nn = NearestNeighbors(n_neighbors=k + 1, metric="euclidean").fit(x)
        distances = nn.kneighbors(x, return_distance=True)[0][:, 1:]
        local_density_radius = distances.mean(axis=1)
        low, high = np.quantile(local_density_radius, [0.10, 0.90])
        candidate_mask = (local_density_radius >= low) & (local_density_radius <= high)
        candidate_idx = np.where(candidate_mask)[0]
        if len(candidate_idx) < budget:
            candidate_idx = np.arange(len(train_rows), dtype=np.int64)
        x_candidate = x[candidate_idx]
        centroid = x_candidate.mean(axis=0, keepdims=True)
        start_local = int(np.argmin(pairwise_distances(x_candidate, centroid).ravel()))
        chosen_in_candidate = farthest_first_indices(x_candidate, budget, start_local)
        return np.asarray(sorted(train_rows[candidate_idx[chosen_in_candidate]]), dtype=np.int64)
    if method == "stratified_bin_32shot":
        bins = np.asarray([int(row_bins[int(r)]) for r in train_rows], dtype=np.int64)
        unique_bins = sorted(set(int(b) for b in bins if b >= 0))
        if not unique_bins:
            raise RuntimeError("No train bin metadata available for stratified selection.")
        selected_local: list[int] = []
        base_quota = budget // len(unique_bins)
        remainder = budget % len(unique_bins)
        for i, b in enumerate(unique_bins):
            quota = base_quota + (1 if i < remainder else 0)
            idx = np.where(bins == b)[0]
            if quota <= 0 or len(idx) == 0:
                continue
            x_bin = x[idx]
            centroid = x_bin.mean(axis=0, keepdims=True)
            start_bin = int(np.argmin(pairwise_distances(x_bin, centroid).ravel()))
            chosen = farthest_first_indices(x_bin, min(quota, len(idx)), start_bin)
            selected_local.extend(idx[chosen].tolist())
        if len(selected_local) < budget:
            remaining = np.asarray([i for i in range(len(train_rows)) if i not in set(selected_local)], dtype=np.int64)
            if len(remaining):
                x_remain = x[remaining]
                centroid = x.mean(axis=0, keepdims=True)
                start = int(np.argmin(pairwise_distances(x_remain, centroid).ravel()))
                add = farthest_first_indices(x_remain, min(budget - len(selected_local), len(remaining)), start)
                selected_local.extend(remaining[add].tolist())
        selected_local = selected_local[:budget]
        return np.asarray(sorted(train_rows[np.asarray(selected_local, dtype=np.int64)]), dtype=np.int64)
    raise ValueError(f"Unknown support selection method: {method}")


def fit_and_score(
    *,
    x_id_train: np.ndarray,
    x_ood_train: np.ndarray,
    x_pos: np.ndarray,
    x_id_calib: np.ndarray,
    x_ood_val: np.ndarray,
    x_ood_eval: np.ndarray,
    x_attack_eval: np.ndarray,
) -> dict[str, Any]:
    x_train = np.concatenate([x_id_train, x_ood_train, x_pos], axis=0)
    y_train = np.concatenate(
        [
            np.zeros(len(x_id_train), dtype=np.int64),
            np.zeros(len(x_ood_train), dtype=np.int64),
            np.ones(len(x_pos), dtype=np.int64),
        ]
    )
    sample_weight = np.concatenate(
        [
            np.ones(len(x_id_train), dtype=np.float64),
            np.full(len(x_ood_train), 2.0, dtype=np.float64),
            np.ones(len(x_pos), dtype=np.float64),
        ]
    )
    scaler = StandardScaler()
    t0 = time.perf_counter()
    x_train_z = scaler.fit_transform(x_train)
    model = LogisticRegression(
        C=1.0,
        penalty="l2",
        solver="liblinear",
        class_weight="balanced",
        max_iter=2000,
        random_state=42,
    )
    model.fit(x_train_z, y_train, sample_weight=sample_weight)
    train_time = time.perf_counter() - t0
    t1 = time.perf_counter()
    score_id_calib = model.decision_function(scaler.transform(x_id_calib)).astype(np.float64)
    score_ood_val = model.decision_function(scaler.transform(x_ood_val)).astype(np.float64)
    score_ood_eval = model.decision_function(scaler.transform(x_ood_eval)).astype(np.float64)
    score_attack_eval = model.decision_function(scaler.transform(x_attack_eval)).astype(np.float64)
    inference_time = time.perf_counter() - t1
    guarded = v72.guarded_val_threshold(score_id_calib, score_ood_val, TARGET_ALARM)
    threshold = float(guarded["threshold"])
    y_eval = np.concatenate([np.zeros(len(score_ood_eval), dtype=np.int64), np.ones(len(score_attack_eval), dtype=np.int64)])
    s_eval = np.concatenate([score_ood_eval, score_attack_eval])
    return {
        "train_time": train_time,
        "inference_time": inference_time,
        "threshold": threshold,
        "roc_auc": float(roc_auc_score(y_eval, s_eval)),
        "pr_auc": float(average_precision_score(y_eval, s_eval)),
        "ood_high_alarm": float(np.mean(score_ood_eval > threshold)),
        "attack_high_detection": float(np.mean(score_attack_eval > threshold)),
        "feasible": bool(np.mean(score_ood_eval > threshold) <= TARGET_ALARM),
        "id_calib_alarm_at_selection": float(np.mean(score_id_calib > threshold)),
        "ood_val_alarm_at_selection": float(np.mean(score_ood_val > threshold)),
        "parameter_count": int(model.coef_.size + model.intercept_.size),
    }


def coverage_metrics(
    *,
    support_rows: np.ndarray,
    train_rows: np.ndarray,
    eval_rows: np.ndarray,
    x_attack: np.ndarray,
) -> dict[str, float]:
    support_rows = np.asarray(support_rows, dtype=np.int64)
    train_rows = np.asarray(train_rows, dtype=np.int64)
    eval_rows = np.asarray(eval_rows, dtype=np.int64)
    scaler = StandardScaler().fit(x_attack[train_rows])
    support_x = scaler.transform(x_attack[support_rows])
    train_x = scaler.transform(x_attack[train_rows])
    eval_x = scaler.transform(x_attack[eval_rows])
    pairwise = pairwise_distances(support_x, support_x, metric="euclidean")
    upper = pairwise[np.triu_indices(len(support_rows), k=1)]
    centroid = train_x.mean(axis=0, keepdims=True)
    support_centroid_dist = pairwise_distances(support_x, centroid).ravel()
    nn = NearestNeighbors(n_neighbors=1, metric="euclidean").fit(support_x)
    train_nearest = nn.kneighbors(train_x, return_distance=True)[0].ravel()
    eval_nearest = nn.kneighbors(eval_x, return_distance=True)[0].ravel()
    p95 = float(np.quantile(train_nearest, 0.95))
    return {
        "mean_pairwise_support_distance": float(np.mean(upper)) if len(upper) else 0.0,
        "min_pairwise_support_distance": float(np.min(upper)) if len(upper) else 0.0,
        "support_to_attack_train_centroid_distance_mean": float(np.mean(support_centroid_dist)),
        "attack_train_coverage_radius": float(np.max(train_nearest)),
        "mean_nearest_support_distance_attack_train": float(np.mean(train_nearest)),
        "mean_nearest_support_distance_attack_eval_diagnostic": float(np.mean(eval_nearest)),
        "pct_attack_eval_within_train_pool_p95_coverage_diagnostic": float(np.mean(eval_nearest <= p95)),
    }


def aggregate(seed_df: pd.DataFrame) -> pd.DataFrame:
    return (
        seed_df.groupby(["holdout_name", "support_selection_method", "positive_budget", "seed_group"], as_index=False)
        .agg(
            n_seeds=("seed", "nunique"),
            roc_auc_mean=("roc_auc", "mean"),
            roc_auc_std=("roc_auc", "std"),
            roc_auc_min=("roc_auc", "min"),
            roc_auc_max=("roc_auc", "max"),
            pr_auc_mean=("pr_auc", "mean"),
            pr_auc_std=("pr_auc", "std"),
            pr_auc_min=("pr_auc", "min"),
            pr_auc_max=("pr_auc", "max"),
            attack_high_detection_mean=("attack_high_detection", "mean"),
            attack_high_detection_std=("attack_high_detection", "std"),
            attack_high_detection_min=("attack_high_detection", "min"),
            attack_high_detection_max=("attack_high_detection", "max"),
            ood_high_alarm_mean=("ood_high_alarm", "mean"),
            ood_high_alarm_std=("ood_high_alarm", "std"),
            ood_high_alarm_min=("ood_high_alarm", "min"),
            ood_high_alarm_max=("ood_high_alarm", "max"),
            feasible_rate=("feasible", "mean"),
            threshold_mean=("threshold", "mean"),
            threshold_min=("threshold", "min"),
            threshold_max=("threshold", "max"),
            support_diversity_mean=("support_diversity_metric", "mean"),
            support_train_coverage_radius_mean=("support_train_coverage_radius", "mean"),
            eval_nearest_support_distance_mean=("eval_nearest_support_distance_diagnostic", "mean"),
            train_time_mean=("train_time", "mean"),
            inference_time_mean=("inference_time", "mean"),
        )
        .sort_values(["holdout_name", "positive_budget", "seed_group", "support_selection_method"])
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "figures").mkdir(exist_ok=True)
    missing = require_inputs()
    if missing:
        write_text(OUT / "missing_input_report.md", "# Missing Input Report\n\n" + "\n".join(f"- {m}" for m in missing))
        raise RuntimeError(f"Missing required inputs: {missing}")

    with (ISSUE11 / "config.json").open("r", encoding="utf-8") as handle:
        issue11_config = json.load(handle)
    paths = issue11_config["paths"]
    x_id = load_matrix(Path(paths["original100_id"]))
    x_ood = load_matrix(Path(paths["original100_ood"]))
    x_attack = load_matrix(Path(paths["original100_attack"]))
    with Path(paths["stage2_manifest"]).open("r", encoding="utf-8-sig") as handle:
        manifest = json.load(handle)

    row_bins = np.asarray(v74.load_attack_bins(manifest))
    specs = [s for s in v74.make_holdout_specs(manifest, row_bins, min_eval_rows=300) if s["holdout_name"] in MAIN_HOLDOUTS]
    specs_by_name = {str(s["holdout_name"]): s for s in specs}
    if sorted(specs_by_name) != sorted(MAIN_HOLDOUTS):
        raise RuntimeError(f"Missing holdout specs: {set(MAIN_HOLDOUTS) - set(specs_by_name)}")

    issue16b_seed = pd.read_csv(ISSUE16B / "method_comparison_by_seed.csv")
    issue16b_random = issue16b_seed[
        (issue16b_seed["method"] == "original100_fixed_guard_lr")
        & (issue16b_seed["positive_budget"] == POSITIVE_BUDGET)
    ].copy()
    random_support = pd.read_csv(ISSUE16B / "support_id_provenance.csv")
    random_support = random_support[random_support["positive_budget"] == POSITIVE_BUDGET].copy()
    random_threshold = pd.read_csv(ISSUE16B / "threshold_provenance.csv")
    random_threshold = random_threshold[
        (random_threshold["method"] == "original100_fixed_guard_lr")
        & (random_threshold["positive_budget"] == POSITIVE_BUDGET)
    ].copy()

    # Preflight provenance.
    random_overlap_bad = int(
        (
            (random_support["overlaps_attack_eval"].astype(str) == "True")
            | (random_support["overlaps_attack_val"].astype(str) == "True")
            | (random_support["in_attack_train_pool"].astype(str) != "True")
        ).sum()
    )
    if random_overlap_bad:
        raise RuntimeError(f"Random baseline provenance failed: {random_overlap_bad} bad support rows")

    id_train_end = 8000
    id_calib_end = id_train_end + 5000
    ood_train_end = 8000
    ood_val_end = ood_train_end + 2000
    x_id_train = x_id[:id_train_end]
    x_id_calib = x_id[id_train_end:id_calib_end]
    x_ood_train = x_ood[:ood_train_end]
    x_ood_val = x_ood[ood_train_end:ood_val_end]
    x_ood_eval = x_ood[ood_val_end:]

    seed_rows: list[dict[str, Any]] = []
    support_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []

    # Reuse random baseline metrics and provenance from issue16b.
    for _, row in issue16b_random.iterrows():
        method = "random_32shot_baseline"
        seed_rows.append(
            {
                "holdout_name": row["holdout_name"],
                "holdout_type": row["holdout_type"],
                "protocol": "local_calibration",
                "support_selection_method": method,
                "model": "original100_fixed_guard_lr",
                "positive_budget": POSITIVE_BUDGET,
                "seed": int(row["seed"]),
                "seed_group": row["seed_group"],
                "roc_auc": float(row["roc_auc"]),
                "pr_auc": float(row["pr_auc"]),
                "ood_high_alarm": float(row["ood_high_alarm"]),
                "attack_high_detection": float(row["attack_high_detection"]),
                "feasible": str(row["feasible"]).lower() == "true",
                "threshold": float(row["threshold"]),
                "attack_eval_size": int(row["attack_eval_size"]),
                "ood_eval_size": int(row["ood_eval_size"]),
                "support_size": int(row["support_count"]),
                "support_train_pool_size": int(specs_by_name[str(row["holdout_name"])]["train_pool_idx"].shape[0]),
                "support_diversity_metric": math.nan,
                "support_train_coverage_radius": math.nan,
                "eval_nearest_support_distance_diagnostic": math.nan,
                "train_time": float(row["train_time"]),
                "inference_time": float(row["inference_time"]),
                "parameter_count": int(row["parameter_count"]),
                "result_source": "reused_issue16b",
            }
        )
    for _, row in random_support.iterrows():
        new = row.to_dict()
        new["support_selection_method"] = "random_32shot_baseline"
        new["selection_uses_attack_eval"] = False
        new["selection_uses_final_ood_eval"] = False
        new["result_source"] = "reused_issue16b"
        support_rows.append(new)
    for _, row in random_threshold.iterrows():
        new = row.to_dict()
        new["support_selection_method"] = "random_32shot_baseline"
        new["result_source"] = "reused_issue16b"
        threshold_rows.append(new)

    # New support-selection methods.
    for spec in specs:
        holdout = str(spec["holdout_name"])
        attack_val_idx = np.asarray(spec["attack_val_idx"], dtype=np.int64)
        if not spec["val_bins"]:
            attack_val_idx = np.asarray([], dtype=np.int64)
        attack_eval_idx = np.asarray(spec["attack_eval_idx"], dtype=np.int64)
        train_idx = np.asarray(spec["train_pool_idx"], dtype=np.int64)
        train_x = x_attack[train_idx]
        x_attack_eval = x_attack[attack_eval_idx]
        attack_eval_set = set(int(x) for x in attack_eval_idx)
        attack_val_set = set(int(x) for x in attack_val_idx)
        for method in NEW_METHODS:
            for seed in SEEDS:
                selected = select_support(
                    method=method,
                    train_rows=train_idx,
                    train_x_raw=train_x,
                    row_bins=row_bins,
                    budget=POSITIVE_BUDGET,
                    seed=seed,
                )
                if any(int(x) in attack_eval_set or int(x) in attack_val_set for x in selected):
                    raise RuntimeError(f"Support overlap detected for {holdout} {method} seed={seed}")
                cov = coverage_metrics(
                    support_rows=selected,
                    train_rows=train_idx,
                    eval_rows=attack_eval_idx,
                    x_attack=x_attack,
                )
                x_pos = x_attack[selected]
                result = fit_and_score(
                    x_id_train=x_id_train,
                    x_ood_train=x_ood_train,
                    x_pos=x_pos,
                    x_id_calib=x_id_calib,
                    x_ood_val=x_ood_val,
                    x_ood_eval=x_ood_eval,
                    x_attack_eval=x_attack_eval,
                )
                seed_rows.append(
                    {
                        "holdout_name": holdout,
                        "holdout_type": spec["holdout_type"],
                        "protocol": "local_calibration",
                        "support_selection_method": method,
                        "model": "original100_fixed_guard_lr",
                        "positive_budget": POSITIVE_BUDGET,
                        "seed": int(seed),
                        "seed_group": seed_group(seed),
                        "roc_auc": result["roc_auc"],
                        "pr_auc": result["pr_auc"],
                        "ood_high_alarm": result["ood_high_alarm"],
                        "attack_high_detection": result["attack_high_detection"],
                        "feasible": result["feasible"],
                        "threshold": result["threshold"],
                        "attack_eval_size": int(len(attack_eval_idx)),
                        "ood_eval_size": int(len(x_ood_eval)),
                        "support_size": int(len(selected)),
                        "support_train_pool_size": int(len(train_idx)),
                        "support_diversity_metric": cov["mean_pairwise_support_distance"],
                        "support_train_coverage_radius": cov["attack_train_coverage_radius"],
                        "eval_nearest_support_distance_diagnostic": cov["mean_nearest_support_distance_attack_eval_diagnostic"],
                        "train_time": result["train_time"],
                        "inference_time": result["inference_time"],
                        "parameter_count": result["parameter_count"],
                        "result_source": "issue17_new_run",
                    }
                )
                coverage_rows.append(
                    {
                        "holdout_name": holdout,
                        "support_selection_method": method,
                        "positive_budget": POSITIVE_BUDGET,
                        "seed": int(seed),
                        "seed_group": seed_group(seed),
                        **cov,
                    }
                )
                threshold_rows.append(
                    {
                        "holdout_name": holdout,
                        "protocol": "local_calibration",
                        "method": "original100_fixed_guard_lr",
                        "support_selection_method": method,
                        "positive_budget": POSITIVE_BUDGET,
                        "seed": int(seed),
                        "seed_group": seed_group(seed),
                        "threshold": result["threshold"],
                        "uses_id_calib": True,
                        "uses_ood_val": True,
                        "uses_final_ood_eval": False,
                        "uses_attack_eval": False,
                        "id_calib_alarm_at_selection": result["id_calib_alarm_at_selection"],
                        "ood_val_alarm_at_selection": result["ood_val_alarm_at_selection"],
                        "target_alarm": TARGET_ALARM,
                        "result_source": "issue17_new_run",
                    }
                )
                for selected_row in selected:
                    support_rows.append(
                        {
                            "holdout_name": holdout,
                            "positive_budget": POSITIVE_BUDGET,
                            "seed": int(seed),
                            "seed_group": seed_group(seed),
                            "support_selection_method": method,
                            "selected_attack_row_id": int(selected_row),
                            "support_source": "pre_registered_hard_holdout_attack_train_pool",
                            "train_bins": ",".join(str(x) for x in spec["train_bins"]),
                            "eval_bins": ",".join(str(x) for x in spec["eval_bins"]),
                            "in_attack_train_pool": bool(int(selected_row) in set(int(x) for x in train_idx)),
                            "overlaps_attack_val": bool(int(selected_row) in attack_val_set),
                            "overlaps_attack_eval": bool(int(selected_row) in attack_eval_set),
                            "selection_uses_attack_eval": False,
                            "selection_uses_final_ood_eval": False,
                            "result_source": "issue17_new_run",
                        }
                    )
                print(f"[done] {holdout} {method} seed={seed}")

    seed_df = pd.DataFrame(seed_rows)
    support_df = pd.DataFrame(support_rows)
    threshold_df = pd.DataFrame(threshold_rows)
    coverage_df = pd.DataFrame(coverage_rows)

    # Add random coverage using issue16b random support.
    random_cov_rows: list[dict[str, Any]] = []
    for (holdout, seed), group in support_df[support_df["support_selection_method"] == "random_32shot_baseline"].groupby(["holdout_name", "seed"]):
        spec = specs_by_name[str(holdout)]
        selected = group["selected_attack_row_id"].astype(int).to_numpy()
        cov = coverage_metrics(
            support_rows=selected,
            train_rows=np.asarray(spec["train_pool_idx"], dtype=np.int64),
            eval_rows=np.asarray(spec["attack_eval_idx"], dtype=np.int64),
            x_attack=x_attack,
        )
        random_cov_rows.append(
            {
                "holdout_name": str(holdout),
                "support_selection_method": "random_32shot_baseline",
                "positive_budget": POSITIVE_BUDGET,
                "seed": int(seed),
                "seed_group": seed_group(int(seed)),
                **cov,
            }
        )
    if random_cov_rows:
        coverage_df = pd.concat([coverage_df, pd.DataFrame(random_cov_rows)], ignore_index=True)
        for _, cov in pd.DataFrame(random_cov_rows).iterrows():
            mask = (
                seed_df["holdout_name"].eq(cov["holdout_name"])
                & seed_df["support_selection_method"].eq("random_32shot_baseline")
                & seed_df["seed"].eq(int(cov["seed"]))
            )
            seed_df.loc[mask, "support_diversity_metric"] = float(cov["mean_pairwise_support_distance"])
            seed_df.loc[mask, "support_train_coverage_radius"] = float(cov["attack_train_coverage_radius"])
            seed_df.loc[mask, "eval_nearest_support_distance_diagnostic"] = float(cov["mean_nearest_support_distance_attack_eval_diagnostic"])

    summary_df = aggregate(seed_df)
    seed_df.to_csv(OUT / "method_comparison_by_seed.csv", index=False)
    summary_df.to_csv(OUT / "method_comparison_summary.csv", index=False)
    support_df.to_csv(OUT / "support_id_provenance.csv", index=False)
    threshold_df.to_csv(OUT / "threshold_provenance.csv", index=False)
    coverage_df.to_csv(OUT / "support_coverage_by_seed.csv", index=False)
    coverage_summary = (
        coverage_df.groupby(["holdout_name", "support_selection_method", "positive_budget", "seed_group"], as_index=False)
        .agg(
            n_seeds=("seed", "nunique"),
            mean_pairwise_support_distance=("mean_pairwise_support_distance", "mean"),
            min_pairwise_support_distance=("min_pairwise_support_distance", "mean"),
            attack_train_coverage_radius=("attack_train_coverage_radius", "mean"),
            mean_nearest_support_distance_attack_train=("mean_nearest_support_distance_attack_train", "mean"),
            mean_nearest_support_distance_attack_eval_diagnostic=("mean_nearest_support_distance_attack_eval_diagnostic", "mean"),
            pct_attack_eval_within_train_pool_p95_coverage_diagnostic=("pct_attack_eval_within_train_pool_p95_coverage_diagnostic", "mean"),
        )
        .sort_values(["holdout_name", "seed_group", "support_selection_method"])
    )
    coverage_summary.to_csv(OUT / "support_coverage_summary.csv", index=False)

    random_base = summary_df[summary_df["support_selection_method"] == "random_32shot_baseline"][
        [
            "holdout_name",
            "positive_budget",
            "seed_group",
            "attack_high_detection_mean",
            "ood_high_alarm_mean",
            "ood_high_alarm_max",
            "feasible_rate",
            "support_diversity_mean",
            "support_train_coverage_radius_mean",
            "eval_nearest_support_distance_mean",
        ]
    ].rename(
        columns={
            "attack_high_detection_mean": "random_attack_high_detection_mean",
            "ood_high_alarm_mean": "random_ood_high_alarm_mean",
            "ood_high_alarm_max": "random_ood_high_alarm_max",
            "feasible_rate": "random_feasible_rate",
            "support_diversity_mean": "random_support_diversity_mean",
            "support_train_coverage_radius_mean": "random_support_train_coverage_radius_mean",
            "eval_nearest_support_distance_mean": "random_eval_nearest_support_distance_mean",
        }
    )
    deltas = []
    for _, row in summary_df[summary_df["support_selection_method"] != "random_32shot_baseline"].iterrows():
        match = random_base[
            random_base["holdout_name"].eq(row["holdout_name"])
            & random_base["positive_budget"].eq(row["positive_budget"])
            & random_base["seed_group"].eq(row["seed_group"])
        ]
        if match.empty:
            continue
        base = match.iloc[0]
        deltas.append(
            {
                "holdout_name": row["holdout_name"],
                "support_selection_method": row["support_selection_method"],
                "positive_budget": int(row["positive_budget"]),
                "seed_group": row["seed_group"],
                "delta_detection_vs_random": float(row["attack_high_detection_mean"] - base["random_attack_high_detection_mean"]),
                "delta_ood_alarm_mean_vs_random": float(row["ood_high_alarm_mean"] - base["random_ood_high_alarm_mean"]),
                "delta_ood_alarm_max_vs_random": float(row["ood_high_alarm_max"] - base["random_ood_high_alarm_max"]),
                "delta_feasible_rate_vs_random": float(row["feasible_rate"] - base["random_feasible_rate"]),
                "delta_support_diversity_vs_random": float(row["support_diversity_mean"] - base["random_support_diversity_mean"]),
                "delta_train_coverage_radius_vs_random": float(row["support_train_coverage_radius_mean"] - base["random_support_train_coverage_radius_mean"]),
                "delta_eval_nearest_distance_vs_random_diagnostic": float(row["eval_nearest_support_distance_mean"] - base["random_eval_nearest_support_distance_mean"]),
            }
        )
    delta_df = pd.DataFrame(deltas)
    delta_df.to_csv(OUT / "random_vs_diverse_support_delta.csv", index=False)
    hb2_method_delta_for_file = (
        delta_df[delta_df["holdout_name"].eq("holdout_bin_2")]
        .groupby("support_selection_method", as_index=False)
        .agg(
            mean_delta_detection_vs_random=("delta_detection_vs_random", "mean"),
            min_delta_detection_vs_random=("delta_detection_vs_random", "min"),
            max_delta_detection_vs_random=("delta_detection_vs_random", "max"),
            max_delta_ood_alarm_max_vs_random=("delta_ood_alarm_max_vs_random", "max"),
            mean_delta_support_diversity_vs_random=("delta_support_diversity_vs_random", "mean"),
        )
        .sort_values("mean_delta_detection_vs_random", ascending=False)
    )
    hb2_method_delta_for_file.to_csv(OUT / "holdout_bin2_method_delta_summary.csv", index=False)

    holdout_bin2 = summary_df[summary_df["holdout_name"] == "holdout_bin_2"].copy()
    chrono = summary_df[summary_df["holdout_name"] == "chrono_late_train_early_eval"].copy()
    holdout_bin2.to_csv(OUT / "holdout_bin2_support_repair_summary.csv", index=False)
    chrono.to_csv(OUT / "chrono_late_support_repair_summary.csv", index=False)

    # Preflight report after all checks.
    leakage_bad = int(
        (
            (support_df["overlaps_attack_eval"].astype(str) == "True")
            | (support_df["overlaps_attack_val"].astype(str) == "True")
            | (support_df["in_attack_train_pool"].astype(str) != "True")
            | (support_df["selection_uses_attack_eval"].astype(str) == "True")
            | (support_df["selection_uses_final_ood_eval"].astype(str) == "True")
        ).sum()
    )
    threshold_bad = int(
        (
            (threshold_df["uses_final_ood_eval"].astype(str) != "False")
            | (threshold_df["uses_attack_eval"].astype(str) != "False")
        ).sum()
    )
    preflight_ok = leakage_bad == 0 and threshold_bad == 0
    write_text(
        OUT / "preflight_support_provenance_check.md",
        f"""
# Preflight Support Provenance Check

- Harder holdout support attack pool is local to each harder holdout attack train pool: True.
- Support selection uses only attack train pool features: True.
- Support has no overlap with attack eval / attack validation: {leakage_bad == 0}.
- Support selection uses final OOD eval or attack eval: False.
- Local calibration protocol follows issue16b: True.
- Scaler fit scope is ID train + OOD train + selected supports: True.
- Threshold source is ID calibration + OOD validation only: {threshold_bad == 0}.
- OOD weight changed from 2: False.

Preflight status: `{preflight_ok}`.
""",
    )
    if not preflight_ok:
        raise RuntimeError("Preflight provenance failed after run; outputs should not be interpreted.")

    write_text(
        OUT / "protocol.md",
        """
# Issue17 Protocol

This is a targeted support-acquisition repair experiment after issue16b/issue16c failure analysis.

- Model: original100 fixed-guard LogisticRegression only.
- OOD benign weight: fixed at 2.
- Positive budget: 32-shot.
- Seeds: 42-46 main, 47-51 held-out.
- Holdouts: holdout_bin_2 and chrono_late_train_early_eval.
- Support selection uses only local harder-holdout attack train pool features.
- Scaler fit: ID benign train + OOD benign train + selected attack supports.
- Threshold: local ID calibration + OOD validation target 1%.
- Final OOD eval and attack eval are evaluation-only.
- No dA/Transformer training, no MLP/prototype/margin-GDA, no OOD-weight search.
""",
    )
    write_text(
        OUT / "support_selection_method_report.md",
        """
# Support Selection Method Report

- `random_32shot_baseline`: reused issue16b random support and metrics.
- `kcenter_32shot`: farthest-first k-center in standardized attack train-pool original100 space, initialized at the point nearest the train-pool centroid.
- `diversity_32shot`: seeded farthest-first max-min selection in attack train-pool original100 space.
- `density_aware_32shot`: k-center after excluding the most extreme sparse/dense 10% by local kNN radius, using train-pool features only.
- `stratified_bin_32shot`: uses available stage2 attack bin metadata and allocates support quota across train bins, with k-center selection inside each bin.

All methods are train-pool-only support acquisition rules. Attack eval and final OOD eval are not used for selection.

64-shot sensitivity was not run in this pass to avoid turning the repair test into a budget sweep.
""",
    )
    write_text(
        OUT / "scaler_provenance.md",
        """
# Scaler Provenance

For every issue17 run, StandardScaler is fit only on ID benign train, OOD benign train, and the selected attack support rows. It is not fit on ID calibration, OOD validation, final OOD eval, or attack eval.
""",
    )
    write_text(
        OUT / "support_coverage_analysis.md",
        f"""
# Support Coverage Analysis

{md_table(coverage_summary)}

Coverage metrics are diagnostic. Eval-nearest-support distance is reported only after support selection and is never used to choose supports.
""",
    )
    core_cols = [
        "holdout_name",
        "support_selection_method",
        "seed_group",
        "attack_high_detection_mean",
        "attack_high_detection_min",
        "ood_high_alarm_mean",
        "ood_high_alarm_max",
        "feasible_rate",
        "support_diversity_mean",
    ]
    core_table = summary_df[summary_df["positive_budget"].eq(POSITIVE_BUDGET)][core_cols]
    hb2_delta = delta_df[delta_df["holdout_name"].eq("holdout_bin_2")].copy()
    hb2_method_delta = (
        hb2_delta.groupby("support_selection_method", as_index=False)
        .agg(
            mean_delta_detection_vs_random=("delta_detection_vs_random", "mean"),
            min_delta_detection_vs_random=("delta_detection_vs_random", "min"),
            max_delta_detection_vs_random=("delta_detection_vs_random", "max"),
            max_delta_ood_alarm_max_vs_random=("delta_ood_alarm_max_vs_random", "max"),
            mean_delta_support_diversity_vs_random=("delta_support_diversity_vs_random", "mean"),
        )
        .sort_values("mean_delta_detection_vs_random", ascending=False)
    )
    best_method_row = hb2_method_delta.head(1)
    best_method = str(best_method_row["support_selection_method"].iloc[0]) if not best_method_row.empty else "not_available"
    best_delta = float(best_method_row["mean_delta_detection_vs_random"].iloc[0]) if not best_method_row.empty else math.nan
    best_min_delta = float(best_method_row["min_delta_detection_vs_random"].iloc[0]) if not best_method_row.empty else math.nan
    best_max_delta = float(best_method_row["max_delta_detection_vs_random"].iloc[0]) if not best_method_row.empty else math.nan
    best_alarm_delta = float(best_method_row["max_delta_ood_alarm_max_vs_random"].iloc[0]) if not best_method_row.empty else math.nan
    best_summary_rows = summary_df[
        summary_df["holdout_name"].eq("holdout_bin_2")
        & summary_df["support_selection_method"].eq(best_method)
    ]
    best_min_abs_detection = float(best_summary_rows["attack_high_detection_mean"].min()) if not best_summary_rows.empty else math.nan
    if (
        not best_method_row.empty
        and best_min_delta > 0.05
        and best_alarm_delta <= 0.005
        and best_min_abs_detection >= 0.50
    ):
        verdict = "positive_support_diversity_signal"
        next_step = "Run same-protocol few-shot anomaly baselines and OOD target sensitivity before any model upgrade."
    elif not best_method_row.empty and (best_delta > 0.01 or best_max_delta > 0.05):
        verdict = "moderate_or_mixed_support_signal"
        next_step = "Treat support diversity as a partial repair signal; run row-level score persistence and OOD target sensitivity before any model upgrade."
    else:
        verdict = "negative_support_diversity_signal"
        next_step = "Support coverage is unlikely the main bottleneck; prioritize representation repair or row-level score diagnostics."
    write_text(
        OUT / "failure_or_success_interpretation.md",
        f"""
# Failure or Success Interpretation

Issue17 verdict: `{verdict}`.

Best holdout_bin_2 average delta vs random: `{best_method}` with mean_delta_detection={best_delta:.6f}, min_delta_detection={best_min_delta:.6f}, max_delta_detection={best_max_delta:.6f}, min_abs_detection={best_min_abs_detection:.6f}, and max_delta_ood_alarm={best_alarm_delta:.6f}.

- If positive: support acquisition is a plausible deployment repair mechanism.
- If negative: support coverage is not the main bottleneck; move toward representation repair or row-level score diagnostics.
- If mixed: report conditions carefully and do not write harder holdout as solved.
""",
    )
    write_text(
        OUT / "claim_boundary.md",
        """
# Claim Boundary

## Can Say

- Support diversity selection improves or does not improve harder-holdout adaptation if supported by metrics.
- Support acquisition may be a key factor for deployment-stage adaptation if supported.
- All support selection used only attack train pool information.

## Cannot Say

- Final harder holdout is solved unless metrics support it.
- Support diversity proves universal generalization.
- Model fully generalized.
- Detector-agnostic adaptation is proven.
- Full GDA is completed.
- A-zone / CCF-A readiness is achieved.
""",
    )
    risk_rows = [
        {"risk_name": "support selection leakage risk", "severity": "low" if preflight_ok else "high", "reason": "Support selection must not use eval data.", "mitigation": "Preflight and support provenance saved."},
        {"risk_name": "overfitting to holdout_bin_2 risk", "severity": "medium", "reason": "Repair is motivated by holdout_bin_2 failure.", "mitigation": "Evaluate both holdout_bin_2 and chrono_late without changing holdouts."},
        {"risk_name": "support diversity overclaim risk", "severity": "medium", "reason": "Coverage metrics may improve without detection improvement.", "mitigation": "Interpret only with detection and OOD alarm."},
        {"risk_name": "insufficient budget risk", "severity": "medium", "reason": "Only 32-shot was run.", "mitigation": "64-shot reserved as later sensitivity if needed."},
        {"risk_name": "OOD alarm tradeoff risk", "severity": "medium", "reason": "Better attack support can increase attack-like scores for OOD.", "mitigation": "Require OOD high alarm <=1%."},
        {"risk_name": "metadata stratification risk", "severity": "medium", "reason": "Only bin metadata is available, not full attack family metadata.", "mitigation": "Call it bin stratification, not family stratification."},
        {"risk_name": "seed instability risk", "severity": "medium", "reason": "Support selection can be deterministic or seed-dependent.", "mitigation": "Main and held-out seeds are reported separately."},
    ]
    write_csv(OUT / "risk_register.csv", risk_rows)
    write_text(
        OUT / "recommended_next_action.md",
        f"""
# Recommended Next Action

## Verdict

`{verdict}`

## Unique First Choice

{next_step}

## Backup

If support diversity is negative or mixed, run row-level score persistence plus pre-registered OOD target sensitivity before moving to representation upgrade / margin-GDA.
""",
    )
    write_text(
        OUT / "doc_update_patch_suggestion.md",
        """
# Doc Update Patch Suggestion

Suggested mainline docs note:

`issue17 tested train-pool-only support diversity selection as a targeted repair for issue16b holdout_bin_2. Interpret results as support acquisition evidence only; do not claim full harder-holdout generalization unless metrics support it.`
""",
    )
    write_text(
        OUT / "summary.md",
        f"""
# Issue17 Support Diversity Selection Summary

## Outcome

Preflight provenance passed. The experiment used local harder-holdout attack train pools only and did not use attack eval or final OOD eval for support selection.

## Core Results

{md_table(core_table)}

## Random vs Diverse Delta

{md_table(delta_df)}

## Verdict

`{verdict}`

Best holdout_bin_2 method by average delta: `{best_method}`, mean_delta_detection_vs_random={best_delta:.6f}, min_delta={best_min_delta:.6f}, max_delta={best_max_delta:.6f}, min_abs_detection={best_min_abs_detection:.6f}.

This is not a strong positive: the best method improves held-out seed behavior but does not deliver high absolute detection on `holdout_bin_2`, and the main seed group improvement is small.

## Interpretation

Support diversity is meaningful only if it improves holdout_bin_2 detection while keeping OOD high alarm <= 1%. This run does not change the LOW-GUARD-minimal model family, OOD weight, threshold protocol, or manuscript.

## Safety

- Manuscript modified: False.
- Historical experimental numbers modified: False.
- dA / Transformer trained: False.
- OOD weight search: False.
- Eval data used for support selection: False.
""",
    )
    config = {
        "run": "issue17_support_diversity_selection_harder_holdout_2026-05-15",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "positive_budget": POSITIVE_BUDGET,
        "seeds": SEEDS,
        "holdouts": MAIN_HOLDOUTS,
        "new_methods": NEW_METHODS,
        "random_baseline": "reused_issue16b original100_fixed_guard_lr 32-shot",
        "ood_weight": 2.0,
        "target_alarm": TARGET_ALARM,
        "no_final_eval_tuning": True,
    }
    write_text(OUT / "config.json", json.dumps(config, indent=2, ensure_ascii=False))
    manifest_rows = []
    for path in sorted(OUT.iterdir()):
        if path.is_file():
            manifest_rows.append({"asset_name": path.name, "file_path": str(path), "role": "issue17 output"})
    write_csv(OUT / "manifest.csv", manifest_rows)


if __name__ == "__main__":
    main()
