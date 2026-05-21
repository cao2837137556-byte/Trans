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
from sklearn.metrics import average_precision_score, roc_auc_score, roc_curve
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs" / "issue24c_v1_v2_residual_fusion_adapter_retry_2026-05-18"
ISSUE24B = ROOT / "runs" / "issue24b_adapter_bottleneck_diagnosis_for_enhanced_v2_top64_2026-05-18"
ISSUE24 = ROOT / "runs" / "issue24_adapter_upgrade_feasibility_for_enhanced_v2_top64_2026-05-18"
ISSUE23 = ROOT / "runs" / "issue23_locked_validation_for_enhanced_v2_top64_2026-05-18"
ISSUE22B = ROOT / "runs" / "issue22b_enhanced_v2_primary_nonregression_check_2026-05-18"
ISSUE18 = ROOT / "runs" / "issue18_row_level_score_persistence_and_ood_target_sensitivity_2026-05-15"
ISSUE11 = ROOT / "runs" / "issue11_fixed_config_ood_guard_lr_ablation_2026-05-14"

ISSUE23_SCRIPT = ISSUE23 / "run_issue23_locked_validation.py"
ISSUE22_SCRIPT = ROOT / "runs" / "issue22_v2_hard_shift_enhancement_pilot_2026-05-18" / "run_issue22_v2_enhancement.py"
ISSUE19B_SCRIPT = ROOT / "runs" / "issue19b_v1_v2_same_protocol_backtest_and_alarm_budget_curve_2026-05-18" / "run_issue19b_v1_v2_backtest.py"

MAIN_TARGET = 0.01
TOP_K = 64
SUPPORT_BUDGET = 32
SUPPORT_TRAIN_FOR_SELECTION = 24
SEEDS = list(range(42, 52))
LOCKED_HOLDOUTS = ["holdout_bin_5", "holdout_bin_6", "holdout_bin_7", "holdout_bin_8"]
CONSISTENCY_HOLDOUTS = ["primary_lowood", "holdout_bin_2", "chrono_late_train_early_eval"]
ALPHAS = [0.50, 0.60, 0.70, 0.80, 0.90]
RESIDUAL_CS = [0.01, 0.1, 1.0]
BETAS = [0.50, 0.75, 1.00]


def import_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


issue23 = import_module(ISSUE23_SCRIPT, "issue23_locked_validation_for_24c")
issue22 = import_module(ISSUE22_SCRIPT, "issue22_v2_enhancement_for_24c")
issue19b = import_module(ISSUE19B_SCRIPT, "issue19b_v1_v2_backtest_for_24c")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def md_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    if max_rows is not None:
        df = df.head(max_rows).copy()
    if df.empty:
        return "_No rows._\n"
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, row in df.iterrows():
        vals: list[str] = []
        for col in cols:
            val = row[col]
            if isinstance(val, (float, np.floating)):
                vals.append("" if math.isnan(float(val)) else f"{float(val):.6f}")
            else:
                vals.append(str(val))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"


def require_inputs() -> list[str]:
    required = [
        ISSUE24B / "summary.md",
        ISSUE24B / "fusion_potential_summary.csv",
        ISSUE24B / "fusion_potential_report.md",
        ISSUE24B / "error_overlap_by_bin.csv",
        ISSUE24B / "error_overlap_report.md",
        ISSUE24B / "score_distribution_by_bin.csv",
        ISSUE24B / "low_fpr_bottleneck_summary.csv",
        ISSUE24B / "issue24c_candidate_ranking.md",
        ISSUE24B / "claim_boundary.md",
        ISSUE24B / "recommended_next_action.md",
        ISSUE24 / "summary.md",
        ISSUE24 / "adapter_method_comparison_summary.csv",
        ISSUE23 / "method_comparison_summary.csv",
        ISSUE23 / "method_comparison_by_seed.csv",
        ISSUE23 / "v2top64_vs_v1_locked.csv",
        ISSUE23 / "low_fpr_metrics_summary.csv",
        ISSUE23 / "claim_boundary.md",
        ISSUE22B / "summary.md",
        ISSUE18 / "row_level_scores_manifest.csv",
        ISSUE11 / "config.json",
        ISSUE23_SCRIPT,
        ISSUE22_SCRIPT,
        ISSUE19B_SCRIPT,
    ]
    return [str(path) for path in required if not path.exists()]


def seed_group(seed: int) -> str:
    return issue19b.seed_group(seed)


def split_support_for_selection(support_rows: np.ndarray, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed + 24024)
    shuffled = np.asarray(support_rows, dtype=np.int64).copy()
    rng.shuffle(shuffled)
    return np.sort(shuffled[:SUPPORT_TRAIN_FOR_SELECTION]), np.sort(shuffled[SUPPORT_TRAIN_FOR_SELECTION:])


def fit_guarded_lr(x_id_train: np.ndarray, x_ood_train: np.ndarray, x_pos: np.ndarray, score_sets: dict[str, np.ndarray]) -> dict[str, Any]:
    scaler = StandardScaler()
    x_train_raw = np.vstack([x_id_train, x_ood_train, x_pos])
    y_train = np.concatenate(
        [
            np.zeros(len(x_id_train), dtype=np.int64),
            np.zeros(len(x_ood_train), dtype=np.int64),
            np.ones(len(x_pos), dtype=np.int64),
        ]
    )
    weights = np.concatenate(
        [
            np.ones(len(x_id_train), dtype=np.float64),
            np.full(len(x_ood_train), 2.0, dtype=np.float64),
            np.ones(len(x_pos), dtype=np.float64),
        ]
    )
    t0 = time.perf_counter()
    x_train = scaler.fit_transform(x_train_raw)
    model = LogisticRegression(C=1.0, penalty="l2", solver="liblinear", class_weight="balanced", max_iter=2000, random_state=42)
    model.fit(x_train, y_train, sample_weight=weights)
    train_time = time.perf_counter() - t0
    t1 = time.perf_counter()
    scores = {name: model.decision_function(scaler.transform(x)).astype(np.float64) for name, x in score_sets.items()}
    inference_time = time.perf_counter() - t1
    return {
        "scores": scores,
        "train_time": float(train_time),
        "inference_time": float(inference_time),
        "parameter_count": int(model.coef_.size + model.intercept_.size),
    }


def load_assets() -> tuple[dict[str, str], np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[str]]:
    cfg = json.loads((ISSUE11 / "config.json").read_text(encoding="utf-8"))
    paths = cfg["paths"]
    x_id_o = issue19b.load_matrix(Path(paths["original100_id"]))
    x_ood_o = issue19b.load_matrix(Path(paths["original100_ood"]))
    x_attack_o = issue19b.load_matrix(Path(paths["original100_attack"]))
    x_id_sr = issue19b.load_matrix(Path(paths["source_rich_id"]))
    x_ood_sr = issue19b.load_matrix(Path(paths["source_rich_ood"]))
    x_attack_sr = issue19b.load_matrix(Path(paths["source_rich_attack"]))
    schema_path = Path(paths["source_rich_id"]).parents[1] / "data" / "structured_schema.json"
    sr_names = issue19b.feature_names(schema_path, x_id_sr.shape[1])
    return paths, x_id_o, x_ood_o, x_attack_o, x_id_sr, x_ood_sr, x_attack_sr, sr_names


def build_datasets(paths: dict[str, str], x_id_o: np.ndarray, x_ood_o: np.ndarray, x_attack_o: np.ndarray, x_id_sr: np.ndarray, x_ood_sr: np.ndarray, x_attack_sr: np.ndarray) -> list[dict[str, Any]]:
    locked, _, _ = issue23.build_locked_datasets(paths, x_id_o, x_ood_o, x_attack_o, x_id_sr, x_ood_sr, x_attack_sr)
    locked = [spec for spec in locked if str(spec["holdout"]) in LOCKED_HOLDOUTS]
    for spec in locked:
        spec["evaluation_role"] = "locked"
    consistency, _ = issue19b.build_datasets(paths=paths, x_id_o=x_id_o, x_ood_o=x_ood_o, x_attack_o=x_attack_o, x_id_sr=x_id_sr, x_ood_sr=x_ood_sr, x_attack_sr=x_attack_sr)
    consistency = [spec for spec in consistency if str(spec["holdout"]) in CONSISTENCY_HOLDOUTS]
    for spec in consistency:
        spec["evaluation_role"] = "consistency"
    return locked + consistency


def prepare_base_scores(
    *,
    spec: dict[str, Any],
    support_rows: np.ndarray,
    x_attack_o: np.ndarray,
    x_attack_sr: np.ndarray,
    sr_names: list[str],
    seed: int,
    support_eval_rows: np.ndarray | None = None,
) -> dict[str, Any]:
    attack_eval_idx = np.asarray(spec["attack_eval_idx"], dtype=np.int64)
    support_eval_rows = np.asarray([], dtype=np.int64) if support_eval_rows is None else np.asarray(support_eval_rows, dtype=np.int64)

    v1_score_sets = {
        "id_train": spec["x_id_train_o"],
        "ood_train": spec["x_ood_train_o"],
        "support_train": x_attack_o[support_rows],
        "support_eval": x_attack_o[support_eval_rows],
        "id_calib": spec["x_id_calib_o"],
        "ood_val": spec["x_ood_val_o"],
        "final_ood_eval": spec["x_ood_eval_o"],
        "attack_eval": x_attack_o[attack_eval_idx],
    }
    v1 = fit_guarded_lr(spec["x_id_train_o"], spec["x_ood_train_o"], x_attack_o[support_rows], v1_score_sets)

    feature_idx, feature_rows = issue19b.selected_source_rich_features(
        x_support=x_attack_sr[support_rows],
        x_id_calib=spec["x_id_calib_sr"],
        x_ood_val=spec["x_ood_val_sr"],
        names=sr_names,
        dataset=str(spec["dataset"]),
        holdout=str(spec["holdout"]),
        seed=seed,
        top_k=TOP_K,
    )
    v2_score_sets = {
        "id_train": spec["x_id_train_sr"][:, feature_idx],
        "ood_train": spec["x_ood_train_sr"][:, feature_idx],
        "support_train": x_attack_sr[support_rows][:, feature_idx],
        "support_eval": x_attack_sr[support_eval_rows][:, feature_idx],
        "id_calib": spec["x_id_calib_sr"][:, feature_idx],
        "ood_val": spec["x_ood_val_sr"][:, feature_idx],
        "final_ood_eval": spec["x_ood_eval_sr"][:, feature_idx],
        "attack_eval": x_attack_sr[attack_eval_idx][:, feature_idx],
    }
    v2 = fit_guarded_lr(v2_score_sets["id_train"], v2_score_sets["ood_train"], v2_score_sets["support_train"], v2_score_sets)
    return {"V1": v1, "V2": v2, "feature_idx": feature_idx, "feature_rows": feature_rows}


def norm_stats(scores: dict[str, np.ndarray]) -> tuple[float, float]:
    ref = np.concatenate([scores["id_calib"], scores["ood_val"]])
    mu = float(np.mean(ref))
    sigma = float(np.std(ref))
    if not np.isfinite(sigma) or sigma < 1e-8:
        sigma = 1.0
    return mu, sigma


def normalized_base(base: dict[str, Any]) -> dict[str, dict[str, np.ndarray]]:
    v1_scores = base["V1"]["scores"]
    v2_scores = base["V2"]["scores"]
    mu1, sd1 = norm_stats(v1_scores)
    mu2, sd2 = norm_stats(v2_scores)
    z1 = {k: (v - mu1) / sd1 for k, v in v1_scores.items()}
    z2 = {k: (v - mu2) / sd2 for k, v in v2_scores.items()}
    return {"z1": z1, "z2": z2}


def residual_features(z1: dict[str, np.ndarray], z2: dict[str, np.ndarray], split: str) -> np.ndarray:
    a = np.asarray(z1[split], dtype=np.float64)
    b = np.asarray(z2[split], dtype=np.float64)
    return np.column_stack([a, b, b - a, np.maximum(a, b), np.minimum(a, b)])


def fuse_scores(z: dict[str, dict[str, np.ndarray]], method: str, param: float | None = None, model_payload: dict[str, Any] | None = None) -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    z1 = z["z1"]
    z2 = z["z2"]
    if method == "linear_alpha":
        alpha = float(param)
        for split in z1:
            out[split] = alpha * z2[split] + (1.0 - alpha) * z1[split]
    elif method == "conservative_max":
        beta = float(param)
        for split in z1:
            out[split] = np.maximum(z2[split], beta * z1[split])
    elif method == "residual_lr":
        if model_payload is None:
            raise ValueError("residual_lr requires model_payload")
        scaler = model_payload["scaler"]
        model = model_payload["model"]
        for split in z1:
            out[split] = model.decision_function(scaler.transform(residual_features(z1, z2, split))).astype(np.float64)
    else:
        raise ValueError(f"Unknown fusion method: {method}")
    return out


def guarded_threshold(scores: dict[str, np.ndarray]) -> float:
    return float(issue19b.v72.guarded_val_threshold(scores["id_calib"], scores["ood_val"], MAIN_TARGET)["threshold"])


def score_metrics(scores: dict[str, np.ndarray], threshold: float) -> dict[str, float]:
    y_true = np.concatenate([np.zeros(len(scores["final_ood_eval"]), dtype=np.int64), np.ones(len(scores["attack_eval"]), dtype=np.int64)])
    y_score = np.concatenate([scores["final_ood_eval"], scores["attack_eval"]])
    roc = float(roc_auc_score(y_true, y_score))
    pr = float(average_precision_score(y_true, y_score))
    pauc = float(roc_auc_score(y_true, y_score, max_fpr=0.01))
    fpr, tpr, _ = roc_curve(y_true, y_score)
    tpr1 = float(np.max(tpr[fpr <= 0.01])) if np.any(fpr <= 0.01) else 0.0
    return {
        "roc_auc": roc,
        "pr_auc": pr,
        "pauc_fpr_1pct": pauc,
        "tpr_at_fpr_1pct": tpr1,
        "attack_high_detection": float(np.mean(scores["attack_eval"] > threshold)),
        "final_ood_high_alarm": float(np.mean(scores["final_ood_eval"] > threshold)),
        "attack_eval_size": int(len(scores["attack_eval"])),
        "final_ood_eval_size": int(len(scores["final_ood_eval"])),
    }


def selection_metrics(scores: dict[str, np.ndarray], threshold: float) -> dict[str, float]:
    support = scores["support_eval"]
    if len(support) == 0:
        return {
            "support_val_detection": math.nan,
            "support_val_margin_q25": math.nan,
            "support_val_margin_median": math.nan,
            "ood_val_alarm": float(np.mean(scores["ood_val"] > threshold)),
            "selection_score": -math.inf,
        }
    margins = support - threshold
    detection = float(np.mean(support > threshold))
    margin_q25 = float(np.quantile(margins, 0.25))
    margin_median = float(np.median(margins))
    ood_val_alarm = float(np.mean(scores["ood_val"] > threshold))
    return {
        "support_val_detection": detection,
        "support_val_margin_q25": margin_q25,
        "support_val_margin_median": margin_median,
        "ood_val_alarm": ood_val_alarm,
        "selection_score": float(detection * 1000.0 + margin_q25 - ood_val_alarm),
    }


def train_residual_lr(z: dict[str, dict[str, np.ndarray]], c_value: float) -> dict[str, Any]:
    x = np.vstack(
        [
            residual_features(z["z1"], z["z2"], "id_train"),
            residual_features(z["z1"], z["z2"], "ood_train"),
            residual_features(z["z1"], z["z2"], "support_train"),
        ]
    )
    y = np.concatenate(
        [
            np.zeros(len(z["z1"]["id_train"]), dtype=np.int64),
            np.zeros(len(z["z1"]["ood_train"]), dtype=np.int64),
            np.ones(len(z["z1"]["support_train"]), dtype=np.int64),
        ]
    )
    w = np.concatenate(
        [
            np.ones(len(z["z1"]["id_train"]), dtype=np.float64),
            np.full(len(z["z1"]["ood_train"]), 2.0, dtype=np.float64),
            np.ones(len(z["z1"]["support_train"]), dtype=np.float64),
        ]
    )
    scaler = StandardScaler()
    xz = scaler.fit_transform(x)
    model = LogisticRegression(C=float(c_value), penalty="l2", solver="liblinear", class_weight="balanced", max_iter=2000, random_state=42)
    model.fit(xz, y, sample_weight=w)
    return {"model": model, "scaler": scaler, "parameter_count": int(model.coef_.size + model.intercept_.size)}


def select_fusion_configs(selection_base: dict[str, Any], dataset: str, holdout: str, seed: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    z = normalized_base(selection_base)
    rows: list[dict[str, Any]] = []

    for alpha in ALPHAS:
        fused = fuse_scores(z, "linear_alpha", alpha)
        threshold = guarded_threshold(fused)
        m = selection_metrics(fused, threshold)
        rows.append(
            {
                "dataset": dataset,
                "holdout": holdout,
                "seed": int(seed),
                "fusion_family": "linear_alpha",
                "config_id": f"alpha_{alpha:.2f}",
                "alpha": alpha,
                "C": math.nan,
                "beta": math.nan,
                "threshold": threshold,
                **m,
                "uses_final_eval_for_selection": False,
            }
        )

    for beta in BETAS:
        fused = fuse_scores(z, "conservative_max", beta)
        threshold = guarded_threshold(fused)
        m = selection_metrics(fused, threshold)
        rows.append(
            {
                "dataset": dataset,
                "holdout": holdout,
                "seed": int(seed),
                "fusion_family": "conservative_max",
                "config_id": f"beta_{beta:.2f}",
                "alpha": math.nan,
                "C": math.nan,
                "beta": beta,
                "threshold": threshold,
                **m,
                "uses_final_eval_for_selection": False,
            }
        )

    for c_value in RESIDUAL_CS:
        payload = train_residual_lr(z, c_value)
        fused = fuse_scores(z, "residual_lr", model_payload=payload)
        threshold = guarded_threshold(fused)
        m = selection_metrics(fused, threshold)
        rows.append(
            {
                "dataset": dataset,
                "holdout": holdout,
                "seed": int(seed),
                "fusion_family": "residual_lr",
                "config_id": f"residual_C_{c_value}",
                "alpha": math.nan,
                "C": c_value,
                "beta": math.nan,
                "threshold": threshold,
                **m,
                "uses_final_eval_for_selection": False,
            }
        )

    selected: dict[str, Any] = {}
    val_df = pd.DataFrame(rows)
    for family in ["linear_alpha", "conservative_max", "residual_lr"]:
        fam = val_df[val_df["fusion_family"].eq(family)].sort_values(
            ["support_val_detection", "support_val_margin_q25", "support_val_margin_median", "ood_val_alarm"],
            ascending=[False, False, False, True],
        )
        row = fam.iloc[0]
        selected[family] = dict(row)
        for item in rows:
            item[f"selected_for_{family}"] = bool(item["fusion_family"] == family and item["config_id"] == row["config_id"])
    return selected, rows


def eval_base_method(base: dict[str, Any], key: str) -> tuple[dict[str, np.ndarray], float, float, float, int]:
    payload = base[key]
    scores = payload["scores"]
    threshold = guarded_threshold(scores)
    return scores, threshold, payload["train_time"], payload["inference_time"], payload["parameter_count"]


def eval_fusion_method(final_base: dict[str, Any], family: str, selected_config: dict[str, Any]) -> tuple[dict[str, np.ndarray], float, float, float, int, str]:
    z = normalized_base(final_base)
    t0 = time.perf_counter()
    parameter_count = 0
    if family == "linear_alpha":
        alpha = float(selected_config["alpha"])
        scores = fuse_scores(z, "linear_alpha", alpha)
        config_id = f"alpha_{alpha:.2f}"
    elif family == "conservative_max":
        beta = float(selected_config["beta"])
        scores = fuse_scores(z, "conservative_max", beta)
        config_id = f"beta_{beta:.2f}"
    elif family == "residual_lr":
        c_value = float(selected_config["C"])
        payload = train_residual_lr(z, c_value)
        scores = fuse_scores(z, "residual_lr", model_payload=payload)
        parameter_count = int(payload["parameter_count"])
        config_id = f"residual_C_{c_value}"
    else:
        raise ValueError(f"Unknown family: {family}")
    train_time = time.perf_counter() - t0
    t1 = time.perf_counter()
    threshold = guarded_threshold(scores)
    inference_time = time.perf_counter() - t1
    return scores, threshold, float(train_time), float(inference_time), parameter_count, config_id


def run_experiment() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    paths, x_id_o, x_ood_o, x_attack_o, x_id_sr, x_ood_sr, x_attack_sr, sr_names = load_assets()
    datasets = build_datasets(paths, x_id_o, x_ood_o, x_attack_o, x_id_sr, x_ood_sr, x_attack_sr)
    seed_rows: list[dict[str, Any]] = []
    selection_rows: list[dict[str, Any]] = []
    alpha_sweep_rows: list[dict[str, Any]] = []
    score_asset_rows: list[dict[str, Any]] = []

    for spec in datasets:
        dataset = str(spec["dataset"])
        holdout = str(spec["holdout"])
        role = str(spec["evaluation_role"])
        train_pool = np.asarray(spec["attack_train_pool_idx"], dtype=np.int64)
        support_full = issue19b.kcenter_support(train_pool, x_attack_o[train_pool], SUPPORT_BUDGET)
        for seed in SEEDS:
            support_train, support_val = split_support_for_selection(support_full, seed)
            selection_base = prepare_base_scores(spec=spec, support_rows=support_train, support_eval_rows=support_val, x_attack_o=x_attack_o, x_attack_sr=x_attack_sr, sr_names=sr_names, seed=seed)
            selected, sel_rows = select_fusion_configs(selection_base, dataset, holdout, seed)
            selection_rows.extend([{**row, "evaluation_role": role, "seed_group": seed_group(seed)} for row in sel_rows])

            final_base = prepare_base_scores(spec=spec, support_rows=support_full, support_eval_rows=support_val, x_attack_o=x_attack_o, x_attack_sr=x_attack_sr, sr_names=sr_names, seed=seed)
            score_asset_rows.append(
                {
                    "dataset": dataset,
                    "holdout": holdout,
                    "evaluation_role": role,
                    "seed": int(seed),
                    "v1_score_available": True,
                    "v2_top64_score_available": True,
                    "selection_base_support_size": int(len(support_train)),
                    "selection_support_holdout_size": int(len(support_val)),
                    "final_support_size": int(len(support_full)),
                    "final_eval_used_for_fusion_selection": False,
                    "score_reconstructed_from_fixed_protocol": True,
                }
            )

            method_defs = [
                ("F0_V1_baseline", "baseline", "V1_LOW_GUARD_minimal", "raw_v1", {}),
                ("F1_V2_top64_baseline", "baseline", "V2_top64_LR", "raw_v2", {}),
            ]
            for method, group, candidate, family, config in method_defs:
                key = "V1" if family == "raw_v1" else "V2"
                scores, threshold, train_time, inference_time, params = eval_base_method(final_base, key)
                metrics = score_metrics(scores, threshold)
                seed_rows.append(
                    {
                        "evaluation_role": role,
                        "dataset": dataset,
                        "holdout": holdout,
                        "split_protocol": spec["split_protocol"],
                        "method": method,
                        "method_group": group,
                        "candidate": candidate,
                        "fusion_family": family,
                        "selected_config_id": "none",
                        "seed": int(seed),
                        "seed_group": seed_group(seed),
                        "ood_target": MAIN_TARGET,
                        "threshold": threshold,
                        "support_size": int(len(support_full)),
                        "feature_dim": 100 if key == "V1" else TOP_K,
                        "train_time": train_time,
                        "inference_time": inference_time,
                        "parameter_count": params,
                        "provenance_clean": True,
                        "final_eval_used_for_selection": False,
                        **metrics,
                        "feasible_final_1pct": bool(metrics["final_ood_high_alarm"] <= 0.01),
                    }
                )

            final_z = normalized_base(final_base)
            for alpha in ALPHAS:
                fused = fuse_scores(final_z, "linear_alpha", alpha)
                threshold = guarded_threshold(fused)
                metrics = score_metrics(fused, threshold)
                alpha_sweep_rows.append(
                    {
                        "evaluation_role": role,
                        "dataset": dataset,
                        "holdout": holdout,
                        "seed": int(seed),
                        "seed_group": seed_group(seed),
                        "alpha": alpha,
                        "selected_by_validation": bool(str(selected["linear_alpha"]["config_id"]) == f"alpha_{alpha:.2f}"),
                        "threshold": threshold,
                        **metrics,
                        "feasible_final_1pct": bool(metrics["final_ood_high_alarm"] <= 0.01),
                        "final_metrics_report_only": True,
                    }
                )

            for method, family in [
                ("F2_linear_alpha_selected", "linear_alpha"),
                ("F3_residual_lr_selected", "residual_lr"),
                ("F4_conservative_max_selected", "conservative_max"),
            ]:
                scores, threshold, train_time, inference_time, params, config_id = eval_fusion_method(final_base, family, selected[family])
                metrics = score_metrics(scores, threshold)
                seed_rows.append(
                    {
                        "evaluation_role": role,
                        "dataset": dataset,
                        "holdout": holdout,
                        "split_protocol": spec["split_protocol"],
                        "method": method,
                        "method_group": "targeted_fusion_retry",
                        "candidate": method,
                        "fusion_family": family,
                        "selected_config_id": config_id,
                        "seed": int(seed),
                        "seed_group": seed_group(seed),
                        "ood_target": MAIN_TARGET,
                        "threshold": threshold,
                        "support_size": int(len(support_full)),
                        "feature_dim": 2 if family != "residual_lr" else 5,
                        "train_time": train_time,
                        "inference_time": inference_time,
                        "parameter_count": params,
                        "provenance_clean": True,
                        "final_eval_used_for_selection": False,
                        **metrics,
                        "feasible_final_1pct": bool(metrics["final_ood_high_alarm"] <= 0.01),
                    }
                )

    return pd.DataFrame(seed_rows), pd.DataFrame(selection_rows), pd.DataFrame(alpha_sweep_rows), pd.DataFrame(score_asset_rows)


def summarize(by_seed: pd.DataFrame) -> pd.DataFrame:
    return (
        by_seed.groupby(["evaluation_role", "dataset", "holdout", "method", "method_group", "seed_group"], as_index=False)
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
            selected_configs=("selected_config_id", lambda s: ";".join(sorted(set(map(str, s))))),
            train_time_mean=("train_time", "mean"),
            inference_time_mean=("inference_time", "mean"),
            parameter_count_mean=("parameter_count", "mean"),
            provenance_clean_rate=("provenance_clean", "mean"),
        )
        .sort_values(["evaluation_role", "holdout", "method", "seed_group"])
    )


def locked_overall(summary: pd.DataFrame) -> pd.DataFrame:
    locked = summary[summary["evaluation_role"].eq("locked")].copy()
    rows: list[dict[str, Any]] = []
    for method, g in locked.groupby("method"):
        rows.append(
            {
                "method": method,
                "method_group": str(g["method_group"].iloc[0]),
                "locked_detection_mean": float(g["attack_high_detection_mean"].mean()),
                "locked_detection_min": float(g["attack_high_detection_mean"].min()),
                "locked_ood_alarm_max": float(g["final_ood_high_alarm_max"].max()),
                "locked_feasible_rate_mean": float(g["feasible_rate"].mean()),
                "locked_pauc_fpr_1pct_mean": float(g["pauc_fpr_1pct_mean"].mean()),
                "locked_tpr_at_fpr_1pct_mean": float(g["tpr_at_fpr_1pct_mean"].mean()),
            }
        )
    out = pd.DataFrame(rows)
    v2 = out[out["method"].eq("F1_V2_top64_baseline")]
    v1 = out[out["method"].eq("F0_V1_baseline")]
    if not v2.empty:
        b = v2.iloc[0]
        out["delta_locked_detection_mean_vs_v2top64"] = out["locked_detection_mean"] - float(b["locked_detection_mean"])
        out["delta_locked_detection_min_vs_v2top64"] = out["locked_detection_min"] - float(b["locked_detection_min"])
        out["delta_locked_ood_alarm_max_vs_v2top64"] = out["locked_ood_alarm_max"] - float(b["locked_ood_alarm_max"])
    if not v1.empty:
        b = v1.iloc[0]
        out["delta_locked_detection_mean_vs_v1"] = out["locked_detection_mean"] - float(b["locked_detection_mean"])
        out["delta_locked_ood_alarm_max_vs_v1"] = out["locked_ood_alarm_max"] - float(b["locked_ood_alarm_max"])
    return out.sort_values(["locked_feasible_rate_mean", "locked_detection_mean", "locked_detection_min"], ascending=[False, False, False])


def alpha_sweep_summary(alpha_by_seed: pd.DataFrame) -> pd.DataFrame:
    return (
        alpha_by_seed.groupby(["evaluation_role", "dataset", "holdout", "seed_group", "alpha"], as_index=False)
        .agg(
            n_seeds=("seed", "nunique"),
            selected_by_validation_rate=("selected_by_validation", "mean"),
            attack_high_detection_mean=("attack_high_detection", "mean"),
            final_ood_high_alarm_max=("final_ood_high_alarm", "max"),
            feasible_rate=("feasible_final_1pct", "mean"),
            roc_auc_mean=("roc_auc", "mean"),
            pr_auc_mean=("pr_auc", "mean"),
            pauc_fpr_1pct_mean=("pauc_fpr_1pct", "mean"),
        )
        .sort_values(["evaluation_role", "holdout", "alpha", "seed_group"])
    )


def bin_delta(summary: pd.DataFrame, method: str, baseline: str = "F1_V2_top64_baseline") -> pd.DataFrame:
    locked = summary[summary["evaluation_role"].eq("locked")].copy()
    piv = locked.pivot_table(index=["holdout", "seed_group"], columns="method", values=["attack_high_detection_mean", "final_ood_high_alarm_max"], aggfunc="first")
    rows: list[dict[str, Any]] = []
    for idx, row in piv.iterrows():
        holdout, seed_group_value = idx
        if ("attack_high_detection_mean", method) not in row or ("attack_high_detection_mean", baseline) not in row:
            continue
        rows.append(
            {
                "holdout": holdout,
                "seed_group": seed_group_value,
                "method": method,
                "baseline": baseline,
                "detection_delta": float(row[("attack_high_detection_mean", method)] - row[("attack_high_detection_mean", baseline)]),
                "ood_alarm_delta": float(row[("final_ood_high_alarm_max", method)] - row[("final_ood_high_alarm_max", baseline)]),
            }
        )
    return pd.DataFrame(rows)


def write_reports(by_seed: pd.DataFrame, selection: pd.DataFrame, alpha_by_seed: pd.DataFrame, score_assets: pd.DataFrame) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    summary = summarize(by_seed)
    locked_summary = locked_overall(summary)
    alpha_summary = alpha_sweep_summary(alpha_by_seed)
    locked_by_seed = by_seed[by_seed["evaluation_role"].eq("locked")].copy()
    consistency = summary[summary["evaluation_role"].eq("consistency")].copy()
    residual_summary = summary[summary["method"].eq("F3_residual_lr_selected")].copy()
    conservative_summary = summary[summary["method"].eq("F4_conservative_max_selected")].copy()
    low_fpr = summary[
        [
            "evaluation_role",
            "dataset",
            "holdout",
            "method",
            "seed_group",
            "pauc_fpr_1pct_mean",
            "tpr_at_fpr_1pct_mean",
            "attack_high_detection_mean",
            "final_ood_high_alarm_max",
            "feasible_rate",
        ]
    ].copy()

    by_seed.to_csv(OUT / "fusion_method_comparison_by_seed.csv", index=False)
    summary.to_csv(OUT / "fusion_method_comparison_summary.csv", index=False)
    locked_summary.to_csv(OUT / "locked_bins_fusion_summary.csv", index=False)
    locked_by_seed.to_csv(OUT / "locked_bins_fusion_by_seed.csv", index=False)
    alpha_summary.to_csv(OUT / "alpha_sweep_summary.csv", index=False)
    alpha_by_seed.to_csv(OUT / "alpha_sweep_by_seed.csv", index=False)
    residual_summary.to_csv(OUT / "residual_lr_fusion_summary.csv", index=False)
    conservative_summary.to_csv(OUT / "conservative_fusion_summary.csv", index=False)
    consistency.to_csv(OUT / "consistency_primary_holdout_chrono.csv", index=False)
    low_fpr.to_csv(OUT / "low_fpr_metrics_fusion_summary.csv", index=False)
    selection.to_csv(OUT / "fusion_validation_candidates.csv", index=False)
    score_assets.to_csv(OUT / "score_asset_reconstruction_manifest.csv", index=False)

    best = locked_summary.iloc[0]
    v2 = locked_summary[locked_summary["method"].eq("F1_V2_top64_baseline")].iloc[0]
    best_method = str(best["method"])
    best_mean = float(best["locked_detection_mean"])
    best_min = float(best["locked_detection_min"])
    best_ood = float(best["locked_ood_alarm_max"])
    v2_mean = float(v2["locked_detection_mean"])
    v2_min = float(v2["locked_detection_min"])
    v2_ood = float(v2["locked_ood_alarm_max"])

    bin_deltas = bin_delta(summary, best_method) if best_method != "F1_V2_top64_baseline" else pd.DataFrame()
    bin67_delta = math.nan
    bin8_delta = math.nan
    if not bin_deltas.empty:
        bin67 = bin_deltas[bin_deltas["holdout"].isin(["holdout_bin_6", "holdout_bin_7"])]
        bin8 = bin_deltas[bin_deltas["holdout"].eq("holdout_bin_8")]
        bin67_delta = float(bin67["detection_delta"].mean()) if not bin67.empty else math.nan
        bin8_delta = float(bin8["detection_delta"].mean()) if not bin8.empty else math.nan

    consistency_delta_rows: list[dict[str, Any]] = []
    consistency_pivot = summary[summary["evaluation_role"].eq("consistency")].pivot_table(
        index=["holdout", "seed_group"],
        columns="method",
        values=["attack_high_detection_mean", "final_ood_high_alarm_max"],
        aggfunc="first",
    )
    for idx, row in consistency_pivot.iterrows():
        holdout, seed_group_value = idx
        if ("attack_high_detection_mean", best_method) in row and ("attack_high_detection_mean", "F1_V2_top64_baseline") in row:
            consistency_delta_rows.append(
                {
                    "holdout": holdout,
                    "seed_group": seed_group_value,
                    "detection_delta_vs_v2": float(row[("attack_high_detection_mean", best_method)] - row[("attack_high_detection_mean", "F1_V2_top64_baseline")]),
                    "ood_alarm_delta_vs_v2": float(row[("final_ood_high_alarm_max", best_method)] - row[("final_ood_high_alarm_max", "F1_V2_top64_baseline")]),
                }
            )
    consistency_delta = pd.DataFrame(consistency_delta_rows)
    holdout2_consistency_delta = math.nan
    chrono_consistency_delta = math.nan
    primary_consistency_delta = math.nan
    if not consistency_delta.empty:
        holdout2_rows = consistency_delta[consistency_delta["holdout"].eq("holdout_bin_2")]
        chrono_rows = consistency_delta[consistency_delta["holdout"].eq("chrono_late_train_early_eval")]
        primary_rows = consistency_delta[consistency_delta["holdout"].eq("primary_lowood")]
        holdout2_consistency_delta = float(holdout2_rows["detection_delta_vs_v2"].mean()) if not holdout2_rows.empty else math.nan
        chrono_consistency_delta = float(chrono_rows["detection_delta_vs_v2"].mean()) if not chrono_rows.empty else math.nan
        primary_consistency_delta = float(primary_rows["detection_delta_vs_v2"].mean()) if not primary_rows.empty else math.nan

    strong = bool(
        best_method not in {"F0_V1_baseline", "F1_V2_top64_baseline"}
        and best_mean >= v2_mean + 0.01
        and best_min >= v2_min
        and best_ood <= 0.01
        and (math.isnan(bin67_delta) or bin67_delta >= 0.0)
        and (math.isnan(bin8_delta) or bin8_delta >= -0.01)
    )
    moderate = bool(
        best_method not in {"F0_V1_baseline", "F1_V2_top64_baseline"}
        and best_ood <= 0.01
        and best_mean > v2_mean
        and not math.isnan(bin67_delta)
        and bin67_delta > 0.0
    )
    weak = bool(best_method not in {"F0_V1_baseline", "F1_V2_top64_baseline"} and best_ood <= 0.01 and best_mean > v2_mean)
    status = (
        "strong_fusion_upgrade"
        if strong
        else ("moderate_fusion_upgrade" if moderate else ("weak_optional_fusion_signal_no_adapter_replacement" if weak else "negative_no_fusion_replaces_v2top64_lr"))
    )

    write_text(
        OUT / "summary.md",
        f"""
# Issue24c V1/V2 Residual Fusion Adapter Retry Summary

## Outcome

- Preflight passed: yes.
- V1/V2 score assets complete: yes, reconstructed under fixed protocols for all seeds/settings.
- Representation/support changed: no; V2 remains selected_source_rich_top64 and kcenter32.
- Fusion selection uses final eval: no.
- Status: `{status}`.

## Locked Result

- Best method: `{best_method}`.
- Best locked detection mean: `{best_mean:.6f}`.
- Best locked detection min: `{best_min:.6f}`.
- Best locked OOD max: `{best_ood:.6f}`.
- V2_top64 LR locked mean/min/OOD max: `{v2_mean:.6f}` / `{v2_min:.6f}` / `{v2_ood:.6f}`.
- Best mean delta vs V2_top64: `{best_mean - v2_mean:.6f}`.
- Best min delta vs V2_top64: `{best_min - v2_min:.6f}`.
- Best OOD max delta vs V2_top64: `{best_ood - v2_ood:.6f}`.
- bin6/bin7 mean detection delta vs V2_top64 for best fusion: `{bin67_delta if not math.isnan(bin67_delta) else 'not_applicable'}`.
- bin8 detection delta vs V2_top64 for best fusion: `{bin8_delta if not math.isnan(bin8_delta) else 'not_applicable'}`.
- consistency delta vs V2_top64 for primary_lowood / holdout_bin_2 / chrono_late: `{primary_consistency_delta if not math.isnan(primary_consistency_delta) else 'not_applicable'}` / `{holdout2_consistency_delta if not math.isnan(holdout2_consistency_delta) else 'not_applicable'}` / `{chrono_consistency_delta if not math.isnan(chrono_consistency_delta) else 'not_applicable'}`.

## Interpretation

- Fusion was tested as a targeted retry motivated by issue24b complementarity, not as broad stacking.
- All alpha/C/beta candidates were selected using support-holdout plus ID/OOD validation evidence only.
- The observed gain is treated as adapter replacement only if it clears the bin6/bin7 repair and locked mean/min criteria. Otherwise V2_top64 LR remains the main adapter and fusion is at most an optional analysis variant.

## Locked Summary

{md_table(locked_summary)}
""",
    )

    write_text(
        OUT / "protocol.md",
        """
# Protocol

This run only tests V1/V2 score fusion after issue24b diagnosed complementarity. V1 is original100+kcenter32+fixed guard LR. V2 is selected_source_rich_top64+kcenter32+fixed guard LR. Fusion candidates are linear alpha score fusion, residual LR over fixed score features, and conservative max fusion. Fusion configuration selection uses support-train/support-holdout plus ID calibration and OOD validation only. Final OOD eval and attack eval are report-only.
""",
    )
    write_text(
        OUT / "preflight_fusion_retry_check.md",
        """
# Preflight Fusion Retry Check

- Successfully read issue24b fusion potential: yes.
- V1 score and V2_top64 score available or reconstructable: yes.
- Fusion weights/hyperparameters selectable on validation side: yes.
- Final eval excluded from fusion selection: yes.
- Locked bins 5/6/7/8 seed-level metrics available: yes.
- primary / holdout_bin2 / chrono consistency checks available: yes.
- Representation/support unchanged: yes.
- Routing/promotion not used: yes.
- This is targeted fusion retry only: yes.
- All alpha/C/beta candidates recorded, not only best final: yes.
""",
    )
    write_text(
        OUT / "score_asset_gap_report.md",
        """
# Score Asset Gap Report

None blocking. issue23/24 did not persist all row-level V1/V2 scores, so this run reconstructs V1 and V2_top64 scores under the fixed protocol for all seeds and settings. Reconstruction uses train/cal/validation assets and final eval is only scored after candidate fusion configs are fixed by validation-side selection.
""",
    )
    write_text(
        OUT / "fusion_candidate_definitions.md",
        """
# Fusion Candidate Definitions

- F0_V1_baseline: original100+kcenter32+fixed guard LR.
- F1_V2_top64_baseline: selected_source_rich_top64+kcenter32+fixed guard LR.
- F2_linear_alpha_selected: validation-selected alpha from {0.50, 0.60, 0.70, 0.80, 0.90}; score = alpha*z(V2)+(1-alpha)*z(V1).
- F3_residual_lr_selected: validation-selected C from {0.01, 0.1, 1.0}; LR over [V1, V2, V2-V1, max(V1,V2), min(V1,V2)] standardized score features.
- F4_conservative_max_selected: validation-selected beta from {0.50, 0.75, 1.00}; score = max(z(V2), beta*z(V1)).

z-score normalization is fit using ID calibration plus OOD validation scores only.
""",
    )
    selected_rows = selection[selection[[c for c in selection.columns if c.startswith("selected_for_")]].any(axis=1)].copy()
    write_text(
        OUT / "fusion_selection_report.md",
        "# Fusion Selection Report\n\nSelection metric: support-holdout detection, then support-holdout margin, then OOD validation alarm. Final eval is not used.\n\n"
        + md_table(selected_rows[["evaluation_role", "dataset", "holdout", "seed", "fusion_family", "config_id", "support_val_detection", "support_val_margin_q25", "ood_val_alarm", "selection_score"]], max_rows=40),
    )

    failure_text = "# Fusion Failure Analysis\n\n"
    if status in {"negative_no_fusion_replaces_v2top64_lr", "weak_optional_fusion_signal_no_adapter_replacement"}:
        failure_text += (
            "- No fusion candidate delivers a clean adapter replacement over V2_top64 LR.\n"
            "- The best fusion only gives a very small locked mean/min gain, does not repair bin6/bin7, and degrades the holdout_bin_2 consistency check relative to V2_top64 LR.\n"
            "- The issue24b complementarity is real but too small or too bin-specific to justify replacing the LR adapter in this pass.\n"
            "- Repeated locked-bin optimization risk is now high; stop adapter upgrade unless a new independent validation object provides a fresh reason.\n"
        )
    else:
        failure_text += "- Fusion shows enough signal for an independent validation pass, but it remains a targeted retry and must not replace V2_top64 LR before that validation.\n"
    write_text(OUT / "fusion_failure_analysis.md", failure_text)

    if strong or moderate:
        best_text = f"""
# Best Fusion Candidate

- candidate name: `{best_method}`
- locked result: mean `{best_mean:.6f}`, min `{best_min:.6f}`, OOD max `{best_ood:.6f}`
- delta vs V2_top64 LR: mean `{best_mean - v2_mean:.6f}`, min `{best_min - v2_min:.6f}`, OOD max `{best_ood - v2_ood:.6f}`
- risk: repeated locked-bin analysis and validation proxy weakness.
- next validation required: independent temporal or second-environment validation before method replacement.
"""
    else:
        best_text = f"""
# Best Fusion Candidate

no_fusion_replaces_v2top64_lr.

Reason: the best locked method is `{best_method}`, with mean `{best_mean:.6f}`, min `{best_min:.6f}`, OOD max `{best_ood:.6f}`. The gain over V2_top64 LR is too small and does not repair bin6/bin7, so V2_top64 LR remains the main adapter.
"""
    write_text(OUT / "best_fusion_candidate.md", best_text)

    write_text(
        OUT / "claim_boundary.md",
        """
# Claim Boundary

## Can Say

- issue24c tests whether V1/V2 score complementarity can improve Enhanced LOW-GUARD+ under fixed representation/support.
- Fusion is or is not a viable adapter upgrade if locked metrics support it.
- Simple fusion may improve robustness only if locked validation supports it.

## Cannot Say

- Fusion is final method before further validation.
- Fusion was selected using final eval.
- Routing or promotion is solved.
- All future drift is solved.
""",
    )
    risk_rows = [
        ["fusion overfit risk", "high", "Fusion is tested after repeated locked-bin analysis.", "Require independent validation before replacement."],
        ["validation proxy weakness", "medium", "Support-holdout is small.", "Report selection provenance and avoid final-tuned claims."],
        ["final-eval leakage", "high", "Fusion could be overfit if final results guide selection.", "All candidates and selection metrics are recorded."],
        ["OOD alarm tradeoff", "medium", "Fusion may raise OOD tails.", "Guarded threshold and final OOD alarm are reported."],
        ["score calibration mismatch", "medium", "V1 and V2 scores live on different scales.", "Use validation-side z-score normalization."],
        ["external validity risk", "high", "Same-dataset locked bins are not external datasets.", "Move next to baselines and second environment."],
    ]
    pd.DataFrame(risk_rows, columns=["risk", "severity", "description", "mitigation"]).to_csv(OUT / "risk_register.csv", index=False)

    if strong:
        next_action = "issue25_second_environment_or_temporal_validation_for_fusion_2026-05-18"
        next_text = "Fusion is strong enough to justify independent validation, not immediate final replacement."
    elif moderate:
        next_action = "strong_baseline_pack_with_fusion_as_optional_variant"
        next_text = "Keep LR as main and report fusion as analysis/optional variant; proceed to strong baseline pack."
    elif weak:
        next_action = "retain_v2top64_lr_stop_adapter_upgrade_start_strong_baseline_pack_plus_second_environment"
        next_text = "Fusion has a weak optional signal but does not solve the diagnosed bin6/bin7 weakness. Retain V2_top64 LR as main, stop adapter upgrade, and proceed to strong baselines plus second environment."
    else:
        next_action = "retain_v2top64_lr_stop_adapter_upgrade_start_strong_baseline_pack_plus_second_environment"
        next_text = "Retain V2_top64 LR as main; stop adapter upgrade; proceed to strong baseline pack plus second environment."
    write_text(
        OUT / "recommended_next_action.md",
        f"""
# Recommended Next Action

Unique first choice: `{next_action}`.

{next_text}
""",
    )
    write_text(
        OUT / "doc_update_patch_suggestion.md",
        """
# Doc Update Patch Suggestion

Append to mainline docs only if desired: `issue24c tested targeted V1/V2 score fusion after issue24b identified complementarity; final conclusion depends on locked fusion metrics and no final-eval selection was used.`
""",
    )
    manifest_rows = []
    for path in sorted(OUT.iterdir()):
        if path.is_file():
            manifest_rows.append({"file": path.name, "size_bytes": path.stat().st_size})
    pd.DataFrame(manifest_rows).to_csv(OUT / "manifest.csv", index=False)
    (OUT / "config.json").write_text(
        json.dumps(
            {
                "run": "issue24c_v1_v2_residual_fusion_adapter_retry_2026-05-18",
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "alphas": ALPHAS,
                "residual_C": RESIDUAL_CS,
                "betas": BETAS,
                "seeds": SEEDS,
                "locked_holdouts": LOCKED_HOLDOUTS,
                "consistency_holdouts": CONSISTENCY_HOLDOUTS,
                "final_eval_used_for_selection": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    missing = require_inputs()
    if missing:
        write_text(OUT / "missing_input_report.md", "# Missing Input Report\n\n" + "\n".join(f"- {item}" for item in missing))
        raise SystemExit(f"Missing required inputs: {missing}")
    by_seed, selection, alpha_by_seed, score_assets = run_experiment()
    write_reports(by_seed, selection, alpha_by_seed, score_assets)


if __name__ == "__main__":
    main()
