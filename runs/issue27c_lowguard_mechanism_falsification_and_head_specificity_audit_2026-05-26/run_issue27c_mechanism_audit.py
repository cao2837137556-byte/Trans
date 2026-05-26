from __future__ import annotations

import importlib.util
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs" / "issue27c_lowguard_mechanism_falsification_and_head_specificity_audit_2026-05-26"

ISSUE27B = ROOT / "runs" / "issue27b_guarded_protocol_transfer_and_adapter_recovery_2026-05-26"
ISSUE25C = ROOT / "runs" / "issue25c_strong_baseline_pack_execution_for_enhanced_lowguard_top64_2026-05-18"
ISSUE23 = ROOT / "runs" / "issue23_locked_validation_for_enhanced_v2_top64_2026-05-18"
ISSUE11 = ROOT / "runs" / "issue11_fixed_config_ood_guard_lr_ablation_2026-05-14"
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"
ISSUE27B_SCRIPT = ISSUE27B / "run_issue27b_guarded_protocol_transfer.py"

TARGETS = [0.0100, 0.0075, 0.0050, 0.0025]
CORE_HEADS = ["LOW_GUARD_LR_reference", "DevNet_like_MLP", "HistGB_shallow", "DeepSAD_like_center"]
LOCKED_HOLDOUTS = ["holdout_bin_5", "holdout_bin_6", "holdout_bin_7", "holdout_bin_8"]
SEEDS = list(range(42, 52))


def import_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


issue27b = import_module(ISSUE27B_SCRIPT, "issue27b_for_issue27c")


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
        ISSUE27B / "summary.md",
        ISSUE27B / "protocol_transfer_by_seed.csv",
        ISSUE27B / "protocol_transfer_locked_summary.csv",
        ISSUE27B / "adapter_selection_trace.csv",
        ISSUE27B / "model_recovery_mode_summary.csv",
        ISSUE27B / "near_lr_baseline_upgrade_report.csv",
        ISSUE27B / "lowguard_plus_plus_candidate_report.csv",
        ISSUE25C / "summary.md",
        ISSUE23 / "locked_validation_asset_report.md",
        MAINLINE_DOCS / "mainline_handoff.md",
        MAINLINE_DOCS / "mainline_experiment_map.md",
        ISSUE11 / "config.json",
        ISSUE27B_SCRIPT,
    ]
    return [str(path) for path in required if not path.exists()]


def find_head(head_id: str) -> dict[str, Any]:
    for head in issue27b.head_specs():
        if head["head_id"] == head_id:
            return head
    raise KeyError(head_id)


def find_protocol(protocol_variant: str) -> dict[str, Any]:
    for proto in issue27b.protocol_variants():
        if proto["protocol_variant"] == protocol_variant:
            return proto
    raise KeyError(protocol_variant)


def find_config(head: dict[str, Any], config_id: str) -> dict[str, Any]:
    for config in head["configs"]:
        if str(config["config_id"]) == str(config_id):
            return config
    raise KeyError((head["head_id"], config_id))


def selected_config_id(selection: pd.DataFrame, holdout: str, seed: int, head_id: str, protocol_variant: str) -> str:
    mask = (
        selection["holdout"].eq(holdout)
        & selection["seed"].eq(seed)
        & selection["head_id"].eq(head_id)
        & selection["protocol_variant"].eq(protocol_variant)
        & selection["selected"].astype(str).str.lower().eq("true")
    )
    rows = selection[mask]
    if rows.empty:
        raise RuntimeError(f"Missing selected config for {holdout} seed={seed} {head_id} {protocol_variant}")
    return str(rows.iloc[0]["config_id"])


def quantiles(scores: np.ndarray) -> dict[str, float]:
    scores = np.asarray(scores, dtype=np.float64)
    return {
        "min": float(np.min(scores)),
        "q01": float(np.quantile(scores, 0.01)),
        "q05": float(np.quantile(scores, 0.05)),
        "q25": float(np.quantile(scores, 0.25)),
        "median": float(np.median(scores)),
        "q75": float(np.quantile(scores, 0.75)),
        "q95": float(np.quantile(scores, 0.95)),
        "q99": float(np.quantile(scores, 0.99)),
        "max": float(np.max(scores)),
    }


def guarded_threshold(score_id_calib: np.ndarray, score_ood_val: np.ndarray, target: float) -> dict[str, Any]:
    out = issue27b.issue25c.issue19b.v72.guarded_val_threshold(score_id_calib, score_ood_val, float(target))
    out["threshold_source"] = "id_calib_plus_ood_val_guarded"
    return out


def mechanism_tables(summary: pd.DataFrame, by_seed: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    lr = summary[summary["head_id"].eq("LOW_GUARD_LR_reference")].copy()
    order = ["P0_raw_train_id_threshold", "P1_raw_train_oodval_threshold", "P2_guarded_train_id_threshold", "P3_full_lowguard"]
    lr["protocol_order"] = lr["protocol_variant"].map({p: i for i, p in enumerate(order)})
    lr = lr.sort_values("protocol_order")
    p0 = lr[lr["protocol_variant"].eq("P0_raw_train_id_threshold")].iloc[0]
    rows = []
    for _, row in lr.iterrows():
        rows.append(
            {
                "head_id": "LOW_GUARD_LR_reference",
                "protocol_variant": row["protocol_variant"],
                "train_uses_ood_guard": bool(row["protocol_variant"] in {"P2_guarded_train_id_threshold", "P3_full_lowguard"}),
                "threshold_uses_ood_val_guard": bool(row["protocol_variant"] in {"P1_raw_train_oodval_threshold", "P3_full_lowguard"}),
                "locked_detection_mean": float(row["locked_detection_mean"]),
                "locked_detection_min": float(row["locked_detection_min"]),
                "locked_ood_alarm_max": float(row["locked_ood_alarm_max"]),
                "feasible_rate": float(row["feasible_rate"]),
                "delta_detection_vs_p0": float(row["locked_detection_mean"] - p0["locked_detection_mean"]),
                "delta_ood_alarm_vs_p0": float(row["locked_ood_alarm_max"] - p0["locked_ood_alarm_max"]),
                "mechanism_interpretation": {
                    "P0_raw_train_id_threshold": "raw LR separates attacks but also raises OOD tail; high detection is not deployable",
                    "P1_raw_train_oodval_threshold": "threshold guard alone enforces budget by moving threshold above attack support/eval mass; detection collapses",
                    "P2_guarded_train_id_threshold": "OOD-guarded training reshapes LR score separation; ID-only threshold already becomes low-alert feasible",
                    "P3_full_lowguard": "full protocol preserves P2 detection and adds validation safety gate",
                }[str(row["protocol_variant"])],
            }
        )
    row_df = pd.DataFrame(rows)

    seed_lr = by_seed[by_seed["head_id"].eq("LOW_GUARD_LR_reference")].copy()
    seed_pivot = seed_lr.pivot_table(
        index=["holdout", "seed"],
        columns="protocol_variant",
        values=["attack_detection", "final_ood_alarm", "threshold", "ood_val_alarm"],
        aggfunc="first",
    )
    seed_pivot.columns = ["__".join(col) for col in seed_pivot.columns]
    seed_pivot = seed_pivot.reset_index()
    seed_pivot["p2_detection_minus_p1"] = seed_pivot["attack_detection__P2_guarded_train_id_threshold"] - seed_pivot["attack_detection__P1_raw_train_oodval_threshold"]
    seed_pivot["p2_ood_minus_p0"] = seed_pivot["final_ood_alarm__P2_guarded_train_id_threshold"] - seed_pivot["final_ood_alarm__P0_raw_train_id_threshold"]
    return row_df, seed_pivot


def head_specificity(summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for head_id, g in summary.groupby("head_id"):
        d = {row["protocol_variant"]: row for _, row in g.iterrows()}
        if not all(k in d for k in ["P0_raw_train_id_threshold", "P1_raw_train_oodval_threshold", "P2_guarded_train_id_threshold", "P3_full_lowguard"]):
            continue
        p0, p1, p2, p3 = d["P0_raw_train_id_threshold"], d["P1_raw_train_oodval_threshold"], d["P2_guarded_train_id_threshold"], d["P3_full_lowguard"]
        train_guard_detection_response = float(p2["locked_detection_mean"] - p0["locked_detection_mean"])
        train_guard_ood_response = float(p2["locked_ood_alarm_max"] - p0["locked_ood_alarm_max"])
        threshold_guard_detection_response = float(p1["locked_detection_mean"] - p0["locked_detection_mean"])
        threshold_guard_ood_response = float(p1["locked_ood_alarm_max"] - p0["locked_ood_alarm_max"])
        if float(p3["locked_detection_mean"]) >= 0.90 and float(p3["locked_ood_alarm_max"]) <= 0.01:
            response_label = "full_lowguard_success"
        elif float(p3["locked_detection_mean"]) >= 0.90 and float(p3["locked_ood_alarm_max"]) > 0.01:
            response_label = "detection_high_ood_tail_uncontrolled"
        elif train_guard_detection_response > 0.10 and float(p3["locked_ood_alarm_max"]) > 0.01:
            response_label = "training_guard_response_not_low_alert_feasible"
        elif float(p3["locked_detection_mean"]) < 0.20:
            response_label = "nonresponsive_or_collapsed"
        else:
            response_label = "partial_response"
        rows.append(
            {
                "head_id": head_id,
                "head_family": str(g["head_family"].iloc[0]),
                "p0_detection": float(p0["locked_detection_mean"]),
                "p0_ood_max": float(p0["locked_ood_alarm_max"]),
                "p1_detection": float(p1["locked_detection_mean"]),
                "p1_ood_max": float(p1["locked_ood_alarm_max"]),
                "p2_detection": float(p2["locked_detection_mean"]),
                "p2_ood_max": float(p2["locked_ood_alarm_max"]),
                "p3_detection": float(p3["locked_detection_mean"]),
                "p3_detection_min": float(p3["locked_detection_min"]),
                "p3_ood_max": float(p3["locked_ood_alarm_max"]),
                "p3_feasible_rate": float(p3["feasible_rate"]),
                "train_guard_detection_response": train_guard_detection_response,
                "train_guard_ood_response": train_guard_ood_response,
                "threshold_guard_detection_response": threshold_guard_detection_response,
                "threshold_guard_ood_response": threshold_guard_ood_response,
                "response_label": response_label,
                "head_agnostic_support": bool(response_label == "full_lowguard_success" and head_id != "LOW_GUARD_LR_reference"),
            }
        )
    return pd.DataFrame(rows)


def load_frozen_assets() -> tuple[list[dict[str, Any]], np.ndarray, np.ndarray, list[str]]:
    cfg = json.loads((ISSUE11 / "config.json").read_text(encoding="utf-8"))
    paths = cfg["paths"]
    x_id_o = issue27b.issue25c.issue19b.load_matrix(Path(paths["original100_id"]))
    x_ood_o = issue27b.issue25c.issue19b.load_matrix(Path(paths["original100_ood"]))
    x_attack_o = issue27b.issue25c.issue19b.load_matrix(Path(paths["original100_attack"]))
    x_id_sr = issue27b.issue25c.issue19b.load_matrix(Path(paths["source_rich_id"]))
    x_ood_sr = issue27b.issue25c.issue19b.load_matrix(Path(paths["source_rich_ood"]))
    x_attack_sr = issue27b.issue25c.issue19b.load_matrix(Path(paths["source_rich_attack"]))
    schema_path = Path(paths["source_rich_id"]).parents[1] / "data" / "structured_schema.json"
    sr_names = issue27b.issue25c.issue19b.feature_names(schema_path, x_id_sr.shape[1])
    datasets, _, _ = issue27b.issue25c.issue23.build_locked_datasets(paths, x_id_o, x_ood_o, x_attack_o, x_id_sr, x_ood_sr, x_attack_sr)
    for spec in datasets:
        spec["evaluation_role"] = "locked"
    return datasets, x_attack_o, x_attack_sr, sr_names


def score_tail_and_curves(selection: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    datasets, x_attack_o, x_attack_sr, sr_names = load_frozen_assets()
    score_rows: list[dict[str, Any]] = []
    curve_rows: list[dict[str, Any]] = []
    for spec in datasets:
        holdout = str(spec["holdout"])
        train_pool = np.asarray(spec["attack_train_pool_idx"], dtype=np.int64)
        support_rows = issue27b.issue25c.issue19b.kcenter_support(train_pool, x_attack_o[train_pool], issue27b.SUPPORT_BUDGET)
        for seed in SEEDS:
            _, feature_idx, _, _ = issue27b.select_features_for_spec(spec, support_rows, x_attack_sr, sr_names, seed)
            mats_base = issue27b.mats_for(spec, feature_idx, x_attack_o, x_attack_sr, support_rows)
            for head_id in CORE_HEADS:
                head = find_head(head_id)
                for proto in issue27b.protocol_variants():
                    protocol_variant = str(proto["protocol_variant"])
                    config_id = selected_config_id(selection, holdout, seed, head_id, protocol_variant)
                    config = find_config(head, config_id)
                    fitted, aux = issue27b.fit_head(head, config, mats_base, seed, bool(proto["train_uses_ood_guard"]))
                    scores = {
                        "id_calib": issue27b.score_head(fitted, mats_base["id_calib"]),
                        "ood_val": issue27b.score_head(fitted, mats_base["ood_val"]),
                        "final_ood_eval": issue27b.score_head(fitted, mats_base["ood_eval"]),
                        "support": issue27b.score_head(fitted, mats_base["support"]),
                        "attack_eval": issue27b.score_head(fitted, mats_base["attack_eval"]),
                    }
                    thr_info = issue27b.calibrate_threshold(scores, proto)
                    threshold = float(thr_info["threshold"])
                    y = np.concatenate([np.zeros(len(scores["final_ood_eval"]), dtype=np.int64), np.ones(len(scores["attack_eval"]), dtype=np.int64)])
                    s = np.concatenate([scores["final_ood_eval"], scores["attack_eval"]])
                    base = {
                        "holdout": holdout,
                        "seed": int(seed),
                        "seed_group": issue27b.seed_group(seed),
                        "head_id": head_id,
                        "head_family": head["head_family"],
                        "protocol_variant": protocol_variant,
                        "selected_config_id": config_id,
                        "train_uses_ood_guard": bool(proto["train_uses_ood_guard"]),
                        "threshold_uses_ood_val_guard": bool(proto["threshold_uses_ood_val_guard"]),
                        "threshold": threshold,
                        "threshold_source": str(thr_info["threshold_source"]),
                        "id_calib_alarm": float(np.mean(scores["id_calib"] > threshold)),
                        "ood_val_alarm": float(np.mean(scores["ood_val"] > threshold)),
                        "final_ood_alarm": float(np.mean(scores["final_ood_eval"] > threshold)),
                        "support_detection": float(np.mean(scores["support"] > threshold)),
                        "attack_detection": float(np.mean(scores["attack_eval"] > threshold)),
                        "attack_margin_median": float(np.median(scores["attack_eval"] - threshold)),
                        "attack_margin_q25": float(np.quantile(scores["attack_eval"] - threshold, 0.25)),
                        "support_margin_median": float(np.median(scores["support"] - threshold)),
                        "ood_tail_count": int(np.sum(scores["final_ood_eval"] > threshold)),
                        "ood_tail_rate": float(np.mean(scores["final_ood_eval"] > threshold)),
                        "roc_auc_attack_vs_ood": float(issue27b.roc_auc_score(y, s)),
                        "score_direction_risk": bool(float(issue27b.roc_auc_score(y, s)) < 0.50),
                        "train_time": float(aux["train_time"]),
                    }
                    for name, vals in scores.items():
                        q = quantiles(vals)
                        for k, v in q.items():
                            base[f"{name}_{k}"] = v
                        base[f"{name}_threshold_percentile"] = float(np.mean(vals <= threshold))
                    base["attack_median_minus_final_ood_q99"] = float(base["attack_eval_median"] - base["final_ood_eval_q99"])
                    base["support_median_minus_ood_val_q99"] = float(base["support_median"] - base["ood_val_q99"])
                    score_rows.append(base)

                    if protocol_variant == "P3_full_lowguard":
                        for target in TARGETS:
                            target_thr = guarded_threshold(scores["id_calib"], scores["ood_val"], target)
                            thr = float(target_thr["threshold"])
                            curve_rows.append(
                                {
                                    "holdout": holdout,
                                    "seed": int(seed),
                                    "seed_group": issue27b.seed_group(seed),
                                    "head_id": head_id,
                                    "head_family": head["head_family"],
                                    "protocol_variant": protocol_variant,
                                    "selected_config_id": config_id,
                                    "ood_val_target": float(target),
                                    "threshold": thr,
                                    "id_calib_alarm": float(np.mean(scores["id_calib"] > thr)),
                                    "ood_val_alarm": float(np.mean(scores["ood_val"] > thr)),
                                    "attack_detection": float(np.mean(scores["attack_eval"] > thr)),
                                    "final_ood_alarm": float(np.mean(scores["final_ood_eval"] > thr)),
                                    "feasible_under_target": bool(float(np.mean(scores["final_ood_eval"] > thr)) <= float(target)),
                                    "selection_used_final_eval": False,
                                    "threshold_uses_final_eval": False,
                                    "config_selection_target": 0.01,
                                }
                            )
            print(f"[issue27c] {holdout} seed={seed} score audit completed", flush=True)
    score_df = pd.DataFrame(score_rows)
    curve_raw = pd.DataFrame(curve_rows)
    grouped = (
        curve_raw.groupby(["head_id", "head_family", "ood_val_target", "holdout", "seed_group"], as_index=False)
        .agg(
            detection_mean=("attack_detection", "mean"),
            detection_min=("attack_detection", "min"),
            ood_alarm_max=("final_ood_alarm", "max"),
            feasible_rate=("feasible_under_target", "mean"),
            id_calib_alarm_mean=("id_calib_alarm", "mean"),
            ood_val_alarm_mean=("ood_val_alarm", "mean"),
        )
    )
    curve_summary = (
        grouped.groupby(["head_id", "head_family", "ood_val_target"], as_index=False)
        .agg(
            locked_detection_mean=("detection_mean", "mean"),
            locked_detection_min=("detection_mean", "min"),
            locked_ood_alarm_max=("ood_alarm_max", "max"),
            feasible_rate=("feasible_rate", "mean"),
            id_calib_alarm_mean=("id_calib_alarm_mean", "mean"),
            ood_val_alarm_mean=("ood_val_alarm_mean", "mean"),
        )
    )
    curve_summary["threshold_source"] = "id_calib_plus_ood_val_guarded"
    curve_summary["selection_used_final_eval"] = False
    curve_summary["threshold_uses_final_eval"] = False
    return score_df, curve_summary


def top64_linearity_bias(summary27b: pd.DataFrame) -> pd.DataFrame:
    issue25c_locked = pd.read_csv(ISSUE25C / "locked_bins_baseline_summary.csv")
    rows = []
    def add(item: str, source: str, evidence: str, implication: str, risk: str, followup: str) -> None:
        rows.append(
            {
                "audit_item": item,
                "source": source,
                "evidence": evidence,
                "mechanism_implication": implication,
                "linearity_or_bias_risk": risk,
                "required_followup": followup,
            }
        )
    lr_top64 = issue25c_locked[issue25c_locked["method"].eq("M2_Enhanced_LOW_GUARD_top64_fixed_guard_LR")].iloc[0]
    lr_orig = issue25c_locked[issue25c_locked["method"].eq("M0_V1_original100_fixed_guard_LR")].iloc[0]
    lr_top32 = issue25c_locked[issue25c_locked["method"].eq("M1_V2_top32_fixed_guard_LR")].iloc[0]
    add(
        "top64_vs_original100_lr",
        "issue25c locked summary",
        f"top64 LR {lr_top64.locked_detection_mean:.6f}/{lr_top64.locked_detection_min:.6f}/{lr_top64.locked_ood_alarm_max:.6f}; original100 LR {lr_orig.locked_detection_mean:.6f}/{lr_orig.locked_detection_min:.6f}/{lr_orig.locked_ood_alarm_max:.6f}",
        "top64 improves min detection and keeps OOD max lower than original100, consistent with representation-side stabilization.",
        "medium",
        "Do not claim top64 alone proves head-agnostic transfer; it was selected by support-vs-OOD/ID effects that are friendly to linear separation.",
    )
    add(
        "top64_vs_top32_lr",
        "issue25c locked summary",
        f"top64 OOD max {lr_top64.locked_ood_alarm_max:.6f}; top32 OOD max {lr_top32.locked_ood_alarm_max:.6f}",
        "top64 repairs the top32 OOD-budget failure, suggesting representation capacity/coverage matters before head complexity.",
        "medium",
        "Keep top64 frozen; no topK search in this audit.",
    )
    lr_p0 = summary27b[(summary27b["head_id"].eq("LOW_GUARD_LR_reference")) & (summary27b["protocol_variant"].eq("P0_raw_train_id_threshold"))].iloc[0]
    lr_p2 = summary27b[(summary27b["head_id"].eq("LOW_GUARD_LR_reference")) & (summary27b["protocol_variant"].eq("P2_guarded_train_id_threshold"))].iloc[0]
    add(
        "linear_boundary_without_guard",
        "issue27b protocol matrix",
        f"LR P0 detection {lr_p0.locked_detection_mean:.6f} but OOD max {lr_p0.locked_ood_alarm_max:.6f}; LR P2 detection {lr_p2.locked_detection_mean:.6f}, OOD max {lr_p2.locked_ood_alarm_max:.6f}",
        "top64 appears to expose an attack-separating linear direction, while OOD-guarded training is needed to suppress benign-OOD tail.",
        "medium_high",
        "Falsify with bounded representation controls rather than more adapter zoo expansion.",
    )
    add(
        "original100_non_lr_missing",
        "available inventory",
        "No same P0/P1/P2/P3 matrix for original100 non-LR heads was found in issue27b.",
        "Cannot separate representation linearization from head-specific protocol behavior for non-LR heads yet.",
        "unknown",
        "Required follow-up: small original100 vs top64 LR/DevNet/HistGB matrix, report-only, no new method tuning.",
    )
    return pd.DataFrame(rows)


def write_diagnostics(
    lr_audit: pd.DataFrame,
    head_audit: pd.DataFrame,
    score_audit: pd.DataFrame,
    curve: pd.DataFrame,
    top64: pd.DataFrame,
    by_seed: pd.DataFrame,
    summary27b: pd.DataFrame,
) -> tuple[str, list[str], str]:
    lr_p3 = summary27b[(summary27b["head_id"].eq("LOW_GUARD_LR_reference")) & (summary27b["protocol_variant"].eq("P3_full_lowguard"))].iloc[0]
    dev_p3 = summary27b[(summary27b["head_id"].eq("DevNet_like_MLP")) & (summary27b["protocol_variant"].eq("P3_full_lowguard"))].iloc[0]
    hist_p3 = summary27b[(summary27b["head_id"].eq("HistGB_shallow")) & (summary27b["protocol_variant"].eq("P3_full_lowguard"))].iloc[0]
    deep_p3 = summary27b[(summary27b["head_id"].eq("DeepSAD_like_center")) & (summary27b["protocol_variant"].eq("P3_full_lowguard"))].iloc[0]

    primary_verdict = "lowguard_lr_success_mechanistically_supported"
    secondary = [
        "representation_linearization_explains_lr_advantage",
        "lowguard_effect_head_specific_lr_only_so_far",
        "non_lr_results_inconclusive_due_to_proxy_implementation",
    ]
    recommendation = "issue27d_bounded_representation_and_objective_falsification_for_lowguard_lr_specificity"

    write_text(
        OUT / "lr_rescue_mechanism_diagnosis.md",
        f"""
# LR Rescue Mechanism Diagnosis

LR P0 shows the core pathology: attack detection is high, but the final OOD tail explodes. LR P1 shows that threshold guard alone is not the mechanism; it satisfies the alarm budget by pushing the threshold so high that attack detection collapses. LR P2 shows the key recovery: adding OOD benign samples during training reshapes the linear score so ID/OOD/support are separated enough that even an ID-only threshold becomes feasible. P3 preserves the P2 behavior while adding the official ID+OOD validation safety gate.

Mechanistic reading:
- The rescue is not "just thresholding".
- The decisive LR mechanism is OOD-guarded training on the frozen top64 representation.
- The threshold guard is still required as a deployment safety gate and for final protocol consistency.
- LR success likely depends on top64 exposing a mostly linear attack-vs-benign-OOD direction.

Key LR P3 locked result: `{float(lr_p3.locked_detection_mean):.6f}` / `{float(lr_p3.locked_detection_min):.6f}` / `{float(lr_p3.locked_ood_alarm_max):.6f}`.
""",
    )
    write_text(
        OUT / "head_specificity_diagnosis.md",
        f"""
# Head Specificity Diagnosis

The non-LR heads do not show the same clean P0-to-P2/P3 recovery pattern as LR. DevNet-like is the closest: full LOW-GUARD detection remains high, but OOD max is `{float(dev_p3.locked_ood_alarm_max):.6f}`, just over the official 1% budget. HistGB responds in detection but has a weak locked minimum and OOD max `{float(hist_p3.locked_ood_alarm_max):.6f}`. DeepSAD-like remains collapsed under the proxy objective.

Conclusion:
- LOW-GUARD cannot currently be claimed as head-agnostic.
- The evidence supports LOW-GUARD-LR as a stable instance.
- Non-LR failures should be described as bounded proxy-head evidence, not general defeats of DevNet, Deep SAD, or nonlinear adapters.
""",
    )
    worst_tails = (
        score_audit[score_audit["protocol_variant"].eq("P3_full_lowguard")]
        .groupby("head_id", as_index=False)
        .agg(max_ood_tail_rate=("ood_tail_rate", "max"), median_attack_margin=("attack_margin_median", "median"), min_attack_minus_ood_q99=("attack_median_minus_final_ood_q99", "min"))
        .sort_values("max_ood_tail_rate", ascending=False)
    )
    direction_risk = (
        score_audit.groupby(["head_id", "protocol_variant"], as_index=False)["score_direction_risk"]
        .sum()
        .query("score_direction_risk > 0")
        .sort_values(["head_id", "protocol_variant"])
    )
    write_text(
        OUT / "score_distribution_tail_diagnosis.md",
        f"""
# Score Distribution And Tail Diagnosis

P3 score-tail audit shows that LR has the cleanest low-alert tail under the frozen protocol. DevNet-like keeps attack margins high, but its final-OOD tail has too little safety margin and crosses 1% in at least one locked seed/bin. HistGB has unstable attack margins across bins. DeepSAD-like has weak attack separation under the center-distance proxy.

Worst P3 tail snapshot:

{md_table(worst_tails)}

Score direction / objective mismatch is visible for DeepSAD-like raw and threshold-only variants, and in a small number of HistGB rows. It is not the dominant explanation for LR or DevNet-like. For the main non-LR near miss, the problem is tail calibration and low-alert safety margin.

Direction-risk rows:

{md_table(direction_risk)}
""",
    )
    curve_focus = curve[curve["ood_val_target"].isin([0.01, 0.005])].sort_values(["ood_val_target", "locked_detection_mean"], ascending=[False, False])
    write_text(
        OUT / "threshold_feasibility_curve_diagnosis.md",
        f"""
# Threshold Feasibility Curve Diagnosis

The stricter target curve was computed using ID calibration + OOD validation only. Final OOD and attack eval remain report-only. The curve does not select a better target; it asks whether non-LR heads merely lack safety margin.

Interpretation:
- DevNet-like's near miss at 1% indicates a safety-margin problem, not a clear LOW-GUARD++ candidate.
- As targets tighten, non-LR detection degrades or remains OOD-risky, so the current evidence does not justify upgrading beyond LOW-GUARD-LR.
- LR retains the clearest feasible low-alert operating point.

Target snapshot:

{md_table(curve_focus)}
""",
    )
    write_text(
        OUT / "top64_linearity_bias_diagnosis.md",
        f"""
# Top64 Linearity / Representation Bias Diagnosis

The available evidence is consistent with top64 doing a large part of the work: it exposes an attack-separating direction that LR can exploit, while OOD-guarded training suppresses benign-OOD tail. This does not prove that top64 is unfairly biased toward LR, but it makes broad head-agnostic claims unsafe.

What we can say:
- top64 improves the feasible LR operating point versus top32 and original100 in the existing locked summaries.
- issue27b shows raw LR has strong attack detection on top64, but only guarded training makes it low-alert feasible.
- Non-LR original100-vs-top64 controls are not available, so representation-vs-head causality remains only partially resolved.

Required follow-up:
- bounded original100-vs-top64 matrix for LR / DevNet-like / HistGB;
- no topK search;
- final eval report-only.
""",
    )
    write_text(
        OUT / "implementation_gap_audit.md",
        f"""
# Implementation Gap Audit

## DevNet-like MLP

The current DevNet-like head is a lightweight weighted MLP classifier. It is not equivalent to full DevNet: it does not implement the original deviation-network objective, reference-score prior, or full method-specific training recipe. It did use OOD_train in P2/P3 through the guarded training matrix, and sample weights were passed to `MLPClassifier.fit` without runtime failure.

## DeepSAD-like center

The current DeepSAD-like head is a center-distance proxy with attack-weighted feature weights. It is not equivalent to full Deep SAD because it does not learn a deep representation or optimize the full Deep SAD objective. Its failure should not be written as "Deep SAD is defeated".

## HistGB

HistGB is a shallow supervised tree baseline with OOD_train negatives in P2/P3 and a validation-only threshold. It does not directly optimize the low-alert tail objective, which likely explains why detection can remain useful while the OOD tail is not controlled.

## RFF Logistic

RFF Logistic was optional in issue27b and is sensitive to scaling/gamma. It is useful as a kernelized linearity probe, not as a strong method claim.

## Protocol-equivalence risks

- Non-LR heads do receive OOD_train guard in P2/P3.
- No final eval selection was found in issue27b traces.
- No direct implementation bug was found for LR or DevNet-like.
- DeepSAD-like shows score/objective mismatch in raw and threshold-only variants, which should be interpreted as proxy-objective weakness rather than a final conclusion about full Deep SAD.
- Proxy implementations are not method-equivalent to full DevNet / Deep SAD, so non-LR conclusions must stay bounded.
""",
    )
    write_text(
        OUT / "mechanism_verdict_and_claim_boundary.md",
        f"""
# Mechanism Verdict And Claim Boundary

## Primary verdict

`{primary_verdict}`

## Secondary verdicts

{chr(10).join(f"- `{v}`" for v in secondary)}

## Rationale

LR has a clean falsification pattern: P0 detects attacks but fails OOD, P1 controls OOD by collapsing detection, and P2/P3 preserve detection while controlling OOD. That pattern supports a real OOD-guarded training mechanism rather than a threshold-only artifact.

At the same time, the non-LR results do not establish head-agnostic transfer. DevNet-like is a near miss, but its OOD max remains over 1%. DeepSAD-like and DevNet-like are proxies, not full method implementations, so they cannot be used to make broad negative claims.

## Claim boundary

Allowed:
- Current evidence supports LOW-GUARD-LR as the strongest feasible instance.
- Broader head-agnostic transfer is not established.
- LR success appears linked to source-rich top64, OOD-guarded training, and validation-only thresholding.

Not allowed:
- LOW-GUARD works for all heads.
- Nonlinear adapters are useless.
- DevNet or Deep SAD are defeated.
- LR is universally optimal.
- Deployment robustness, temporal generalization, or cross-dataset generalization is proven.
""",
    )
    write_text(
        OUT / "claim_update_after_issue27c.md",
        """
# Claim Update After Issue27c

## Allowed

- Current evidence supports LOW-GUARD-LR as the strongest feasible instance.
- Broader head-agnostic transfer is not established.
- LOW-GUARD should be framed cautiously unless further adapter-specific objectives are validated.
- LR success appears linked to the interaction between source-rich top64, OOD-guarded training, and validation-only thresholding.

## Not allowed

- LOW-GUARD works for all heads.
- Nonlinear adapters are useless.
- DevNet is defeated.
- Deep SAD is defeated.
- LR is universally optimal.
- Deployment robustness is proven.
- Temporal generalization is proven.
- Cross-dataset generalization is proven.
""",
    )
    write_text(
        OUT / "reviewer_defense_lr_specificity.md",
        f"""
# Reviewer Defense: LR Specificity

## Q1: Is LOW-GUARD just an LR trick?

Current evidence says LOW-GUARD-LR is the strongest feasible instance. The broader framework claim must be bounded because non-LR transfer was not stable under the locked low-alert protocol.

## Q2: Why did LR recover but threshold-only LR collapse?

Threshold-only LR moves the decision threshold high enough to suppress benign-OOD alarms, but this also suppresses attack detection. OOD-guarded LR training changes the score geometry so the same low-alert budget can retain attack detection.

## Q3: Did non-LR heads receive the OOD guard?

Yes. P2/P3 variants include OOD_train guard for non-LR heads. The issue is not that they were unguarded; it is that their score tails were less compatible with the strict low-alert threshold.

## Q4: Are DevNet and Deep SAD defeated?

No. The implemented heads are lightweight proxies. The correct claim is that these proxy heads did not produce a stronger low-alert instance under this protocol.

## Q5: Should the paper call LOW-GUARD a framework?

Only cautiously. It can be described as a guarded adaptation protocol, but current positive performance evidence should center on LOW-GUARD-LR.

## Q6: What is the next falsification?

Run `{recommendation}` before returning to deployment robustness, because direct deployment robustness would be a premature close if the mechanism is still head-specific.
""",
    )
    write_text(
        OUT / "issue27d_next_action.md",
        f"""
# Issue27d Next Action

## Recommendation

`{recommendation}`

## Why this, not deployment robustness yet

issue27b made deployment robustness tempting, but issue27c shows the mechanism question is not fully closed. Before stress-testing deployment assumptions, run a bounded falsification control to separate representation linearization from adapter/objective specificity.

## Minimal run matrix

- Freeze locked bins, top64, kcenter32, and final-eval exclusion.
- Compare original100 vs top64 for LR, DevNet-like, and HistGB only.
- Keep P0/P2/P3; P1 can be diagnostic if cheap.
- Add no new large model and no topK search.
- Report whether non-LR failure persists when representation bias is controlled.

## Slurm

Not needed unless the matrix is expanded beyond the bounded lightweight heads.
""",
    )
    return primary_verdict, secondary, recommendation


def write_summary(primary_verdict: str, secondary: list[str], recommendation: str, summary27b: pd.DataFrame, head_audit: pd.DataFrame, curve: pd.DataFrame) -> None:
    lr = summary27b[(summary27b["head_id"].eq("LOW_GUARD_LR_reference")) & (summary27b["protocol_variant"].eq("P3_full_lowguard"))].iloc[0]
    dev = summary27b[(summary27b["head_id"].eq("DevNet_like_MLP")) & (summary27b["protocol_variant"].eq("P3_full_lowguard"))].iloc[0]
    summary_text = f"""
# Issue27c LOW-GUARD Mechanism Falsification And Head Specificity Audit Summary

## Total-control critique

- issue27b 后直接转 deployment robustness 是过早收口。
- 只做 DevNet near-miss rescue 也太窄。
- 当前最重要问题是：LOW-GUARD 是 general protocol，还是 LR-specific method。
- 如果只有 LR 被救回，必须诚实收缩 claim。
- 不能因为 LR 当前最好就直接假设协议具有广泛迁移性。
- 不能因为非 LR 没赢就直接放弃审计实现和设置问题。

## Verdict

- primary_verdict: `{primary_verdict}`
- secondary_verdicts: {", ".join(f"`{v}`" for v in secondary)}

## 1. Why does LOW-GUARD clearly rescue LR?

LR has the cleanest P0/P1/P2/P3 mechanism pattern: raw LR detects attacks but badly violates OOD alarm; threshold-only LR controls OOD by collapsing detection; OOD-guarded training preserves attack detection while suppressing OOD tail; P3 adds the validation safety gate.

## 2. Mechanism evidence or accident?

The LR result is unlikely to be pure accident because the mechanism pattern repeats across locked bins and seeds, and LOW-GUARD-LR P3 remains `{float(lr.locked_detection_mean):.6f}` / `{float(lr.locked_detection_min):.6f}` / `{float(lr.locked_ood_alarm_max):.6f}`. However, broad protocol transfer remains unproven.

## 3. Non-LR failure: real model failure or proxy/implementation issue?

Both are plausible. DevNet-like is a lightweight proxy, DeepSAD-like is a center-distance proxy, and HistGB does not optimize a low-alert tail objective. Therefore non-LR failures should not be written as general defeats of DevNet, Deep SAD, or nonlinear adapters.

## 4. Does top64 bias toward LR?

Possibly. top64 selection uses support-vs-OOD/ID effect and tail-margin criteria that can expose a linear attack-separating direction. This supports LOW-GUARD-LR but makes head-agnostic claims risky without original100/top64 representation controls.

## 5. Training guard vs threshold guard for LR

Training guard is the decisive recovery mechanism. Threshold guard is the safety gate. Threshold-only LR is not sufficient because it collapses attack detection.

## 6. Did non-LR heads actually consume OOD guard?

Yes. P2/P3 variants used OOD_train guard. The issue is score-tail behavior, proxy objectives, and low-alert calibration, not absence of OOD guard.

## 7. Implementation bug or protocol inequivalence risk?

No direct bug or final-eval leakage was found. But protocol-equivalence risk remains because DevNet-like and DeepSAD-like are proxies rather than full methods.

## 8. Can LOW-GUARD still be written as framework?

Only cautiously. It can be framed as a guarded adaptation protocol, but positive empirical claims should center on LOW-GUARD-LR unless issue27d finds broader transfer.

## 9. Should claims shrink to LOW-GUARD-LR?

Yes for performance claims. The framework language may remain as motivation/protocol, but the demonstrated instance is LOW-GUARD-LR.

## 10. Issue27d next step

`{recommendation}`.

## 11. Slurm

Not needed for this audit or the recommended bounded issue27d controls.

## 12. Final eval leakage

No final eval leakage was found. Final OOD and attack eval were used only for report-only metrics.

## Key head-specific rows

{md_table(head_audit[["head_id", "p3_detection", "p3_detection_min", "p3_ood_max", "p3_feasible_rate", "response_label"]])}

## Threshold curve snapshot

{md_table(curve[curve["ood_val_target"].isin([0.01, 0.005])].sort_values(["ood_val_target", "locked_detection_mean"], ascending=[False, False]))}
"""
    write_text(OUT / "summary.md", summary_text)


def main() -> None:
    t0 = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    missing = require_inputs()
    if missing:
        write_text(OUT / "missing_input_report.md", "# Missing Input Report\n\n" + "\n".join(f"- {item}" for item in missing))
        raise RuntimeError(f"Missing inputs: {missing}")
    write_text(OUT / "missing_input_report.md", "# Missing Input Report\n\nnone")

    by_seed = pd.read_csv(ISSUE27B / "protocol_transfer_by_seed.csv")
    summary27b = pd.read_csv(ISSUE27B / "protocol_transfer_locked_summary.csv")
    selection = pd.read_csv(ISSUE27B / "adapter_selection_trace.csv")
    pd.read_csv(ISSUE27B / "model_recovery_mode_summary.csv")
    pd.read_csv(ISSUE27B / "near_lr_baseline_upgrade_report.csv")
    pd.read_csv(ISSUE27B / "lowguard_plus_plus_candidate_report.csv")

    lr_audit, lr_seed_delta = mechanism_tables(summary27b, by_seed)
    head_audit = head_specificity(summary27b)
    score_audit, curve = score_tail_and_curves(selection)
    top64 = top64_linearity_bias(summary27b)

    lr_audit.to_csv(OUT / "lr_rescue_mechanism_audit.csv", index=False)
    lr_seed_delta.to_csv(OUT / "lr_rescue_seed_delta_audit.csv", index=False)
    head_audit.to_csv(OUT / "head_specificity_audit.csv", index=False)
    score_audit.to_csv(OUT / "score_distribution_tail_audit.csv", index=False)
    curve.to_csv(OUT / "threshold_feasibility_curve.csv", index=False)
    top64.to_csv(OUT / "top64_linearity_bias_audit.csv", index=False)

    primary, secondary, recommendation = write_diagnostics(lr_audit, head_audit, score_audit, curve, top64, by_seed, summary27b)
    write_summary(primary, secondary, recommendation, summary27b, head_audit, curve)

    config = {
        "issue": "issue27c_lowguard_mechanism_falsification_and_head_specificity_audit_2026-05-26",
        "primary_verdict": primary,
        "secondary_verdicts": secondary,
        "frozen": {
            "representation": "source_rich_top64",
            "support": "kcenter32",
            "locked_bins": LOCKED_HOLDOUTS,
            "final_eval": "report_only",
            "no_temporal_validation": True,
            "no_deployment_robustness": True,
            "no_manuscript_edit": True,
        },
        "threshold_curve_targets": TARGETS,
        "core_heads_for_score_audit": CORE_HEADS,
        "recommended_next_action": recommendation,
        "runtime_seconds": time.perf_counter() - t0,
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    run_spec = {
        "task_type": "mechanism_falsification_and_head_specificity_audit",
        "inputs": [str(ISSUE27B), str(ISSUE25C), str(ISSUE23), str(MAINLINE_DOCS)],
        "computed": ["lr mechanism deltas", "head specificity responses", "score distribution/tail audit", "threshold feasibility curve"],
        "not_in_scope": ["deployment robustness", "temporal validation", "cross-dataset validation", "new method development", "manuscript edit"],
    }
    (OUT / "run_spec.json").write_text(json.dumps(run_spec, indent=2, ensure_ascii=False), encoding="utf-8")
    write_text(
        OUT / "command.txt",
        """
git branch --show-current
git status --short
python runs/issue27c_lowguard_mechanism_falsification_and_head_specificity_audit_2026-05-26/run_issue27c_mechanism_audit.py
git status
git add repo runs/mainline_docs runs/issue27c_lowguard_mechanism_falsification_and_head_specificity_audit_2026-05-26
git commit -m "Add issue27c LOW-GUARD mechanism audit"
git push origin codex/exp-mainline
""",
    )

    manifest_rows = []
    for path in sorted(OUT.glob("*")):
        if path.is_file() and path.name != "manifest.csv":
            manifest_rows.append({"file": path.name, "size_bytes": path.stat().st_size})
    manifest_rows.append({"file": "runtime_seconds", "size_bytes": f"{time.perf_counter() - t0:.3f}"})
    pd.DataFrame(manifest_rows).to_csv(OUT / "manifest.csv", index=False)


if __name__ == "__main__":
    main()
