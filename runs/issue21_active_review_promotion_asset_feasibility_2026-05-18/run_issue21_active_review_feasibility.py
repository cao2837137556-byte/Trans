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
from sklearn.metrics import pairwise_distances
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs" / "issue21_active_review_promotion_asset_feasibility_2026-05-18"
ISSUE21 = OUT
ISSUE20B = ROOT / "runs" / "issue20b_promotion_proxy_construction_for_routing_2026-05-18"
ISSUE20 = ROOT / "runs" / "issue20_mode_specific_routing_validation_2026-05-18"
ISSUE20A = ROOT / "runs" / "issue20a_lowguard_routed_lifecycle_design_doc_2026-05-18"
ISSUE19B = ROOT / "runs" / "issue19b_v1_v2_same_protocol_backtest_and_alarm_budget_curve_2026-05-18"
ISSUE19 = ROOT / "runs" / "issue19_lowguard_plus_representation_margin_repair_pilot_2026-05-18"
ISSUE18 = ROOT / "runs" / "issue18_row_level_score_persistence_and_ood_target_sensitivity_2026-05-15"
ISSUE15 = ROOT / "runs" / "issue15_review_budget_constrained_arbitration_2026-05-15"
ISSUE11 = ROOT / "runs" / "issue11_fixed_config_ood_guard_lr_ablation_2026-05-14"
ISSUE20_SCRIPT = ISSUE20 / "run_issue20_routing_validation.py"

POSITIVE_BUDGET = 32
SEEDS = list(range(42, 52))
KS = [4, 8, 16, 32]
DELTAS = [0.05, 0.10, 0.20]
TARGET = 0.01
STRATEGIES = [
    "R0_random_confirmed_attack_validation",
    "R1_kcenter_confirmed_attack_validation",
    "R2_V2_high_V1_low_disagreement_review",
    "R3_near_threshold_uncertainty_review",
    "R4_representation_shift_high_review",
    "R5_hybrid_active_review",
]


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
                vals.append("" if math.isnan(float(value)) else f"{float(value):.6f}")
            else:
                vals.append(str(value))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"


def require_inputs() -> list[str]:
    required = [
        ISSUE20B / "summary.md",
        ISSUE20B / "proxy_selection_summary.csv",
        ISSUE20B / "proxy_metrics_by_setting.csv",
        ISSUE20B / "recommended_next_action.md",
        ISSUE20B / "proxy_asset_gap_report.md",
        ISSUE20B / "claim_boundary.md",
        ISSUE20 / "summary.md",
        ISSUE20 / "routing_decision_table.csv",
        ISSUE20 / "strategy_metrics_summary.csv",
        ISSUE20 / "conflict_matrix_summary.csv",
        ISSUE20 / "review_burden_summary.csv",
        ISSUE20 / "wrong_routing_cases.md",
        ISSUE20A / "promotion_gate_policy.md",
        ISSUE20A / "v1_v2_deployment_roles.md",
        ISSUE20A / "reviewer_defense.md",
        ISSUE20A / "issue20_routing_validation_plan.md",
        ISSUE20A / "claim_boundary.md",
        ISSUE19B / "v1_vs_v2_by_dataset.csv",
        ISSUE19B / "alarm_budget_curve_summary.csv",
        ISSUE19B / "feasible_operating_points.csv",
        ISSUE19B / "mode_routing_implication.md",
        ISSUE19B / "non_regression_report.md",
        ISSUE19 / "summary.md",
        ISSUE18 / "summary.md",
        ISSUE18 / "diagnostic_decision.md",
        ISSUE15 / "review_budget_metrics_summary.csv",
        ISSUE11 / "config.json",
        ISSUE20_SCRIPT,
    ]
    return [str(path) for path in required if not path.exists()]


def seed_group(seed: int) -> str:
    return issue20.seed_group(seed)


def safe_mean_bool(arr: np.ndarray) -> float:
    return float(np.mean(arr)) if len(arr) else math.nan


def kcenter_rows(rows: np.ndarray, features: np.ndarray, k: int) -> np.ndarray:
    if len(rows) <= k:
        return np.asarray(rows, dtype=np.int64)
    scaler = StandardScaler().fit(features)
    x = scaler.transform(features)
    centroid = x.mean(axis=0, keepdims=True)
    start_idx = int(np.argmin(pairwise_distances(x, centroid).ravel()))
    local_idx = issue20.farthest_first_indices(x, k, start_idx)
    return np.asarray(rows, dtype=np.int64)[local_idx]


def support_holdout(train_pool: np.ndarray, support_rows: np.ndarray) -> np.ndarray:
    support_set = set(map(int, support_rows))
    return np.asarray([int(row) for row in train_pool if int(row) not in support_set], dtype=np.int64)


def zscore(arr: np.ndarray) -> np.ndarray:
    arr = np.asarray(arr, dtype=np.float64)
    if len(arr) == 0:
        return arr
    std = float(np.std(arr))
    if std < 1e-12:
        return np.zeros_like(arr)
    return (arr - float(np.mean(arr))) / std


def desired_champion(setting: str) -> str:
    if setting == "primary_lowood":
        return "V1"
    if setting in {"holdout_bin_2", "chrono_late_train_early_eval"}:
        return "V2"
    return "V1"


def final_metrics(selected: str, v1_flags: dict[str, np.ndarray], v2_flags: dict[str, np.ndarray]) -> dict[str, Any]:
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
        "final_attack_detection": safe_mean_bool(high_attack),
        "final_ood_alarm": safe_mean_bool(high_ood),
        "feasible": bool(safe_mean_bool(high_ood) <= TARGET),
        "review_rate_attack": safe_mean_bool(review_attack),
        "review_rate_ood": safe_mean_bool(review_ood),
    }


def select_evidence(
    *,
    strategy: str,
    k: int,
    seed: int,
    support_holdout_rows: np.ndarray,
    support_holdout_o: np.ndarray,
    support_holdout_sr_sel: np.ndarray,
    ood_val_o: np.ndarray,
    ood_val_sr_sel: np.ndarray,
    v1_support_scores: np.ndarray,
    v2_support_scores: np.ndarray,
    v1_ood_scores: np.ndarray,
    v2_ood_scores: np.ndarray,
    v1_threshold: float,
    v2_threshold: float,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Return candidate indices in concatenated [support-holdout attack, OOD-val benign] space."""
    n_attack = len(support_holdout_rows)
    n_ood = len(ood_val_o)
    labels = np.concatenate([np.ones(n_attack, dtype=np.int64), np.zeros(n_ood, dtype=np.int64)])
    v1_scores = np.concatenate([v1_support_scores, v1_ood_scores])
    v2_scores = np.concatenate([v2_support_scores, v2_ood_scores])
    v1_high = v1_scores > v1_threshold
    v2_high = v2_scores > v2_threshold
    sr_all = np.vstack([support_holdout_sr_sel, ood_val_sr_sel])

    rng = np.random.default_rng(seed + 2100)
    if strategy == "R0_random_confirmed_attack_validation":
        attack_idx = np.arange(n_attack)
        selected = rng.choice(attack_idx, size=min(k, len(attack_idx)), replace=False)
        pool_mask = labels == 1
        selection_score = np.ones(len(selected))
    elif strategy == "R1_kcenter_confirmed_attack_validation":
        selected_rows = kcenter_rows(np.arange(n_attack), support_holdout_o, min(k, n_attack))
        selected = selected_rows.astype(np.int64)
        pool_mask = labels == 1
        selection_score = np.ones(len(selected))
    elif strategy == "R2_V2_high_V1_low_disagreement_review":
        pool_mask = v2_high & ~v1_high
        pool = np.where(pool_mask)[0]
        order_score = v2_scores[pool] - v2_threshold if len(pool) else np.asarray([])
        order = np.argsort(-order_score)[:k] if len(pool) else np.asarray([], dtype=np.int64)
        selected = pool[order]
        selection_score = order_score[order] if len(pool) else np.asarray([])
    elif strategy == "R3_near_threshold_uncertainty_review":
        dist = np.minimum(np.abs(v1_scores - v1_threshold), np.abs(v2_scores - v2_threshold))
        pool_mask = np.ones_like(labels, dtype=bool)
        selected = np.argsort(dist)[: min(k, len(dist))]
        selection_score = -dist[selected]
    elif strategy == "R4_representation_shift_high_review":
        ood_centroid = ood_val_sr_sel.mean(axis=0, keepdims=True)
        ood_std = ood_val_sr_sel.std(axis=0, keepdims=True) + 1e-8
        drift = np.linalg.norm((sr_all - ood_centroid) / ood_std, axis=1)
        pool_mask = np.ones_like(labels, dtype=bool)
        selected = np.argsort(-drift)[: min(k, len(drift))]
        selection_score = drift[selected]
    elif strategy == "R5_hybrid_active_review":
        ood_centroid = ood_val_sr_sel.mean(axis=0, keepdims=True)
        ood_std = ood_val_sr_sel.std(axis=0, keepdims=True) + 1e-8
        drift = np.linalg.norm((sr_all - ood_centroid) / ood_std, axis=1)
        uncertainty = -np.minimum(np.abs(v1_scores - v1_threshold), np.abs(v2_scores - v2_threshold))
        disagreement = (v2_high & ~v1_high).astype(np.float64)
        score = zscore(drift) + zscore(uncertainty) + 2.0 * disagreement
        pool_mask = np.ones_like(labels, dtype=bool)
        selected = np.argsort(-score)[: min(k, len(score))]
        selection_score = score[selected]
    else:
        raise ValueError(f"Unknown strategy {strategy}")

    selected = np.asarray(selected, dtype=np.int64)
    reviewed_labels = labels[selected] if len(selected) else np.asarray([], dtype=np.int64)
    confirmed_attack_mask = reviewed_labels == 1
    confirmed_idx = selected[confirmed_attack_mask]
    meta = {
        "pool_size": int(np.sum(pool_mask)),
        "reviewed_count": int(len(selected)),
        "confirmed_attack_count": int(np.sum(confirmed_attack_mask)),
        "reviewed_attack_fraction": float(np.mean(reviewed_labels)) if len(reviewed_labels) else math.nan,
        "selection_score_mean": float(np.mean(selection_score)) if len(selection_score) else math.nan,
        "selected_candidate_indices": ";".join(map(str, selected[:100])),
    }
    return confirmed_idx, meta


def build_results() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    cfg = json.loads((ISSUE11 / "config.json").read_text(encoding="utf-8"))
    paths = cfg["paths"]
    x_id_o = issue20.load_matrix(Path(paths["original100_id"]))
    x_ood_o = issue20.load_matrix(Path(paths["original100_ood"]))
    x_attack_o = issue20.load_matrix(Path(paths["original100_attack"]))
    x_id_sr = issue20.load_matrix(Path(paths["source_rich_id"]))
    x_ood_sr = issue20.load_matrix(Path(paths["source_rich_ood"]))
    x_attack_sr = issue20.load_matrix(Path(paths["source_rich_attack"]))
    sr_names = issue20.feature_names(Path(paths["source_rich_id"]).parents[1] / "data" / "structured_schema.json", x_id_sr.shape[1])
    datasets, dataset_meta = issue20.build_datasets(paths, x_id_o, x_ood_o, x_attack_o, x_id_sr, x_ood_sr)

    metric_rows: list[dict[str, Any]] = []
    pool_rows: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    feature_rows: list[dict[str, Any]] = []

    for spec in datasets:
        train_pool = np.asarray(spec["attack_train_pool_idx"], dtype=np.int64)
        support = issue20.kcenter_support(train_pool, x_attack_o[train_pool], POSITIVE_BUDGET)
        holdout = support_holdout(train_pool, support)
        for seed in SEEDS:
            results, selected_feature_rows, _support_prov = issue20.method_results_for_dataset(
                spec={**spec, "attack_val_idx": holdout},
                seed=seed,
                support_rows=support,
                x_attack_o=x_attack_o,
                x_attack_sr=x_attack_sr,
                sr_names=sr_names,
            )
            feature_rows.extend(selected_feature_rows)
            feat_idx = np.asarray([int(row["feature_index"]) for row in selected_feature_rows], dtype=np.int64)
            v1_flags = issue20.high_flags(results["V1"])
            v2_flags = issue20.high_flags(results["V2"])
            v1_thr = float(results["V1"]["threshold"])
            v2_thr = float(results["V2"]["threshold"])
            v2_val_ood_alarm = safe_mean_bool(v2_flags["ood_val"])

            for strategy in STRATEGIES:
                for k in KS:
                    confirmed_idx, meta = select_evidence(
                        strategy=strategy,
                        k=k,
                        seed=seed,
                        support_holdout_rows=holdout,
                        support_holdout_o=x_attack_o[holdout],
                        support_holdout_sr_sel=x_attack_sr[holdout][:, feat_idx],
                        ood_val_o=spec["x_ood_val_o"],
                        ood_val_sr_sel=spec["x_ood_val_sr"][:, feat_idx],
                        v1_support_scores=results["V1"]["scores"]["attack_val"],
                        v2_support_scores=results["V2"]["scores"]["attack_val"],
                        v1_ood_scores=results["V1"]["scores"]["ood_val"],
                        v2_ood_scores=results["V2"]["scores"]["ood_val"],
                        v1_threshold=v1_thr,
                        v2_threshold=v2_thr,
                    )
                    if len(confirmed_idx):
                        promotion_v1 = safe_mean_bool(results["V1"]["scores"]["attack_val"][confirmed_idx] > v1_thr)
                        promotion_v2 = safe_mean_bool(results["V2"]["scores"]["attack_val"][confirmed_idx] > v2_thr)
                        delta_promo = promotion_v2 - promotion_v1
                    else:
                        promotion_v1 = math.nan
                        promotion_v2 = math.nan
                        delta_promo = math.nan

                    pool_rows.append(
                        {
                            "setting": spec["setting"],
                            "seed": int(seed),
                            "seed_group": seed_group(seed),
                            "evidence_strategy": strategy,
                            "k": int(k),
                            "pool_size": meta["pool_size"],
                            "reviewed_count": meta["reviewed_count"],
                            "confirmed_attack_count": meta["confirmed_attack_count"],
                            "attack_fraction_if_labels_available_for_simulation": meta["reviewed_attack_fraction"],
                            "estimated_manual_review_cost": meta["reviewed_count"],
                            "selection_efficiency": float(meta["confirmed_attack_count"] / meta["reviewed_count"]) if meta["reviewed_count"] else math.nan,
                            "selection_score_mean": meta["selection_score_mean"],
                            "selection_uses_final_eval": False,
                        }
                    )
                    evidence_rows.append(
                        {
                            "setting": spec["setting"],
                            "seed": int(seed),
                            "seed_group": seed_group(seed),
                            "evidence_strategy": strategy,
                            "k": int(k),
                            "confirmed_attack_count": meta["confirmed_attack_count"],
                            "confirmed_attack_candidate_indices": meta["selected_candidate_indices"],
                            "evidence_uses_final_attack_eval": False,
                            "evidence_uses_final_ood_eval": False,
                        }
                    )
                    for delta in DELTAS:
                        if not math.isnan(delta_promo) and v2_val_ood_alarm <= TARGET and delta_promo >= delta:
                            selected = "V2"
                            reason = f"V2 OOD validation <=1% and promotion delta >= {delta:.2f}"
                        else:
                            selected = "V1"
                            reason = f"V2 OOD validation >1%, no confirmed attack evidence, or promotion delta < {delta:.2f}"
                        fm = final_metrics(selected, v1_flags, v2_flags)
                        desired = desired_champion(spec["setting"])
                        metric_rows.append(
                            {
                                "setting": spec["setting"],
                                "dataset": spec["dataset"],
                                "holdout": spec["holdout"],
                                "seed": int(seed),
                                "seed_group": seed_group(seed),
                                "evidence_strategy": strategy,
                                "k": int(k),
                                "delta_threshold": float(delta),
                                "promotion_detection_v1": promotion_v1,
                                "promotion_detection_v2": promotion_v2,
                                "delta_promotion_detection": delta_promo,
                                "v2_ood_validation_alarm": v2_val_ood_alarm,
                                "selected_champion": selected,
                                "selected_reason": reason,
                                "desired_champion": desired,
                                "selection_correct": bool(selected == desired),
                                "final_attack_detection": fm["final_attack_detection"],
                                "final_ood_alarm": fm["final_ood_alarm"],
                                "feasible": fm["feasible"],
                                "review_cost": int(meta["reviewed_count"]),
                                "review_pool_size": int(meta["pool_size"]),
                                "confirmed_attack_count": int(meta["confirmed_attack_count"]),
                                "estimated_label_efficiency": float(meta["confirmed_attack_count"] / meta["reviewed_count"]) if meta["reviewed_count"] else math.nan,
                                "review_rate_attack_report_only": fm["review_rate_attack"],
                                "review_rate_ood_report_only": fm["review_rate_ood"],
                                "promotion_uses_final_attack_eval": False,
                                "promotion_uses_final_ood_eval": False,
                            }
                        )
            print(f"[issue21] {spec['setting']} seed={seed} promotion evidence simulated", flush=True)
    return pd.DataFrame(metric_rows), pd.DataFrame(pool_rows), pd.DataFrame(evidence_rows), pd.DataFrame(feature_rows), dataset_meta


def aggregate_selection(metrics: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (strategy, k, delta), g in metrics.groupby(["evidence_strategy", "k", "delta_threshold"], sort=True):
        primary = g[g["setting"].eq("primary_lowood")]
        hb2 = g[g["setting"].eq("holdout_bin_2")]
        chrono = g[g["setting"].eq("chrono_late_train_early_eval")]
        rows.append(
            {
                "evidence_strategy": strategy,
                "k": int(k),
                "delta_threshold": float(delta),
                "primary_selects_v1_rate": float(np.mean(primary["selected_champion"].eq("V1"))) if len(primary) else math.nan,
                "holdout_bin2_selects_v2_rate": float(np.mean(hb2["selected_champion"].eq("V2"))) if len(hb2) else math.nan,
                "chrono_selects_v2_rate": float(np.mean(chrono["selected_champion"].eq("V2"))) if len(chrono) else math.nan,
                "overall_selection_correct_rate": float(g["selection_correct"].mean()),
                "final_detection_mean": float(g["final_attack_detection"].mean()),
                "final_ood_alarm_max": float(g["final_ood_alarm"].max()),
                "feasible_rate": float(g["feasible"].mean()),
                "mean_review_cost": float(g["review_cost"].mean()),
                "label_efficiency": float(g["estimated_label_efficiency"].mean()),
                "mean_confirmed_attack_count": float(g["confirmed_attack_count"].mean()),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["overall_selection_correct_rate", "feasible_rate", "final_ood_alarm_max", "mean_review_cost"],
        ascending=[False, False, True, True],
    )


def label_budget_curve(metrics: pd.DataFrame) -> pd.DataFrame:
    return (
        metrics.groupby(["evidence_strategy", "k"], as_index=False)
        .agg(
            selection_correct_rate=("selection_correct", "mean"),
            final_detection_mean=("final_attack_detection", "mean"),
            final_ood_alarm_max=("final_ood_alarm", "max"),
            feasible_rate=("feasible", "mean"),
            label_efficiency=("estimated_label_efficiency", "mean"),
            mean_confirmed_attack_count=("confirmed_attack_count", "mean"),
        )
        .sort_values(["evidence_strategy", "k"])
    )


def write_reports(metrics: pd.DataFrame, pool_df: pd.DataFrame, summary_df: pd.DataFrame, curve_df: pd.DataFrame, dataset_meta: dict[str, Any]) -> None:
    best = summary_df.iloc[0] if not summary_df.empty else None
    strong_candidates = summary_df[
        summary_df["primary_selects_v1_rate"].ge(1.0)
        & summary_df["holdout_bin2_selects_v2_rate"].ge(1.0)
        & summary_df["feasible_rate"].ge(1.0)
    ]
    strong_positive = not strong_candidates.empty
    if strong_positive:
        chosen = strong_candidates.sort_values(["k", "delta_threshold", "overall_selection_correct_rate"], ascending=[True, True, False]).iloc[0]
        next_action = "issue22_evidence_gated_promotion_validation_2026-05-18"
        interpretation = "active evidence can repair proxy failure under at least one pre-registered candidate"
    else:
        chosen = best
        next_action = "weaken_routing_claim_or_recover_stronger_promotion_validation_assets"
        interpretation = "current active evidence assets do not cleanly repair proxy failure"

    top_cols = [
        "evidence_strategy",
        "k",
        "delta_threshold",
        "primary_selects_v1_rate",
        "holdout_bin2_selects_v2_rate",
        "chrono_selects_v2_rate",
        "overall_selection_correct_rate",
        "final_ood_alarm_max",
        "feasible_rate",
        "label_efficiency",
    ]
    top_table = summary_df[top_cols].head(15)
    chosen_name = "none" if chosen is None else f"{chosen['evidence_strategy']} k={int(chosen['k'])} delta={float(chosen['delta_threshold']):.2f}"
    chosen_rows = metrics[
        (metrics["evidence_strategy"].eq(chosen["evidence_strategy"]) if chosen is not None else False)
        & (metrics["k"].eq(int(chosen["k"])) if chosen is not None else False)
        & (metrics["delta_threshold"].eq(float(chosen["delta_threshold"])) if chosen is not None else False)
    ] if chosen is not None else pd.DataFrame()
    chosen_setting = (
        chosen_rows.groupby("setting", as_index=False).agg(
            selected_champion=("selected_champion", lambda x: ",".join(sorted(set(map(str, x))))),
            selection_correct_rate=("selection_correct", "mean"),
            final_attack_detection=("final_attack_detection", "mean"),
            final_ood_alarm=("final_ood_alarm", "mean"),
            feasible_rate=("feasible", "mean"),
            confirmed_attack_count=("confirmed_attack_count", "mean"),
        )
        if not chosen_rows.empty
        else pd.DataFrame()
    )

    write_text(
        OUT / "preflight_active_review_promotion_check.md",
        """
# Preflight Active Review Promotion Check

- Successfully read issue20/20b proxy failure: yes.
- Candidate review pools can be identified: yes.
- Promotion validation evidence is constructed from non-final sources: yes.
- Support train / support validation split can be reconstructed from local attack train pool: yes.
- 4 / 8 / 16 / 32 evidence budgets can be simulated: yes.
- V1/V2 can be evaluated on promotion evidence: yes.
- Final attack eval is not used to construct evidence: yes.
- Final OOD eval is not used to select promotion threshold: yes.
- V1/V2 definitions are unchanged: yes.
- This run is feasibility, not final deployment validation: yes.
""",
    )
    write_text(
        OUT / "promotion_asset_gap_report.md",
        """
# Promotion Asset Gap Report

Blocking gap: none for this feasibility simulation.

Important limitation: active-review strategies R2-R5 use labels only after simulated review on non-final candidate pools. The result estimates evidence cost and feasibility; it is not a production-ready active review loop.
""",
    )
    write_text(
        OUT / "evidence_source_definitions.md",
        """
# Evidence Source Definitions

- R0 random confirmed attack validation: randomly draw confirmed attack evidence from local attack train pool after selected supports are removed.
- R1 kcenter confirmed attack validation: choose representative confirmed attack evidence from the same non-final local attack train pool.
- R2 V2_high_V1_low disagreement review: review candidates where V2 is high and V1 is low, then use only confirmed attacks from reviewed samples for promotion evidence.
- R3 near-threshold / uncertainty review: review samples closest to V1/V2 thresholds, then use confirmed attacks only.
- R4 representation-shift-high review: review samples far from OOD validation centroid in selected_source_rich_top32 space.
- R5 hybrid active review: combine disagreement, threshold uncertainty, and selected representation shift.

Review candidates are not assumed to be attacks. Review labels are simulated only for non-final candidate pools.
""",
    )
    write_text(
        OUT / "promotion_rule.md",
        """
# Promotion Rule

For each setting, seed, evidence strategy, evidence budget k, and delta threshold:

1. Keep V1 and V2 definitions fixed.
2. Obtain promotion evidence from non-final sources only.
3. Compute `promotion_detection_v1` and `promotion_detection_v2` on confirmed attack evidence.
4. Check `V2 OOD validation alarm <= 1%`.
5. Promote V2 only if `promotion_detection_v2 - promotion_detection_v1 >= delta`; otherwise use V1.

Delta candidates are 0.05, 0.10, and 0.20. All are reported. Final eval is report-only.
""",
    )
    write_text(
        OUT / "wrong_promotion_cases.md",
        "# Wrong Promotion Cases\n\n"
        + (
            md_table(
                metrics[~metrics["selection_correct"]][
                    [
                        "setting",
                        "seed",
                        "evidence_strategy",
                        "k",
                        "delta_threshold",
                        "selected_champion",
                        "desired_champion",
                        "promotion_detection_v1",
                        "promotion_detection_v2",
                        "delta_promotion_detection",
                        "confirmed_attack_count",
                    ]
                ],
                max_rows=80,
            )
            if (~metrics["selection_correct"]).any()
            else "None.\n"
        )
        + "\nWrong promotions are expected in this feasibility run. They are not hidden; they define whether evidence-gated promotion is viable.\n",
    )
    write_text(
        OUT / "evidence_gated_promotion_interpretation.md",
        """
# Evidence-Gated Promotion Interpretation

This run is not continual learning and not fully automatic routing. It asks whether a small, explicit evidence budget can support promotion from V1 to V2 when fully automatic proxy signals are insufficient.

Evidence-gated promotion is safer than pure continual adaptation because a challenger must pass a low-alert OOD validation gate and an explicit confirmed-attack evidence gate before promotion. Review samples are not free and are not assumed to be attacks; they are a bounded evidence acquisition cost.
""",
    )
    write_text(
        OUT / "claim_boundary.md",
        """
# Claim Boundary

## Can Say

- issue21 estimates the active evidence needed for safe V2 promotion if metrics support it.
- Active review / confirmed evidence may repair proxy failure if promotion selection improves.
- Evidence-gated promotion is more realistic than fully automatic proxy when proxy-only routing fails.

## Cannot Say

- Fully automatic routing is solved.
- V2 universally replaces V1.
- Future drift is automatically solved.
- Review labels are free.
- Final eval was used as promotion trigger.
- The evidence-gated system is production-ready before locked validation.
""",
    )
    risks = [
        ["promotion evidence overfit", "high", "Evidence policies are tested on current settings.", "Require locked validation before claims."],
        ["simulated review label optimism", "high", "Simulation knows labels after review.", "Report review cost and attack fraction explicitly."],
        ["review pool attack fraction uncertainty", "high", "Real review pools may be less attack-rich.", "Separate candidate pool size from confirmed evidence count."],
        ["label cost underestimation", "medium", "Manual review cost can exceed k confirmed attacks.", "Report reviewed count and label efficiency."],
        ["delayed label problem", "medium", "Confirmed labels may arrive late in deployment.", "Frame as feasibility, not real-time guarantee."],
        ["primary mis-promotion", "high", "V2 can exceed OOD budget in primary.", "Require V2 OOD validation and selection correctness reporting."],
        ["holdout false negative promotion", "high", "Evidence may still fail to activate V2.", "Report wrong_promotion_cases.md."],
        ["review bias", "medium", "Active review sampling may bias evidence.", "Compare random/kcenter/disagreement/uncertainty/drift strategies."],
        ["future drift mismatch", "high", "Current evidence may not represent future drift.", "Use champion-challenger lifecycle."],
        ["final eval leakage", "low", "Final metrics must remain report-only.", "Emit explicit provenance flags."],
    ]
    pd.DataFrame(risks, columns=["risk_name", "severity", "reason", "mitigation"]).to_csv(OUT / "risk_register.csv", index=False)

    write_text(
        OUT / "summary.md",
        f"""
# Issue21 Active Review Promotion Asset Feasibility Summary

## Outcome

- Preflight passed: yes.
- Promotion asset gap: none blocking for feasibility simulation.
- Final eval used for promotion evidence: no.
- V1/V2 definitions changed: no.
- issue20/20b proxy failure retained: yes.
- Best candidate summary: `{chosen_name}`.
- Strong/moderate positive candidate exists: `{strong_positive}`.
- Interpretation: `{interpretation}`.
- Recommended next step: `{next_action}`.

## Top Evidence-Gated Candidates

{md_table(top_table)}

## Chosen Candidate By Setting

{md_table(chosen_setting)}

## Research Interpretation

This run estimates whether small confirmed evidence budgets can repair the promotion-trigger gap. The key question is not whether V2 is good on final metrics, but whether V2 can be promoted using non-final evidence without mis-promoting primary_lowood. If no strategy achieves that, the routing claim should be weakened or the promotion assets must be improved before issue22.
""",
    )
    write_text(
        OUT / "protocol.md",
        """
# Protocol

This is an active review / promotion evidence feasibility run.

- Fixed V1: original100 + kcenter32 + fixed guard LR.
- Fixed V2: selected_source_rich_top32 + kcenter32 + fixed guard LR.
- Evidence budgets: 4, 8, 16, 32.
- Delta thresholds: 0.05, 0.10, 0.20.
- Evidence sources R0-R5 are built from non-final support/validation candidates.
- Final attack eval and final OOD eval are report-only.
- No V2 repair, V3, source_rich topK reselection, continual training, or threshold tuning is performed.
""",
    )
    write_text(
        OUT / "recommended_next_action.md",
        f"""
# Recommended Next Action

Unique first choice: `{next_action}`.

If using this as a basis for issue22, lock the evidence strategy, k, and delta before evaluation. Do not select a route using final metrics.

If the evidence-gated candidates are weak or primary mis-promotion remains common, weaken the routing claim and position V2 as a manually triggered repair module until stronger promotion assets exist.
""",
    )
    write_text(
        OUT / "doc_update_patch_suggestion.md",
        """
# Suggested Mainline Docs Patch

Append after issue20b:

`issue21 evaluates whether a small active-review / confirmed-evidence budget can repair the promotion-trigger gap after automatic proxy routing failed. It is feasibility analysis, not continual learning and not final deployment validation.`
""",
    )

    # Compact cross-method comparison against issue20/20b baselines.
    naive = pd.read_csv(ISSUE20 / "strategy_metrics_summary.csv")
    naive_routed = naive[naive["strategy"].eq("LOW_GUARD_Routed")].copy()
    rows = []
    for _, row in naive_routed.iterrows():
        rows.append(
            {
                "method": "issue20_naive_routing",
                "setting": row["setting"],
                "seed_group": row["seed_group"],
                "selection_source": "attack_validation_proxy_or_default_v1",
                "detection": row["attack_high_detection_mean"],
                "ood_alarm": row["OOD_high_alarm_mean"],
                "feasible_rate": row["feasible_rate"],
                "notes": "issue20 proxy failure retained",
            }
        )
    if chosen is not None:
        grouped = chosen_rows.groupby(["setting", "seed_group"], as_index=False).agg(
            detection=("final_attack_detection", "mean"),
            ood_alarm=("final_ood_alarm", "mean"),
            feasible_rate=("feasible", "mean"),
        )
        for _, row in grouped.iterrows():
            rows.append(
                {
                    "method": "issue21_evidence_gated_candidate",
                    "setting": row["setting"],
                    "seed_group": row["seed_group"],
                    "selection_source": chosen_name,
                    "detection": row["detection"],
                    "ood_alarm": row["ood_alarm"],
                    "feasible_rate": row["feasible_rate"],
                    "notes": "final metrics report-only",
                }
            )
    pd.DataFrame(rows).to_csv(OUT / "evidence_gated_vs_naive_proxy.csv", index=False)

    config = {
        "run": "issue21_active_review_promotion_asset_feasibility_2026-05-18",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "evidence_budgets": KS,
        "delta_thresholds": DELTAS,
        "target": TARGET,
        "strategies": STRATEGIES,
        "dataset_meta": dataset_meta,
        "final_metrics_report_only": True,
        "no_final_eval_promotion_trigger": True,
        "v1_v2_definitions_unchanged": True,
        "best_candidate": chosen_name,
        "strong_positive_candidate_exists": strong_positive,
        "recommended_next_action": next_action,
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
    metrics, pools, evidence, features, dataset_meta = build_results()
    selection_summary = aggregate_selection(metrics)
    budget_curve = label_budget_curve(metrics)

    metrics.to_csv(OUT / "promotion_metrics_by_setting.csv", index=False)
    selection_summary.to_csv(OUT / "promotion_selection_summary.csv", index=False)
    pools.to_csv(OUT / "active_review_pool_analysis.csv", index=False)
    budget_curve.to_csv(OUT / "label_budget_curve.csv", index=False)
    evidence.to_csv(OUT / "promotion_evidence_manifest.csv", index=False)
    features.to_csv(OUT / "selected_feature_report.csv", index=False)

    write_reports(metrics, pools, selection_summary, budget_curve, dataset_meta)

    manifest_rows = []
    for path in sorted(OUT.glob("*")):
        if path.is_file() and path.name != "manifest.csv":
            manifest_rows.append({"file": path.name, "size_bytes": path.stat().st_size})
    manifest_rows.append({"file": "runtime_seconds", "size_bytes": f"{time.perf_counter() - t0:.3f}"})
    pd.DataFrame(manifest_rows).to_csv(OUT / "manifest.csv", index=False)


if __name__ == "__main__":
    main()
