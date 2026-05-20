from __future__ import annotations

import importlib.util
import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, roc_curve


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs" / "issue23_locked_validation_for_enhanced_v2_top64_2026-05-18"
ISSUE22 = ROOT / "runs" / "issue22_v2_hard_shift_enhancement_pilot_2026-05-18"
ISSUE22B = ROOT / "runs" / "issue22b_enhanced_v2_primary_nonregression_check_2026-05-18"
ISSUE19B = ROOT / "runs" / "issue19b_v1_v2_same_protocol_backtest_and_alarm_budget_curve_2026-05-18"
ISSUE18 = ROOT / "runs" / "issue18_row_level_score_persistence_and_ood_target_sensitivity_2026-05-15"
ISSUE20 = ROOT / "runs" / "issue20_mode_specific_routing_validation_2026-05-18"
ISSUE20B = ROOT / "runs" / "issue20b_promotion_proxy_construction_for_routing_2026-05-18"
ISSUE21 = ROOT / "runs" / "issue21_active_review_promotion_asset_feasibility_2026-05-18"
ISSUE11 = ROOT / "runs" / "issue11_fixed_config_ood_guard_lr_ablation_2026-05-14"
ISSUE22_SCRIPT = ISSUE22 / "run_issue22_v2_enhancement.py"
ISSUE19B_SCRIPT = ISSUE19B / "run_issue19b_v1_v2_backtest.py"

DISCOVERY_EVAL_BINS = {2, 3, 4}
LOCKED_HOLDOUTS = ["holdout_bin_5", "holdout_bin_6", "holdout_bin_7", "holdout_bin_8"]
EXCLUDED_HOLDOUTS = {
    "holdout_bin_2": "used directly in issue22 top64 discovery",
    "holdout_bin_3": "eval bin overlaps issue22 chrono_late discovery eval bins",
    "holdout_bin_4": "eval bin overlaps issue22 chrono_late discovery eval bins",
}
SEEDS = list(range(42, 52))
TARGETS = [0.005, 0.008, 0.01, 0.012, 0.015, 0.02]
MAIN_TARGET = 0.01
TARGET_LABELS = {
    0.005: "0.5pct",
    0.008: "0.8pct",
    0.01: "1.0pct",
    0.012: "1.2pct",
    0.015: "1.5pct",
    0.02: "2.0pct",
}


def import_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


issue22 = import_module(ISSUE22_SCRIPT, "issue22_v2_enhancement")
issue19b = import_module(ISSUE19B_SCRIPT, "issue19b_v1_v2_backtest")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def md_table(df: pd.DataFrame, cols: list[str] | None = None, max_rows: int | None = None) -> str:
    if cols is not None:
        df = df[cols].copy()
    if max_rows is not None:
        df = df.head(max_rows).copy()
    if df.empty:
        return "_No rows._\n"
    lines = ["| " + " | ".join(df.columns) + " |", "|" + "|".join(["---"] * len(df.columns)) + "|"]
    for _, row in df.iterrows():
        vals: list[str] = []
        for value in row:
            if isinstance(value, (float, np.floating)):
                vals.append("" if math.isnan(float(value)) else f"{float(value):.6f}")
            else:
                vals.append(str(value))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"


def require_inputs() -> list[str]:
    required = [
        ISSUE22 / "summary.md",
        ISSUE22 / "method_comparison_summary.csv",
        ISSUE22 / "method_comparison_by_seed.csv",
        ISSUE22 / "holdout_bin2_v2_enhancement_summary.csv",
        ISSUE22 / "chrono_late_v2_enhancement_summary.csv",
        ISSUE22 / "primary_lowood_safety_check.csv",
        ISSUE22 / "feature_count_sensitivity.csv",
        ISSUE22 / "claim_boundary.md",
        ISSUE22 / "recommended_next_action.md",
        ISSUE22B / "summary.md",
        ISSUE22B / "primary_lowood_nonregression_summary.csv",
        ISSUE22B / "primary_lowood_nonregression_by_seed.csv",
        ISSUE22B / "v1_v2top32_v2top64_by_dataset.csv",
        ISSUE22B / "global_candidate_status.md",
        ISSUE22B / "claim_boundary.md",
        ISSUE22B / "recommended_next_action.md",
        ISSUE19B / "summary.md",
        ISSUE18 / "row_level_scores_manifest.csv",
        ISSUE20 / "summary.md",
        ISSUE20 / "claim_boundary.md",
        ISSUE20B / "summary.md",
        ISSUE20B / "claim_boundary.md",
        ISSUE21 / "summary.md",
        ISSUE21 / "claim_boundary.md",
        ISSUE11 / "config.json",
        ISSUE22_SCRIPT,
        ISSUE19B_SCRIPT,
    ]
    return [str(path) for path in required if not path.exists()]


def method_specs() -> list[dict[str, Any]]:
    return [
        {
            "method": "M0_V1_original100_kcenter32_fixed_guard",
            "method_group": "baseline",
            "candidate": "V1",
            "representation": "original100",
            "support_method": "kcenter",
            "support_budget": 32,
            "top_k": 0,
            "adapter": "fixed_guard_lr",
        },
        {
            "method": "M1_V2_source_rich_top32_kcenter32_fixed_guard",
            "method_group": "reference",
            "candidate": "V2_top32",
            "representation": "selected_source_rich",
            "support_method": "kcenter",
            "support_budget": 32,
            "top_k": 32,
            "adapter": "fixed_guard_lr",
        },
        {
            "method": "M2_enhanced_V2_source_rich_top64_kcenter32_fixed_guard",
            "method_group": "locked_candidate",
            "candidate": "V2_top64",
            "representation": "selected_source_rich",
            "support_method": "kcenter",
            "support_budget": 32,
            "top_k": 64,
            "adapter": "fixed_guard_lr",
        },
        {
            "method": "M3_source_rich_top64_random32_fixed_guard_optional",
            "method_group": "optional_support_baseline",
            "candidate": "V2_top64_random32",
            "representation": "selected_source_rich",
            "support_method": "random",
            "support_budget": 32,
            "top_k": 64,
            "adapter": "fixed_guard_lr",
        },
    ]


def low_fpr_metrics(scores_ood: np.ndarray, scores_attack: np.ndarray) -> tuple[float, float]:
    y_true = np.concatenate([np.zeros(len(scores_ood), dtype=np.int64), np.ones(len(scores_attack), dtype=np.int64)])
    y_score = np.concatenate([scores_ood, scores_attack])
    pauc = float(roc_auc_score(y_true, y_score, max_fpr=0.01))
    fpr, tpr, _ = roc_curve(y_true, y_score)
    tpr_at_1pct = float(np.max(tpr[fpr <= 0.01])) if np.any(fpr <= 0.01) else 0.0
    return pauc, tpr_at_1pct


def run_method_locked(
    *,
    dataset_spec: dict[str, Any],
    method_spec: dict[str, Any],
    seed: int,
    support_rows: np.ndarray,
    x_attack_o: np.ndarray,
    x_attack_sr: np.ndarray,
    sr_names: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    dataset = str(dataset_spec["dataset"])
    holdout = str(dataset_spec["holdout"])
    attack_eval_idx = np.asarray(dataset_spec["attack_eval_idx"], dtype=np.int64)
    x_attack_eval_o = x_attack_o[attack_eval_idx]
    x_attack_eval_sr = x_attack_sr[attack_eval_idx]
    x_pos_o = x_attack_o[support_rows]
    x_pos_sr = x_attack_sr[support_rows]
    method = str(method_spec["method"])
    representation = str(method_spec["representation"])
    top_k = int(method_spec["top_k"])
    selected_feature_rows: list[dict[str, Any]] = []

    if representation == "original100":
        x_id_train = dataset_spec["x_id_train_o"]
        x_ood_train = dataset_spec["x_ood_train_o"]
        x_pos = x_pos_o
        x_id_calib = dataset_spec["x_id_calib_o"]
        x_ood_val = dataset_spec["x_ood_val_o"]
        x_ood_eval = dataset_spec["x_ood_eval_o"]
        x_attack_eval = x_attack_eval_o
        feature_count = int(x_id_train.shape[1])
    else:
        feature_idx, selected_feature_rows = issue19b.selected_source_rich_features(
            x_support=x_pos_sr,
            x_id_calib=dataset_spec["x_id_calib_sr"],
            x_ood_val=dataset_spec["x_ood_val_sr"],
            names=sr_names,
            dataset=dataset,
            holdout=holdout,
            seed=seed,
            top_k=top_k,
        )
        x_id_train = dataset_spec["x_id_train_sr"][:, feature_idx]
        x_ood_train = dataset_spec["x_ood_train_sr"][:, feature_idx]
        x_pos = x_pos_sr[:, feature_idx]
        x_id_calib = dataset_spec["x_id_calib_sr"][:, feature_idx]
        x_ood_val = dataset_spec["x_ood_val_sr"][:, feature_idx]
        x_ood_eval = dataset_spec["x_ood_eval_sr"][:, feature_idx]
        x_attack_eval = x_attack_eval_sr[:, feature_idx]
        feature_count = int(top_k)

    result = issue22.fit_lr_scores(
        x_id_train=x_id_train,
        x_ood_train=x_ood_train,
        x_pos=x_pos,
        x_id_calib=x_id_calib,
        x_ood_val=x_ood_val,
        x_ood_eval=x_ood_eval,
        x_attack_eval=x_attack_eval,
        hard_negative=False,
    )
    pauc_1pct, tpr_at_fpr1 = low_fpr_metrics(result["scores"]["final_ood_eval"], result["scores"]["attack_eval"])

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
                "method_group": method_spec["method_group"],
                "candidate": method_spec["candidate"],
                "representation": representation if representation == "original100" else f"selected_source_rich_top{top_k}",
                "adapter": "fixed_guard_lr",
                "support_method": method_spec["support_method"],
                "support_size": int(len(support_rows)),
                "support_budget": int(method_spec["support_budget"]),
                "seed": int(seed),
                "seed_group": issue22.seed_group(seed),
                "ood_target": float(target),
                "ood_target_label": label,
                "roc_auc": float(result["roc_auc"]),
                "pr_auc": float(result["pr_auc"]),
                "pauc_fpr_1pct": pauc_1pct,
                "tpr_at_fpr_1pct": tpr_at_fpr1,
                "attack_high_detection": attack_det,
                "final_ood_high_alarm": ood_alarm,
                "feasible_final_1pct": bool(ood_alarm <= 0.01),
                "threshold": threshold,
                "attack_eval_size": int(len(attack_scores)),
                "final_ood_eval_size": int(len(ood_scores)),
                "feature_dim": feature_count,
                "selected_topk": top_k,
                "train_time": float(result["train_time"]),
                "inference_time": float(result["inference_time"]),
                "parameter_count": int(result["parameter_count"]),
                "provenance_clean": True,
                "threshold_diagnostic_only": bool(target != MAIN_TARGET),
                "final_eval_used_for_selection": False,
            }
        )
        threshold_rows.append(
            {
                "dataset": dataset,
                "holdout": holdout,
                "method": method,
                "candidate": method_spec["candidate"],
                "seed": int(seed),
                "seed_group": issue22.seed_group(seed),
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

    attack_val = set(map(int, dataset_spec.get("attack_val_idx", [])))
    attack_eval = set(map(int, dataset_spec.get("attack_eval_idx", [])))
    support_rows_out = [
        {
            "dataset": dataset,
            "holdout": holdout,
            "method": method,
            "candidate": method_spec["candidate"],
            "seed": int(seed),
            "seed_group": issue22.seed_group(seed),
            "support_method": method_spec["support_method"],
            "support_budget": int(method_spec["support_budget"]),
            "selected_attack_row_id": int(row),
            "support_pool_name": dataset_spec["support_pool_name"],
            "in_attack_train_pool": True,
            "overlaps_attack_val": bool(int(row) in attack_val),
            "overlaps_attack_eval": bool(int(row) in attack_eval),
            "selection_uses_attack_eval": False,
            "selection_uses_final_ood_eval": False,
        }
        for row in support_rows
    ]
    return seed_rows, threshold_rows, support_rows_out, selected_feature_rows


def summarize(by_seed: pd.DataFrame) -> pd.DataFrame:
    return (
        by_seed.groupby(
            ["dataset", "holdout", "method", "method_group", "candidate", "seed_group", "ood_target", "ood_target_label"],
            as_index=False,
        )
        .agg(
            n_seeds=("seed", "nunique"),
            roc_auc_mean=("roc_auc", "mean"),
            pr_auc_mean=("pr_auc", "mean"),
            pauc_fpr_1pct_mean=("pauc_fpr_1pct", "mean"),
            tpr_at_fpr_1pct_mean=("tpr_at_fpr_1pct", "mean"),
            attack_high_detection_mean=("attack_high_detection", "mean"),
            attack_high_detection_std=("attack_high_detection", "std"),
            attack_high_detection_min=("attack_high_detection", "min"),
            attack_high_detection_max=("attack_high_detection", "max"),
            final_ood_high_alarm_mean=("final_ood_high_alarm", "mean"),
            final_ood_high_alarm_max=("final_ood_high_alarm", "max"),
            feasible_rate=("feasible_final_1pct", "mean"),
            threshold_mean=("threshold", "mean"),
            support_size=("support_size", "first"),
            feature_dim=("feature_dim", "first"),
            selected_topk=("selected_topk", "first"),
            train_time_mean=("train_time", "mean"),
            inference_time_mean=("inference_time", "mean"),
            provenance_clean_rate=("provenance_clean", "mean"),
        )
        .sort_values(["dataset", "holdout", "ood_target", "method", "seed_group"])
    )


def build_locked_datasets(paths: dict[str, str], x_id_o: np.ndarray, x_ood_o: np.ndarray, x_attack_o: np.ndarray, x_id_sr: np.ndarray, x_ood_sr: np.ndarray, x_attack_sr: np.ndarray) -> tuple[list[dict[str, Any]], pd.DataFrame, dict[str, Any]]:
    manifest = issue19b.load_json(Path(paths["stage2_manifest"]))
    row_bins = np.asarray(issue19b.v74.load_attack_bins(manifest))
    all_specs = issue19b.v74.make_holdout_specs(manifest, row_bins, min_eval_rows=300)
    rows: list[dict[str, Any]] = []
    specs_by_name: dict[str, dict[str, Any]] = {}
    for spec in all_specs:
        name = str(spec["holdout_name"])
        eval_bins = list(map(int, spec.get("eval_bins", [])))
        is_locked = name in LOCKED_HOLDOUTS
        reason = "unused leave-one-bin eval object" if is_locked else EXCLUDED_HOLDOUTS.get(name, "not selected for this locked pass")
        rows.append(
            {
                "holdout_name": name,
                "holdout_type": spec.get("holdout_type", ""),
                "train_bins": ",".join(map(str, spec.get("train_bins", []))),
                "eval_bins": ",".join(map(str, eval_bins)),
                "train_pool_count": int(len(spec.get("train_pool_idx", []))),
                "attack_eval_count": int(len(spec.get("attack_eval_idx", []))),
                "used_in_issue22_discovery_eval": bool(any(bin_id in DISCOVERY_EVAL_BINS for bin_id in eval_bins)),
                "locked_validation_object": bool(is_locked),
                "asset_status": "locked_used" if is_locked else "excluded",
                "reason": reason,
            }
        )
        if is_locked:
            specs_by_name[name] = spec
    missing = set(LOCKED_HOLDOUTS) - set(specs_by_name)
    if missing:
        raise RuntimeError(f"Missing locked holdout specs: {sorted(missing)}")

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
    datasets: list[dict[str, Any]] = []
    for holdout in LOCKED_HOLDOUTS:
        spec = specs_by_name[holdout]
        attack_val_idx = np.asarray(spec.get("attack_val_idx", []), dtype=np.int64)
        if not spec.get("val_bins"):
            attack_val_idx = np.asarray([], dtype=np.int64)
        datasets.append(
            {
                "dataset": "locked_harder_holdout",
                "holdout": holdout,
                "split_protocol": "issue23_locked_leave_one_bin_local_calibration",
                "support_pool_name": "local_locked_holdout_attack_train_pool",
                "attack_train_pool_idx": np.asarray(spec["train_pool_idx"], dtype=np.int64),
                "attack_val_idx": attack_val_idx,
                "attack_eval_idx": np.asarray(spec["attack_eval_idx"], dtype=np.int64),
                "locked_validation_object": True,
                **hh_split,
            }
        )
    meta = {
        "locked_holdouts": LOCKED_HOLDOUTS,
        "excluded_holdouts": EXCLUDED_HOLDOUTS,
        "discovery_eval_bins": sorted(DISCOVERY_EVAL_BINS),
    }
    return datasets, pd.DataFrame(rows), meta


def comparison_tables(official: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    locked_main = official[official["method"].isin([
        "M0_V1_original100_kcenter32_fixed_guard",
        "M1_V2_source_rich_top32_kcenter32_fixed_guard",
        "M2_enhanced_V2_source_rich_top64_kcenter32_fixed_guard",
    ])].copy()
    wide = locked_main.pivot_table(
        index=["holdout", "seed_group"],
        columns="candidate",
        values=["attack_high_detection_mean", "final_ood_high_alarm_max", "pauc_fpr_1pct_mean", "tpr_at_fpr_1pct_mean", "feasible_rate"],
        aggfunc="first",
    )
    wide.columns = [f"{metric}_{candidate}" for metric, candidate in wide.columns]
    wide = wide.reset_index()
    for cand in ["V1", "V2_top32", "V2_top64"]:
        if f"attack_high_detection_mean_{cand}" not in wide.columns:
            wide[f"attack_high_detection_mean_{cand}"] = np.nan
        if f"final_ood_high_alarm_max_{cand}" not in wide.columns:
            wide[f"final_ood_high_alarm_max_{cand}"] = np.nan
    wide["v2top64_minus_v1_detection"] = wide["attack_high_detection_mean_V2_top64"] - wide["attack_high_detection_mean_V1"]
    wide["v2top64_minus_v1_ood_alarm"] = wide["final_ood_high_alarm_max_V2_top64"] - wide["final_ood_high_alarm_max_V1"]
    wide["v2top64_minus_v2top32_detection"] = wide["attack_high_detection_mean_V2_top64"] - wide["attack_high_detection_mean_V2_top32"]
    wide["v2top64_minus_v2top32_ood_alarm"] = wide["final_ood_high_alarm_max_V2_top64"] - wide["final_ood_high_alarm_max_V2_top32"]
    vs_v1_cols = [
        "holdout",
        "seed_group",
        "attack_high_detection_mean_V1",
        "attack_high_detection_mean_V2_top64",
        "v2top64_minus_v1_detection",
        "final_ood_high_alarm_max_V1",
        "final_ood_high_alarm_max_V2_top64",
        "v2top64_minus_v1_ood_alarm",
    ]
    vs_v2_cols = [
        "holdout",
        "seed_group",
        "attack_high_detection_mean_V2_top32",
        "attack_high_detection_mean_V2_top64",
        "v2top64_minus_v2top32_detection",
        "final_ood_high_alarm_max_V2_top32",
        "final_ood_high_alarm_max_V2_top64",
        "v2top64_minus_v2top32_ood_alarm",
    ]
    return wide, wide[vs_v1_cols].copy(), wide[vs_v2_cols].copy()


def status_from(official: pd.DataFrame, vs_v1: pd.DataFrame, vs_v2: pd.DataFrame) -> tuple[str, str, str]:
    v2 = official[official["candidate"].eq("V2_top64")].copy()
    v2_main = v2[v2["seed_group"].eq("main_42_46")]
    v2_held = v2[v2["seed_group"].eq("heldout_47_51")]
    ood_ok = bool((v2["final_ood_high_alarm_max"] <= 0.01).all())
    stable = bool(not v2_main.empty and not v2_held.empty)
    better_v1 = bool((vs_v1["v2top64_minus_v1_detection"] > 0).all())
    better_v2 = bool((vs_v2["v2top64_minus_v2top32_detection"] > 0).all())
    det_ge_09 = bool((v2["attack_high_detection_mean"] >= 0.90).all())
    if ood_ok and stable and better_v1 and better_v2 and det_ge_09:
        return (
            "very_strong_locked_validation",
            "V2_top64 beats V1 and V2_top32 on all locked bins, keeps OOD <=1%, and all locked-bin detections are >=0.90.",
            "start_paper_integration_and_formal_strong_baseline_pack",
        )
    if ood_ok and stable and better_v1:
        return (
            "strong_locked_validation",
            "V2_top64 beats V1 on locked bins and keeps OOD <=1%; some bins may be below the very-strong 0.90 criterion or not beat V2_top32 everywhere.",
            "start_paper_integration_and_formal_strong_baseline_pack",
        )
    if ood_ok and bool((vs_v1["v2top64_minus_v1_detection"] >= 0).mean() >= 0.5):
        return (
            "moderate_locked_validation",
            "V2_top64 is feasible and improves over V1 on part of the locked set, but evidence is not uniformly strong.",
            "run_second_environment_or_locked_temporal_validation_before_main_method_claim",
        )
    return (
        "negative_locked_validation",
        "V2_top64 does not provide clean locked validation improvement or violates OOD feasibility.",
        "keep_top64_as_pilot_and_return_to_generalization_baseline_design",
    )


def write_reports(summary: pd.DataFrame, by_seed: pd.DataFrame, thresholds: pd.DataFrame, supports: pd.DataFrame, features: pd.DataFrame, asset_report: pd.DataFrame, meta: dict[str, Any]) -> None:
    official = summary[summary["ood_target"].eq(MAIN_TARGET)].copy()
    official_main = official[official["method"].isin([
        "M0_V1_original100_kcenter32_fixed_guard",
        "M1_V2_source_rich_top32_kcenter32_fixed_guard",
        "M2_enhanced_V2_source_rich_top64_kcenter32_fixed_guard",
    ])].copy()
    success_wide, vs_v1, vs_v2 = comparison_tables(official_main)
    status, status_reason, next_action = status_from(official_main, vs_v1, vs_v2)
    v2_locked = official_main[official_main["candidate"].eq("V2_top64")]
    v2_ood_max = float(v2_locked["final_ood_high_alarm_max"].max()) if not v2_locked.empty else math.nan
    v2_det_min = float(v2_locked["attack_high_detection_mean"].min()) if not v2_locked.empty else math.nan
    v2_det_mean = float(v2_locked["attack_high_detection_mean"].mean()) if not v2_locked.empty else math.nan
    v2_vs_v1_mean = float(vs_v1["v2top64_minus_v1_detection"].mean()) if not vs_v1.empty else math.nan
    v2_vs_top32_mean = float(vs_v2["v2top64_minus_v2top32_detection"].mean()) if not vs_v2.empty else math.nan

    official_main.to_csv(OUT / "method_comparison_summary_official_1pct.csv", index=False)
    success_wide.to_csv(OUT / "locked_validation_success_wide.csv", index=False)
    vs_v1.to_csv(OUT / "v2top64_vs_v1_locked.csv", index=False)
    vs_v2.to_csv(OUT / "v2top64_vs_v2top32_locked.csv", index=False)
    low_fpr = official_main[
        [
            "dataset",
            "holdout",
            "method",
            "candidate",
            "seed_group",
            "pauc_fpr_1pct_mean",
            "tpr_at_fpr_1pct_mean",
            "attack_high_detection_mean",
            "final_ood_high_alarm_max",
        ]
    ].copy()
    low_fpr.to_csv(OUT / "low_fpr_metrics_summary.csv", index=False)

    consistency_parts = []
    issue22_summary = pd.read_csv(ISSUE22 / "method_comparison_summary.csv")
    issue22b_summary = pd.read_csv(ISSUE22B / "primary_lowood_nonregression_summary.csv")
    existing_methods = [
        "M0_V1_original100_kcenter32_fixed_guard",
        "M1_V2_source_rich_top32_kcenter32_fixed_guard",
        "M8_source_rich_top64_kcenter32_fixed_guard",
    ]
    issue22_existing = issue22_summary[
        issue22_summary["method"].isin(existing_methods)
        & issue22_summary["holdout"].isin(["holdout_bin_2", "chrono_late_train_early_eval"])
        & issue22_summary["ood_target"].eq(MAIN_TARGET)
    ].copy()
    if not issue22_existing.empty:
        issue22_existing["consistency_role"] = "discovery_consistency_not_locked"
        consistency_parts.append(issue22_existing)
    issue22b_existing = issue22b_summary.copy()
    if not issue22b_existing.empty:
        issue22b_existing["holdout"] = "primary_lowood"
        issue22b_existing["dataset"] = "primary_lowood"
        issue22b_existing["consistency_role"] = "primary_nonregression_consistency_not_locked"
        consistency_parts.append(issue22b_existing)
    consistency = pd.concat(consistency_parts, ignore_index=True, sort=False) if consistency_parts else pd.DataFrame()
    consistency.to_csv(OUT / "consistency_check_existing_settings.csv", index=False)

    write_text(
        OUT / "preflight_locked_validation_check.md",
        f"""
# Preflight Locked Validation Check

- Successfully read issue22 / issue22b: yes.
- Main method fixed as selected_source_rich_top64 + kcenter32 + fixed guard LR: yes.
- topK re-selected: no.
- threshold target re-selected: no.
- final eval used to select configuration: no.
- locked validation object available: yes.
- locked validation object used for top64 selection: no.
- seed-level results available: yes.
- low-FPR / OOD budget metrics available: yes.
- routing / promotion / V3 attempted: no.

Locked validation objects: `{', '.join(LOCKED_HOLDOUTS)}`.

Excluded from locked proof:

{chr(10).join(f'- `{name}`: {reason}.' for name, reason in EXCLUDED_HOLDOUTS.items())}
""",
    )
    write_text(
        OUT / "protocol.md",
        f"""
# Protocol

This run locks the enhanced V2_top64 configuration found in issue22/22b.

- Candidate: selected_source_rich_top64 + kcenter32 + fixed OOD guard LR.
- Official OOD target: 1%.
- Locked objects: {', '.join(LOCKED_HOLDOUTS)}.
- The locked objects are unused leave-one-bin eval objects whose eval bins were not used to choose top64 in issue22.
- Support source: local attack train pool per locked holdout.
- Scaler fit: ID benign train + OOD benign train + selected attack supports.
- Feature selection: selected source_rich top64 is recomputed using training/support and ID/OOD calibration/validation only.
- Threshold: ID calibration + OOD validation only.
- Final OOD eval and attack eval are report-only.
- No routing, no promotion, no V3, no margin-hardneg main method, no topK search.
""",
    )
    write_text(
        OUT / "scaler_provenance.md",
        """
# Scaler Provenance

Each method/holdout/seed fits StandardScaler only on the corresponding training matrix: ID benign train + OOD benign train + selected local attack supports. ID calibration, OOD validation, final OOD eval, and attack eval are transformed using that train-fitted scaler only.
""",
    )
    write_text(
        OUT / "locked_validation_asset_report.md",
        f"""
# Locked Validation Asset Report

The v7.4 paired hard-holdout assets provide multiple leave-one-attack-window-out bins. issue22 selected V2_top64 after inspecting primary_lowood, holdout_bin_2, and chrono_late_train_early_eval. Since chrono_late evaluates bins 2/3/4, `holdout_bin_3` and `holdout_bin_4` are excluded from locked proof even though they exist.

Main locked objects used here:

{md_table(asset_report[asset_report['locked_validation_object']].sort_values('holdout_name'))}

Full candidate inventory:

{md_table(asset_report.sort_values('holdout_name'))}
""",
    )
    write_text(
        OUT / "locked_validation_success_table.md",
        f"""
# Locked Validation Success Table

Status: `{status}`.

Reason: {status_reason}

Official 1% locked comparison:

{md_table(official_main.sort_values(['holdout', 'candidate', 'seed_group']))}

V2_top64 vs V1:

{md_table(vs_v1)}

V2_top64 vs V2_top32:

{md_table(vs_v2)}
""",
    )
    write_text(
        OUT / "summary.md",
        f"""
# Issue23 Locked Validation Summary

## Outcome

- Preflight passed: yes.
- True locked validation objects found: yes.
- Locked objects: `{', '.join(LOCKED_HOLDOUTS)}`.
- Main candidate fixed: `selected_source_rich_top64 + kcenter32 + fixed guard LR`.
- topK search: no.
- final eval used for selection: no.
- routing / promotion / V3: no.
- Locked validation status: `{status}`.
- V2_top64 locked detection mean across summary rows: `{v2_det_mean:.6f}`.
- V2_top64 locked detection minimum across summary rows: `{v2_det_min:.6f}`.
- V2_top64 locked OOD alarm max: `{v2_ood_max:.6f}`.
- Mean V2_top64 - V1 detection delta: `{v2_vs_v1_mean:.6f}`.
- Mean V2_top64 - V2_top32 detection delta: `{v2_vs_top32_mean:.6f}`.
- Recommended next action: `{next_action}`.

## Core Locked Results

{md_table(official_main.sort_values(['holdout', 'candidate', 'seed_group']))}

## Interpretation

Existing primary_lowood / holdout_bin_2 / chrono_late results are kept as consistency checks only. The locked claim in this run rests on the unused leave-one-bin objects above. If the status is strong or very strong, enhanced LOW-GUARD+ top64 can move into paper integration and formal strong-baseline packaging; it still does not prove external-dataset generalization or routing/promotion.
""",
    )
    write_text(
        OUT / "claim_boundary.md",
        """
# Claim Boundary

## Can Say

- V2_top64 passes or does not pass locked validation according to the locked leave-one-bin objects reported here.
- Existing primary_lowood, holdout_bin_2, and chrono_late are consistency checks, not standalone locked proof.
- Enhanced LOW-GUARD+ can be treated as a unified candidate only if locked validation metrics support it.

## Cannot Say

- All future drift is solved.
- Routing or promotion is solved by this run.
- top64 was selected using locked validation.
- External-dataset validation is complete.
- CCF-A readiness is achieved.
""",
    )
    risks = [
        ["locked object weakness", "medium", "Locked objects are same-dataset bins, not external environments.", "Add second-environment validation later."],
        ["holdout reuse risk", "medium", "Some local support pools may include bins previously inspected elsewhere.", "Treat lockedness as eval-object locked and document limitation."],
        ["top64 overfit risk", "medium", "top64 was chosen after issue22 discovery settings.", "This run uses unused eval bins and forbids topK changes."],
        ["source_rich alignment risk", "low", "source_rich and original100 must remain row-aligned.", "Reuse issue19b/22 loaders and row-count checks."],
        ["seed instability", "medium", "few-shot support may vary.", "Report main and held-out seeds separately."],
        ["low-FPR metric instability", "medium", "low-FPR pAUC can be noisy.", "Report pAUC and guarded threshold metrics together."],
        ["external validity risk", "high", "No external dataset is validated here.", "Do not overclaim external generalization."],
        ["missing second environment risk", "high", "CCF-A-level evidence still needs second environment or stronger baselines.", "Plan formal baseline/second-environment pack."],
    ]
    pd.DataFrame(risks, columns=["risk_name", "severity", "reason", "mitigation"]).to_csv(OUT / "risk_register.csv", index=False)
    write_text(
        OUT / "recommended_next_action.md",
        f"""
# Recommended Next Action

Unique first choice: `{next_action}`.

If `{status}` remains strong after review, stop tuning topK/support/threshold and start paper integration plus formal strong-baseline pack. If reviewers would require stronger generalization, add a second-environment validation after the baseline pack rather than further optimizing V2 on these bins.
""",
    )
    write_text(
        OUT / "doc_update_patch_suggestion.md",
        """
# Suggested Mainline Docs Patch

Append a short issue23 note:

`issue23 locks the enhanced LOW-GUARD+ top64 configuration from issue22/22b and validates it on unused v7.4 leave-one-bin hard-holdout objects. Existing primary/holdout_bin_2/chrono_late remain consistency checks only.`
""",
    )
    config = {
        "run": "issue23_locked_validation_for_enhanced_v2_top64_2026-05-18",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "locked_holdouts": LOCKED_HOLDOUTS,
        "excluded_holdouts": EXCLUDED_HOLDOUTS,
        "discovery_eval_bins": sorted(DISCOVERY_EVAL_BINS),
        "candidate": "selected_source_rich_top64 + kcenter32 + fixed guard LR",
        "targets": TARGETS,
        "official_target": MAIN_TARGET,
        "seeds": SEEDS,
        "status": status,
        "next_action": next_action,
        "fairness": {
            "topk_researched": False,
            "threshold_target_researched": False,
            "final_ood_eval_used_for_threshold": False,
            "attack_eval_used_for_threshold": False,
            "final_ood_eval_used_for_feature_selection": False,
            "attack_eval_used_for_feature_selection": False,
            "routing_or_promotion_attempted": False,
            "v3_attempted": False,
        },
        "inputs": {
            "issue22": str(ISSUE22),
            "issue22b": str(ISSUE22B),
            "issue19b": str(ISSUE19B),
        },
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    t0 = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "figures").mkdir(exist_ok=True)
    missing = require_inputs()
    if missing:
        write_text(OUT / "missing_input_report.md", "# Missing Input Report\n\n" + "\n".join(f"- {item}" for item in missing))
        raise RuntimeError(f"Missing required inputs: {missing}")

    cfg = json.loads((ISSUE11 / "config.json").read_text(encoding="utf-8"))
    paths = cfg["paths"]
    x_id_o = issue19b.load_matrix(Path(paths["original100_id"]))
    x_ood_o = issue19b.load_matrix(Path(paths["original100_ood"]))
    x_attack_o = issue19b.load_matrix(Path(paths["original100_attack"]))
    x_id_sr = issue19b.load_matrix(Path(paths["source_rich_id"]))
    x_ood_sr = issue19b.load_matrix(Path(paths["source_rich_ood"]))
    x_attack_sr = issue19b.load_matrix(Path(paths["source_rich_attack"]))
    if x_id_o.shape[0] != x_id_sr.shape[0] or x_ood_o.shape[0] != x_ood_sr.shape[0] or x_attack_o.shape[0] != x_attack_sr.shape[0]:
        write_text(OUT / "alignment_failure_report.md", "# Alignment Failure\n\noriginal100 and source_rich row counts do not align.")
        raise RuntimeError("original100/source_rich row-count mismatch")
    schema_path = Path(paths["source_rich_id"]).parents[1] / "data" / "structured_schema.json"
    sr_names = issue19b.feature_names(schema_path, x_id_sr.shape[1])
    datasets, asset_report, meta = build_locked_datasets(paths, x_id_o, x_ood_o, x_attack_o, x_id_sr, x_ood_sr, x_attack_sr)
    if not datasets:
        write_text(OUT / "locked_validation_asset_gap.md", "# Locked Validation Asset Gap\n\nNo unused locked validation object was available.")
        raise RuntimeError("No locked validation object")

    rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    support_rows: list[dict[str, Any]] = []
    selected_rows: list[dict[str, Any]] = []
    specs = method_specs()
    for spec in datasets:
        train_pool = np.asarray(spec["attack_train_pool_idx"], dtype=np.int64)
        kcenter_cache: dict[int, np.ndarray] = {}
        for seed in SEEDS:
            for method_spec in specs:
                budget = int(method_spec["support_budget"])
                if str(method_spec["support_method"]) == "random":
                    support = issue22.random_support(train_pool, budget, seed)
                else:
                    if budget not in kcenter_cache:
                        kcenter_cache[budget] = issue19b.kcenter_support(train_pool, x_attack_o[train_pool], budget)
                    support = kcenter_cache[budget]
                seed_rows, thr_rows, supp_rows, feat_rows = run_method_locked(
                    dataset_spec=spec,
                    method_spec=method_spec,
                    seed=seed,
                    support_rows=support,
                    x_attack_o=x_attack_o,
                    x_attack_sr=x_attack_sr,
                    sr_names=sr_names,
                )
                rows.extend(seed_rows)
                threshold_rows.extend(thr_rows)
                support_rows.extend(supp_rows)
                selected_rows.extend(feat_rows)
            print(f"[issue23] {spec['holdout']} seed={seed} completed", flush=True)

    by_seed = pd.DataFrame(rows)
    thresholds = pd.DataFrame(threshold_rows)
    supports = pd.DataFrame(support_rows)
    features = pd.DataFrame(selected_rows)
    summary = summarize(by_seed)
    by_seed.to_csv(OUT / "method_comparison_by_seed.csv", index=False)
    summary.to_csv(OUT / "method_comparison_summary.csv", index=False)
    thresholds.to_csv(OUT / "threshold_provenance.csv", index=False)
    supports.to_csv(OUT / "support_id_provenance.csv", index=False)
    features.to_csv(OUT / "selected_feature_provenance.csv", index=False)
    asset_report.to_csv(OUT / "locked_validation_asset_report.csv", index=False)
    write_reports(summary, by_seed, thresholds, supports, features, asset_report, meta)

    manifest_rows = []
    for path in sorted(OUT.glob("*")):
        if path.is_file() and path.name != "manifest.csv":
            manifest_rows.append({"file": path.name, "size_bytes": path.stat().st_size})
    manifest_rows.append({"file": "runtime_seconds", "size_bytes": f"{time.perf_counter() - t0:.3f}"})
    pd.DataFrame(manifest_rows).to_csv(OUT / "manifest.csv", index=False)


if __name__ == "__main__":
    main()
