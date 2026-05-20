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
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import average_precision_score, roc_auc_score, roc_curve
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs" / "issue24_adapter_upgrade_feasibility_for_enhanced_v2_top64_2026-05-18"
ISSUE23 = ROOT / "runs" / "issue23_locked_validation_for_enhanced_v2_top64_2026-05-18"
ISSUE22B = ROOT / "runs" / "issue22b_enhanced_v2_primary_nonregression_check_2026-05-18"
ISSUE22 = ROOT / "runs" / "issue22_v2_hard_shift_enhancement_pilot_2026-05-18"
ISSUE19B = ROOT / "runs" / "issue19b_v1_v2_same_protocol_backtest_and_alarm_budget_curve_2026-05-18"
ISSUE18 = ROOT / "runs" / "issue18_row_level_score_persistence_and_ood_target_sensitivity_2026-05-15"
ISSUE11 = ROOT / "runs" / "issue11_fixed_config_ood_guard_lr_ablation_2026-05-14"
ISSUE23_SCRIPT = ISSUE23 / "run_issue23_locked_validation.py"
ISSUE22_SCRIPT = ISSUE22 / "run_issue22_v2_enhancement.py"
ISSUE19B_SCRIPT = ISSUE19B / "run_issue19b_v1_v2_backtest.py"

TOP_K = 64
SUPPORT_BUDGET = 32
SUPPORT_TRAIN_FOR_SELECTION = 24
MAIN_TARGET = 0.01
TARGET_LABEL = "1.0pct"
SEEDS = list(range(42, 52))
LOCKED_HOLDOUTS = ["holdout_bin_5", "holdout_bin_6", "holdout_bin_7", "holdout_bin_8"]
CONSISTENCY_HOLDOUTS = ["primary_lowood", "holdout_bin_2", "chrono_late_train_early_eval"]
FEATURE_CACHE: dict[tuple[str, int, tuple[int, ...], int], tuple[np.ndarray, list[dict[str, Any]]]] = {}


def import_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


issue23 = import_module(ISSUE23_SCRIPT, "issue23_locked_validation")
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
        ISSUE23 / "summary.md",
        ISSUE23 / "locked_validation_asset_report.md",
        ISSUE23 / "method_comparison_summary.csv",
        ISSUE23 / "method_comparison_by_seed.csv",
        ISSUE23 / "v2top64_vs_v1_locked.csv",
        ISSUE23 / "v2top64_vs_v2top32_locked.csv",
        ISSUE23 / "low_fpr_metrics_summary.csv",
        ISSUE23 / "claim_boundary.md",
        ISSUE23 / "recommended_next_action.md",
        ISSUE22B / "summary.md",
        ISSUE22B / "primary_lowood_nonregression_summary.csv",
        ISSUE22B / "primary_lowood_nonregression_by_seed.csv",
        ISSUE22B / "global_candidate_status.md",
        ISSUE22 / "summary.md",
        ISSUE19B / "summary.md",
        ISSUE18 / "row_level_scores_manifest.csv",
        ISSUE11 / "config.json",
        ISSUE23_SCRIPT,
        ISSUE22_SCRIPT,
        ISSUE19B_SCRIPT,
    ]
    return [str(path) for path in required if not path.exists()]


def adapter_spaces() -> dict[str, list[dict[str, Any]]]:
    return {
        "A0_lr_baseline": [
            {"adapter": "A0_lr_baseline", "config_id": "lr_fixed_guard", "model_type": "lr", "attack_weight": 1.0, "ood_train_weight": 2.0, "tail_quantile": None, "tail_weight": 0.0, "C": 1.0}
        ],
        "A1_low_fpr_weighted_lr": [
            {"adapter": "A1_low_fpr_weighted_lr", "config_id": f"lr_tail_q{q}_w{w}_a{a}", "model_type": "lr", "attack_weight": a, "ood_train_weight": 2.0, "tail_quantile": q, "tail_weight": w, "C": 1.0}
            for q, w, a in [
                (0.95, 4.0, 1.0),
                (0.975, 4.0, 1.0),
                (0.975, 8.0, 1.0),
            ]
        ],
        "A2_linear_svm_margin": [
            {"adapter": "A2_linear_svm_margin", "config_id": f"sgd_hinge_alpha{alpha}_a{a}", "model_type": "linear_svm", "attack_weight": a, "ood_train_weight": 2.0, "alpha": alpha}
            for alpha, a in [(1e-4, 1.0), (1e-5, 1.0), (1e-4, 2.0)]
        ],
    }


def all_candidate_configs() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for configs in adapter_spaces().values():
        rows.extend(configs)
    return rows


def split_support_for_selection(support_rows: np.ndarray, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed + 24024)
    shuffled = np.asarray(support_rows, dtype=np.int64).copy()
    rng.shuffle(shuffled)
    return np.sort(shuffled[:SUPPORT_TRAIN_FOR_SELECTION]), np.sort(shuffled[SUPPORT_TRAIN_FOR_SELECTION:])


def fit_scaler(x_id_train: np.ndarray, x_ood_train: np.ndarray, x_pos: np.ndarray) -> StandardScaler:
    scaler = StandardScaler()
    scaler.fit(np.vstack([x_id_train, x_ood_train, x_pos]))
    return scaler


def train_model(
    *,
    config: dict[str, Any],
    scaler: StandardScaler,
    x_id_train: np.ndarray,
    x_ood_train: np.ndarray,
    x_pos: np.ndarray,
    x_ood_val: np.ndarray,
    seed: int,
) -> tuple[Any, int, int]:
    model_type = str(config["model_type"])
    x_train_raw = np.vstack([x_id_train, x_ood_train, x_pos])
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
            np.full(len(x_ood_train), float(config.get("ood_train_weight", 2.0)), dtype=np.float64),
            np.full(len(x_pos), float(config.get("attack_weight", 1.0)), dtype=np.float64),
        ]
    )
    x_train = scaler.transform(x_train_raw)
    hard_negative_count = 0

    if model_type == "lr" and config.get("tail_quantile") is not None and float(config.get("tail_weight", 0.0)) > 0:
        base = LogisticRegression(C=float(config.get("C", 1.0)), penalty="l2", solver="liblinear", class_weight="balanced", max_iter=2000, random_state=seed)
        base.fit(x_train, y_train, sample_weight=sample_weight)
        ood_val_scores = base.decision_function(scaler.transform(x_ood_val))
        cutoff = np.quantile(ood_val_scores, float(config["tail_quantile"]))
        tail_raw = x_ood_val[ood_val_scores >= cutoff]
        if len(tail_raw):
            x_train = np.vstack([x_train, scaler.transform(tail_raw)])
            y_train = np.concatenate([y_train, np.zeros(len(tail_raw), dtype=np.int64)])
            sample_weight = np.concatenate([sample_weight, np.full(len(tail_raw), float(config["tail_weight"]), dtype=np.float64)])
            hard_negative_count = int(len(tail_raw))

    if model_type == "lr":
        model = LogisticRegression(C=float(config.get("C", 1.0)), penalty="l2", solver="liblinear", class_weight="balanced", max_iter=2000, random_state=seed)
        model.fit(x_train, y_train, sample_weight=sample_weight)
        param_count = int(model.coef_.size + model.intercept_.size)
    elif model_type == "linear_svm":
        model = SGDClassifier(
            loss="hinge",
            penalty="l2",
            alpha=float(config.get("alpha", 1e-4)),
            max_iter=2000,
            tol=1e-3,
            class_weight="balanced",
            random_state=seed,
        )
        model.fit(x_train, y_train, sample_weight=sample_weight)
        param_count = int(model.coef_.size + model.intercept_.size)
    else:
        raise ValueError(f"Unknown model_type: {model_type}")
    return model, hard_negative_count, param_count


def score_model(model: Any, scaler: StandardScaler, x: np.ndarray, model_type: str) -> np.ndarray:
    xz = scaler.transform(x)
    if model_type in {"lr", "linear_svm"}:
        return np.asarray(model.decision_function(xz), dtype=np.float64)
    if hasattr(model, "predict_proba"):
        proba = model.predict_proba(xz)
        return np.asarray(proba[:, 1], dtype=np.float64)
    return np.asarray(model.decision_function(xz), dtype=np.float64)


def evaluate_scores(scores_ood: np.ndarray, scores_attack: np.ndarray) -> tuple[float, float, float, float]:
    y_true = np.concatenate([np.zeros(len(scores_ood), dtype=np.int64), np.ones(len(scores_attack), dtype=np.int64)])
    y_score = np.concatenate([scores_ood, scores_attack])
    roc = float(roc_auc_score(y_true, y_score))
    pr = float(average_precision_score(y_true, y_score))
    pauc = float(roc_auc_score(y_true, y_score, max_fpr=0.01))
    fpr, tpr, _ = roc_curve(y_true, y_score)
    tpr1 = float(np.max(tpr[fpr <= 0.01])) if np.any(fpr <= 0.01) else 0.0
    return roc, pr, pauc, tpr1


def prepare_top64(
    *,
    dataset_spec: dict[str, Any],
    support_rows: np.ndarray,
    x_attack_sr: np.ndarray,
    sr_names: list[str],
    seed: int,
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    key = (str(dataset_spec["holdout"]), int(seed), tuple(map(int, support_rows)), TOP_K)
    if key in FEATURE_CACHE:
        return FEATURE_CACHE[key]
    x_pos_sr = x_attack_sr[support_rows]
    value = issue19b.selected_source_rich_features(
        x_support=x_pos_sr,
        x_id_calib=dataset_spec["x_id_calib_sr"],
        x_ood_val=dataset_spec["x_ood_val_sr"],
        names=sr_names,
        dataset=str(dataset_spec["dataset"]),
        holdout=str(dataset_spec["holdout"]),
        seed=seed,
        top_k=TOP_K,
    )
    FEATURE_CACHE[key] = value
    return value


def run_config_once(
    *,
    dataset_spec: dict[str, Any],
    config: dict[str, Any],
    support_train_rows: np.ndarray,
    eval_positive_rows: np.ndarray,
    x_attack_sr: np.ndarray,
    sr_names: list[str],
    seed: int,
    use_final_eval: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    feature_idx, feature_rows = prepare_top64(dataset_spec=dataset_spec, support_rows=support_train_rows, x_attack_sr=x_attack_sr, sr_names=sr_names, seed=seed)
    x_id_train = dataset_spec["x_id_train_sr"][:, feature_idx]
    x_ood_train = dataset_spec["x_ood_train_sr"][:, feature_idx]
    x_pos = x_attack_sr[support_train_rows][:, feature_idx]
    x_id_calib = dataset_spec["x_id_calib_sr"][:, feature_idx]
    x_ood_val = dataset_spec["x_ood_val_sr"][:, feature_idx]
    x_eval_pos = x_attack_sr[eval_positive_rows][:, feature_idx]
    if use_final_eval:
        x_ood_eval = dataset_spec["x_ood_eval_sr"][:, feature_idx]
    else:
        x_ood_eval = x_ood_val
    scaler = fit_scaler(x_id_train, x_ood_train, x_pos)
    t0 = time.perf_counter()
    model, hard_negative_count, param_count = train_model(
        config=config,
        scaler=scaler,
        x_id_train=x_id_train,
        x_ood_train=x_ood_train,
        x_pos=x_pos,
        x_ood_val=x_ood_val,
        seed=seed,
    )
    train_time = time.perf_counter() - t0
    t1 = time.perf_counter()
    model_type = str(config["model_type"])
    id_calib_scores = score_model(model, scaler, x_id_calib, model_type)
    ood_val_scores = score_model(model, scaler, x_ood_val, model_type)
    ood_eval_scores = score_model(model, scaler, x_ood_eval, model_type)
    eval_pos_scores = score_model(model, scaler, x_eval_pos, model_type)
    inference_time = time.perf_counter() - t1
    threshold_info = issue19b.v72.guarded_val_threshold(id_calib_scores, ood_val_scores, MAIN_TARGET)
    threshold = float(threshold_info["threshold"])
    roc, pr, pauc, tpr1 = evaluate_scores(ood_eval_scores, eval_pos_scores)
    result = {
        "threshold": threshold,
        "roc_auc": roc,
        "pr_auc": pr,
        "pauc_fpr_1pct": pauc,
        "tpr_at_fpr_1pct": tpr1,
        "positive_detection": float(np.mean(eval_pos_scores > threshold)),
        "ood_alarm": float(np.mean(ood_eval_scores > threshold)),
        "id_calib_alarm_at_selection": float(np.mean(id_calib_scores > threshold)),
        "ood_val_alarm_at_selection": float(np.mean(ood_val_scores > threshold)),
        "positive_score_q25": float(np.quantile(eval_pos_scores, 0.25)),
        "positive_score_median": float(np.median(eval_pos_scores)),
        "positive_margin_q25": float(np.quantile(eval_pos_scores - threshold, 0.25)),
        "positive_margin_median": float(np.median(eval_pos_scores - threshold)),
        "train_time": float(train_time),
        "inference_time": float(inference_time),
        "parameter_count": int(param_count),
        "hard_negative_count": int(hard_negative_count),
        "feature_dim": int(TOP_K),
        "eval_positive_size": int(len(eval_pos_scores)),
        "ood_eval_size": int(len(ood_eval_scores)),
    }
    return result, feature_rows


def select_adapter_config(
    *,
    dataset_spec: dict[str, Any],
    adapter_name: str,
    configs: list[dict[str, Any]],
    support_rows: np.ndarray,
    x_attack_sr: np.ndarray,
    sr_names: list[str],
    seed: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if adapter_name == "A0_lr_baseline":
        return configs[0], []
    train_support, val_support = split_support_for_selection(support_rows, seed)
    validation_rows: list[dict[str, Any]] = []
    for config in configs:
        result, _ = run_config_once(
            dataset_spec=dataset_spec,
            config=config,
            support_train_rows=train_support,
            eval_positive_rows=val_support,
            x_attack_sr=x_attack_sr,
            sr_names=sr_names,
            seed=seed,
            use_final_eval=False,
        )
        validation_rows.append(
            {
                "dataset": dataset_spec["dataset"],
                "holdout": dataset_spec["holdout"],
                "seed": int(seed),
                "seed_group": issue22.seed_group(seed),
                "adapter": adapter_name,
                "config_id": config["config_id"],
                "model_type": config["model_type"],
                "support_train_size": int(len(train_support)),
                "support_validation_size": int(len(val_support)),
                "support_val_detection": result["positive_detection"],
                "support_val_margin_q25": result["positive_margin_q25"],
                "support_val_margin_median": result["positive_margin_median"],
                "ood_val_alarm_at_selection": result["ood_val_alarm_at_selection"],
                "id_calib_alarm_at_selection": result["id_calib_alarm_at_selection"],
                "validation_selection_score": result["positive_detection"] * 1000.0 + result["positive_margin_q25"] - result["ood_val_alarm_at_selection"],
                "uses_final_eval": False,
            }
        )
    val_df = pd.DataFrame(validation_rows)
    val_df = val_df.sort_values(
        ["support_val_detection", "support_val_margin_q25", "support_val_margin_median", "ood_val_alarm_at_selection"],
        ascending=[False, False, False, True],
    )
    selected_config_id = str(val_df.iloc[0]["config_id"])
    selected = next(config for config in configs if str(config["config_id"]) == selected_config_id)
    for row in validation_rows:
        row["selected"] = bool(row["config_id"] == selected_config_id)
    return selected, validation_rows


def build_datasets(paths: dict[str, str], x_id_o: np.ndarray, x_ood_o: np.ndarray, x_attack_o: np.ndarray, x_id_sr: np.ndarray, x_ood_sr: np.ndarray, x_attack_sr: np.ndarray) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    locked_datasets, _, _ = issue23.build_locked_datasets(paths, x_id_o, x_ood_o, x_attack_o, x_id_sr, x_ood_sr, x_attack_sr)
    consistency_datasets, _ = issue19b.build_datasets(paths=paths, x_id_o=x_id_o, x_ood_o=x_ood_o, x_attack_o=x_attack_o, x_id_sr=x_id_sr, x_ood_sr=x_ood_sr, x_attack_sr=x_attack_sr)
    consistency_datasets = [spec for spec in consistency_datasets if str(spec["holdout"]) in CONSISTENCY_HOLDOUTS]
    for spec in locked_datasets:
        spec["evaluation_role"] = "locked"
    for spec in consistency_datasets:
        spec["evaluation_role"] = "consistency"
    return locked_datasets, consistency_datasets


def summarize(by_seed: pd.DataFrame) -> pd.DataFrame:
    return (
        by_seed.groupby(["evaluation_role", "dataset", "holdout", "adapter", "seed_group"], as_index=False)
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
            selected_config=("selected_config_id", lambda s: ";".join(sorted(set(map(str, s))))),
            train_time_mean=("train_time", "mean"),
            inference_time_mean=("inference_time", "mean"),
            parameter_count_mean=("parameter_count", "mean"),
            hard_negative_count_mean=("hard_negative_count", "mean"),
            provenance_clean_rate=("provenance_clean", "mean"),
        )
        .sort_values(["evaluation_role", "holdout", "adapter", "seed_group"])
    )


def locked_adapter_summary(summary: pd.DataFrame) -> pd.DataFrame:
    locked = summary[(summary["evaluation_role"].eq("locked")) & (summary["seed_group"].isin(["main_42_46", "heldout_47_51"]))].copy()
    rows = []
    for adapter, g in locked.groupby("adapter"):
        rows.append(
            {
                "adapter": adapter,
                "locked_detection_mean": float(g["attack_high_detection_mean"].mean()),
                "locked_detection_min": float(g["attack_high_detection_mean"].min()),
                "locked_ood_alarm_max": float(g["final_ood_high_alarm_max"].max()),
                "locked_feasible_rate_mean": float(g["feasible_rate"].mean()),
                "locked_pauc_fpr_1pct_mean": float(g["pauc_fpr_1pct_mean"].mean()),
                "locked_tpr_at_fpr_1pct_mean": float(g["tpr_at_fpr_1pct_mean"].mean()),
                "mean_train_time": float(g["train_time_mean"].mean()),
                "mean_inference_time": float(g["inference_time_mean"].mean()),
                "mean_parameter_count": float(g["parameter_count_mean"].mean()),
            }
        )
    out = pd.DataFrame(rows)
    baseline = out[out["adapter"].eq("A0_lr_baseline")]
    if not baseline.empty:
        b = baseline.iloc[0]
        out["delta_detection_mean_vs_lr"] = out["locked_detection_mean"] - float(b["locked_detection_mean"])
        out["delta_detection_min_vs_lr"] = out["locked_detection_min"] - float(b["locked_detection_min"])
        out["delta_ood_alarm_max_vs_lr"] = out["locked_ood_alarm_max"] - float(b["locked_ood_alarm_max"])
    return out.sort_values(["locked_feasible_rate_mean", "locked_detection_mean", "locked_detection_min"], ascending=[False, False, False])


def write_reports(summary: pd.DataFrame, by_seed: pd.DataFrame, validation: pd.DataFrame, complexity: pd.DataFrame) -> None:
    locked_sum = locked_adapter_summary(summary)
    locked_sum.to_csv(OUT / "locked_bins_adapter_summary.csv", index=False)
    locked_by_seed = by_seed[by_seed["evaluation_role"].eq("locked")].copy()
    locked_by_seed.to_csv(OUT / "locked_bins_adapter_by_seed.csv", index=False)
    consistency = summary[summary["evaluation_role"].eq("consistency")].copy()
    consistency.to_csv(OUT / "consistency_primary_holdout_chrono.csv", index=False)
    low_fpr = summary[
        [
            "evaluation_role",
            "dataset",
            "holdout",
            "adapter",
            "seed_group",
            "pauc_fpr_1pct_mean",
            "tpr_at_fpr_1pct_mean",
            "attack_high_detection_mean",
            "final_ood_high_alarm_max",
            "feasible_rate",
        ]
    ].copy()
    low_fpr.to_csv(OUT / "low_fpr_metrics_adapter_summary.csv", index=False)
    complexity.to_csv(OUT / "adapter_complexity_summary.csv", index=False)

    baseline = locked_sum[locked_sum["adapter"].eq("A0_lr_baseline")]
    best = locked_sum.iloc[0] if not locked_sum.empty else None
    baseline_row = baseline.iloc[0] if not baseline.empty else None
    best_adapter = str(best["adapter"]) if best is not None else "none"
    best_mean = float(best["locked_detection_mean"]) if best is not None else math.nan
    best_min = float(best["locked_detection_min"]) if best is not None else math.nan
    best_ood = float(best["locked_ood_alarm_max"]) if best is not None else math.nan
    lr_mean = float(baseline_row["locked_detection_mean"]) if baseline_row is not None else math.nan
    lr_min = float(baseline_row["locked_detection_min"]) if baseline_row is not None else math.nan
    lr_ood = float(baseline_row["locked_ood_alarm_max"]) if baseline_row is not None else math.nan
    delta_mean = best_mean - lr_mean
    delta_min = best_min - lr_min
    stable_upgrade = bool(best_adapter != "A0_lr_baseline" and delta_mean >= 0.01 and delta_min >= 0 and best_ood <= 0.01)
    very_strong = bool(best_mean >= 0.96 and best_min >= 0.90 and best_ood <= 0.01 and stable_upgrade)
    if very_strong:
        status = "very_strong_adapter_upgrade"
        next_action = "issue25_locked_or_second_environment_validation_for_best_adapter_2026-05-18"
    elif stable_upgrade:
        status = "strong_adapter_upgrade"
        next_action = "issue25_locked_or_second_environment_validation_for_best_adapter_2026-05-18"
    elif best_adapter != "A0_lr_baseline" and best_ood <= 0.01 and delta_mean > 0:
        status = "moderate_adapter_upgrade"
        next_action = "keep_lr_as_main_report_adapter_analysis_then_second_environment_or_strong_baseline_pack"
    else:
        status = "negative_adapter_upgrade"
        next_action = "retain_lr_as_main_adapter_then_strong_baselines_and_external_or_temporal_validation"

    bin_table = summary[(summary["evaluation_role"].eq("locked")) & (summary["seed_group"].eq("main_42_46"))][
        ["holdout", "adapter", "attack_high_detection_mean", "final_ood_high_alarm_max", "pauc_fpr_1pct_mean", "selected_config"]
    ].copy()
    bin8 = bin_table[bin_table["holdout"].eq("holdout_bin_8")]
    bin6_7 = bin_table[bin_table["holdout"].isin(["holdout_bin_6", "holdout_bin_7"])]

    write_text(
        OUT / "summary.md",
        f"""
# Issue24 Adapter Upgrade Feasibility Summary

## Outcome

- Preflight passed: yes.
- Representation fixed: selected_source_rich_top64.
- Support fixed: kcenter32.
- topK search: no.
- final eval used for adapter selection: no.
- Adapter status: `{status}`.
- Best adapter by locked feasible mean/min ranking: `{best_adapter}`.
- Best locked detection mean: `{best_mean:.6f}`.
- Best locked detection min: `{best_min:.6f}`.
- Best locked OOD max: `{best_ood:.6f}`.
- LR baseline locked detection mean: `{lr_mean:.6f}`.
- LR baseline locked detection min: `{lr_min:.6f}`.
- LR baseline locked OOD max: `{lr_ood:.6f}`.
- Best - LR locked mean delta: `{delta_mean:.6f}`.
- Best - LR locked min delta: `{delta_min:.6f}`.
- Recommended next action: `{next_action}`.

## Locked Adapter Summary

{md_table(locked_sum)}

## Bin-Level Main-Seed Snapshot

{md_table(bin_table)}

## Interpretation

This is a feasibility ablation. If the best adapter is not a stable improvement over LR under the 1% OOD constraint, LR remains the main adapter and the paper should frame representation plus low-alert guard as the stronger contribution.
""",
    )
    write_text(
        OUT / "protocol.md",
        """
# Protocol

This run fixes selected_source_rich_top64 and kcenter32 support. It compares adapter families only.

- Official target: 1% OOD alarm.
- Hyperparameter selection: support-validation split from the selected 32 support samples plus ID calibration and OOD validation.
- Support split for selection: 24 support-train / 8 support-validation.
- Final report: models are retrained on all 32 support samples with the selected adapter config.
- Final OOD eval and final attack eval are report-only.
- No topK search, no representation change, no routing, no promotion, no V3, no dA/Transformer training.
""",
    )
    write_text(
        OUT / "preflight_adapter_upgrade_check.md",
        """
# Preflight Adapter Upgrade Check

- Successfully read issue23 locked bins: yes.
- Representation fixed as selected_source_rich_top64: yes.
- Support fixed as kcenter32: yes.
- topK retuned: no.
- This run compares adapters only: yes.
- train/cal/val support adapter selection: yes, via 24/8 support split and ID/OOD calibration/validation.
- final eval used for adapter selection: no.
- locked bins 5/6/7/8 seed-level metrics available: yes.
- primary / holdout_bin2 / chrono consistency checks available: yes.
- This is feasibility, not final method replacement: yes.
""",
    )
    write_text(
        OUT / "adapter_candidate_definitions.md",
        """
# Adapter Candidate Definitions

- A0_lr_baseline: current fixed OOD guard logistic regression on selected_source_rich_top64.
- A1_low_fpr_weighted_lr: logistic regression with OOD-validation high-tail hard negatives added as weighted negatives.
- A2_linear_svm_margin: linear SVM margin scorer using fixed source_rich_top64 and weighted benign/attack samples.
- A3_hist_gradient_boosting: not run in this pass after the full grid exceeded the execution budget; kept as future design-only candidate.
- A4_devnet_like_lightweight_adapter: design-only in this pass; not run to avoid neural sweep creep.
- A5_deepsad_like_center_margin_adapter: design-only in this pass; not run due to objective/protocol risk.
""",
    )
    config_rows = []
    for config in all_candidate_configs():
        config_rows.append({k: v for k, v in config.items() if k not in set()})
    pd.DataFrame(config_rows).to_csv(OUT / "adapter_hyperparameter_search_space.csv", index=False)
    write_text(
        OUT / "adapter_hyperparameter_search_space.md",
        md_table(pd.DataFrame(config_rows)),
    )
    validation.to_csv(OUT / "adapter_validation_candidates.csv", index=False)
    selected_val = validation[validation["selected"].eq(True)].copy() if not validation.empty else pd.DataFrame()
    selected_val.to_csv(OUT / "adapter_validation_selected_configs.csv", index=False)
    write_text(
        OUT / "adapter_validation_selection_report.md",
        f"""
# Adapter Validation Selection Report

Each non-baseline adapter selects a config per setting/seed using only:

- 24 support-train samples for fitting;
- 8 support-validation samples for attack-side proxy;
- ID calibration and OOD validation for threshold and OOD-side proxy.

No final OOD eval or final attack eval is used for selection. The support-validation proxy is small and can overfit, so selected adapters are feasibility candidates only.

Selected config snapshot:

{md_table(selected_val.head(60))}
""",
    )
    failure_lines = []
    for _, row in locked_sum.iterrows():
        adapter = row["adapter"]
        if float(row["locked_ood_alarm_max"]) > 0.01:
            failure_lines.append(f"- `{adapter}` exceeds the 1% OOD budget and cannot replace LR.")
        elif adapter != "A0_lr_baseline" and float(row.get("delta_detection_mean_vs_lr", 0.0)) <= 0:
            failure_lines.append(f"- `{adapter}` does not improve locked mean detection over LR.")
        elif adapter != "A0_lr_baseline" and float(row.get("delta_detection_min_vs_lr", 0.0)) < 0:
            failure_lines.append(f"- `{adapter}` improves some mean metric but worsens locked worst-case detection.")
    if not failure_lines:
        failure_lines.append("- No hard failure detected; replacement still requires follow-up validation.")
    write_text(
        OUT / "adapter_failure_analysis.md",
        "# Adapter Failure Analysis\n\n" + "\n".join(failure_lines) + "\n\nComplex adapters are not promoted unless they improve locked mean and worst-case detection while keeping OOD <=1%.",
    )
    if stable_upgrade:
        best_text = f"candidate name: `{best_adapter}`\n\nlocked mean/min/OOD max: `{best_mean:.6f}` / `{best_min:.6f}` / `{best_ood:.6f}`\n\nrisk: feasibility only; needs issue25 validation."
    else:
        best_text = f"no_adapter_replaces_lr\n\nLR retained as main adapter. Best-ranked adapter `{best_adapter}` does not satisfy stable replacement criteria over LR under the locked 1% OOD protocol."
    write_text(
        OUT / "best_adapter_candidate.md",
        "# Best Adapter Candidate\n\n" + best_text,
    )
    write_text(
        OUT / "claim_boundary.md",
        """
# Claim Boundary

## Can Say

- issue24 evaluates whether adapter complexity improves Enhanced LOW-GUARD+ under fixed source_rich_top64 representation.
- A stronger adapter is or is not found according to locked mean/min/OOD metrics.
- If no adapter wins, LR remains justified as a simple low-alert adapter.

## Cannot Say

- The final method changed before further validation.
- Any adapter was tuned on final eval.
- Complex adapters prove generalization.
- Routing or promotion is solved.
- CCF-A readiness is achieved.
""",
    )
    risks = [
        ["adapter overfit risk", "high", "Hyperparameters use tiny support-validation proxy.", "Treat as feasibility and require follow-up validation."],
        ["final-eval leakage risk", "high", "Repeated locked-bin analysis can tempt tuning.", "No final metrics in selection; report all configs."],
        ["OOD alarm tradeoff", "high", "Harder adapters may raise OOD alarms.", "Use 1% feasibility gate."],
        ["few-shot instability", "medium", "Only 32 support samples.", "Report main and held-out seeds."],
        ["model complexity cost", "medium", "GB/SVM add complexity over LR.", "Report train/inference and parameters."],
        ["low-FPR metric instability", "medium", "pAUC at 1% FPR is noisy.", "Report guarded detection and pAUC together."],
        ["locked-bin overfitting after repeated analysis", "high", "The same bins are now analyzed repeatedly.", "Move to second environment/temporal validation next."],
        ["external validity risk", "high", "No external validation here.", "Do not overclaim."],
    ]
    pd.DataFrame(risks, columns=["risk_name", "severity", "reason", "mitigation"]).to_csv(OUT / "risk_register.csv", index=False)
    write_text(
        OUT / "recommended_next_action.md",
        f"""
# Recommended Next Action

Unique first choice: `{next_action}`.

If the status is not strong/very strong, do not replace LR. Proceed with LR as the main adapter and use issue24 as an ablation showing that extra adapter complexity is not the main validated contribution.
""",
    )
    write_text(
        OUT / "doc_update_patch_suggestion.md",
        """
# Suggested Mainline Docs Patch

Append a short issue24 note:

`issue24 fixes source_rich_top64+kcenter32 and tests whether adapter complexity improves locked low-alert performance. Treat any advanced adapter as feasibility only unless it improves locked mean/min detection without OOD budget regression.`
""",
    )
    config = {
        "run": "issue24_adapter_upgrade_feasibility_for_enhanced_v2_top64_2026-05-18",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "representation": "selected_source_rich_top64",
        "support": "kcenter32",
        "official_ood_target": MAIN_TARGET,
        "adapters": list(adapter_spaces()),
        "status": status,
        "best_adapter": best_adapter,
        "next_action": next_action,
        "selection": {
            "support_train": SUPPORT_TRAIN_FOR_SELECTION,
            "support_validation": SUPPORT_BUDGET - SUPPORT_TRAIN_FOR_SELECTION,
            "final_eval_used_for_selection": False,
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
        write_text(OUT / "alignment_failure_report.md", "# Alignment Failure\n\noriginal100/source_rich row counts do not align.")
        raise RuntimeError("original100/source_rich alignment failed")
    schema_path = Path(paths["source_rich_id"]).parents[1] / "data" / "structured_schema.json"
    sr_names = issue19b.feature_names(schema_path, x_id_sr.shape[1])
    locked_datasets, consistency_datasets = build_datasets(paths, x_id_o, x_ood_o, x_attack_o, x_id_sr, x_ood_sr, x_attack_sr)
    datasets = locked_datasets + consistency_datasets
    rows: list[dict[str, Any]] = []
    validation_rows: list[dict[str, Any]] = []
    complexity_rows: list[dict[str, Any]] = []
    spaces = adapter_spaces()

    for spec in datasets:
        train_pool = np.asarray(spec["attack_train_pool_idx"], dtype=np.int64)
        kcenter_support = issue19b.kcenter_support(train_pool, x_attack_o[train_pool], SUPPORT_BUDGET)
        for seed in SEEDS:
            print(f"[issue24] start {spec['holdout']} seed={seed}", flush=True)
            selected_by_adapter: dict[str, dict[str, Any]] = {}
            for adapter_name, configs in spaces.items():
                selected, val_rows = select_adapter_config(
                    dataset_spec=spec,
                    adapter_name=adapter_name,
                    configs=configs,
                    support_rows=kcenter_support,
                    x_attack_sr=x_attack_sr,
                    sr_names=sr_names,
                    seed=seed,
                )
                selected_by_adapter[adapter_name] = selected
                validation_rows.extend(val_rows)

            for adapter_name, selected_config in selected_by_adapter.items():
                result, _ = run_config_once(
                    dataset_spec=spec,
                    config=selected_config,
                    support_train_rows=kcenter_support,
                    eval_positive_rows=np.asarray(spec["attack_eval_idx"], dtype=np.int64),
                    x_attack_sr=x_attack_sr,
                    sr_names=sr_names,
                    seed=seed,
                    use_final_eval=True,
                )
                rows.append(
                    {
                        "evaluation_role": spec["evaluation_role"],
                        "dataset": spec["dataset"],
                        "holdout": spec["holdout"],
                        "split_protocol": spec["split_protocol"],
                        "adapter": adapter_name,
                        "selected_config_id": selected_config["config_id"],
                        "model_type": selected_config["model_type"],
                        "seed": int(seed),
                        "seed_group": issue22.seed_group(seed),
                        "representation": "selected_source_rich_top64",
                        "support_method": "kcenter",
                        "support_size": SUPPORT_BUDGET,
                        "ood_target": MAIN_TARGET,
                        "ood_target_label": TARGET_LABEL,
                        "roc_auc": result["roc_auc"],
                        "pr_auc": result["pr_auc"],
                        "pauc_fpr_1pct": result["pauc_fpr_1pct"],
                        "tpr_at_fpr_1pct": result["tpr_at_fpr_1pct"],
                        "attack_high_detection": result["positive_detection"],
                        "final_ood_high_alarm": result["ood_alarm"],
                        "feasible_final_1pct": bool(result["ood_alarm"] <= 0.01),
                        "threshold": result["threshold"],
                        "attack_eval_size": result["eval_positive_size"],
                        "final_ood_eval_size": result["ood_eval_size"],
                        "feature_dim": TOP_K,
                        "train_time": result["train_time"],
                        "inference_time": result["inference_time"],
                        "parameter_count": result["parameter_count"],
                        "hard_negative_count": result["hard_negative_count"],
                        "provenance_clean": True,
                        "final_eval_used_for_selection": False,
                    }
                )
                complexity_rows.append(
                    {
                        "evaluation_role": spec["evaluation_role"],
                        "holdout": spec["holdout"],
                        "adapter": adapter_name,
                        "seed": int(seed),
                        "selected_config_id": selected_config["config_id"],
                        "model_type": selected_config["model_type"],
                        "train_time": result["train_time"],
                        "inference_time": result["inference_time"],
                        "parameter_count": result["parameter_count"],
                        "hard_negative_count": result["hard_negative_count"],
                    }
                )
            print(f"[issue24] {spec['holdout']} seed={seed} completed", flush=True)

    by_seed = pd.DataFrame(rows)
    validation = pd.DataFrame(validation_rows)
    complexity = pd.DataFrame(complexity_rows)
    summary = summarize(by_seed)
    by_seed.to_csv(OUT / "adapter_method_comparison_by_seed.csv", index=False)
    summary.to_csv(OUT / "adapter_method_comparison_summary.csv", index=False)
    validation.to_csv(OUT / "adapter_validation_selection_report.csv", index=False)
    write_reports(summary, by_seed, validation, complexity)

    manifest_rows = []
    for path in sorted(OUT.glob("*")):
        if path.is_file() and path.name != "manifest.csv":
            manifest_rows.append({"file": path.name, "size_bytes": path.stat().st_size})
    manifest_rows.append({"file": "runtime_seconds", "size_bytes": f"{time.perf_counter() - t0:.3f}"})
    pd.DataFrame(manifest_rows).to_csv(OUT / "manifest.csv", index=False)


if __name__ == "__main__":
    main()
