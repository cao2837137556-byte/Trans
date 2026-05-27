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
OUT = ROOT / "runs" / "issue27i_separator_independent_validation_and_data_expansion_feasibility_for_lowguard_plus_plus_2026-05-27"
ISSUE27H = ROOT / "runs" / "issue27h_original100_feature_provenance_and_independent_verification_before_claim_upgrade_2026-05-27"
ISSUE27G = ROOT / "runs" / "issue27g_suspicious_perfect_score_audit_for_lowguard_plus_plus_2026-05-27"
ISSUE27F = ROOT / "runs" / "issue27f_config_freeze_then_formal_validation_for_original100_histgb_conservative_2026-05-27"
ISSUE26B = ROOT / "runs" / "issue26b_split_metadata_recovery_and_temporal_asset_build_2026-05-22"
ISSUE25C = ROOT / "runs" / "issue25c_strong_baseline_pack_execution_for_enhanced_lowguard_top64_2026-05-18"
ISSUE23 = ROOT / "runs" / "issue23_locked_validation_for_enhanced_v2_top64_2026-05-18"
MAINLINE = ROOT / "runs" / "mainline_docs"
ISSUE27F_SCRIPT = ISSUE27F / "run_issue27f_config_freeze_formal_validation.py"

LOCKED_BINS = ["holdout_bin_5", "holdout_bin_6", "holdout_bin_7", "holdout_bin_8"]
NONLOCKED_HOLDOUTS = ["primary_lowood", "holdout_bin_2", "chrono_late_train_early_eval"]
FULL_SEEDS = list(range(42, 52))
OFFICIAL_TARGET = 0.01
FORMAL_TARGET = 0.005
SUPPORT_BUDGET = 32
LAMBDA_ORDER = [5, 3, 1, 0.1, 0.01]


def import_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


issue27f = import_module(ISSUE27F_SCRIPT, "issue27f_for_issue27i")
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
        ISSUE27H / "summary.md",
        ISSUE27H / "feature_provenance_mapping.csv",
        ISSUE27H / "feature_provenance_mapping.md",
        ISSUE27H / "separator_distribution_by_split.csv",
        ISSUE27H / "separator_distribution_diagnosis.md",
        ISSUE27H / "feature_ablation_summary.csv",
        ISSUE27H / "feature_ablation_vs_lowguard_lr.csv",
        ISSUE27H / "histgb_feature_importance_audit.csv",
        ISSUE27H / "claim_update_after_issue27h.md",
        ISSUE27G / "summary.md",
        ISSUE27F / "summary.md",
        ISSUE26B / "summary.md",
        ISSUE25C / "summary.md",
        ISSUE23 / "locked_validation_asset_report.md",
        MAINLINE / "mainline_handoff.md",
        MAINLINE / "mainline_experiment_map.md",
        ISSUE27F_SCRIPT,
    ]
    optional_any = [ISSUE27H / "independent_verification_summary.csv", ISSUE27H / "independent_verification_blocked.md"]
    rows = [{"path": str(p.relative_to(ROOT)), "exists": p.exists(), "required": True} for p in paths]
    rows += [{"path": str(p.relative_to(ROOT)), "exists": p.exists(), "required": False} for p in optional_any]
    return pd.DataFrame(rows)


def feature_descriptor(feature_index: int) -> dict[str, Any]:
    one_d = ["weight", "mean", "std"]
    two_d = ["weight", "mean", "std", "radius", "magnitude", "covariance", "pcc"]
    idx = int(feature_index)
    if idx < 15:
        return {"feature_family": "MI_dir", "lambda": LAMBDA_ORDER[idx // 3], "stat_slot": one_d[idx % 3], "feature_name": f"MI_dir_{one_d[idx % 3]}_lambda_{LAMBDA_ORDER[idx // 3]}"}
    idx -= 15
    if idx < 35:
        return {"feature_family": "HH", "lambda": LAMBDA_ORDER[idx // 7], "stat_slot": two_d[idx % 7], "feature_name": f"HH_{two_d[idx % 7]}_lambda_{LAMBDA_ORDER[idx // 7]}"}
    idx -= 35
    if idx < 15:
        return {"feature_family": "HH_jit", "lambda": LAMBDA_ORDER[idx // 3], "stat_slot": one_d[idx % 3], "feature_name": f"HH_jit_{one_d[idx % 3]}_lambda_{LAMBDA_ORDER[idx // 3]}"}
    idx -= 15
    if idx < 35:
        return {"feature_family": "HpHp", "lambda": LAMBDA_ORDER[idx // 7], "stat_slot": two_d[idx % 7], "feature_name": f"HpHp_{two_d[idx % 7]}_lambda_{LAMBDA_ORDER[idx // 7]}"}
    return {"feature_family": "unknown", "lambda": math.nan, "stat_slot": "unknown", "feature_name": "unknown"}


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
    vals = np.sort(np.unique(np.concatenate([a, b])))
    ca = np.searchsorted(a, vals, side="right") / len(a)
    cb = np.searchsorted(b, vals, side="right") / len(b)
    return float(np.max(np.abs(ca - cb)))


def load_all_assets() -> tuple[dict[str, str], list[dict[str, Any]], np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[str], pd.DataFrame]:
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
    return paths, datasets, x_id_o, x_ood_o, x_attack_o, x_id_sr, x_ood_sr, x_attack_sr, sr_names, asset_report


def support_rows_for_spec(spec: dict[str, Any], x_attack_o: np.ndarray) -> np.ndarray:
    train_pool = np.asarray(spec["attack_train_pool_idx"], dtype=np.int64)
    return issue25c.issue19b.kcenter_support(train_pool, x_attack_o[train_pool], SUPPORT_BUDGET)


def mats_for_spec(spec: dict[str, Any], support_rows: np.ndarray, x_attack_o: np.ndarray, x_attack_sr: np.ndarray, sr_names: list[str]) -> dict[str, np.ndarray]:
    mats, _, _, _ = issue27d.feature_view(spec, "original100", support_rows, x_attack_o, x_attack_sr, sr_names, 42)
    return mats


def fit_frozen_histgb(mats: dict[str, np.ndarray], seed: int) -> Any:
    return issue27d.LowGuardHistGBConservative(issue27f.FROZEN_CONFIG, seed).fit(
        mats["id_train"],
        mats["ood_train"],
        mats["support"],
        {
            "fit_role": "issue27i_frozen_report_only",
            "representation": "original100",
            "selected_config_id": issue27f.FROZEN_CONFIG_ID,
            "final_eval_used_for_selection": False,
        },
    )


def eval_adapter(adapter: Any, mats: dict[str, np.ndarray], target: float = FORMAL_TARGET) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    result, scores, _ = issue27d.evaluate_adapter(adapter, mats, target)
    return result, scores


def all_hh_indices() -> list[int]:
    return list(range(15, 50))


def hh_lambda_indices(lambda_value: float) -> list[int]:
    li = LAMBDA_ORDER.index(lambda_value)
    start = 15 + li * 7
    return list(range(start, start + 7))


def hh_radius_magnitude_indices() -> list[int]:
    out: list[int] = []
    for li in range(5):
        start = 15 + li * 7
        out.extend([start + 3, start + 4])
    return out


def subset_mats(mats: dict[str, np.ndarray], keep_idx: np.ndarray) -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    max_idx = int(np.max(keep_idx)) if len(keep_idx) else -1
    for key, value in mats.items():
        if isinstance(value, np.ndarray) and value.ndim == 2 and value.shape[1] > max_idx:
            out[key] = value[:, keep_idx]
        else:
            out[key] = value
    return out


def transform_mats(mats: dict[str, np.ndarray], variant: str, sep_idx: list[int]) -> tuple[dict[str, np.ndarray], str, int]:
    all_idx = np.arange(100, dtype=np.int64)
    if variant == "original100_all":
        return mats, "all 100 original features", 100
    if variant == "original100_remove_top1":
        keep = np.asarray([i for i in all_idx if i not in sep_idx[:1]], dtype=np.int64)
        return subset_mats(mats, keep), "remove top1 separator", int(len(keep))
    if variant == "original100_remove_top2":
        keep = np.asarray([i for i in all_idx if i not in sep_idx[:2]], dtype=np.int64)
        return subset_mats(mats, keep), "remove top2 separators", int(len(keep))
    if variant == "original100_remove_top3":
        keep = np.asarray([i for i in all_idx if i not in sep_idx[:3]], dtype=np.int64)
        return subset_mats(mats, keep), "remove top3 separators", int(len(keep))
    if variant == "original100_drop_lambda_0.01_HH_features":
        drop = set(hh_lambda_indices(0.01))
        keep = np.asarray([i for i in all_idx if i not in drop], dtype=np.int64)
        return subset_mats(mats, keep), "drop all HH lambda=0.01 features", int(len(keep))
    if variant == "original100_drop_all_HH_radius_magnitude_top_family":
        drop = set(hh_radius_magnitude_indices())
        keep = np.asarray([i for i in all_idx if i not in drop], dtype=np.int64)
        return subset_mats(mats, keep), "drop all HH radius/magnitude features across lambdas", int(len(keep))
    if variant in {"original100_clip_top3_by_train_quantile", "original100_rank_normalize_top3"}:
        transformed = {k: np.array(v, copy=True) if isinstance(v, np.ndarray) and v.ndim == 2 and v.shape[1] == 100 else v for k, v in mats.items()}
        train_values = np.vstack([mats["id_train"], mats["ood_train"], mats["support"]])
        for feat in sep_idx[:3]:
            ref = np.asarray(train_values[:, feat], dtype=np.float64)
            if variant == "original100_clip_top3_by_train_quantile":
                lo, hi = np.quantile(ref, [0.01, 0.99])
                for key, value in transformed.items():
                    if isinstance(value, np.ndarray) and value.ndim == 2 and value.shape[1] == 100:
                        value[:, feat] = np.clip(value[:, feat], lo, hi)
            else:
                sorted_ref = np.sort(ref)
                denom = max(1, len(sorted_ref))
                for key, value in transformed.items():
                    if isinstance(value, np.ndarray) and value.ndim == 2 and value.shape[1] == 100:
                        value[:, feat] = np.searchsorted(sorted_ref, value[:, feat], side="right") / denom
        return transformed, "train-side clip/rank transform on top3 separators only", 100
    if variant == "original100_group_aggregate_HH_features":
        non_hh = [i for i in all_idx if i not in set(all_hh_indices())]
        stat_groups = []
        for slot in range(7):
            stat_groups.append([15 + li * 7 + slot for li in range(5)])
        transformed = {}
        for key, value in mats.items():
            if isinstance(value, np.ndarray) and value.ndim == 2 and value.shape[1] == 100:
                aggregates = [np.mean(value[:, group], axis=1, keepdims=True) for group in stat_groups]
                transformed[key] = np.hstack([value[:, non_hh]] + aggregates)
            else:
                transformed[key] = value
        return transformed, "replace 35 HH features with 7 stat-slot aggregates", len(non_hh) + 7
    raise ValueError(f"Unknown variant {variant}")


def available_assets_inventory(paths: dict[str, str], datasets: list[dict[str, Any]], asset_report: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for spec in datasets:
        holdout = str(spec["holdout"])
        role = str(spec.get("evaluation_role", "unknown"))
        rows.append(
            {
                "asset_name": f"{role}_{holdout}",
                "asset_path": "constructed_by_issue25c_build_all_datasets",
                "asset_type": f"{role}_dataset_spec",
                "contains_original100": True,
                "contains_top64": True,
                "contains_attack_eval": "attack_eval_idx" in spec,
                "contains_final_ood_eval": "x_ood_eval_o" in spec,
                "contains_timestamp": False,
                "contains_packet_order": False,
                "contains_capture_id": False,
                "contains_bin_id": "bin" in holdout or "chrono" in holdout,
                "can_support_clean_independent_validation": False if role != "locked" else "already_used_locked_not_new_independent",
                "can_support_consistency_only": role == "consistency",
                "leakage_risk": "medium" if role == "consistency" else "low_for_current_locked_but_not_new",
                "notes": "Dataset spec has arrays and attack indices but lacks raw timestamp/packet-order provenance; consistency objects are not clean independent.",
            }
        )
    for name, path_str in paths.items():
        path = Path(path_str)
        rows.append(
            {
                "asset_name": name,
                "asset_path": str(path),
                "asset_type": path.suffix.lower().lstrip(".") or "path",
                "contains_original100": "original100" in name,
                "contains_top64": "source_rich" in name,
                "contains_attack_eval": "attack" in name,
                "contains_final_ood_eval": "ood" in name,
                "contains_timestamp": False,
                "contains_packet_order": False,
                "contains_capture_id": False,
                "contains_bin_id": "stage2_manifest" in name,
                "can_support_clean_independent_validation": False,
                "can_support_consistency_only": True,
                "leakage_risk": "unknown_without_row_manifest",
                "notes": f"exists={path.exists()}; feature matrix/manifest asset but no persisted full row-level timestamp mapping.",
            }
        )
    raw_candidates = [
        ("stage2_attack_manifest", paths.get("stage2_manifest", "")),
        ("raw_iot23_mirai_log_from_manifest", ""),
    ]
    manifest_path = Path(paths.get("stage2_manifest", ""))
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            raw_candidates[1] = ("raw_iot23_mirai_log_from_manifest", manifest.get("source_zeek_log", ""))
        except Exception:
            pass
    for name, path_str in raw_candidates:
        if not path_str:
            continue
        path = Path(path_str)
        rows.append(
            {
                "asset_name": name,
                "asset_path": str(path),
                "asset_type": path.suffix.lower().lstrip(".") or "manifest/raw",
                "contains_original100": False,
                "contains_top64": False,
                "contains_attack_eval": "malicious" in path.name.lower() or "mirai" in path.name.lower(),
                "contains_final_ood_eval": False,
                "contains_timestamp": name != "stage2_attack_manifest",
                "contains_packet_order": name != "stage2_attack_manifest",
                "contains_capture_id": "log" in path.name.lower(),
                "contains_bin_id": name == "stage2_attack_manifest",
                "can_support_clean_independent_validation": False,
                "can_support_consistency_only": True,
                "leakage_risk": "medium_until_reconstruction_manifest_exists",
                "notes": f"exists={path.exists()}; could help raw provenance recovery but not directly ready as clean validation.",
            }
        )
    rows.append(
        {
            "asset_name": "issue26b_metadata_recovery",
            "asset_path": str(ISSUE26B / "summary.md"),
            "asset_type": "metadata_audit",
            "contains_original100": False,
            "contains_top64": False,
            "contains_attack_eval": False,
            "contains_final_ood_eval": False,
            "contains_timestamp": False,
            "contains_packet_order": False,
            "contains_capture_id": False,
            "contains_bin_id": True,
            "can_support_clean_independent_validation": False,
            "can_support_consistency_only": True,
            "leakage_risk": "blocking_metadata_gap",
            "notes": "issue26b recovered coarse bin provenance but not raw timestamp/packet-order/capture/session row manifest.",
        }
    )
    return pd.DataFrame(rows)


def separator_stability_nonlocked(specs: list[dict[str, Any]], sep_idx: list[int], x_attack_o: np.ndarray, x_attack_sr: np.ndarray, sr_names: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for spec in specs:
        support_rows = support_rows_for_spec(spec, x_attack_o)
        mats = mats_for_spec(spec, support_rows, x_attack_o, x_attack_sr, sr_names)
        final_ood = mats["ood_eval"]
        attack_eval = mats["attack_eval"]
        y = np.concatenate([np.zeros(len(final_ood), dtype=np.int64), np.ones(len(attack_eval), dtype=np.int64)])
        all_auc: list[tuple[int, float]] = []
        for feat in range(100):
            score = np.concatenate([final_ood[:, feat], attack_eval[:, feat]])
            auc_pos = safe_auc(y, score)
            auc_neg = safe_auc(y, -score)
            all_auc.append((feat, float(np.nanmax([auc_pos, auc_neg]))))
        sorted_auc = sorted(all_auc, key=lambda x: x[1], reverse=True)
        ranks = {feat: rank + 1 for rank, (feat, _) in enumerate(sorted_auc)}
        for feat in sep_idx:
            desc = feature_descriptor(feat)
            attack = attack_eval[:, feat]
            ood = final_ood[:, feat]
            support = mats["support"][:, feat]
            ood_train = mats["ood_train"][:, feat]
            score = np.concatenate([ood, attack])
            auc_pos = safe_auc(y, score)
            auc_neg = safe_auc(y, -score)
            best_auc = float(np.nanmax([auc_pos, auc_neg]))
            rows.append(
                {
                    "asset_name": str(spec["holdout"]),
                    "dataset": spec["dataset"],
                    "evidence_level": "consistency_only",
                    "clean_independent": False,
                    "feature_index": feat,
                    **desc,
                    "attack_median": float(np.median(attack)),
                    "attack_q05": float(np.quantile(attack, 0.05)),
                    "attack_q95": float(np.quantile(attack, 0.95)),
                    "ood_eval_median": float(np.median(ood)),
                    "ood_eval_q05": float(np.quantile(ood, 0.05)),
                    "ood_eval_q95": float(np.quantile(ood, 0.95)),
                    "attack_vs_ood_best_auc": best_auc,
                    "attack_vs_ood_direction": "positive" if (not math.isnan(auc_pos) and auc_pos >= auc_neg) else "negative",
                    "feature_rank_by_single_feature_auc": ranks[feat],
                    "top3_remain_high_separator": ranks[feat] <= 10 and best_auc >= 0.9,
                    "support_vs_new_attack_ks": ks_distance(support, attack),
                    "support_vs_new_attack_median_delta": float(abs(np.median(support) - np.median(attack))),
                    "ood_train_vs_new_ood_ks": ks_distance(ood_train, ood),
                    "distribution_shift_appears_time_or_capture_driven": bool(ks_distance(ood_train, ood) > 0.2 or ks_distance(support, attack) > 0.5),
                    "notes": "Non-locked consistency only; not a clean independent validation asset.",
                }
            )
    return pd.DataFrame(rows)


def frozen_lowguardpp_nonlocked(specs: list[dict[str, Any]], x_attack_o: np.ndarray, x_attack_sr: np.ndarray, sr_names: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    for spec in specs:
        support_rows = support_rows_for_spec(spec, x_attack_o)
        mats = mats_for_spec(spec, support_rows, x_attack_o, x_attack_sr, sr_names)
        for seed in FULL_SEEDS:
            adapter = fit_frozen_histgb(mats, seed)
            result, _ = eval_adapter(adapter, mats, FORMAL_TARGET)
            rows.append(
                {
                    "asset_name": str(spec["holdout"]),
                    "dataset": spec["dataset"],
                    "evidence_level": "consistency_only",
                    "clean_independent": False,
                    "seed": int(seed),
                    "attack_detection": result["attack_detection"],
                    "final_ood_alarm": result["final_ood_alarm"],
                    "id_calib_alarm": result["id_calib_alarm"],
                    "ood_val_alarm": result["ood_val_alarm"],
                    "threshold": result["threshold"],
                    "feasible_under_1pct": bool(result["final_ood_alarm"] <= OFFICIAL_TARGET),
                    "roc_auc_attack_vs_ood": result["roc_auc_attack_vs_ood"],
                    "pr_auc_attack_vs_ood": result["pr_auc_attack_vs_ood"],
                    "pauc_fpr_1pct": result["pauc_fpr_1pct"],
                    "tpr_at_fpr_1pct": result["tpr_at_fpr_1pct"],
                    "frozen_config_id": issue27f.FROZEN_CONFIG_ID,
                    "final_eval_used_for_selection": False,
                    "notes": "Frozen LOW-GUARD++ direct report on non-locked consistency object.",
                }
            )
    by_seed = pd.DataFrame(rows)
    summary = (
        by_seed.groupby(["asset_name", "dataset", "evidence_level", "clean_independent"], as_index=False)
        .agg(
            detection_mean=("attack_detection", "mean"),
            detection_min=("attack_detection", "min"),
            ood_alarm_max=("final_ood_alarm", "max"),
            feasible_rate=("feasible_under_1pct", "mean"),
            pauc_mean=("pauc_fpr_1pct", "mean"),
            tpr_at_fpr_1pct_mean=("tpr_at_fpr_1pct", "mean"),
        )
        .sort_values("asset_name")
    )
    return by_seed, summary


def safer_feature_variants(specs: list[dict[str, Any]], sep_idx: list[int], x_attack_o: np.ndarray, x_attack_sr: np.ndarray, sr_names: list[str]) -> pd.DataFrame:
    variants = [
        "original100_all",
        "original100_remove_top1",
        "original100_remove_top2",
        "original100_remove_top3",
        "original100_clip_top3_by_train_quantile",
        "original100_rank_normalize_top3",
        "original100_group_aggregate_HH_features",
        "original100_drop_lambda_0.01_HH_features",
        "original100_drop_all_HH_radius_magnitude_top_family",
    ]
    rows: list[dict[str, Any]] = []
    for spec in specs:
        support_rows = support_rows_for_spec(spec, x_attack_o)
        base_mats = mats_for_spec(spec, support_rows, x_attack_o, x_attack_sr, sr_names)
        for seed in FULL_SEEDS:
            for variant in variants:
                mats, transform_description, feature_count = transform_mats(base_mats, variant, sep_idx)
                t0 = time.perf_counter()
                adapter = fit_frozen_histgb(mats, seed)
                result, _ = eval_adapter(adapter, mats, FORMAL_TARGET)
                rows.append(
                    {
                        "feature_variant": variant,
                        "holdout": spec["holdout"],
                        "seed": int(seed),
                        "feature_count": feature_count,
                        "transform_description": transform_description,
                        "attack_detection": result["attack_detection"],
                        "final_ood_alarm": result["final_ood_alarm"],
                        "id_calib_alarm": result["id_calib_alarm"],
                        "ood_val_alarm": result["ood_val_alarm"],
                        "threshold": result["threshold"],
                        "feasible_under_1pct": bool(result["final_ood_alarm"] <= OFFICIAL_TARGET),
                        "roc_auc_attack_vs_ood": result["roc_auc_attack_vs_ood"],
                        "pr_auc_attack_vs_ood": result["pr_auc_attack_vs_ood"],
                        "pauc_fpr_1pct": result["pauc_fpr_1pct"],
                        "tpr_at_fpr_1pct": result["tpr_at_fpr_1pct"],
                        "train_time": float(adapter.train_time),
                        "inference_time": float(result["inference_time"]),
                        "frozen_config_id": issue27f.FROZEN_CONFIG_ID,
                        "final_eval_used_for_selection": False,
                        "threshold_uses_final_eval": False,
                        "notes": "Predefined safer feature variant; not selected using final eval.",
                    }
                )
    return pd.DataFrame(rows)


def summarize_by_seed(by_seed: pd.DataFrame, group_col: str) -> pd.DataFrame:
    return (
        by_seed.groupby([group_col, "feature_count", "transform_description"], as_index=False)
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
        .sort_values(["locked_detection_mean", "locked_detection_min"], ascending=False)
    )


def compare_variants_to_lr(summary: pd.DataFrame) -> pd.DataFrame:
    formal = pd.read_csv(ISSUE27F / "formal_locked_summary.csv")
    lr = formal[formal["method"].eq("LOW_GUARD_LR_top64_reference")].iloc[0]
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
    out["risk_reduced_feature_transform"] = ~out["feature_variant"].isin(["original100_all", "original100_remove_top1", "original100_remove_top2"])
    out["retains_top3_separator_information"] = ~out["feature_variant"].isin(
        ["original100_remove_top3", "original100_drop_all_HH_radius_magnitude_top_family"]
    )
    out["separator_independent"] = ~out["retains_top3_separator_information"]
    # Backward-compatible column name for the requested output schema. This means
    # "less raw top3-dependent", not "separator independent"; reports spell out
    # the distinction to avoid overclaiming safer transforms.
    out["safer_than_top3_dependency"] = out["risk_reduced_feature_transform"]
    return out


def data_expansion_plan(inventory: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {
            "route": "same_dataset_new_chronological_window",
            "required_inputs": "raw packet timestamp; packet order; window start/end; original100 reconstruction script; attack/OOD split map",
            "estimated_engineering_cost": "medium",
            "whether_slurm_needed": "maybe_for_full_reconstruction",
            "leakage_risk": "medium_without_purge_embargo",
            "expected_evidence_value": "high_for_separator_temporal_stability",
            "priority": "P0",
            "reason": "Directly tests whether HH separators survive a new chronological window without using locked bins.",
        },
        {
            "route": "same_dataset_new_capture_or_session",
            "required_inputs": "capture/session id; raw feature reconstruction; benign/attack label map; unused session boundary",
            "estimated_engineering_cost": "medium_high",
            "whether_slurm_needed": "maybe",
            "leakage_risk": "low_medium_if_session_disjoint",
            "expected_evidence_value": "high_for_capture_artifact_defense",
            "priority": "P1",
            "reason": "Best defense against capture-specific separator artifact if assets exist.",
        },
        {
            "route": "second_environment_same_feature_builder",
            "required_inputs": "raw compatible traffic; Kitsune original100 extractor; attack/OOD labels; clean support/eval split",
            "estimated_engineering_cost": "high",
            "whether_slurm_needed": "yes_if_large_extraction",
            "leakage_risk": "low_if_protocol_pre_registered",
            "expected_evidence_value": "very_high_external_generalization",
            "priority": "P2",
            "reason": "Needed for external claims, but should follow raw provenance recovery unless ready assets exist.",
        },
        {
            "route": "second_dataset_schema_compatible",
            "required_inputs": "feature construction compatibility; labels; benign OOD split; support pool; no final eval tuning",
            "estimated_engineering_cost": "high",
            "whether_slurm_needed": "yes_possible",
            "leakage_risk": "medium_due_schema_shift",
            "expected_evidence_value": "high_if_successful_but_harder_to_interpret",
            "priority": "P3",
            "reason": "Useful later; schema and capture differences can confound separator interpretation.",
        },
    ]
    return pd.DataFrame(rows)


def decide(
    inventory: pd.DataFrame,
    stability: pd.DataFrame,
    nonlocked_summary: pd.DataFrame,
    variants_vs_lr: pd.DataFrame,
) -> tuple[str, str, dict[str, Any]]:
    clean_asset_exists = inventory["can_support_clean_independent_validation"].astype(str).str.lower().eq("true").any()
    separator_stability_strong = bool(len(stability) and (stability.groupby("asset_name")["top3_remain_high_separator"].mean() >= 2 / 3).mean() >= 2 / 3)
    consistency_support_strong = bool(len(nonlocked_summary) and (nonlocked_summary["detection_mean"] >= 0.9).mean() >= 2 / 3 and (nonlocked_summary["ood_alarm_max"] <= OFFICIAL_TARGET).all())
    safer = variants_vs_lr[
        variants_vs_lr["risk_reduced_feature_transform"].astype(bool)
        & ~variants_vs_lr["feature_variant"].isin(["original100_remove_top3"])
    ].copy()
    safer_strong = bool(len(safer) and safer["dominates_lowguard_lr_three_axis"].astype(bool).any())
    best_safer = safer.sort_values(["dominates_lowguard_lr_three_axis", "locked_detection_mean", "locked_detection_min"], ascending=False).head(1)
    best_safer_variant = str(best_safer["feature_variant"].iloc[0]) if len(best_safer) else "none"
    diagnostics = {
        "clean_asset_exists": clean_asset_exists,
        "separator_stability_strong_on_consistency": separator_stability_strong,
        "nonlocked_consistency_support_strong": consistency_support_strong,
        "safer_variant_strong_vs_lr": safer_strong,
        "best_safer_variant": best_safer_variant,
    }
    if clean_asset_exists and safer_strong:
        return "lowguard_plus_plus_independent_support_strengthened", "issue27j_formal_independent_validation_for_lowguard_plus_plus", diagnostics
    if not clean_asset_exists and safer_strong:
        return "lowguard_plus_plus_promising_needs_clean_independent_validation", "issue27j_raw_provenance_recovery_and_clean_independent_split_construction", diagnostics
    if (not safer_strong) and separator_stability_strong:
        return "lowguard_plus_plus_separator_signal_real_but_high_dependency", "issue27j_separator_dependency_deeper_audit_and_data_expansion", diagnostics
    if not separator_stability_strong and len(stability):
        return "lowguard_plus_plus_separator_signal_not_stable_needs_data_expansion", "issue27j_data_expansion_for_separator_stability", diagnostics
    return "independent_validation_blocked_needs_data_expansion", "issue27j_raw_provenance_recovery_and_clean_independent_split_construction", diagnostics


def write_reports(
    *,
    input_status: pd.DataFrame,
    inventory: pd.DataFrame,
    stability: pd.DataFrame,
    nonlocked_by_seed: pd.DataFrame,
    nonlocked_summary: pd.DataFrame,
    variants_by_seed: pd.DataFrame,
    variants_summary: pd.DataFrame,
    variants_vs_lr: pd.DataFrame,
    expansion_table: pd.DataFrame,
    primary_verdict: str,
    issue27j_action: str,
    diagnostics: dict[str, Any],
) -> None:
    write_text(
        OUT / "available_independent_assets_diagnosis.md",
        f"""
# Available Independent Assets Diagnosis

Clean independent validation asset exists: `{diagnostics['clean_asset_exists']}`.

Current repository assets include locked bins and several non-locked consistency objects, but no row-level raw timestamp / packet-order / capture/session manifest sufficient for a clean new formal independent split.

{md_table(inventory[['asset_name','asset_type','contains_original100','contains_attack_eval','contains_timestamp','contains_packet_order','contains_capture_id','contains_bin_id','can_support_clean_independent_validation','can_support_consistency_only','leakage_risk']].head(25), 25)}
""",
    )
    write_text(
        OUT / "separator_stability_nonlocked_diagnosis.md",
        f"""
# Separator Stability On Non-Locked Assets

Evidence level: `consistency_only`.

Separator stability strong on available consistency assets: `{diagnostics['separator_stability_strong_on_consistency']}`.

{md_table(stability.groupby(['asset_name','feature_index','feature_name'], as_index=False).agg(auc=('attack_vs_ood_best_auc','mean'), rank=('feature_rank_by_single_feature_auc','mean'), top_high=('top3_remain_high_separator','mean'), support_ks=('support_vs_new_attack_ks','mean'), ood_ks=('ood_train_vs_new_ood_ks','mean')), 30)}

Boundary: these are not clean independent validation objects because primary / holdout_bin_2 / chrono_late were already part of earlier discovery or consistency evidence.
""",
    )
    write_text(
        OUT / "safer_feature_variants_diagnosis.md",
        f"""
# Safer Feature Variants Diagnosis

Best safer variant: `{diagnostics['best_safer_variant']}`.
Safer variant strong vs LOW-GUARD-LR: `{diagnostics['safer_variant_strong_vs_lr']}`.

Important boundary: "safer" here means a pre-registered risk-reduction transform, not proof of separator independence. The strongest safer variant (`original100_rank_normalize_top3`) still retains top3 separator information, so it is promising but not enough for claim upgrade.

{md_table(variants_vs_lr[['feature_variant','feature_count','locked_detection_mean','locked_detection_min','locked_ood_alarm_max','feasible_rate','dominates_lowguard_lr_three_axis','risk_reduced_feature_transform','retains_top3_separator_information','separator_independent']])}

Interpretation: this stage does not select a replacement method. It identifies whether any pre-registered safer feature transform is promising enough for issue27j formal validation.
""",
    )
    write_text(
        OUT / "data_expansion_feasibility_plan.md",
        f"""
# Data Expansion Feasibility Plan

The current blocker is not compute; it is provenance and clean split construction. Minimum required raw assets:

- raw packet timestamp;
- packet order;
- capture/session id;
- window start/end;
- original100 reconstruction script and exact feature mapping;
- attack label mapping;
- OOD benign split mapping;
- support/eval row manifests.

Recommended minimum next step: `{issue27j_action}`.

{md_table(expansion_table)}
""",
    )
    write_text(
        OUT / "lowguard_plus_plus_path_decision.md",
        f"""
# LOW-GUARD++ Path Decision

- primary_verdict: `{primary_verdict}`
- issue27j_next_action: `{issue27j_action}`

Diagnostics:

{md_table(pd.DataFrame([diagnostics]))}

Key caution: the best current safer variant is a transformed-use variant, not a separator-independent variant. It cannot by itself clear the original100 separator-dependency concern.

Decision:
- Do not demote LOW-GUARD++ permanently.
- Do not upgrade it to a main-text performance instance yet.
- Continue through raw provenance / clean independent validation unless future evidence proves separator artifact.
""",
    )
    if primary_verdict in {"lowguard_plus_plus_independent_support_strengthened", "lowguard_plus_plus_promising_needs_clean_independent_validation", "lowguard_plus_plus_separator_signal_real_but_high_dependency"}:
        claim = """
- LOW-GUARD++ remains a high-potential performance instance candidate.
- Separator dependency is now characterized rather than ignored.
- Claim upgrade requires clean independent validation unless formal independent support is obtained.
"""
    else:
        claim = """
- LOW-GUARD++ is not abandoned, but current evidence is insufficient for main claim upgrade.
- Further raw provenance or independent validation is required.
- LOW-GUARD-LR remains the clean demonstrated fallback, not necessarily the final mainline.
"""
    write_text(
        OUT / "claim_update_after_issue27i.md",
        f"""
# Claim Update After Issue27i

## Allowed

{claim}

## Forbidden

- LOW-GUARD++ is demoted permanently without independent validation.
- LOW-GUARD-LR is the final main method solely because issue27h found separator dependency.
- Deployment robustness is the next step unless LOW-GUARD++ validation is blocked and no data expansion path exists.
- Temporal/cross-dataset generalization is proven.
- Broad model universality is proven.
""",
    )
    write_text(
        OUT / "reviewer_defense_separator_dependency.md",
        f"""
# Reviewer Defense: Separator Dependency

## Q1: Are the HH separator features ignored?

No. issue27h showed strong dependence; issue27i characterizes their stability and plans clean validation rather than hiding the risk.

## Q2: Are they real attack signals or data artifacts?

Current evidence says they are legal KitNET traffic-stat features and remain informative in some non-locked consistency assets. However, without clean row-level provenance and independent splits, they cannot yet be promoted as general attack statistics.

## Q3: Does this mean LOW-GUARD++ should be abandoned?

No. It means LOW-GUARD++ is a high-potential candidate with a separator-dependency risk. The correct next step is clean validation/data expansion, not premature demotion.

## Q4: Why not deployment robustness now?

Because deployment robustness would stress a candidate whose feature-dependency claim is not cleanly validated. The scientific blocker is separator independence and provenance.
""",
    )
    write_text(
        OUT / "issue27j_next_action.md",
        f"""
# Issue27j Next Action

Recommended next action: `{issue27j_action}`.

Rationale: LOW-GUARD++ should continue, but the next experiment must resolve whether the HH separator signal survives clean independent construction. Deployment robustness should wait until this gate is resolved or explicitly blocked.
""",
    )
    write_text(
        OUT / "summary.md",
        f"""
# Issue27i Separator Independent Validation And Data Expansion Feasibility Summary

## Verdict

- primary_verdict: `{primary_verdict}`
- issue27j_next_action: `{issue27j_action}`

## 1. Clean independent validation asset

Exists now: `{diagnostics['clean_asset_exists']}`.

Missing: raw timestamp, packet order, capture/session id, window start/end, row-level support/eval manifests, and clean unused split construction.

## 2. Separator stability outside locked bins

Separator stability on available non-locked consistency assets: `{diagnostics['separator_stability_strong_on_consistency']}`.

## 3. Frozen LOW-GUARD++ non-locked report

{md_table(nonlocked_summary)}

Evidence level is consistency-only, not formal independent validation.

## 4. Safer feature variants

Safer variant strong vs LOW-GUARD-LR: `{diagnostics['safer_variant_strong_vs_lr']}`.
Best safer variant: `{diagnostics['best_safer_variant']}`.

{md_table(variants_vs_lr[['feature_variant','locked_detection_mean','locked_detection_min','locked_ood_alarm_max','dominates_lowguard_lr_three_axis','risk_reduced_feature_transform','retains_top3_separator_information','separator_independent']])}

Boundary: the best safer variant still retains transformed top3 separator information. This supports continuing LOW-GUARD++, but it does not establish separator-independent generalization.

## 5. Interpretation of top3 separator

The separator is more likely a real but currently over-sharp traffic-stat signal than an explicit label/split artifact. It is still not cleanly generalizable until raw provenance and independent validation are obtained.

## 6. Continue LOW-GUARD++?

Yes. Do not abandon or permanently demote it. But do not upgrade it to main-text performance instance yet.

## 7. Need raw provenance / second environment / temporal expansion?

Yes. The preferred next step is raw provenance and clean independent split construction; second environment remains valuable if compatible features can be reconstructed.

## 8. Slurm

Not needed for this feasibility run. May be needed for full raw feature reconstruction or large second-environment extraction.
""",
    )
    write_text(
        OUT / "command.txt",
        """
git branch --show-current
git status --short
read issue27h/27g/27f/26b/25c assets
python runs/issue27i_separator_independent_validation_and_data_expansion_feasibility_for_lowguard_plus_plus_2026-05-27/run_issue27i_separator_validation_feasibility.py
""",
    )
    config = {
        "issue": "issue27i_separator_independent_validation_and_data_expansion_feasibility_for_lowguard_plus_plus_2026-05-27",
        "frozen_method": "LOW-GUARD++ original100 + HistGB-Conservative",
        "frozen_config_id": issue27f.FROZEN_CONFIG_ID,
        "locked_bins": LOCKED_BINS,
        "nonlocked_holdouts": NONLOCKED_HOLDOUTS,
        "seeds": FULL_SEEDS,
        "official_ood_target": OFFICIAL_TARGET,
        "threshold_target": FORMAL_TARGET,
        "final_eval_policy": "report_only_no_selection",
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    run_spec = {
        "task": "separator_independent_validation_and_data_expansion_feasibility",
        "inputs": input_status.to_dict(orient="records"),
        "primary_verdict": primary_verdict,
        "issue27j_action": issue27j_action,
        "outputs": [
            "summary.md",
            "available_independent_assets_inventory.csv",
            "available_independent_assets_diagnosis.md",
            "separator_stability_nonlocked_by_asset.csv",
            "separator_stability_nonlocked_diagnosis.md",
            "frozen_lowguardpp_nonlocked_by_asset.csv",
            "frozen_lowguardpp_nonlocked_summary.csv",
            "safer_feature_variants_by_seed.csv",
            "safer_feature_variants_summary.csv",
            "safer_feature_variants_vs_lr.csv",
            "safer_feature_variants_diagnosis.md",
            "data_expansion_feasibility_plan.md",
            "data_expansion_feasibility_table.csv",
            "lowguard_plus_plus_path_decision.md",
            "claim_update_after_issue27i.md",
            "reviewer_defense_separator_dependency.md",
            "issue27j_next_action.md",
            "command.txt",
            "config.json",
            "run_spec.json",
            "manifest.csv",
        ],
    }
    (OUT / "run_spec.json").write_text(json.dumps(run_spec, indent=2), encoding="utf-8")


def update_mainline_docs(primary_verdict: str, issue27j_action: str) -> None:
    handoff = MAINLINE / "mainline_handoff.md"
    expmap = MAINLINE / "mainline_experiment_map.md"
    handoff_append = f"""

## issue27i separator validation feasibility (2026-05-27)

- primary_verdict: `{primary_verdict}`
- scope: inventories clean independent assets, checks HH separator stability on non-locked consistency objects, reports frozen LOW-GUARD++ outside locked bins, evaluates safer feature variants without tuning, and plans data expansion.
- claim boundary: LOW-GUARD++ is not abandoned, but cannot be upgraded to main-text performance instance until clean independent validation or raw provenance resolves separator dependency.
- next action: `{issue27j_action}`.
"""
    expmap_append = f"""
| issue27i | LOW-GUARD++ separator validation and data expansion feasibility | `{primary_verdict}` | Characterizes separator stability and safer variants; keeps LOW-GUARD++ alive while blocking claim upgrade pending clean independent validation. Next: `{issue27j_action}`. |
"""
    htxt = handoff.read_text(encoding="utf-8")
    htxt = re.sub(r"\n## issue27i separator validation feasibility \(2026-05-27\)\n.*?(?=\n## |\Z)", "", htxt, flags=re.S)
    handoff.write_text(htxt.rstrip() + handoff_append + "\n", encoding="utf-8")
    etxt = expmap.read_text(encoding="utf-8")
    etxt = re.sub(r"(?m)^\| issue27i \|.*\|\r?\n?", "", etxt)
    etxt = re.sub(r"(?m)^ Characterizes separator stability and safer variants;.*\|\r?\n?", "", etxt)
    expmap.write_text(etxt.rstrip() + "\n\n" + expmap_append.strip() + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    input_status = required_input_status()
    input_status.to_csv(OUT / "manifest.csv", index=False)
    missing = input_status[(input_status["required"]) & (~input_status["exists"])]
    if len(missing):
        write_text(OUT / "summary.md", "primary_verdict: `independent_validation_blocked_needs_data_expansion`\n\nRequired inputs missing; see manifest.csv.")
        raise SystemExit(1)

    sep_df = pd.read_csv(ISSUE27H / "feature_provenance_mapping.csv")
    sep_idx = sep_df["original100_index"].astype(int).tolist()
    paths, datasets, _, _, x_attack_o, _, _, x_attack_sr, sr_names, asset_report = load_all_assets()
    inventory = available_assets_inventory(paths, datasets, asset_report)
    nonlocked_specs = [spec for spec in datasets if str(spec.get("evaluation_role")) == "consistency" and str(spec["holdout"]) in NONLOCKED_HOLDOUTS]
    locked_specs = [spec for spec in datasets if str(spec.get("evaluation_role")) == "locked" and str(spec["holdout"]) in LOCKED_BINS]

    stability = separator_stability_nonlocked(nonlocked_specs, sep_idx, x_attack_o, x_attack_sr, sr_names)
    nonlocked_by_seed, nonlocked_summary = frozen_lowguardpp_nonlocked(nonlocked_specs, x_attack_o, x_attack_sr, sr_names)
    variants_by_seed = safer_feature_variants(locked_specs, sep_idx, x_attack_o, x_attack_sr, sr_names)
    variants_summary = summarize_by_seed(variants_by_seed, "feature_variant")
    variants_vs_lr = compare_variants_to_lr(variants_summary)
    expansion_table = data_expansion_plan(inventory)
    primary_verdict, issue27j_action, diagnostics = decide(inventory, stability, nonlocked_summary, variants_vs_lr)

    inventory.to_csv(OUT / "available_independent_assets_inventory.csv", index=False)
    stability.to_csv(OUT / "separator_stability_nonlocked_by_asset.csv", index=False)
    nonlocked_by_seed.to_csv(OUT / "frozen_lowguardpp_nonlocked_by_asset.csv", index=False)
    nonlocked_summary.to_csv(OUT / "frozen_lowguardpp_nonlocked_summary.csv", index=False)
    variants_by_seed.to_csv(OUT / "safer_feature_variants_by_seed.csv", index=False)
    variants_summary.to_csv(OUT / "safer_feature_variants_summary.csv", index=False)
    variants_vs_lr.to_csv(OUT / "safer_feature_variants_vs_lr.csv", index=False)
    expansion_table.to_csv(OUT / "data_expansion_feasibility_table.csv", index=False)

    write_reports(
        input_status=input_status,
        inventory=inventory,
        stability=stability,
        nonlocked_by_seed=nonlocked_by_seed,
        nonlocked_summary=nonlocked_summary,
        variants_by_seed=variants_by_seed,
        variants_summary=variants_summary,
        variants_vs_lr=variants_vs_lr,
        expansion_table=expansion_table,
        primary_verdict=primary_verdict,
        issue27j_action=issue27j_action,
        diagnostics=diagnostics,
    )
    update_mainline_docs(primary_verdict, issue27j_action)
    print(f"[issue27i] primary_verdict={primary_verdict}")
    print(f"[issue27i] issue27j_action={issue27j_action}")


if __name__ == "__main__":
    main()
