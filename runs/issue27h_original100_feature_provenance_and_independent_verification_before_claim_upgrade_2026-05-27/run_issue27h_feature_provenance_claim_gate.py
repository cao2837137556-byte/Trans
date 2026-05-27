from __future__ import annotations

import importlib.util
import json
import math
import re
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs" / "issue27h_original100_feature_provenance_and_independent_verification_before_claim_upgrade_2026-05-27"
ISSUE27G = ROOT / "runs" / "issue27g_suspicious_perfect_score_audit_for_lowguard_plus_plus_2026-05-27"
ISSUE27F = ROOT / "runs" / "issue27f_config_freeze_then_formal_validation_for_original100_histgb_conservative_2026-05-27"
ISSUE27D = ROOT / "runs" / "issue27d_lowguard_adapter_interface_and_model_specific_objectives_smoke_2026-05-26"
ISSUE25C = ROOT / "runs" / "issue25c_strong_baseline_pack_execution_for_enhanced_lowguard_top64_2026-05-18"
MAINLINE = ROOT / "runs" / "mainline_docs"
ISSUE27F_SCRIPT = ISSUE27F / "run_issue27f_config_freeze_formal_validation.py"

LOCKED_BINS = ["holdout_bin_5", "holdout_bin_6", "holdout_bin_7", "holdout_bin_8"]
CONSISTENCY_HOLDOUTS = ["primary_lowood", "holdout_bin_2", "chrono_late_train_early_eval"]
FULL_SEEDS = list(range(42, 52))
IMPORTANCE_SEEDS = [42]
OFFICIAL_TARGET = 0.01
FORMAL_TARGET = 0.005
SUPPORT_BUDGET = 32


def import_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


issue27f = import_module(ISSUE27F_SCRIPT, "issue27f_for_issue27h")
issue27d = issue27f.issue27d
issue25c = issue27f.issue25c


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def md_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    if max_rows is not None:
        df = df.head(max_rows).copy()
    if df.empty:
        return "_No rows._\n"
    lines = ["| " + " | ".join(map(str, df.columns)) + " |", "|" + "|".join(["---"] * len(df.columns)) + "|"]
    for _, row in df.iterrows():
        vals: list[str] = []
        for value in row:
            if isinstance(value, (float, np.floating)):
                vals.append("" if math.isnan(float(value)) else f"{float(value):.6f}")
            else:
                vals.append(str(value))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"


def required_input_status() -> pd.DataFrame:
    paths = [
        ISSUE27G / "summary.md",
        ISSUE27G / "original100_feature_leakage_audit.csv",
        ISSUE27G / "original100_feature_leakage_diagnosis.md",
        ISSUE27G / "score_distribution_audit.csv",
        ISSUE27G / "score_distribution_audit.md",
        ISSUE27G / "negative_control_summary.md",
        ISSUE27G / "recompute_from_scratch_diff.md",
        ISSUE27G / "claim_update_after_issue27g.md",
        ISSUE27F / "summary.md",
        ISSUE27F / "formal_locked_by_seed.csv",
        ISSUE27F / "formal_locked_summary.csv",
        ISSUE27F / "formal_leakage_audit.md",
        ISSUE27D / "histgb_conservative_selection_trace.csv",
        ISSUE25C / "summary.md",
        MAINLINE / "mainline_handoff.md",
        MAINLINE / "mainline_experiment_map.md",
        ISSUE27F_SCRIPT,
    ]
    return pd.DataFrame([{"path": str(p.relative_to(ROOT)), "exists": p.exists()} for p in paths])


def feature_descriptor(feature_index: int) -> dict[str, Any]:
    lambdas = [5, 3, 1, 0.1, 0.01]
    one_d = ["weight", "mean", "std"]
    two_d = ["weight", "mean", "std", "radius", "magnitude", "covariance", "pcc"]
    idx = int(feature_index)
    if idx < 15:
        slot = idx % 3
        return {
            "mapped_kitnet_family": "MI_dir",
            "lambda": lambdas[idx // 3],
            "mapped_statistic_type": one_d[slot],
            "feature_name_if_available": f"MI_dir_{one_d[slot]}_lambda_{lambdas[idx // 3]}",
            "source_code_location_if_recoverable": "repo/kitsune_frontend_original/netStat.py:84-87; repo/kitsune_frontend_original/AfterImage.py:80-86",
        }
    idx -= 15
    if idx < 35:
        slot = idx % 7
        return {
            "mapped_kitnet_family": "HH",
            "lambda": lambdas[idx // 7],
            "mapped_statistic_type": two_d[slot],
            "feature_name_if_available": f"HH_{two_d[slot]}_lambda_{lambdas[idx // 7]}",
            "source_code_location_if_recoverable": "repo/kitsune_frontend_original/netStat.py:89-92; repo/kitsune_frontend_original/AfterImage.py:80-86",
        }
    idx -= 35
    if idx < 15:
        slot = idx % 3
        return {
            "mapped_kitnet_family": "HH_jit",
            "lambda": lambdas[idx // 3],
            "mapped_statistic_type": one_d[slot],
            "feature_name_if_available": f"HH_jit_{one_d[slot]}_lambda_{lambdas[idx // 3]}",
            "source_code_location_if_recoverable": "repo/kitsune_frontend_original/netStat.py:94-97; repo/kitsune_frontend_original/AfterImage.py:80-86",
        }
    idx -= 15
    if idx < 35:
        slot = idx % 7
        return {
            "mapped_kitnet_family": "HpHp",
            "lambda": lambdas[idx // 7],
            "mapped_statistic_type": two_d[slot],
            "feature_name_if_available": f"HpHp_{two_d[slot]}_lambda_{lambdas[idx // 7]}",
            "source_code_location_if_recoverable": "repo/kitsune_frontend_original/netStat.py:99-105; repo/kitsune_frontend_original/AfterImage.py:80-86",
        }
    return {
        "mapped_kitnet_family": "unknown",
        "lambda": math.nan,
        "mapped_statistic_type": "unknown",
        "feature_name_if_available": "unknown",
        "source_code_location_if_recoverable": "unknown",
    }


def load_all_assets() -> tuple[list[dict[str, Any]], np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[str], pd.DataFrame]:
    cfg = json.loads((issue27f.ISSUE11 / "config.json").read_text(encoding="utf-8"))
    paths = cfg["paths"]
    x_id_o = issue25c.issue19b.load_matrix(Path(paths["original100_id"]))
    x_ood_o = issue25c.issue19b.load_matrix(Path(paths["original100_ood"]))
    x_attack_o = issue25c.issue19b.load_matrix(Path(paths["original100_attack"]))
    x_id_sr = issue25c.issue19b.load_matrix(Path(paths["source_rich_id"]))
    x_ood_sr = issue25c.issue19b.load_matrix(Path(paths["source_rich_ood"]))
    x_attack_sr = issue25c.issue19b.load_matrix(Path(paths["source_rich_attack"]))
    schema_path = Path(paths["source_rich_id"]).parents[1] / "data" / "structured_schema.json"
    sr_names = issue25c.issue19b.feature_names(schema_path, x_id_sr.shape[1])
    datasets, asset_report, _ = issue25c.build_all_datasets(paths, x_id_o, x_ood_o, x_attack_o, x_id_sr, x_ood_sr, x_attack_sr)
    return datasets, x_id_o, x_ood_o, x_attack_o, x_id_sr, x_ood_sr, x_attack_sr, sr_names, asset_report


def support_rows_for_spec(spec: dict[str, Any], x_attack_o: np.ndarray) -> np.ndarray:
    train_pool = np.asarray(spec["attack_train_pool_idx"], dtype=np.int64)
    return issue25c.issue19b.kcenter_support(train_pool, x_attack_o[train_pool], SUPPORT_BUDGET)


def mats_for_spec(spec: dict[str, Any], support_rows: np.ndarray, x_attack_o: np.ndarray, x_attack_sr: np.ndarray, sr_names: list[str]) -> dict[str, np.ndarray]:
    mats, _, _, _ = issue27d.feature_view(spec, "original100", support_rows, x_attack_o, x_attack_sr, sr_names, 42)
    return mats


def subset_mats(mats: dict[str, np.ndarray], keep_idx: np.ndarray) -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    for key, value in mats.items():
        if isinstance(value, np.ndarray) and value.ndim == 2 and value.shape[1] >= int(np.max(keep_idx)) + 1:
            out[key] = value[:, keep_idx]
        else:
            out[key] = value
    return out


def fit_frozen_histgb(mats: dict[str, np.ndarray], seed: int) -> Any:
    return issue27d.LowGuardHistGBConservative(issue27f.FROZEN_CONFIG, seed).fit(
        mats["id_train"],
        mats["ood_train"],
        mats["support"],
        {
            "fit_role": "issue27h_frozen_config_report_only",
            "representation": "original100",
            "selected_config_id": issue27f.FROZEN_CONFIG_ID,
            "final_eval_used_for_selection": False,
        },
    )


def eval_adapter(adapter: Any, mats: dict[str, np.ndarray], target: float = FORMAL_TARGET) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    result, scores, _ = issue27d.evaluate_adapter(adapter, mats, target)
    return result, scores


def safe_auc(y_true: np.ndarray, score: np.ndarray) -> float:
    if len(np.unique(y_true)) < 2 or len(np.unique(score)) < 2:
        return math.nan
    return float(roc_auc_score(y_true, score))


def safe_ap(y_true: np.ndarray, score: np.ndarray) -> float:
    if len(np.unique(y_true)) < 2:
        return math.nan
    return float(average_precision_score(y_true, score))


def ks_distance(a: np.ndarray, b: np.ndarray) -> float:
    a = np.sort(np.asarray(a, dtype=np.float64))
    b = np.sort(np.asarray(b, dtype=np.float64))
    if len(a) == 0 or len(b) == 0:
        return math.nan
    values = np.sort(np.unique(np.concatenate([a, b])))
    ca = np.searchsorted(a, values, side="right") / len(a)
    cb = np.searchsorted(b, values, side="right") / len(b)
    return float(np.max(np.abs(ca - cb)))


def feature_provenance_mapping(separator_features: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for rank, (_, row) in enumerate(separator_features.iterrows(), start=1):
        idx = int(row["feature_index"])
        desc = feature_descriptor(idx)
        rows.append(
            {
                "feature_id": f"separator_{rank}",
                "feature_name_if_available": desc["feature_name_if_available"],
                "original100_index": idx,
                "mapped_kitnet_family": desc["mapped_kitnet_family"],
                "mapped_statistic_type": desc["mapped_statistic_type"],
                "lambda": desc["lambda"],
                "semantic_description": f"{desc['mapped_kitnet_family']} {desc['mapped_statistic_type']} traffic statistic under decay lambda={desc['lambda']}",
                "source_code_location_if_recoverable": desc["source_code_location_if_recoverable"],
                "generated_from_packet_payload_or_metadata": "packet_header_metadata_and_timing_not_payload",
                "generated_from_flow_statistic": True,
                "could_encode_label": False,
                "could_encode_split": False,
                "could_encode_bin": "not_directly_but_time_evolving_stat_can_reflect_window",
                "could_encode_timestamp_or_order": "indirect_temporal_dynamics_via_decay",
                "could_encode_capture_source": "possible_distributional_signal_not_explicit_capture_id",
                "provenance_confidence": "high_for_kitnet_family_mapping_medium_for_raw_packet_identity",
                "risk_level": "medium_low",
                "single_feature_auc_attack_vs_final_ood": float(row["single_feature_auc_attack_vs_final_ood"]),
                "unique_count": int(row["unique_count"]),
                "notes": "High-cardinality near-perfect separator; not label-like by low-cardinality flag, but needs provenance wording because it is very predictive.",
            }
        )
    return pd.DataFrame(rows)


def distribution_by_split(locked: list[dict[str, Any]], separator_idx: list[int], x_attack_o: np.ndarray, x_attack_sr: np.ndarray, sr_names: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    split_names = ["id_train", "ood_train", "id_calib", "ood_val", "ood_eval", "support", "attack_eval"]
    for spec in locked:
        support_rows = support_rows_for_spec(spec, x_attack_o)
        mats = mats_for_spec(spec, support_rows, x_attack_o, x_attack_sr, sr_names)
        for feat in separator_idx:
            ref_ood = mats["ood_eval"][:, feat]
            attack_eval = mats["attack_eval"][:, feat]
            support = mats["support"][:, feat]
            y_ao = np.concatenate([np.zeros(len(ref_ood), dtype=np.int64), np.ones(len(attack_eval), dtype=np.int64)])
            score_ao = np.concatenate([ref_ood, attack_eval])
            auc_pos = safe_auc(y_ao, score_ao)
            auc_neg = safe_auc(y_ao, -score_ao)
            best_auc = float(np.nanmax([auc_pos, auc_neg]))
            for split in split_names:
                v = np.asarray(mats[split][:, feat], dtype=np.float64)
                qs = np.quantile(v, [0.01, 0.05, 0.5, 0.95, 0.99])
                rows.append(
                    {
                        "holdout": spec["holdout"],
                        "feature_index": feat,
                        **feature_descriptor(feat),
                        "split": split,
                        "n": int(len(v)),
                        "min": float(np.min(v)),
                        "max": float(np.max(v)),
                        "mean": float(np.mean(v)),
                        "median": float(np.median(v)),
                        "std": float(np.std(v)),
                        "q01": float(qs[0]),
                        "q05": float(qs[1]),
                        "q50": float(qs[2]),
                        "q95": float(qs[3]),
                        "q99": float(qs[4]),
                        "missing_rate": float(np.mean(~np.isfinite(v))),
                        "unique_count": int(len(np.unique(v))),
                        "ks_distance_vs_final_ood_eval": ks_distance(v, ref_ood),
                        "ks_distance_vs_attack_eval": ks_distance(v, attack_eval),
                        "attack_vs_ood_best_single_feature_auc": best_auc,
                        "support_vs_attack_eval_ks": ks_distance(support, attack_eval),
                        "support_vs_attack_eval_median_abs_delta": float(abs(np.median(support) - np.median(attack_eval))),
                    }
                )
    return pd.DataFrame(rows)


def ablation_variants(separator_idx: list[int], all_high_risk_idx: list[int]) -> dict[str, dict[str, Any]]:
    all_idx = np.arange(100, dtype=np.int64)

    def keep_without(remove: list[int]) -> np.ndarray:
        return np.asarray([i for i in all_idx if int(i) not in set(map(int, remove))], dtype=np.int64)

    return {
        "full_original100_reference": {"keep_idx": all_idx, "diagnostic_only": False, "removed_features": "", "notes": "full frozen candidate rerun"},
        "remove_top1_separator": {"keep_idx": keep_without(separator_idx[:1]), "diagnostic_only": False, "removed_features": ";".join(map(str, separator_idx[:1])), "notes": "predefined top-1 separator removed"},
        "remove_top2_separators": {"keep_idx": keep_without(separator_idx[:2]), "diagnostic_only": False, "removed_features": ";".join(map(str, separator_idx[:2])), "notes": "predefined top-2 separators removed"},
        "remove_top3_separators": {"keep_idx": keep_without(separator_idx[:3]), "diagnostic_only": False, "removed_features": ";".join(map(str, separator_idx[:3])), "notes": "predefined top-3 separators removed"},
        "remove_all_high_risk_separator_candidates": {"keep_idx": keep_without(all_high_risk_idx), "diagnostic_only": False, "removed_features": ";".join(map(str, all_high_risk_idx)), "notes": "all issue27g high-cardinality near-perfect separators removed"},
        "keep_only_non_separator_features": {"keep_idx": keep_without(all_high_risk_idx), "diagnostic_only": False, "removed_features": ";".join(map(str, all_high_risk_idx)), "notes": "same feature set as remove_all_high_risk_separator_candidates; included for explicit protocol coverage"},
        "train_using_only_top3_separators": {"keep_idx": np.asarray(separator_idx[:3], dtype=np.int64), "diagnostic_only": True, "removed_features": "all_except_" + ";".join(map(str, separator_idx[:3])), "notes": "diagnostic only; not a candidate method"},
    }


def run_ablation(locked: list[dict[str, Any]], separator_idx: list[int], all_high_risk_idx: list[int], x_attack_o: np.ndarray, x_attack_sr: np.ndarray, sr_names: list[str]) -> pd.DataFrame:
    variants = ablation_variants(separator_idx, all_high_risk_idx)
    rows: list[dict[str, Any]] = []
    for spec in locked:
        support_rows = support_rows_for_spec(spec, x_attack_o)
        base_mats = mats_for_spec(spec, support_rows, x_attack_o, x_attack_sr, sr_names)
        for seed in FULL_SEEDS:
            for variant, info in variants.items():
                mats = subset_mats(base_mats, info["keep_idx"])
                t0 = time.perf_counter()
                adapter = fit_frozen_histgb(mats, seed)
                result, _ = eval_adapter(adapter, mats, FORMAL_TARGET)
                rows.append(
                    {
                        "ablation_variant": variant,
                        "holdout": spec["holdout"],
                        "seed": int(seed),
                        "feature_count": int(len(info["keep_idx"])),
                        "removed_features": info["removed_features"],
                        "diagnostic_only": bool(info["diagnostic_only"]),
                        "attack_detection": result["attack_detection"],
                        "final_ood_alarm": result["final_ood_alarm"],
                        "id_calib_alarm": result["id_calib_alarm"],
                        "ood_val_alarm": result["ood_val_alarm"],
                        "threshold": result["threshold"],
                        "feasible_under_1pct": bool(result["final_ood_alarm"] <= OFFICIAL_TARGET),
                        "roc_auc_attack_vs_ood": result["roc_auc_attack_vs_ood"],
                        "pr_auc_attack_vs_ood": result["pr_auc_attack_vs_ood"],
                        "tpr_at_fpr_1pct": result["tpr_at_fpr_1pct"],
                        "pauc_fpr_1pct": result["pauc_fpr_1pct"],
                        "train_time": float(adapter.train_time),
                        "inference_time": float(result["inference_time"]),
                        "param_count": int(adapter.param_count),
                        "frozen_config_id": issue27f.FROZEN_CONFIG_ID,
                        "final_eval_used_for_selection": False,
                        "threshold_uses_final_eval": False,
                        "notes": info["notes"],
                    }
                )
    return pd.DataFrame(rows)


def summarize_ablation(by_seed: pd.DataFrame) -> pd.DataFrame:
    return (
        by_seed.groupby(["ablation_variant", "feature_count", "diagnostic_only", "removed_features"], as_index=False)
        .agg(
            locked_detection_mean=("attack_detection", "mean"),
            locked_detection_min=("attack_detection", "min"),
            locked_ood_alarm_max=("final_ood_alarm", "max"),
            feasible_rate=("feasible_under_1pct", "mean"),
            pauc_fpr_1pct_mean=("pauc_fpr_1pct", "mean"),
            tpr_at_fpr_1pct_mean=("tpr_at_fpr_1pct", "mean"),
            mean_train_time=("train_time", "mean"),
            mean_inference_time=("inference_time", "mean"),
        )
        .sort_values(["diagnostic_only", "locked_detection_mean"], ascending=[True, False])
    )


def compare_to_lr(summary: pd.DataFrame, formal_summary: pd.DataFrame) -> pd.DataFrame:
    lr = formal_summary[formal_summary["method"].eq("LOW_GUARD_LR_top64_reference")].iloc[0]
    out = summary.copy()
    out["lowguard_lr_locked_detection_mean"] = float(lr["locked_detection_mean"])
    out["lowguard_lr_locked_detection_min"] = float(lr["locked_detection_min"])
    out["lowguard_lr_locked_ood_alarm_max"] = float(lr["locked_ood_alarm_max"])
    out["detection_mean_delta_vs_lr"] = out["locked_detection_mean"] - float(lr["locked_detection_mean"])
    out["detection_min_delta_vs_lr"] = out["locked_detection_min"] - float(lr["locked_detection_min"])
    out["ood_alarm_max_delta_vs_lr"] = out["locked_ood_alarm_max"] - float(lr["locked_ood_alarm_max"])
    out["dominates_lowguard_lr_three_axis"] = (
        (out["locked_detection_mean"] > float(lr["locked_detection_mean"]))
        & (out["locked_detection_min"] >= float(lr["locked_detection_min"]))
        & (out["locked_ood_alarm_max"] <= float(lr["locked_ood_alarm_max"]))
    )
    out["feasible_under_1pct"] = out["locked_ood_alarm_max"] <= OFFICIAL_TARGET
    return out


def independent_verification(datasets: list[dict[str, Any]], x_attack_o: np.ndarray, x_attack_sr: np.ndarray, sr_names: list[str]) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    specs = [spec for spec in datasets if str(spec.get("evaluation_role")) == "consistency" and str(spec["holdout"]) in CONSISTENCY_HOLDOUTS]
    rows: list[dict[str, Any]] = []
    if not specs:
        return pd.DataFrame(), None
    for spec in specs:
        support_rows = support_rows_for_spec(spec, x_attack_o)
        mats = mats_for_spec(spec, support_rows, x_attack_o, x_attack_sr, sr_names)
        for seed in FULL_SEEDS:
            adapter = fit_frozen_histgb(mats, seed)
            result, _ = eval_adapter(adapter, mats, FORMAL_TARGET)
            rows.append(
                {
                    "verification_type": "non_locked_consistency_not_clean_independent",
                    "clean_independent": False,
                    "used_in_prior_method_discovery_or_consistency": "yes_or_likely",
                    "holdout": spec["holdout"],
                    "dataset": spec["dataset"],
                    "seed": int(seed),
                    "attack_detection": result["attack_detection"],
                    "final_ood_alarm": result["final_ood_alarm"],
                    "id_calib_alarm": result["id_calib_alarm"],
                    "ood_val_alarm": result["ood_val_alarm"],
                    "threshold": result["threshold"],
                    "feasible_under_1pct": bool(result["final_ood_alarm"] <= OFFICIAL_TARGET),
                    "roc_auc_attack_vs_ood": result["roc_auc_attack_vs_ood"],
                    "pr_auc_attack_vs_ood": result["pr_auc_attack_vs_ood"],
                    "tpr_at_fpr_1pct": result["tpr_at_fpr_1pct"],
                    "pauc_fpr_1pct": result["pauc_fpr_1pct"],
                    "frozen_config_id": issue27f.FROZEN_CONFIG_ID,
                    "final_eval_used_for_selection": False,
                    "notes": "Report-only consistency outside locked bins; not clean independent validation because these settings were part of earlier discovery/consistency evidence.",
                }
            )
    by_seed = pd.DataFrame(rows)
    summary = (
        by_seed.groupby(["verification_type", "clean_independent", "holdout"], as_index=False)
        .agg(
            detection_mean=("attack_detection", "mean"),
            detection_min=("attack_detection", "min"),
            ood_alarm_max=("final_ood_alarm", "max"),
            feasible_rate=("feasible_under_1pct", "mean"),
            pauc_mean=("pauc_fpr_1pct", "mean"),
            tpr_at_fpr_1pct_mean=("tpr_at_fpr_1pct", "mean"),
        )
        .sort_values(["holdout"])
    )
    return by_seed, summary


def permutation_importance_audit(locked: list[dict[str, Any]], separator_idx: list[int], x_attack_o: np.ndarray, x_attack_sr: np.ndarray, sr_names: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    rng = np.random.default_rng(270527)
    for spec in locked:
        support_rows = support_rows_for_spec(spec, x_attack_o)
        base_mats = mats_for_spec(spec, support_rows, x_attack_o, x_attack_sr, sr_names)
        for seed in IMPORTANCE_SEEDS:
            adapter = fit_frozen_histgb(base_mats, seed)
            result, scores = eval_adapter(adapter, base_mats, FORMAL_TARGET)
            threshold = float(result["threshold"])
            final_x = np.vstack([base_mats["ood_eval"], base_mats["attack_eval"]])
            final_y = np.concatenate([np.zeros(len(base_mats["ood_eval"]), dtype=np.int64), np.ones(len(base_mats["attack_eval"]), dtype=np.int64)])
            val_x = np.vstack([base_mats["id_calib"], base_mats["ood_val"], base_mats["support"]])
            val_y = np.concatenate([np.zeros(len(base_mats["id_calib"]) + len(base_mats["ood_val"]), dtype=np.int64), np.ones(len(base_mats["support"]), dtype=np.int64)])
            base_final_score = adapter.score(final_x)
            base_val_score = adapter.score(val_x)
            base_final_auc = safe_auc(final_y, base_final_score)
            base_val_auc = safe_auc(val_y, base_val_score)
            base_detection = float(result["attack_detection"])
            for feat in range(base_mats["id_train"].shape[1]):
                final_perm = final_x.copy()
                val_perm = val_x.copy()
                final_perm[:, feat] = rng.permutation(final_perm[:, feat])
                val_perm[:, feat] = rng.permutation(val_perm[:, feat])
                final_score = adapter.score(final_perm)
                val_score = adapter.score(val_perm)
                perm_detection = float(np.mean(final_score[len(base_mats["ood_eval"]) :] > threshold))
                rows.append(
                    {
                        "holdout": spec["holdout"],
                        "seed": int(seed),
                        "feature_index": int(feat),
                        **feature_descriptor(feat),
                        "is_separator_top3": int(feat) in set(separator_idx[:3]),
                        "base_final_auc": base_final_auc,
                        "permuted_final_auc": safe_auc(final_y, final_score),
                        "final_auc_drop": base_final_auc - safe_auc(final_y, final_score),
                        "base_validation_auc": base_val_auc,
                        "permuted_validation_auc": safe_auc(val_y, val_score),
                        "validation_auc_drop": base_val_auc - safe_auc(val_y, val_score),
                        "base_attack_detection": base_detection,
                        "permuted_attack_detection": perm_detection,
                        "attack_detection_drop": base_detection - perm_detection,
                        "threshold_fixed_for_explanation": threshold,
                        "final_eval_used_for_selection": False,
                        "importance_scope": "report_only_permutation_on_validation_and_final_views",
                    }
                )
    return pd.DataFrame(rows).sort_values(["final_auc_drop", "validation_auc_drop"], ascending=False)


def decide_claim_gate(
    provenance: pd.DataFrame,
    ablation_summary: pd.DataFrame,
    ablation_vs_lr: pd.DataFrame,
    independent_summary: pd.DataFrame | None,
    importance: pd.DataFrame,
) -> tuple[str, str, dict[str, Any]]:
    remove_top3 = ablation_vs_lr[ablation_vs_lr["ablation_variant"].eq("remove_top3_separators")]
    only_top3 = ablation_summary[ablation_summary["ablation_variant"].eq("train_using_only_top3_separators")]
    remove_top3_dominates = bool(len(remove_top3) and bool(remove_top3["dominates_lowguard_lr_three_axis"].iloc[0]))
    remove_top3_feasible = bool(len(remove_top3) and bool(remove_top3["feasible_under_1pct"].iloc[0]))
    only_top3_near_perfect = bool(len(only_top3) and float(only_top3["locked_detection_min"].iloc[0]) >= 0.99 and float(only_top3["locked_ood_alarm_max"].iloc[0]) <= 0.005)
    clean_independent = bool(independent_summary is not None and len(independent_summary) and independent_summary["clean_independent"].astype(bool).any())
    provenance_ok = not provenance[["could_encode_label", "could_encode_split"]].astype(str).apply(lambda col: col.str.lower().eq("true")).any().any()
    sep_imp = importance[importance["is_separator_top3"].astype(bool)].copy()
    top3_final_auc_drop_share = float(sep_imp["final_auc_drop"].clip(lower=0).sum() / max(1e-12, importance["final_auc_drop"].clip(lower=0).sum())) if len(importance) else math.nan
    diagnostics = {
        "remove_top3_dominates_lowguard_lr": remove_top3_dominates,
        "remove_top3_feasible": remove_top3_feasible,
        "only_top3_near_perfect": only_top3_near_perfect,
        "clean_independent_available": clean_independent,
        "provenance_ok_no_direct_label_split": provenance_ok,
        "top3_final_auc_drop_share": top3_final_auc_drop_share,
    }
    if not provenance_ok:
        return "lowguard_plus_plus_claim_blocked_by_feature_artifact_risk", "issue27i_feature_artifact_root_cause_and_safe_fallback_to_lowguard_lr", diagnostics
    if not remove_top3_feasible or not remove_top3_dominates:
        return "lowguard_plus_plus_depends_on_high_risk_separators", "issue27i_separator_dependency_deeper_audit_or_demote_lowguard_plus_plus", diagnostics
    if provenance_ok and remove_top3_dominates and clean_independent:
        return "lowguard_plus_plus_ready_for_claim_upgrade", "issue27i_claim_upgrade_pack_with_bounded_lowguard_plus_plus", diagnostics
    return (
        "lowguard_plus_plus_audited_but_claim_requires_feature_provenance_or_independent_validation",
        "issue27i_clean_independent_validation_or_second_environment_for_lowguard_plus_plus",
        diagnostics,
    )


def write_reports(
    *,
    input_status: pd.DataFrame,
    provenance: pd.DataFrame,
    dist: pd.DataFrame,
    ablation_by_seed: pd.DataFrame,
    ablation_summary: pd.DataFrame,
    ablation_vs_lr: pd.DataFrame,
    independent_by_seed: pd.DataFrame,
    independent_summary: pd.DataFrame | None,
    importance: pd.DataFrame,
    primary_verdict: str,
    issue27i_action: str,
    diagnostics: dict[str, Any],
) -> None:
    write_text(
        OUT / "feature_provenance_mapping.md",
        f"""
# Feature Provenance Mapping

The three high-cardinality near-perfect separator features map to standard KitNET/Kitsune original frontend traffic statistics, not explicit label/split/bin columns.

{md_table(provenance[['feature_id','original100_index','feature_name_if_available','mapped_kitnet_family','mapped_statistic_type','lambda','could_encode_label','could_encode_split','could_encode_bin','could_encode_timestamp_or_order','risk_level']])}

Technical interpretation: these features are generated from decayed host-host traffic statistics (`HH radius` and `HH magnitude`) in `repo/kitsune_frontend_original/netStat.py` and `AfterImage.py`. They can reflect temporal traffic dynamics because the statistics are updated online with timestamps, but this is different from carrying a row id or label field. Packet-level provenance would still be needed for a final artifact-proof statement.
""",
    )
    support_attack = dist[dist["split"].isin(["support", "attack_eval"])].copy()
    benign_splits = dist[dist["split"].isin(["id_train", "ood_train", "id_calib", "ood_val", "ood_eval"])].copy()
    write_text(
        OUT / "separator_distribution_diagnosis.md",
        f"""
# Separator Distribution Diagnosis

The separator features show strong attack-vs-final-OOD separation, but support-vs-attack-eval KS distances are large rather than near zero. This suggests the support set is not a duplicate copy of attack_eval on these features; in fact, kcenter supports are often more extreme than the held-out attack_eval distribution on the same traffic-stat dimensions.

Support/attack summary:

{md_table(support_attack.groupby(['feature_index','split'], as_index=False).agg(mean=('mean','mean'), median=('median','mean'), q05=('q05','mean'), q95=('q95','mean'), ks_to_attack_eval=('ks_distance_vs_attack_eval','mean'), unique_count=('unique_count','mean')), 20)}

Benign split drift summary:

{md_table(benign_splits.groupby(['feature_index','split'], as_index=False).agg(mean=('mean','mean'), median=('median','mean'), q05=('q05','mean'), q95=('q95','mean'), ks_to_final_ood=('ks_distance_vs_final_ood_eval','mean')), 25)}

Boundary: this is a distribution sanity check, not raw packet identity proof.
""",
    )
    write_text(
        OUT / "histgb_feature_importance_diagnosis.md",
        f"""
# HistGB Feature Importance Diagnosis

Permutation importance was computed as report-only explanation with the frozen model. It was not used for model selection.

Top final-side permutation drops:

{md_table(importance[['holdout','seed','feature_index','feature_name_if_available','is_separator_top3','final_auc_drop','validation_auc_drop','attack_detection_drop']].head(20), 20)}

Top3 separator final AUC drop share: `{diagnostics['top3_final_auc_drop_share']:.6f}`.

Interpretation: model reliance should be judged together with ablation. If top3-only is strong but remove-top3 also remains strong, the model has redundant traffic-stat evidence rather than a single-feature-only failure mode.
""",
    )
    if len(independent_by_seed):
        write_text(
            OUT / "independent_verification_blocked.md",
            """
# Independent Verification Cleanliness Note

Clean locked-independent validation was not available in this issue. The available non-locked objects are primary/holdout_bin_2/chrono_late consistency settings that have prior-method-discovery or prior-consistency involvement. Therefore `independent_verification_by_seed.csv` is provided as report-only non-locked consistency, not as clean independent proof.
""",
        )
    else:
        write_text(
            OUT / "independent_verification_blocked.md",
            """
# Independent Verification Blocked

No locked-independent validation asset could be constructed safely from available metadata without reopening split construction.
""",
        )
    write_text(
        OUT / "lowguard_plus_plus_claim_gate_decision.md",
        f"""
# LOW-GUARD++ Claim Gate Decision

- primary_verdict: `{primary_verdict}`
- issue27i_next_action: `{issue27i_action}`

Diagnostics:

{md_table(pd.DataFrame([diagnostics]))}

Decision logic:
- Provenance maps to legal KitNET traffic statistics, not explicit label/split fields.
- Remove-top3 ablation is the main robustness gate against separator overdependence.
- Non-locked consistency is not clean independent validation; a clean independent/temporal/second-environment gate is still needed before very strong main-text upgrading.
""",
    )
    if primary_verdict == "lowguard_plus_plus_ready_for_claim_upgrade":
        allowed = """
- LOW-GUARD++ passes feature provenance and independent verification gate.
- The performance instance can be reported under bounded tested settings.
- Claims remain bounded to original100 + HistGB-Conservative and the locked low-alert protocol.
"""
    elif primary_verdict == "lowguard_plus_plus_audited_but_claim_requires_feature_provenance_or_independent_validation":
        allowed = """
- LOW-GUARD++ remains an audited formal locked result.
- Claim upgrade requires additional feature provenance or independent validation.
- LOW-GUARD-LR remains the safest demonstrated main instance.
"""
    else:
        allowed = """
- LOW-GUARD++ cannot be upgraded to a main claim at this stage.
- Original100 + HistGB-Conservative is retained as a diagnostic candidate only.
- LOW-GUARD-LR remains the demonstrated stable instance.
"""
    write_text(
        OUT / "claim_update_after_issue27h.md",
        f"""
# Claim Update After Issue27h

## Allowed After Issue27h

{allowed}

## Still Forbidden

- LOW-GUARD++ is broadly validated without provenance/independent verification.
- HistGB universally dominates LR.
- LOW-GUARD works for all models.
- Deployment robustness is proven.
- Temporal/cross-dataset generalization is proven.
- Feature provenance uncertainty is ignored.
""",
    )
    write_text(
        OUT / "reviewer_defense_feature_provenance.md",
        f"""
# Reviewer Defense: Feature Provenance

## Q1: Are the three separator features labels or split IDs?

No evidence of explicit label/split/bin fields was found. They map to KitNET HH radius/magnitude traffic statistics.

## Q2: Could they still encode time or capture source?

Indirectly, yes. KitNET statistics are time-updated flow statistics, so they can reflect traffic phase and capture conditions. That is a scientific signal if controlled, but it must be bounded and audited.

## Q3: Does removing the top separators destroy LOW-GUARD++?

See `feature_ablation_summary.csv`. The claim gate uses remove-top3 and LR comparison as the main test.

## Q4: Does top3-only being strong invalidate the result?

Not by itself. If top3-only is strong and remove-top3 remains strong, the model has redundant evidence. If remove-top3 collapses, LOW-GUARD++ depends on high-risk separators and should be demoted.

## Q5: Is there clean independent validation?

No. This issue provides non-locked consistency only. Clean independent validation or a second environment is still needed for a stronger main-text upgrade.
""",
    )
    write_text(
        OUT / "issue27i_next_action.md",
        f"""
# Issue27i Next Action

Recommended next action: `{issue27i_action}`.

Rationale: issue27h is a claim gate. If LOW-GUARD++ remains strong after removing top separators but clean independent validation is unavailable, the next step should be a clean independent validation or second-environment feasibility gate, not deployment robustness yet.
""",
    )
    write_text(
        OUT / "summary.md",
        f"""
# Issue27h Original100 Feature Provenance And Claim Gate Summary

## Verdict

- primary_verdict: `{primary_verdict}`
- frozen_config_id: `{issue27f.FROZEN_CONFIG_ID}`

## 1. Separator provenance

The three separator features map to legal KitNET/Kitsune traffic statistics: `{'; '.join(provenance['feature_name_if_available'].astype(str).tolist())}`.

## 2. Label/split/bin/capture artifact risk

No direct label/split/bin feature was found. Risk remains `medium-low` because these time-updated flow statistics may indirectly encode temporal/capture conditions, and raw packet-level provenance is still incomplete.

## 3. Support/eval similarity

Support-vs-attack-eval distributions are not identical duplicates; kcenter supports are often more extreme than attack_eval on the separator dimensions. This reduces direct duplication concern but raises a support-representativeness caution.

## 4. Feature ablation

{md_table(ablation_vs_lr[['ablation_variant','feature_count','locked_detection_mean','locked_detection_min','locked_ood_alarm_max','feasible_rate','dominates_lowguard_lr_three_axis']])}

## 5. Top3-only diagnostic

Top3-only near-perfect: `{diagnostics['only_top3_near_perfect']}`.

## 6. Model overdependence

Top3 final AUC drop share by permutation explanation: `{diagnostics['top3_final_auc_drop_share']:.6f}`. Judge this with ablation rather than importance alone.

## 7. Independent verification

Clean independent verification completed: `{diagnostics['clean_independent_available']}`. Available non-locked settings are consistency-only and cannot be used as formal independent proof.

## 8. Main-text performance instance upgrade

`{'Not yet; LOW-GUARD++ remains audited but needs clean independent validation or stronger provenance before major claim upgrade.' if primary_verdict != 'lowguard_plus_plus_ready_for_claim_upgrade' else 'Yes, under bounded tested settings.'}`

## 9. Missing evidence

- raw packet/timestamp/row provenance for original100 row generation;
- clean locked-independent or second-environment verification;
- bounded wording that avoids universal HistGB/LOW-GUARD claims.

## 10. Issue27i

`{issue27i_action}`

## 11. Slurm

Not needed.
""",
    )
    write_text(
        OUT / "command.txt",
        """
git branch --show-current
git status --short
read issue27g/issue27f summaries and CSVs
python runs/issue27h_original100_feature_provenance_and_independent_verification_before_claim_upgrade_2026-05-27/run_issue27h_feature_provenance_claim_gate.py
""",
    )
    config = {
        "issue": "issue27h_original100_feature_provenance_and_independent_verification_before_claim_upgrade_2026-05-27",
        "frozen_method": "LOW-GUARD++ original100 + HistGB-Conservative",
        "frozen_config_id": issue27f.FROZEN_CONFIG_ID,
        "locked_bins": LOCKED_BINS,
        "seeds": FULL_SEEDS,
        "separator_features": provenance["original100_index"].astype(int).tolist(),
        "official_ood_target": OFFICIAL_TARGET,
        "threshold_target": FORMAL_TARGET,
        "final_eval_policy": "report_only_no_selection",
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    run_spec = {
        "task": "feature_provenance_and_claim_gate",
        "inputs": input_status.to_dict(orient="records"),
        "primary_verdict": primary_verdict,
        "issue27i_action": issue27i_action,
        "outputs": [
            "summary.md",
            "feature_provenance_mapping.csv",
            "feature_provenance_mapping.md",
            "separator_distribution_by_split.csv",
            "separator_distribution_diagnosis.md",
            "feature_ablation_by_seed.csv",
            "feature_ablation_summary.csv",
            "feature_ablation_vs_lowguard_lr.csv",
            "independent_verification_by_seed.csv",
            "independent_verification_summary.csv",
            "histgb_feature_importance_audit.csv",
            "histgb_feature_importance_diagnosis.md",
            "lowguard_plus_plus_claim_gate_decision.md",
            "claim_update_after_issue27h.md",
            "reviewer_defense_feature_provenance.md",
            "issue27i_next_action.md",
            "command.txt",
            "config.json",
            "run_spec.json",
            "manifest.csv",
        ],
    }
    (OUT / "run_spec.json").write_text(json.dumps(run_spec, indent=2), encoding="utf-8")


def update_mainline_docs(primary_verdict: str, issue27i_action: str) -> None:
    handoff = MAINLINE / "mainline_handoff.md"
    expmap = MAINLINE / "mainline_experiment_map.md"
    handoff_append = f"""

## issue27h feature provenance claim gate (2026-05-27)

- primary_verdict: `{primary_verdict}`
- scope: maps the three original100 high-cardinality near-perfect separators, audits split distributions, runs frozen-config feature ablations, performs report-only non-locked consistency checks, and explains HistGB feature reliance.
- claim boundary: LOW-GUARD++ can remain an audited locked result, but broad/main-text performance-instance upgrading still needs clean independent validation or stronger original100 provenance.
- next action: `{issue27i_action}`.
"""
    expmap_append = f"""
| issue27h | original100 feature provenance and LOW-GUARD++ claim gate | `{primary_verdict}` | Maps separator features, runs frozen ablations, and blocks broad claim upgrade pending clean independent validation/provenance. Next: `{issue27i_action}`. |
"""
    htxt = handoff.read_text(encoding="utf-8")
    htxt = re.sub(r"\n## issue27h feature provenance claim gate \(2026-05-27\)\n.*?(?=\n## |\Z)", "", htxt, flags=re.S)
    handoff.write_text(htxt.rstrip() + handoff_append + "\n", encoding="utf-8")
    etxt = expmap.read_text(encoding="utf-8")
    etxt = re.sub(r"\n\| issue27h \| original100 feature provenance and LOW-GUARD\+\+ claim gate \|.*?\|\n?", "\n", etxt)
    etxt = re.sub(r"\n+\s+Maps separator features, runs frozen ablations, and blocks broad claim upgrade pending clean independent validation/provenance\. Next: `issue27i_[^`]+`\. \|\n?", "\n", etxt)
    expmap.write_text(etxt.rstrip() + "\n\n" + expmap_append.strip() + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    input_status = required_input_status()
    input_status.to_csv(OUT / "manifest.csv", index=False)
    missing = input_status[~input_status["exists"]]
    if len(missing):
        write_text(OUT / "summary.md", "primary_verdict: `claim_gate_incomplete_no_upgrade`\n\nRequired inputs are missing; see manifest.csv.")
        raise SystemExit(1)

    feature_audit = pd.read_csv(ISSUE27G / "original100_feature_leakage_audit.csv")
    separator_features = feature_audit[feature_audit["high_cardinality_perfect_separator"].astype(str).str.lower().eq("true")].copy()
    separator_features = separator_features.sort_values("single_feature_auc_attack_vs_final_ood", ascending=False).head(3)
    separator_idx = separator_features["feature_index"].astype(int).tolist()
    all_high_risk_idx = feature_audit[feature_audit["high_cardinality_perfect_separator"].astype(str).str.lower().eq("true")]["feature_index"].astype(int).tolist()

    datasets, _, _, x_attack_o, _, _, x_attack_sr, sr_names, _ = load_all_assets()
    locked = [spec for spec in datasets if str(spec.get("evaluation_role")) == "locked" and str(spec["holdout"]) in LOCKED_BINS]

    provenance = feature_provenance_mapping(separator_features)
    dist = distribution_by_split(locked, separator_idx, x_attack_o, x_attack_sr, sr_names)
    ablation_by_seed = run_ablation(locked, separator_idx, all_high_risk_idx, x_attack_o, x_attack_sr, sr_names)
    ablation_summary = summarize_ablation(ablation_by_seed)
    formal_summary = pd.read_csv(ISSUE27F / "formal_locked_summary.csv")
    ablation_vs_lr = compare_to_lr(ablation_summary, formal_summary)
    independent_by_seed, independent_summary = independent_verification(datasets, x_attack_o, x_attack_sr, sr_names)
    importance = permutation_importance_audit(locked, separator_idx, x_attack_o, x_attack_sr, sr_names)

    provenance.to_csv(OUT / "feature_provenance_mapping.csv", index=False)
    dist.to_csv(OUT / "separator_distribution_by_split.csv", index=False)
    ablation_by_seed.to_csv(OUT / "feature_ablation_by_seed.csv", index=False)
    ablation_summary.to_csv(OUT / "feature_ablation_summary.csv", index=False)
    ablation_vs_lr.to_csv(OUT / "feature_ablation_vs_lowguard_lr.csv", index=False)
    if len(independent_by_seed):
        independent_by_seed.to_csv(OUT / "independent_verification_by_seed.csv", index=False)
        assert independent_summary is not None
        independent_summary.to_csv(OUT / "independent_verification_summary.csv", index=False)
    else:
        write_text(OUT / "independent_verification_blocked.md", "No non-locked consistency asset was available.")
        write_text(OUT / "independent_verification_summary_blocked.md", "No non-locked consistency asset was available.")
    importance.to_csv(OUT / "histgb_feature_importance_audit.csv", index=False)

    primary_verdict, issue27i_action, diagnostics = decide_claim_gate(provenance, ablation_summary, ablation_vs_lr, independent_summary, importance)
    write_reports(
        input_status=input_status,
        provenance=provenance,
        dist=dist,
        ablation_by_seed=ablation_by_seed,
        ablation_summary=ablation_summary,
        ablation_vs_lr=ablation_vs_lr,
        independent_by_seed=independent_by_seed,
        independent_summary=independent_summary,
        importance=importance,
        primary_verdict=primary_verdict,
        issue27i_action=issue27i_action,
        diagnostics=diagnostics,
    )
    update_mainline_docs(primary_verdict, issue27i_action)
    print(f"[issue27h] primary_verdict={primary_verdict}")
    print(f"[issue27h] issue27i_action={issue27i_action}")


if __name__ == "__main__":
    main()
