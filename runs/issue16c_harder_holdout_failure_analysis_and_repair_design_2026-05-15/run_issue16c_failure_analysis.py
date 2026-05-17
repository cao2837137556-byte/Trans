from __future__ import annotations

import csv
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs" / "issue16c_harder_holdout_failure_analysis_and_repair_design_2026-05-15"
ISSUE16 = ROOT / "runs" / "issue16_harder_holdout_second_environment_feasibility_2026-05-15"
ISSUE16B = ROOT / "runs" / "issue16b_harder_holdout_fixed_guard_validation_2026-05-15"
ISSUE11 = ROOT / "runs" / "issue11_fixed_config_ood_guard_lr_ablation_2026-05-14"
ISSUE14B = ROOT / "runs" / "issue14b_gda_minimal_score_recovery_for_arbitration_2026-05-15"
ISSUE15 = ROOT / "runs" / "issue15_review_budget_constrained_arbitration_2026-05-15"

FRONTEND_F2_ROOT = ROOT.parent / "kitnet-frontend-f2"
KITNET_ROOT = ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master"
REPO_DIR = ROOT / "repo"
OOD_DIR = REPO_DIR / "ood"
F2_OOD = FRONTEND_F2_ROOT / "repo" / "ood"
for path in [REPO_DIR, OOD_DIR, F2_OOD]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import frontend100_negative_recipe_rescoring as resc  # noqa: E402
import frontend_f2_v7_4_paired_holdout_fairness as v74  # noqa: E402
from original100_fewshot_official_control import split_contiguous  # noqa: E402


TARGET_ALARM = 0.01
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
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def md_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No rows._"
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, row in df.iterrows():
        vals: list[str] = []
        for col in cols:
            val = row[col]
            if isinstance(val, float):
                vals.append(f"{val:.6f}")
            else:
                vals.append(str(val))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def load_matrix(path: Path) -> np.ndarray:
    if path.suffix.lower() == ".npy":
        arr = np.load(path)
    else:
        arr = pd.read_csv(path, header=None).to_numpy(np.float32)
    if arr.ndim != 2:
        raise RuntimeError(f"Expected matrix from {path}, got {arr.shape}")
    return np.nan_to_num(arr.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)


def require_inputs() -> list[str]:
    required = [
        ISSUE16 / "summary.md",
        ISSUE16B / "summary.md",
        ISSUE16B / "method_comparison_summary.csv",
        ISSUE16B / "method_comparison_by_seed.csv",
        ISSUE16B / "fixed_guard_vs_plain_harder_holdout.csv",
        ISSUE16B / "support_id_provenance.csv",
        ISSUE16B / "threshold_provenance.csv",
        ISSUE16B / "harder_holdout_asset_report.csv",
        ISSUE11 / "method_comparison_summary.csv",
        ISSUE14B / "summary.md",
        ISSUE15 / "summary.md",
    ]
    return [str(path) for path in required if not path.exists()]


def quantile_rows(values: np.ndarray, prefix: str) -> dict[str, float]:
    values = np.asarray(values, dtype=np.float64)
    if values.size == 0:
        return {f"{prefix}_{name}": math.nan for name in ["mean", "std", "min", "max", "q01", "q05", "q10", "q25", "q50", "q75", "q90", "q95", "q99"]}
    qs = np.quantile(values, [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99])
    return {
        f"{prefix}_mean": float(np.mean(values)),
        f"{prefix}_std": float(np.std(values)),
        f"{prefix}_min": float(np.min(values)),
        f"{prefix}_max": float(np.max(values)),
        f"{prefix}_q01": float(qs[0]),
        f"{prefix}_q05": float(qs[1]),
        f"{prefix}_q10": float(qs[2]),
        f"{prefix}_q25": float(qs[3]),
        f"{prefix}_q50": float(qs[4]),
        f"{prefix}_q75": float(qs[5]),
        f"{prefix}_q90": float(qs[6]),
        f"{prefix}_q95": float(qs[7]),
        f"{prefix}_q99": float(qs[8]),
    }


def smd(source: np.ndarray, target: np.ndarray) -> np.ndarray:
    source = np.asarray(source, dtype=np.float64)
    target = np.asarray(target, dtype=np.float64)
    mean_diff = target.mean(axis=0) - source.mean(axis=0)
    pooled = np.sqrt((source.var(axis=0) + target.var(axis=0)) / 2.0) + 1e-8
    return mean_diff / pooled


def feature_auc_rows(source: np.ndarray, target: np.ndarray, max_features: int = 100) -> list[dict[str, Any]]:
    y = np.concatenate([np.zeros(len(source), dtype=np.int64), np.ones(len(target), dtype=np.int64)])
    rows = []
    for j in range(min(source.shape[1], max_features)):
        vals = np.concatenate([source[:, j], target[:, j]])
        try:
            auc = float(roc_auc_score(y, vals))
        except Exception:
            auc = math.nan
        rows.append({"feature_index": j, "feature_auc_target_vs_source": auc, "separability_abs_from_0_5": abs(auc - 0.5) if not math.isnan(auc) else math.nan})
    return rows


def compute_support_similarity(
    *,
    x_attack: np.ndarray,
    support_df: pd.DataFrame,
    specs_by_name: dict[str, dict[str, Any]],
    current_attack_eval: np.ndarray,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    by_seed_rows: list[dict[str, Any]] = []

    for (holdout, budget, seed), group in support_df.groupby(["holdout_name", "positive_budget", "seed"]):
        support_rows = group["selected_attack_row_id"].astype(int).to_numpy()
        spec = specs_by_name[str(holdout)]
        train_pool = np.asarray(spec["train_pool_idx"], dtype=np.int64)
        eval_rows = np.asarray(spec["attack_eval_idx"], dtype=np.int64)
        scaler = StandardScaler().fit(x_attack[train_pool])
        x_support = scaler.transform(x_attack[support_rows])
        x_eval = scaler.transform(x_attack[eval_rows])
        centroid = x_support.mean(axis=0, keepdims=True)
        centroid_dist = np.linalg.norm(x_eval - centroid, axis=1)
        nn = NearestNeighbors(n_neighbors=1, metric="euclidean").fit(x_support)
        nearest_dist = nn.kneighbors(x_eval, return_distance=True)[0].ravel()

        # Compare current primary eval to the same support as a rough reference; this is a diagnostic proxy only.
        x_current = scaler.transform(current_attack_eval)
        current_nearest = nn.kneighbors(x_current, return_distance=True)[0].ravel()
        current_centroid = np.linalg.norm(x_current - centroid, axis=1)

        row = {
            "setting": "harder_holdout",
            "holdout_name": str(holdout),
            "positive_budget": int(budget),
            "seed": int(seed),
            "seed_group": str(group["seed_group"].iloc[0]),
            "support_count": int(len(support_rows)),
            "eval_count": int(len(eval_rows)),
            **quantile_rows(centroid_dist, "eval_to_support_centroid_distance"),
            **quantile_rows(nearest_dist, "eval_to_nearest_support_distance"),
            "current_eval_nearest_support_mean_proxy": float(np.mean(current_nearest)),
            "current_eval_centroid_distance_mean_proxy": float(np.mean(current_centroid)),
            "holdout_vs_current_nearest_distance_ratio": float(np.mean(nearest_dist) / (np.mean(current_nearest) + 1e-8)),
        }
        by_seed_rows.append(row)

    by_seed = pd.DataFrame(by_seed_rows)
    if not by_seed.empty:
        summary = (
            by_seed.groupby(["holdout_name", "positive_budget", "seed_group"], as_index=False)
            .agg(
                n_seeds=("seed", "nunique"),
                eval_to_nearest_support_distance_mean=("eval_to_nearest_support_distance_mean", "mean"),
                eval_to_nearest_support_distance_max=("eval_to_nearest_support_distance_max", "max"),
                eval_to_support_centroid_distance_mean=("eval_to_support_centroid_distance_mean", "mean"),
                current_eval_nearest_support_mean_proxy=("current_eval_nearest_support_mean_proxy", "mean"),
                holdout_vs_current_nearest_distance_ratio=("holdout_vs_current_nearest_distance_ratio", "mean"),
            )
            .sort_values(["holdout_name", "positive_budget", "seed_group"])
        )
    else:
        summary = pd.DataFrame(summary_rows)
    return summary, by_seed


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    missing = require_inputs()
    if missing:
        write_text(OUT / "missing_input_report.md", "# Missing Input Report\n\n" + "\n".join(f"- {m}" for m in missing))
        raise RuntimeError(f"Missing required inputs: {missing}")

    issue16b_seed = pd.read_csv(ISSUE16B / "method_comparison_by_seed.csv")
    issue16b_summary = pd.read_csv(ISSUE16B / "method_comparison_summary.csv")
    issue16b_delta = pd.read_csv(ISSUE16B / "fixed_guard_vs_plain_harder_holdout.csv")
    support_df = pd.read_csv(ISSUE16B / "support_id_provenance.csv")
    threshold_df = pd.read_csv(ISSUE16B / "threshold_provenance.csv")
    issue11_summary = pd.read_csv(ISSUE11 / "method_comparison_summary.csv")

    with (ISSUE11 / "config.json").open("r", encoding="utf-8") as handle:
        issue11_config = json.load(handle)
    paths = issue11_config["paths"]
    x_id = load_matrix(Path(paths["original100_id"]))
    x_ood = load_matrix(Path(paths["original100_ood"]))
    x_attack = load_matrix(Path(paths["original100_attack"]))
    with Path(paths["stage2_manifest"]).open("r", encoding="utf-8-sig") as handle:
        manifest = json.load(handle)

    row_bins = v74.load_attack_bins(manifest)
    specs = [s for s in v74.make_holdout_specs(manifest, row_bins, min_eval_rows=300) if s["holdout_name"] in MAIN_HOLDOUTS]
    specs_by_name = {str(s["holdout_name"]): s for s in specs}
    high_idx = np.asarray(sorted(resc.build_stage2_indices(manifest)["high"]), dtype=np.int64)
    high_idx = high_idx[(high_idx >= 0) & (high_idx < len(x_attack))]
    current_split = split_contiguous(high_idx, 0.60, 0.20)
    current_attack_eval_rows = np.asarray(current_split["eval"], dtype=np.int64)
    current_attack_eval = x_attack[current_attack_eval_rows]

    # A. Score distribution analysis cannot be computed without row-level issue16b scores.
    score_missing_rows = []
    for holdout in MAIN_HOLDOUTS:
        for method in ["original100_plain_lr", "original100_fixed_guard_lr", "dA_only", "Transformer_only"]:
            for split in ["attack_eval", "ood_eval"]:
                score_missing_rows.append(
                    {
                        "setting": holdout,
                        "method": method,
                        "split": split,
                        "score_available": False,
                        "reason": "issue16b saved seed-level metrics and thresholds but did not save row-level scores; no model retraining is allowed in issue16c.",
                    }
                )
    pd.DataFrame(score_missing_rows).to_csv(OUT / "score_distribution_summary.csv", index=False)
    pd.DataFrame(score_missing_rows).to_csv(OUT / "score_margin_summary.csv", index=False)
    write_text(
        OUT / "missing_score_report.md",
        """
# Missing Row-Level Score Report

Issue16c does not recompute models or train new models. Issue16b saved seed-level metrics, thresholds, support provenance, and threshold provenance, but it did not save per-sample score arrays for the v7.4 harder holdouts.

Therefore score distribution and margin-to-threshold diagnostics cannot be computed honestly for `chrono_late_train_early_eval` or `holdout_bin_2` without rerunning or extending the issue16b scorer to persist row-level scores. This is a provenance gap, not a negative result.
""",
    )

    # B. Plain vs fixed guard diagnosis.
    issue16b_delta["setting"] = "harder_holdout"
    current_rows = []
    issue11_orig = issue11_summary[
        (issue11_summary["method"].isin(["original100_plain_lr", "original100_fixed_guard_lr"]))
        & (issue11_summary["positive_budget"].isin([16, 32]))
    ].copy()
    for (seed_group, budget), sub in issue11_orig.groupby(["seed_group", "positive_budget"]):
        plain = sub[sub["method"] == "original100_plain_lr"]
        fixed = sub[sub["method"] == "original100_fixed_guard_lr"]
        if plain.empty or fixed.empty:
            continue
        p = plain.iloc[0]
        f = fixed.iloc[0]
        current_rows.append(
            {
                "setting": "current_low_ood_primary",
                "holdout_name": "primary_split",
                "protocol": "guarded_id_calib_and_ood_val_target1pct",
                "positive_budget": int(budget),
                "seed_group": str(seed_group),
                "fixed_attack_high_detection_mean": float(f["attack_detection_mean"]),
                "fixed_attack_high_detection_min": float(f["attack_detection_min"]),
                "fixed_ood_high_alarm_mean": float(f["ood_alarm_mean"]),
                "fixed_ood_high_alarm_max": float(f["ood_alarm_max"]),
                "fixed_feasible_rate": float(f["feasible_rate"]),
                "plain_attack_high_detection_mean": float(p["attack_detection_mean"]),
                "plain_attack_high_detection_min": float(p["attack_detection_min"]),
                "plain_ood_high_alarm_mean": float(p["ood_alarm_mean"]),
                "plain_ood_high_alarm_max": float(p["ood_alarm_max"]),
                "plain_feasible_rate": float(p["feasible_rate"]),
                "delta_detection_mean_fixed_minus_plain": float(f["attack_detection_mean"] - p["attack_detection_mean"]),
                "delta_ood_alarm_mean_fixed_minus_plain": float(f["ood_alarm_mean"] - p["ood_alarm_mean"]),
                "delta_ood_alarm_max_fixed_minus_plain": float(f["ood_alarm_max"] - p["ood_alarm_max"]),
                "delta_feasible_rate_fixed_minus_plain": float(f["feasible_rate"] - p["feasible_rate"]),
            }
        )
    diagnosis_df = pd.concat([pd.DataFrame(current_rows), issue16b_delta], ignore_index=True, sort=False)
    diagnosis_df.to_csv(OUT / "plain_vs_fixed_guard_failure_diagnosis.csv", index=False)

    # C. Support-to-holdout similarity.
    support_summary, support_by_seed = compute_support_similarity(
        x_attack=x_attack,
        support_df=support_df,
        specs_by_name=specs_by_name,
        current_attack_eval=current_attack_eval,
    )
    support_summary.to_csv(OUT / "support_similarity_summary.csv", index=False)
    support_by_seed.to_csv(OUT / "support_similarity_by_seed.csv", index=False)

    # D. Feature drift analysis.
    drift_rows: list[dict[str, Any]] = []
    top_feature_rows: list[dict[str, Any]] = []
    composition_rows: list[dict[str, Any]] = []
    bin_to_rows: dict[int, list[int]] = {}
    if hasattr(row_bins, "items"):
        row_bin_iter = row_bins.items()
    else:
        row_bin_iter = enumerate(np.asarray(row_bins).tolist())
    for row_id, bin_id in row_bin_iter:
        if bin_id is None or int(bin_id) < 0:
            continue
        bin_to_rows.setdefault(int(bin_id), []).append(int(row_id))

    current_train_rows = np.asarray(current_split["train"], dtype=np.int64)
    current_eval_rows = np.asarray(current_split["eval"], dtype=np.int64)
    drift_pairs = [
        ("current_primary", "train_pool_vs_eval", current_train_rows, current_eval_rows),
    ]
    for spec in specs:
        drift_pairs.append(
            (
                str(spec["holdout_name"]),
                "train_pool_vs_eval",
                np.asarray(spec["train_pool_idx"], dtype=np.int64),
                np.asarray(spec["attack_eval_idx"], dtype=np.int64),
            )
        )
        eval_bins = [int(x) for x in spec.get("eval_bins", [])]
        train_bins = [int(x) for x in spec.get("train_bins", [])]
        for role, bins in [("train_bins", train_bins), ("eval_bins", eval_bins)]:
            rows = [r for b in bins for r in bin_to_rows.get(int(b), [])]
            composition_rows.append(
                {
                    "holdout_name": str(spec["holdout_name"]),
                    "role": role,
                    "bins": ",".join(str(b) for b in bins),
                    "row_count": len(rows),
                    "metadata_type": "stage2_attack_bin",
                    "notes": "Bin metadata available; attack family/device labels were not found in issue16b assets.",
                }
            )

    for setting, comparison, source_rows, target_rows in drift_pairs:
        source_x = x_attack[source_rows]
        target_x = x_attack[target_rows]
        drift = smd(source_x, target_x)
        abs_drift = np.abs(drift)
        aucs = feature_auc_rows(source_x, target_x, max_features=x_attack.shape[1])
        auc_df = pd.DataFrame(aucs)
        drift_rows.append(
            {
                "setting": setting,
                "comparison": comparison,
                "source_count": int(len(source_rows)),
                "target_count": int(len(target_rows)),
                "mean_abs_smd": float(np.mean(abs_drift)),
                "median_abs_smd": float(np.median(abs_drift)),
                "max_abs_smd": float(np.max(abs_drift)),
                "features_abs_smd_gt_0_5": int(np.sum(abs_drift > 0.5)),
                "features_abs_smd_gt_1_0": int(np.sum(abs_drift > 1.0)),
                "mean_feature_auc_abs_from_0_5": float(auc_df["separability_abs_from_0_5"].mean()),
                "max_feature_auc_abs_from_0_5": float(auc_df["separability_abs_from_0_5"].max()),
            }
        )
        top_idx = np.argsort(-abs_drift)[:15]
        for rank, idx in enumerate(top_idx, start=1):
            auc_row = auc_df[auc_df["feature_index"] == int(idx)].iloc[0]
            top_feature_rows.append(
                {
                    "setting": setting,
                    "comparison": comparison,
                    "rank": rank,
                    "feature_index": int(idx),
                    "smd_eval_minus_train": float(drift[idx]),
                    "abs_smd": float(abs_drift[idx]),
                    "source_mean": float(source_x[:, idx].mean()),
                    "target_mean": float(target_x[:, idx].mean()),
                    "feature_auc_target_vs_source": float(auc_row["feature_auc_target_vs_source"]),
                }
            )

    drift_df = pd.DataFrame(drift_rows)
    drift_df.to_csv(OUT / "feature_drift_summary.csv", index=False)
    pd.DataFrame(top_feature_rows).to_csv(OUT / "top_shifted_features.csv", index=False)
    pd.DataFrame(composition_rows).to_csv(OUT / "attack_subgroup_summary.csv", index=False)

    # F. Threshold and calibration diagnosis from available threshold/metric aggregates.
    thresh_summary = (
        issue16b_seed.groupby(["holdout_name", "method", "positive_budget", "seed_group"], as_index=False)
        .agg(
            threshold_mean=("threshold", "mean"),
            threshold_std=("threshold", "std"),
            threshold_min=("threshold", "min"),
            threshold_max=("threshold", "max"),
            id_calib_alarm_mean=("id_calib_alarm_at_selection", "mean"),
            ood_val_alarm_mean=("ood_val_alarm_at_selection", "mean"),
            attack_detection_mean=("attack_high_detection", "mean"),
            ood_alarm_mean=("ood_high_alarm", "mean"),
        )
        .sort_values(["holdout_name", "positive_budget", "seed_group", "method"])
    )
    thresh_summary.to_csv(OUT / "threshold_diagnosis.csv", index=False)
    curve_rows = []
    for target in [0.005, 0.01, 0.02]:
        curve_rows.append(
            {
                "ood_target": target,
                "status": "not_computed_no_row_level_scores",
                "reason": "Issue16b did not persist validation/eval score arrays; issue16c is not allowed to retrain models or select a new target from final eval.",
            }
        )
    pd.DataFrame(curve_rows).to_csv(OUT / "ood_target_diagnostic_curve.csv", index=False)

    # Taxonomy inputs.
    hb2_fixed_32 = issue16b_summary[
        (issue16b_summary["holdout_name"] == "holdout_bin_2")
        & (issue16b_summary["method"] == "original100_fixed_guard_lr")
        & (issue16b_summary["positive_budget"] == 32)
    ]
    chrono_fixed_32 = issue16b_summary[
        (issue16b_summary["holdout_name"] == "chrono_late_train_early_eval")
        & (issue16b_summary["method"] == "original100_fixed_guard_lr")
        & (issue16b_summary["positive_budget"] == 32)
    ]
    hb2_mean_det = float(hb2_fixed_32["attack_high_detection_mean"].min())
    chrono_mean_det = float(chrono_fixed_32["attack_high_detection_mean"].min())
    hb2_alarm = float(hb2_fixed_32["ood_high_alarm_max"].max())
    drift_hb2 = drift_df[drift_df["setting"] == "holdout_bin_2"].iloc[0]
    drift_chrono = drift_df[drift_df["setting"] == "chrono_late_train_early_eval"].iloc[0]
    support_hb2 = support_summary[(support_summary["holdout_name"] == "holdout_bin_2") & (support_summary["positive_budget"] == 32)]
    support_chrono = support_summary[(support_summary["holdout_name"] == "chrono_late_train_early_eval") & (support_summary["positive_budget"] == 32)]
    support_ratio_hb2 = float(support_hb2["holdout_vs_current_nearest_distance_ratio"].mean())
    support_ratio_chrono = float(support_chrono["holdout_vs_current_nearest_distance_ratio"].mean())

    taxonomy = [
        {
            "failure_type": "T1_attack_representation_shift",
            "support_level": "high" if drift_hb2["mean_abs_smd"] > drift_chrono["mean_abs_smd"] else "medium",
            "evidence": f"holdout_bin_2 mean_abs_smd={drift_hb2['mean_abs_smd']:.4f}, chrono mean_abs_smd={drift_chrono['mean_abs_smd']:.4f}.",
        },
        {
            "failure_type": "T2_support_mismatch",
            "support_level": "medium_to_uncertain",
            "evidence": (
                f"holdout_bin_2 support distance ratio={support_ratio_hb2:.4f}, chrono ratio={support_ratio_chrono:.4f}; "
                "nearest-distance proxy does not by itself prove bin2 supports are farther than chrono supports."
            ),
        },
        {
            "failure_type": "T3_guard_over_conservatism",
            "support_level": "low",
            "evidence": "Plain LR is also weak on holdout_bin_2 and fixed guard changes detection only slightly; guard is not the primary cause.",
        },
        {
            "failure_type": "T4_threshold_calibration_issue",
            "support_level": "medium",
            "evidence": "Only local calibration was run and OOD target curves cannot be computed without row-level scores; threshold transfer remains unresolved.",
        },
        {
            "failure_type": "T5_feature_drift_domain_shift",
            "support_level": "high",
            "evidence": f"holdout_bin_2 detection mean minimum={hb2_mean_det:.4f} while OOD alarm max={hb2_alarm:.4f}; failure is attack-side rather than OOD alarm.",
        },
        {
            "failure_type": "T6_metadata_label_alignment_risk",
            "support_level": "low_to_medium",
            "evidence": "Stage2 bin metadata is available and row-id alignment is clean, but attack family/device labels are missing.",
        },
        {
            "failure_type": "T7_base_detector_collapse_dominates",
            "support_level": "unknown",
            "evidence": "dA/Transformer harder-holdout row-level base scores were not available under issue16b; no delta-vs-base claim is possible.",
        },
    ]
    write_csv(OUT / "failure_taxonomy.csv", taxonomy)

    # Markdown reports.
    issue16b_core = issue16b_summary[
        (issue16b_summary["positive_budget"] == 32)
        & (issue16b_summary["method"].isin(["original100_plain_lr", "original100_fixed_guard_lr"]))
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
        OUT / "plain_vs_fixed_guard_failure_diagnosis.md",
        f"""
# Plain vs Fixed Guard Failure Diagnosis

## Harder-Holdout 32-Shot Core Rows

{md_table(issue16b_core)}

## Interpretation

- `holdout_bin_2` is weak for both plain LR and fixed-guard LR, so the failure is not primarily caused by the OOD guard.
- Fixed guard consistently lowers OOD high alarm relative to plain LR, but plain LR is already feasible under this local-calibration harder-holdout protocol.
- The guard's observed value in issue16b is alarm control, not attack-side recovery.
""",
    )
    write_text(
        OUT / "support_similarity_analysis.md",
        f"""
# Support Similarity Analysis

The analysis uses original100 features and issue16b support IDs. Distances are standardized using each holdout's attack train pool only, so final attack eval is not used to fit the distance scale.

## Summary

{md_table(support_summary)}

## Interpretation

`holdout_bin_2` shows weaker detection and should be treated as a support/attack-shift candidate. If its support-to-eval distance is larger than the chrono holdout, the next repair should target support diversity or representation coverage rather than increasing model complexity blindly.
""",
    )
    write_text(
        OUT / "feature_drift_analysis.md",
        f"""
# Feature Drift Analysis

Feature drift is measured with standardized mean difference between attack train-pool rows and attack eval rows in original100 space.

{md_table(drift_df)}

## Interpretation

The failure is attack-side: OOD high alarm stays far below 1%, while holdout_bin_2 attack detection collapses. Large feature shifts or high single-feature separability between train and eval indicate that the random few-shot support may not cover the harder attack window.
""",
    )
    write_text(
        OUT / "attack_composition_analysis.md",
        f"""
# Attack Composition Analysis

Stage2 attack-bin metadata is available, but richer attack-family/device metadata was not found in issue16b assets.

{md_table(pd.DataFrame(composition_rows))}

## Interpretation

`holdout_bin_2` is explicitly a leave-one-attack-window-out case: train bins exclude bin 2 and eval is bin 2. This supports the interpretation that the failure is a harder attack-window shift rather than an OOD alarm-control failure.
""",
    )
    write_text(
        OUT / "threshold_diagnosis.md",
        f"""
# Threshold Diagnosis

Issue16b used local ID calibration + OOD validation thresholding. Final OOD eval and attack eval were not used for threshold selection.

{md_table(thresh_summary.head(16))}

## Interpretation

- OOD high alarm remains below 1% on the hard holdouts, so the main failure is not OOD alarm overflow.
- The 0.5% / 1% / 2% diagnostic curve cannot be computed without row-level score arrays.
- OOD target sensitivity is a reasonable next diagnostic, but it must be run as a pre-registered analysis with saved row-level scores and no final-eval target selection.
""",
    )
    write_text(
        OUT / "failure_taxonomy.md",
        f"""
# Failure Taxonomy

{md_table(pd.DataFrame(taxonomy))}

## Main Diagnosis

The current evidence most strongly supports T1/T5: attack-side representation shift and feature/domain shift. T2 support mismatch remains a plausible repair target, but the nearest-support proxy alone does not prove it as the dominant cause. T3 guard over-conservatism is not the leading explanation because plain LR is also weak on `holdout_bin_2`.
""",
    )
    repair_rows = [
        {
            "priority": "P1",
            "repair_name": "support_diversity_selection",
            "target_failure_type": "T2_support_mismatch",
            "mechanism": "Select support positives to cover the attack train-pool feature space using only train-pool distances.",
            "required_assets": "original100 attack train pool, support provenance, no final eval access",
            "expected_benefit": "Improve coverage of holdout_bin_2-like attack variation without changing the model family.",
            "risk": "Support selection leakage if final attack eval influences selection.",
            "validation_without_leakage": "Pre-register selection rule on train pool only; evaluate on chrono and holdout_bin_2 unchanged.",
            "stopping_rule": "Stop if diversity support does not improve holdout_bin_2 detection without OOD alarm increase.",
        },
        {
            "priority": "P2",
            "repair_name": "ood_target_sensitivity_with_row_scores",
            "target_failure_type": "T4_threshold_calibration_issue",
            "mechanism": "Re-run scorer once with row-level score persistence and report pre-specified OOD targets 0.5/1/2%.",
            "required_assets": "issue16b deterministic scorer extended to save row-level scores",
            "expected_benefit": "Separate missed attack due to threshold stringency from representation failure.",
            "risk": "Threshold relaxation can be misread as post-hoc metric shopping.",
            "validation_without_leakage": "Report all targets, do not select one from final eval.",
            "stopping_rule": "If 2% still fails on holdout_bin_2, prioritize representation/support repair.",
        },
        {
            "priority": "P3",
            "repair_name": "source_rich_or_selected_representation_probe_on_holdout",
            "target_failure_type": "T1_attack_representation_shift",
            "mechanism": "Test whether source_rich or a small selected source_rich subset improves attack-window separability.",
            "required_assets": "source_rich v1 aligned to v7.4 hard holdout",
            "expected_benefit": "May improve representation coverage if original100 lacks features for bin 2.",
            "risk": "source_rich was unstable in earlier runs; do not make it the main claim without robust evidence.",
            "validation_without_leakage": "Use same supports, same fixed guard, no weight search.",
            "stopping_rule": "Stop if no improvement over original100 fixed guard on both holdouts.",
        },
        {
            "priority": "P4",
            "repair_name": "margin_or_deviation_gda_design_only",
            "target_failure_type": "T1_attack_representation_shift_and_T3_guard_tradeoff",
            "mechanism": "Design an attack-vs-OOD margin objective, but validate only after P1/P2 identify the failure mode.",
            "required_assets": "row-level scores, validation-only target selection, clean provenance",
            "expected_benefit": "Could protect attack margin while retaining OOD guard.",
            "risk": "Premature model complexity and overfitting to holdout_bin_2.",
            "validation_without_leakage": "Tune only on validation split; keep hard holdout final eval sealed.",
            "stopping_rule": "Do not run until support and threshold diagnostics are complete.",
        },
    ]
    write_csv(OUT / "repair_candidate_plan.csv", repair_rows)
    write_text(
        OUT / "repair_candidate_plan.md",
        f"""
# Repair Candidate Plan

{md_table(pd.DataFrame(repair_rows))}

## Unique First Choice

The first repair should be `support_diversity_selection`, not because support mismatch is already proven as the sole cause, but because it is the smallest leakage-safe test of the attack-window shift hypothesis. If train-pool-only support diversification cannot improve `holdout_bin_2`, the next step should move toward representation repair or row-level score diagnostics rather than increasing LR complexity blindly.
""",
    )
    write_text(
        OUT / "claim_boundary.md",
        """
# Claim Boundary

## Can Say

- Issue16b exposed attack-side harder-holdout generalization weakness.
- Fixed guard preserves low OOD alarm but does not automatically solve attack-side shift.
- Subsequent repair should target the identified failure type.
- Negative evidence is being used to drive targeted repair.

## Cannot Say

- Harder holdout success.
- LOW-GUARD fully generalizes.
- Issue16b failure is solved.
- Adapter upgrade already works.
- OOD target can be changed after looking at final eval.
- holdout_bin_2 is positive.
""",
    )
    risk_rows = [
        {"risk_name": "final eval tuning risk", "severity": "high", "reason": "Repair design is based on final hard-holdout weakness.", "mitigation": "Pre-register repair before rerun; no final-eval target selection."},
        {"risk_name": "overfitting repair to holdout_bin_2 risk", "severity": "high", "reason": "Targeting bin 2 can become cherry-pick tuning.", "mitigation": "Use train-pool-only rules and evaluate both pre-registered holdouts."},
        {"risk_name": "support selection leakage risk", "severity": "high", "reason": "Diversity selection can leak if eval features influence support.", "mitigation": "Use attack train pool only."},
        {"risk_name": "feature drift overclaim risk", "severity": "medium", "reason": "Feature drift is descriptive, not causal.", "mitigation": "Frame as diagnostic evidence."},
        {"risk_name": "threshold relaxation risk", "severity": "medium", "reason": "OOD target sensitivity can become post-hoc loosening.", "mitigation": "Report all pre-set targets."},
        {"risk_name": "metadata missing risk", "severity": "medium", "reason": "Attack family/device metadata not found.", "mitigation": "Use bin metadata only and avoid family-level claims."},
        {"risk_name": "repair complexity risk", "severity": "medium", "reason": "Jumping to neural GDA before diagnosis can weaken paper logic.", "mitigation": "Run P1/P2 first."},
    ]
    write_csv(OUT / "risk_register.csv", risk_rows)
    write_text(
        OUT / "recommended_next_action.md",
        """
# Recommended Next Action

## Unique First Choice

Run `issue17_support_diversity_selection_harder_holdout_2026-05-15`.

Purpose: test whether the holdout_bin_2 failure can be repaired by better support coverage. This is a minimal mechanism test for the attack-window shift hypothesis, not a claim that support mismatch is already the proven dominant cause. Use only the attack train pool for diversity selection, keep OOD weight=2 fixed, keep the same local-calibration protocol, and evaluate on both pre-registered hard holdouts.

## Backup

If support diversity fails, run a row-level score persistence pass and pre-registered OOD target sensitivity at 0.5%, 1%, and 2% to separate threshold stringency from representation failure.

## Do Not Do Yet

Do not upgrade to MLP/prototype/margin-GDA before support coverage and threshold diagnostics are complete.
""",
    )
    write_text(
        OUT / "protocol.md",
        """
# Issue16c Protocol

This run performs failure analysis and repair design only.

- No model training.
- No hyperparameter tuning.
- No split, seed, support, threshold, or scaler changes.
- No final-eval model selection.
- No manuscript modification.

Inputs are issue16b aggregate metrics, support provenance, threshold provenance, and original100 feature assets used by issue16b/issue11.
""",
    )
    write_text(
        OUT / "summary.md",
        f"""
# Issue16c Failure Analysis Summary

## Read Status

Issue16b was successfully read. No manuscript or historical result file was modified.

## Main Failure Type

The leading diagnosis is:

- T1 attack representation shift,
- T5 feature/domain shift.

T2 support mismatch remains a plausible repair target, but the nearest-support-distance proxy does not prove it as the dominant cause. T3 guard over-conservatism is not the leading explanation because plain LR is also weak on `holdout_bin_2`.

## Plain LR vs Fixed Guard

Fixed guard lowers OOD high alarm but does not materially improve detection. Plain LR is also feasible and weak on `holdout_bin_2`, so the failure is not caused mainly by the OOD guard.

## Support Similarity

Support-to-holdout distance diagnostics were generated in `support_similarity_summary.csv` and `support_similarity_by_seed.csv`. They do not by themselves prove support mismatch as the dominant cause, but they provide the audit basis for a leakage-safe support diversity repair.

## Feature Drift

Feature drift diagnostics were generated in `feature_drift_summary.csv` and `top_shifted_features.csv`. `holdout_bin_2` should be treated as an attack-window shift, not a low-OOD alarm-control failure.

## Threshold Diagnosis

OOD high alarm remains below 1%, so the main failure is attack-side missed detection. OOD target curves were not computed because issue16b did not save row-level score arrays, and issue16c is not allowed to retrain models.

## Recommended Repair

First choice: `support_diversity_selection`.

This is a minimal mechanism test, not a claim that support mismatch is already proven. Do not immediately upgrade LR to MLP/prototype/full neural GDA. The next experiment should test whether better train-pool support coverage repairs `holdout_bin_2` without loosening the low-alert constraint.
""",
    )
    write_text(
        OUT / "doc_update_patch_suggestion.md",
        """
# Doc Update Patch Suggestion

Suggested mainline docs note:

`issue16c diagnosed issue16b as an attack-side harder-holdout failure, likely driven by support mismatch / attack-window feature shift rather than OOD guard over-conservatism. Next planned repair is train-pool-only support diversity selection before any complex adapter upgrade.`
""",
    )
    manifest_rows = []
    for path in sorted(OUT.iterdir()):
        if path.is_file():
            manifest_rows.append({"asset_name": path.name, "file_path": str(path), "role": "issue16c output"})
    write_csv(OUT / "manifest.csv", manifest_rows)


if __name__ == "__main__":
    main()
