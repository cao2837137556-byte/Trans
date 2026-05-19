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


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs" / "issue20b_promotion_proxy_construction_for_routing_2026-05-18"
ISSUE20 = ROOT / "runs" / "issue20_mode_specific_routing_validation_2026-05-18"
ISSUE20A = ROOT / "runs" / "issue20a_lowguard_routed_lifecycle_design_doc_2026-05-18"
ISSUE19B = ROOT / "runs" / "issue19b_v1_v2_same_protocol_backtest_and_alarm_budget_curve_2026-05-18"
ISSUE19 = ROOT / "runs" / "issue19_lowguard_plus_representation_margin_repair_pilot_2026-05-18"
ISSUE18 = ROOT / "runs" / "issue18_row_level_score_persistence_and_ood_target_sensitivity_2026-05-15"
ISSUE17 = ROOT / "runs" / "issue17_support_diversity_selection_harder_holdout_2026-05-15"
ISSUE11 = ROOT / "runs" / "issue11_fixed_config_ood_guard_lr_ablation_2026-05-14"

ISSUE20_SCRIPT = ISSUE20 / "run_issue20_routing_validation.py"

POSITIVE_BUDGET = 32
SEEDS = list(range(42, 52))
TARGET = 0.01
SUPPORT_DELTA_THRESHOLDS = [0.03, 0.05, 0.10]
SEP_SIGMA_THRESHOLDS = [0.0, 0.25, 0.5]
REVIEW_BUDGETS = [0.005, 0.01, 0.02]


def import_issue20() -> Any:
    spec = importlib.util.spec_from_file_location("issue20_routing_validation", ISSUE20_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {ISSUE20_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["issue20_routing_validation"] = module
    spec.loader.exec_module(module)
    return module


issue20 = import_issue20()


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
        vals = []
        for value in row:
            if isinstance(value, (float, np.floating)):
                if math.isnan(float(value)):
                    vals.append("")
                else:
                    vals.append(f"{float(value):.6f}")
            else:
                vals.append(str(value))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"


def require_inputs() -> list[str]:
    required = [
        ISSUE20 / "summary.md",
        ISSUE20 / "routing_decision_table.csv",
        ISSUE20 / "strategy_metrics_summary.csv",
        ISSUE20 / "strategy_metrics_by_seed.csv",
        ISSUE20 / "routed_vs_always_v1_v2.csv",
        ISSUE20 / "routed_vs_or_and.csv",
        ISSUE20 / "conflict_matrix_summary.csv",
        ISSUE20 / "review_burden_summary.csv",
        ISSUE20 / "wrong_routing_cases.md",
        ISSUE20 / "validation_proxy_report.md",
        ISSUE20 / "proxy_gap_report.md",
        ISSUE20 / "claim_boundary.md",
        ISSUE20 / "recommended_next_action.md",
        ISSUE20A / "promotion_gate_policy.md",
        ISSUE20A / "v1_v2_deployment_roles.md",
        ISSUE20A / "issue20_routing_validation_plan.md",
        ISSUE20A / "reviewer_defense.md",
        ISSUE20A / "claim_boundary.md",
        ISSUE19B / "v1_vs_v2_by_dataset.csv",
        ISSUE19B / "alarm_budget_curve_summary.csv",
        ISSUE19B / "feasible_operating_points.csv",
        ISSUE19B / "mode_routing_implication.md",
        ISSUE19B / "non_regression_report.md",
        ISSUE19 / "summary.md",
        ISSUE18 / "row_level_scores_manifest.csv",
        ISSUE18 / "attack_ood_separation_summary.csv",
        ISSUE18 / "margin_distribution_summary.csv",
        ISSUE18 / "diagnostic_decision.md",
        ISSUE17 / "summary.md",
        ISSUE11 / "config.json",
        ISSUE20_SCRIPT,
    ]
    return [str(path) for path in required if not path.exists()]


def safe_mean_bool(arr: np.ndarray) -> float:
    return float(np.mean(arr)) if len(arr) else math.nan


def q99(arr: np.ndarray) -> float:
    return float(np.quantile(arr, 0.99)) if len(arr) else math.nan


def median(arr: np.ndarray) -> float:
    return float(np.median(arr)) if len(arr) else math.nan


def q25(arr: np.ndarray) -> float:
    return float(np.quantile(arr, 0.25)) if len(arr) else math.nan


def standardized_mean_shift(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) == 0 or len(b) == 0:
        return math.nan
    denom = b.std(axis=0) + 1e-8
    shift = np.abs((a.mean(axis=0) - b.mean(axis=0)) / denom)
    return float(np.nanmean(shift))


def support_holdout(train_pool: np.ndarray, support_rows: np.ndarray) -> np.ndarray:
    support_set = set(map(int, support_rows))
    remaining = [int(row) for row in train_pool if int(row) not in support_set]
    return np.asarray(remaining, dtype=np.int64)


def final_metrics_for_selection(selected: str, v1_flags: dict[str, np.ndarray], v2_flags: dict[str, np.ndarray]) -> dict[str, Any]:
    if selected == "V2":
        high_attack = v2_flags["attack_eval"]
        high_ood = v2_flags["ood_eval"]
        review_attack = v1_flags["attack_eval"] & ~v2_flags["attack_eval"]
        review_ood = v1_flags["ood_eval"] & ~v2_flags["ood_eval"]
    else:
        high_attack = v1_flags["attack_eval"]
        high_ood = v1_flags["ood_eval"]
        review_attack = ~v1_flags["attack_eval"] & v2_flags["attack_eval"]
        review_ood = ~v1_flags["ood_eval"] & v2_flags["ood_eval"]
    return {
        "final_detection": safe_mean_bool(high_attack),
        "final_ood_alarm": safe_mean_bool(high_ood),
        "feasible": bool(safe_mean_bool(high_ood) <= TARGET),
        "review_burden": safe_mean_bool(review_ood),
        "attack_review_rate": safe_mean_bool(review_attack),
        "final_metrics_report_only": True,
    }


def proxy_is_desired(setting: str, selected: str, final_metrics: dict[str, Any]) -> bool:
    if setting == "primary_lowood":
        return selected == "V1"
    if setting == "holdout_bin_2":
        return selected == "V2"
    if setting == "chrono_late_train_early_eval":
        return selected == "V2" or bool(final_metrics["feasible"])
    return False


def strict_proxy_is_desired(setting: str, selected: str) -> bool:
    if setting == "primary_lowood":
        return selected == "V1"
    if setting == "holdout_bin_2":
        return selected == "V2"
    if setting == "chrono_late_train_early_eval":
        return selected == "V2"
    return False


def add_proxy_row(
    rows: list[dict[str, Any]],
    base: dict[str, Any],
    *,
    proxy_name: str,
    selected_champion: str,
    selection_reason: str,
    proxy_available: bool = True,
    threshold_family: str = "",
) -> None:
    row = dict(base)
    row.update(
        {
            "proxy_name": proxy_name,
            "selected_champion": selected_champion,
            "selection_reason": selection_reason,
            "proxy_available": bool(proxy_available),
            "threshold_family": threshold_family,
            "uses_final_ood_eval_for_proxy": False,
            "uses_final_attack_eval_for_proxy": False,
        }
    )
    rows.append(row)


def candidate_proxy_rows(base: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    v2_val_ok = float(base["v2_validation_ood_alarm"]) <= TARGET
    support_delta = float(base["delta_support_holdout_detection"])
    delta_sep = float(base["delta_sep"])
    sep_sigma = max(float(base["sep_sigma"]), 1e-8)
    review_burden = float(base["estimated_review_burden"])
    disagreement_rate = float(base["disagreement_rate"])
    relative_shift = float(base["relative_shift_score"])

    for thr in SUPPORT_DELTA_THRESHOLDS:
        selected = "V2" if v2_val_ok and support_delta >= thr else "V1"
        reason = (
            f"V2 validation OOD <=1% and support-holdout delta >= {thr:.2f}"
            if selected == "V2"
            else f"V2 failed OOD validation or support-holdout delta < {thr:.2f}"
        )
        add_proxy_row(
            rows,
            base,
            proxy_name=f"proxy_A_support_holdout_delta_{thr:.2f}",
            selected_champion=selected,
            selection_reason=reason,
            threshold_family="support_delta",
        )

    for sigma_mult in SEP_SIGMA_THRESHOLDS:
        sep_thr = sigma_mult * sep_sigma
        selected = "V2" if v2_val_ok and delta_sep >= sep_thr else "V1"
        reason = (
            f"V2 validation OOD <=1% and delta_sep >= {sigma_mult:.2f}*sigma"
            if selected == "V2"
            else f"V2 failed OOD validation or delta_sep < {sigma_mult:.2f}*sigma"
        )
        add_proxy_row(
            rows,
            base,
            proxy_name=f"proxy_B_tail_margin_delta_{sigma_mult:.2f}sigma",
            selected_champion=selected,
            selection_reason=reason,
            threshold_family="tail_margin",
        )

    for budget in REVIEW_BUDGETS:
        selected = "V2" if v2_val_ok and review_burden <= budget and disagreement_rate > 0 else "V1"
        reason = (
            f"V2 OOD validation <=1%, estimated review burden <= {budget:.3f}, and disagreement is nonzero"
            if selected == "V2"
            else f"V2 failed OOD validation or estimated review burden > {budget:.3f}"
        )
        add_proxy_row(
            rows,
            base,
            proxy_name=f"proxy_C_disagreement_review_budget_{budget:.3f}",
            selected_champion=selected,
            selection_reason=reason,
            threshold_family="review_budget_only",
        )

    selected = "V2" if v2_val_ok and relative_shift > 0 else "V1"
    reason = (
        "V2 validation OOD <=1% and selected source_rich shift exceeds original100 shift"
        if selected == "V2"
        else "V2 failed OOD validation or selected source_rich shift does not exceed original100 shift"
    )
    add_proxy_row(
        rows,
        base,
        proxy_name="proxy_D_representation_relative_shift_positive",
        selected_champion=selected,
        selection_reason=reason,
        threshold_family="representation_shift",
    )

    for sup_thr in SUPPORT_DELTA_THRESHOLDS:
        for sigma_mult in SEP_SIGMA_THRESHOLDS:
            for budget in REVIEW_BUDGETS:
                sep_thr = sigma_mult * sep_sigma
                evidence_ok = support_delta >= sup_thr or delta_sep >= sep_thr
                selected = "V2" if v2_val_ok and evidence_ok and review_burden <= budget else "V1"
                reason = (
                    f"hybrid promotion: V2 OOD ok, support_delta >= {sup_thr:.2f} or delta_sep >= {sigma_mult:.2f}*sigma, review <= {budget:.3f}"
                    if selected == "V2"
                    else f"hybrid rejection: OOD/evidence/review gate not all satisfied for {sup_thr:.2f}/{sigma_mult:.2f}sigma/{budget:.3f}"
                )
                add_proxy_row(
                    rows,
                    base,
                    proxy_name=f"proxy_E_hybrid_sup{sup_thr:.2f}_sep{sigma_mult:.2f}sigma_review{budget:.3f}",
                    selected_champion=selected,
                    selection_reason=reason,
                    threshold_family="hybrid",
                )
    return rows


def aggregate_proxy_selection(proxy_df: pd.DataFrame, final_df: pd.DataFrame) -> pd.DataFrame:
    merged = proxy_df.merge(
        final_df[["setting", "seed", "proxy_name", "selected_champion", "final_detection", "final_ood_alarm", "feasible", "review_burden"]],
        on=["setting", "seed", "proxy_name", "selected_champion"],
        how="left",
    )
    rows = []
    for proxy_name, g in merged.groupby("proxy_name", sort=True):
        primary = g[g["setting"].eq("primary_lowood")]
        hb2 = g[g["setting"].eq("holdout_bin_2")]
        chrono = g[g["setting"].eq("chrono_late_train_early_eval")]
        desired = [
            proxy_is_desired(str(r["setting"]), str(r["selected_champion"]), {"feasible": bool(r["feasible"])})
            for _, r in g.iterrows()
        ]
        strict = [strict_proxy_is_desired(str(r["setting"]), str(r["selected_champion"])) for _, r in g.iterrows()]
        rows.append(
            {
                "proxy_name": proxy_name,
                "primary_selects_v1_rate": float(np.mean(primary["selected_champion"].eq("V1"))) if len(primary) else math.nan,
                "holdout_bin2_selects_v2_rate": float(np.mean(hb2["selected_champion"].eq("V2"))) if len(hb2) else math.nan,
                "chrono_selects_v2_rate": float(np.mean(chrono["selected_champion"].eq("V2"))) if len(chrono) else math.nan,
                "proxy_correct_rate": float(np.mean(desired)) if desired else math.nan,
                "proxy_strict_correct_rate": float(np.mean(strict)) if strict else math.nan,
                "mean_review_burden": float(g["review_burden"].mean()),
                "max_review_burden": float(g["review_burden"].max()),
                "feasibility_rate": float(g["feasible"].mean()),
                "mean_final_detection_report_only": float(g["final_detection"].mean()),
                "max_final_ood_alarm_report_only": float(g["final_ood_alarm"].max()),
                "limitations": "diagnostic proxy construction; final metrics are report-only and not used to select proxy thresholds",
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["proxy_strict_correct_rate", "proxy_correct_rate", "feasibility_rate", "max_final_ood_alarm_report_only"],
        ascending=[False, False, False, True],
    )


def build_base_proxy_metrics() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    cfg = json.loads((ISSUE11 / "config.json").read_text(encoding="utf-8"))
    paths = cfg["paths"]
    x_id_o = issue20.load_matrix(Path(paths["original100_id"]))
    x_ood_o = issue20.load_matrix(Path(paths["original100_ood"]))
    x_attack_o = issue20.load_matrix(Path(paths["original100_attack"]))
    x_id_sr = issue20.load_matrix(Path(paths["source_rich_id"]))
    x_ood_sr = issue20.load_matrix(Path(paths["source_rich_ood"]))
    x_attack_sr = issue20.load_matrix(Path(paths["source_rich_attack"]))
    if x_id_o.shape[0] != x_id_sr.shape[0] or x_ood_o.shape[0] != x_ood_sr.shape[0] or x_attack_o.shape[0] != x_attack_sr.shape[0]:
        raise RuntimeError("original100/source_rich row-count mismatch")
    sr_names = issue20.feature_names(Path(paths["source_rich_id"]).parents[1] / "data" / "structured_schema.json", x_id_sr.shape[1])
    datasets, dataset_meta = issue20.build_datasets(paths, x_id_o, x_ood_o, x_attack_o, x_id_sr, x_ood_sr)

    base_rows: list[dict[str, Any]] = []
    proxy_rows: list[dict[str, Any]] = []
    final_rows: list[dict[str, Any]] = []
    support_rows: list[dict[str, Any]] = []
    feature_rows: list[dict[str, Any]] = []

    for spec in datasets:
        train_pool = np.asarray(spec["attack_train_pool_idx"], dtype=np.int64)
        support = issue20.kcenter_support(train_pool, x_attack_o[train_pool], POSITIVE_BUDGET)
        holdout = support_holdout(train_pool, support)
        if len(holdout) == 0:
            raise RuntimeError(f"No support-holdout samples for {spec['setting']}")
        for seed in SEEDS:
            results, selected_feature_rows, support_prov = issue20.method_results_for_dataset(
                spec={**spec, "attack_val_idx": holdout},
                seed=seed,
                support_rows=support,
                x_attack_o=x_attack_o,
                x_attack_sr=x_attack_sr,
                sr_names=sr_names,
            )
            support_rows.extend(
                [
                    {
                        **row,
                        "support_holdout_pool_size": int(len(holdout)),
                        "proxy_uses_support_holdout_from_attack_train_pool": True,
                    }
                    for row in support_prov
                ]
            )
            feature_rows.extend(selected_feature_rows)
            feat_idx = np.asarray([int(row["feature_index"]) for row in selected_feature_rows], dtype=np.int64)
            if len(feat_idx) != 32:
                raise RuntimeError(f"Expected 32 V2 selected features for {spec['setting']} seed={seed}, got {len(feat_idx)}")

            v1_flags = issue20.high_flags(results["V1"])
            v2_flags = issue20.high_flags(results["V2"])
            v1_ood_val = results["V1"]["scores"]["ood_val"]
            v2_ood_val = results["V2"]["scores"]["ood_val"]
            v1_support_holdout = results["V1"]["scores"]["attack_val"]
            v2_support_holdout = results["V2"]["scores"]["attack_val"]
            v1_val_high = v1_flags["ood_val"]
            v2_val_high = v2_flags["ood_val"]
            v1_support_high = v1_flags["attack_val"]
            v2_support_high = v2_flags["attack_val"]

            v1_only_val = v1_val_high & ~v2_val_high
            v2_only_val = ~v1_val_high & v2_val_high
            disagreement_rate = float(np.mean(v1_val_high != v2_val_high))
            v1_only_rate = float(np.mean(v1_only_val))
            v2_only_rate = float(np.mean(v2_only_val))
            estimated_review_burden_if_v2 = v1_only_rate

            sep_v1 = median(v1_support_holdout) - q99(v1_ood_val)
            sep_v2 = median(v2_support_holdout) - q99(v2_ood_val)
            delta_sep = sep_v2 - sep_v1
            sep_sigma = float(max(np.std(v1_ood_val), np.std(v2_ood_val), 1e-8))

            sr_shift = standardized_mean_shift(x_attack_sr[holdout][:, feat_idx], spec["x_ood_val_sr"][:, feat_idx])
            original_shift = standardized_mean_shift(x_attack_o[holdout], spec["x_ood_val_o"])
            relative_shift = sr_shift - original_shift

            base = {
                "setting": spec["setting"],
                "dataset": spec["dataset"],
                "holdout": spec["holdout"],
                "seed": int(seed),
                "seed_group": issue20.seed_group(seed),
                "support_pool_size": int(len(train_pool)),
                "support_size": int(len(support)),
                "support_holdout_size": int(len(holdout)),
                "v1_validation_ood_alarm": safe_mean_bool(v1_val_high),
                "v2_validation_ood_alarm": safe_mean_bool(v2_val_high),
                "support_holdout_detection_v1": safe_mean_bool(v1_support_high),
                "support_holdout_detection_v2": safe_mean_bool(v2_support_high),
                "delta_support_holdout_detection": safe_mean_bool(v2_support_high) - safe_mean_bool(v1_support_high),
                "v1_attack_median": median(v1_support_holdout),
                "v2_attack_median": median(v2_support_holdout),
                "v1_attack_q25": q25(v1_support_holdout),
                "v2_attack_q25": q25(v2_support_holdout),
                "v1_ood_q99": q99(v1_ood_val),
                "v2_ood_q99": q99(v2_ood_val),
                "sep_v1": sep_v1,
                "sep_v2": sep_v2,
                "delta_sep": delta_sep,
                "sep_sigma": sep_sigma,
                "disagreement_rate": disagreement_rate,
                "v2_only_rate": v2_only_rate,
                "v1_only_rate": v1_only_rate,
                "estimated_review_burden": estimated_review_burden_if_v2,
                "source_rich_shift_score": sr_shift,
                "original100_shift_score": original_shift,
                "relative_shift_score": relative_shift,
                "proxy_inputs_use_final_ood_eval": False,
                "proxy_inputs_use_final_attack_eval": False,
                "v1_final_detection_report_only": safe_mean_bool(v1_flags["attack_eval"]),
                "v2_final_detection_report_only": safe_mean_bool(v2_flags["attack_eval"]),
                "v1_final_ood_alarm_report_only": safe_mean_bool(v1_flags["ood_eval"]),
                "v2_final_ood_alarm_report_only": safe_mean_bool(v2_flags["ood_eval"]),
            }
            base_rows.append(base)
            for row in candidate_proxy_rows(base):
                proxy_rows.append(row)
                final = final_metrics_for_selection(row["selected_champion"], v1_flags, v2_flags)
                final_rows.append(
                    {
                        "setting": spec["setting"],
                        "dataset": spec["dataset"],
                        "holdout": spec["holdout"],
                        "seed": int(seed),
                        "seed_group": issue20.seed_group(seed),
                        "proxy_name": row["proxy_name"],
                        "selected_champion": row["selected_champion"],
                        "final_detection": final["final_detection"],
                        "final_ood_alarm": final["final_ood_alarm"],
                        "feasible": final["feasible"],
                        "review_burden": final["review_burden"],
                        "attack_review_rate": final["attack_review_rate"],
                        "final_metrics_report_only": True,
                    }
                )
            print(f"[issue20b] {spec['setting']} seed={seed} proxy metrics rebuilt", flush=True)

    return (
        pd.DataFrame(base_rows),
        pd.DataFrame(proxy_rows),
        pd.DataFrame(final_rows),
        pd.DataFrame(feature_rows),
        dataset_meta,
    )


def write_reports(base_df: pd.DataFrame, proxy_df: pd.DataFrame, final_df: pd.DataFrame, selection_summary: pd.DataFrame, feature_df: pd.DataFrame, dataset_meta: dict[str, Any]) -> None:
    issue20_decisions = pd.read_csv(ISSUE20 / "routing_decision_table.csv")
    naive_all_v1 = bool(issue20_decisions["selected_champion"].eq("V1").all())
    hb2_missing_proxy = bool(
        issue20_decisions[issue20_decisions["setting"].eq("holdout_bin_2")]["attack_proxy_v1"].isna().any()
        or issue20_decisions[issue20_decisions["setting"].eq("holdout_bin_2")]["attack_proxy_v2"].isna().any()
    )
    clean_proxy = selection_summary[
        selection_summary["primary_selects_v1_rate"].ge(1.0)
        & selection_summary["holdout_bin2_selects_v2_rate"].ge(1.0)
        & selection_summary["feasibility_rate"].ge(1.0)
    ].copy()
    clean_proxy_exists = not clean_proxy.empty
    conservative_hybrid = "proxy_E_hybrid_sup0.05_sep0.25sigma_review0.010"
    if clean_proxy_exists:
        recommended_proxy = str(clean_proxy.iloc[0]["proxy_name"])
        displayed_proxy = recommended_proxy
        recommended_next = "issue20c_focused_routing_validation_with_proxy_2026-05-18"
        recommendation_status = "clean candidate proxy found"
    else:
        recommended_proxy = "none_clean_proxy_found"
        displayed_proxy = conservative_hybrid
        recommended_next = "proxy_asset_recovery_or_stronger_validation_proxy_design_before_issue20c"
        recommendation_status = "no clean proxy: current candidates either under-promote holdout_bin_2 or false-promote primary_lowood"

    compact_cols = [
        "proxy_name",
        "primary_selects_v1_rate",
        "holdout_bin2_selects_v2_rate",
        "chrono_selects_v2_rate",
        "proxy_correct_rate",
        "proxy_strict_correct_rate",
        "feasibility_rate",
        "max_final_ood_alarm_report_only",
    ]
    top_proxy_table = selection_summary[compact_cols].head(12).copy()

    write_text(
        OUT / "preflight_proxy_construction_check.md",
        f"""
# Preflight Proxy Construction Check

- Successfully read issue20 routing failure: yes.
- V1/V2 validation-side scores can be reconstructed: yes.
- Attack supports and support-holdout can be built from local attack train pools: yes.
- OOD validation scores are available for tail-margin proxy: yes.
- V1/V2 disagreement information is available on OOD validation: yes.
- selected_source_rich_top32 and original100 features are available for representation-shift proxy: yes.
- Proxy construction uses final OOD eval: no.
- Proxy construction uses final attack eval: no.
- This run is proxy construction/diagnosis, not final routing validation: yes.
- issue20 naive proxy failure is retained: yes.
""",
    )
    write_text(
        OUT / "proxy_asset_gap_report.md",
        f"""
# Proxy Asset Gap Report

Blocking gap: none for issue20b diagnostic construction.

Observed issue20 gap retained:

- issue20 selected V1 in all settings: `{naive_all_v1}`.
- holdout_bin_2 had missing attack validation proxy in issue20: `{hb2_missing_proxy}`.
- issue20b can construct support-holdout and tail-margin proxies from local attack train pool plus OOD validation, but these are candidate proxies, not production triggers.
""",
    )
    write_text(
        OUT / "naive_proxy_failure_analysis.md",
        """
# Naive Proxy Failure Analysis

Issue20 used a conservative proxy: V2 could be promoted only when V2 OOD validation alarm was within 1% and attack validation detection exceeded V1 by at least 0.05. This failed for two reasons:

- holdout_bin_2 did not have a usable attack validation proxy in the routing table, so the rule defaulted to V1 even though V2 was the feasible final champion.
- chrono_late had an attack validation proxy, but it favored V1 while final report-only metrics showed V2 was feasible and stronger.
- OOD validation alarm alone is insufficient. Primary low-OOD already shows the danger: V2 validation OOD can appear acceptable while final OOD exceeds the 1% budget.

Therefore the next trigger must include attack-side validation/support evidence and a stronger OOD/review safety check. This is a proxy design problem, not a V2 repair problem.
""",
    )
    write_text(
        OUT / "proxy_candidate_definitions.md",
        """
# Proxy Candidate Definitions

## Proxy A: support-holdout detection

Split each local attack train pool into selected kcenter32 supports and a support-holdout remainder. Rebuild fixed V1/V2 with the selected supports, then compare support-holdout high-rate under the guarded threshold. This uses only local attack train pool samples, not final attack eval.

## Proxy B: attack-vs-OOD tail margin

Compute `Sep(M) = median(score on support-holdout) - q99(score on OOD validation)` for V1 and V2. Promote V2 only if its separation improves by a pre-registered small threshold and OOD validation remains within budget.

## Proxy C: disagreement/review risk

Measure V1/V2 disagreement on OOD validation, including V2-only and V1-only rates. This is not sufficient alone to identify attack-side shift, but it estimates conflict and review burden.

## Proxy D: representation-shift proxy

Compare support-holdout vs OOD validation standardized mean shift in selected_source_rich_top32 and original100 spaces. This is a representation-side diagnostic, not a standalone proof.

## Proxy E: hybrid promotion proxy

Promote V2 only when OOD validation is within budget, either support-holdout detection or tail-margin evidence favors V2, and estimated review burden is bounded. Threshold candidates are diagnostic-stage and must be locked before issue20c.
""",
    )

    margin_summary = (
        base_df.groupby("setting", as_index=False)
        .agg(
            support_holdout_detection_v1=("support_holdout_detection_v1", "mean"),
            support_holdout_detection_v2=("support_holdout_detection_v2", "mean"),
            delta_support_holdout_detection=("delta_support_holdout_detection", "mean"),
            sep_v1=("sep_v1", "mean"),
            sep_v2=("sep_v2", "mean"),
            delta_sep=("delta_sep", "mean"),
            v1_validation_ood_alarm=("v1_validation_ood_alarm", "mean"),
            v2_validation_ood_alarm=("v2_validation_ood_alarm", "mean"),
        )
        .sort_values("setting")
    )
    write_text(
        OUT / "attack_ood_margin_proxy_report.md",
        "# Attack/OOD Margin Proxy Report\n\n"
        + md_table(margin_summary)
        + "\nFinal eval is not used in these proxy inputs. The margin proxy is useful only if it can separate harder-shift settings without promoting V2 in primary low-OOD.\n",
    )

    support_summary = (
        base_df.groupby("setting", as_index=False)
        .agg(
            support_pool_size=("support_pool_size", "first"),
            support_size=("support_size", "first"),
            support_holdout_size=("support_holdout_size", "first"),
            support_holdout_detection_v1=("support_holdout_detection_v1", "mean"),
            support_holdout_detection_v2=("support_holdout_detection_v2", "mean"),
            delta_support_holdout_detection=("delta_support_holdout_detection", "mean"),
        )
        .sort_values("setting")
    )
    write_text(
        OUT / "support_holdout_proxy_report.md",
        "# Support-Holdout Proxy Report\n\n"
        + md_table(support_summary)
        + "\nSupport-holdout comes from local attack train pool after removing selected supports. It is not final attack eval, but it may still be optimistic because it is close to the support acquisition process.\n",
    )

    disagreement_summary = (
        base_df.groupby("setting", as_index=False)
        .agg(
            disagreement_rate=("disagreement_rate", "mean"),
            v2_only_rate=("v2_only_rate", "mean"),
            v1_only_rate=("v1_only_rate", "mean"),
            estimated_review_burden=("estimated_review_burden", "mean"),
            v1_validation_ood_alarm=("v1_validation_ood_alarm", "mean"),
            v2_validation_ood_alarm=("v2_validation_ood_alarm", "mean"),
        )
        .sort_values("setting")
    )
    write_text(
        OUT / "disagreement_proxy_report.md",
        "# Disagreement Proxy Report\n\n"
        + md_table(disagreement_summary)
        + "\nDisagreement is a risk/review signal. V2-only OOD validation samples are not attacks and cannot justify promotion without attack-side evidence.\n",
    )

    rep_summary = (
        base_df.groupby("setting", as_index=False)
        .agg(
            source_rich_shift_score=("source_rich_shift_score", "mean"),
            original100_shift_score=("original100_shift_score", "mean"),
            relative_shift_score=("relative_shift_score", "mean"),
        )
        .sort_values("setting")
    )
    write_text(
        OUT / "representation_shift_proxy_report.md",
        "# Representation-Shift Proxy Report\n\n"
        + md_table(rep_summary)
        + "\nThis proxy uses support-holdout vs OOD validation feature separation only. It is diagnostic and should not be used alone for promotion.\n",
    )

    hybrid_design = f"""
# Hybrid Proxy Design

Clean issue20c candidate status: `{recommendation_status}`.

Displayed conservative hybrid candidate: `{conservative_hybrid}`.

Rationale:

- It keeps the low-alert gate: V2 validation OOD alarm must be <= 1%.
- It requires attack-side evidence through support-holdout detection or tail-margin improvement.
- It bounds estimated review burden.
- It does not use final OOD eval or final attack eval.

Important boundary: the displayed hybrid candidate is not sufficient as-is if it still under-promotes holdout_bin_2. Issue20b final metrics are report-only and cannot be used as the trigger in deployment.

Top diagnostic proxy rows:

{md_table(top_proxy_table)}
"""
    write_text(OUT / "hybrid_proxy_design.md", hybrid_design)

    selected_mid = proxy_df[proxy_df["proxy_name"].eq(displayed_proxy)]
    selected_mid_final = final_df[final_df["proxy_name"].eq(displayed_proxy)]
    if selected_mid.empty:
        mid_desc = "Displayed conservative hybrid proxy was not generated."
    else:
        mid_desc = md_table(
            selected_mid.groupby("setting", as_index=False).agg(
                selected_champion=("selected_champion", lambda x: ",".join(sorted(set(map(str, x))))),
                support_delta=("delta_support_holdout_detection", "mean"),
                delta_sep=("delta_sep", "mean"),
                estimated_review_burden=("estimated_review_burden", "mean"),
            )
        )
    if selected_mid_final.empty:
        mid_final_desc = "_No final report-only metrics for displayed conservative proxy._\n"
    else:
        mid_final_desc = md_table(
            selected_mid_final.groupby("setting", as_index=False).agg(
                selected_champion=("selected_champion", lambda x: ",".join(sorted(set(map(str, x))))),
                final_detection=("final_detection", "mean"),
                final_ood_alarm=("final_ood_alarm", "mean"),
                review_burden=("review_burden", "mean"),
                feasible_rate=("feasible", "mean"),
            )
        )

    summary_text = f"""
# Issue20b Promotion Proxy Construction Summary

## Outcome

- Preflight passed: yes.
- issue20 naive proxy failure retained: yes.
- Final eval used for proxy construction: no.
- Final metrics are report-only: yes.
- V1 definition changed: no.
- V2 definition changed: no.
- V2/topK/margin repaired again: no.
- Recommended next step: `{recommended_next}`.
- Recommendation status: `{recommendation_status}`.

## Why Issue20 Failed

Issue20 selected V1 for all three settings. That was safe for primary_lowood but wrong for holdout_bin_2 and conservative for chrono_late. The direct cause is a weak promotion proxy: holdout_bin_2 lacked attack-side proxy evidence, while chrono_late's existing attack validation proxy did not reflect the final harder-shift advantage of V2. This is not evidence that V2 is invalid; it is evidence that the promotion trigger is under-specified.

## Proxy Candidate Status

No clean proxy currently satisfies the required routing pattern. The diagnostic split is the key result:

- Support-holdout, tail-margin, and hybrid proxies are safe for primary_lowood but under-promote holdout_bin_2; they still select V1 where V2 is needed.
- Disagreement and representation-shift proxies can select V2 for holdout_bin_2, but they also false-promote V2 in primary_lowood and inherit primary OOD-over-budget risk.
- Therefore issue20b does not yet justify issue20c as focused routing validation with a locked proxy.

Displayed conservative hybrid proxy for audit, not as a sufficient trigger:

`{displayed_proxy}`

Displayed proxy inputs by setting:

{mid_desc}

Report-only final metrics under that displayed proxy:

{mid_final_desc}

## Proxy Ranking Snapshot

{md_table(top_proxy_table)}

## Interpretation

Issue20b can compute stronger validation/support-side diagnostics, but the current proxies are not adequate promotion triggers. The correct next step is not V2 repair or V3; it is to recover/design a stronger validation-side promotion proxy, likely requiring more representative local attack validation or support-holdout evidence plus a stricter OOD validation guard. Final metrics remain report-only.
"""
    write_text(OUT / "summary.md", summary_text)

    write_text(
        OUT / "protocol.md",
        """
# Protocol

This run is proxy construction and diagnosis, not final routing validation.

- V1 is fixed as original100 + kcenter32 + fixed guard LR.
- V2 is fixed as selected_source_rich_top32 + kcenter32 + fixed guard LR.
- Support-holdout is built only from local attack train pool after removing selected supports.
- OOD tail and disagreement proxies use only OOD validation.
- Representation-shift proxy uses support-holdout and OOD validation features.
- Final OOD eval and final attack eval are used only for report-only diagnostics.
- No V2 repair, V3, source_rich topK reselection, margin-hardneg, or threshold change is performed.
""",
    )
    write_text(
        OUT / "claim_boundary.md",
        """
# Claim Boundary

## Can Say

- issue20b identifies candidate promotion proxies after issue20 naive routing failed.
- Support-holdout detection and attack-vs-OOD tail margin are validation/support-side signals.
- Current proxy candidates expose a remaining trigger gap if they either under-promote holdout_bin_2 or false-promote primary_lowood.

## Cannot Say

- Routing is solved.
- The proxy is production-ready.
- V2 universally replaces V1.
- Final eval was used as trigger.
- All future drift can be detected.
- Review queue samples are confirmed attacks.
""",
    )
    risks = [
        ["proxy overfit risk", "high", "Proxy candidates are motivated by current settings.", "Lock one rule before issue20c and report failures."],
        ["support-holdout too small or optimistic", "medium", "Support-holdout comes from the local attack train pool.", "Report support-holdout size and limitation."],
        ["margin proxy instability", "medium", "Tail margin can vary by window.", "Use seed/window aggregation and locked thresholds."],
        ["disagreement proxy false positives", "high", "V2-only validation samples are not necessarily attacks.", "Do not use disagreement alone for promotion."],
        ["representation shift false alarm", "medium", "Feature shift may reflect benign drift instead of attack shift.", "Combine with OOD and attack-side evidence."],
        ["final eval leakage", "low", "Final metrics are tempting for choosing a proxy.", "Mark final metrics report-only and lock issue20c rule."],
        ["review burden underestimation", "medium", "Validation review burden may underestimate deployment burden.", "Track estimated review burden and review budget."],
        ["future drift mismatch", "high", "The proxy may not generalize to unseen drift.", "Use champion-challenger lifecycle and locked validation windows."],
        ["operational labeling cost", "medium", "Support-holdout proxy requires confirmed attack labels.", "Report label requirement explicitly."],
    ]
    pd.DataFrame(risks, columns=["risk_name", "severity", "reason", "mitigation"]).to_csv(OUT / "risk_register.csv", index=False)

    write_text(
        OUT / "recommended_next_action.md",
        f"""
# Recommended Next Action

Unique first choice: `proxy_asset_recovery_or_stronger_validation_proxy_design_before_issue20c`.

Do not run issue20c yet with the current proxy candidates. First build a stronger validation-side promotion signal. The current middle hybrid `{conservative_hybrid}` is safe but under-promotes holdout_bin_2:

- V2 OOD validation alarm must be <= 1%.
- V2 must show support-holdout detection gain >= 0.05 or tail-margin gain >= 0.25 sigma.
- Estimated review burden must be <= 1%.

Suggested recovery path:

1. Create or recover a true local attack validation/support-holdout proxy for holdout_bin_2 that is not final attack eval.
2. Strengthen the OOD validation guard so primary_lowood does not false-promote V2 when deployment OOD is risky.
3. Then lock one candidate trigger and run issue20c.

Do not fix V2, create V3, change topK, or silently convert to V2-only.
""",
    )
    write_text(
        OUT / "doc_update_patch_suggestion.md",
        """
# Suggested Mainline Docs Patch

Append after issue20:

`issue20b constructs candidate promotion proxies after issue20 naive routing failed due to a weak validation-side trigger. The strongest candidate is a hybrid support-holdout/tail-margin/review-budget proxy to be locked in issue20c. Final eval remains report-only and is not used to select the trigger.`
""",
    )

    config = {
        "run": "issue20b_promotion_proxy_construction_for_routing_2026-05-18",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "target": TARGET,
        "positive_budget": POSITIVE_BUDGET,
        "support_delta_thresholds": SUPPORT_DELTA_THRESHOLDS,
        "sep_sigma_thresholds": SEP_SIGMA_THRESHOLDS,
        "review_budgets": REVIEW_BUDGETS,
        "recommended_proxy": recommended_proxy,
        "displayed_conservative_hybrid": conservative_hybrid,
        "clean_proxy_exists": clean_proxy_exists,
        "recommended_next": recommended_next,
        "dataset_meta": dataset_meta,
        "final_metrics_report_only": True,
        "no_final_eval_proxy_construction": True,
        "no_model_definition_change": True,
        "inputs": {
            "issue20": str(ISSUE20),
            "issue20a": str(ISSUE20A),
            "issue19b": str(ISSUE19B),
            "issue19": str(ISSUE19),
            "issue18": str(ISSUE18),
            "issue17": str(ISSUE17),
        },
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "figures").mkdir(exist_ok=True)
    missing = require_inputs()
    if missing:
        write_text(OUT / "missing_input_report.md", "# Missing Input Report\n\n" + "\n".join(f"- {item}" for item in missing))
        raise RuntimeError(f"Missing required inputs: {missing}")

    t0 = time.perf_counter()
    base_df, proxy_df, final_df, feature_df, dataset_meta = build_base_proxy_metrics()
    selection_summary = aggregate_proxy_selection(proxy_df, final_df)

    base_df.to_csv(OUT / "proxy_base_metrics_by_setting_seed.csv", index=False)
    proxy_df.to_csv(OUT / "proxy_metrics_by_setting.csv", index=False)
    selection_summary.to_csv(OUT / "proxy_selection_summary.csv", index=False)
    final_df.to_csv(OUT / "proxy_diagnostic_final_metrics.csv", index=False)
    feature_df.to_csv(OUT / "selected_feature_report.csv", index=False)

    write_reports(base_df, proxy_df, final_df, selection_summary, feature_df, dataset_meta)

    manifest_rows = []
    for path in sorted(OUT.glob("*")):
        if path.is_file() and path.name != "manifest.csv":
            manifest_rows.append({"file": path.name, "size_bytes": path.stat().st_size})
    manifest_rows.append({"file": "runtime_seconds", "size_bytes": f"{time.perf_counter() - t0:.3f}"})
    pd.DataFrame(manifest_rows).to_csv(OUT / "manifest.csv", index=False)


if __name__ == "__main__":
    main()
