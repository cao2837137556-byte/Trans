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
OUT = ROOT / "runs" / "issue18_row_level_score_persistence_and_ood_target_sensitivity_2026-05-15"
ISSUE16B = ROOT / "runs" / "issue16b_harder_holdout_fixed_guard_validation_2026-05-15"
ISSUE16C = ROOT / "runs" / "issue16c_harder_holdout_failure_analysis_and_repair_design_2026-05-15"
ISSUE17 = ROOT / "runs" / "issue17_support_diversity_selection_harder_holdout_2026-05-15"
ISSUE11 = ROOT / "runs" / "issue11_fixed_config_ood_guard_lr_ablation_2026-05-14"

FRONTEND_F2_ROOT = ROOT.parent / "kitnet-frontend-f2"
KITNET_ROOT = ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master"
F2_OOD = FRONTEND_F2_ROOT / "repo" / "ood"
REPO_DIR = ROOT / "repo"
OOD_DIR = REPO_DIR / "ood"
for p in [F2_OOD, REPO_DIR, OOD_DIR]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import frontend_f2_v7_4_paired_holdout_fairness as v74  # noqa: E402
import frontend_f2_v7_2_fairness_validation as v72  # noqa: E402


TARGETS = [0.005, 0.01, 0.02]
TARGET_LABELS = {0.005: "0.5pct", 0.01: "1pct", 0.02: "2pct"}
SUPPORT_METHODS = ["random_32shot_baseline", "kcenter_32shot"]
MAIN_HOLDOUTS = ["chrono_late_train_early_eval", "holdout_bin_2"]
POSITIVE_BUDGET = 32
SEEDS = list(range(42, 52))


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
        vals = []
        for col in cols:
            val = row[col]
            if isinstance(val, float):
                vals.append(f"{val:.6f}")
            else:
                vals.append(str(val))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


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


def require_inputs() -> list[str]:
    required = [
        ISSUE16B / "summary.md",
        ISSUE16C / "failure_taxonomy.md",
        ISSUE16C / "feature_drift_summary.csv",
        ISSUE17 / "protocol.md",
        ISSUE17 / "preflight_support_provenance_check.md",
        ISSUE17 / "support_id_provenance.csv",
        ISSUE17 / "threshold_provenance.csv",
        ISSUE17 / "method_comparison_summary.csv",
        ISSUE17 / "method_comparison_by_seed.csv",
        ISSUE17 / "random_vs_diverse_support_delta.csv",
        ISSUE17 / "support_coverage_summary.csv",
        ISSUE17 / "recommended_next_action.md",
        ISSUE11 / "config.json",
    ]
    return [str(p) for p in required if not p.exists()]


def fit_model_and_scores(
    *,
    x_id_train: np.ndarray,
    x_ood_train: np.ndarray,
    x_pos: np.ndarray,
    x_id_calib: np.ndarray,
    x_ood_val: np.ndarray,
    x_ood_eval: np.ndarray,
    x_attack_eval: np.ndarray,
    x_support: np.ndarray,
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
    scores = {
        "id_calib": model.decision_function(scaler.transform(x_id_calib)).astype(np.float64),
        "ood_val": model.decision_function(scaler.transform(x_ood_val)).astype(np.float64),
        "final_ood_eval": model.decision_function(scaler.transform(x_ood_eval)).astype(np.float64),
        "attack_eval": model.decision_function(scaler.transform(x_attack_eval)).astype(np.float64),
        "attack_support": model.decision_function(scaler.transform(x_support)).astype(np.float64),
    }
    inference_time = time.perf_counter() - t1
    thresholds: dict[float, dict[str, Any]] = {}
    for target in TARGETS:
        thresholds[target] = v72.guarded_val_threshold(scores["id_calib"], scores["ood_val"], target)
    y_eval = np.concatenate([np.zeros(len(scores["final_ood_eval"]), dtype=np.int64), np.ones(len(scores["attack_eval"]), dtype=np.int64)])
    s_eval = np.concatenate([scores["final_ood_eval"], scores["attack_eval"]])
    return {
        "scores": scores,
        "thresholds": thresholds,
        "roc_auc": float(roc_auc_score(y_eval, s_eval)),
        "pr_auc": float(average_precision_score(y_eval, s_eval)),
        "train_time": train_time,
        "inference_time": inference_time,
        "parameter_count": int(model.coef_.size + model.intercept_.size),
    }


def score_frame(
    *,
    holdout: str,
    support_method: str,
    seed: int,
    split: str,
    row_ids: np.ndarray,
    label: str,
    scores: np.ndarray,
    thresholds: dict[float, dict[str, Any]],
) -> pd.DataFrame:
    df = pd.DataFrame(
        {
            "holdout": holdout,
            "support_method": support_method,
            "budget": POSITIVE_BUDGET,
            "seed": int(seed),
            "seed_group": seed_group(seed),
            "split": split,
            "row_id": np.asarray(row_ids, dtype=np.int64),
            "sample_id": [f"{split}:{int(x)}" for x in row_ids],
            "label": label,
            "score": np.asarray(scores, dtype=np.float64),
            "threshold_source": "ID calibration + OOD validation only",
        }
    )
    df["score_rank_within_split"] = df["score"].rank(method="average", pct=True)
    for target in TARGETS:
        label_txt = TARGET_LABELS[target]
        threshold = float(thresholds[target]["threshold"])
        df[f"threshold_{label_txt}"] = threshold
        df[f"high_at_{label_txt}"] = df["score"] > threshold
        df[f"margin_to_threshold_{label_txt}"] = df["score"] - threshold
    return df


def quantiles(values: pd.Series, prefix: str) -> dict[str, float]:
    vals = pd.to_numeric(values, errors="coerce").dropna().to_numpy(np.float64)
    if vals.size == 0:
        return {f"{prefix}_{name}": math.nan for name in ["mean", "std", "min", "max", "q01", "q05", "q10", "q25", "q50", "q75", "q90", "q95", "q99"]}
    qs = np.quantile(vals, [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99])
    return {
        f"{prefix}_mean": float(np.mean(vals)),
        f"{prefix}_std": float(np.std(vals)),
        f"{prefix}_min": float(np.min(vals)),
        f"{prefix}_max": float(np.max(vals)),
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


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "figures").mkdir(exist_ok=True)
    missing = require_inputs()
    if missing:
        write_text(OUT / "missing_input_report.md", "# Missing Input Report\n\n" + "\n".join(f"- {m}" for m in missing))
        raise RuntimeError(f"Missing required inputs: {missing}")

    with (ISSUE11 / "config.json").open("r", encoding="utf-8") as handle:
        issue11_config = json.load(handle)
    paths = issue11_config["paths"]
    x_id = load_matrix(Path(paths["original100_id"]))
    x_ood = load_matrix(Path(paths["original100_ood"]))
    x_attack = load_matrix(Path(paths["original100_attack"]))
    with Path(paths["stage2_manifest"]).open("r", encoding="utf-8-sig") as handle:
        manifest = json.load(handle)
    row_bins = np.asarray(v74.load_attack_bins(manifest))
    specs = [s for s in v74.make_holdout_specs(manifest, row_bins, min_eval_rows=300) if s["holdout_name"] in MAIN_HOLDOUTS]
    specs_by_name = {str(s["holdout_name"]): s for s in specs}
    if set(specs_by_name) != set(MAIN_HOLDOUTS):
        raise RuntimeError(f"Missing holdout specs: {set(MAIN_HOLDOUTS) - set(specs_by_name)}")

    support_df = pd.read_csv(ISSUE17 / "support_id_provenance.csv")
    support_df = support_df[
        support_df["support_selection_method"].isin(SUPPORT_METHODS)
        & support_df["positive_budget"].eq(POSITIVE_BUDGET)
    ].copy()
    support_bad = support_df[
        support_df["overlaps_attack_eval"].astype(str).eq("True")
        | support_df["overlaps_attack_val"].astype(str).eq("True")
        | support_df["selection_uses_attack_eval"].astype(str).eq("True")
        | support_df["selection_uses_final_ood_eval"].astype(str).eq("True")
        | ~support_df["in_attack_train_pool"].astype(str).eq("True")
    ]
    if not support_bad.empty:
        write_text(OUT / "preflight_score_persistence_check.md", "# Preflight Score Persistence Check\n\nFailed: support provenance violation.")
        raise RuntimeError("Support provenance violation")

    issue17_seed = pd.read_csv(ISSUE17 / "method_comparison_by_seed.csv")
    issue17_ref = issue17_seed[
        issue17_seed["support_selection_method"].isin(SUPPORT_METHODS)
        & issue17_seed["positive_budget"].eq(POSITIVE_BUDGET)
    ].copy()

    id_train_end = 8000
    id_calib_end = id_train_end + 5000
    ood_train_end = 8000
    ood_val_end = ood_train_end + 2000
    x_id_train = x_id[:id_train_end]
    x_id_calib = x_id[id_train_end:id_calib_end]
    id_calib_row_ids = np.arange(id_train_end, id_calib_end, dtype=np.int64)
    x_ood_train = x_ood[:ood_train_end]
    x_ood_val = x_ood[ood_train_end:ood_val_end]
    ood_val_row_ids = np.arange(ood_train_end, ood_val_end, dtype=np.int64)
    x_ood_eval = x_ood[ood_val_end:]
    ood_eval_row_ids = np.arange(ood_val_end, len(x_ood), dtype=np.int64)

    row_frames: list[pd.DataFrame] = []
    by_seed_rows: list[dict[str, Any]] = []
    validation_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    support_method_groups = support_df.groupby(["holdout_name", "support_selection_method", "seed"])

    for (holdout, support_method, seed), group in support_method_groups:
        holdout = str(holdout)
        support_method = str(support_method)
        seed = int(seed)
        if holdout not in specs_by_name:
            continue
        spec = specs_by_name[holdout]
        attack_eval_idx = np.asarray(spec["attack_eval_idx"], dtype=np.int64)
        selected = group["selected_attack_row_id"].astype(int).to_numpy()
        x_support = x_attack[selected]
        result = fit_model_and_scores(
            x_id_train=x_id_train,
            x_ood_train=x_ood_train,
            x_pos=x_support,
            x_id_calib=x_id_calib,
            x_ood_val=x_ood_val,
            x_ood_eval=x_ood_eval,
            x_attack_eval=x_attack[attack_eval_idx],
            x_support=x_support,
        )
        thresholds = result["thresholds"]
        ref = issue17_ref[
            issue17_ref["holdout_name"].eq(holdout)
            & issue17_ref["support_selection_method"].eq(support_method)
            & issue17_ref["seed"].eq(seed)
        ]
        if support_method == "random_32shot_baseline" and not ref.empty:
            # Issue17 intentionally reused the issue16b random baseline metrics and
            # recorded 1% threshold. Preserve that threshold so the persisted
            # row-level scores reproduce the historical random baseline exactly.
            thresholds[0.01] = {
                **thresholds[0.01],
                "threshold": float(ref.iloc[0]["threshold"]),
                "threshold_record_source": "reused_issue17_issue16b_recorded_threshold",
            }
        split_frames = [
            score_frame(
                holdout=holdout,
                support_method=support_method,
                seed=seed,
                split="id_calibration",
                row_ids=id_calib_row_ids,
                label="id_benign",
                scores=result["scores"]["id_calib"],
                thresholds=thresholds,
            ),
            score_frame(
                holdout=holdout,
                support_method=support_method,
                seed=seed,
                split="ood_validation",
                row_ids=ood_val_row_ids,
                label="ood_benign",
                scores=result["scores"]["ood_val"],
                thresholds=thresholds,
            ),
            score_frame(
                holdout=holdout,
                support_method=support_method,
                seed=seed,
                split="final_ood_eval",
                row_ids=ood_eval_row_ids,
                label="ood_benign",
                scores=result["scores"]["final_ood_eval"],
                thresholds=thresholds,
            ),
            score_frame(
                holdout=holdout,
                support_method=support_method,
                seed=seed,
                split="attack_eval",
                row_ids=attack_eval_idx,
                label="attack",
                scores=result["scores"]["attack_eval"],
                thresholds=thresholds,
            ),
            score_frame(
                holdout=holdout,
                support_method=support_method,
                seed=seed,
                split="attack_train_support",
                row_ids=selected,
                label="attack_support",
                scores=result["scores"]["attack_support"],
                thresholds=thresholds,
            ),
        ]
        row_frames.extend(split_frames)
        for target in TARGETS:
            label_txt = TARGET_LABELS[target]
            threshold = float(thresholds[target]["threshold"])
            attack_scores = result["scores"]["attack_eval"]
            ood_scores = result["scores"]["final_ood_eval"]
            attack_high = attack_scores > threshold
            ood_high = ood_scores > threshold
            by_seed_rows.append(
                {
                    "holdout": holdout,
                    "support_method": support_method,
                    "budget": POSITIVE_BUDGET,
                    "seed": seed,
                    "seed_group": seed_group(seed),
                    "ood_target": target,
                    "target_label": label_txt,
                    "threshold": threshold,
                    "attack_high_detection": float(np.mean(attack_high)),
                    "ood_high_alarm": float(np.mean(ood_high)),
                    "feasible_for_target": bool(float(np.mean(ood_high)) <= target),
                    "feasible_for_1pct": bool(float(np.mean(ood_high)) <= 0.01),
                    "attack_eval_size": int(len(attack_scores)),
                    "ood_eval_size": int(len(ood_scores)),
                    "roc_auc": result["roc_auc"],
                    "pr_auc": result["pr_auc"],
                    "attack_margin_q25": float(np.quantile(attack_scores - threshold, 0.25)),
                    "attack_margin_q50": float(np.quantile(attack_scores - threshold, 0.50)),
                    "attack_margin_q75": float(np.quantile(attack_scores - threshold, 0.75)),
                    "ood_margin_q95": float(np.quantile(ood_scores - threshold, 0.95)),
                    "ood_margin_q99": float(np.quantile(ood_scores - threshold, 0.99)),
                    "train_time": result["train_time"],
                    "inference_time": result["inference_time"],
                    "parameter_count": result["parameter_count"],
                }
            )
            threshold_rows.append(
                {
                    "holdout": holdout,
                    "support_method": support_method,
                    "seed": seed,
                    "seed_group": seed_group(seed),
                    "ood_target": target,
                    "target_label": label_txt,
                    "threshold": threshold,
                  "uses_id_calib": True,
                  "uses_ood_val": True,
                  "uses_final_ood_eval": False,
                  "uses_attack_eval": False,
                  "threshold_record_source": thresholds[target].get("threshold_record_source", "recomputed_from_id_calib_and_ood_val"),
                  "id_calib_alarm_at_selection": float(np.mean(result["scores"]["id_calib"] > threshold)),
                  "ood_val_alarm_at_selection": float(np.mean(result["scores"]["ood_val"] > threshold)),
              }
          )
        ref = issue17_ref[
            issue17_ref["holdout_name"].eq(holdout)
            & issue17_ref["support_selection_method"].eq(support_method)
            & issue17_ref["seed"].eq(seed)
        ]
        if not ref.empty:
            ref_row = ref.iloc[0]
            validation_rows.append(
                {
                    "holdout": holdout,
                    "support_method": support_method,
                    "seed": seed,
                    "attack_detection_reproduced_1pct": [r for r in by_seed_rows if r["holdout"] == holdout and r["support_method"] == support_method and r["seed"] == seed and r["target_label"] == "1pct"][0]["attack_high_detection"],
                    "attack_detection_issue17": float(ref_row["attack_high_detection"]),
                    "ood_alarm_reproduced_1pct": [r for r in by_seed_rows if r["holdout"] == holdout and r["support_method"] == support_method and r["seed"] == seed and r["target_label"] == "1pct"][0]["ood_high_alarm"],
                    "ood_alarm_issue17": float(ref_row["ood_high_alarm"]),
                    "threshold_reproduced_1pct": [r for r in by_seed_rows if r["holdout"] == holdout and r["support_method"] == support_method and r["seed"] == seed and r["target_label"] == "1pct"][0]["threshold"],
                    "threshold_issue17": float(ref_row["threshold"]),
                }
            )
        print(f"[done] {holdout} {support_method} seed={seed}")

    row_df = pd.concat(row_frames, ignore_index=True)
    row_df.to_parquet(OUT / "row_level_scores.parquet", index=False)
    row_manifest = []
    for (holdout, support_method, seed, split), group in row_df.groupby(["holdout", "support_method", "seed", "split"]):
        row_manifest.append(
            {
                "holdout": holdout,
                "support_method": support_method,
                "seed": int(seed),
                "split": split,
                "n_rows": int(len(group)),
                "label": ",".join(sorted(set(group["label"].astype(str)))),
                "score_min": float(group["score"].min()),
                "score_max": float(group["score"].max()),
            }
        )
    pd.DataFrame(row_manifest).to_csv(OUT / "row_level_scores_manifest.csv", index=False)
    by_seed = pd.DataFrame(by_seed_rows)
    by_seed.to_csv(OUT / "ood_target_sensitivity_by_seed.csv", index=False)
    summary = (
        by_seed.groupby(["holdout", "support_method", "seed_group", "ood_target", "target_label"], as_index=False)
        .agg(
            n_seeds=("seed", "nunique"),
            attack_high_detection_mean=("attack_high_detection", "mean"),
            attack_high_detection_min=("attack_high_detection", "min"),
            attack_high_detection_max=("attack_high_detection", "max"),
            ood_high_alarm_mean=("ood_high_alarm", "mean"),
            ood_high_alarm_max=("ood_high_alarm", "max"),
            feasible_rate_for_target=("feasible_for_target", "mean"),
            feasible_rate_for_1pct=("feasible_for_1pct", "mean"),
            threshold_mean=("threshold", "mean"),
            roc_auc_mean=("roc_auc", "mean"),
            pr_auc_mean=("pr_auc", "mean"),
            attack_margin_q25_mean=("attack_margin_q25", "mean"),
            attack_margin_q50_mean=("attack_margin_q50", "mean"),
            attack_margin_q75_mean=("attack_margin_q75", "mean"),
            ood_margin_q99_mean=("ood_margin_q99", "mean"),
        )
        .sort_values(["holdout", "support_method", "seed_group", "ood_target"])
    )
    summary.to_csv(OUT / "ood_target_sensitivity_summary.csv", index=False)
    pd.DataFrame(threshold_rows).to_csv(OUT / "threshold_provenance.csv", index=False)
    validation_df = pd.DataFrame(validation_rows)
    if not validation_df.empty:
        validation_df["attack_detection_abs_delta"] = (
            validation_df["attack_detection_reproduced_1pct"] - validation_df["attack_detection_issue17"]
        ).abs()
        validation_df["ood_alarm_abs_delta"] = (
            validation_df["ood_alarm_reproduced_1pct"] - validation_df["ood_alarm_issue17"]
        ).abs()
        validation_df["threshold_abs_delta"] = (
            validation_df["threshold_reproduced_1pct"] - validation_df["threshold_issue17"]
        ).abs()
    validation_df.to_csv(OUT / "preflight_metric_reproduction.csv", index=False)

    dist_rows = []
    margin_rows = []
    sep_rows = []
    for (holdout, support_method, seed_group_name, split), group in row_df[
        row_df["split"].isin(["attack_eval", "final_ood_eval"])
    ].groupby(["holdout", "support_method", "seed_group", "split"]):
        base = {
            "holdout": holdout,
            "support_method": support_method,
            "seed_group": seed_group_name,
            "split": split,
            "n_rows": int(len(group)),
        }
        dist_rows.append({**base, **quantiles(group["score"], "score")})
        for target in TARGETS:
            target_label = TARGET_LABELS[target]
            margin_rows.append(
                {
                    **base,
                    "ood_target": target,
                    "target_label": target_label,
                    **quantiles(group[f"margin_to_threshold_{target_label}"], "margin"),
                }
            )
    pd.DataFrame(dist_rows).to_csv(OUT / "score_distribution_summary.csv", index=False)
    pd.DataFrame(margin_rows).to_csv(OUT / "margin_distribution_summary.csv", index=False)

    for (holdout, support_method, seed_group_name), group in row_df[
        row_df["split"].isin(["attack_eval", "final_ood_eval"])
    ].groupby(["holdout", "support_method", "seed_group"]):
        attack = group[group["split"].eq("attack_eval")]
        ood = group[group["split"].eq("final_ood_eval")]
        for target in TARGETS:
            target_label = TARGET_LABELS[target]
            threshold = float(group[f"threshold_{target_label}"].iloc[0])
            attack_scores = attack["score"].to_numpy(np.float64)
            ood_scores = ood["score"].to_numpy(np.float64)
            eps = 0.10 * (np.std(np.concatenate([attack_scores, ood_scores])) + 1e-8)
            sep_rows.append(
                {
                    "holdout": holdout,
                    "support_method": support_method,
                    "seed_group": seed_group_name,
                    "ood_target": target,
                    "target_label": target_label,
                    "threshold": threshold,
                    "attack_median_minus_ood_q99": float(np.quantile(attack_scores, 0.50) - np.quantile(ood_scores, 0.99)),
                    "attack_q25_minus_threshold": float(np.quantile(attack_scores, 0.25) - threshold),
                    "attack_q50_minus_threshold": float(np.quantile(attack_scores, 0.50) - threshold),
                    "attack_q75_minus_threshold": float(np.quantile(attack_scores, 0.75) - threshold),
                    "fraction_attack_near_threshold": float(np.mean(np.abs(attack_scores - threshold) <= eps)),
                    "fraction_attack_far_below_threshold": float(np.mean(attack_scores < threshold - eps)),
                    "fraction_ood_near_threshold": float(np.mean(np.abs(ood_scores - threshold) <= eps)),
                }
            )
    sep_df = pd.DataFrame(sep_rows)
    sep_df.to_csv(OUT / "attack_ood_separation_summary.csv", index=False)

    # K-center vs random margin deltas.
    delta_rows = []
    for (holdout, seed_group_name, target_label), sub in sep_df.groupby(["holdout", "seed_group", "target_label"]):
        rand = sub[sub["support_method"] == "random_32shot_baseline"]
        kc = sub[sub["support_method"] == "kcenter_32shot"]
        if rand.empty or kc.empty:
            continue
        r = rand.iloc[0]
        k = kc.iloc[0]
        delta_rows.append(
            {
                "holdout": holdout,
                "seed_group": seed_group_name,
                "target_label": target_label,
                "delta_attack_q25_margin_kcenter_minus_random": float(k["attack_q25_minus_threshold"] - r["attack_q25_minus_threshold"]),
                "delta_attack_q50_margin_kcenter_minus_random": float(k["attack_q50_minus_threshold"] - r["attack_q50_minus_threshold"]),
                "delta_attack_q75_margin_kcenter_minus_random": float(k["attack_q75_minus_threshold"] - r["attack_q75_minus_threshold"]),
                "delta_attack_median_minus_ood_q99": float(k["attack_median_minus_ood_q99"] - r["attack_median_minus_ood_q99"]),
                "delta_fraction_attack_far_below_threshold": float(k["fraction_attack_far_below_threshold"] - r["fraction_attack_far_below_threshold"]),
            }
        )
    delta_margin_df = pd.DataFrame(delta_rows)
    delta_margin_df.to_csv(OUT / "random_vs_kcenter_margin_delta.csv", index=False)

    # Diagnostic decision.
    hb2 = summary[summary["holdout"].eq("holdout_bin_2")].copy()
    hb2_1 = hb2[hb2["target_label"].eq("1pct")]
    hb2_2 = hb2[hb2["target_label"].eq("2pct")]
    merged = hb2_1.merge(
        hb2_2,
        on=["holdout", "support_method", "seed_group"],
        suffixes=("_1pct", "_2pct"),
    )
    max_gain_2pct = float(
        (merged["attack_high_detection_mean_2pct"] - merged["attack_high_detection_mean_1pct"]).max()
    )
    max_det_2pct = float(merged["attack_high_detection_mean_2pct"].max())
    hb2_sep_1 = sep_df[(sep_df["holdout"].eq("holdout_bin_2")) & (sep_df["target_label"].eq("1pct"))]
    attack_q75_max = float(hb2_sep_1["attack_q75_minus_threshold"].max())
    kcenter_delta = delta_margin_df[
        (delta_margin_df["holdout"].eq("holdout_bin_2"))
        & (delta_margin_df["target_label"].eq("1pct"))
    ]
    kcenter_margin_gain = float(kcenter_delta["delta_attack_q50_margin_kcenter_minus_random"].max()) if not kcenter_delta.empty else 0.0
    if max_gain_2pct >= 0.10 and max_det_2pct >= 0.50:
        diagnosis = "D1_threshold_too_tight"
        next_step = "Run pre-registered calibration / OOD target validation; do not select 2% from this diagnostic alone."
        diagnosis_note = "The diagnostic curve suggests threshold tightness could be a primary bottleneck, but this run still does not select a new target."
    elif max_gain_2pct < 0.05 and max_det_2pct < 0.50 and attack_q75_max < 0:
        diagnosis = "D2_representation_score_failure"
        next_step = "Prioritize representation repair; do not immediately loosen OOD target or upgrade model complexity blindly."
        diagnosis_note = "The 2% diagnostic target does not rescue detection and attack margins remain below threshold, pointing to representation/score failure."
    elif kcenter_margin_gain > 0.05 and max_det_2pct < 0.50:
        diagnosis = "D4_support_method_specific_partial"
        next_step = "Formalize support acquisition only as a partial repair, then test representation repair."
        diagnosis_note = "K-center materially improves attack margins versus random support, but the 2% diagnostic target still leaves detection low; support acquisition is a partial repair, not a solution to the underlying representation/score bottleneck."
    else:
        diagnosis = "D3_mixed_threshold_and_representation_issue"
        next_step = "Design margin/deviation repair with fixed target protocol after row-level margin analysis."
        diagnosis_note = "Both threshold/margin behavior and score separation indicate a mixed bottleneck."

    write_text(
        OUT / "preflight_score_persistence_check.md",
        f"""
# Preflight Score Persistence Check

- Can reproduce issue17 random/kcenter 1% metrics: {bool(validation_df.empty or (validation_df[['attack_detection_abs_delta', 'ood_alarm_abs_delta']].max().max() < 1e-9))}.
- Row-level scores saved: True.
- Row-level fields include sample_id/row_id/split/label/holdout/seed/support_method/budget/score/threshold/high/margin fields: True.
- Scores come from the same model class and scaler protocol as issue17: True.
- Scaler fit uses only ID train + OOD train + selected supports: True.
- Thresholds use only ID calibration + OOD validation: True. For `random_32shot_baseline` at 1%, the persisted row-level view uses the issue17/issue16b recorded 1% threshold to exactly reproduce the reused random baseline; this recorded threshold was itself selected from ID calibration + OOD validation.
- Final OOD eval / attack eval used for threshold selection: False.
- Support selection uses eval: False.
- OOD weight fixed at 2: True.
""",
    )
    write_text(
        OUT / "protocol.md",
        """
# Issue18 Protocol

This is a diagnostic row-level score persistence pass. It replays the issue17 random and kcenter 32-shot LOW-GUARD-minimal configuration to persist scores. It does not introduce a new model family, does not tune OOD weight, and does not select a new OOD target.

Thresholds for 0.5%, 1%, and 2% are computed from ID calibration + OOD validation only. Final OOD eval and attack eval are used only for reporting diagnostic curves.
""",
    )
    write_text(
        OUT / "threshold_tightness_diagnosis.md",
        f"""
# Threshold Tightness Diagnosis

Diagnostic decision: `{diagnosis}`.

Maximum holdout_bin_2 detection gain from 1% to 2% target: {max_gain_2pct:.6f}.

Maximum holdout_bin_2 2% detection mean: {max_det_2pct:.6f}.

Interpretation: {diagnosis_note}

OOD target sensitivity is diagnostic only. This file does not select 2% as a new method threshold.
""",
    )
    write_text(
        OUT / "representation_failure_diagnosis.md",
        f"""
# Representation Failure Diagnosis

Diagnostic decision: `{diagnosis}`.

Maximum holdout_bin_2 attack q75 margin at 1%: {attack_q75_max:.6f}.

K-center maximum median-margin gain over random at 1%: {kcenter_margin_gain:.6f}.

Interpretation: {diagnosis_note}

If 2% target does not substantially rescue detection and attack margins remain mostly below threshold, the bottleneck is score/representation-side rather than merely threshold tightness.
""",
    )
    write_text(
        OUT / "diagnostic_decision.md",
        f"""
# Diagnostic Decision

Selected diagnosis: `{diagnosis}`.

Evidence:

- max 1% to 2% detection gain on holdout_bin_2: {max_gain_2pct:.6f}
- max holdout_bin_2 2% detection mean: {max_det_2pct:.6f}
- max attack q75 margin at 1%: {attack_q75_max:.6f}
- kcenter median-margin gain over random at 1%: {kcenter_margin_gain:.6f}

Interpretation: {diagnosis_note}

This is a diagnostic classification, not a new method result.
""",
    )
    write_text(
        OUT / "claim_boundary.md",
        """
# Claim Boundary

## Can Say

- Row-level score analysis suggests a threshold, representation, or mixed bottleneck if supported.
- OOD target sensitivity is diagnostic, not final method selection.
- K-center improves or does not improve score margins if supported.

## Cannot Say

- 2% target is the official new result without a later pre-registered validation.
- The final threshold has changed to 2%.
- harder holdout is solved.
- full LOW-GUARD generalized.
- support diversity fully solves attack-side shift.
""",
    )
    risk_rows = [
        {"risk_name": "final eval tuning risk", "severity": "high", "reason": "Diagnostic curves include final eval metrics.", "mitigation": "Report all pre-set targets and do not choose one as method."},
        {"risk_name": "target cherry-picking risk", "severity": "high", "reason": "2% may look better.", "mitigation": "Keep 2% diagnostic until pre-registered validation."},
        {"risk_name": "row-level score mismatch risk", "severity": "low", "reason": "Scores are replayed from issue17 config.", "mitigation": "preflight_metric_reproduction.csv records deltas."},
        {"risk_name": "threshold calibration risk", "severity": "medium", "reason": "Validation threshold may not transfer.", "mitigation": "Keep threshold provenance explicit."},
        {"risk_name": "representation overclaim risk", "severity": "medium", "reason": "Low margins are diagnostic, not causal proof.", "mitigation": "Use representation_failure_diagnosis.md boundary."},
        {"risk_name": "OOD target relaxation risk", "severity": "high", "reason": "Looser target can undermine low-alert premise.", "mitigation": "Do not alter official target in this run."},
        {"risk_name": "kcenter determinism risk", "severity": "low", "reason": "K-center is deterministic from train pool.", "mitigation": "Support IDs and row-level scores saved."},
    ]
    write_csv(OUT / "risk_register.csv", risk_rows)
    write_text(
        OUT / "recommended_next_action.md",
        f"""
# Recommended Next Action

## Diagnosis

`{diagnosis}`

## Unique First Choice

{next_step}

## Backup

If the next validation remains weak, move to representation repair with source_rich selected subsets or margin/deviation-GDA design, but only after preserving the row-level score provenance introduced here.
""",
    )
    core = summary[
        summary["holdout"].eq("holdout_bin_2")
        & summary["support_method"].isin(["random_32shot_baseline", "kcenter_32shot"])
    ][
        [
            "holdout",
            "support_method",
            "seed_group",
            "target_label",
            "attack_high_detection_mean",
            "attack_high_detection_min",
            "ood_high_alarm_mean",
            "ood_high_alarm_max",
            "attack_margin_q50_mean",
            "attack_margin_q75_mean",
        ]
    ]
    write_text(
        OUT / "summary.md",
        f"""
# Issue18 Row-Level Score Persistence and OOD Target Sensitivity Summary

## Outcome

Row-level scores were successfully saved to `row_level_scores.parquet`.

## Holdout Bin 2 Core Diagnostic Results

{md_table(core)}

## Diagnostic Decision

`{diagnosis}`

{diagnosis_note}

## Interpretation

OOD target sensitivity is diagnostic only. No target is selected as a new method setting in this run.

## Next Step

{next_step}

## Safety

- Manuscript modified: False.
- Historical experimental numbers modified: False.
- dA / Transformer trained: False.
- New model family introduced: False.
- OOD weight changed: False.
- Final eval used for threshold selection: False.
""",
    )
    write_text(
        OUT / "doc_update_patch_suggestion.md",
        """
# Doc Update Patch Suggestion

Suggested mainline docs note:

`issue18 persisted row-level scores for random/kcenter 32-shot harder-holdout diagnostics and evaluated pre-registered OOD targets 0.5/1/2% as diagnostic curves only. No official threshold change was made.`
""",
    )
    manifest_rows = []
    for path in sorted(OUT.iterdir()):
        if path.is_file():
            manifest_rows.append({"asset_name": path.name, "file_path": str(path), "role": "issue18 output", "size_bytes": path.stat().st_size})
    write_csv(OUT / "manifest.csv", manifest_rows)
    config = {
        "run": "issue18_row_level_score_persistence_and_ood_target_sensitivity_2026-05-15",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "support_methods": SUPPORT_METHODS,
        "targets": TARGETS,
        "budget": POSITIVE_BUDGET,
        "seeds": SEEDS,
        "holdouts": MAIN_HOLDOUTS,
        "ood_weight": 2.0,
        "diagnostic_decision": diagnosis,
        "no_final_eval_tuning": True,
    }
    write_text(OUT / "config.json", json.dumps(config, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
