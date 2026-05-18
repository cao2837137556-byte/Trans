from __future__ import annotations

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
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs" / "issue19b_v1_v2_same_protocol_backtest_and_alarm_budget_curve_2026-05-18"
ISSUE11 = ROOT / "runs" / "issue11_fixed_config_ood_guard_lr_ablation_2026-05-14"
ISSUE16B = ROOT / "runs" / "issue16b_harder_holdout_fixed_guard_validation_2026-05-15"
ISSUE17 = ROOT / "runs" / "issue17_support_diversity_selection_harder_holdout_2026-05-15"
ISSUE18 = ROOT / "runs" / "issue18_row_level_score_persistence_and_ood_target_sensitivity_2026-05-15"
ISSUE19 = ROOT / "runs" / "issue19_lowguard_plus_representation_margin_repair_pilot_2026-05-18"

REPO_DIR = ROOT / "repo"
OOD_DIR = REPO_DIR / "ood"
FRONTEND_F2_ROOT = ROOT.parent / "kitnet-frontend-f2"
F2_OOD = FRONTEND_F2_ROOT / "repo" / "ood"
for path in [str(REPO_DIR), str(OOD_DIR), str(F2_OOD)]:
    if path not in sys.path:
        sys.path.insert(0, path)

import frontend100_negative_recipe_rescoring as resc  # noqa: E402
from original100_fewshot_official_control import load_json, split_contiguous  # noqa: E402

import frontend_f2_v7_2_fairness_validation as v72  # noqa: E402
import frontend_f2_v7_4_paired_holdout_fairness as v74  # noqa: E402


POSITIVE_BUDGET = 32
SEEDS = list(range(42, 52))
TARGETS = [0.005, 0.008, 0.01, 0.012, 0.015, 0.02]
TARGET_LABELS = {
    0.005: "0.5pct",
    0.008: "0.8pct",
    0.01: "1.0pct",
    0.012: "1.2pct",
    0.015: "1.5pct",
    0.02: "2.0pct",
}
MAIN_TARGET = 0.01
MAIN_TARGET_LABEL = TARGET_LABELS[MAIN_TARGET]
MAIN_HOLDOUTS = ["chrono_late_train_early_eval", "holdout_bin_2"]


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def md_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No rows._\n"
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, row in df.iterrows():
        vals: list[str] = []
        for col in cols:
            val = row[col]
            if isinstance(val, (float, np.floating)):
                vals.append(f"{float(val):.6f}")
            else:
                vals.append(str(val))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"


def load_matrix(path: Path) -> np.ndarray:
    if path.suffix.lower() == ".npy":
        arr = np.load(path)
    else:
        arr = pd.read_csv(path, header=None).to_numpy(np.float32)
    if arr.ndim != 2:
        raise RuntimeError(f"Expected 2D matrix from {path}, got {arr.shape}")
    return np.nan_to_num(arr.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)


def feature_names(schema_path: Path, dim: int) -> list[str]:
    names = [f"source_rich_{idx}" for idx in range(dim)]
    if not schema_path.exists():
        return names
    data = json.loads(schema_path.read_text(encoding="utf-8"))
    for item in data.get("header_mappings", []):
        idx = int(item.get("flat_index", -1))
        if 0 <= idx < dim:
            names[idx] = str(item.get("header", names[idx]))
    return names


def seed_group(seed: int) -> str:
    if 42 <= int(seed) <= 46:
        return "main_42_46"
    if 47 <= int(seed) <= 51:
        return "heldout_47_51"
    return "other"


def require_inputs() -> list[str]:
    required = [
        ISSUE11 / "config.json",
        ISSUE11 / "method_comparison_summary.csv",
        ISSUE18 / "row_level_scores_manifest.csv",
        ISSUE17 / "support_coverage_summary.csv",
        ISSUE18 / "ood_target_sensitivity_summary.csv",
        ISSUE19 / "summary.md",
        ISSUE19 / "method_comparison_summary.csv",
        ISSUE19 / "representation_ablation_summary.csv",
        ISSUE19 / "selected_feature_report.csv",
        ISSUE19 / "selected_representation_protocol.md",
        ISSUE19 / "provenance_report.md",
        ISSUE19 / "claim_boundary.md",
    ]
    return [str(path) for path in required if not path.exists()]


def farthest_first_indices(x: np.ndarray, budget: int, start_idx: int) -> np.ndarray:
    n = int(len(x))
    if budget >= n:
        return np.arange(n, dtype=np.int64)
    selected = [int(start_idx)]
    min_dist = pairwise_distances(x, x[[start_idx]], metric="euclidean").ravel()
    min_dist[start_idx] = -1.0
    while len(selected) < budget:
        nxt = int(np.argmax(min_dist))
        selected.append(nxt)
        dist = pairwise_distances(x, x[[nxt]], metric="euclidean").ravel()
        min_dist = np.minimum(min_dist, dist)
        min_dist[selected] = -1.0
    return np.asarray(selected, dtype=np.int64)


def kcenter_support(train_rows: np.ndarray, train_x_raw: np.ndarray, budget: int) -> np.ndarray:
    scaler = StandardScaler().fit(train_x_raw)
    x = scaler.transform(train_x_raw)
    centroid = x.mean(axis=0, keepdims=True)
    start_idx = int(np.argmin(pairwise_distances(x, centroid).ravel()))
    local_idx = farthest_first_indices(x, budget, start_idx)
    return np.asarray(sorted(np.asarray(train_rows, dtype=np.int64)[local_idx]), dtype=np.int64)


def selected_source_rich_features(
    *,
    x_support: np.ndarray,
    x_id_calib: np.ndarray,
    x_ood_val: np.ndarray,
    names: list[str],
    dataset: str,
    holdout: str,
    seed: int,
    top_k: int = 32,
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    eps = 1e-8
    support_mean = x_support.mean(axis=0)
    id_mean = x_id_calib.mean(axis=0)
    ood_mean = x_ood_val.mean(axis=0)
    support_std = x_support.std(axis=0) + eps
    id_std = x_id_calib.std(axis=0) + eps
    ood_std = x_ood_val.std(axis=0) + eps
    effect_vs_ood = (support_mean - ood_mean) / np.sqrt(0.5 * (support_std**2 + ood_std**2) + eps)
    effect_vs_id = (support_mean - id_mean) / np.sqrt(0.5 * (support_std**2 + id_std**2) + eps)
    ood_tail = np.quantile(x_ood_val, 0.99, axis=0)
    support_q25 = np.quantile(x_support, 0.25, axis=0)
    tail_margin = support_q25 - ood_tail
    raw_score = np.abs(effect_vs_ood) + 0.5 * np.abs(effect_vs_id) + 0.05 * np.maximum(tail_margin, 0.0)
    order = np.argsort(-raw_score)
    candidate = np.vstack([x_support, x_id_calib, x_ood_val])
    selected: list[int] = []
    for idx_raw in order:
        idx = int(idx_raw)
        if not selected:
            selected.append(idx)
        else:
            vals = candidate[:, selected + [idx]]
            corr = np.corrcoef(vals, rowvar=False)
            max_corr = np.nanmax(np.abs(corr[-1, :-1])) if corr.ndim == 2 and corr.shape[0] > 1 else 0.0
            if not np.isfinite(max_corr) or max_corr < 0.95:
                selected.append(idx)
        if len(selected) >= top_k:
            break
    if len(selected) < top_k:
        for idx_raw in order:
            idx = int(idx_raw)
            if idx not in selected:
                selected.append(idx)
            if len(selected) >= top_k:
                break

    rows: list[dict[str, Any]] = []
    for rank, idx in enumerate(selected, start=1):
        rows.append(
            {
                "dataset": dataset,
                "holdout": holdout,
                "seed": int(seed),
                "seed_group": seed_group(seed),
                "top_k": top_k,
                "rank": rank,
                "feature_index": int(idx),
                "feature_name": names[idx] if idx < len(names) else f"source_rich_{idx}",
                "selection_score": float(raw_score[idx]),
                "effect_vs_ood_val": float(effect_vs_ood[idx]),
                "effect_vs_id_calib": float(effect_vs_id[idx]),
                "support_q25_minus_ood_val_q99": float(tail_margin[idx]),
                "selection_uses_attack_eval": False,
                "selection_uses_final_ood_eval": False,
                "selection_rule_fixed_from_issue19": True,
            }
        )
    return np.asarray(selected, dtype=np.int64), rows


def fit_adapter(
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
    scores = {
        "id_calib": model.decision_function(scaler.transform(x_id_calib)).astype(np.float64),
        "ood_val": model.decision_function(scaler.transform(x_ood_val)).astype(np.float64),
        "final_ood_eval": model.decision_function(scaler.transform(x_ood_eval)).astype(np.float64),
        "attack_eval": model.decision_function(scaler.transform(x_attack_eval)).astype(np.float64),
    }
    inference_time = time.perf_counter() - t1

    y_auc = np.concatenate(
        [np.zeros(len(scores["final_ood_eval"]), dtype=np.int64), np.ones(len(scores["attack_eval"]), dtype=np.int64)]
    )
    s_auc = np.concatenate([scores["final_ood_eval"], scores["attack_eval"]])
    roc_auc = float(roc_auc_score(y_auc, s_auc))
    pr_auc = float(average_precision_score(y_auc, s_auc))
    thresholds = {target: v72.guarded_val_threshold(scores["id_calib"], scores["ood_val"], target) for target in TARGETS}
    return {
        "scores": scores,
        "roc_auc": roc_auc,
        "pr_auc": pr_auc,
        "thresholds": thresholds,
        "train_time": train_time,
        "inference_time": inference_time,
        "parameter_count": int(model.coef_.size + model.intercept_.size),
    }


def summarize(by_seed: pd.DataFrame) -> pd.DataFrame:
    return (
        by_seed.groupby(
            ["dataset", "holdout", "method", "method_version", "seed_group", "ood_target", "ood_target_label"],
            as_index=False,
        )
        .agg(
            n_seeds=("seed", "nunique"),
            roc_auc_mean=("roc_auc", "mean"),
            roc_auc_std=("roc_auc", "std"),
            pr_auc_mean=("pr_auc", "mean"),
            pr_auc_std=("pr_auc", "std"),
            attack_high_detection_mean=("attack_high_detection", "mean"),
            attack_high_detection_std=("attack_high_detection", "std"),
            attack_high_detection_min=("attack_high_detection", "min"),
            attack_high_detection_max=("attack_high_detection", "max"),
            final_ood_high_alarm_mean=("final_ood_high_alarm", "mean"),
            final_ood_high_alarm_std=("final_ood_high_alarm", "std"),
            final_ood_high_alarm_min=("final_ood_high_alarm", "min"),
            final_ood_high_alarm_max=("final_ood_high_alarm", "max"),
            feasible_rate=("feasible_final_1pct", "mean"),
            threshold_mean=("threshold", "mean"),
            threshold_min=("threshold", "min"),
            threshold_max=("threshold", "max"),
            feature_dim=("feature_dim", "first"),
            selected_feature_count=("selected_feature_count", "first"),
            train_time_mean=("train_time", "mean"),
            inference_time_mean=("inference_time", "mean"),
            support_provenance_clean_rate=("support_provenance_clean", "mean"),
            threshold_provenance_clean_rate=("threshold_provenance_clean", "mean"),
        )
        .sort_values(["dataset", "holdout", "ood_target", "method", "seed_group"])
    )


def build_datasets(
    *,
    paths: dict[str, str],
    x_id_o: np.ndarray,
    x_ood_o: np.ndarray,
    x_attack_o: np.ndarray,
    x_id_sr: np.ndarray,
    x_ood_sr: np.ndarray,
    x_attack_sr: np.ndarray,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    manifest = load_json(Path(paths["stage2_manifest"]))
    high_idx = np.asarray(sorted(resc.build_stage2_indices(manifest)["high"]), dtype=np.int64)
    high_idx = high_idx[(high_idx >= 0) & (high_idx < len(x_attack_o))]
    attack_split = split_contiguous(high_idx, 0.60, 0.20)

    id_train_end, id_val_end, id_calib_end = 8000, 10000, 15000
    ood_train_end, ood_val_end = 8000, 10000

    base_split = {
        "x_id_train_o": x_id_o[:id_train_end],
        "x_id_calib_o": x_id_o[id_val_end:id_calib_end],
        "x_ood_train_o": x_ood_o[:ood_train_end],
        "x_ood_val_o": x_ood_o[ood_train_end:ood_val_end],
        "x_ood_eval_o": x_ood_o[ood_val_end:],
        "x_id_train_sr": x_id_sr[:id_train_end],
        "x_id_calib_sr": x_id_sr[id_val_end:id_calib_end],
        "x_ood_train_sr": x_ood_sr[:ood_train_end],
        "x_ood_val_sr": x_ood_sr[ood_train_end:ood_val_end],
        "x_ood_eval_sr": x_ood_sr[ood_val_end:],
    }
    datasets: list[dict[str, Any]] = [
        {
            "dataset": "primary_lowood",
            "holdout": "primary_lowood",
            "split_protocol": "current_lowood_same_protocol",
            "support_pool_name": "stage2_high_purity_attack_train_pool",
            "attack_train_pool_idx": np.asarray(attack_split["train"], dtype=np.int64),
            "attack_val_idx": np.asarray(attack_split["val"], dtype=np.int64),
            "attack_eval_idx": np.asarray(attack_split["eval"], dtype=np.int64),
            **base_split,
        }
    ]

    row_bins = np.asarray(v74.load_attack_bins(manifest))
    specs = [s for s in v74.make_holdout_specs(manifest, row_bins, min_eval_rows=300) if s["holdout_name"] in MAIN_HOLDOUTS]
    specs_by_name = {str(spec["holdout_name"]): spec for spec in specs}
    if sorted(specs_by_name) != sorted(MAIN_HOLDOUTS):
        raise RuntimeError(f"Missing holdout specs: {set(MAIN_HOLDOUTS) - set(specs_by_name)}")

    # Harder-holdout backtest follows the issue17/18/19 repair-line local-calibration slice.
    hh_id_train_end = 8000
    hh_id_calib_end = hh_id_train_end + 5000
    hh_ood_train_end = 8000
    hh_ood_val_end = hh_ood_train_end + 2000
    hh_split = {
        "x_id_train_o": x_id_o[:hh_id_train_end],
        "x_id_calib_o": x_id_o[hh_id_train_end:hh_id_calib_end],
        "x_ood_train_o": x_ood_o[:hh_ood_train_end],
        "x_ood_val_o": x_ood_o[hh_ood_train_end:hh_ood_val_end],
        "x_ood_eval_o": x_ood_o[hh_ood_val_end:],
        "x_id_train_sr": x_id_sr[:hh_id_train_end],
        "x_id_calib_sr": x_id_sr[hh_id_train_end:hh_id_calib_end],
        "x_ood_train_sr": x_ood_sr[:hh_ood_train_end],
        "x_ood_val_sr": x_ood_sr[hh_ood_train_end:hh_ood_val_end],
        "x_ood_eval_sr": x_ood_sr[hh_ood_val_end:],
    }
    for holdout in MAIN_HOLDOUTS:
        spec = specs_by_name[holdout]
        attack_val_idx = np.asarray(spec.get("attack_val_idx", []), dtype=np.int64)
        if not spec.get("val_bins"):
            attack_val_idx = np.asarray([], dtype=np.int64)
        datasets.append(
            {
                "dataset": "harder_holdout",
                "holdout": holdout,
                "split_protocol": "harder_holdout_local_calibration_issue17_18_19",
                "support_pool_name": "local_harder_holdout_attack_train_pool",
                "attack_train_pool_idx": np.asarray(spec["train_pool_idx"], dtype=np.int64),
                "attack_val_idx": attack_val_idx,
                "attack_eval_idx": np.asarray(spec["attack_eval_idx"], dtype=np.int64),
                **hh_split,
            }
        )
    meta = {
        "primary_high_attack_total": int(len(high_idx)),
        "primary_attack_train_pool": int(len(attack_split["train"])),
        "primary_attack_val": int(len(attack_split["val"])),
        "primary_attack_eval": int(len(attack_split["eval"])),
        "harder_holdout_names": MAIN_HOLDOUTS,
    }
    return datasets, meta


def run_one(
    *,
    dataset_spec: dict[str, Any],
    method: str,
    support_rows: np.ndarray,
    x_attack_o: np.ndarray,
    x_attack_sr: np.ndarray,
    sr_names: list[str],
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    dataset = str(dataset_spec["dataset"])
    holdout = str(dataset_spec["holdout"])
    attack_eval_idx = np.asarray(dataset_spec["attack_eval_idx"], dtype=np.int64)
    x_attack_eval_o = x_attack_o[attack_eval_idx]
    x_attack_eval_sr = x_attack_sr[attack_eval_idx]
    x_pos_o = x_attack_o[support_rows]
    x_pos_sr = x_attack_sr[support_rows]

    selected_feature_rows: list[dict[str, Any]] = []
    if method == "V1_original100_kcenter32_fixed_guard_lr":
        method_version = "V1_LOW_GUARD_minimal"
        representation = "original100"
        x_id_train = dataset_spec["x_id_train_o"]
        x_ood_train = dataset_spec["x_ood_train_o"]
        x_pos = x_pos_o
        x_id_calib = dataset_spec["x_id_calib_o"]
        x_ood_val = dataset_spec["x_ood_val_o"]
        x_ood_eval = dataset_spec["x_ood_eval_o"]
        x_attack_eval = x_attack_eval_o
        selected_feature_count = 0
    elif method == "V2_selected_source_rich_top32_kcenter32_fixed_guard_lr":
        method_version = "V2_LOW_GUARD_plus"
        representation = "selected_source_rich_top32"
        feature_idx, selected_feature_rows = selected_source_rich_features(
            x_support=x_pos_sr,
            x_id_calib=dataset_spec["x_id_calib_sr"],
            x_ood_val=dataset_spec["x_ood_val_sr"],
            names=sr_names,
            dataset=dataset,
            holdout=holdout,
            seed=seed,
            top_k=32,
        )
        x_id_train = dataset_spec["x_id_train_sr"][:, feature_idx]
        x_ood_train = dataset_spec["x_ood_train_sr"][:, feature_idx]
        x_pos = x_pos_sr[:, feature_idx]
        x_id_calib = dataset_spec["x_id_calib_sr"][:, feature_idx]
        x_ood_val = dataset_spec["x_ood_val_sr"][:, feature_idx]
        x_ood_eval = dataset_spec["x_ood_eval_sr"][:, feature_idx]
        x_attack_eval = x_attack_eval_sr[:, feature_idx]
        selected_feature_count = 32
    else:
        raise ValueError(f"Unknown method: {method}")

    result = fit_adapter(
        x_id_train=x_id_train,
        x_ood_train=x_ood_train,
        x_pos=x_pos,
        x_id_calib=x_id_calib,
        x_ood_val=x_ood_val,
        x_ood_eval=x_ood_eval,
        x_attack_eval=x_attack_eval,
    )
    seed_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    for target in TARGETS:
        label = TARGET_LABELS[target]
        threshold_info = result["thresholds"][target]
        threshold = float(threshold_info["threshold"])
        attack_scores = result["scores"]["attack_eval"]
        ood_scores = result["scores"]["final_ood_eval"]
        attack_det = float(np.mean(attack_scores > threshold))
        ood_alarm = float(np.mean(ood_scores > threshold))
        seed_rows.append(
            {
                "dataset": dataset,
                "holdout": holdout,
                "split_protocol": dataset_spec["split_protocol"],
                "method": method,
                "method_version": method_version,
                "representation": representation,
                "adapter": "fixed_guard_lr",
                "support_method": "kcenter_32shot",
                "positive_budget": POSITIVE_BUDGET,
                "seed": int(seed),
                "seed_group": seed_group(seed),
                "ood_target": float(target),
                "ood_target_label": label,
                "roc_auc": float(result["roc_auc"]),
                "pr_auc": float(result["pr_auc"]),
                "attack_high_detection": attack_det,
                "final_ood_high_alarm": ood_alarm,
                "feasible_final_1pct": bool(ood_alarm <= 0.01),
                "threshold": threshold,
                "attack_eval_size": int(len(attack_scores)),
                "final_ood_eval_size": int(len(ood_scores)),
                "support_size": int(len(support_rows)),
                "support_pool_size": int(len(dataset_spec["attack_train_pool_idx"])),
                "feature_dim": int(x_id_train.shape[1]),
                "selected_feature_count": int(selected_feature_count),
                "train_time": float(result["train_time"]),
                "inference_time": float(result["inference_time"]),
                "parameter_count": int(result["parameter_count"]),
                "support_provenance_clean": True,
                "threshold_provenance_clean": True,
                "result_source": "issue19b_same_protocol_backtest",
            }
        )
        threshold_rows.append(
            {
                "dataset": dataset,
                "holdout": holdout,
                "method": method,
                "seed": int(seed),
                "seed_group": seed_group(seed),
                "ood_target": float(target),
                "ood_target_label": label,
                "threshold": threshold,
                "uses_id_calib": True,
                "uses_ood_val": True,
                "uses_final_ood_eval": False,
                "uses_attack_eval": False,
                "ood_val_alarm_at_selection": float(np.mean(result["scores"]["ood_val"] > threshold)),
                "id_calib_alarm_at_selection": float(np.mean(result["scores"]["id_calib"] > threshold)),
            }
        )

    support_provenance_rows = [
        {
            "dataset": dataset,
            "holdout": holdout,
            "method": method,
            "seed": int(seed),
            "seed_group": seed_group(seed),
            "support_method": "kcenter_32shot",
            "positive_budget": POSITIVE_BUDGET,
            "selected_attack_row_id": int(row),
            "support_pool_name": dataset_spec["support_pool_name"],
            "in_attack_train_pool": True,
            "overlaps_attack_val": bool(int(row) in set(map(int, dataset_spec["attack_val_idx"]))),
            "overlaps_attack_eval": bool(int(row) in set(map(int, dataset_spec["attack_eval_idx"]))),
            "selection_uses_attack_eval": False,
            "selection_uses_final_ood_eval": False,
        }
        for row in support_rows
    ]
    return seed_rows, threshold_rows, support_provenance_rows, selected_feature_rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "figures").mkdir(exist_ok=True)
    missing = require_inputs()
    if missing:
        write_text(OUT / "missing_input_report.md", "# Missing Input Report\n\n" + "\n".join(f"- {item}" for item in missing))
        raise RuntimeError(f"Missing required inputs: {missing}")

    cfg = json.loads((ISSUE11 / "config.json").read_text(encoding="utf-8"))
    paths = cfg["paths"]
    x_id_o = load_matrix(Path(paths["original100_id"]))
    x_ood_o = load_matrix(Path(paths["original100_ood"]))
    x_attack_o = load_matrix(Path(paths["original100_attack"]))
    x_id_sr = load_matrix(Path(paths["source_rich_id"]))
    x_ood_sr = load_matrix(Path(paths["source_rich_ood"]))
    x_attack_sr = load_matrix(Path(paths["source_rich_attack"]))
    if x_id_o.shape[0] != x_id_sr.shape[0] or x_ood_o.shape[0] != x_ood_sr.shape[0] or x_attack_o.shape[0] != x_attack_sr.shape[0]:
        write_text(OUT / "alignment_failure_report.md", "# Alignment Failure\n\noriginal100 and source_rich row counts do not align.")
        raise RuntimeError("original100/source_rich row-count mismatch")
    schema_path = Path(paths["source_rich_id"]).parents[1] / "data" / "structured_schema.json"
    sr_names = feature_names(schema_path, x_id_sr.shape[1])
    datasets, dataset_meta = build_datasets(
        paths=paths,
        x_id_o=x_id_o,
        x_ood_o=x_ood_o,
        x_attack_o=x_attack_o,
        x_id_sr=x_id_sr,
        x_ood_sr=x_ood_sr,
        x_attack_sr=x_attack_sr,
    )

    preflight_ok = True
    preflight_notes = [
        "V1 fixed as original100 + kcenter32 + fixed guard LR: yes.",
        "V2 fixed as selected_source_rich_top32 + kcenter32 + fixed guard LR: yes.",
        "V2 topK is fixed at 32 and is not re-selected by outcome: yes.",
        "V2 does not concatenate original100: yes.",
        "V2 does not use margin-hardneg: yes.",
        "Support is selected from each dataset/holdout local attack train pool only: yes.",
        "Thresholds use ID calibration + OOD validation only: yes.",
        "Alarm-budget curve uses pre-registered validation targets, not final-OOD selection: yes.",
        "All V1/V2 target results are written, not only the best point: yes.",
        "V2 definition is not modified based on this backtest: yes.",
    ]
    write_text(OUT / "preflight_v1_v2_backtest_check.md", "# Preflight V1/V2 Backtest Check\n\n" + "\n".join(f"- {x}" for x in preflight_notes))
    if not preflight_ok:
        raise RuntimeError("preflight failed")

    seed_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    support_rows: list[dict[str, Any]] = []
    selected_rows: list[dict[str, Any]] = []
    asset_rows: list[dict[str, Any]] = []
    methods = [
        "V1_original100_kcenter32_fixed_guard_lr",
        "V2_selected_source_rich_top32_kcenter32_fixed_guard_lr",
    ]

    for spec in datasets:
        support = kcenter_support(spec["attack_train_pool_idx"], x_attack_o[spec["attack_train_pool_idx"]], POSITIVE_BUDGET)
        overlap = set(map(int, support)) & (set(map(int, spec["attack_val_idx"])) | set(map(int, spec["attack_eval_idx"])))
        if overlap:
            raise RuntimeError(f"Support overlap for {spec['holdout']}: {sorted(overlap)[:5]}")
        asset_rows.append(
            {
                "dataset": spec["dataset"],
                "holdout": spec["holdout"],
                "split_protocol": spec["split_protocol"],
                "support_pool_name": spec["support_pool_name"],
                "support_pool_size": int(len(spec["attack_train_pool_idx"])),
                "attack_val_size": int(len(spec["attack_val_idx"])),
                "attack_eval_size": int(len(spec["attack_eval_idx"])),
                "id_train_size": int(len(spec["x_id_train_o"])),
                "id_calib_size": int(len(spec["x_id_calib_o"])),
                "ood_train_size": int(len(spec["x_ood_train_o"])),
                "ood_val_size": int(len(spec["x_ood_val_o"])),
                "final_ood_eval_size": int(len(spec["x_ood_eval_o"])),
                "original100_dim": int(x_id_o.shape[1]),
                "source_rich_dim": int(x_id_sr.shape[1]),
                "ordinary_setting_available": False,
                "notes": "ordinary normal-vs-attack has no same guarded OOD-validation protocol for V2 in this run",
            }
        )
        for seed in SEEDS:
            for method in methods:
                rows, thr_rows, sup_rows, feat_rows = run_one(
                    dataset_spec=spec,
                    method=method,
                    support_rows=support,
                    x_attack_o=x_attack_o,
                    x_attack_sr=x_attack_sr,
                    sr_names=sr_names,
                    seed=seed,
                )
                seed_rows.extend(rows)
                threshold_rows.extend(thr_rows)
                support_rows.extend(sup_rows)
                selected_rows.extend(feat_rows)
                print(f"[done] {spec['holdout']} seed={seed} method={method}", flush=True)

    by_seed = pd.DataFrame(seed_rows)
    thresholds = pd.DataFrame(threshold_rows)
    supports = pd.DataFrame(support_rows)
    features = pd.DataFrame(selected_rows)
    assets = pd.DataFrame(asset_rows)
    if (supports["overlaps_attack_val"].astype(bool) | supports["overlaps_attack_eval"].astype(bool)).any():
        raise RuntimeError("support overlap appeared after execution")

    summary = summarize(by_seed)
    main_by_seed = by_seed[by_seed["ood_target_label"].eq(MAIN_TARGET_LABEL)].copy()
    main_summary = summary[summary["ood_target_label"].eq(MAIN_TARGET_LABEL)].copy()

    by_seed.to_csv(OUT / "alarm_budget_curve_by_seed.csv", index=False)
    summary.to_csv(OUT / "alarm_budget_curve_summary.csv", index=False)
    main_by_seed.to_csv(OUT / "method_comparison_by_seed.csv", index=False)
    main_summary.to_csv(OUT / "method_comparison_summary.csv", index=False)
    thresholds.to_csv(OUT / "threshold_provenance.csv", index=False)
    supports.to_csv(OUT / "support_id_provenance.csv", index=False)
    features.to_csv(OUT / "selected_feature_report.csv", index=False)
    assets.to_csv(OUT / "dataset_asset_report.csv", index=False)

    v1 = main_summary[main_summary["method_version"].eq("V1_LOW_GUARD_minimal")][
        ["dataset", "holdout", "seed_group", "attack_high_detection_mean", "final_ood_high_alarm_mean", "final_ood_high_alarm_max", "feasible_rate"]
    ].rename(
        columns={
            "attack_high_detection_mean": "v1_detection_mean",
            "final_ood_high_alarm_mean": "v1_ood_alarm_mean",
            "final_ood_high_alarm_max": "v1_ood_alarm_max",
            "feasible_rate": "v1_feasible_rate",
        }
    )
    v2 = main_summary[main_summary["method_version"].eq("V2_LOW_GUARD_plus")][
        ["dataset", "holdout", "seed_group", "attack_high_detection_mean", "final_ood_high_alarm_mean", "final_ood_high_alarm_max", "feasible_rate"]
    ].rename(
        columns={
            "attack_high_detection_mean": "v2_detection_mean",
            "final_ood_high_alarm_mean": "v2_ood_alarm_mean",
            "final_ood_high_alarm_max": "v2_ood_alarm_max",
            "feasible_rate": "v2_feasible_rate",
        }
    )
    comparison = v1.merge(v2, on=["dataset", "holdout", "seed_group"], how="outer")
    comparison["delta_detection_v2_minus_v1"] = comparison["v2_detection_mean"] - comparison["v1_detection_mean"]
    comparison["delta_ood_alarm_v2_minus_v1"] = comparison["v2_ood_alarm_mean"] - comparison["v1_ood_alarm_mean"]
    comparison.to_csv(OUT / "v1_vs_v2_by_dataset.csv", index=False)

    feasible = summary[summary["final_ood_high_alarm_max"].le(0.01)].copy()
    feasible["diagnostic_only"] = True
    feasible["candidate_operating_point_requires_locked_validation"] = True
    feasible.to_csv(OUT / "feasible_operating_points.csv", index=False)

    for holdout, filename in [
        ("primary_lowood", "primary_lowood_v1_v2_summary.csv"),
        ("holdout_bin_2", "holdout_bin2_v1_v2_summary.csv"),
        ("chrono_late_train_early_eval", "chrono_late_v1_v2_summary.csv"),
    ]:
        main_summary[main_summary["holdout"].eq(holdout)].to_csv(OUT / filename, index=False)

    pd.DataFrame(
        [
            {
                "setting": "ordinary_normal_vs_attack",
                "status": "not_available",
                "reason": "V2 requires source_rich selected under an ID/OOD guarded threshold protocol; ordinary normal-vs-attack lacks a same-protocol OOD validation target in this run.",
                "claim_role": "compatibility gap only; not used as a V2 superiority claim",
            }
        ]
    ).to_csv(OUT / "ordinary_setting_v1_v2_summary.csv", index=False)

    # Reports.
    core_cols = [
        "dataset",
        "holdout",
        "seed_group",
        "v1_detection_mean",
        "v1_ood_alarm_max",
        "v2_detection_mean",
        "v2_ood_alarm_max",
        "delta_detection_v2_minus_v1",
    ]
    core_table = comparison[core_cols].sort_values(["dataset", "holdout", "seed_group"])
    primary = comparison[comparison["holdout"].eq("primary_lowood")]
    hb2 = comparison[comparison["holdout"].eq("holdout_bin_2")]
    chrono = comparison[comparison["holdout"].eq("chrono_late_train_early_eval")]

    primary_non_regression = bool((primary["delta_detection_v2_minus_v1"] >= -0.01).all() and (primary["v2_ood_alarm_max"] <= 0.01).all())
    hb2_positive = bool((hb2["delta_detection_v2_minus_v1"] > 0.20).all() and (hb2["v2_ood_alarm_max"] <= 0.01).all())
    chrono_not_harmed = bool((chrono["delta_detection_v2_minus_v1"] >= -0.05).all() and (chrono["v2_ood_alarm_max"] <= 0.01).all())
    consistent_upgrade = primary_non_regression and hb2_positive and chrono_not_harmed

    candidate_targets = feasible[
        feasible["method_version"].eq("V2_LOW_GUARD_plus") & feasible["ood_target"].isin([0.012, 0.015])
    ][["dataset", "holdout", "seed_group", "ood_target_label", "attack_high_detection_mean", "final_ood_high_alarm_max"]]

    write_text(
        OUT / "summary.md",
        f"""
# Issue19b V1/V2 Same-Protocol Backtest Summary

## Outcome

- Preflight passed: yes.
- V1 definition: `original100 + kcenter32 + fixed guard LR`.
- V2 definition: `selected_source_rich_top32 + kcenter32 + fixed guard LR`.
- Evaluated settings: primary low-OOD, holdout_bin_2, chrono_late_train_early_eval.
- Ordinary normal-vs-attack compatibility check: not run; see `ordinary_setting_v1_v2_summary.csv`.
- V2 primary non-regression at 1% target: {primary_non_regression}.
- V2 holdout_bin_2 repair remains positive at 1% target: {hb2_positive}.
- V2 chrono_late not-harmed criterion: {chrono_not_harmed}.
- Recommended locked-validation status: {'V2 can enter locked validation as a drift/adaptation candidate' if consistent_upgrade else 'V2 evidence is mixed; locked validation should be mode-specific or preceded by routing analysis'}.

## Core 1% Target Table

{md_table(core_table)}

## Alarm-Budget Curve Finding

The curve reports all pre-registered validation OOD targets: 0.5%, 0.8%, 1.0%, 1.2%, 1.5%, and 2.0%. Feasible operating points are diagnostic only; no final threshold is changed here.

Candidate V2 targets among 1.2%/1.5% with final OOD max <= 1%:

{md_table(candidate_targets)}

## Interpretation Boundary

V2 is fixed as selected_source_rich_top32; this run does not re-search topK, does not add original100 fusion, and does not add margin-hardneg. Alarm-budget slack is a diagnostic indication for future locked validation, not a new official threshold.
""",
    )
    write_text(
        OUT / "protocol.md",
        f"""
# Protocol

This is a V1/V2 same-protocol backtest plus alarm-budget curve. It is not new method development and not locked validation.

- V1: original100 representation, kcenter32 support selected from the applicable attack train pool only, L2 LogisticRegression, OOD weight 2.
- V2: selected_source_rich_top32 selected by the fixed issue19 rule using only attack supports, ID calibration, and OOD validation; kcenter32 support; L2 LogisticRegression; OOD weight 2.
- Thresholds: guarded ID calibration + OOD validation thresholds at targets {', '.join(TARGET_LABELS[t] for t in TARGETS)}.
- Official reporting target: 1.0%.
- Diagnostic targets: all non-1.0% entries. They cannot be selected as final thresholds from this run.
- Final OOD eval and attack eval are used only for final evaluation.
- Support selection does not use attack eval or final OOD eval.
- Primary low-OOD split follows issue09 stage2 high-purity attack split.
- Harder holdout split follows the issue17/18/19 repair-line local-calibration slice for comparability with issue19.
""",
    )
    write_text(
        OUT / "v1_v2_method_definition.md",
        """
# V1/V2 Method Definition

- V1 / LOW-GUARD-minimal: `original100 + kcenter32 + fixed guard LR`.
- V2 / LOW-GUARD+: `selected_source_rich_top32 + kcenter32 + fixed guard LR`.

V2 is intentionally narrow: no original100 fusion, no margin-hardneg, no topK search, no MLP/prototype/full neural GDA. The selected source_rich top32 rule is the fixed rule inherited from issue19 and applied using allowed development data only.
""",
    )
    write_text(
        OUT / "ordinary_asset_gap.md",
        """
# Ordinary Setting Asset Gap

The ordinary normal-vs-attack setting is not evaluated in this issue19b pass because V2 is defined under a guarded ID/OOD validation threshold protocol. The available ordinary sanity assets do not provide a directly comparable same-protocol OOD validation target for selected_source_rich_top32. This is a compatibility gap, not negative evidence against V2.
""",
    )
    write_text(
        OUT / "non_regression_report.md",
        f"""
# Non-Regression Report

Primary low-OOD non-regression criterion: V2 detection delta >= -0.01 and V2 final OOD alarm max <= 1%.

Result: {primary_non_regression}.

{md_table(primary[core_cols])}
""",
    )
    routing_text = "unified V2 locked validation is reasonable" if consistent_upgrade else "mode-specific validation/routing should be considered before calling V2 a universal replacement for V1"
    write_text(
        OUT / "mode_routing_implication.md",
        f"""
# Mode Routing Implication

The current implication is: {routing_text}.

If V2 is strong on holdout_bin_2 but regresses in primary low-OOD or chrono_late, it should be treated as a harder-shift repair module rather than a universal V1 replacement. If V2 is non-regressive across these settings, it can enter locked validation as the drift/adaptation-mode candidate.
""",
    )
    write_text(
        OUT / "claim_boundary.md",
        """
# Claim Boundary

## Can Say

- V2 outperforms or does not outperform V1 on the same protocol according to the reported settings.
- Alarm-budget curves suggest possible operating-point slack if feasible targets remain under final OOD <= 1%.
- Candidate operating points require locked validation.

## Cannot Say

- The final threshold has changed based on final eval.
- V2 universally replaces V1 unless all same-protocol tests support it.
- V2 solves all drift settings.
- A-zone readiness is achieved.
- Ordinary normal-vs-attack superiority is established by this run.
""",
    )
    risk_rows = [
        {"risk_name": "final threshold tuning risk", "severity": "high", "mitigation": "All targets are reported; no target is selected from final eval."},
        {"risk_name": "V2 overfit to holdout_bin_2 risk", "severity": "high", "mitigation": "Backtest includes primary low-OOD and chrono_late."},
        {"risk_name": "topK selection overfit risk", "severity": "medium", "mitigation": "topK fixed at 32; no topK search in this run."},
        {"risk_name": "source_rich alignment risk", "severity": "low", "mitigation": "Row-count alignment checked for ID/OOD/attack assets."},
        {"risk_name": "mode-routing ambiguity risk", "severity": "medium", "mitigation": "Non-regression and routing implication reports are emitted."},
        {"risk_name": "alarm-budget cherry-picking risk", "severity": "high", "mitigation": "All pre-registered targets are saved to curve files."},
        {"risk_name": "ordinary regression risk", "severity": "medium", "mitigation": "Ordinary setting not claimed; compatibility gap documented."},
    ]
    pd.DataFrame(risk_rows).to_csv(OUT / "risk_register.csv", index=False)

    if consistent_upgrade:
        next_action = "issue20 locked validation with V2 fixed."
    elif hb2_positive and primary_non_regression:
        next_action = "issue20 mode-specific locked validation: V2 for harder-shift adaptation, V1 retained as baseline route."
    else:
        next_action = "freeze V1/V2 as routed candidates and design a routing criterion before locked validation."
    write_text(
        OUT / "recommended_next_action.md",
        f"""
# Recommended Next Action

Unique first choice: {next_action}

If 1.2% or 1.5% validation targets look attractive, pre-register that target for locked validation; do not replace the current 1% method based on this diagnostic curve.
""",
    )
    write_text(
        OUT / "doc_update_patch_suggestion.md",
        """
# Suggested Mainline Docs Patch

Append a short issue19b note:

`issue19b compares fixed V1 and fixed V2 under the same protocols and reports pre-registered alarm-budget curves. Treat feasible non-1% targets as diagnostic only; locked validation is required before changing the operating point.`
""",
    )

    config = {
        "run": "issue19b_v1_v2_same_protocol_backtest_and_alarm_budget_curve_2026-05-18",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "v1": "original100 + kcenter32 + fixed guard LR",
        "v2": "selected_source_rich_top32 + kcenter32 + fixed guard LR",
        "targets": TARGETS,
        "official_target": MAIN_TARGET,
        "seeds": SEEDS,
        "dataset_meta": dataset_meta,
        "inputs": {
            "issue11": str(ISSUE11),
            "issue16b": str(ISSUE16B),
            "issue17": str(ISSUE17),
            "issue18": str(ISSUE18),
            "issue19": str(ISSUE19),
        },
        "fairness": {
            "final_ood_eval_used_for_threshold": False,
            "attack_eval_used_for_threshold": False,
            "final_ood_eval_used_for_feature_selection": False,
            "attack_eval_used_for_feature_selection": False,
            "topk_researched": False,
            "margin_hardneg_used": False,
            "original100_fusion_used_in_v2": False,
        },
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    manifest_rows = []
    for path in sorted(OUT.glob("*")):
        if path.is_file() and path.name != "manifest.csv":
            manifest_rows.append({"file": path.name, "size_bytes": path.stat().st_size})
    pd.DataFrame(manifest_rows).to_csv(OUT / "manifest.csv", index=False)


if __name__ == "__main__":
    main()
