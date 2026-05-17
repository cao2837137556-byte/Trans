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
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs" / "issue19_lowguard_plus_representation_margin_repair_pilot_2026-05-18"
ISSUE11 = ROOT / "runs" / "issue11_fixed_config_ood_guard_lr_ablation_2026-05-14"
ISSUE16B = ROOT / "runs" / "issue16b_harder_holdout_fixed_guard_validation_2026-05-15"
ISSUE16C = ROOT / "runs" / "issue16c_harder_holdout_failure_analysis_and_repair_design_2026-05-15"
ISSUE17 = ROOT / "runs" / "issue17_support_diversity_selection_harder_holdout_2026-05-15"
ISSUE18 = ROOT / "runs" / "issue18_row_level_score_persistence_and_ood_target_sensitivity_2026-05-15"
FRONTEND_F2_ROOT = ROOT.parent / "kitnet-frontend-f2"
F2_OOD = FRONTEND_F2_ROOT / "repo" / "ood"
if str(F2_OOD) not in sys.path:
    sys.path.insert(0, str(F2_OOD))

import frontend_f2_v7_4_paired_holdout_fairness as v74  # noqa: E402
import frontend_f2_v7_2_fairness_validation as v72  # noqa: E402


TARGETS = [0.005, 0.01, 0.02]
TARGET_LABELS = {0.005: "0.5pct", 0.01: "1pct", 0.02: "2pct"}
TARGET_ALARM = 0.01
POSITIVE_BUDGET = 32
SEEDS = list(range(42, 52))
MAIN_HOLDOUTS = ["chrono_late_train_early_eval", "holdout_bin_2"]
TOPK_VALUES = [16, 32]
MARGIN_WEIGHTS = [2.0, 4.0, 8.0]
HARD_TAIL_FRAC = 0.05


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


def seed_group(seed: int) -> str:
    seed = int(seed)
    if 42 <= seed <= 46:
        return "main_42_46"
    if 47 <= seed <= 51:
        return "heldout_47_51"
    return "other"


def load_matrix(path: Path) -> np.ndarray:
    if path.suffix.lower() == ".npy":
        arr = np.load(path)
    else:
        arr = pd.read_csv(path, header=None).to_numpy(np.float32)
    if arr.ndim != 2:
        raise RuntimeError(f"Expected a 2D matrix from {path}, got {arr.shape}")
    return np.nan_to_num(arr.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)


def feature_names(schema_path: Path, dim: int) -> list[str]:
    if not schema_path.exists():
        return [f"source_rich_{i}" for i in range(dim)]
    data = json.loads(schema_path.read_text(encoding="utf-8"))
    names = [f"source_rich_{i}" for i in range(dim)]
    for item in data.get("header_mappings", []):
        idx = int(item.get("flat_index", -1))
        if 0 <= idx < dim:
            names[idx] = str(item.get("header", names[idx]))
    return names


def require_inputs() -> list[str]:
    required = [
        ISSUE11 / "config.json",
        ISSUE16B / "method_comparison_by_seed.csv",
        ISSUE16C / "feature_drift_summary.csv",
        ISSUE17 / "support_id_provenance.csv",
        ISSUE17 / "method_comparison_by_seed.csv",
        ISSUE18 / "summary.md",
        ISSUE18 / "diagnostic_decision.md",
        ISSUE18 / "ood_target_sensitivity_summary.csv",
        ISSUE18 / "attack_ood_separation_summary.csv",
        ISSUE18 / "random_vs_kcenter_margin_delta.csv",
        ISSUE18 / "representation_failure_diagnosis.md",
    ]
    return [str(p) for p in required if not p.exists()]


def select_source_rich_features(
    *,
    x_support: np.ndarray,
    x_id_calib: np.ndarray,
    x_ood_val: np.ndarray,
    top_k: int,
    names: list[str],
    holdout: str,
    seed: int,
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
    for idx in order:
        idx = int(idx)
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
        for idx in order:
            idx = int(idx)
            if idx not in selected:
                selected.append(idx)
            if len(selected) >= top_k:
                break

    rows = []
    for rank, idx in enumerate(selected, start=1):
        rows.append(
            {
                "holdout": holdout,
                "seed": int(seed),
                "seed_group": seed_group(seed),
                "top_k": int(top_k),
                "rank": rank,
                "feature_index": int(idx),
                "feature_name": names[idx] if idx < len(names) else f"source_rich_{idx}",
                "selection_score": float(raw_score[idx]),
                "effect_vs_ood_val": float(effect_vs_ood[idx]),
                "effect_vs_id_calib": float(effect_vs_id[idx]),
                "support_q25_minus_ood_val_q99": float(tail_margin[idx]),
                "selection_uses_attack_eval": False,
                "selection_uses_final_ood_eval": False,
            }
        )
    return np.asarray(selected, dtype=np.int64), rows


def fit_once(
    x_train_raw: np.ndarray,
    y_train: np.ndarray,
    sample_weight: np.ndarray,
    eval_mats: dict[str, np.ndarray],
    *,
    extra_negative_raw: np.ndarray | None = None,
    extra_negative_weight: float | None = None,
) -> tuple[LogisticRegression, StandardScaler, dict[str, np.ndarray], float, float]:
    scaler = StandardScaler()
    t0 = time.perf_counter()
    x_train_z = scaler.fit_transform(x_train_raw)
    y = y_train
    w = sample_weight
    if extra_negative_raw is not None and len(extra_negative_raw):
        extra_z = scaler.transform(extra_negative_raw)
        x_train_z = np.vstack([x_train_z, extra_z])
        y = np.concatenate([y, np.zeros(len(extra_negative_raw), dtype=np.int64)])
        w = np.concatenate([w, np.full(len(extra_negative_raw), float(extra_negative_weight), dtype=np.float64)])
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
    scores = {name: model.decision_function(scaler.transform(mat)).astype(np.float64) for name, mat in eval_mats.items()}
    inference_time = time.perf_counter() - t1
    return model, scaler, scores, train_time, inference_time


def fit_adapter(
    *,
    x_id_train: np.ndarray,
    x_ood_train: np.ndarray,
    x_pos: np.ndarray,
    x_id_calib: np.ndarray,
    x_ood_val: np.ndarray,
    x_ood_eval: np.ndarray,
    x_attack_eval: np.ndarray,
    method: str,
    margin_weight: float | None = None,
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
    eval_mats = {
        "id_calib": x_id_calib,
        "ood_val": x_ood_val,
        "final_ood_eval": x_ood_eval,
        "attack_eval": x_attack_eval,
    }
    hard_negative_indices: np.ndarray = np.asarray([], dtype=np.int64)
    if margin_weight is not None:
        _, base_scaler, base_scores, _, _ = fit_once(x_train, y_train, sample_weight, eval_mats)
        n_hard = max(1, int(math.ceil(len(x_ood_val) * HARD_TAIL_FRAC)))
        hard_negative_indices = np.argsort(-base_scores["ood_val"])[:n_hard].astype(np.int64)
        # Keep scaler fit provenance clean: the final model scaler is fit only on
        # ID train + OOD train + selected supports; hard OOD validation negatives
        # are transformed by that scaler, not used to fit it.
        del base_scaler
    model, scaler, scores, train_time, inference_time = fit_once(
        x_train,
        y_train,
        sample_weight,
        eval_mats,
        extra_negative_raw=x_ood_val[hard_negative_indices] if len(hard_negative_indices) else None,
        extra_negative_weight=margin_weight,
    )
    thresholds: dict[float, dict[str, Any]] = {}
    for target in TARGETS:
        thresholds[target] = v72.guarded_val_threshold(scores["id_calib"], scores["ood_val"], target)
    y_eval = np.concatenate([np.zeros(len(scores["final_ood_eval"]), dtype=np.int64), np.ones(len(scores["attack_eval"]), dtype=np.int64)])
    s_eval = np.concatenate([scores["final_ood_eval"], scores["attack_eval"]])
    return {
        "model": model,
        "scaler": scaler,
        "scores": scores,
        "thresholds": thresholds,
        "roc_auc": float(roc_auc_score(y_eval, s_eval)),
        "pr_auc": float(average_precision_score(y_eval, s_eval)),
        "train_time": train_time,
        "inference_time": inference_time,
        "parameter_count": int(model.coef_.size + model.intercept_.size),
        "hard_negative_count": int(len(hard_negative_indices)),
        "hard_negative_source": "ood_validation_top_5pct_by_base_model_score" if margin_weight is not None else "not_applicable",
        "margin_weight": float(margin_weight) if margin_weight is not None else math.nan,
        "method": method,
    }


def summarize(seed_df: pd.DataFrame) -> pd.DataFrame:
    return (
        seed_df.groupby(["holdout", "method", "seed_group"], as_index=False)
        .agg(
            method_group=("method_group", "first"),
            representation=("representation", "first"),
            adapter=("adapter", "first"),
            n_seeds=("seed", "nunique"),
            attack_high_detection_mean=("attack_high_detection", "mean"),
            attack_high_detection_std=("attack_high_detection", "std"),
            attack_high_detection_min=("attack_high_detection", "min"),
            attack_high_detection_max=("attack_high_detection", "max"),
            ood_high_alarm_mean=("ood_high_alarm", "mean"),
            ood_high_alarm_max=("ood_high_alarm", "max"),
            feasible_rate=("feasible", "mean"),
            roc_auc_mean=("roc_auc", "mean"),
            pr_auc_mean=("pr_auc", "mean"),
            threshold_mean=("threshold", "mean"),
            feature_dim=("feature_dim", "first"),
            selected_feature_count=("selected_feature_count", "first"),
            margin_weight=("margin_weight", "first"),
            hard_negative_count=("hard_negative_count", "first"),
            parameter_count=("parameter_count", "first"),
            train_time_mean=("train_time", "mean"),
            inference_time_mean=("inference_time", "mean"),
        )
        .sort_values(["holdout", "seed_group", "method"])
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "figures").mkdir(exist_ok=True)
    missing = require_inputs()
    if missing:
        write_text(OUT / "missing_input_report.md", "# Missing Input Report\n\n" + "\n".join(f"- {m}" for m in missing))
        raise RuntimeError(f"Missing required inputs: {missing}")

    cfg = json.loads((ISSUE11 / "config.json").read_text(encoding="utf-8"))
    paths = cfg["paths"]
    x_id_o = load_matrix(Path(paths["original100_id"]))
    x_ood_o = load_matrix(Path(paths["original100_ood"]))
    x_attack_o = load_matrix(Path(paths["original100_attack"]))
    x_id_sr = load_matrix(Path(paths["source_rich_id"]))
    x_ood_sr = load_matrix(Path(paths["source_rich_ood"]))
    x_attack_sr = load_matrix(Path(paths["source_rich_attack"]))
    schema_path = Path(paths["source_rich_id"]).parents[1] / "data" / "structured_schema.json"
    sr_names = feature_names(schema_path, x_id_sr.shape[1])
    if x_id_o.shape[0] != x_id_sr.shape[0] or x_ood_o.shape[0] != x_ood_sr.shape[0] or x_attack_o.shape[0] != x_attack_sr.shape[0]:
        write_text(OUT / "alignment_failure_report.md", "# Alignment Failure\n\noriginal100 and source_rich row counts do not match.")
        raise RuntimeError("original100/source_rich row-count mismatch")

    manifest = json.loads(Path(paths["stage2_manifest"]).read_text(encoding="utf-8-sig"))
    row_bins = np.asarray(v74.load_attack_bins(manifest))
    specs = [s for s in v74.make_holdout_specs(manifest, row_bins, min_eval_rows=300) if s["holdout_name"] in MAIN_HOLDOUTS]
    specs_by_name = {str(s["holdout_name"]): s for s in specs}
    if sorted(specs_by_name) != sorted(MAIN_HOLDOUTS):
        raise RuntimeError(f"Missing holdout specs: {set(MAIN_HOLDOUTS) - set(specs_by_name)}")

    # Follow the issue17/18 repair-line calibration slice for direct comparison
    # to the kcenter repair and row-level score diagnostic.
    id_train_end = 8000
    id_calib_end = id_train_end + 5000
    ood_train_end = 8000
    ood_val_end = ood_train_end + 2000
    split = {
        "x_id_train_o": x_id_o[:id_train_end],
        "x_id_calib_o": x_id_o[id_train_end:id_calib_end],
        "x_ood_train_o": x_ood_o[:ood_train_end],
        "x_ood_val_o": x_ood_o[ood_train_end:ood_val_end],
        "x_ood_eval_o": x_ood_o[ood_val_end:],
        "x_id_train_sr": x_id_sr[:id_train_end],
        "x_id_calib_sr": x_id_sr[id_train_end:id_calib_end],
        "x_ood_train_sr": x_ood_sr[:ood_train_end],
        "x_ood_val_sr": x_ood_sr[ood_train_end:ood_val_end],
        "x_ood_eval_sr": x_ood_sr[ood_val_end:],
    }

    support_df = pd.read_csv(ISSUE17 / "support_id_provenance.csv")
    support_df = support_df[
        support_df["support_selection_method"].isin(["kcenter_32shot", "random_32shot_baseline"])
        & support_df["positive_budget"].eq(POSITIVE_BUDGET)
    ].copy()
    bad_support = support_df[
        support_df["overlaps_attack_eval"].astype(str).eq("True")
        | support_df["overlaps_attack_val"].astype(str).eq("True")
        | support_df["selection_uses_attack_eval"].astype(str).eq("True")
        | support_df["selection_uses_final_ood_eval"].astype(str).eq("True")
        | ~support_df["in_attack_train_pool"].astype(str).eq("True")
    ]
    if not bad_support.empty:
        write_text(OUT / "preflight_lowguard_plus_repair_check.md", "# Preflight\n\nFailed: support provenance violation.")
        raise RuntimeError("support provenance violation")

    issue18_by_seed = pd.read_csv(ISSUE18 / "ood_target_sensitivity_by_seed.csv")
    baseline = issue18_by_seed[issue18_by_seed["target_label"].eq("1pct")].copy()
    baseline = baseline[baseline["support_method"].isin(["random_32shot_baseline", "kcenter_32shot"])]
    baseline_rows: list[dict[str, Any]] = []
    for _, row in baseline.iterrows():
        method = {
            "random_32shot_baseline": "baseline_original100_random32_fixed_guard",
            "kcenter_32shot": "baseline_original100_kcenter32_fixed_guard",
        }[str(row["support_method"])]
        baseline_rows.append(
            {
                "holdout": row["holdout"],
                "method": method,
                "method_group": "A_baseline",
                "seed": int(row["seed"]),
                "seed_group": row["seed_group"],
                "support_method": row["support_method"],
                "representation": "original100",
                "adapter": "fixed_guard_lr",
                "positive_budget": POSITIVE_BUDGET,
                "ood_target_label": "1pct",
                "attack_high_detection": float(row["attack_high_detection"]),
                "ood_high_alarm": float(row["ood_high_alarm"]),
                "feasible": bool(str(row["feasible_for_1pct"]).lower() == "true"),
                "threshold": float(row["threshold"]),
                "roc_auc": float(row["roc_auc"]),
                "pr_auc": float(row["pr_auc"]),
                "attack_eval_size": int(row["attack_eval_size"]),
                "ood_eval_size": int(row["ood_eval_size"]),
                "feature_dim": 100,
                "selected_feature_count": 0,
                "margin_weight": math.nan,
                "hard_negative_count": 0,
                "parameter_count": 101,
                "train_time": math.nan,
                "inference_time": math.nan,
                "result_source": "reused_issue18_row_level_diagnostic",
            }
        )

    seed_rows: list[dict[str, Any]] = baseline_rows.copy()
    target_rows: list[dict[str, Any]] = []
    selected_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    hardneg_rows: list[dict[str, Any]] = []
    support_rows: list[dict[str, Any]] = []

    for holdout in MAIN_HOLDOUTS:
        spec = specs_by_name[holdout]
        attack_eval_idx = np.asarray(spec["attack_eval_idx"], dtype=np.int64)
        for seed in SEEDS:
            group = support_df[
                support_df["holdout_name"].eq(holdout)
                & support_df["support_selection_method"].eq("kcenter_32shot")
                & support_df["seed"].eq(seed)
            ]
            if group.empty:
                raise RuntimeError(f"Missing kcenter support for {holdout} seed={seed}")
            selected_attack_rows = group["selected_attack_row_id"].astype(int).to_numpy()
            for support_id in selected_attack_rows:
                support_rows.append(
                    {
                        "holdout": holdout,
                        "seed": int(seed),
                        "seed_group": seed_group(seed),
                        "support_method": "kcenter_32shot",
                        "selected_attack_row_id": int(support_id),
                        "in_attack_train_pool": True,
                        "overlaps_attack_eval": bool(int(support_id) in set(map(int, spec["attack_eval_idx"]))),
                        "selection_uses_attack_eval": False,
                        "selection_uses_final_ood_eval": False,
                    }
                )

            x_pos_o = x_attack_o[selected_attack_rows]
            x_attack_eval_o = x_attack_o[attack_eval_idx]
            x_pos_sr_all = x_attack_sr[selected_attack_rows]
            x_attack_eval_sr_all = x_attack_sr[attack_eval_idx]

            selected_by_k: dict[int, np.ndarray] = {}
            for top_k in TOPK_VALUES:
                feat_idx, feat_rows = select_source_rich_features(
                    x_support=x_pos_sr_all,
                    x_id_calib=split["x_id_calib_sr"],
                    x_ood_val=split["x_ood_val_sr"],
                    top_k=top_k,
                    names=sr_names,
                    holdout=holdout,
                    seed=seed,
                )
                selected_by_k[top_k] = feat_idx
                selected_rows.extend(feat_rows)

            method_specs: list[dict[str, Any]] = []
            for top_k in TOPK_VALUES:
                idx = selected_by_k[top_k]
                method_specs.extend(
                    [
                        {
                            "method": f"selected_source_rich_top{top_k}_fixed_guard_lr",
                            "method_group": "B_representation_repair",
                            "representation": f"selected_source_rich_top{top_k}",
                            "adapter": "fixed_guard_lr",
                            "top_k": top_k,
                            "margin_weight": None,
                            "x_id_train": split["x_id_train_sr"][:, idx],
                            "x_ood_train": split["x_ood_train_sr"][:, idx],
                            "x_pos": x_pos_sr_all[:, idx],
                            "x_id_calib": split["x_id_calib_sr"][:, idx],
                            "x_ood_val": split["x_ood_val_sr"][:, idx],
                            "x_ood_eval": split["x_ood_eval_sr"][:, idx],
                            "x_attack_eval": x_attack_eval_sr_all[:, idx],
                        },
                        {
                            "method": f"original100_plus_selected_source_rich_top{top_k}_fixed_guard_lr",
                            "method_group": "B_representation_repair",
                            "representation": f"original100_plus_selected_source_rich_top{top_k}",
                            "adapter": "fixed_guard_lr",
                            "top_k": top_k,
                            "margin_weight": None,
                            "x_id_train": np.hstack([split["x_id_train_o"], split["x_id_train_sr"][:, idx]]),
                            "x_ood_train": np.hstack([split["x_ood_train_o"], split["x_ood_train_sr"][:, idx]]),
                            "x_pos": np.hstack([x_pos_o, x_pos_sr_all[:, idx]]),
                            "x_id_calib": np.hstack([split["x_id_calib_o"], split["x_id_calib_sr"][:, idx]]),
                            "x_ood_val": np.hstack([split["x_ood_val_o"], split["x_ood_val_sr"][:, idx]]),
                            "x_ood_eval": np.hstack([split["x_ood_eval_o"], split["x_ood_eval_sr"][:, idx]]),
                            "x_attack_eval": np.hstack([x_attack_eval_o, x_attack_eval_sr_all[:, idx]]),
                        },
                    ]
                )
            for margin_weight in MARGIN_WEIGHTS:
                method_specs.append(
                    {
                        "method": f"original100_margin_hardneg_w{int(margin_weight)}",
                        "method_group": "C_margin_deviation_adapter",
                        "representation": "original100",
                        "adapter": "hard_negative_margin_lr",
                        "top_k": 0,
                        "margin_weight": margin_weight,
                        "x_id_train": split["x_id_train_o"],
                        "x_ood_train": split["x_ood_train_o"],
                        "x_pos": x_pos_o,
                        "x_id_calib": split["x_id_calib_o"],
                        "x_ood_val": split["x_ood_val_o"],
                        "x_ood_eval": split["x_ood_eval_o"],
                        "x_attack_eval": x_attack_eval_o,
                    }
                )
                idx32 = selected_by_k[32]
                method_specs.append(
                    {
                        "method": f"original100_plus_selected_source_rich_top32_margin_hardneg_w{int(margin_weight)}",
                        "method_group": "C_margin_deviation_adapter",
                        "representation": "original100_plus_selected_source_rich_top32",
                        "adapter": "hard_negative_margin_lr",
                        "top_k": 32,
                        "margin_weight": margin_weight,
                        "x_id_train": np.hstack([split["x_id_train_o"], split["x_id_train_sr"][:, idx32]]),
                        "x_ood_train": np.hstack([split["x_ood_train_o"], split["x_ood_train_sr"][:, idx32]]),
                        "x_pos": np.hstack([x_pos_o, x_pos_sr_all[:, idx32]]),
                        "x_id_calib": np.hstack([split["x_id_calib_o"], split["x_id_calib_sr"][:, idx32]]),
                        "x_ood_val": np.hstack([split["x_ood_val_o"], split["x_ood_val_sr"][:, idx32]]),
                        "x_ood_eval": np.hstack([split["x_ood_eval_o"], split["x_ood_eval_sr"][:, idx32]]),
                        "x_attack_eval": np.hstack([x_attack_eval_o, x_attack_eval_sr_all[:, idx32]]),
                    }
                )

            for spec_m in method_specs:
                result = fit_adapter(
                    x_id_train=spec_m["x_id_train"],
                    x_ood_train=spec_m["x_ood_train"],
                    x_pos=spec_m["x_pos"],
                    x_id_calib=spec_m["x_id_calib"],
                    x_ood_val=spec_m["x_ood_val"],
                    x_ood_eval=spec_m["x_ood_eval"],
                    x_attack_eval=spec_m["x_attack_eval"],
                    method=spec_m["method"],
                    margin_weight=spec_m["margin_weight"],
                )
                hardneg_rows.append(
                    {
                        "holdout": holdout,
                        "method": spec_m["method"],
                        "seed": int(seed),
                        "hard_negative_source": result["hard_negative_source"],
                        "hard_negative_count": result["hard_negative_count"],
                        "hard_tail_fraction": HARD_TAIL_FRAC if spec_m["margin_weight"] is not None else math.nan,
                        "margin_weight": result["margin_weight"],
                        "uses_final_ood_eval": False,
                        "uses_attack_eval": False,
                    }
                )
                for target in TARGETS:
                    label = TARGET_LABELS[target]
                    threshold = float(result["thresholds"][target]["threshold"])
                    attack_scores = result["scores"]["attack_eval"]
                    ood_scores = result["scores"]["final_ood_eval"]
                    attack_det = float(np.mean(attack_scores > threshold))
                    ood_alarm = float(np.mean(ood_scores > threshold))
                    common = {
                        "holdout": holdout,
                        "method": spec_m["method"],
                        "method_group": spec_m["method_group"],
                        "seed": int(seed),
                        "seed_group": seed_group(seed),
                        "support_method": "kcenter_32shot",
                        "representation": spec_m["representation"],
                        "adapter": spec_m["adapter"],
                        "positive_budget": POSITIVE_BUDGET,
                        "ood_target_label": label,
                        "attack_high_detection": attack_det,
                        "ood_high_alarm": ood_alarm,
                        "feasible": bool(ood_alarm <= target),
                        "threshold": threshold,
                        "roc_auc": result["roc_auc"],
                        "pr_auc": result["pr_auc"],
                        "attack_eval_size": int(len(attack_scores)),
                        "ood_eval_size": int(len(ood_scores)),
                        "feature_dim": int(spec_m["x_id_train"].shape[1]),
                        "selected_feature_count": int(spec_m["top_k"]),
                        "margin_weight": result["margin_weight"],
                        "hard_negative_count": result["hard_negative_count"],
                        "parameter_count": result["parameter_count"],
                        "train_time": result["train_time"],
                        "inference_time": result["inference_time"],
                        "result_source": "issue19_repair_pilot",
                    }
                    target_rows.append(common)
                    threshold_rows.append(
                        {
                            "holdout": holdout,
                            "method": spec_m["method"],
                            "seed": int(seed),
                            "seed_group": seed_group(seed),
                            "target_label": label,
                            "threshold": threshold,
                            "uses_id_calib": True,
                            "uses_ood_val": True,
                            "uses_final_ood_eval": False,
                            "uses_attack_eval": False,
                            "ood_val_alarm_at_selection": float(np.mean(result["scores"]["ood_val"] > threshold)),
                            "id_calib_alarm_at_selection": float(np.mean(result["scores"]["id_calib"] > threshold)),
                        }
                    )
                    if label == "1pct":
                        seed_rows.append(common)
                print(f"[done] {holdout} seed={seed} method={spec_m['method']}")

    seed_df = pd.DataFrame(seed_rows)
    target_df = pd.DataFrame(target_rows)
    feature_df = pd.DataFrame(selected_rows)
    threshold_df = pd.DataFrame(threshold_rows)
    hardneg_df = pd.DataFrame(hardneg_rows)
    support_out = pd.DataFrame(support_rows)
    summary_df = summarize(seed_df)
    seed_df.to_csv(OUT / "method_comparison_by_seed.csv", index=False)
    summary_df.to_csv(OUT / "method_comparison_summary.csv", index=False)
    target_df.to_csv(OUT / "ood_target_sensitivity_by_seed.csv", index=False)
    feature_df.to_csv(OUT / "selected_feature_report.csv", index=False)
    threshold_df.to_csv(OUT / "threshold_provenance.csv", index=False)
    hardneg_df.to_csv(OUT / "hard_negative_report.csv", index=False)
    support_out.to_csv(OUT / "support_id_provenance.csv", index=False)

    stability = (
        feature_df.groupby(["holdout", "top_k", "feature_index", "feature_name"], as_index=False)
        .agg(selection_count=("seed", "nunique"), mean_rank=("rank", "mean"), mean_score=("selection_score", "mean"))
        .sort_values(["holdout", "top_k", "selection_count", "mean_rank"], ascending=[True, True, False, True])
    )
    stability.to_csv(OUT / "selected_feature_stability.csv", index=False)

    hb2_summary = summary_df[summary_df["holdout"].eq("holdout_bin_2")].copy()
    chrono_summary = summary_df[summary_df["holdout"].eq("chrono_late_train_early_eval")].copy()
    hb2_summary.to_csv(OUT / "holdout_bin2_lowguard_plus_summary.csv", index=False)
    chrono_summary.to_csv(OUT / "chrono_late_lowguard_plus_summary.csv", index=False)

    baseline_key = ["holdout", "seed_group"]
    ref = summary_df[summary_df["method"].eq("baseline_original100_kcenter32_fixed_guard")][
        baseline_key + ["attack_high_detection_mean", "ood_high_alarm_mean", "feasible_rate"]
    ].rename(
        columns={
            "attack_high_detection_mean": "baseline_detection_mean",
            "ood_high_alarm_mean": "baseline_ood_alarm_mean",
            "feasible_rate": "baseline_feasible_rate",
        }
    )
    delta = summary_df.merge(ref, on=baseline_key, how="left")
    delta["delta_detection_vs_kcenter_original100"] = delta["attack_high_detection_mean"] - delta["baseline_detection_mean"]
    delta["delta_ood_alarm_vs_kcenter_original100"] = delta["ood_high_alarm_mean"] - delta["baseline_ood_alarm_mean"]

    rep_ablation = delta[delta["method_group"].isin(["A_baseline", "B_representation_repair"])].copy()
    margin_ablation = delta[delta["method_group"].isin(["A_baseline", "C_margin_deviation_adapter"])].copy()
    rep_ablation.to_csv(OUT / "representation_ablation_summary.csv", index=False)
    margin_ablation.to_csv(OUT / "margin_ablation_summary.csv", index=False)

    interaction = delta[
        delta["method"].str.contains("original100_plus_selected_source_rich_top32_margin", regex=False)
    ].copy()
    interaction.to_csv(OUT / "interaction_gain_summary.csv", index=False)
    margin_candidate = target_df[target_df["adapter"].eq("hard_negative_margin_lr")].copy()
    margin_candidate.to_csv(OUT / "margin_candidate_results.csv", index=False)

    row_level_manifest = pd.DataFrame(
        [
            {
                "row_level_scores_saved": False,
                "reason": "Issue19 is a controlled pilot with many method variants; row-level score persistence was already established in issue18. This run saves method-level metrics, threshold provenance, feature provenance, and hard-negative provenance to keep the pilot lightweight.",
                "canonical_row_level_reference": str(ISSUE18 / "row_level_scores.parquet"),
            }
        ]
    )
    row_level_manifest.to_csv(OUT / "row_level_scores_manifest.csv", index=False)

    best_hb2 = hb2_summary.sort_values("attack_high_detection_mean", ascending=False).head(10)
    best_by_holdout = summary_df.sort_values("attack_high_detection_mean", ascending=False).groupby(["holdout", "seed_group"], as_index=False).head(1)
    best_hb2_max = float(hb2_summary["attack_high_detection_mean"].max()) if not hb2_summary.empty else math.nan
    strong70 = bool(best_hb2_max >= 0.70)
    strong80 = bool(best_hb2_max >= 0.80)
    strong90 = bool(best_hb2_max >= 0.90)
    max_alarm_at_best = float(best_hb2.iloc[0]["ood_high_alarm_max"]) if not best_hb2.empty else math.nan
    if best_hb2_max >= 0.70:
        verdict = "strong_repair_candidate"
        next_step = "issue20 locked validation on a second harder split without changing feature/margin choices."
    elif best_hb2_max >= 0.45:
        verdict = "weak_positive_repair"
        next_step = "issue20 stronger margin/prototype or selected representation refinement, with locked provenance."
    else:
        verdict = "negative_or_insufficient_repair"
        next_step = "Stop minimal-linear route for holdout_bin_2; design representation-learning adapter or pivot to measurement and boundary paper."

    write_text(
        OUT / "preflight_lowguard_plus_repair_check.md",
        f"""
# Preflight LOW-GUARD+ Repair Check

- Method development uses train/support plus ID calibration and OOD validation only: True.
- source_rich row counts align with original100: True (`ID={x_id_sr.shape}`, `OOD={x_ood_sr.shape}`, `attack={x_attack_sr.shape}`).
- Feature selection uses attack eval / final OOD eval: False.
- Margin hard negatives use final OOD eval / attack eval: False.
- Support comes from local harder-holdout attack train pool: True.
- K-center support uses eval: False.
- Main OOD target remains 1%: True.
- 0.5% / 2% are sensitivity only: True.
- original100 fixed-guard LR baseline retained: True.
- Large neural sweep performed: False.
- Calibration slice note: issue19 follows the issue17/issue18 repair-line local-calibration slice for direct comparison to kcenter support repair; this is recorded as a comparability caveat, not hidden.
""",
    )
    write_text(
        OUT / "protocol.md",
        """
# Issue19 Protocol

This is a controlled LOW-GUARD+ repair pilot after issue18 diagnosed a representation/score bottleneck. It keeps the base LOW-GUARD-minimal ingredients fixed where possible: local harder-holdout supports, OOD benign weight 2, L2 LogisticRegression, and guarded ID-calibration + OOD-validation thresholding.

The pilot tests selected source_rich features and a lightweight hard-negative margin adapter. It does not train dA or Transformer, does not use final OOD eval or attack eval for feature/margin/threshold selection, and does not select 2% OOD target as a new method.
""",
    )
    write_text(
        OUT / "selected_representation_protocol.md",
        """
# Selected Representation Protocol

source_rich feature selection is performed per holdout/seed/topK using only selected attack supports, ID calibration, and OOD validation. The score combines attack-support versus OOD-validation standardized effect, attack-support versus ID-calibration effect, and a small OOD-tail safety term. A greedy redundancy pruning step skips features with absolute correlation >= 0.95 against already selected features.

Reported topK settings are top16 and top32. No attack eval or final OOD eval is used for feature selection.
""",
    )
    write_text(
        OUT / "margin_adapter_protocol.md",
        f"""
# Margin Adapter Protocol

The implemented margin/deviation pilot is a lightweight hard-negative LR adapter. For margin candidates, a first-pass LR model identifies the top {HARD_TAIL_FRAC:.0%} OOD-validation tail samples. The final LR is then refit with those OOD-validation hard negatives appended as negatives with pre-registered extra weights `{MARGIN_WEIGHTS}`.

The scaler is still fit only on ID benign train, OOD benign train, and selected attack supports. OOD validation hard negatives are transformed by that scaler. Final OOD eval and attack eval are never used for hard-negative mining or margin choice.
""",
    )
    write_text(
        OUT / "provenance_report.md",
        """
# Provenance Report

- Support provenance: `support_id_provenance.csv`; all support rows are inherited from issue17 kcenter support and remain local attack-train-pool only.
- Feature selection provenance: `selected_feature_report.csv`; selection uses supports + ID calibration + OOD validation only.
- Margin provenance: `hard_negative_report.csv`; hard negatives come from OOD validation tail only, never final OOD eval.
- Threshold provenance: `threshold_provenance.csv`; thresholds use ID calibration + OOD validation only.
- Scaler provenance: scaler fit remains ID train + OOD train + selected attack supports only.
""",
    )
    write_text(
        OUT / "claim_boundary.md",
        """
# Claim Boundary

## Can Say

- LOW-GUARD+ pilot improves or does not improve harder holdout if supported by the reported metrics.
- selected representation helps or does not help if the ablation supports it.
- hard-negative margin/deviation helps or does not help if the ablation supports it.

## Cannot Say

- harder holdout is solved unless detection and OOD metrics support it.
- the final method changed without locked validation.
- full LOW-GUARD generalized.
- external dataset validation is complete.
- A-zone readiness is achieved.
- margin or selected features were chosen using final eval.
""",
    )
    write_text(
        OUT / "risk_register.csv",
        """risk,severity,mitigation
feature selection leakage risk,high,Feature selection uses supports plus ID/OOD calibration-validation only; final eval flags are recorded.
margin overfitting risk,high,All margin candidates are reported; no final eval candidate selection is allowed.
validation overfitting risk,medium,This is a pilot and requires locked validation before claims.
topK cherry-picking risk,medium,top16 and top32 are both reported.
OOD alarm tradeoff risk,high,OOD alarm and feasible flags are reported for every method.
seed instability risk,medium,main and held-out seed groups are separated.
complexity creep risk,medium,No neural sweep or prototype/full GDA is run.
calibration slice comparability risk,medium,issue19 follows issue17/18 repair-line calibration for kcenter comparability and records this caveat.
""",
    )
    write_text(
        OUT / "recommended_next_action.md",
        f"""
# Recommended Next Action

## Verdict

`{verdict}`

## Unique First Choice

{next_step}

## Backup

If the best method is unstable across seed groups or raises OOD alarm, do not escalate claims. Return to representation diagnosis or a measurement/boundary framing.
""",
    )
    write_text(
        OUT / "summary.md",
        f"""
# Issue19 LOW-GUARD+ Representation and Margin Repair Pilot Summary

## Outcome

Verdict: `{verdict}`.

Best holdout_bin_2 mean detection across reported seed groups/methods: `{best_hb2_max:.6f}`.

Reached >=0.70: `{strong70}`. Reached >=0.80: `{strong80}`. Reached >=0.90: `{strong90}`.

OOD alarm at the top holdout_bin_2 row max: `{max_alarm_at_best:.6f}`.

## Top holdout_bin_2 rows

{md_table(best_hb2[["holdout", "method", "seed_group", "attack_high_detection_mean", "attack_high_detection_min", "ood_high_alarm_mean", "ood_high_alarm_max", "feasible_rate"]])}

## Best by holdout / seed group

{md_table(best_by_holdout[["holdout", "seed_group", "method", "attack_high_detection_mean", "ood_high_alarm_mean", "ood_high_alarm_max", "feasible_rate"]])}

## Interpretation

This is a controlled pilot, not locked validation. A positive pilot still requires a locked second validation before the paper can change the final method. A negative pilot means the minimal-linear route is insufficient for holdout_bin_2 and should not be dressed up as solved.

## Safety

- Manuscript modified: False.
- Historical experimental numbers modified: False.
- dA / Transformer trained: False.
- MLP / prototype / full neural GDA run: False.
- OOD weight changed: False.
- Final eval used for feature/margin/threshold selection: False.
""",
    )
    write_text(
        OUT / "doc_update_patch_suggestion.md",
        """
# Doc Update Patch Suggestion

Append to mainline docs only after review:

`issue19 tests LOW-GUARD+ selected representation and hard-negative margin repair after issue18 diagnosed a representation/score bottleneck. Treat as pilot evidence only; locked validation is required before paper integration.`
""",
    )
    config = {
        "run": "issue19_lowguard_plus_representation_margin_repair_pilot_2026-05-18",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "holdouts": MAIN_HOLDOUTS,
        "seeds": SEEDS,
        "positive_budget": POSITIVE_BUDGET,
        "topk_values": TOPK_VALUES,
        "margin_weights": MARGIN_WEIGHTS,
        "hard_tail_frac": HARD_TAIL_FRAC,
        "target_alarm": TARGET_ALARM,
        "verdict": verdict,
        "paths": paths,
    }
    write_text(OUT / "config.json", json.dumps(config, ensure_ascii=False, indent=2))
    manifest_rows = []
    for path in sorted(OUT.rglob("*")):
        if path.is_file():
            manifest_rows.append(
                {
                    "file": str(path.relative_to(OUT)),
                    "bytes": path.stat().st_size,
                    "role": "issue19_output",
                }
            )
    pd.DataFrame(manifest_rows).to_csv(OUT / "manifest.csv", index=False)
    print(f"[done] wrote {OUT}")


if __name__ == "__main__":
    main()
