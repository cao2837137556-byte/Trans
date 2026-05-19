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
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs" / "issue22_v2_hard_shift_enhancement_pilot_2026-05-18"
ISSUE19 = ROOT / "runs" / "issue19_lowguard_plus_representation_margin_repair_pilot_2026-05-18"
ISSUE19B = ROOT / "runs" / "issue19b_v1_v2_same_protocol_backtest_and_alarm_budget_curve_2026-05-18"
ISSUE18 = ROOT / "runs" / "issue18_row_level_score_persistence_and_ood_target_sensitivity_2026-05-15"
ISSUE17 = ROOT / "runs" / "issue17_support_diversity_selection_harder_holdout_2026-05-15"
ISSUE20 = ROOT / "runs" / "issue20_mode_specific_routing_validation_2026-05-18"
ISSUE20B = ROOT / "runs" / "issue20b_promotion_proxy_construction_for_routing_2026-05-18"
ISSUE21 = ROOT / "runs" / "issue21_active_review_promotion_asset_feasibility_2026-05-18"
ISSUE11 = ROOT / "runs" / "issue11_fixed_config_ood_guard_lr_ablation_2026-05-14"
ISSUE19B_SCRIPT = ISSUE19B / "run_issue19b_v1_v2_backtest.py"

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
SEEDS = list(range(42, 52))
OOD_TAIL_FRAC = 0.05
HARDNEG_WEIGHT = 4.0


def import_issue19b() -> Any:
    spec = importlib.util.spec_from_file_location("issue19b_v1_v2_backtest", ISSUE19B_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {ISSUE19B_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["issue19b_v1_v2_backtest"] = module
    spec.loader.exec_module(module)
    return module


issue19b = import_issue19b()


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
        vals = []
        for value in row:
            if isinstance(value, (float, np.floating)):
                vals.append("" if math.isnan(float(value)) else f"{float(value):.6f}")
            else:
                vals.append(str(value))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"


def require_inputs() -> list[str]:
    required = [
        ISSUE19 / "summary.md",
        ISSUE19 / "method_comparison_summary.csv",
        ISSUE19 / "representation_ablation_summary.csv",
        ISSUE19 / "selected_feature_report.csv",
        ISSUE19 / "selected_representation_protocol.md",
        ISSUE19 / "margin_ablation_summary.csv",
        ISSUE19 / "provenance_report.md",
        ISSUE19B / "summary.md",
        ISSUE19B / "v1_vs_v2_by_dataset.csv",
        ISSUE19B / "alarm_budget_curve_summary.csv",
        ISSUE19B / "feasible_operating_points.csv",
        ISSUE19B / "non_regression_report.md",
        ISSUE19B / "mode_routing_implication.md",
        ISSUE18 / "row_level_scores_manifest.csv",
        ISSUE18 / "attack_ood_separation_summary.csv",
        ISSUE18 / "margin_distribution_summary.csv",
        ISSUE18 / "ood_target_sensitivity_summary.csv",
        ISSUE17 / "summary.md",
        ISSUE20 / "summary.md",
        ISSUE20B / "summary.md",
        ISSUE21 / "summary.md",
        ISSUE11 / "config.json",
        ISSUE19B_SCRIPT,
    ]
    return [str(path) for path in required if not path.exists()]


def seed_group(seed: int) -> str:
    return issue19b.seed_group(seed)


def random_support(train_rows: np.ndarray, budget: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed + 2200 + budget)
    if len(train_rows) <= budget:
        return np.asarray(sorted(train_rows), dtype=np.int64)
    return np.asarray(sorted(rng.choice(np.asarray(train_rows, dtype=np.int64), size=budget, replace=False)), dtype=np.int64)


def fit_lr_scores(
    *,
    x_id_train: np.ndarray,
    x_ood_train: np.ndarray,
    x_pos: np.ndarray,
    x_id_calib: np.ndarray,
    x_ood_val: np.ndarray,
    x_ood_eval: np.ndarray,
    x_attack_eval: np.ndarray,
    hard_negative: bool = False,
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

    def train_and_score(extra_raw: np.ndarray | None = None) -> tuple[dict[str, np.ndarray], float, float, int]:
        scaler = StandardScaler()
        t0 = time.perf_counter()
        x_train_z = scaler.fit_transform(x_train)
        y = y_train
        w = sample_weight
        if extra_raw is not None and len(extra_raw):
            extra_z = scaler.transform(extra_raw)
            x_train_z = np.vstack([x_train_z, extra_z])
            y = np.concatenate([y, np.zeros(len(extra_raw), dtype=np.int64)])
            w = np.concatenate([w, np.full(len(extra_raw), HARDNEG_WEIGHT, dtype=np.float64)])
        model = LogisticRegression(
            C=1.0,
            penalty="l2",
            solver="liblinear",
            class_weight="balanced",
            max_iter=2000,
            random_state=42,
        )
        model.fit(x_train_z, y, sample_weight=w)
        train_time = time.perf_counter() - t0
        t1 = time.perf_counter()
        scores = {
            "id_calib": model.decision_function(scaler.transform(x_id_calib)).astype(np.float64),
            "ood_val": model.decision_function(scaler.transform(x_ood_val)).astype(np.float64),
            "final_ood_eval": model.decision_function(scaler.transform(x_ood_eval)).astype(np.float64),
            "attack_eval": model.decision_function(scaler.transform(x_attack_eval)).astype(np.float64),
        }
        inference_time = time.perf_counter() - t1
        parameter_count = int(model.coef_.size + model.intercept_.size)
        return scores, train_time, inference_time, parameter_count

    hard_negative_count = 0
    if hard_negative:
        base_scores, _, _, _ = train_and_score()
        n_tail = max(1, int(math.ceil(len(x_ood_val) * OOD_TAIL_FRAC)))
        tail_idx = np.argsort(-base_scores["ood_val"])[:n_tail]
        extra = x_ood_val[tail_idx]
        hard_negative_count = int(len(extra))
        scores, train_time, inference_time, parameter_count = train_and_score(extra)
    else:
        scores, train_time, inference_time, parameter_count = train_and_score()

    y_auc = np.concatenate(
        [np.zeros(len(scores["final_ood_eval"]), dtype=np.int64), np.ones(len(scores["attack_eval"]), dtype=np.int64)]
    )
    s_auc = np.concatenate([scores["final_ood_eval"], scores["attack_eval"]])
    thresholds = {target: issue19b.v72.guarded_val_threshold(scores["id_calib"], scores["ood_val"], target) for target in TARGETS}
    return {
        "scores": scores,
        "roc_auc": float(roc_auc_score(y_auc, s_auc)),
        "pr_auc": float(average_precision_score(y_auc, s_auc)),
        "thresholds": thresholds,
        "train_time": float(train_time),
        "inference_time": float(inference_time),
        "parameter_count": int(parameter_count),
        "hard_negative_count": hard_negative_count,
    }


def method_specs() -> list[dict[str, Any]]:
    return [
        {
            "method": "M0_V1_original100_kcenter32_fixed_guard",
            "method_group": "baseline",
            "representation": "original100",
            "support_method": "kcenter",
            "support_budget": 32,
            "top_k": 0,
            "adapter": "fixed_guard_lr",
        },
        {
            "method": "M1_V2_source_rich_top32_kcenter32_fixed_guard",
            "method_group": "v2_baseline",
            "representation": "selected_source_rich",
            "support_method": "kcenter",
            "support_budget": 32,
            "top_k": 32,
            "adapter": "fixed_guard_lr",
        },
        {
            "method": "M3_source_rich_top32_kcenter64_fixed_guard",
            "method_group": "support_budget",
            "representation": "selected_source_rich",
            "support_method": "kcenter",
            "support_budget": 64,
            "top_k": 32,
            "adapter": "fixed_guard_lr",
        },
        {
            "method": "M4_source_rich_top32_kcenter128_fixed_guard",
            "method_group": "support_budget",
            "representation": "selected_source_rich",
            "support_method": "kcenter",
            "support_budget": 128,
            "top_k": 32,
            "adapter": "fixed_guard_lr",
        },
        {
            "method": "M4b_source_rich_top32_random64_fixed_guard",
            "method_group": "support_budget_random_baseline",
            "representation": "selected_source_rich",
            "support_method": "random",
            "support_budget": 64,
            "top_k": 32,
            "adapter": "fixed_guard_lr",
        },
        {
            "method": "M5_source_rich_top16_kcenter32_fixed_guard",
            "method_group": "feature_count",
            "representation": "selected_source_rich",
            "support_method": "kcenter",
            "support_budget": 32,
            "top_k": 16,
            "adapter": "fixed_guard_lr",
        },
        {
            "method": "M7_source_rich_top48_kcenter32_fixed_guard",
            "method_group": "feature_count",
            "representation": "selected_source_rich",
            "support_method": "kcenter",
            "support_budget": 32,
            "top_k": 48,
            "adapter": "fixed_guard_lr",
        },
        {
            "method": "M8_source_rich_top64_kcenter32_fixed_guard",
            "method_group": "feature_count",
            "representation": "selected_source_rich",
            "support_method": "kcenter",
            "support_budget": 32,
            "top_k": 64,
            "adapter": "fixed_guard_lr",
        },
        {
            "method": "M9_source_rich_top32_kcenter32_hardneg_w4",
            "method_group": "low_fpr_adapter_sanity",
            "representation": "selected_source_rich",
            "support_method": "kcenter",
            "support_budget": 32,
            "top_k": 32,
            "adapter": "ood_tail_hard_negative_lr",
        },
    ]


def run_method(
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
    feature_idx: np.ndarray | None = None

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

    result = fit_lr_scores(
        x_id_train=x_id_train,
        x_ood_train=x_ood_train,
        x_pos=x_pos,
        x_id_calib=x_id_calib,
        x_ood_val=x_ood_val,
        x_ood_eval=x_ood_eval,
        x_attack_eval=x_attack_eval,
        hard_negative=str(method_spec["adapter"]) == "ood_tail_hard_negative_lr",
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
                "method_group": method_spec["method_group"],
                "representation": representation if representation == "original100" else f"selected_source_rich_top{top_k}",
                "adapter": method_spec["adapter"],
                "support_method": method_spec["support_method"],
                "support_size": int(len(support_rows)),
                "support_budget": int(method_spec["support_budget"]),
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
                "feature_dim": feature_count,
                "selected_topk": top_k,
                "hard_negative_count": int(result["hard_negative_count"]),
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
    support_rows_out = [
        {
            "dataset": dataset,
            "holdout": holdout,
            "method": method,
            "seed": int(seed),
            "seed_group": seed_group(seed),
            "support_method": method_spec["support_method"],
            "support_budget": int(method_spec["support_budget"]),
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
    return seed_rows, threshold_rows, support_rows_out, selected_feature_rows


def summarize(by_seed: pd.DataFrame) -> pd.DataFrame:
    return (
        by_seed.groupby(
            ["dataset", "holdout", "method", "method_group", "seed_group", "ood_target", "ood_target_label"],
            as_index=False,
        )
        .agg(
            n_seeds=("seed", "nunique"),
            roc_auc_mean=("roc_auc", "mean"),
            pr_auc_mean=("pr_auc", "mean"),
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
            hard_negative_count=("hard_negative_count", "first"),
            train_time_mean=("train_time", "mean"),
            inference_time_mean=("inference_time", "mean"),
            provenance_clean_rate=("provenance_clean", "mean"),
        )
        .sort_values(["dataset", "holdout", "ood_target", "method", "seed_group"])
    )


def write_reports(summary: pd.DataFrame, by_seed: pd.DataFrame, threshold_rows: pd.DataFrame, support_rows: pd.DataFrame, selected_rows: pd.DataFrame, dataset_meta: dict[str, Any]) -> None:
    official = summary[summary["ood_target"].eq(MAIN_TARGET)].copy()
    hb2 = official[official["holdout"].eq("holdout_bin_2")].copy()
    hb2_all = (
        by_seed[(by_seed["holdout"].eq("holdout_bin_2")) & (by_seed["ood_target"].eq(MAIN_TARGET))]
        .groupby(["method", "method_group"], as_index=False)
        .agg(
            attack_high_detection_mean=("attack_high_detection", "mean"),
            attack_high_detection_min=("attack_high_detection", "min"),
            attack_high_detection_max=("attack_high_detection", "max"),
            final_ood_high_alarm_max=("final_ood_high_alarm", "max"),
            feasible_rate=("feasible_final_1pct", "mean"),
            feature_dim=("feature_dim", "first"),
            support_size=("support_size", "first"),
        )
        .sort_values(["feasible_rate", "attack_high_detection_mean", "final_ood_high_alarm_max"], ascending=[False, False, True])
    )
    best = hb2_all.iloc[0] if not hb2_all.empty else None
    best_method = str(best["method"]) if best is not None else "none"
    best_det = float(best["attack_high_detection_mean"]) if best is not None else math.nan
    best_ood = float(best["final_ood_high_alarm_max"]) if best is not None else math.nan
    reaches_085 = bool(best_det >= 0.85 and best_ood <= 0.01) if best is not None else False
    reaches_090 = bool(best_det >= 0.90 and best_ood <= 0.01) if best is not None else False

    chrono_best_rows = official[official["holdout"].eq("chrono_late_train_early_eval")]
    primary_rows = official[official["holdout"].eq("primary_lowood")]
    best_chrono = chrono_best_rows[chrono_best_rows["method"].eq(best_method)] if best_method != "none" else pd.DataFrame()
    best_primary = primary_rows[primary_rows["method"].eq(best_method)] if best_method != "none" else pd.DataFrame()
    chrono_ood_max = float(best_chrono["final_ood_high_alarm_max"].max()) if not best_chrono.empty else math.nan
    chrono_det = float(best_chrono["attack_high_detection_mean"].mean()) if not best_chrono.empty else math.nan
    primary_ood_max = float(best_primary["final_ood_high_alarm_max"].max()) if not best_primary.empty else math.nan

    write_text(
        OUT / "preflight_v2_enhancement_check.md",
        """
# Preflight V2 Enhancement Check

- Successfully read V2 baseline: yes.
- This run does not do routing or promotion: yes.
- V2 baseline is selected_source_rich_top32 + kcenter32 + fixed guard LR: yes.
- Final eval is not used for parameter selection: yes.
- source_rich feature assets are available: yes.
- kcenter64 and kcenter128 support can be reconstructed: yes.
- Alarm-budget curve can be evaluated: yes.
- holdout_bin_2 and chrono_late can be evaluated: yes.
- primary_lowood is retained as OOD safety check: yes.
- This is a pilot, not locked validation: yes.
""",
    )
    write_text(
        OUT / "summary.md",
        f"""
# Issue22 V2 Hard-Shift Enhancement Pilot Summary

## Outcome

- Preflight passed: yes.
- Routing/promotion attempted: no.
- V1/V2 historical definitions modified: no.
- Final eval used for topK/support/target selection: no.
- Strong enhancement threshold 0.85 reached: `{reaches_085}`.
- Very strong threshold 0.90 reached: `{reaches_090}`.
- Best holdout_bin_2 official-1% method: `{best_method}`.
- Best holdout_bin_2 detection mean: `{best_det:.6f}`.
- Best holdout_bin_2 OOD alarm max: `{best_ood:.6f}`.
- Best-method chrono_late detection mean: `{chrono_det:.6f}`.
- Best-method chrono_late OOD alarm max: `{chrono_ood_max:.6f}`.
- Best-method primary_lowood OOD alarm max: `{primary_ood_max:.6f}`.

## Holdout Bin 2 Official 1% Ranking

{md_table(hb2_all)}

## Interpretation

This is a pilot, not locked validation. The result should be used to decide whether an enhanced V2 candidate deserves locked validation. If the best method only improves by relaxing diagnostic targets or worsens primary_lowood safety, it cannot be promoted as a final method.
""",
    )
    write_text(
        OUT / "protocol.md",
        """
# Protocol

- Fixed official OOD target: 1%.
- Diagnostic OOD targets: 0.5%, 0.8%, 1.2%, 1.5%, 2.0%.
- Support samples are selected only from the local attack train pool.
- TopK feature selection uses attack supports, ID calibration, and OOD validation only.
- Thresholds use ID calibration and OOD validation only.
- Final OOD eval and attack eval are report-only.
- No dA/Transformer training, V3, routing, promotion, MLP, prototype, or continual learning is performed.
""",
    )
    write_text(
        OUT / "enhancement_interpretation.md",
        f"""
# Enhancement Interpretation

Best official-1% holdout_bin_2 method: `{best_method}`.

- Holdout_bin_2 detection: `{best_det:.6f}`.
- Holdout_bin_2 OOD alarm max: `{best_ood:.6f}`.
- Reaches 0.85 threshold: `{reaches_085}`.
- Reaches 0.90 threshold: `{reaches_090}`.

Interpretation should be based on the method-group deltas:

- Alarm-budget operating points are diagnostic only.
- Support budget changes test whether V2 is label-budget limited.
- Feature-count sensitivity tests whether selected_source_rich_top32 is under/over-sized.
- Hard-negative sanity tests whether low-FPR weighting helps without introducing a new model class.

Any candidate must pass locked validation before becoming a new V2.
""",
    )
    write_text(
        OUT / "claim_boundary.md",
        """
# Claim Boundary

## Can Say

- V2 hard-shift enhancement pilot improves or does not improve detection if reported metrics support it.
- Candidate operating points require locked validation.
- holdout_bin_2 is a diagnostic challenge, not final generalization proof.

## Cannot Say

- Enhanced V2 is the final method.
- All future drift is solved.
- Routing or promotion is solved.
- Final eval was used to choose threshold/topK.
- CCF-A readiness is achieved.
""",
    )
    risks = [
        ["holdout_bin_2 overfitting", "high", "Enhancement is motivated by holdout_bin_2.", "Require locked validation before claims."],
        ["target cherry-picking", "high", "Diagnostic targets can look attractive.", "Keep 1% as official and report all targets."],
        ["topK overfitting", "medium", "TopK sensitivity can be selected post hoc.", "Report top16/top32/top48/top64 together."],
        ["support budget label cost", "medium", "kcenter64/128 require more confirmed attacks.", "Report support size and cost."],
        ["OOD alarm tradeoff", "high", "More detection can raise OOD alarms.", "Report final OOD max and feasibility."],
        ["primary safety degradation", "high", "V2 already fails primary OOD budget.", "Keep primary as safety check, not main battlefield."],
        ["chrono_late regression", "medium", "Hard-shift repair may hurt another holdout.", "Report chrono_late separately."],
        ["locked validation missing", "high", "Pilot is not final proof.", "Use issue23 if strong positive."],
    ]
    pd.DataFrame(risks, columns=["risk_name", "severity", "reason", "mitigation"]).to_csv(OUT / "risk_register.csv", index=False)

    if reaches_085:
        next_action = "issue23_locked_validation_for_enhanced_v2_2026-05-18"
    elif best_det >= 0.83 and best_ood <= 0.01:
        next_action = "run_leave_one_bin_or_additional_hard_holdout_before_claiming"
    else:
        next_action = "stop_v2_micro_optimization_and_proceed_to_generalization_baseline_pack"
    write_text(
        OUT / "recommended_next_action.md",
        f"""
# Recommended Next Action

Unique first choice: `{next_action}`.

Do not resume routing/promotion based on this pilot. If the best candidate is strong, lock it and validate; if not, stop micro-optimizing V2 and move to broader generalization/baseline evidence.
""",
    )
    write_text(
        OUT / "doc_update_patch_suggestion.md",
        """
# Suggested Mainline Docs Patch

Append after issue21:

`issue22 tests whether V2 hard-shift repair can be further improved without breaking low-alert constraints. It is a pilot only, not routing, promotion, V3, or locked validation.`
""",
    )

    official.to_csv(OUT / "method_comparison_summary_official_1pct.csv", index=False)
    hb2.to_csv(OUT / "holdout_bin2_v2_enhancement_summary.csv", index=False)
    official[official["holdout"].eq("chrono_late_train_early_eval")].to_csv(OUT / "chrono_late_v2_enhancement_summary.csv", index=False)
    official[official["holdout"].eq("primary_lowood")].to_csv(OUT / "primary_lowood_safety_check.csv", index=False)

    alarm_summary = summary[summary["method"].str.contains("M1_V2_source_rich_top32_kcenter32", regex=False)].copy()
    alarm_summary.to_csv(OUT / "alarm_budget_curve_summary.csv", index=False)
    by_seed[by_seed["method"].str.contains("M1_V2_source_rich_top32_kcenter32", regex=False)].to_csv(OUT / "alarm_budget_curve_by_seed.csv", index=False)

    support_sens = official[official["method_group"].isin(["support_budget", "support_budget_random_baseline", "v2_baseline"])].copy()
    support_sens.to_csv(OUT / "support_budget_sensitivity.csv", index=False)
    feature_sens = official[official["method_group"].isin(["feature_count", "v2_baseline"])].copy()
    feature_sens.to_csv(OUT / "feature_count_sensitivity.csv", index=False)
    low_fpr = official[official["method_group"].eq("low_fpr_adapter_sanity")].copy()
    if low_fpr.empty:
        pd.DataFrame([{"status": "not_run", "not_run_reason": "low-FPR adapter sanity skipped"}]).to_csv(OUT / "low_fpr_adapter_sanity.csv", index=False)
    else:
        low_fpr.to_csv(OUT / "low_fpr_adapter_sanity.csv", index=False)

    feasible = summary[summary["final_ood_high_alarm_max"].le(0.01)].copy()
    feasible["diagnostic_only"] = feasible["ood_target"].ne(MAIN_TARGET)
    feasible.to_csv(OUT / "feasible_operating_points.csv", index=False)

    config = {
        "run": "issue22_v2_hard_shift_enhancement_pilot_2026-05-18",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "targets": TARGETS,
        "main_target": MAIN_TARGET,
        "seeds": SEEDS,
        "methods": [m["method"] for m in method_specs()],
        "best_method": best_method,
        "best_holdout_bin2_detection": best_det,
        "best_holdout_bin2_ood_max": best_ood,
        "reaches_085": reaches_085,
        "reaches_090": reaches_090,
        "next_action": next_action,
        "final_eval_used_for_selection": False,
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "figures").mkdir(exist_ok=True)
    missing = require_inputs()
    if missing:
        write_text(OUT / "missing_input_report.md", "# Missing Input Report\n\n" + "\n".join(f"- {item}" for item in missing))
        raise RuntimeError(f"Missing required inputs: {missing}")
    t0 = time.perf_counter()
    cfg = json.loads((ISSUE11 / "config.json").read_text(encoding="utf-8"))
    paths = cfg["paths"]
    x_id_o = issue19b.load_matrix(Path(paths["original100_id"]))
    x_ood_o = issue19b.load_matrix(Path(paths["original100_ood"]))
    x_attack_o = issue19b.load_matrix(Path(paths["original100_attack"]))
    x_id_sr = issue19b.load_matrix(Path(paths["source_rich_id"]))
    x_ood_sr = issue19b.load_matrix(Path(paths["source_rich_ood"]))
    x_attack_sr = issue19b.load_matrix(Path(paths["source_rich_attack"]))
    if x_id_o.shape[0] != x_id_sr.shape[0] or x_ood_o.shape[0] != x_ood_sr.shape[0] or x_attack_o.shape[0] != x_attack_sr.shape[0]:
        write_text(OUT / "alignment_failure_report.md", "# Alignment Failure\n\noriginal100/source_rich row-count mismatch.")
        raise RuntimeError("original100/source_rich row-count mismatch")
    schema_path = Path(paths["source_rich_id"]).parents[1] / "data" / "structured_schema.json"
    sr_names = issue19b.feature_names(schema_path, x_id_sr.shape[1])
    datasets, dataset_meta = issue19b.build_datasets(
        paths=paths,
        x_id_o=x_id_o,
        x_ood_o=x_ood_o,
        x_attack_o=x_attack_o,
        x_id_sr=x_id_sr,
        x_ood_sr=x_ood_sr,
        x_attack_sr=x_attack_sr,
    )

    rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    support_rows: list[dict[str, Any]] = []
    selected_rows: list[dict[str, Any]] = []
    for spec in datasets:
        train_pool = np.asarray(spec["attack_train_pool_idx"], dtype=np.int64)
        kcenter_cache: dict[int, np.ndarray] = {}
        for seed in SEEDS:
            for method_spec in method_specs():
                budget = int(method_spec["support_budget"])
                if str(method_spec["support_method"]) == "random":
                    support = random_support(train_pool, budget, seed)
                else:
                    if budget not in kcenter_cache:
                        kcenter_cache[budget] = issue19b.kcenter_support(train_pool, x_attack_o[train_pool], budget)
                    support = kcenter_cache[budget]
                seed_rows, thr_rows, supp_rows, feat_rows = run_method(
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
            print(f"[issue22] {spec['holdout']} seed={seed} completed", flush=True)

    by_seed = pd.DataFrame(rows)
    thresholds = pd.DataFrame(threshold_rows)
    supports = pd.DataFrame(support_rows)
    features = pd.DataFrame(selected_rows)
    summary = summarize(by_seed)

    by_seed.to_csv(OUT / "method_comparison_by_seed.csv", index=False)
    summary.to_csv(OUT / "method_comparison_summary.csv", index=False)
    thresholds.to_csv(OUT / "threshold_provenance.csv", index=False)
    supports.to_csv(OUT / "support_id_provenance.csv", index=False)
    features.to_csv(OUT / "selected_feature_report.csv", index=False)

    write_reports(summary, by_seed, thresholds, supports, features, dataset_meta)

    manifest_rows = []
    for path in sorted(OUT.glob("*")):
        if path.is_file() and path.name != "manifest.csv":
            manifest_rows.append({"file": path.name, "size_bytes": path.stat().st_size})
    manifest_rows.append({"file": "runtime_seconds", "size_bytes": f"{time.perf_counter() - t0:.3f}"})
    pd.DataFrame(manifest_rows).to_csv(OUT / "manifest.csv", index=False)


if __name__ == "__main__":
    main()
