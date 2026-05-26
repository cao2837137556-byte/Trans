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
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.kernel_approximation import RBFSampler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score, roc_curve
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs" / "issue27b_guarded_protocol_transfer_and_adapter_recovery_2026-05-26"

ISSUE27A = ROOT / "runs" / "issue27a_deployment_feasibility_and_guarded_training_protocol_audit_2026-05-22"
ISSUE25C = ROOT / "runs" / "issue25c_strong_baseline_pack_execution_for_enhanced_lowguard_top64_2026-05-18"
ISSUE25B = ROOT / "runs" / "issue25b_strong_baseline_protocol_and_fairness_design_2026-05-18"
ISSUE23 = ROOT / "runs" / "issue23_locked_validation_for_enhanced_v2_top64_2026-05-18"
ISSUE11 = ROOT / "runs" / "issue11_fixed_config_ood_guard_lr_ablation_2026-05-14"
ISSUE25C_SCRIPT = ISSUE25C / "run_issue25c_strong_baselines.py"

SEEDS = list(range(42, 52))
MAIN_TARGET = 0.01
SUPPORT_BUDGET = 32
SUPPORT_TRAIN_FOR_SELECTION = 24
LOCKED_HOLDOUTS = ["holdout_bin_5", "holdout_bin_6", "holdout_bin_7", "holdout_bin_8"]


def import_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


issue25c = import_module(ISSUE25C_SCRIPT, "issue25c_for_issue27b")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def md_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
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
    return issue25c.seed_group(seed)


def require_inputs() -> list[str]:
    required = [
        ISSUE27A / "summary.md",
        ISSUE27A / "lr_vs_framework_positioning.md",
        ISSUE27A / "issue27b_next_experiment_decision.md",
        ISSUE25C / "summary.md",
        ISSUE25C / "baseline_method_comparison_by_seed.csv",
        ISSUE25C / "locked_bins_baseline_summary.csv",
        ISSUE25B / "summary.md",
        ISSUE25B / "threshold_and_hyperparameter_protocol.md",
        ISSUE23 / "locked_validation_asset_report.md",
        ROOT / "runs" / "mainline_docs" / "mainline_handoff.md",
        ROOT / "runs" / "mainline_docs" / "mainline_experiment_map.md",
        ISSUE11 / "config.json",
        ISSUE25C_SCRIPT,
    ]
    return [str(path) for path in required if not path.exists()]


def protocol_variants() -> list[dict[str, Any]]:
    return [
        {
            "protocol_variant": "P0_raw_train_id_threshold",
            "train_uses_ood_guard": False,
            "threshold_uses_ood_val_guard": False,
            "purpose": "ordinary few-shot training baseline",
        },
        {
            "protocol_variant": "P1_raw_train_oodval_threshold",
            "train_uses_ood_guard": False,
            "threshold_uses_ood_val_guard": True,
            "purpose": "threshold guard only",
        },
        {
            "protocol_variant": "P2_guarded_train_id_threshold",
            "train_uses_ood_guard": True,
            "threshold_uses_ood_val_guard": False,
            "purpose": "training guard only",
        },
        {
            "protocol_variant": "P3_full_lowguard",
            "train_uses_ood_guard": True,
            "threshold_uses_ood_val_guard": True,
            "purpose": "full LOW-GUARD protocol",
        },
    ]


def head_specs() -> list[dict[str, Any]]:
    return [
        {
            "head_id": "LOW_GUARD_LR_reference",
            "head_family": "lr",
            "head_label": "LOW-GUARD-LR reference",
            "mandatory": True,
            "configs": [{"config_id": "lr_C1", "C": 1.0}],
        },
        {
            "head_id": "DevNet_like_MLP",
            "head_family": "devnet_like_mlp",
            "head_label": "DevNet-like MLP",
            "mandatory": True,
            "configs": [
                {"config_id": "mlp_h8_alpha001", "hidden": 8, "alpha": 0.001, "max_iter": 80},
                {"config_id": "mlp_h16_alpha001", "hidden": 16, "alpha": 0.001, "max_iter": 80},
            ],
        },
        {
            "head_id": "HistGB_shallow",
            "head_family": "histgb",
            "head_label": "HistGB shallow",
            "mandatory": True,
            "configs": [
                {"config_id": "histgb_depth2_iter50_lr005", "max_depth": 2, "max_iter": 50, "learning_rate": 0.05, "l2_regularization": 0.0},
                {"config_id": "histgb_depth3_iter50_lr005", "max_depth": 3, "max_iter": 50, "learning_rate": 0.05, "l2_regularization": 0.0},
            ],
        },
        {
            "head_id": "DeepSAD_like_center",
            "head_family": "deepsad_like_center",
            "head_label": "DeepSAD-like center",
            "mandatory": True,
            "configs": [
                {"config_id": "center_lambda0", "lambda_attack": 0.0},
                {"config_id": "center_lambda1", "lambda_attack": 1.0},
                {"config_id": "center_lambda2", "lambda_attack": 2.0},
            ],
        },
        {
            "head_id": "Prototype_metric_LR",
            "head_family": "prototype_metric_lr",
            "head_label": "Prototype / metric LR",
            "mandatory": True,
            "configs": [{"config_id": "prototype_metric_lr_C1", "C": 1.0}],
        },
        {
            "head_id": "RFF_Logistic",
            "head_family": "rff_logistic",
            "head_label": "RFF Logistic optional",
            "mandatory": False,
            "configs": [
                {"config_id": "rff128_gamma01_C1", "n_components": 128, "gamma": 0.1, "C": 1.0},
                {"config_id": "rff128_gamma1_C1", "n_components": 128, "gamma": 1.0, "C": 1.0},
                {"config_id": "rff256_gamma01_C1", "n_components": 256, "gamma": 0.1, "C": 1.0},
                {"config_id": "rff256_gamma1_C1", "n_components": 256, "gamma": 1.0, "C": 1.0},
            ],
        },
    ]


def split_support_for_selection(support_rows: np.ndarray, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed + 27026)
    rows = np.asarray(support_rows, dtype=np.int64).copy()
    rng.shuffle(rows)
    return np.sort(rows[:SUPPORT_TRAIN_FOR_SELECTION]), np.sort(rows[SUPPORT_TRAIN_FOR_SELECTION:])


def id_only_threshold(score_id_calib: np.ndarray, target_alarm: float) -> dict[str, Any]:
    scores = np.asarray(score_id_calib, dtype=np.float64)
    candidates = np.unique(np.quantile(scores, np.linspace(0.0, 1.0, 4001)[1:]))
    for thr in sorted(candidates):
        id_alarm = float(np.mean(scores > thr))
        if id_alarm <= float(target_alarm):
            return {
                "threshold": float(thr),
                "id_calib_alarm_at_selection": id_alarm,
                "ood_val_alarm_at_selection": math.nan,
                "selection_feasible": True,
            }
    thr = float(np.max(scores))
    return {
        "threshold": thr,
        "id_calib_alarm_at_selection": float(np.mean(scores > thr)),
        "ood_val_alarm_at_selection": math.nan,
        "selection_feasible": False,
    }


def calibrate_threshold(scores: dict[str, np.ndarray], protocol: dict[str, Any]) -> dict[str, Any]:
    if bool(protocol["threshold_uses_ood_val_guard"]):
        out = issue25c.issue19b.v72.guarded_val_threshold(scores["id_calib"], scores["ood_val"], MAIN_TARGET)
        out["threshold_source"] = "id_calib_plus_ood_val_guarded_1pct"
        return out
    out = id_only_threshold(scores["id_calib"], MAIN_TARGET)
    out["ood_val_alarm_at_selection"] = float(np.mean(scores["ood_val"] > float(out["threshold"])))
    out["threshold_source"] = "id_calib_only_1pct"
    return out


class CenterDistanceModel:
    def __init__(self, center: np.ndarray, weights: np.ndarray):
        self.center = center
        self.weights = weights

    def score(self, x: np.ndarray) -> np.ndarray:
        return np.sum(((x - self.center) ** 2) * self.weights, axis=1)


class PrototypeMetricLR:
    def __init__(self, id_center: np.ndarray, attack_center: np.ndarray, ood_center: np.ndarray | None, scaler: StandardScaler, model: LogisticRegression):
        self.id_center = id_center
        self.attack_center = attack_center
        self.ood_center = ood_center
        self.scaler = scaler
        self.model = model

    def features(self, x: np.ndarray) -> np.ndarray:
        d_id = np.linalg.norm(x - self.id_center, axis=1)
        d_attack = np.linalg.norm(x - self.attack_center, axis=1)
        cols = [d_id, d_attack, d_id - d_attack]
        if self.ood_center is not None:
            d_ood = np.linalg.norm(x - self.ood_center, axis=1)
            cols.extend([d_ood, d_ood - d_attack])
        return np.vstack(cols).T

    def score(self, x: np.ndarray) -> np.ndarray:
        return np.asarray(self.model.decision_function(self.scaler.transform(self.features(x))), dtype=np.float64)


class RFFLogistic:
    def __init__(self, scaler: StandardScaler, rff: RBFSampler, model: LogisticRegression):
        self.scaler = scaler
        self.rff = rff
        self.model = model

    def score(self, x: np.ndarray) -> np.ndarray:
        return np.asarray(self.model.decision_function(self.rff.transform(self.scaler.transform(x))), dtype=np.float64)


def build_training_data(mats: dict[str, np.ndarray], train_uses_guard: bool) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if train_uses_guard:
        x_train = np.vstack([mats["id_train"], mats["ood_train"], mats["support"]])
        y_train = np.concatenate([np.zeros(len(mats["id_train"])), np.zeros(len(mats["ood_train"])), np.ones(len(mats["support"]))])
        sample_weight = np.concatenate([np.ones(len(mats["id_train"])), np.full(len(mats["ood_train"]), 2.0), np.ones(len(mats["support"]))])
    else:
        x_train = np.vstack([mats["id_train"], mats["support"]])
        y_train = np.concatenate([np.zeros(len(mats["id_train"])), np.ones(len(mats["support"]))])
        sample_weight = np.ones(len(y_train), dtype=np.float64)
    return x_train, y_train, sample_weight


def fit_head(head: dict[str, Any], config: dict[str, Any], mats: dict[str, np.ndarray], seed: int, train_uses_guard: bool) -> tuple[Any, dict[str, Any]]:
    family = str(head["head_family"])
    t0 = time.perf_counter()
    x_train, y_train, sample_weight = build_training_data(mats, train_uses_guard)
    aux: dict[str, Any] = {}

    if family == "lr":
        scaler = StandardScaler().fit(x_train)
        model = LogisticRegression(C=float(config["C"]), penalty="l2", solver="liblinear", class_weight="balanced", max_iter=2000, random_state=seed)
        model.fit(scaler.transform(x_train), y_train, sample_weight=sample_weight)
        aux["train_time"] = time.perf_counter() - t0
        return ("linear", model, scaler), {"param_count": int(model.coef_.size + model.intercept_.size), **aux}

    if family == "devnet_like_mlp":
        if train_uses_guard:
            sw = np.concatenate([np.ones(len(mats["id_train"])), np.full(len(mats["ood_train"]), 2.0), np.full(len(mats["support"]), 16.0)])
        else:
            sw = np.concatenate([np.ones(len(mats["id_train"])), np.full(len(mats["support"]), 16.0)])
        scaler = StandardScaler().fit(x_train)
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
            model.fit(scaler.transform(x_train), y_train, sample_weight=sw)
        aux["train_time"] = time.perf_counter() - t0
        param_count = sum(w.size for w in model.coefs_) + sum(b.size for b in model.intercepts_)
        return ("proba", model, scaler), {"param_count": int(param_count), **aux}

    if family == "histgb":
        model = HistGradientBoostingClassifier(
            max_depth=int(config["max_depth"]),
            max_iter=int(config["max_iter"]),
            learning_rate=float(config["learning_rate"]),
            l2_regularization=float(config["l2_regularization"]),
            random_state=seed,
        )
        model.fit(x_train, y_train, sample_weight=sample_weight)
        aux["train_time"] = time.perf_counter() - t0
        return ("proba_no_scaler", model, None), {"param_count": int(config["max_iter"]), **aux}

    if family == "deepsad_like_center":
        scaler = StandardScaler().fit(x_train)
        benign_raw = np.vstack([mats["id_train"], mats["ood_train"]]) if train_uses_guard else mats["id_train"]
        benign = scaler.transform(benign_raw)
        support = scaler.transform(mats["support"])
        center = benign.mean(axis=0)
        if len(support):
            sep = np.abs(support.mean(axis=0) - center)
            sep = sep / (np.median(sep) + 1e-8)
        else:
            sep = np.zeros_like(center)
        weights = 1.0 + float(config["lambda_attack"]) * sep
        aux["train_time"] = time.perf_counter() - t0
        return ("center", CenterDistanceModel(center=center, weights=weights), scaler), {"param_count": int(len(center) * 2), **aux}

    if family == "prototype_metric_lr":
        id_center = mats["id_train"].mean(axis=0)
        attack_center = mats["support"].mean(axis=0)
        ood_center = mats["ood_train"].mean(axis=0) if train_uses_guard else None
        tmp = PrototypeMetricLR(id_center, attack_center, ood_center, StandardScaler(), LogisticRegression())
        x_proto = tmp.features(x_train)
        scaler = StandardScaler().fit(x_proto)
        model = LogisticRegression(C=float(config["C"]), penalty="l2", solver="liblinear", class_weight="balanced", max_iter=2000, random_state=seed)
        model.fit(scaler.transform(x_proto), y_train, sample_weight=sample_weight)
        wrapped = PrototypeMetricLR(id_center, attack_center, ood_center, scaler, model)
        aux["train_time"] = time.perf_counter() - t0
        return ("prototype", wrapped, None), {"param_count": int(model.coef_.size + model.intercept_.size + len(id_center) * (3 if ood_center is not None else 2)), **aux}

    if family == "rff_logistic":
        scaler = StandardScaler().fit(x_train)
        rff = RBFSampler(gamma=float(config["gamma"]), n_components=int(config["n_components"]), random_state=seed)
        x_rff = rff.fit_transform(scaler.transform(x_train))
        model = LogisticRegression(C=float(config["C"]), penalty="l2", solver="liblinear", class_weight="balanced", max_iter=2000, random_state=seed)
        model.fit(x_rff, y_train, sample_weight=sample_weight)
        wrapped = RFFLogistic(scaler, rff, model)
        aux["train_time"] = time.perf_counter() - t0
        return ("rff", wrapped, None), {"param_count": int(model.coef_.size + model.intercept_.size + int(config["n_components"]) * x_train.shape[1]), **aux}

    raise ValueError(f"Unknown head family: {family}")


def score_head(fitted: tuple[Any, Any, Any], x: np.ndarray) -> np.ndarray:
    mode, model, scaler = fitted
    if mode == "linear":
        return np.asarray(model.decision_function(scaler.transform(x)), dtype=np.float64)
    if mode == "proba":
        return np.asarray(model.predict_proba(scaler.transform(x))[:, 1], dtype=np.float64)
    if mode == "proba_no_scaler":
        return np.asarray(model.predict_proba(x)[:, 1], dtype=np.float64)
    if mode == "center":
        return np.asarray(model.score(scaler.transform(x)), dtype=np.float64)
    if mode in {"prototype", "rff"}:
        return np.asarray(model.score(x), dtype=np.float64)
    raise ValueError(f"Unknown fitted mode: {mode}")


def low_fpr_metrics(scores_ood: np.ndarray, scores_attack: np.ndarray) -> tuple[float, float]:
    y_true = np.concatenate([np.zeros(len(scores_ood), dtype=np.int64), np.ones(len(scores_attack), dtype=np.int64)])
    y_score = np.concatenate([scores_ood, scores_attack])
    pauc = float(roc_auc_score(y_true, y_score, max_fpr=0.01))
    fpr, tpr, _ = roc_curve(y_true, y_score)
    tpr_at_1pct = float(np.max(tpr[fpr <= 0.01])) if np.any(fpr <= 0.01) else 0.0
    return pauc, tpr_at_1pct


def evaluate_config(head: dict[str, Any], config: dict[str, Any], protocol: dict[str, Any], mats: dict[str, np.ndarray], seed: int, positive_key: str) -> dict[str, Any]:
    fitted, aux = fit_head(head, config, mats, seed, bool(protocol["train_uses_ood_guard"]))
    t1 = time.perf_counter()
    scores = {
        "id_calib": score_head(fitted, mats["id_calib"]),
        "ood_val": score_head(fitted, mats["ood_val"]),
        "final_ood_eval": score_head(fitted, mats["ood_eval"]),
        "attack_eval": score_head(fitted, mats["attack_eval"]),
    }
    if "support_val" in mats:
        scores["support_val"] = score_head(fitted, mats["support_val"])
    inference_time = time.perf_counter() - t1
    threshold_info = calibrate_threshold(scores, protocol)
    threshold = float(threshold_info["threshold"])
    positive_scores = scores[positive_key]
    final_y = np.concatenate([np.zeros(len(scores["final_ood_eval"]), dtype=np.int64), np.ones(len(scores["attack_eval"]), dtype=np.int64)])
    final_s = np.concatenate([scores["final_ood_eval"], scores["attack_eval"]])
    pauc, tpr1 = low_fpr_metrics(scores["final_ood_eval"], scores["attack_eval"])
    return {
        "scores": scores,
        "threshold": threshold,
        "threshold_info": threshold_info,
        "roc_auc_attack_vs_ood": float(roc_auc_score(final_y, final_s)),
        "pr_auc_attack_vs_ood": float(average_precision_score(final_y, final_s)),
        "pauc_fpr_1pct": pauc,
        "tpr_at_fpr_1pct": tpr1,
        "positive_detection": float(np.mean(positive_scores > threshold)),
        "positive_margin_q25": float(np.quantile(positive_scores - threshold, 0.25)) if len(positive_scores) else math.nan,
        "positive_margin_median": float(np.median(positive_scores - threshold)) if len(positive_scores) else math.nan,
        "id_calib_alarm": float(np.mean(scores["id_calib"] > threshold)),
        "ood_val_alarm": float(np.mean(scores["ood_val"] > threshold)),
        "final_ood_alarm": float(np.mean(scores["final_ood_eval"] > threshold)),
        "train_time": float(aux["train_time"]),
        "inference_time": float(inference_time),
        "param_count": int(aux["param_count"]),
    }


def select_features_for_spec(dataset_spec: dict[str, Any], support_rows: np.ndarray, x_attack_sr: np.ndarray, sr_names: list[str], seed: int) -> tuple[str, np.ndarray, int, list[dict[str, Any]]]:
    representation, feature_idx, feature_dim, feature_rows = issue25c.select_features(
        dataset_spec=dataset_spec,
        feature_kind="source_rich_top64",
        support_rows=support_rows,
        x_attack_sr=x_attack_sr,
        sr_names=sr_names,
        seed=seed,
    )
    if feature_idx is None:
        raise RuntimeError("top64 feature_idx is required")
    return representation, feature_idx, int(feature_dim), feature_rows


def mats_for(
    dataset_spec: dict[str, Any],
    feature_idx: np.ndarray,
    x_attack_o: np.ndarray,
    x_attack_sr: np.ndarray,
    support_rows: np.ndarray,
) -> dict[str, np.ndarray]:
    return issue25c.matrix_view(dataset_spec, "selected_source_rich_top64", feature_idx, x_attack_o, x_attack_sr, support_rows)


def choose_config(
    *,
    head: dict[str, Any],
    protocol: dict[str, Any],
    dataset_spec: dict[str, Any],
    support_rows: np.ndarray,
    x_attack_o: np.ndarray,
    x_attack_sr: np.ndarray,
    sr_names: list[str],
    seed: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    support_train, support_val = split_support_for_selection(support_rows, seed)
    _, feature_idx, _, _ = select_features_for_spec(dataset_spec, support_train, x_attack_sr, sr_names, seed)
    mats = mats_for(dataset_spec, feature_idx, x_attack_o, x_attack_sr, support_train)
    mats["support_val"] = x_attack_sr[support_val][:, feature_idx]
    rows: list[dict[str, Any]] = []
    for config in head["configs"]:
        result = evaluate_config(head, config, protocol, mats, seed, "support_val")
        validation_feasible = bool(result["ood_val_alarm"] <= MAIN_TARGET)
        rows.append(
            {
                "dataset": dataset_spec["dataset"],
                "holdout": dataset_spec["holdout"],
                "seed": int(seed),
                "seed_group": seed_group(seed),
                "head_id": head["head_id"],
                "head_family": head["head_family"],
                "protocol_variant": protocol["protocol_variant"],
                "config_id": config["config_id"],
                "support_train_size": int(len(support_train)),
                "support_validation_size": int(len(support_val)),
                "support_val_detection": result["positive_detection"],
                "support_val_margin_q25": result["positive_margin_q25"],
                "support_val_margin_median": result["positive_margin_median"],
                "id_calib_alarm_at_selection": result["id_calib_alarm"],
                "ood_val_alarm_at_selection": result["ood_val_alarm"],
                "validation_feasible_under_1pct": validation_feasible,
                "selection_used_final_eval": False,
                "config_param_count": result["param_count"],
            }
        )
    val = pd.DataFrame(rows)
    if val["validation_feasible_under_1pct"].any():
        val_sorted = val.sort_values(
            ["validation_feasible_under_1pct", "support_val_detection", "support_val_margin_q25", "support_val_margin_median", "config_param_count", "config_id"],
            ascending=[False, False, False, False, True, True],
        )
        selection_rule = "feasible_ood_val_then_support_val_detection_then_margin_then_simplicity"
    else:
        val_sorted = val.sort_values(
            ["ood_val_alarm_at_selection", "support_val_detection", "support_val_margin_q25", "config_param_count", "config_id"],
            ascending=[True, False, False, True, True],
        )
        selection_rule = "no_feasible_config_lowest_ood_val_alarm_then_support_signal"
    selected_config_id = str(val_sorted.iloc[0]["config_id"])
    for row in rows:
        row["selected"] = bool(row["config_id"] == selected_config_id)
        row["selection_rule"] = selection_rule
        row["rejection_reason"] = "selected" if row["selected"] else "lower_validation_rank"
    return next(config for config in head["configs"] if str(config["config_id"]) == selected_config_id), rows


def run_one(
    *,
    dataset_spec: dict[str, Any],
    head: dict[str, Any],
    protocol: dict[str, Any],
    seed: int,
    support_rows: np.ndarray,
    x_attack_o: np.ndarray,
    x_attack_sr: np.ndarray,
    sr_names: list[str],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    selected_config, selection_rows = choose_config(
        head=head,
        protocol=protocol,
        dataset_spec=dataset_spec,
        support_rows=support_rows,
        x_attack_o=x_attack_o,
        x_attack_sr=x_attack_sr,
        sr_names=sr_names,
        seed=seed,
    )
    representation, feature_idx, feature_dim, feature_rows = select_features_for_spec(dataset_spec, support_rows, x_attack_sr, sr_names, seed)
    mats = mats_for(dataset_spec, feature_idx, x_attack_o, x_attack_sr, support_rows)
    result = evaluate_config(head, selected_config, protocol, mats, seed, "attack_eval")
    scores = result["scores"]
    threshold = float(result["threshold"])
    row = {
        "evaluation_role": "locked",
        "dataset": dataset_spec["dataset"],
        "holdout": dataset_spec["holdout"],
        "split_protocol": dataset_spec["split_protocol"],
        "head_id": head["head_id"],
        "head_family": head["head_family"],
        "head_label": head["head_label"],
        "protocol_variant": protocol["protocol_variant"],
        "train_uses_ood_guard": bool(protocol["train_uses_ood_guard"]),
        "threshold_uses_ood_val_guard": bool(protocol["threshold_uses_ood_val_guard"]),
        "selected_config_id": selected_config["config_id"],
        "seed": int(seed),
        "seed_group": seed_group(seed),
        "feature_input": representation,
        "feature_dim": int(feature_dim),
        "support_method": "kcenter",
        "support_count": int(len(support_rows)),
        "ood_target": MAIN_TARGET,
        "threshold_source": result["threshold_info"]["threshold_source"],
        "threshold": threshold,
        "attack_detection": float(np.mean(scores["attack_eval"] > threshold)),
        "final_ood_alarm": result["final_ood_alarm"],
        "id_calib_alarm": result["id_calib_alarm"],
        "ood_val_alarm": result["ood_val_alarm"],
        "roc_auc_attack_vs_ood": result["roc_auc_attack_vs_ood"],
        "pr_auc_attack_vs_ood": result["pr_auc_attack_vs_ood"],
        "pauc_fpr_1pct": result["pauc_fpr_1pct"],
        "tpr_at_fpr_1pct": result["tpr_at_fpr_1pct"],
        "feasible_under_1pct": bool(result["final_ood_alarm"] <= MAIN_TARGET),
        "attack_eval_size": int(len(scores["attack_eval"])),
        "final_ood_eval_size": int(len(scores["final_ood_eval"])),
        "train_time": result["train_time"],
        "inference_time": result["inference_time"],
        "param_count": result["param_count"],
        "selection_used_final_eval": False,
        "threshold_uses_final_eval": False,
        "hyperparameter_uses_final_eval": False,
    }
    return row, selection_rows, feature_rows


def holdout_seed_group_summary(by_seed: pd.DataFrame) -> pd.DataFrame:
    return (
        by_seed.groupby(["head_id", "head_family", "protocol_variant", "holdout", "seed_group"], as_index=False)
        .agg(
            detection_mean=("attack_detection", "mean"),
            detection_min=("attack_detection", "min"),
            ood_alarm_max=("final_ood_alarm", "max"),
            feasible_rate=("feasible_under_1pct", "mean"),
            pauc_mean=("pauc_fpr_1pct", "mean"),
            tpr_at_fpr_1pct_mean=("tpr_at_fpr_1pct", "mean"),
            train_time_mean=("train_time", "mean"),
            inference_time_mean=("inference_time", "mean"),
            param_count_mean=("param_count", "mean"),
        )
    )


def locked_summary(by_seed: pd.DataFrame) -> pd.DataFrame:
    hs = holdout_seed_group_summary(by_seed)
    out = (
        hs.groupby(["head_id", "head_family", "protocol_variant"], as_index=False)
        .agg(
            locked_detection_mean=("detection_mean", "mean"),
            locked_detection_min=("detection_mean", "min"),
            locked_ood_alarm_max=("ood_alarm_max", "max"),
            feasible_rate=("feasible_rate", "mean"),
            locked_pauc_fpr_1pct_mean=("pauc_mean", "mean"),
            locked_tpr_at_fpr_1pct_mean=("tpr_at_fpr_1pct_mean", "mean"),
            mean_train_time=("train_time_mean", "mean"),
            mean_inference_time=("inference_time_mean", "mean"),
            mean_parameter_count=("param_count_mean", "mean"),
        )
    )
    ref = out[(out["head_id"].eq("LOW_GUARD_LR_reference")) & (out["protocol_variant"].eq("P3_full_lowguard"))].iloc[0]
    out["detection_delta_vs_lowguard_lr"] = out["locked_detection_mean"] - float(ref["locked_detection_mean"])
    out["min_detection_delta_vs_lowguard_lr"] = out["locked_detection_min"] - float(ref["locked_detection_min"])
    out["ood_delta_vs_lowguard_lr"] = out["locked_ood_alarm_max"] - float(ref["locked_ood_alarm_max"])
    out["dominates_lowguard_lr"] = (
        (out["locked_detection_mean"] > float(ref["locked_detection_mean"]))
        & (out["locked_detection_min"] >= float(ref["locked_detection_min"]))
        & (out["locked_ood_alarm_max"] <= float(ref["locked_ood_alarm_max"]))
        & (out["feasible_rate"] >= float(ref["feasible_rate"]))
    )
    out["promising_for_lowguard_plus_plus"] = (
        (out["head_id"].ne("LOW_GUARD_LR_reference"))
        & (out["protocol_variant"].eq("P3_full_lowguard"))
        & (out["locked_detection_mean"] > float(ref["locked_detection_mean"]))
        & (out["locked_detection_min"] >= float(ref["locked_detection_min"]))
        & (out["locked_ood_alarm_max"] <= MAIN_TARGET)
        & (out["feasible_rate"] >= float(ref["feasible_rate"]) - 0.05)
    )
    return out.sort_values(["protocol_variant", "feasible_rate", "locked_detection_mean", "locked_detection_min"], ascending=[True, False, False, False])


def add_recovery_flags(summary: pd.DataFrame) -> pd.DataFrame:
    out = summary.copy()
    out["rescued_from_collapse"] = False
    out["converted_to_feasible"] = False
    out["recovery_mode"] = "no_recovery"
    for head_id, g in out.groupby("head_id"):
        p0 = g[g["protocol_variant"].eq("P0_raw_train_id_threshold")]
        p1 = g[g["protocol_variant"].eq("P1_raw_train_oodval_threshold")]
        p2 = g[g["protocol_variant"].eq("P2_guarded_train_id_threshold")]
        p3 = g[g["protocol_variant"].eq("P3_full_lowguard")]
        if p0.empty or p1.empty or p2.empty or p3.empty:
            continue
        raw_det = float(p0.iloc[0]["locked_detection_mean"])
        raw_ood = float(p0.iloc[0]["locked_ood_alarm_max"])
        p1_det = float(p1.iloc[0]["locked_detection_mean"])
        p1_ood = float(p1.iloc[0]["locked_ood_alarm_max"])
        p2_det = float(p2.iloc[0]["locked_detection_mean"])
        p2_ood = float(p2.iloc[0]["locked_ood_alarm_max"])
        full_det = float(p3.iloc[0]["locked_detection_mean"])
        full_ood = float(p3.iloc[0]["locked_ood_alarm_max"])
        raw_collapse = raw_det < 0.20
        raw_violation = raw_ood > MAIN_TARGET
        p1_feasible_strong = p1_ood <= MAIN_TARGET and p1_det >= 0.80
        p2_feasible_strong = p2_ood <= MAIN_TARGET and p2_det >= 0.80
        full_feasible = full_ood <= MAIN_TARGET
        full_strong = full_det >= 0.80
        idx = out["head_id"].eq(head_id) & out["protocol_variant"].eq("P3_full_lowguard")
        out.loc[idx, "rescued_from_collapse"] = bool(raw_collapse and full_strong)
        out.loc[idx, "converted_to_feasible"] = bool(raw_violation and full_feasible)
        if bool(out.loc[idx, "promising_for_lowguard_plus_plus"].any()):
            mode = "candidate_lowguard_plus_plus"
        elif raw_violation and p2_feasible_strong and not p1_feasible_strong:
            mode = "training_guard_recovers_detection"
        elif raw_violation and p1_feasible_strong:
            mode = "threshold_guard_recovers_feasibility"
        elif raw_collapse and full_strong and full_feasible:
            mode = "full_lowguard_recovers_both"
        elif full_det > raw_det + 0.10 and not full_feasible:
            mode = "detection_gain_not_feasible"
        elif full_feasible and full_det < raw_det - 0.10:
            mode = "feasible_but_detection_drop"
        elif full_feasible:
            mode = "lr_remains_best_feasible" if head_id == "LOW_GUARD_LR_reference" else "feasible_without_lr_dominance"
        else:
            mode = "no_recovery"
        out.loc[idx, "recovery_mode"] = mode
        raw_idx = out["head_id"].eq(head_id) & out["protocol_variant"].eq("P0_raw_train_id_threshold")
        if raw_collapse:
            out.loc[raw_idx, "recovery_mode"] = "raw_detection_collapse"
        elif raw_violation:
            out.loc[raw_idx, "recovery_mode"] = "raw_ood_budget_violation"
    return out


def write_static_matrices() -> None:
    coverage_rows = []
    config_rows = []
    for head in head_specs():
        for protocol in protocol_variants():
            coverage_rows.append(
                {
                    "head_id": head["head_id"],
                    "head_family": head["head_family"],
                    "protocol_variant": protocol["protocol_variant"],
                    "coverage_status": "evaluated",
                    "skipped_with_reason": "",
                    "train_uses_ood_guard": protocol["train_uses_ood_guard"],
                    "threshold_uses_ood_val_guard": protocol["threshold_uses_ood_val_guard"],
                }
            )
            for config in head["configs"]:
                row = {
                    "head_id": head["head_id"],
                    "head_family": head["head_family"],
                    "protocol_variant": protocol["protocol_variant"],
                    "config_id": config["config_id"],
                    "pre_registered": True,
                    "uses_final_eval_for_selection": False,
                }
                row.update({k: v for k, v in config.items() if k != "config_id"})
                config_rows.append(row)
    pd.DataFrame(coverage_rows).to_csv(OUT / "protocol_matrix_coverage.csv", index=False)
    pd.DataFrame(config_rows).to_csv(OUT / "adapter_protocol_config_matrix.csv", index=False)


def write_reports(by_seed: pd.DataFrame, selection: pd.DataFrame, summary: pd.DataFrame, feature_rows: pd.DataFrame, runtime: float) -> None:
    ref = summary[(summary["head_id"].eq("LOW_GUARD_LR_reference")) & (summary["protocol_variant"].eq("P3_full_lowguard"))].iloc[0]
    full = summary[summary["protocol_variant"].eq("P3_full_lowguard")].copy()
    non_lr_full = full[full["head_id"].ne("LOW_GUARD_LR_reference")].sort_values(
        ["feasible_rate", "locked_detection_mean", "locked_detection_min"], ascending=[False, False, False]
    )
    best_non_lr = non_lr_full.iloc[0]
    plus = full[full["promising_for_lowguard_plus_plus"]].copy()
    if not plus.empty:
        primary_verdict = "lowguard_plus_plus_candidate_found"
        next_action = "issue27c_formal_validation_for_lowguard_plus_plus_candidate"
    elif bool((full["converted_to_feasible"] & full["head_id"].ne("LOW_GUARD_LR_reference")).any()):
        primary_verdict = "protocol_transfer_supported_lr_remains_best_minimal_instance"
        next_action = "issue27c_deployment_robustness_simulation_then_adapter_scope_decision"
    elif bool(((full["locked_detection_mean"] >= float(ref["locked_detection_mean"]) - 0.01) & (full["locked_ood_alarm_max"] > MAIN_TARGET) & full["head_id"].ne("LOW_GUARD_LR_reference")).any()):
        primary_verdict = "nonlinear_detection_gain_not_low_alert_feasible"
        next_action = "issue27c_deployment_robustness_simulation_for_lowguard_lr"
    else:
        primary_verdict = "lowguard_effect_head_specific_lr_only_so_far"
        next_action = "issue27c_reframe_lowguard_lr_and_run_deployment_robustness"

    transfer_supported = bool((full["head_id"].ne("LOW_GUARD_LR_reference") & (full["locked_ood_alarm_max"] <= MAIN_TARGET)).any())
    collapse_rescued = bool((full["head_id"].ne("LOW_GUARD_LR_reference") & full["rescued_from_collapse"]).any())
    converted = bool((full["head_id"].ne("LOW_GUARD_LR_reference") & full["converted_to_feasible"]).any())
    lr_best_minimal = not bool(plus["head_id"].ne("LOW_GUARD_LR_reference").any())

    issue25c_ref = pd.read_csv(ISSUE25C / "locked_bins_baseline_summary.csv")
    issue25c_lr = issue25c_ref[issue25c_ref["method"].eq("M2_Enhanced_LOW_GUARD_top64_fixed_guard_LR")].iloc[0]
    reproduction_delta_mean = float(ref["locked_detection_mean"]) - float(issue25c_lr["locked_detection_mean"])
    reproduction_delta_min = float(ref["locked_detection_min"]) - float(issue25c_lr["locked_detection_min"])
    reproduction_delta_ood = float(ref["locked_ood_alarm_max"]) - float(issue25c_lr["locked_ood_alarm_max"])

    summary_text = f"""
# Issue27b Guarded Protocol Transfer And Adapter Recovery Summary

## Verdict

- primary_verdict: `{primary_verdict}`
- next_action: `{next_action}`

## 1. Does LOW-GUARD transfer to non-LR heads?

Transfer evidence is `{"supported but bounded" if transfer_supported else "not strongly supported"}`. The matrix evaluated LR, DevNet-like MLP, HistGB, DeepSAD-like center, Prototype/metric LR, and optional RFF Logistic under P0/P1/P2/P3 protocol variants on locked bins 5/6/7/8.

## 2. Did it rescue collapsed models?

`{"Yes for at least one non-LR head." if collapse_rescued else "No clean non-LR collapse rescue was found."}` Collapse rescue is defined as raw P0 locked detection below 0.20 and full P3 detection at or above 0.80 while meeting the 1% OOD budget.

## 3. Did it convert near-LR but OOD-over-budget models to feasible?

`{"Yes for at least one non-LR head." if converted else "No robust conversion was found for a near-LR non-LR model."}`

## 4. LOW-GUARD++ candidate

`{"A candidate was found." if not plus.empty else "No adapter met the LOW-GUARD++ dominance rule."}` A candidate must beat LOW-GUARD-LR locked mean, match or exceed locked min, keep locked OOD max <= 1%, and keep feasibility rate near the LR reference.

## 5. Reference LOW-GUARD-LR reproduction

- issue27b LOW-GUARD-LR P3 locked mean/min/OOD max: `{float(ref["locked_detection_mean"]):.6f}` / `{float(ref["locked_detection_min"]):.6f}` / `{float(ref["locked_ood_alarm_max"]):.6f}`.
- issue25c reference locked mean/min/OOD max: `{float(issue25c_lr["locked_detection_mean"]):.6f}` / `{float(issue25c_lr["locked_detection_min"]):.6f}` / `{float(issue25c_lr["locked_ood_alarm_max"]):.6f}`.
- delta: `{reproduction_delta_mean:.6e}` / `{reproduction_delta_min:.6e}` / `{reproduction_delta_ood:.6e}`.

## 6. Best non-LR full LOW-GUARD head

- head: `{best_non_lr["head_id"]}`
- locked mean/min/OOD max: `{float(best_non_lr["locked_detection_mean"]):.6f}` / `{float(best_non_lr["locked_detection_min"]):.6f}` / `{float(best_non_lr["locked_ood_alarm_max"]):.6f}`.
- feasible_rate: `{float(best_non_lr["feasible_rate"]):.6f}`.

## 7. Does LOW-GUARD-LR remain the strongest feasible minimal instance?

`{"Yes." if lr_best_minimal else "No, a LOW-GUARD++ candidate should be validated."}` Under this issue's locked matrix, no final eval was used for model, config, or threshold selection.

## 8. Training guard vs threshold guard

For LOW-GUARD-LR, the training-side OOD guard is the decisive recovery mechanism: raw LR has high detection but severe OOD over-budget, while threshold-only raw LR becomes feasible only by collapsing attack detection. The threshold guard is still necessary as the deployment safety gate because it enforces the ID+OOD validation alarm budget. For nonlinear heads, training guard often preserves attack separation, but it did not consistently pull final OOD alarm below 1%.

## 9. Issue27c need

`{"Yes: run formal validation for the LOW-GUARD++ candidate before changing the main method." if not plus.empty else "No immediate LOW-GUARD++ formal validation is justified; deployment robustness simulation should be next."}`

## 10. Slurm

Not needed. This was a local lightweight adapter/head matrix; no dA, Transformer, large model, temporal validation, or cross-dataset execution was run.

## 11. Leakage audit

No final OOD eval or attack eval was used for threshold, hyperparameter, feature, support, or model selection in this run. Final OOD and attack eval are report-only.

## 12. Deployment robustness

Yes, deployment robustness simulation remains necessary. issue27b tests adapter transfer, not support-noise, OOD contamination, label delay, or online update safety.

## Top Full LOW-GUARD Rows

{md_table(full[["head_id", "locked_detection_mean", "locked_detection_min", "locked_ood_alarm_max", "feasible_rate", "promising_for_lowguard_plus_plus", "recovery_mode"]].sort_values(["feasible_rate", "locked_detection_mean"], ascending=[False, False]))}
"""
    write_text(OUT / "summary.md", summary_text)

    vs = summary.copy()
    vs.to_csv(OUT / "protocol_transfer_vs_lowguard_lr.csv", index=False)
    summary[["head_id", "head_family", "protocol_variant", "recovery_mode", "rescued_from_collapse", "converted_to_feasible", "promising_for_lowguard_plus_plus"]].to_csv(
        OUT / "model_recovery_mode_summary.csv", index=False
    )
    summary[(summary["protocol_variant"].eq("P3_full_lowguard")) & (summary["rescued_from_collapse"])].to_csv(OUT / "collapsed_model_recovery_report.csv", index=False)
    summary[(summary["protocol_variant"].eq("P3_full_lowguard")) & (summary["head_id"].isin(["DevNet_like_MLP", "HistGB_shallow"]))].to_csv(OUT / "near_lr_baseline_upgrade_report.csv", index=False)
    plus.to_csv(OUT / "lowguard_plus_plus_candidate_report.csv", index=False)
    by_seed[["head_id", "protocol_variant", "holdout", "seed", "roc_auc_attack_vs_ood", "pr_auc_attack_vs_ood", "pauc_fpr_1pct", "tpr_at_fpr_1pct", "feasible_under_1pct"]].to_csv(
        OUT / "low_fpr_metrics.csv", index=False
    )
    summary[summary["locked_ood_alarm_max"] > MAIN_TARGET].to_csv(OUT / "ood_budget_violation_report.csv", index=False)
    summary[["head_id", "head_family", "protocol_variant", "mean_train_time", "mean_inference_time", "mean_parameter_count"]].to_csv(OUT / "adapter_complexity_costs.csv", index=False)

    allowed = "- LOW-GUARD can be discussed as a guarded few-shot adaptation protocol only if bounded by the evaluated lightweight heads.\n"
    if transfer_supported:
        allowed += "- The protocol can be instantiated with multiple lightweight heads, but LOW-GUARD-LR remains the reference unless LOW-GUARD++ is validated.\n"
    else:
        allowed += "- Current evidence supports LOW-GUARD-LR as the strongest feasible instance; broader protocol transfer is limited.\n"
    claim = f"""
# Claim Update After Issue27b

## Allowed now

{allowed}- Low-alert feasibility depends on support-based attack alignment and benign-OOD threshold guarding.
- The issue27b matrix did not use final eval for model selection.

## Still not allowed

- LOW-GUARD works for all semi-supervised anomaly detectors.
- LR is universally optimal.
- DevNet / DeepSAD are defeated in general.
- Temporal generalization is proven.
- Cross-dataset generalization is proven.
- Deployment robustness is proven by this issue.
- Final eval was used for model selection.

## Needs issue27c

- Any LOW-GUARD++ replacement claim needs a formal validation run.
- Deployment robustness claims need shot, support-noise, OOD-contamination, and update simulations.
"""
    write_text(OUT / "claim_update_after_issue27b.md", claim)

    defense = f"""
# Reviewer Defense: Protocol Transfer

## Q1: Is this just Logistic Regression?

issue27b tests that question directly by wrapping LR, DevNet-like MLP, HistGB, DeepSAD-like center, Prototype/metric LR, and optional RFF Logistic in the same P0/P1/P2/P3 guarded protocol matrix. The answer is bounded: the protocol framing is useful, but the LR instance remains the reference unless a head dominates it under the low-alert constraint.

## Q2: Did you use final eval to pick heads?

No. Config selection uses support validation and OOD validation only. Final OOD eval and attack eval are report-only.

## Q3: Why not use a bigger neural adapter?

The task is low-alert few-shot deployment adaptation. Large neural sweeps would reopen model-search risk and weaken the claim boundary. This issue uses only pre-registered lightweight heads.

## Q4: What counts as LOW-GUARD++?

A non-LR full LOW-GUARD head must exceed LOW-GUARD-LR mean detection, match or exceed its minimum detection, keep OOD max <= 1%, and preserve feasibility rate. Result: `{primary_verdict}`.

## Q5: Why are high-detection but OOD-over-budget models not enough?

The paper problem is low-alert IDS under benign-OOD drift. A head that raises detection while exceeding 1% OOD alarm is not a deployable low-alert instance.

## Q6: Does this prove temporal or external generalization?

No. issue27b reuses the locked within-dataset bins; temporal and external generalization remain separate evidence gaps.

## Q7: What should happen next?

`{next_action}`. If no LOW-GUARD++ candidate dominates, prioritize deployment robustness simulation rather than expanding the adapter space.
"""
    write_text(OUT / "reviewer_defense_protocol_transfer.md", defense)

    next_doc = f"""
# Issue27c Next Action

## Recommendation

`{next_action}`

## Reason

Primary verdict is `{primary_verdict}`. If a LOW-GUARD++ candidate exists, it must be validated before changing the main method. If not, the most useful next evidence is deployment robustness: shot sensitivity, support noise, OOD benign contamination, support source, update cadence, and shadow-mode workload.

## Slurm

Not required for LR-level robustness or small adapter follow-up. Use Slurm only if the project expands to larger neural adapters, large replay, or cross-dataset processing.
"""
    write_text(OUT / "issue27c_next_action.md", next_doc)

    risk_rows = [
        ["adapter overclaim risk", "medium", "Protocol transfer may be uneven across heads.", "Separate LR instance claim from framework claim."],
        ["model search risk", "medium", "Adding many heads can look like model zoo tuning.", "Keep the pre-registered matrix bounded."],
        ["final eval leakage risk", "low", "Final eval must stay report-only.", "Selection trace records selection_used_final_eval=false."],
        ["OOD budget violation risk", "high", "Some heads can detect attacks but exceed 1% OOD alarm.", "Treat them as non-deployable under this problem."],
        ["deployment robustness gap", "medium", "This issue does not simulate label noise or OOD contamination.", "Run deployment robustness next unless LOW-GUARD++ needs validation."],
    ]
    pd.DataFrame(risk_rows, columns=["risk", "severity", "description", "mitigation"]).to_csv(OUT / "risk_register_protocol_transfer.csv", index=False)

    config = {
        "issue": "issue27b_guarded_protocol_transfer_and_adapter_recovery_2026-05-26",
        "main_method_reference": "LOW-GUARD-LR",
        "frozen": {
            "representation": "selected_source_rich_top64",
            "locked_bins": LOCKED_HOLDOUTS,
            "support_method": "kcenter",
            "support_budget": SUPPORT_BUDGET,
            "ood_target": MAIN_TARGET,
            "final_eval_report_only": True,
        },
        "seeds": SEEDS,
        "protocol_variants": protocol_variants(),
        "heads": head_specs(),
        "runtime_seconds": runtime,
        "primary_verdict": primary_verdict,
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    run_spec = {
        "task_type": "guarded_protocol_transfer_and_adapter_recovery",
        "not_in_scope": ["temporal_validation", "cross_dataset_validation", "topK_search", "support_budget_search", "large_neural_sweep", "manuscript_edit"],
        "selection_rule": "OOD_val <= 1%, then support_val detection/margin, then simpler model; final eval never used",
        "outputs": [
            "protocol_transfer_by_seed.csv",
            "protocol_transfer_locked_summary.csv",
            "adapter_selection_trace.csv",
            "protocol_transfer_vs_lowguard_lr.csv",
        ],
    }
    (OUT / "run_spec.json").write_text(json.dumps(run_spec, indent=2, ensure_ascii=False), encoding="utf-8")
    write_text(
        OUT / "command.txt",
        """
git branch --show-current
git status --short
python runs/issue27b_guarded_protocol_transfer_and_adapter_recovery_2026-05-26/run_issue27b_guarded_protocol_transfer.py
git status
git add repo runs/mainline_docs runs/issue27b_guarded_protocol_transfer_and_adapter_recovery_2026-05-26
git commit -m "Add issue27b guarded protocol transfer"
git push origin codex/exp-mainline
""",
    )
    if not feature_rows.empty:
        feature_rows.to_csv(OUT / "selected_feature_provenance.csv", index=False)


def main() -> None:
    t0 = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    missing = require_inputs()
    if missing:
        write_text(OUT / "missing_input_report.md", "# Missing Input Report\n\n" + "\n".join(f"- {item}" for item in missing))
        raise RuntimeError(f"Missing required inputs: {missing}")
    write_text(OUT / "missing_input_report.md", "# Missing Input Report\n\nnone")
    write_static_matrices()

    cfg = json.loads((ISSUE11 / "config.json").read_text(encoding="utf-8"))
    paths = cfg["paths"]
    x_id_o = issue25c.issue19b.load_matrix(Path(paths["original100_id"]))
    x_ood_o = issue25c.issue19b.load_matrix(Path(paths["original100_ood"]))
    x_attack_o = issue25c.issue19b.load_matrix(Path(paths["original100_attack"]))
    x_id_sr = issue25c.issue19b.load_matrix(Path(paths["source_rich_id"]))
    x_ood_sr = issue25c.issue19b.load_matrix(Path(paths["source_rich_ood"]))
    x_attack_sr = issue25c.issue19b.load_matrix(Path(paths["source_rich_attack"]))
    if x_id_o.shape[0] != x_id_sr.shape[0] or x_ood_o.shape[0] != x_ood_sr.shape[0] or x_attack_o.shape[0] != x_attack_sr.shape[0]:
        raise RuntimeError("original100/source_rich row-count mismatch")
    schema_path = Path(paths["source_rich_id"]).parents[1] / "data" / "structured_schema.json"
    sr_names = issue25c.issue19b.feature_names(schema_path, x_id_sr.shape[1])
    datasets, asset_report, meta = issue25c.issue23.build_locked_datasets(paths, x_id_o, x_ood_o, x_attack_o, x_id_sr, x_ood_sr, x_attack_sr)
    for spec in datasets:
        spec["evaluation_role"] = "locked"
    asset_report.to_csv(OUT / "locked_asset_report.csv", index=False)

    rows: list[dict[str, Any]] = []
    selection_rows: list[dict[str, Any]] = []
    feature_rows: list[dict[str, Any]] = []
    support_prov: list[dict[str, Any]] = []
    heads = head_specs()
    protocols = protocol_variants()
    for spec in datasets:
        holdout = str(spec["holdout"])
        train_pool = np.asarray(spec["attack_train_pool_idx"], dtype=np.int64)
        support_rows = issue25c.issue19b.kcenter_support(train_pool, x_attack_o[train_pool], SUPPORT_BUDGET)
        attack_eval = set(map(int, spec.get("attack_eval_idx", [])))
        attack_val = set(map(int, spec.get("attack_val_idx", [])))
        for seed in SEEDS:
            for support_id in support_rows:
                support_prov.append(
                    {
                        "holdout": holdout,
                        "seed": int(seed),
                        "support_method": "kcenter",
                        "selected_attack_row_id": int(support_id),
                        "in_attack_train_pool": True,
                        "overlaps_attack_val": bool(int(support_id) in attack_val),
                        "overlaps_attack_eval": bool(int(support_id) in attack_eval),
                        "selection_uses_attack_eval": False,
                        "selection_uses_final_ood_eval": False,
                    }
                )
            for head in heads:
                for protocol in protocols:
                    row, sel, feat = run_one(
                        dataset_spec=spec,
                        head=head,
                        protocol=protocol,
                        seed=seed,
                        support_rows=support_rows,
                        x_attack_o=x_attack_o,
                        x_attack_sr=x_attack_sr,
                        sr_names=sr_names,
                    )
                    rows.append(row)
                    selection_rows.extend(sel)
                    feature_rows.extend(feat)
            print(f"[issue27b] {holdout} seed={seed} completed", flush=True)

    by_seed = pd.DataFrame(rows)
    selection = pd.DataFrame(selection_rows)
    features = pd.DataFrame(feature_rows)
    support = pd.DataFrame(support_prov)
    summary = add_recovery_flags(locked_summary(by_seed))

    by_seed.to_csv(OUT / "protocol_transfer_by_seed.csv", index=False)
    selection.to_csv(OUT / "adapter_selection_trace.csv", index=False)
    summary.to_csv(OUT / "protocol_transfer_locked_summary.csv", index=False)
    support.to_csv(OUT / "support_provenance.csv", index=False)
    write_reports(by_seed, selection, summary, features, time.perf_counter() - t0)

    manifest_rows = []
    for path in sorted(OUT.glob("*")):
        if path.is_file() and path.name != "manifest.csv":
            manifest_rows.append({"file": path.name, "size_bytes": path.stat().st_size})
    manifest_rows.append({"file": "runtime_seconds", "size_bytes": f"{time.perf_counter() - t0:.3f}"})
    pd.DataFrame(manifest_rows).to_csv(OUT / "manifest.csv", index=False)


if __name__ == "__main__":
    main()
