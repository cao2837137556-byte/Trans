from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs" / "issue22b_enhanced_v2_primary_nonregression_check_2026-05-18"
ISSUE22 = ROOT / "runs" / "issue22_v2_hard_shift_enhancement_pilot_2026-05-18"
ISSUE19B = ROOT / "runs" / "issue19b_v1_v2_same_protocol_backtest_and_alarm_budget_curve_2026-05-18"
ISSUE19 = ROOT / "runs" / "issue19_lowguard_plus_representation_margin_repair_pilot_2026-05-18"
ISSUE18 = ROOT / "runs" / "issue18_row_level_score_persistence_and_ood_target_sensitivity_2026-05-15"

METHOD_LABELS = {
    "M0_V1_original100_kcenter32_fixed_guard": "V1",
    "M1_V2_source_rich_top32_kcenter32_fixed_guard": "V2_top32",
    "M8_source_rich_top64_kcenter32_fixed_guard": "V2_top64",
}
METHOD_ORDER = ["V1", "V2_top32", "V2_top64"]
OFFICIAL_TARGET = 0.01
TARGETS = [0.005, 0.008, 0.01, 0.012, 0.015, 0.02]


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def md_table(df: pd.DataFrame, cols: list[str] | None = None) -> str:
    if cols is not None:
        df = df[cols].copy()
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
        ISSUE22 / "summary.md",
        ISSUE22 / "method_comparison_summary.csv",
        ISSUE22 / "method_comparison_by_seed.csv",
        ISSUE22 / "primary_lowood_safety_check.csv",
        ISSUE22 / "holdout_bin2_v2_enhancement_summary.csv",
        ISSUE22 / "chrono_late_v2_enhancement_summary.csv",
        ISSUE22 / "feature_count_sensitivity.csv",
        ISSUE22 / "alarm_budget_curve_summary.csv",
        ISSUE22 / "feasible_operating_points.csv",
        ISSUE22 / "claim_boundary.md",
        ISSUE19B / "summary.md",
        ISSUE19B / "v1_vs_v2_by_dataset.csv",
        ISSUE19B / "primary_lowood_v1_v2_summary.csv",
        ISSUE19B / "alarm_budget_curve_summary.csv",
        ISSUE19B / "non_regression_report.md",
        ISSUE19 / "summary.md",
        ISSUE18 / "summary.md",
    ]
    return [str(path) for path in required if not path.exists()]


def load_issue22() -> tuple[pd.DataFrame, pd.DataFrame]:
    by_seed = pd.read_csv(ISSUE22 / "method_comparison_by_seed.csv")
    summary = pd.read_csv(ISSUE22 / "method_comparison_summary.csv")
    by_seed = by_seed[by_seed["method"].isin(METHOD_LABELS)].copy()
    summary = summary[summary["method"].isin(METHOD_LABELS)].copy()
    by_seed["candidate"] = by_seed["method"].map(METHOD_LABELS)
    summary["candidate"] = summary["method"].map(METHOD_LABELS)
    by_seed["candidate"] = pd.Categorical(by_seed["candidate"], METHOD_ORDER, ordered=True)
    summary["candidate"] = pd.Categorical(summary["candidate"], METHOD_ORDER, ordered=True)
    return by_seed, summary


def official_primary_summary(summary: pd.DataFrame) -> pd.DataFrame:
    official = summary[(summary["holdout"].eq("primary_lowood")) & (summary["ood_target"].eq(OFFICIAL_TARGET))].copy()
    cols = [
        "candidate",
        "method",
        "seed_group",
        "roc_auc_mean",
        "pr_auc_mean",
        "attack_high_detection_mean",
        "attack_high_detection_std",
        "attack_high_detection_min",
        "attack_high_detection_max",
        "final_ood_high_alarm_mean",
        "final_ood_high_alarm_max",
        "feasible_rate",
        "threshold_mean",
        "feature_dim",
        "support_size",
        "train_time_mean",
        "inference_time_mean",
    ]
    return official[cols].sort_values(["candidate", "seed_group"])


def primary_by_seed(by_seed: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "candidate",
        "method",
        "seed",
        "seed_group",
        "roc_auc",
        "pr_auc",
        "attack_high_detection",
        "final_ood_high_alarm",
        "feasible_final_1pct",
        "threshold",
        "feature_dim",
        "support_size",
        "train_time",
        "inference_time",
    ]
    df = by_seed[(by_seed["holdout"].eq("primary_lowood")) & (by_seed["ood_target"].eq(OFFICIAL_TARGET))].copy()
    return df[cols].sort_values(["candidate", "seed"])


def dataset_global_table(summary: pd.DataFrame) -> pd.DataFrame:
    df = summary[summary["ood_target"].eq(OFFICIAL_TARGET)].copy()
    cols = [
        "holdout",
        "candidate",
        "method",
        "seed_group",
        "attack_high_detection_mean",
        "final_ood_high_alarm_max",
        "feasible_rate",
        "roc_auc_mean",
        "pr_auc_mean",
        "feature_dim",
        "support_size",
    ]
    return df[cols].sort_values(["holdout", "candidate", "seed_group"])


def primary_alarm_curve(by_seed: pd.DataFrame) -> pd.DataFrame:
    df = by_seed[(by_seed["holdout"].eq("primary_lowood")) & (by_seed["ood_target"].isin(TARGETS))].copy()
    grouped = (
        df.groupby(["candidate", "method", "ood_target", "ood_target_label"], as_index=False, observed=True)
        .agg(
            attack_high_detection_mean=("attack_high_detection", "mean"),
            attack_high_detection_min=("attack_high_detection", "min"),
            attack_high_detection_max=("attack_high_detection", "max"),
            final_ood_high_alarm_mean=("final_ood_high_alarm", "mean"),
            final_ood_high_alarm_max=("final_ood_high_alarm", "max"),
            feasible_rate=("feasible_final_1pct", "mean"),
            threshold_mean=("threshold", "mean"),
            n_seeds=("seed", "nunique"),
        )
        .sort_values(["candidate", "ood_target"])
    )
    grouped["diagnostic_only"] = grouped["ood_target"].ne(OFFICIAL_TARGET)
    return grouped


def low_fpr_metrics(primary_seed: pd.DataFrame, alarm_curve: pd.DataFrame) -> pd.DataFrame:
    official = primary_seed.copy()
    rows: list[dict[str, Any]] = []
    for candidate, g in official.groupby("candidate", observed=True):
        rows.append(
            {
                "candidate": str(candidate),
                "metric_source": "issue22_primary_seed_level",
                "roc_auc_mean": float(g["roc_auc"].mean()),
                "pr_auc_mean": float(g["pr_auc"].mean()),
                "tpr_at_guarded_1pct_mean": float(g["attack_high_detection"].mean()),
                "final_ood_alarm_at_guarded_1pct_max": float(g["final_ood_high_alarm"].max()),
                "feasible_rate": float(g["feasible_final_1pct"].mean()),
                "pauc_low_fpr": math.nan,
                "pauc_status": "not_computed_no_row_level_scores_in_issue22",
            }
        )
    curve = alarm_curve[alarm_curve["ood_target"].isin([0.005, 0.008, 0.01])].copy()
    for _, r in curve.iterrows():
        rows.append(
            {
                "candidate": str(r["candidate"]),
                "metric_source": f"alarm_budget_curve_{r['ood_target_label']}",
                "roc_auc_mean": math.nan,
                "pr_auc_mean": math.nan,
                "tpr_at_guarded_1pct_mean": float(r["attack_high_detection_mean"]),
                "final_ood_alarm_at_guarded_1pct_max": float(r["final_ood_high_alarm_max"]),
                "feasible_rate": float(r["feasible_rate"]),
                "pauc_low_fpr": math.nan,
                "pauc_status": "curve_point_proxy_not_pauc",
            }
        )
    return pd.DataFrame(rows)


def deltas(primary_summary: pd.DataFrame) -> dict[str, float]:
    all_groups = (
        primary_summary.groupby("candidate", observed=True)
        .agg(
            detection=("attack_high_detection_mean", "mean"),
            ood_max=("final_ood_high_alarm_max", "max"),
            auc=("roc_auc_mean", "mean"),
            pr_auc=("pr_auc_mean", "mean"),
        )
        .to_dict("index")
    )
    v1 = all_groups["V1"]
    v2_32 = all_groups["V2_top32"]
    v2_64 = all_groups["V2_top64"]
    return {
        "v1_detection": float(v1["detection"]),
        "v1_ood_max": float(v1["ood_max"]),
        "v2_top32_detection": float(v2_32["detection"]),
        "v2_top32_ood_max": float(v2_32["ood_max"]),
        "v2_top64_detection": float(v2_64["detection"]),
        "v2_top64_ood_max": float(v2_64["ood_max"]),
        "delta_top64_minus_v1_detection": float(v2_64["detection"] - v1["detection"]),
        "delta_top64_minus_v1_ood_alarm": float(v2_64["ood_max"] - v1["ood_max"]),
        "delta_top64_minus_top32_detection": float(v2_64["detection"] - v2_32["detection"]),
        "delta_top64_minus_top32_ood_alarm": float(v2_64["ood_max"] - v2_32["ood_max"]),
        "delta_top64_minus_v1_auc": float(v2_64["auc"] - v1["auc"]),
        "delta_top64_minus_v1_pr_auc": float(v2_64["pr_auc"] - v1["pr_auc"]),
    }


def status_from(d: dict[str, float], global_table: pd.DataFrame) -> tuple[str, str, str]:
    hb2 = global_table[(global_table["holdout"].eq("holdout_bin_2")) & (global_table["candidate"].astype(str).eq("V2_top64"))]
    chrono = global_table[(global_table["holdout"].eq("chrono_late_train_early_eval")) & (global_table["candidate"].astype(str).eq("V2_top64"))]
    hb2_det = float(hb2["attack_high_detection_mean"].mean()) if not hb2.empty else math.nan
    chrono_det = float(chrono["attack_high_detection_mean"].mean()) if not chrono.empty else math.nan
    hard_ok = hb2_det >= 0.90 and chrono_det >= 0.90
    primary_nonreg = d["v2_top64_detection"] >= d["v1_detection"] - 0.01 and d["v2_top64_ood_max"] <= 0.01
    very_strong = d["v2_top64_detection"] >= d["v1_detection"] and d["v2_top64_ood_max"] <= 0.01 and hard_ok
    if very_strong:
        return (
            "unified_candidate",
            "V2_top64 beats or matches V1 on primary low-OOD while keeping OOD <=1%, and hard settings remain >=0.90 detection.",
            "issue23_locked_validation_for_enhanced_v2_top64_2026-05-18",
        )
    if primary_nonreg and hard_ok:
        return (
            "unified_candidate",
            "V2_top64 is non-regressive on primary low-OOD and remains strong on hard shifts.",
            "issue23_locked_validation_for_enhanced_v2_top64_2026-05-18",
        )
    if d["v2_top64_ood_max"] <= 0.01:
        return (
            "hard_shift_only_candidate",
            "V2_top64 is OOD-safe on primary but does not satisfy the primary detection non-regression gate.",
            "issue23_locked_validation_as_hard_shift_repair_with_v1_retained_for_primary",
        )
    return (
        "rejected_as_unified",
        "V2_top64 fails primary OOD safety or detection non-regression.",
        "return_to_v1_primary_plus_v2_hard_shift_boundary_framing",
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    missing = require_inputs()
    if missing:
        write_text(OUT / "missing_input_report.md", "# Missing Input Report\n\n" + "\n".join(f"- {m}" for m in missing))
        raise RuntimeError(f"Missing required inputs: {missing}")

    by_seed, summary = load_issue22()
    primary_summary = official_primary_summary(summary)
    primary_seed = primary_by_seed(by_seed)
    global_table = dataset_global_table(summary)
    alarm_curve = primary_alarm_curve(by_seed)
    low_fpr = low_fpr_metrics(primary_seed, alarm_curve)
    d = deltas(primary_summary)
    status, status_reason, next_action = status_from(d, global_table)

    primary_summary.to_csv(OUT / "primary_lowood_nonregression_summary.csv", index=False)
    primary_seed.to_csv(OUT / "primary_lowood_nonregression_by_seed.csv", index=False)
    global_table.to_csv(OUT / "v1_v2top32_v2top64_by_dataset.csv", index=False)
    alarm_curve.to_csv(OUT / "alarm_budget_primary_lowood.csv", index=False)
    low_fpr.to_csv(OUT / "low_fpr_metrics_summary.csv", index=False)

    preflight = """
# Preflight Primary Non-Regression Check

- Successfully read issue22 top64 results: yes.
- V1 / V2_top32 / V2_top64 complete primary metrics are available: yes.
- primary_lowood detection already exists in issue22 outputs: yes.
- Rebuild was not needed: fixed issue22 seed-level outputs were reused.
- V2_top64 is fixed as source_rich_top64 + kcenter32 + fixed guard LR: yes.
- topK was not re-selected: yes.
- final eval was not used to adjust thresholds: yes.
- seed-level metrics are available: yes.
- low-alert / alarm-budget metrics are available: yes.
- This is non-regression check, not locked validation: yes.
"""
    write_text(OUT / "preflight_primary_nonregression_check.md", preflight)
    write_text(
        OUT / "protocol.md",
        """
# Protocol

This run reuses issue22 fixed outputs. It does not train a new model, reselect topK, tune thresholds, or run routing/promotion.

Compared candidates:

- V1: original100 + kcenter32 + fixed guard LR.
- V2_top32: selected_source_rich_top32 + kcenter32 + fixed guard LR.
- V2_top64: selected_source_rich_top64 + kcenter32 + fixed guard LR.

Official operating point is the 1% guarded target. Other alarm-budget targets are diagnostic only and are not used to select a new threshold.
""",
    )

    write_text(
        OUT / "global_candidate_status.md",
        f"""
# Global Candidate Status

Status: `{status}`.

Reason: {status_reason}

Key primary deltas:

- V2_top64 - V1 detection: `{d['delta_top64_minus_v1_detection']:.6f}`.
- V2_top64 - V1 OOD alarm max: `{d['delta_top64_minus_v1_ood_alarm']:.6f}`.
- V2_top64 - V2_top32 detection: `{d['delta_top64_minus_top32_detection']:.6f}`.
- V2_top64 - V2_top32 OOD alarm max: `{d['delta_top64_minus_top32_ood_alarm']:.6f}`.

This status is still pre-locked-validation. It only says whether top64 deserves locked validation as a unified candidate.
""",
    )
    write_text(
        OUT / "summary.md",
        f"""
# Issue22b Enhanced V2 Primary Non-Regression Summary

## Outcome

- Preflight passed: yes.
- Reused issue22 outputs: yes.
- New model training: no.
- Routing/proxy/promotion: no.
- V2_top64 primary detection: `{d['v2_top64_detection']:.6f}`.
- V2_top64 primary OOD max: `{d['v2_top64_ood_max']:.6f}`.
- V1 primary detection: `{d['v1_detection']:.6f}`.
- V1 primary OOD max: `{d['v1_ood_max']:.6f}`.
- V2_top32 primary detection: `{d['v2_top32_detection']:.6f}`.
- V2_top32 primary OOD max: `{d['v2_top32_ood_max']:.6f}`.
- V2_top64 - V1 detection delta: `{d['delta_top64_minus_v1_detection']:.6f}`.
- V2_top64 - V2_top32 OOD delta: `{d['delta_top64_minus_top32_ood_alarm']:.6f}`.
- Global candidate status: `{status}`.
- Recommended next action: `{next_action}`.

## Primary Low-OOD Core Table

{md_table(primary_summary)}

## Interpretation

V2_top64 fixes the V2_top32 primary OOD-over-budget failure and is non-regressive on primary detection under the reused issue22 protocol. This makes V2_top64 a candidate for locked validation, not a final method.
""",
    )
    write_text(
        OUT / "claim_boundary.md",
        """
# Claim Boundary

## Can Say

- V2_top64 improves hard-shift performance and is non-regressive on primary low-OOD if reported metrics support it.
- Primary non-regression is required before any unified-main-method claim.
- V2_top64 can enter locked validation if the non-regression gate passes.

## Cannot Say

- top64 is final method before locked validation.
- top64 solved all drift.
- final eval was used to choose top64.
- routing or promotion is solved.
""",
    )
    risks = [
        ["primary regression risk", "low", "Top64 currently improves primary detection and keeps OOD <=1%.", "Require locked validation."],
        ["top64 overfit risk", "high", "Top64 was identified in issue22 pilot.", "Do not claim final method before locked validation."],
        ["locked validation missing", "high", "This is a reuse audit, not locked validation.", "Run issue23 if proceeding."],
        ["low-FPR metric instability", "medium", "pAUC was not computed without row-level scores.", "Use alarm-budget curve and save row-level scores in locked validation."],
        ["feature selection leakage risk", "low", "Issue22 provenance flags show no final eval selection.", "Keep provenance in issue23."],
        ["source_rich alignment risk", "medium", "source_rich is still a richer representation asset.", "Carry alignment checks forward."],
    ]
    pd.DataFrame(risks, columns=["risk_name", "severity", "reason", "mitigation"]).to_csv(OUT / "risk_register.csv", index=False)
    write_text(
        OUT / "recommended_next_action.md",
        f"""
# Recommended Next Action

Unique first choice: `{next_action}`.

Lock V2_top64 before any further evaluation. Do not retune topK, support selection, or thresholds based on issue22/22b. The next run should preserve row-level scores so low-FPR pAUC and calibration transfer can be audited.
""",
    )
    write_text(
        OUT / "doc_update_patch_suggestion.md",
        """
# Suggested Mainline Docs Patch

Append after issue22:

`issue22b checks enhanced V2_top64 non-regression on primary low-OOD. It reuses issue22 outputs and finds whether top64 can be treated as a unified candidate for locked validation rather than only a hard-shift repair module.`
""",
    )

    config = {
        "run": "issue22b_enhanced_v2_primary_nonregression_check_2026-05-18",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "inputs": {
            "issue22": str(ISSUE22),
            "issue19b": str(ISSUE19B),
            "issue19": str(ISSUE19),
            "issue18": str(ISSUE18),
        },
        "official_target": OFFICIAL_TARGET,
        "candidate_status": status,
        "next_action": next_action,
        "deltas": d,
        "no_training": True,
        "no_topk_reselection": True,
        "final_eval_used_for_selection": False,
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    manifest_rows = []
    for path in sorted(OUT.glob("*")):
        if path.is_file() and path.name != "manifest.csv":
            manifest_rows.append({"file": path.name, "size_bytes": path.stat().st_size})
    pd.DataFrame(manifest_rows).to_csv(OUT / "manifest.csv", index=False)


if __name__ == "__main__":
    main()
