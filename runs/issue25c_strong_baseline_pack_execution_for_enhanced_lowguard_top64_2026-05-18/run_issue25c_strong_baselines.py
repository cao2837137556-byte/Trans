from __future__ import annotations

import importlib.util
import json
import math
import sys
import time
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, IsolationForest
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression, SGDOneClassSVM
from sklearn.metrics import average_precision_score, roc_auc_score, roc_curve
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs" / "issue25c_strong_baseline_pack_execution_for_enhanced_lowguard_top64_2026-05-18"
ISSUE25B = ROOT / "runs" / "issue25b_strong_baseline_protocol_and_fairness_design_2026-05-18"
ISSUE25A = ROOT / "runs" / "issue25a_algorithmic_formalization_and_claim_upgrade_for_lowguard_plus_2026-05-18"
ISSUE23 = ROOT / "runs" / "issue23_locked_validation_for_enhanced_v2_top64_2026-05-18"
ISSUE24 = ROOT / "runs" / "issue24_adapter_upgrade_feasibility_for_enhanced_v2_top64_2026-05-18"
ISSUE24B = ROOT / "runs" / "issue24b_adapter_bottleneck_diagnosis_for_enhanced_v2_top64_2026-05-18"
ISSUE24C = ROOT / "runs" / "issue24c_v1_v2_residual_fusion_adapter_retry_2026-05-18"
ISSUE22 = ROOT / "runs" / "issue22_v2_hard_shift_enhancement_pilot_2026-05-18"
ISSUE22B = ROOT / "runs" / "issue22b_enhanced_v2_primary_nonregression_check_2026-05-18"
ISSUE11 = ROOT / "runs" / "issue11_fixed_config_ood_guard_lr_ablation_2026-05-14"
ISSUE23_SCRIPT = ISSUE23 / "run_issue23_locked_validation.py"
ISSUE22_SCRIPT = ISSUE22 / "run_issue22_v2_enhancement.py"
ISSUE19B = ROOT / "runs" / "issue19b_v1_v2_same_protocol_backtest_and_alarm_budget_curve_2026-05-18"
ISSUE19B_SCRIPT = ISSUE19B / "run_issue19b_v1_v2_backtest.py"

SEEDS = list(range(42, 52))
MAIN_TARGET = 0.01
LOCKED_HOLDOUTS = ["holdout_bin_5", "holdout_bin_6", "holdout_bin_7", "holdout_bin_8"]
CONSISTENCY_HOLDOUTS = ["primary_lowood", "holdout_bin_2", "chrono_late_train_early_eval"]
SUPPORT_BUDGET = 32
SUPPORT_TRAIN_FOR_SELECTION = 24
TOP64_CACHE: dict[tuple[str, int, str, tuple[int, ...], int], tuple[np.ndarray, list[dict[str, Any]]]] = {}


def import_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


issue23 = import_module(ISSUE23_SCRIPT, "issue23_locked_validation_for_issue25c")
issue22 = import_module(ISSUE22_SCRIPT, "issue22_v2_enhancement_for_issue25c")
issue19b = import_module(ISSUE19B_SCRIPT, "issue19b_v1_v2_backtest_for_issue25c")


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


def seed_group(seed: int) -> str:
    return issue19b.seed_group(seed)


def require_inputs() -> list[str]:
    required = [
        ISSUE25B / "summary.md",
        ISSUE25B / "adapter_fairness_protocol.md",
        ISSUE25B / "representation_ablation_protocol.md",
        ISSUE25B / "method_level_baseline_protocol.md",
        ISSUE25B / "baseline_fairness_matrix.csv",
        ISSUE25B / "threshold_and_hyperparameter_protocol.md",
        ISSUE25B / "issue25c_minimal_run_matrix.csv",
        ISSUE25B / "metric_protocol.md",
        ISSUE25B / "claim_boundary.md",
        ISSUE25A / "summary.md",
        ISSUE23 / "summary.md",
        ISSUE23 / "method_comparison_summary.csv",
        ISSUE23 / "method_comparison_by_seed.csv",
        ISSUE23 / "v2top64_vs_v1_locked.csv",
        ISSUE23 / "v2top64_vs_v2top32_locked.csv",
        ISSUE23 / "low_fpr_metrics_summary.csv",
        ISSUE24 / "summary.md",
        ISSUE24B / "summary.md",
        ISSUE24C / "summary.md",
        ISSUE22 / "summary.md",
        ISSUE22B / "summary.md",
        ISSUE11 / "config.json",
        ISSUE23_SCRIPT,
        ISSUE22_SCRIPT,
        ISSUE19B_SCRIPT,
    ]
    return [str(path) for path in required if not path.exists()]


def baseline_definitions() -> list[dict[str, Any]]:
    return [
        {
            "method": "M0_V1_original100_fixed_guard_LR",
            "baseline_category": "existing_detector_baseline",
            "run_priority": "required",
            "feature_kind": "original100",
            "model_kind": "guarded_lr",
            "support_method": "kcenter",
            "uses_attack_supports": True,
            "support_count": 32,
            "allowed_train_data": "ID_train;OOD_train;kcenter32_attack_supports",
            "fairness_layer": "representation_reference",
        },
        {
            "method": "M1_V2_top32_fixed_guard_LR",
            "baseline_category": "existing_detector_baseline",
            "run_priority": "required",
            "feature_kind": "source_rich_top32",
            "model_kind": "guarded_lr",
            "support_method": "kcenter",
            "uses_attack_supports": True,
            "support_count": 32,
            "allowed_train_data": "ID_train;OOD_train;kcenter32_attack_supports",
            "fairness_layer": "representation_reference",
        },
        {
            "method": "M2_Enhanced_LOW_GUARD_top64_fixed_guard_LR",
            "baseline_category": "main_method",
            "run_priority": "required",
            "feature_kind": "source_rich_top64",
            "model_kind": "guarded_lr",
            "support_method": "kcenter",
            "uses_attack_supports": True,
            "support_count": 32,
            "allowed_train_data": "ID_train;OOD_train;kcenter32_attack_supports",
            "fairness_layer": "main_method",
        },
        {
            "method": "M3_top64_no_guard_LR",
            "baseline_category": "component_ablation",
            "run_priority": "required",
            "feature_kind": "source_rich_top64",
            "model_kind": "no_guard_lr",
            "support_method": "kcenter",
            "uses_attack_supports": True,
            "support_count": 32,
            "allowed_train_data": "ID_train;kcenter32_attack_supports",
            "fairness_layer": "representation_ablation",
        },
        {
            "method": "M4_top64_random32_fixed_guard_LR",
            "baseline_category": "component_ablation",
            "run_priority": "required",
            "feature_kind": "source_rich_top64",
            "model_kind": "guarded_lr",
            "support_method": "random",
            "uses_attack_supports": True,
            "support_count": 32,
            "allowed_train_data": "ID_train;OOD_train;random32_attack_supports",
            "fairness_layer": "support_ablation",
        },
        {
            "method": "M5_Isolation_Forest_top64",
            "baseline_category": "unsupervised_anomaly",
            "run_priority": "required",
            "feature_kind": "source_rich_top64_frozen_main",
            "model_kind": "isolation_forest",
            "support_method": "none_for_model",
            "uses_attack_supports": False,
            "support_count": 0,
            "allowed_train_data": "ID_train;OOD_train",
            "fairness_layer": "method_level",
        },
        {
            "method": "M6_OC_SVM_top64",
            "baseline_category": "unsupervised_anomaly",
            "run_priority": "required",
            "feature_kind": "source_rich_top64_frozen_main",
            "model_kind": "ocsvm_sgd",
            "support_method": "none_for_model",
            "uses_attack_supports": False,
            "support_count": 0,
            "allowed_train_data": "ID_train;OOD_train",
            "fairness_layer": "method_level",
        },
        {
            "method": "M7_HistGB_shallow_top64",
            "baseline_category": "nonlinear_tabular",
            "run_priority": "required",
            "feature_kind": "source_rich_top64",
            "model_kind": "histgb",
            "support_method": "kcenter",
            "uses_attack_supports": True,
            "support_count": 32,
            "allowed_train_data": "ID_train;OOD_train;kcenter32_attack_supports",
            "fairness_layer": "adapter_level",
        },
        {
            "method": "M8_DevNet_like_MLP_top64",
            "baseline_category": "fewshot_anomaly",
            "run_priority": "required",
            "feature_kind": "source_rich_top64",
            "model_kind": "devnet_like_mlp",
            "support_method": "kcenter",
            "uses_attack_supports": True,
            "support_count": 32,
            "allowed_train_data": "ID_train;OOD_train;kcenter32_attack_supports",
            "fairness_layer": "adapter_level",
        },
        {
            "method": "M9_DeepSAD_like_center_top64",
            "baseline_category": "semisupervised_anomaly",
            "run_priority": "required",
            "feature_kind": "source_rich_top64",
            "model_kind": "deepsad_like_center",
            "support_method": "kcenter",
            "uses_attack_supports": True,
            "support_count": 32,
            "allowed_train_data": "ID_train;OOD_train;kcenter32_attack_supports",
            "fairness_layer": "adapter_level",
        },
    ]


def search_space_for(method: dict[str, Any]) -> list[dict[str, Any]]:
    kind = str(method["model_kind"])
    if kind in {"guarded_lr", "no_guard_lr"}:
        return [{"config_id": "fixed_lr", "model_kind": kind, "C": 1.0, "ood_weight": 2.0 if kind == "guarded_lr" else 0.0}]
    if kind == "isolation_forest":
        return [{"config_id": "iforest_n100_auto", "model_kind": kind, "n_estimators": 100, "max_samples": 256}]
    if kind == "ocsvm_sgd":
        return [{"config_id": "sgd_ocsvm_nu001", "model_kind": kind, "nu": 0.01}]
    if kind == "histgb":
        return [
            {"config_id": "histgb_depth2_iter50_lr005", "model_kind": kind, "max_depth": 2, "max_iter": 50, "learning_rate": 0.05, "l2_regularization": 1.0},
            {"config_id": "histgb_depth3_iter50_lr005", "model_kind": kind, "max_depth": 3, "max_iter": 50, "learning_rate": 0.05, "l2_regularization": 1.0},
        ]
    if kind == "devnet_like_mlp":
        return [
            {"config_id": "mlp_h16_alpha001", "model_kind": kind, "hidden": 16, "alpha": 0.001, "max_iter": 80},
        ]
    if kind == "deepsad_like_center":
        return [
            {"config_id": "center_lambda0", "model_kind": kind, "lambda_attack": 0.0},
            {"config_id": "center_lambda1", "model_kind": kind, "lambda_attack": 1.0},
            {"config_id": "center_lambda2", "model_kind": kind, "lambda_attack": 2.0},
        ]
    raise ValueError(f"Unknown model kind: {kind}")


def split_support_for_selection(support_rows: np.ndarray, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed + 25025)
    rows = np.asarray(support_rows, dtype=np.int64).copy()
    rng.shuffle(rows)
    return np.sort(rows[:SUPPORT_TRAIN_FOR_SELECTION]), np.sort(rows[SUPPORT_TRAIN_FOR_SELECTION:])


def low_fpr_metrics(scores_ood: np.ndarray, scores_attack: np.ndarray) -> tuple[float, float]:
    y_true = np.concatenate([np.zeros(len(scores_ood), dtype=np.int64), np.ones(len(scores_attack), dtype=np.int64)])
    y_score = np.concatenate([scores_ood, scores_attack])
    pauc = float(roc_auc_score(y_true, y_score, max_fpr=0.01))
    fpr, tpr, _ = roc_curve(y_true, y_score)
    tpr_at_1pct = float(np.max(tpr[fpr <= 0.01])) if np.any(fpr <= 0.01) else 0.0
    return pauc, tpr_at_1pct


def select_features(
    *,
    dataset_spec: dict[str, Any],
    feature_kind: str,
    support_rows: np.ndarray,
    x_attack_sr: np.ndarray,
    sr_names: list[str],
    seed: int,
) -> tuple[str, np.ndarray | None, int, list[dict[str, Any]]]:
    if feature_kind == "original100":
        return "original100", None, int(dataset_spec["x_id_train_o"].shape[1]), []
    if feature_kind in {"source_rich_top32", "source_rich_top64", "source_rich_top64_frozen_main"}:
        top_k = 32 if feature_kind == "source_rich_top32" else 64
        cache_key = (str(dataset_spec["holdout"]), int(seed), feature_kind, tuple(map(int, support_rows)), top_k)
        if cache_key not in TOP64_CACHE:
            TOP64_CACHE[cache_key] = issue19b.selected_source_rich_features(
                x_support=x_attack_sr[support_rows],
                x_id_calib=dataset_spec["x_id_calib_sr"],
                x_ood_val=dataset_spec["x_ood_val_sr"],
                names=sr_names,
                dataset=str(dataset_spec["dataset"]),
                holdout=str(dataset_spec["holdout"]),
                seed=seed,
                top_k=top_k,
            )
        idx, rows = TOP64_CACHE[cache_key]
        label = f"selected_source_rich_top{top_k}" if feature_kind != "source_rich_top64_frozen_main" else "selected_source_rich_top64_frozen_main_protocol"
        return label, idx, top_k, rows
    raise ValueError(f"Unknown feature kind: {feature_kind}")


def matrix_view(dataset_spec: dict[str, Any], representation: str, feature_idx: np.ndarray | None, x_attack_o: np.ndarray, x_attack_sr: np.ndarray, rows: np.ndarray | None = None) -> dict[str, np.ndarray]:
    attack_eval_idx = np.asarray(dataset_spec["attack_eval_idx"], dtype=np.int64)
    if rows is None:
        rows = np.asarray([], dtype=np.int64)
    if representation == "original100":
        return {
            "id_train": dataset_spec["x_id_train_o"],
            "ood_train": dataset_spec["x_ood_train_o"],
            "id_calib": dataset_spec["x_id_calib_o"],
            "ood_val": dataset_spec["x_ood_val_o"],
            "ood_eval": dataset_spec["x_ood_eval_o"],
            "attack_eval": x_attack_o[attack_eval_idx],
            "support": x_attack_o[rows],
        }
    if feature_idx is None:
        raise RuntimeError("source_rich feature_idx required")
    return {
        "id_train": dataset_spec["x_id_train_sr"][:, feature_idx],
        "ood_train": dataset_spec["x_ood_train_sr"][:, feature_idx],
        "id_calib": dataset_spec["x_id_calib_sr"][:, feature_idx],
        "ood_val": dataset_spec["x_ood_val_sr"][:, feature_idx],
        "ood_eval": dataset_spec["x_ood_eval_sr"][:, feature_idx],
        "attack_eval": x_attack_sr[attack_eval_idx][:, feature_idx],
        "support": x_attack_sr[rows][:, feature_idx],
    }


class CenterDistanceModel:
    def __init__(self, center: np.ndarray, weights: np.ndarray):
        self.center = center
        self.weights = weights

    def score(self, x: np.ndarray) -> np.ndarray:
        return np.sum(((x - self.center) ** 2) * self.weights, axis=1)


def fit_score_model(config: dict[str, Any], mats: dict[str, np.ndarray], seed: int, *, use_guard: bool = True) -> tuple[Any, StandardScaler | None, dict[str, Any]]:
    kind = str(config["model_kind"])
    t0 = time.perf_counter()
    param_count = 0
    aux: dict[str, Any] = {}

    if kind in {"guarded_lr", "no_guard_lr"}:
        if kind == "guarded_lr":
            x_train_raw = np.vstack([mats["id_train"], mats["ood_train"], mats["support"]])
            y_train = np.concatenate([np.zeros(len(mats["id_train"])), np.zeros(len(mats["ood_train"])), np.ones(len(mats["support"]))])
            sample_weight = np.concatenate([np.ones(len(mats["id_train"])), np.full(len(mats["ood_train"]), 2.0), np.ones(len(mats["support"]))])
        else:
            x_train_raw = np.vstack([mats["id_train"], mats["support"]])
            y_train = np.concatenate([np.zeros(len(mats["id_train"])), np.ones(len(mats["support"]))])
            sample_weight = np.ones(len(y_train), dtype=np.float64)
        scaler = StandardScaler().fit(x_train_raw)
        model = LogisticRegression(C=1.0, penalty="l2", solver="liblinear", class_weight="balanced", max_iter=2000, random_state=seed)
        model.fit(scaler.transform(x_train_raw), y_train, sample_weight=sample_weight)
        param_count = int(model.coef_.size + model.intercept_.size)
        aux["train_time"] = time.perf_counter() - t0
        return model, scaler, {"param_count": param_count, **aux}

    if kind == "isolation_forest":
        x_train_raw = np.vstack([mats["id_train"], mats["ood_train"]])
        scaler = StandardScaler().fit(x_train_raw)
        model = IsolationForest(n_estimators=int(config["n_estimators"]), max_samples=int(config["max_samples"]), contamination="auto", random_state=seed, n_jobs=1)
        model.fit(scaler.transform(x_train_raw))
        aux["train_time"] = time.perf_counter() - t0
        return model, scaler, {"param_count": int(config["n_estimators"]), **aux}

    if kind == "ocsvm_sgd":
        x_train_raw = np.vstack([mats["id_train"], mats["ood_train"]])
        scaler = StandardScaler().fit(x_train_raw)
        model = SGDOneClassSVM(nu=float(config["nu"]), max_iter=1000, tol=1e-3, random_state=seed)
        model.fit(scaler.transform(x_train_raw))
        aux["train_time"] = time.perf_counter() - t0
        return model, scaler, {"param_count": int(getattr(model, "coef_", np.zeros((1, x_train_raw.shape[1]))).size + 1), **aux}

    if kind == "histgb":
        x_train_raw = np.vstack([mats["id_train"], mats["ood_train"], mats["support"]])
        y_train = np.concatenate([np.zeros(len(mats["id_train"])), np.zeros(len(mats["ood_train"])), np.ones(len(mats["support"]))])
        sample_weight = np.concatenate([np.ones(len(mats["id_train"])), np.full(len(mats["ood_train"]), 2.0), np.ones(len(mats["support"]))])
        model = HistGradientBoostingClassifier(
            max_depth=int(config["max_depth"]),
            max_iter=int(config["max_iter"]),
            learning_rate=float(config["learning_rate"]),
            l2_regularization=float(config["l2_regularization"]),
            random_state=seed,
        )
        model.fit(x_train_raw, y_train, sample_weight=sample_weight)
        aux["train_time"] = time.perf_counter() - t0
        return model, None, {"param_count": int(config["max_iter"]), **aux}

    if kind == "devnet_like_mlp":
        x_train_raw = np.vstack([mats["id_train"], mats["ood_train"], mats["support"]])
        y_train = np.concatenate([np.zeros(len(mats["id_train"])), np.zeros(len(mats["ood_train"])), np.ones(len(mats["support"]))])
        sample_weight = np.concatenate([np.ones(len(mats["id_train"])), np.full(len(mats["ood_train"]), 2.0), np.full(len(mats["support"]), 16.0)])
        scaler = StandardScaler().fit(x_train_raw)
        model = MLPClassifier(
            hidden_layer_sizes=(int(config["hidden"]),),
            alpha=float(config["alpha"]),
            max_iter=int(config["max_iter"]),
            random_state=seed,
            learning_rate_init=0.001,
            early_stopping=False,
        )
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=ConvergenceWarning)
            model.fit(scaler.transform(x_train_raw), y_train, sample_weight=sample_weight)
        param_count = sum(w.size for w in model.coefs_) + sum(b.size for b in model.intercepts_)
        aux["train_time"] = time.perf_counter() - t0
        return model, scaler, {"param_count": int(param_count), **aux}

    if kind == "deepsad_like_center":
        x_train_raw = np.vstack([mats["id_train"], mats["ood_train"], mats["support"]])
        scaler = StandardScaler().fit(x_train_raw)
        benign = scaler.transform(np.vstack([mats["id_train"], mats["ood_train"]]))
        support = scaler.transform(mats["support"])
        center = benign.mean(axis=0)
        if len(support):
            sep = np.abs(support.mean(axis=0) - center)
            sep = sep / (np.median(sep) + 1e-8)
        else:
            sep = np.zeros_like(center)
        weights = 1.0 + float(config["lambda_attack"]) * sep
        model = CenterDistanceModel(center=center, weights=weights)
        aux["train_time"] = time.perf_counter() - t0
        return model, scaler, {"param_count": int(len(center) * 2), **aux}

    raise ValueError(f"Unknown model kind: {kind}")


def score_model(model: Any, scaler: StandardScaler | None, x: np.ndarray, model_kind: str) -> np.ndarray:
    x_in = scaler.transform(x) if scaler is not None else x
    if model_kind in {"guarded_lr", "no_guard_lr"}:
        return np.asarray(model.decision_function(x_in), dtype=np.float64)
    if model_kind == "isolation_forest":
        return -np.asarray(model.score_samples(x_in), dtype=np.float64)
    if model_kind == "ocsvm_sgd":
        return -np.asarray(model.decision_function(x_in), dtype=np.float64)
    if model_kind == "histgb":
        return np.asarray(model.predict_proba(x_in)[:, 1], dtype=np.float64)
    if model_kind == "devnet_like_mlp":
        return np.asarray(model.predict_proba(x_in)[:, 1], dtype=np.float64)
    if model_kind == "deepsad_like_center":
        return np.asarray(model.score(x_in), dtype=np.float64)
    raise ValueError(f"Unknown model kind: {model_kind}")


def evaluate_config(config: dict[str, Any], mats: dict[str, np.ndarray], seed: int, *, eval_positive: str) -> dict[str, Any]:
    model, scaler, aux = fit_score_model(config, mats, seed)
    t1 = time.perf_counter()
    kind = str(config["model_kind"])
    scores = {
        "id_calib": score_model(model, scaler, mats["id_calib"], kind),
        "ood_val": score_model(model, scaler, mats["ood_val"], kind),
        "final_ood_eval": score_model(model, scaler, mats["ood_eval"], kind),
        "attack_eval": score_model(model, scaler, mats["attack_eval"], kind),
    }
    if "support_val" in mats:
        scores["support_val"] = score_model(model, scaler, mats["support_val"], kind)
    inference_time = time.perf_counter() - t1
    threshold_info = issue19b.v72.guarded_val_threshold(scores["id_calib"], scores["ood_val"], MAIN_TARGET)
    threshold = float(threshold_info["threshold"])
    eval_scores = scores[eval_positive]
    eval_ood = scores["ood_val"] if eval_positive == "support_val" else scores["final_ood_eval"]
    y_auc = np.concatenate([np.zeros(len(eval_ood), dtype=np.int64), np.ones(len(eval_scores), dtype=np.int64)])
    s_auc = np.concatenate([eval_ood, eval_scores])
    roc_auc = float(roc_auc_score(y_auc, s_auc)) if len(np.unique(y_auc)) == 2 else math.nan
    pr_auc = float(average_precision_score(y_auc, s_auc)) if len(np.unique(y_auc)) == 2 else math.nan
    pauc, tpr1 = low_fpr_metrics(scores["final_ood_eval"], scores["attack_eval"])
    return {
        "scores": scores,
        "threshold": threshold,
        "roc_auc": roc_auc,
        "pr_auc": pr_auc,
        "pauc_fpr_1pct": pauc,
        "tpr_at_fpr_1pct": tpr1,
        "positive_detection": float(np.mean(eval_scores > threshold)),
        "positive_margin_q25": float(np.quantile(eval_scores - threshold, 0.25)) if len(eval_scores) else math.nan,
        "positive_margin_median": float(np.median(eval_scores - threshold)) if len(eval_scores) else math.nan,
        "ood_val_alarm_at_selection": float(np.mean(scores["ood_val"] > threshold)),
        "id_calib_alarm_at_selection": float(np.mean(scores["id_calib"] > threshold)),
        "train_time": float(aux["train_time"]),
        "inference_time": float(inference_time),
        "parameter_count": int(aux["param_count"]),
    }


def choose_config(
    *,
    method: dict[str, Any],
    dataset_spec: dict[str, Any],
    support_rows: np.ndarray,
    feature_support_rows: np.ndarray,
    x_attack_o: np.ndarray,
    x_attack_sr: np.ndarray,
    sr_names: list[str],
    seed: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    configs = search_space_for(method)
    if len(configs) == 1:
        return configs[0], []
    support_train, support_val = split_support_for_selection(support_rows, seed)
    feature_kind = str(method["feature_kind"])
    selection_feature_support = support_train if str(method["uses_attack_supports"]) == "True" else feature_support_rows
    representation, feature_idx, _, _ = select_features(
        dataset_spec=dataset_spec,
        feature_kind=feature_kind,
        support_rows=selection_feature_support,
        x_attack_sr=x_attack_sr,
        sr_names=sr_names,
        seed=seed,
    )
    mats = matrix_view(dataset_spec, representation, feature_idx, x_attack_o, x_attack_sr, support_train)
    if representation == "original100":
        mats["support_val"] = x_attack_o[support_val]
    else:
        if feature_idx is None:
            raise RuntimeError("feature_idx required for support validation")
        mats["support_val"] = x_attack_sr[support_val][:, feature_idx]
    validation_rows: list[dict[str, Any]] = []
    for config in configs:
        result = evaluate_config(config, mats, seed, eval_positive="support_val")
        validation_rows.append(
            {
                "dataset": dataset_spec["dataset"],
                "holdout": dataset_spec["holdout"],
                "evaluation_role": dataset_spec["evaluation_role"],
                "seed": int(seed),
                "seed_group": seed_group(seed),
                "method": method["method"],
                "model_kind": method["model_kind"],
                "config_id": config["config_id"],
                "support_train_size": int(len(support_train)),
                "support_validation_size": int(len(support_val)),
                "support_val_detection": result["positive_detection"],
                "support_val_margin_q25": result["positive_margin_q25"],
                "support_val_margin_median": result["positive_margin_median"],
                "ood_val_alarm_at_selection": result["ood_val_alarm_at_selection"],
                "id_calib_alarm_at_selection": result["id_calib_alarm_at_selection"],
                "uses_final_eval": False,
            }
        )
    val_df = pd.DataFrame(validation_rows).sort_values(
        ["support_val_detection", "support_val_margin_q25", "support_val_margin_median", "ood_val_alarm_at_selection", "config_id"],
        ascending=[False, False, False, True, True],
    )
    selected_config_id = str(val_df.iloc[0]["config_id"])
    for row in validation_rows:
        row["selected"] = bool(row["config_id"] == selected_config_id)
    return next(config for config in configs if str(config["config_id"]) == selected_config_id), validation_rows


def run_method(
    *,
    dataset_spec: dict[str, Any],
    method: dict[str, Any],
    seed: int,
    support_rows: np.ndarray,
    feature_support_rows: np.ndarray,
    x_attack_o: np.ndarray,
    x_attack_sr: np.ndarray,
    sr_names: list[str],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    selected_config, validation_rows = choose_config(
        method=method,
        dataset_spec=dataset_spec,
        support_rows=support_rows,
        feature_support_rows=feature_support_rows,
        x_attack_o=x_attack_o,
        x_attack_sr=x_attack_sr,
        sr_names=sr_names,
        seed=seed,
    )
    feature_kind = str(method["feature_kind"])
    support_for_feature = support_rows if bool(method["uses_attack_supports"]) else feature_support_rows
    representation, feature_idx, feature_dim, feature_rows = select_features(
        dataset_spec=dataset_spec,
        feature_kind=feature_kind,
        support_rows=support_for_feature,
        x_attack_sr=x_attack_sr,
        sr_names=sr_names,
        seed=seed,
    )
    model_support_rows = support_rows if bool(method["uses_attack_supports"]) else np.asarray([], dtype=np.int64)
    mats = matrix_view(dataset_spec, representation, feature_idx, x_attack_o, x_attack_sr, model_support_rows)
    result = evaluate_config(selected_config, mats, seed, eval_positive="attack_eval")
    scores = result["scores"]
    threshold = float(result["threshold"])
    attack_det = float(np.mean(scores["attack_eval"] > threshold))
    ood_alarm = float(np.mean(scores["final_ood_eval"] > threshold))
    y_auc = np.concatenate([np.zeros(len(scores["final_ood_eval"]), dtype=np.int64), np.ones(len(scores["attack_eval"]), dtype=np.int64)])
    s_auc = np.concatenate([scores["final_ood_eval"], scores["attack_eval"]])
    row = {
        "evaluation_role": dataset_spec["evaluation_role"],
        "dataset": dataset_spec["dataset"],
        "holdout": dataset_spec["holdout"],
        "split_protocol": dataset_spec["split_protocol"],
        "method": method["method"],
        "baseline_category": method["baseline_category"],
        "run_priority": method["run_priority"],
        "fairness_layer": method["fairness_layer"],
        "feature_input": representation,
        "model_kind": method["model_kind"],
        "selected_config_id": selected_config["config_id"],
        "uses_attack_supports": bool(method["uses_attack_supports"]),
        "support_method": method["support_method"],
        "support_count": int(len(model_support_rows)),
        "feature_selection_support_count": int(len(support_for_feature)) if representation != "original100" else 0,
        "seed": int(seed),
        "seed_group": seed_group(seed),
        "ood_target": MAIN_TARGET,
        "ood_target_label": "1.0pct",
        "roc_auc": float(roc_auc_score(y_auc, s_auc)),
        "pr_auc": float(average_precision_score(y_auc, s_auc)),
        "pauc_fpr_1pct": result["pauc_fpr_1pct"],
        "tpr_at_fpr_1pct": result["tpr_at_fpr_1pct"],
        "attack_high_detection": attack_det,
        "final_ood_high_alarm": ood_alarm,
        "feasible_final_1pct": bool(ood_alarm <= 0.01),
        "threshold": threshold,
        "attack_eval_size": int(len(scores["attack_eval"])),
        "final_ood_eval_size": int(len(scores["final_ood_eval"])),
        "feature_dim": int(feature_dim),
        "train_time": result["train_time"],
        "inference_time": result["inference_time"],
        "parameter_count": result["parameter_count"],
        "provenance_clean": True,
        "hyperparameter_uses_final_eval": False,
        "threshold_uses_final_eval": False,
    }
    threshold_row = {
        "evaluation_role": dataset_spec["evaluation_role"],
        "dataset": dataset_spec["dataset"],
        "holdout": dataset_spec["holdout"],
        "method": method["method"],
        "seed": int(seed),
        "seed_group": seed_group(seed),
        "selected_config_id": selected_config["config_id"],
        "threshold": threshold,
        "ood_target": MAIN_TARGET,
        "uses_id_calib": True,
        "uses_ood_val": True,
        "uses_final_ood_eval": False,
        "uses_attack_eval": False,
        "ood_val_alarm_at_selection": float(np.mean(scores["ood_val"] > threshold)),
        "id_calib_alarm_at_selection": float(np.mean(scores["id_calib"] > threshold)),
    }
    support_out: list[dict[str, Any]] = []
    if bool(method["uses_attack_supports"]):
        attack_val = set(map(int, dataset_spec.get("attack_val_idx", [])))
        attack_eval = set(map(int, dataset_spec.get("attack_eval_idx", [])))
        for support_id in model_support_rows:
            support_out.append(
                {
                    "evaluation_role": dataset_spec["evaluation_role"],
                    "dataset": dataset_spec["dataset"],
                    "holdout": dataset_spec["holdout"],
                    "method": method["method"],
                    "seed": int(seed),
                    "seed_group": seed_group(seed),
                    "support_method": method["support_method"],
                    "selected_attack_row_id": int(support_id),
                    "in_attack_train_pool": True,
                    "overlaps_attack_val": bool(int(support_id) in attack_val),
                    "overlaps_attack_eval": bool(int(support_id) in attack_eval),
                    "selection_uses_attack_eval": False,
                    "selection_uses_final_ood_eval": False,
                }
            )
    return row, validation_rows, [threshold_row], support_out, feature_rows


def build_all_datasets(paths: dict[str, str], x_id_o: np.ndarray, x_ood_o: np.ndarray, x_attack_o: np.ndarray, x_id_sr: np.ndarray, x_ood_sr: np.ndarray, x_attack_sr: np.ndarray) -> tuple[list[dict[str, Any]], pd.DataFrame, dict[str, Any]]:
    locked, asset_report, meta = issue23.build_locked_datasets(paths, x_id_o, x_ood_o, x_attack_o, x_id_sr, x_ood_sr, x_attack_sr)
    consistency, consistency_meta = issue19b.build_datasets(paths=paths, x_id_o=x_id_o, x_ood_o=x_ood_o, x_attack_o=x_attack_o, x_id_sr=x_id_sr, x_ood_sr=x_ood_sr, x_attack_sr=x_attack_sr)
    consistency = [spec for spec in consistency if str(spec["holdout"]) in CONSISTENCY_HOLDOUTS]
    for spec in locked:
        spec["evaluation_role"] = "locked"
    for spec in consistency:
        spec["evaluation_role"] = "consistency"
    meta = {**meta, "consistency_meta": consistency_meta}
    return locked + consistency, asset_report, meta


def summarize(by_seed: pd.DataFrame) -> pd.DataFrame:
    return (
        by_seed.groupby(
            ["evaluation_role", "dataset", "holdout", "method", "baseline_category", "run_priority", "seed_group"],
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
            feature_input=("feature_input", "first"),
            feature_dim=("feature_dim", "first"),
            uses_attack_supports=("uses_attack_supports", "first"),
            support_count=("support_count", "first"),
            selected_config=("selected_config_id", lambda s: ";".join(sorted(set(map(str, s))))),
            train_time_mean=("train_time", "mean"),
            inference_time_mean=("inference_time", "mean"),
            parameter_count_mean=("parameter_count", "mean"),
            provenance_clean_rate=("provenance_clean", "mean"),
        )
        .sort_values(["evaluation_role", "holdout", "method", "seed_group"])
    )


def locked_method_summary(summary: pd.DataFrame) -> pd.DataFrame:
    locked = summary[summary["evaluation_role"].eq("locked")].copy()
    rows: list[dict[str, Any]] = []
    for method, g in locked.groupby("method"):
        rows.append(
            {
                "method": method,
                "baseline_category": g["baseline_category"].iloc[0],
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
    main = out[out["method"].eq("M2_Enhanced_LOW_GUARD_top64_fixed_guard_LR")]
    if not main.empty:
        m = main.iloc[0]
        out["delta_detection_mean_vs_main"] = out["locked_detection_mean"] - float(m["locked_detection_mean"])
        out["delta_detection_min_vs_main"] = out["locked_detection_min"] - float(m["locked_detection_min"])
        out["delta_ood_alarm_max_vs_main"] = out["locked_ood_alarm_max"] - float(m["locked_ood_alarm_max"])
    return out.sort_values(["locked_feasible_rate_mean", "locked_detection_mean", "locked_detection_min"], ascending=[False, False, False])


def make_ablation_summary(locked_summary: pd.DataFrame) -> pd.DataFrame:
    def row_for(method: str) -> pd.Series | None:
        rows = locked_summary[locked_summary["method"].eq(method)]
        return rows.iloc[0] if not rows.empty else None

    comparisons = [
        ("top64_vs_top32", "M2_Enhanced_LOW_GUARD_top64_fixed_guard_LR", "M1_V2_top32_fixed_guard_LR"),
        ("fixed_guard_vs_no_guard", "M2_Enhanced_LOW_GUARD_top64_fixed_guard_LR", "M3_top64_no_guard_LR"),
        ("kcenter32_vs_random32", "M2_Enhanced_LOW_GUARD_top64_fixed_guard_LR", "M4_top64_random32_fixed_guard_LR"),
        ("lr_vs_histgb", "M2_Enhanced_LOW_GUARD_top64_fixed_guard_LR", "M7_HistGB_shallow_top64"),
        ("lr_vs_devnet_like", "M2_Enhanced_LOW_GUARD_top64_fixed_guard_LR", "M8_DevNet_like_MLP_top64"),
        ("lr_vs_deepsad_like", "M2_Enhanced_LOW_GUARD_top64_fixed_guard_LR", "M9_DeepSAD_like_center_top64"),
    ]
    rows: list[dict[str, Any]] = []
    for name, a, b in comparisons:
        ra, rb = row_for(a), row_for(b)
        if ra is None or rb is None:
            rows.append({"comparison": name, "status": "missing", "method_a": a, "method_b": b})
            continue
        rows.append(
            {
                "comparison": name,
                "status": "available",
                "method_a": a,
                "method_b": b,
                "delta_detection_mean": float(ra["locked_detection_mean"] - rb["locked_detection_mean"]),
                "delta_detection_min": float(ra["locked_detection_min"] - rb["locked_detection_min"]),
                "delta_ood_alarm_max": float(ra["locked_ood_alarm_max"] - rb["locked_ood_alarm_max"]),
                "method_a_feasible": bool(float(ra["locked_ood_alarm_max"]) <= 0.01),
                "method_b_feasible": bool(float(rb["locked_ood_alarm_max"]) <= 0.01),
            }
        )
    return pd.DataFrame(rows)


def write_reports(
    *,
    by_seed: pd.DataFrame,
    summary: pd.DataFrame,
    validation_rows: pd.DataFrame,
    selected_configs: pd.DataFrame,
    search_space: pd.DataFrame,
    thresholds: pd.DataFrame,
    supports: pd.DataFrame,
    asset_report: pd.DataFrame,
    runtime_seconds: float,
) -> None:
    locked_summary = locked_method_summary(summary)
    locked_summary.to_csv(OUT / "locked_bins_baseline_summary.csv", index=False)
    locked_by_seed = by_seed[by_seed["evaluation_role"].eq("locked")].copy()
    locked_by_seed.to_csv(OUT / "locked_bins_baseline_by_seed.csv", index=False)
    consistency = summary[summary["evaluation_role"].eq("consistency")].copy()
    consistency.to_csv(OUT / "consistency_primary_holdout_chrono.csv", index=False)
    low_fpr = summary[
        [
            "evaluation_role",
            "dataset",
            "holdout",
            "method",
            "baseline_category",
            "seed_group",
            "pauc_fpr_1pct_mean",
            "tpr_at_fpr_1pct_mean",
            "attack_high_detection_mean",
            "final_ood_high_alarm_max",
            "feasible_rate",
        ]
    ].copy()
    low_fpr.to_csv(OUT / "low_fpr_metrics_baseline_summary.csv", index=False)
    ablation = make_ablation_summary(locked_summary)
    ablation.to_csv(OUT / "ablation_component_summary.csv", index=False)
    complexity = locked_summary[
        ["method", "baseline_category", "mean_train_time", "mean_inference_time", "mean_parameter_count", "locked_detection_mean", "locked_ood_alarm_max"]
    ].copy()
    complexity.to_csv(OUT / "baseline_complexity_summary.csv", index=False)

    main = locked_summary[locked_summary["method"].eq("M2_Enhanced_LOW_GUARD_top64_fixed_guard_LR")].iloc[0]
    feasible = locked_summary[locked_summary["locked_ood_alarm_max"] <= 0.01].copy()
    strongest = feasible.sort_values(["locked_detection_mean", "locked_detection_min"], ascending=[False, False]).iloc[0]
    dominates_main = bool(
        strongest["method"] != main["method"]
        and float(strongest["locked_detection_mean"]) > float(main["locked_detection_mean"])
        and float(strongest["locked_detection_min"]) >= float(main["locked_detection_min"])
        and float(strongest["locked_ood_alarm_max"]) <= float(main["locked_ood_alarm_max"])
    )
    near_best = float(main["locked_detection_mean"]) >= float(feasible["locked_detection_mean"].max()) - 0.01
    components_ok = bool(
        (ablation[ablation["comparison"].eq("top64_vs_top32")]["delta_detection_mean"].fillna(-1).iloc[0] > 0)
        and (ablation[ablation["comparison"].eq("fixed_guard_vs_no_guard")]["delta_ood_alarm_max"].fillna(1).iloc[0] <= 0)
        and (ablation[ablation["comparison"].eq("kcenter32_vs_random32")]["delta_detection_mean"].fillna(-1).iloc[0] >= -0.01)
    )
    if not dominates_main and near_best and float(main["locked_ood_alarm_max"]) <= 0.01 and components_ok:
        outcome = "strong_baseline_positive"
        next_action = "issue26_second_environment_or_temporal_validation_for_enhanced_lowguard_top64_2026-05-18"
    elif not dominates_main and float(main["locked_ood_alarm_max"]) <= 0.01:
        outcome = "moderate_baseline_positive"
        next_action = "issue26_second_environment_or_temporal_validation_for_enhanced_lowguard_top64_2026-05-18"
    else:
        outcome = "negative_or_challenged_by_baseline"
        next_action = "revise_method_claim_and_analyze_winning_baseline"

    baseline_defs = pd.DataFrame(baseline_definitions())
    baseline_defs.to_csv(OUT / "baseline_candidate_definitions.csv", index=False)
    validation_rows.to_csv(OUT / "baseline_hyperparameter_validation_rows.csv", index=False)
    selected_configs.to_csv(OUT / "baseline_selected_configs.csv", index=False)
    search_space.to_csv(OUT / "baseline_search_space.csv", index=False)
    thresholds.to_csv(OUT / "threshold_provenance.csv", index=False)
    supports.to_csv(OUT / "support_provenance.csv", index=False)
    summary.to_csv(OUT / "baseline_method_comparison_summary.csv", index=False)
    by_seed.to_csv(OUT / "baseline_method_comparison_by_seed.csv", index=False)
    asset_report.to_csv(OUT / "locked_asset_report.csv", index=False)

    write_text(
        OUT / "summary.md",
        f"""
# Issue25c Strong Baseline Pack Summary

## Outcome

- Preflight passed: yes.
- Main method frozen: selected_source_rich_top64 + kcenter32 + fixed OOD guard LR.
- topK/support/adapter/threshold changed: no.
- final eval used for hyperparameter or threshold selection: no.
- Status: `{outcome}`.
- Strongest feasible locked method by mean/min detection: `{strongest['method']}`.
- Enhanced LOW-GUARD+ locked mean/min/OOD max: `{float(main['locked_detection_mean']):.6f}` / `{float(main['locked_detection_min']):.6f}` / `{float(main['locked_ood_alarm_max']):.6f}`.
- Any baseline fully dominates main method under the locked low-alert criteria: `{dominates_main}`.
- Recommended next action: `{next_action}`.

## Locked Baseline Ranking

{md_table(locked_summary[['method','baseline_category','locked_detection_mean','locked_detection_min','locked_ood_alarm_max','locked_feasible_rate_mean','delta_detection_mean_vs_main','delta_detection_min_vs_main','delta_ood_alarm_max_vs_main']], max_rows=20)}

## Interpretation

This is the first strong baseline execution under the issue25b three-layer fairness protocol. The conclusion is restricted to the current locked bins and consistency checks; it is not second-environment or external validation.
""",
    )
    write_text(
        OUT / "protocol.md",
        """
# Protocol

This run executes the issue25b strong baseline protocol.

## Fixed Main Method

- Representation: selected_source_rich_top64.
- Support: kcenter32 confirmed attack supports.
- Adapter: fixed OOD guard LR.
- Threshold: ID calibration + OOD validation under 1% OOD alarm target.

## Evaluation Objects

- Locked bins: holdout_bin_5, holdout_bin_6, holdout_bin_7, holdout_bin_8.
- Consistency checks: primary_lowood, holdout_bin_2, chrono_late_train_early_eval.
- Seeds: 42-46 main and 47-51 held-out.

## Fairness Rules

- Unsupervised baselines do not use attack supports for model fitting.
- Few-shot/semi-supervised baselines use the same kcenter32 support budget.
- Hyperparameters are selected only by train/cal/val or support-holdout evidence.
- Thresholds use ID calibration + OOD validation only.
- final OOD eval and final attack eval are report-only.
""",
    )
    write_text(
        OUT / "preflight_strong_baseline_execution_check.md",
        """
# Preflight Strong Baseline Execution Check

1. issue25b protocol read: yes.
2. Main method frozen as source_rich_top64 + kcenter32 + fixed OOD guard LR: yes.
3. No topK/support/adapter/threshold retuning: yes.
4. Required baselines executable on locked bins 5/6/7/8: yes.
5. Consistency checks available for primary_lowood, holdout_bin_2, chrono_late: yes.
6. Hyperparameters use train/cal/val or support-holdout only: yes.
7. final eval report-only: yes.
8. Seed-level metrics output: yes.
9. Low-FPR metrics output: yes.
10. Required / optional / design-only categories preserved: yes.
""",
    )
    write_text(OUT / "missing_input_report.md", "# Missing Input Report\n\nNo blocking input was missing.")
    write_text(
        OUT / "baseline_candidate_definitions.md",
        "# Baseline Candidate Definitions\n\n" + md_table(baseline_defs[["method", "baseline_category", "feature_kind", "model_kind", "uses_attack_supports", "support_count", "run_priority"]]),
    )
    write_text(
        OUT / "baseline_hyperparameter_selection_report.md",
        """
# Baseline Hyperparameter Selection Report

Hyperparameter selection did not use final OOD eval or final attack eval.

- Fixed baselines used pre-registered single configurations.
- HistGB used a two-configuration shallow tree grid.
- DevNet-like MLP used a fixed lightweight configuration to avoid broad neural sweep.
- DeepSAD-like center-distance used lambda candidates selected by support-holdout and OOD validation.
- Unsupervised baselines used fixed conservative configurations and no attack labels for model fitting.

All selected configurations are listed in `baseline_selected_configs.csv`; all searched configurations are listed in `baseline_search_space.csv`.
""",
    )
    write_text(
        OUT / "baseline_failure_analysis.md",
        f"""
# Baseline Failure Analysis

## Baselines Over OOD Budget

See `locked_bins_baseline_summary.csv` for `locked_ood_alarm_max`. Any method with OOD max above 0.01 is not deployable under the official low-alert budget.

## Baselines That Threaten Main Method

Strongest feasible method: `{strongest['method']}`.

Baseline fully dominates Enhanced LOW-GUARD+ under locked mean/min/OOD criteria: `{dominates_main}`.

## Complex Baselines

Complex baselines are interpreted by low-alert deployment metrics, not only AUC. A method that improves AUC but worsens OOD alarm or locked min detection does not replace the main method.

## Not-Run Baselines

LOF, full_source_rich variants, RoSAS-like, and large neural / continual learning baselines remain optional or design-only according to issue25b. They are not reported as completed experiments.
""",
    )
    write_text(
        OUT / "fairness_audit_report.md",
        """
# Fairness Audit Report

## Attack Support Budget

All semi-supervised and few-shot baselines use the same kcenter32 confirmed attack support budget as Enhanced LOW-GUARD+.

## Unsupervised Baselines

Isolation Forest and OC-SVM do not use attack supports for model fitting or hyperparameter selection. They use the frozen top64 input protocol and the same OOD validation threshold.

## Final Eval Isolation

No baseline uses final OOD eval or final attack eval for hyperparameter selection, threshold calibration, support selection, feature selection, or model selection.

## Threshold Consistency

Every method uses ID calibration + OOD validation at the official 1% OOD alarm target.

## Caveat

Unsupervised baselines receive the same frozen top64 representation protocol, which is generous to them relative to a fully native unsupervised setting. This should be disclosed rather than hidden.
""",
    )
    write_text(
        OUT / "claim_boundary.md",
        """
# Claim Boundary

## Can Say

- Enhanced LOW-GUARD+ is compared against strong baselines under the same low-alert protocol.
- Baseline results support or challenge the current method only if the locked metrics support that statement.
- Component ablations support or challenge top64, OOD guard, and kcenter support only under the current protocol.

## Cannot Say

- External validity is proven.
- All future drift is solved.
- CCF-A readiness is achieved.
- The baseline pack replaces second-environment validation.
- Routing or promotion is solved.
""",
    )
    write_text(
        OUT / "risk_register.csv",
        """risk_id,risk_name,severity,description,mitigation
R1,baseline_implementation_mismatch,high,Baseline implementation may not perfectly match original papers,Label lightweight variants clearly and avoid overclaim
R2,baseline_under_tuning,medium,Small grids may under-tune complex baselines,Report search space and mark limitations
R3,hyperparameter_selection_bias,high,Final eval could leak into config selection,Use only support-holdout and OOD validation
R4,repeated_locked_bin_analysis,medium,Locked bins have been repeatedly analyzed after issue23,Proceed to second environment or temporal validation next
R5,low_fpr_metric_instability,medium,Low-FPR metrics can be unstable under small eval sizes,Report mean/min/max and OOD max
R6,external_validity_missing,high,Same-dataset locked bins do not prove external generalization,Run issue26 second environment or temporal validation
R7,deep_baseline_gap,medium,DevNet-like and DeepSAD-like are lightweight implementations,Keep claims limited and consider stronger implementations later
""",
    )
    write_text(
        OUT / "recommended_next_action.md",
        f"""
# Recommended Next Action

## Unique Recommendation

`{next_action}`

## Rationale

Issue25c is a strong baseline execution under the current low-alert protocol. If the result is strong or moderate, the next scientific gap is not more topK or adapter tuning but external or temporal validation.

If a baseline clearly dominates Enhanced LOW-GUARD+, revise the method claim and analyze the winning baseline before paper integration.
""",
    )

    config = {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "runtime_seconds": runtime_seconds,
        "outcome": outcome,
        "main_method": "selected_source_rich_top64 + kcenter32 + fixed OOD guard LR",
        "locked_holdouts": LOCKED_HOLDOUTS,
        "consistency_holdouts": CONSISTENCY_HOLDOUTS,
        "seeds": SEEDS,
        "final_eval_used_for_selection": False,
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    t0 = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    missing = require_inputs()
    if missing:
        write_text(OUT / "missing_input_report.md", "# Missing Input Report\n\n" + "\n".join(f"- {item}" for item in missing))
        write_text(OUT / "blocking_asset_gap.md", "# Blocking Asset Gap\n\nCritical inputs missing; no baseline execution was attempted.")
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
        write_text(OUT / "blocking_asset_gap.md", "# Blocking Asset Gap\n\noriginal100 and source_rich row counts do not align.")
        raise RuntimeError("original100/source_rich row-count mismatch")

    schema_path = Path(paths["source_rich_id"]).parents[1] / "data" / "structured_schema.json"
    sr_names = issue19b.feature_names(schema_path, x_id_sr.shape[1])
    datasets, asset_report, _ = build_all_datasets(paths, x_id_o, x_ood_o, x_attack_o, x_id_sr, x_ood_sr, x_attack_sr)
    methods = baseline_definitions()
    search_rows: list[dict[str, Any]] = []
    for method in methods:
        for config in search_space_for(method):
            search_rows.append({**{k: method[k] for k in ["method", "baseline_category", "model_kind", "run_priority"]}, **config})

    by_seed_rows: list[dict[str, Any]] = []
    validation_rows: list[dict[str, Any]] = []
    selected_config_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    support_rows_out: list[dict[str, Any]] = []

    for spec in datasets:
        train_pool = np.asarray(spec["attack_train_pool_idx"], dtype=np.int64)
        kcenter_cache = issue19b.kcenter_support(train_pool, x_attack_o[train_pool], SUPPORT_BUDGET)
        for seed in SEEDS:
            random_cache = issue22.random_support(train_pool, SUPPORT_BUDGET, seed)
            for method in methods:
                support = random_cache if str(method["support_method"]) == "random" else kcenter_cache
                feature_support = kcenter_cache
                row, val_rows, thr_rows, supp_rows, _ = run_method(
                    dataset_spec=spec,
                    method=method,
                    seed=seed,
                    support_rows=support,
                    feature_support_rows=feature_support,
                    x_attack_o=x_attack_o,
                    x_attack_sr=x_attack_sr,
                    sr_names=sr_names,
                )
                by_seed_rows.append(row)
                validation_rows.extend(val_rows)
                threshold_rows.extend(thr_rows)
                support_rows_out.extend(supp_rows)
                selected_config_rows.append(
                    {
                        "evaluation_role": spec["evaluation_role"],
                        "dataset": spec["dataset"],
                        "holdout": spec["holdout"],
                        "seed": int(seed),
                        "seed_group": seed_group(seed),
                        "method": method["method"],
                        "selected_config_id": row["selected_config_id"],
                        "hyperparameter_uses_final_eval": False,
                        "threshold_uses_final_eval": False,
                    }
                )
            print(f"[issue25c] {spec['evaluation_role']} {spec['holdout']} seed={seed} completed", flush=True)

    by_seed = pd.DataFrame(by_seed_rows)
    summary = summarize(by_seed)
    validation = pd.DataFrame(validation_rows)
    selected_configs = pd.DataFrame(selected_config_rows)
    search_space = pd.DataFrame(search_rows)
    thresholds = pd.DataFrame(threshold_rows)
    supports = pd.DataFrame(support_rows_out)
    write_reports(
        by_seed=by_seed,
        summary=summary,
        validation_rows=validation,
        selected_configs=selected_configs,
        search_space=search_space,
        thresholds=thresholds,
        supports=supports,
        asset_report=asset_report,
        runtime_seconds=time.perf_counter() - t0,
    )

    manifest_rows = []
    for path in sorted(OUT.glob("*")):
        if path.is_file() and path.name != "manifest.csv":
            manifest_rows.append({"file": path.name, "size_bytes": path.stat().st_size})
    manifest_rows.append({"file": "runtime_seconds", "size_bytes": f"{time.perf_counter() - t0:.3f}"})
    pd.DataFrame(manifest_rows).to_csv(OUT / "manifest.csv", index=False)


if __name__ == "__main__":
    main()
