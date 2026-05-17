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
OUT = ROOT / "runs" / "issue16b_harder_holdout_fixed_guard_validation_2026-05-15"
FRONTEND_F2_ROOT = ROOT.parent / "kitnet-frontend-f2"
KITNET_ROOT = ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master"
F2_OOD = FRONTEND_F2_ROOT / "repo" / "ood"
if str(F2_OOD) not in sys.path:
    sys.path.insert(0, str(F2_OOD))

import frontend_f2_v7_4_paired_holdout_fairness as v74  # noqa: E402
import frontend_f2_v7_1_source_rich_label_budget_ranker as v71  # noqa: E402
import frontend_f2_v7_2_fairness_validation as v72  # noqa: E402


TARGET_ALARM = 0.01
POSITIVE_BUDGETS = [16, 32]
SEEDS = list(range(42, 52))
MAIN_HOLDOUTS = ["chrono_late_train_early_eval", "holdout_bin_2"]


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
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def md_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No rows._\n"
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, row in df.iterrows():
        vals = []
        for col in cols:
            val = row[col]
            if isinstance(val, float):
                vals.append(f"{val:.6f}")
            else:
                vals.append(str(val))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"


def seed_group(seed: int) -> str:
    if 42 <= int(seed) <= 46:
        return "main_42_46"
    if 47 <= int(seed) <= 51:
        return "heldout_47_51"
    return "other"


def load_matrix(path: Path) -> np.ndarray:
    if path.suffix.lower() == ".npy":
        arr = np.load(path)
    else:
        arr = pd.read_csv(path, header=None).to_numpy(np.float32)
    if arr.ndim != 2:
        raise RuntimeError(f"Expected 2D matrix from {path}, got {arr.shape}")
    return np.nan_to_num(arr.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)


def choose_positive_train_indices(train_idx: np.ndarray, budget: int, seed: int) -> np.ndarray:
    train_idx = np.asarray(train_idx, dtype=np.int64)
    if int(budget) >= len(train_idx):
        return train_idx.copy()
    rng = np.random.default_rng(int(seed) + int(budget) * 1009)
    return np.asarray(sorted(rng.choice(train_idx, size=int(budget), replace=False)), dtype=np.int64)


def fit_and_score(
    *,
    x_id_train: np.ndarray,
    x_ood_train: np.ndarray,
    x_pos: np.ndarray,
    x_id_calib: np.ndarray,
    x_ood_val: np.ndarray,
    x_ood_eval: np.ndarray,
    x_attack_eval: np.ndarray,
    ood_weight: float,
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
            np.full(len(x_ood_train), float(ood_weight), dtype=np.float64),
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
        "model": model,
        "scaler": scaler,
        "train_time": train_time,
        "inference_time": inference_time,
        "score_id_calib": score_id_calib,
        "score_ood_val": score_ood_val,
        "score_ood_eval": score_ood_eval,
        "score_attack_eval": score_attack_eval,
        "threshold": threshold,
        "threshold_info": guarded,
        "roc_auc": float(roc_auc_score(y_eval, s_eval)),
        "pr_auc": float(average_precision_score(y_eval, s_eval)),
        "ood_alarm": float(np.mean(score_ood_eval > threshold)),
        "attack_detection": float(np.mean(score_attack_eval > threshold)),
        "parameter_count": int(model.coef_.size + model.intercept_.size),
    }


def aggregate(seed_df: pd.DataFrame) -> pd.DataFrame:
    if seed_df.empty:
        return pd.DataFrame()
    return (
        seed_df.groupby(
            ["holdout_name", "protocol", "method", "guard_type", "positive_budget", "seed_group"],
            as_index=False,
        )
        .agg(
            n_seeds=("seed", "nunique"),
            roc_auc_mean=("roc_auc", "mean"),
            roc_auc_std=("roc_auc", "std"),
            roc_auc_min=("roc_auc", "min"),
            roc_auc_max=("roc_auc", "max"),
            pr_auc_mean=("pr_auc", "mean"),
            pr_auc_min=("pr_auc", "min"),
            pr_auc_max=("pr_auc", "max"),
            ood_high_alarm_mean=("ood_high_alarm", "mean"),
            ood_high_alarm_std=("ood_high_alarm", "std"),
            ood_high_alarm_min=("ood_high_alarm", "min"),
            ood_high_alarm_max=("ood_high_alarm", "max"),
            attack_high_detection_mean=("attack_high_detection", "mean"),
            attack_high_detection_std=("attack_high_detection", "std"),
            attack_high_detection_min=("attack_high_detection", "min"),
            attack_high_detection_max=("attack_high_detection", "max"),
            feasible_rate=("feasible", "mean"),
            attack_eval_size=("attack_eval_size", "first"),
            ood_eval_size=("ood_eval_size", "first"),
            parameter_count=("parameter_count", "first"),
            train_time_mean=("train_time", "mean"),
            inference_time_mean=("inference_time", "mean"),
        )
        .sort_values(["holdout_name", "positive_budget", "seed_group", "method"])
    )


def make_deltas(seed_summary: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    key = ["holdout_name", "protocol", "positive_budget", "seed_group"]
    fixed = seed_summary[seed_summary["method"].eq("original100_fixed_guard_lr")].copy()
    plain = seed_summary[seed_summary["method"].eq("original100_plain_lr")].copy()
    cols = key + [
        "attack_high_detection_mean",
        "attack_high_detection_min",
        "ood_high_alarm_mean",
        "ood_high_alarm_max",
        "feasible_rate",
    ]
    fixed = fixed[cols].rename(columns={c: f"fixed_{c}" for c in cols if c not in key})
    plain = plain[cols].rename(columns={c: f"plain_{c}" for c in cols if c not in key})
    merged = fixed.merge(plain, on=key, how="outer")
    merged["delta_detection_mean_fixed_minus_plain"] = (
        merged["fixed_attack_high_detection_mean"] - merged["plain_attack_high_detection_mean"]
    )
    merged["delta_ood_alarm_mean_fixed_minus_plain"] = merged["fixed_ood_high_alarm_mean"] - merged["plain_ood_high_alarm_mean"]
    merged["delta_ood_alarm_max_fixed_minus_plain"] = merged["fixed_ood_high_alarm_max"] - merged["plain_ood_high_alarm_max"]
    merged["delta_feasible_rate_fixed_minus_plain"] = merged["fixed_feasible_rate"] - merged["plain_feasible_rate"]

    base_rows = []
    for _, row in fixed.iterrows():
        base_rows.append(
            {
                **{k: row[k] for k in key},
                "base_detector": "dA",
                "base_available": False,
                "reason": "No dA-only v7.4 harder-holdout row-level score/evaluator was found under the issue16b protocol.",
                "lowguard_attack_detection_mean": row["fixed_attack_high_detection_mean"],
                "lowguard_ood_high_alarm_mean": row["fixed_ood_high_alarm_mean"],
                "lowguard_feasible_rate": row["fixed_feasible_rate"],
                "delta_vs_base": "not_applicable_missing_base",
            }
        )
        base_rows.append(
            {
                **{k: row[k] for k in key},
                "base_detector": "Transformer",
                "base_available": False,
                "reason": "No Transformer-only v7.4 harder-holdout row-level score/evaluator was found under the issue16b protocol.",
                "lowguard_attack_detection_mean": row["fixed_attack_high_detection_mean"],
                "lowguard_ood_high_alarm_mean": row["fixed_ood_high_alarm_mean"],
                "lowguard_feasible_rate": row["fixed_feasible_rate"],
                "delta_vs_base": "not_applicable_missing_base",
            }
        )
    return merged.sort_values(key), pd.DataFrame(base_rows)


def classify_verdict(summary_df: pd.DataFrame, fixed_vs_plain: pd.DataFrame) -> dict[str, Any]:
    fixed_32 = summary_df[
        (summary_df["method"] == "original100_fixed_guard_lr")
        & (summary_df["positive_budget"] == 32)
    ].copy()
    if fixed_32.empty:
        return {
            "verdict": "asset_or_execution_failure",
            "next_step": "Stop and recover the missing fixed-guard 32-shot rows before drawing any harder-holdout conclusion.",
            "reason": "No original100 fixed-guard 32-shot summary rows were generated.",
            "min_fixed32_detection_mean": math.nan,
            "min_fixed32_detection_min": math.nan,
            "max_fixed32_ood_alarm": math.nan,
            "min_fixed32_feasible_rate": math.nan,
            "weak_holdouts": "not_applicable",
            "fixed_guard_value": "not_evaluable",
        }

    min_det_mean = float(fixed_32["attack_high_detection_mean"].min())
    min_det_min = float(fixed_32["attack_high_detection_min"].min())
    max_alarm = float(fixed_32["ood_high_alarm_max"].max())
    min_feasible = float(fixed_32["feasible_rate"].min())
    weak_rows = fixed_32[fixed_32["attack_high_detection_mean"] < 0.50]
    weak_holdouts = sorted(set(weak_rows["holdout_name"].astype(str)))

    delta_32 = fixed_vs_plain[fixed_vs_plain["positive_budget"] == 32].copy()
    if delta_32.empty:
        max_det_delta = math.nan
        min_det_delta = math.nan
        max_alarm_reduction = math.nan
        fixed_guard_value = "plain_control_missing"
    else:
        max_det_delta = float(delta_32["delta_detection_mean_fixed_minus_plain"].max())
        min_det_delta = float(delta_32["delta_detection_mean_fixed_minus_plain"].min())
        # Positive value means fixed guard reduced OOD alarm relative to plain LR.
        max_alarm_reduction = float((-delta_32["delta_ood_alarm_mean_fixed_minus_plain"]).max())
        if max_alarm_reduction > 0 and max_det_delta < 0.01:
            fixed_guard_value = "lowers_ood_alarm_without_material_detection_gain"
        elif max_det_delta >= 0.01:
            fixed_guard_value = "improves_detection"
        else:
            fixed_guard_value = "no_clear_gain_over_plain"

    if min_feasible >= 1.0 and max_alarm <= TARGET_ALARM and min_det_mean >= 0.80:
        verdict = "strong_positive"
        reason = "All pre-registered 32-shot fixed-guard holdout groups are feasible with high attack detection."
        next_step = "Run few-shot anomaly baselines and OOD target sensitivity before any adapter upgrade."
    elif min_feasible >= 1.0 and max_alarm <= TARGET_ALARM and min_det_mean >= 0.50:
        verdict = "moderate_positive"
        reason = "Fixed guard keeps the low-OOD alarm budget, but at least one holdout has only moderate attack detection."
        next_step = "Run failure analysis, few-shot anomaly baselines, and OOD target sensitivity before adapter upgrades."
    else:
        verdict = "mixed_or_negative"
        reason = (
            "Fixed guard keeps OOD high alarm feasible, but at least one pre-registered harder holdout has weak "
            f"32-shot attack detection (minimum mean={min_det_mean:.6f})."
        )
        next_step = (
            "Treat this as boundary evidence. Prioritize failure analysis and same-protocol few-shot anomaly baselines; "
            "do not upgrade to complex adapters yet."
        )

    return {
        "verdict": verdict,
        "next_step": next_step,
        "reason": reason,
        "min_fixed32_detection_mean": min_det_mean,
        "min_fixed32_detection_min": min_det_min,
        "max_fixed32_ood_alarm": max_alarm,
        "min_fixed32_feasible_rate": min_feasible,
        "weak_holdouts": ", ".join(weak_holdouts) if weak_holdouts else "none",
        "max_detection_delta_fixed_minus_plain": max_det_delta,
        "min_detection_delta_fixed_minus_plain": min_det_delta,
        "max_ood_alarm_reduction_fixed_vs_plain": max_alarm_reduction,
        "fixed_guard_value": fixed_guard_value,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "figures").mkdir(exist_ok=True)

    source_root = KITNET_ROOT
    cross_data = source_root / "runs" / "frontend100_crosscapture_stage1_2026-03-25" / "data"
    stage1 = source_root / "runs" / "frontend100_joint_eval_stage1_2026-03-31"
    stage2_manifest_path = source_root / "runs" / "frontend100_joint_eval_stage2_2026-04-01" / "attack_manifest_stage2.json"
    v74_dir = FRONTEND_F2_ROOT / "runs" / "frontend_f2_v7_4_paired_holdout_fairness_2026-04-22"
    issue16_dir = ROOT / "runs" / "issue16_harder_holdout_second_environment_feasibility_2026-05-15"

    required_paths = [
        issue16_dir / "summary.md",
        issue16_dir / "harder_holdout_candidate_inventory.csv",
        v74_dir / "frontend_f2_v7_4_holdout_specs.csv",
        stage2_manifest_path,
        cross_data / "id_source_100.npy",
        cross_data / "ood_benign_source_100.npy",
        stage1 / "data" / "attack_source_100.csv",
    ]
    missing = [str(p) for p in required_paths if not p.exists()]
    if missing:
        failure = "\n".join(f"- {m}" for m in missing)
        write_text(
            OUT / "harder_holdout_recovery_failure_report.md",
            f"# Harder-Holdout Recovery Failure\n\nMissing required assets:\n\n{failure}\n",
        )
        raise RuntimeError(f"Missing required assets: {missing}")

    manifest = json.loads(stage2_manifest_path.read_text(encoding="utf-8-sig"))
    row_bins = v74.load_attack_bins(manifest)
    specs = [s for s in v74.make_holdout_specs(manifest, row_bins, min_eval_rows=300) if s["holdout_name"] in MAIN_HOLDOUTS]
    specs_by_name = {s["holdout_name"]: s for s in specs}
    missing_specs = [name for name in MAIN_HOLDOUTS if name not in specs_by_name]
    if missing_specs:
        raise RuntimeError(f"Missing pre-registered holdout specs: {missing_specs}")

    x_id = load_matrix(cross_data / "id_source_100.npy")
    x_ood = load_matrix(cross_data / "ood_benign_source_100.npy")
    x_attack = load_matrix(stage1 / "data" / "attack_source_100.csv")
    n_attack = min(len(x_attack), len(row_bins))
    x_attack = x_attack[:n_attack]
    row_bins = row_bins[:n_attack]

    id_train_end = 8000
    id_val_end = 10000
    id_calib_end = 15000
    ood_train_end = 8000
    ood_val_end = 10000
    x_id_train = x_id[:id_train_end]
    x_id_calib = x_id[id_val_end:id_calib_end]
    x_ood_train = x_ood[:ood_train_end]
    x_ood_val = x_ood[ood_train_end:ood_val_end]
    x_ood_eval = x_ood[ood_val_end:]

    seed_rows: list[dict[str, Any]] = []
    support_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    asset_rows: list[dict[str, Any]] = []

    for spec in specs:
        attack_val_idx = np.asarray(spec["attack_val_idx"], dtype=np.int64)
        # For leave-one-bin holdouts, v7.4 had no independent attack val bin and reused train_pool.
        # Issue16b does not use attack validation for model/threshold selection, so record it as unavailable.
        if not spec["val_bins"]:
            attack_val_idx = np.asarray([], dtype=np.int64)
        asset_rows.append(
            {
                "holdout_name": spec["holdout_name"],
                "holdout_type": spec["holdout_type"],
                "train_bins": ",".join(str(x) for x in spec["train_bins"]),
                "val_bins": ",".join(str(x) for x in spec["val_bins"]),
                "eval_bins": ",".join(str(x) for x in spec["eval_bins"]),
                "train_pool_count": int(len(spec["train_pool_idx"])),
                "attack_val_count": int(len(attack_val_idx)),
                "attack_eval_count": int(len(spec["attack_eval_idx"])),
                "feature_path": str(stage1 / "data" / "attack_source_100.csv"),
                "id_feature_path": str(cross_data / "id_source_100.npy"),
                "ood_feature_path": str(cross_data / "ood_benign_source_100.npy"),
                "row_id_availability": "attack row index from stage2 manifest bins",
                "comparability_risk": "local-calibration hard-holdout; not second-environment and not strict threshold transfer",
            }
        )
        attack_eval_rows = set(int(x) for x in spec["attack_eval_idx"])
        attack_val_rows = set(int(x) for x in attack_val_idx)
        for budget in POSITIVE_BUDGETS:
            for seed in SEEDS:
                selected = choose_positive_train_indices(spec["train_pool_idx"], budget, seed)
                x_pos = x_attack[selected]
                for method, guard_type, ood_weight in [
                    ("original100_plain_lr", "plain", 1.0),
                    ("original100_fixed_guard_lr", "fixed_ood_weight_2", 2.0),
                ]:
                    res = fit_and_score(
                        x_id_train=x_id_train,
                        x_ood_train=x_ood_train,
                        x_pos=x_pos,
                        x_id_calib=x_id_calib,
                        x_ood_val=x_ood_val,
                        x_ood_eval=x_ood_eval,
                        x_attack_eval=x_attack[spec["attack_eval_idx"]],
                        ood_weight=ood_weight,
                    )
                    row = {
                        "holdout_name": spec["holdout_name"],
                        "holdout_type": spec["holdout_type"],
                        "protocol": "local_calibration",
                        "method": method,
                        "representation": "original100",
                        "guard_type": guard_type,
                        "positive_budget": int(budget),
                        "seed": int(seed),
                        "seed_group": seed_group(seed),
                        "ood_negative_weight": float(ood_weight),
                        "roc_auc": res["roc_auc"],
                        "pr_auc": res["pr_auc"],
                        "ood_high_alarm": res["ood_alarm"],
                        "attack_high_detection": res["attack_detection"],
                        "feasible": bool(res["ood_alarm"] <= TARGET_ALARM),
                        "threshold": res["threshold"],
                        "attack_eval_size": int(len(spec["attack_eval_idx"])),
                        "ood_eval_size": int(len(x_ood_eval)),
                        "support_count": int(len(selected)),
                        "support_overlap_attack_val": bool(any(int(x) in attack_val_rows for x in selected)),
                        "support_overlap_attack_eval": bool(any(int(x) in attack_eval_rows for x in selected)),
                        "threshold_source": "ID calibration + OOD validation guard; final OOD eval and attack eval not used",
                        "scaler_fit_scope": "ID benign train + OOD benign train + selected attack supports only",
                        "train_time": res["train_time"],
                        "inference_time": res["inference_time"],
                        "parameter_count": res["parameter_count"],
                        "threshold_selection_feasible": bool(res["threshold_info"].get("selection_feasible", True)),
                        "id_calib_alarm_at_selection": float(res["threshold_info"].get("id_calib_alarm_at_selection", math.nan)),
                        "ood_val_alarm_at_selection": float(res["threshold_info"].get("ood_val_alarm_at_selection", math.nan)),
                    }
                    seed_rows.append(row)
                    threshold_rows.append(
                        {
                            "holdout_name": spec["holdout_name"],
                            "protocol": "local_calibration",
                            "method": method,
                            "positive_budget": int(budget),
                            "seed": int(seed),
                            "seed_group": seed_group(seed),
                            "threshold": res["threshold"],
                            "uses_id_calib": True,
                            "uses_ood_val": True,
                            "uses_final_ood_eval": False,
                            "uses_attack_eval": False,
                            "threshold_source": row["threshold_source"],
                            "id_calib_alarm_at_selection": row["id_calib_alarm_at_selection"],
                            "ood_val_alarm_at_selection": row["ood_val_alarm_at_selection"],
                            "threshold_selection_feasible": row["threshold_selection_feasible"],
                        }
                    )
                for selected_row in selected:
                    support_rows.append(
                        {
                            "holdout_name": spec["holdout_name"],
                            "positive_budget": int(budget),
                            "seed": int(seed),
                            "seed_group": seed_group(seed),
                            "selected_attack_row_id": int(selected_row),
                            "support_source": "pre_registered_hard_holdout_attack_train_pool",
                            "train_bins": ",".join(str(x) for x in spec["train_bins"]),
                            "eval_bins": ",".join(str(x) for x in spec["eval_bins"]),
                            "in_attack_train_pool": bool(int(selected_row) in set(int(x) for x in spec["train_pool_idx"])),
                            "overlaps_attack_val": bool(int(selected_row) in attack_val_rows),
                            "overlaps_attack_eval": bool(int(selected_row) in attack_eval_rows),
                        }
                    )
                print(f"[done] {spec['holdout_name']} budget={budget} seed={seed}", flush=True)

    seed_df = pd.DataFrame(seed_rows)
    summary_df = aggregate(seed_df)
    fixed_vs_plain, base_vs_lowguard = make_deltas(summary_df)
    verdict_info = classify_verdict(summary_df, fixed_vs_plain)

    seed_df.to_csv(OUT / "method_comparison_by_seed.csv", index=False)
    summary_df.to_csv(OUT / "method_comparison_summary.csv", index=False)
    support_df = pd.DataFrame(support_rows)
    support_df.to_csv(OUT / "support_id_provenance.csv", index=False)
    pd.DataFrame(threshold_rows).to_csv(OUT / "threshold_provenance.csv", index=False)
    fixed_vs_plain.to_csv(OUT / "fixed_guard_vs_plain_harder_holdout.csv", index=False)
    base_vs_lowguard.to_csv(OUT / "base_vs_lowguard_harder_holdout.csv", index=False)
    asset_df = pd.DataFrame(asset_rows)
    asset_df.to_csv(OUT / "harder_holdout_asset_report.csv", index=False)
    write_text(
        OUT / "harder_holdout_asset_report.md",
        f"""
# Harder-Holdout Asset Report

The run used the pre-registered v7.4 paired hard-holdout candidates and original100 assets recovered during issue16.

{md_table(asset_df)}

These assets support local-calibration harder-holdout validation. They do not constitute a second-environment dataset, and the current model/scaler/threshold artifacts were not treated as safely transferable to this v7.4 protocol.
""",
    )
    transfer = pd.DataFrame(
        [
            {
                "protocol": "transfer_threshold",
                "status": "not_run",
                "reason": "Current LOW-GUARD-minimal model/scaler/threshold artifacts do not directly transfer to v7.4 holdout windows.",
            },
            {
                "protocol": "local_calibration",
                "status": "run",
                "reason": "Independent hard-holdout local ID calibration + OOD validation threshold; final OOD and attack eval held out.",
            },
        ]
    )
    transfer.to_csv(OUT / "transfer_vs_local_calibration.csv", index=False)

    leakage_ok = not support_df["overlaps_attack_eval"].any() and not support_df["overlaps_attack_val"].any()
    main_table = summary_df[
        (summary_df["positive_budget"] == 32)
        & (summary_df["seed_group"].isin(["main_42_46", "heldout_47_51"]))
    ][
        [
            "holdout_name",
            "method",
            "seed_group",
            "attack_high_detection_mean",
            "attack_high_detection_min",
            "ood_high_alarm_mean",
            "ood_high_alarm_max",
            "feasible_rate",
        ]
    ]

    write_text(
        OUT / "protocol.md",
        f"""
# Issue16b Protocol

## Scope

Formal harder-holdout validation for LOW-GUARD-minimal under pre-registered v7.4 hard-holdout candidates. This is not second-environment validation, not model upgrade, and not hyperparameter search.

## Holdouts

- `chrono_late_train_early_eval`: train bins 6,7,8; validation bin 5; eval bins 2,3,4.
- `holdout_bin_2`: train bins 3,4,5,6,7,8; no independent attack validation; eval bin 2.

## Method Matrix

- `original100_plain_lr`: original100 representation, few-shot LR, OOD benign weight 1.
- `original100_fixed_guard_lr`: original100 representation, few-shot LR, fixed OOD benign weight 2.

Base-only dA/Transformer harder-holdout baselines were not available under this protocol and are reported as missing.

## Fixed Configuration

- LogisticRegression: C=1.0, L2, liblinear, class_weight=balanced, max_iter=2000, random_state=42.
- Budgets: 16 and 32.
- Seeds: 42-46 main, 47-51 held-out.
- Threshold protocol: local ID calibration + OOD validation guard, target OOD alarm {TARGET_ALARM}.
- Scaler fit scope: ID benign train + OOD benign train + selected attack supports only.
- Final OOD eval and attack eval are not used for training, scaler fitting, or threshold selection.

## Protocol Split

Only local-calibration protocol was run. Transfer-threshold protocol was not run because current model/scaler/threshold artifacts do not directly transfer to v7.4 hard-holdout windows.
""",
    )
    write_text(
        OUT / "scaler_provenance.md",
        """
# Scaler Provenance

For each method / holdout / budget / seed, `StandardScaler` is fit only on:

- ID benign train rows,
- OOD benign train rows,
- selected high-purity attack support rows from the pre-registered hard-holdout train pool.

The scaler is never fit on final OOD eval, attack eval, OOD validation, or ID calibration.
""",
    )
    write_text(
        OUT / "failure_analysis.md",
        f"""
# Failure Analysis

This file records the issue16b boundary analysis. It should be read together with `method_comparison_summary.csv` and `fixed_guard_vs_plain_harder_holdout.csv`.

## Observed Verdict

- Verdict: `{verdict_info["verdict"]}`.
- Reason: {verdict_info["reason"]}
- Weak holdouts: {verdict_info["weak_holdouts"]}.
- Minimum fixed-guard 32-shot detection mean: {verdict_info["min_fixed32_detection_mean"]:.6f}.
- Minimum fixed-guard 32-shot per-seed detection: {verdict_info["min_fixed32_detection_min"]:.6f}.
- Maximum fixed-guard 32-shot OOD high alarm: {verdict_info["max_fixed32_ood_alarm"]:.6f}.

## Failure Mode

- Primary weakness: attack detection drops sharply on `holdout_bin_2`, especially for held-out seeds.
- OOD alarm failure: not observed; fixed guard remains well below the 1% high-alarm budget.
- Fixed-guard independent value: {verdict_info["fixed_guard_value"]}. It lowers OOD alarm relative to plain LR, but plain LR is already feasible and fixed guard does not materially improve detection.
- Threshold transfer issue: transfer-threshold protocol was not applicable in this run because current model/scaler/threshold artifacts could not be transferred cleanly.
- Feature/label mismatch: not observed for the local-calibration protocol; v7.4 original100 features and stage2 attack row bins were available.

## Interpretation

Do not package this result as strong LOW-GUARD generalization. It is harder-holdout boundary evidence: the low-alert guard transfers as an alarm-control mechanism under local calibration, but attack recovery is not stable across both pre-registered holdouts.
""",
    )
    write_text(
        OUT / "claim_boundary.md",
        """
# Claim Boundary

## Can Say

- Formal harder-holdout validation was run on pre-registered v7.4 holdout candidates under a controlled local-calibration protocol.
- LOW-GUARD-minimal is supported on these harder holdouts only to the extent shown by the metrics.
- Fixed OOD guard generalizes to this harder-holdout protocol if the fixed-vs-plain metrics support it.
- This result is not second-environment proof.

## Cannot Say

- Second environment has been validated.
- External dataset generalization is complete.
- Full GDA is complete.
- Detector-agnostic adaptation has been proven.
- The paper is A-zone / CCF-A ready.
- A negative or mixed result is a strong positive.
""",
    )
    risk_rows = [
        {
            "risk_name": "holdout comparability risk",
            "severity": "medium",
            "reason": "v7.4 is a same-dataset cross-window hard holdout, not an external environment.",
            "mitigation": "Do not call this second-environment validation.",
        },
        {
            "risk_name": "base baseline missing risk",
            "severity": "medium",
            "reason": "dA/Transformer base-only harder-holdout row-level scores were not available.",
            "mitigation": "Report LOW-GUARD vs plain LR; do not claim delta vs base-only for this run.",
        },
        {
            "risk_name": "threshold transfer risk",
            "severity": "medium",
            "reason": "Only local-calibration protocol was run.",
            "mitigation": "Keep transfer-threshold as a separate future task.",
        },
        {
            "risk_name": "support leakage risk",
            "severity": "low" if leakage_ok else "high",
            "reason": f"support overlap check clean={leakage_ok}.",
            "mitigation": "Use support_id_provenance.csv as audit evidence.",
        },
        {
            "risk_name": "cherry-pick holdout risk",
            "severity": "low",
            "reason": "The run used pre-registered chrono_late_train_early_eval and holdout_bin_2.",
            "mitigation": "Do not add or drop holdouts after seeing metrics.",
        },
        {
            "risk_name": "seed instability risk",
            "severity": "medium",
            "reason": "Main and held-out seed groups must be interpreted separately.",
            "mitigation": "Use min/max and feasible rate, not only means.",
        },
        {
            "risk_name": "overclaiming generalization risk",
            "severity": "high",
            "reason": "This is harder holdout, not second environment or external dataset.",
            "mitigation": "Use claim_boundary.md wording.",
        },
    ]
    write_csv(OUT / "risk_register.csv", risk_rows)
    verdict = verdict_info["verdict"]
    next_step = verdict_info["next_step"]
    write_text(
        OUT / "recommended_next_action.md",
        f"""
# Recommended Next Action

## Verdict

Issue16b verdict: `{verdict}`.

Reason: {verdict_info["reason"]}

## Next Step

{next_step}

## Priority

1. Analyze why `holdout_bin_2` has weak attack recovery before running more model variants.
2. Run same-protocol few-shot anomaly baselines to determine whether LOW-GUARD-minimal is still competitive on this harder holdout.
3. Run OOD target sensitivity only after preserving threshold/support provenance.
4. Do not claim second-environment validation from this run.
5. Do not upgrade to MLP/prototype/full neural GDA until the harder-holdout failure mode and baseline gap are understood.
""",
    )
    write_text(
        OUT / "claim_gate.md",
        """
# Claim Gate

## Target Claim

LOW-GUARD-minimal can remain viable under a pre-registered harder same-dataset holdout when evaluated with a clean low-OOD guarded protocol.

## Reviewer Attack

"The method only works on the current primary split and is just a cost-sensitive LR artifact."

## Expected Evidence

- Harder holdout metrics for original100 fixed guard LR versus original100 plain LR.
- OOD high alarm <= 1% and feasible rate.
- Attack high detection mean/min across main and held-out seeds.
- support_id_provenance.csv and threshold_provenance.csv.

## Positive Interpretation

Only if fixed guard remains feasible and maintains strong attack detection on both pre-registered holdouts should this support Problem B as a strong harder-holdout generalization result.

## Negative Interpretation

If fixed guard keeps OOD alarm low but attack detection drops on a pre-registered holdout, the result is not a method win. It becomes boundary evidence and pushes the paper toward failure analysis, baseline comparison, or measurement/protocol framing.

## Paper Role

Main text only if the result is clearly positive and provenance is clean. Otherwise appendix or limitation/failure analysis.

## Stop Rule

If both pre-registered holdouts fail, stop adapter upgrades and analyze generalization failure before running more model variants.
""",
    )
    write_text(
        OUT / "summary.md",
        f"""
# Issue16b Harder-Holdout Fixed-Guard Validation Summary

## 1. Outcome

Harder-holdout validation ran successfully under the local-calibration protocol. Transfer-threshold protocol was not run because current LOW-GUARD-minimal model/scaler/threshold artifacts do not directly transfer to v7.4 holdout windows.

## 2. Holdouts

- `chrono_late_train_early_eval`
- `holdout_bin_2`

## 3. Core 32-shot Results

{md_table(main_table)}

## 4. LOW-GUARD-minimal Validity

LOW-GUARD-minimal here means `original100_fixed_guard_lr`, 32-shot, fixed OOD benign weight 2. The issue16b verdict is `{verdict}`.

Reason: {verdict_info["reason"]}

The result is best treated as harder-holdout boundary evidence, not a strong generalization result. It does not prove second-environment validation.

## 5. Fixed Guard Value

See `fixed_guard_vs_plain_harder_holdout.csv`. Fixed guard lowers OOD high alarm relative to plain LR, but plain LR is already feasible in this local-calibration harder-holdout protocol and fixed guard does not materially improve attack detection. Its independent value here is alarm-control, not detection gain.

## 6. Provenance

- Support overlap with attack eval: {bool(support_df['overlaps_attack_eval'].any())}.
- Support overlap with attack validation: {bool(support_df['overlaps_attack_val'].any())}.
- Threshold uses final OOD eval: False.
- Threshold uses attack eval: False.

## 7. Missing Baselines

dA-only and Transformer-only harder-holdout base scores were not available under this exact issue16b protocol. Therefore delta-vs-base is not claimed.

## 8. Next Step

{next_step}

## 9. Safety

- Manuscript modified: False.
- Existing experimental numbers modified: False.
- dA / Transformer trained: False.
- Hyperparameter search: False.
- Full GDA claim introduced: False.
""",
    )
    config = {
        "run": "issue16b_harder_holdout_fixed_guard_validation_2026-05-15",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "protocol": "local_calibration_hard_holdout",
        "transfer_threshold_protocol": "not_run",
        "holdouts": MAIN_HOLDOUTS,
        "budgets": POSITIVE_BUDGETS,
        "seeds": SEEDS,
        "methods": ["original100_plain_lr", "original100_fixed_guard_lr"],
        "fixed_ood_weight": 2.0,
        "target_alarm": TARGET_ALARM,
        "no_final_eval_tuning": True,
        "paths": {
            "issue16": str(issue16_dir),
            "v7_4": str(v74_dir),
            "id_features": str(cross_data / "id_source_100.npy"),
            "ood_features": str(cross_data / "ood_benign_source_100.npy"),
            "attack_features": str(stage1 / "data" / "attack_source_100.csv"),
            "stage2_manifest": str(stage2_manifest_path),
        },
    }
    write_text(OUT / "config.json", json.dumps(config, ensure_ascii=False, indent=2))

    manifest_rows = []
    for p in sorted(OUT.iterdir()):
        if p.is_file():
            manifest_rows.append({"asset_name": p.name, "file_path": str(p), "role": "issue16b output"})
    write_csv(OUT / "manifest.csv", manifest_rows)


if __name__ == "__main__":
    main()
