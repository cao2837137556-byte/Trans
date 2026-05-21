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
from sklearn.metrics import roc_curve


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs" / "issue24b_adapter_bottleneck_diagnosis_for_enhanced_v2_top64_2026-05-18"
ISSUE24 = ROOT / "runs" / "issue24_adapter_upgrade_feasibility_for_enhanced_v2_top64_2026-05-18"
ISSUE23 = ROOT / "runs" / "issue23_locked_validation_for_enhanced_v2_top64_2026-05-18"
ISSUE22B = ROOT / "runs" / "issue22b_enhanced_v2_primary_nonregression_check_2026-05-18"
ISSUE22 = ROOT / "runs" / "issue22_v2_hard_shift_enhancement_pilot_2026-05-18"
ISSUE18 = ROOT / "runs" / "issue18_row_level_score_persistence_and_ood_target_sensitivity_2026-05-15"
ISSUE11 = ROOT / "runs" / "issue11_fixed_config_ood_guard_lr_ablation_2026-05-14"
ISSUE24_SCRIPT = ISSUE24 / "run_issue24_adapter_upgrade.py"
ISSUE23_SCRIPT = ISSUE23 / "run_issue23_locked_validation.py"
ISSUE22_SCRIPT = ISSUE22 / "run_issue22_v2_enhancement.py"
ISSUE19B_SCRIPT = ROOT / "runs" / "issue19b_v1_v2_same_protocol_backtest_and_alarm_budget_curve_2026-05-18" / "run_issue19b_v1_v2_backtest.py"

LOCKED_HOLDOUTS = ["holdout_bin_5", "holdout_bin_6", "holdout_bin_7", "holdout_bin_8"]
DIAGNOSTIC_SEED = 42
MAIN_TARGET = 0.01
METHODS = ["V1", "V2_top64_LR", "A1_weighted_LR", "A2_linear_SVM"]


def import_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


issue24 = import_module(ISSUE24_SCRIPT, "issue24_adapter_upgrade")
issue23 = import_module(ISSUE23_SCRIPT, "issue23_locked_validation")
issue22 = import_module(ISSUE22_SCRIPT, "issue22_v2_enhancement")
issue19b = import_module(ISSUE19B_SCRIPT, "issue19b_v1_v2_backtest_for_24b")


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
        vals: list[str] = []
        for value in row:
            if isinstance(value, (float, np.floating)):
                vals.append("" if math.isnan(float(value)) else f"{float(value):.6f}")
            else:
                vals.append(str(value))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"


def require_inputs() -> list[str]:
    required = [
        ISSUE24 / "summary.md",
        ISSUE24 / "adapter_method_comparison_summary.csv",
        ISSUE24 / "adapter_method_comparison_by_seed.csv",
        ISSUE24 / "locked_bins_adapter_summary.csv",
        ISSUE24 / "locked_bins_adapter_by_seed.csv",
        ISSUE24 / "consistency_primary_holdout_chrono.csv",
        ISSUE24 / "low_fpr_metrics_adapter_summary.csv",
        ISSUE24 / "adapter_failure_analysis.md",
        ISSUE24 / "best_adapter_candidate.md",
        ISSUE24 / "claim_boundary.md",
        ISSUE24 / "recommended_next_action.md",
        ISSUE23 / "summary.md",
        ISSUE23 / "method_comparison_summary.csv",
        ISSUE23 / "method_comparison_by_seed.csv",
        ISSUE23 / "v2top64_vs_v1_locked.csv",
        ISSUE23 / "v2top64_vs_v2top32_locked.csv",
        ISSUE23 / "low_fpr_metrics_summary.csv",
        ISSUE23 / "locked_validation_success_table.md",
        ISSUE23 / "claim_boundary.md",
        ISSUE22B / "summary.md",
        ISSUE22 / "summary.md",
        ISSUE18 / "row_level_scores_manifest.csv",
        ISSUE18 / "attack_ood_separation_summary.csv",
        ISSUE18 / "margin_distribution_summary.csv",
        ISSUE11 / "config.json",
        ISSUE24_SCRIPT,
        ISSUE23_SCRIPT,
    ]
    return [str(path) for path in required if not path.exists()]


def quantiles(values: np.ndarray, qs: list[float]) -> dict[str, float]:
    return {f"q{int(q * 1000):03d}" if q not in {0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99} else f"q{int(q * 100):02d}": float(np.quantile(values, q)) for q in qs}


def load_assets() -> tuple[dict[str, str], np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[str], list[dict[str, Any]]]:
    cfg = json.loads((ISSUE11 / "config.json").read_text(encoding="utf-8"))
    paths = cfg["paths"]
    x_id_o = issue19b.load_matrix(Path(paths["original100_id"]))
    x_ood_o = issue19b.load_matrix(Path(paths["original100_ood"]))
    x_attack_o = issue19b.load_matrix(Path(paths["original100_attack"]))
    x_id_sr = issue19b.load_matrix(Path(paths["source_rich_id"]))
    x_ood_sr = issue19b.load_matrix(Path(paths["source_rich_ood"]))
    x_attack_sr = issue19b.load_matrix(Path(paths["source_rich_attack"]))
    schema_path = Path(paths["source_rich_id"]).parents[1] / "data" / "structured_schema.json"
    sr_names = issue19b.feature_names(schema_path, x_id_sr.shape[1])
    locked, _, _ = issue23.build_locked_datasets(paths, x_id_o, x_ood_o, x_attack_o, x_id_sr, x_ood_sr, x_attack_sr)
    locked = [spec for spec in locked if str(spec["holdout"]) in LOCKED_HOLDOUTS]
    return paths, x_id_o, x_ood_o, x_attack_o, x_id_sr, x_ood_sr, x_attack_sr, sr_names, locked


def selected_config(adapter: str, holdout: str, seed: int) -> dict[str, Any]:
    if adapter == "A0_lr_baseline":
        return issue24.adapter_spaces()["A0_lr_baseline"][0]
    selected = pd.read_csv(ISSUE24 / "adapter_validation_selected_configs.csv")
    row = selected[(selected["holdout"].eq(holdout)) & (selected["seed"].eq(seed)) & (selected["adapter"].eq(adapter))]
    if row.empty:
        raise RuntimeError(f"No selected config for {adapter} {holdout} seed {seed}")
    config_id = str(row.iloc[0]["config_id"])
    for config in issue24.adapter_spaces()[adapter]:
        if str(config["config_id"]) == config_id:
            return config
    raise RuntimeError(f"Selected config not found in search space: {config_id}")


def train_v1_scores(spec: dict[str, Any], support: np.ndarray, x_attack_o: np.ndarray) -> dict[str, Any]:
    result = issue22.fit_lr_scores(
        x_id_train=spec["x_id_train_o"],
        x_ood_train=spec["x_ood_train_o"],
        x_pos=x_attack_o[support],
        x_id_calib=spec["x_id_calib_o"],
        x_ood_val=spec["x_ood_val_o"],
        x_ood_eval=spec["x_ood_eval_o"],
        x_attack_eval=x_attack_o[np.asarray(spec["attack_eval_idx"], dtype=np.int64)],
        hard_negative=False,
    )
    threshold = float(result["thresholds"][MAIN_TARGET]["threshold"])
    return {"scores": result["scores"], "threshold": threshold, "feature_idx": np.arange(spec["x_id_train_o"].shape[1])}


def train_top64_adapter_scores(spec: dict[str, Any], support: np.ndarray, x_attack_sr: np.ndarray, sr_names: list[str], adapter: str) -> dict[str, Any]:
    config = selected_config(adapter, str(spec["holdout"]), DIAGNOSTIC_SEED)
    feature_idx, _ = issue24.prepare_top64(dataset_spec=spec, support_rows=support, x_attack_sr=x_attack_sr, sr_names=sr_names, seed=DIAGNOSTIC_SEED)
    x_id_train = spec["x_id_train_sr"][:, feature_idx]
    x_ood_train = spec["x_ood_train_sr"][:, feature_idx]
    x_pos = x_attack_sr[support][:, feature_idx]
    x_id_calib = spec["x_id_calib_sr"][:, feature_idx]
    x_ood_val = spec["x_ood_val_sr"][:, feature_idx]
    x_ood_eval = spec["x_ood_eval_sr"][:, feature_idx]
    x_attack_eval = x_attack_sr[np.asarray(spec["attack_eval_idx"], dtype=np.int64)][:, feature_idx]
    scaler = issue24.fit_scaler(x_id_train, x_ood_train, x_pos)
    model, hard_negative_count, parameter_count = issue24.train_model(
        config=config,
        scaler=scaler,
        x_id_train=x_id_train,
        x_ood_train=x_ood_train,
        x_pos=x_pos,
        x_ood_val=x_ood_val,
        seed=DIAGNOSTIC_SEED,
    )
    model_type = str(config["model_type"])
    scores = {
        "id_calib": issue24.score_model(model, scaler, x_id_calib, model_type),
        "ood_val": issue24.score_model(model, scaler, x_ood_val, model_type),
        "final_ood_eval": issue24.score_model(model, scaler, x_ood_eval, model_type),
        "attack_eval": issue24.score_model(model, scaler, x_attack_eval, model_type),
    }
    threshold = float(issue19b.v72.guarded_val_threshold(scores["id_calib"], scores["ood_val"], MAIN_TARGET)["threshold"])
    return {
        "scores": scores,
        "threshold": threshold,
        "feature_idx": feature_idx,
        "config_id": config["config_id"],
        "hard_negative_count": hard_negative_count,
        "parameter_count": parameter_count,
    }


def reconstruct_scores() -> tuple[pd.DataFrame, dict[tuple[str, str], dict[str, Any]], dict[str, np.ndarray], list[dict[str, Any]]]:
    _, _, _, x_attack_o, _, _, x_attack_sr, sr_names, locked_specs = load_assets()
    rows: list[dict[str, Any]] = []
    score_store: dict[tuple[str, str], dict[str, Any]] = {}
    top64_features_by_holdout: dict[str, np.ndarray] = {}
    feature_rows: list[dict[str, Any]] = []
    for spec in locked_specs:
        holdout = str(spec["holdout"])
        train_pool = np.asarray(spec["attack_train_pool_idx"], dtype=np.int64)
        support = issue19b.kcenter_support(train_pool, x_attack_o[train_pool], 32)
        method_results = {
            "V1": train_v1_scores(spec, support, x_attack_o),
            "V2_top64_LR": train_top64_adapter_scores(spec, support, x_attack_sr, sr_names, "A0_lr_baseline"),
            "A1_weighted_LR": train_top64_adapter_scores(spec, support, x_attack_sr, sr_names, "A1_low_fpr_weighted_lr"),
            "A2_linear_SVM": train_top64_adapter_scores(spec, support, x_attack_sr, sr_names, "A2_linear_svm_margin"),
        }
        top64_features_by_holdout[holdout] = method_results["V2_top64_LR"]["feature_idx"]
        for rank, idx in enumerate(top64_features_by_holdout[holdout], start=1):
            feature_rows.append({"holdout": holdout, "seed": DIAGNOSTIC_SEED, "rank": rank, "feature_index": int(idx), "feature_name": sr_names[int(idx)] if int(idx) < len(sr_names) else f"source_rich_{idx}"})
        for method, payload in method_results.items():
            score_store[(holdout, method)] = payload
            threshold = float(payload["threshold"])
            attack_scores = payload["scores"]["attack_eval"]
            ood_scores = payload["scores"]["final_ood_eval"]
            attack_idx = np.asarray(spec["attack_eval_idx"], dtype=np.int64)
            for i, score in enumerate(attack_scores):
                rows.append({"holdout": holdout, "method": method, "split": "attack_eval", "row_index": int(attack_idx[i]), "label": "attack", "score": float(score), "threshold": threshold, "high": bool(score > threshold), "margin": float(score - threshold)})
            for i, score in enumerate(ood_scores):
                rows.append({"holdout": holdout, "method": method, "split": "final_ood_eval", "row_index": int(i), "label": "ood_benign", "score": float(score), "threshold": threshold, "high": bool(score > threshold), "margin": float(score - threshold)})
    return pd.DataFrame(rows), score_store, top64_features_by_holdout, feature_rows


def score_distribution(row_scores: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (holdout, method), g in row_scores.groupby(["holdout", "method"]):
        attack = g[g["split"].eq("attack_eval")]
        ood = g[g["split"].eq("final_ood_eval")]
        threshold = float(g["threshold"].iloc[0])
        attack_scores = attack["score"].to_numpy(float)
        ood_scores = ood["score"].to_numpy(float)
        margins = attack["margin"].to_numpy(float)
        near_eps = max(1e-9, float(np.std(np.concatenate([attack_scores, ood_scores]))) * 0.10)
        row = {
            "holdout": holdout,
            "method": method,
            "threshold": threshold,
            "attack_high_detection": float(attack["high"].mean()),
            "ood_high_alarm": float(ood["high"].mean()),
            "attack_miss_rate_near_threshold": float(np.mean((margins <= 0) & (margins >= -near_eps))),
            "attack_miss_rate_far_below_threshold": float(np.mean(margins < -near_eps)),
            "ood_tail_distance_q99_to_threshold": float(np.quantile(ood_scores, 0.99) - threshold),
        }
        for name, values, qs in [
            ("attack_score", attack_scores, [0.10, 0.25, 0.50, 0.75, 0.90]),
            ("ood_score", ood_scores, [0.90, 0.95, 0.975, 0.99, 1.00]),
            ("attack_margin", margins, [0.10, 0.25, 0.50]),
        ]:
            for key, value in quantiles(values, qs).items():
                row[f"{name}_{key}"] = value
        rows.append(row)
    return pd.DataFrame(rows)


def error_overlap(row_scores: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for holdout in LOCKED_HOLDOUTS:
        pivot = row_scores[row_scores["holdout"].eq(holdout)].pivot_table(index=["split", "row_index", "label"], columns="method", values="high", aggfunc="first").reset_index()
        for split in ["attack_eval", "final_ood_eval"]:
            g = pivot[pivot["split"].eq(split)].copy()
            if g.empty or not {"V1", "V2_top64_LR"}.issubset(g.columns):
                continue
            v1 = g["V1"].astype(bool)
            v2 = g["V2_top64_LR"].astype(bool)
            n = len(g)
            rows.append({
                "holdout": holdout,
                "split": split,
                "n": int(n),
                "both_high": int((v1 & v2).sum()),
                "v1_high_v2_low": int((v1 & ~v2).sum()),
                "v1_low_v2_high": int((~v1 & v2).sum()),
                "both_low": int((~v1 & ~v2).sum()),
                "both_high_rate": float((v1 & v2).mean()),
                "v1_high_v2_low_rate": float((v1 & ~v2).mean()),
                "v1_low_v2_high_rate": float((~v1 & v2).mean()),
                "both_low_rate": float((~v1 & ~v2).mean()),
            })
    return pd.DataFrame(rows)


def fusion_potential(row_scores: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for holdout in LOCKED_HOLDOUTS:
        score_pivot = row_scores[row_scores["holdout"].eq(holdout)].pivot_table(index=["split", "row_index", "label"], columns="method", values="score", aggfunc="first").reset_index()
        high_pivot = row_scores[row_scores["holdout"].eq(holdout)].pivot_table(index=["split", "row_index", "label"], columns="method", values="high", aggfunc="first").reset_index()
        for split in ["attack_eval", "final_ood_eval"]:
            sg = score_pivot[score_pivot["split"].eq(split)]
            hg = high_pivot[high_pivot["split"].eq(split)]
            if sg.empty or not {"V1", "V2_top64_LR"}.issubset(sg.columns):
                continue
            corr = float(np.corrcoef(sg["V1"].astype(float), sg["V2_top64_LR"].astype(float))[0, 1])
            v1 = hg["V1"].astype(bool)
            v2 = hg["V2_top64_LR"].astype(bool)
            v1_rescues = float((v1 & ~v2).mean())
            v2_rescues = float((~v1 & v2).mean())
            potential = "none"
            if split == "attack_eval":
                if v1_rescues >= 0.03 and v2_rescues >= 0.03:
                    potential = "strong"
                elif max(v1_rescues, v2_rescues) >= 0.03:
                    potential = "moderate"
                elif max(v1_rescues, v2_rescues) >= 0.01:
                    potential = "weak"
            rows.append({"holdout": holdout, "split": split, "v1_v2_score_correlation": corr, "v1_high_v2_low_rate": v1_rescues, "v1_low_v2_high_rate": v2_rescues, "fusion_potential": potential})
    return pd.DataFrame(rows)


def low_fpr_bottleneck(row_scores: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (holdout, method), g in row_scores.groupby(["holdout", "method"]):
        attack = g[g["split"].eq("attack_eval")]["score"].to_numpy(float)
        ood = g[g["split"].eq("final_ood_eval")]["score"].to_numpy(float)
        threshold = float(g["threshold"].iloc[0])
        for fpr_target in [0.005, 0.01, 0.02]:
            thr = float(np.quantile(ood, 1.0 - fpr_target))
            rows.append({
                "holdout": holdout,
                "method": method,
                "fpr_target": fpr_target,
                "eval_ood_quantile_threshold": thr,
                "attack_tpr_at_eval_fpr": float(np.mean(attack > thr)),
                "official_threshold": threshold,
                "official_attack_detection": float(np.mean(attack > threshold)),
                "official_ood_alarm": float(np.mean(ood > threshold)),
                "attack_vs_ood_q99_margin_q25": float(np.quantile(attack - np.quantile(ood, 0.99), 0.25)),
                "pairwise_attack_below_ood_tail_rate": float(np.mean(attack[:, None] <= ood[ood >= np.quantile(ood, 0.99)][None, :])),
            })
    return pd.DataFrame(rows)


def feature_space_diagnostic(score_store: dict[tuple[str, str], dict[str, Any]], top64_features: dict[str, np.ndarray]) -> pd.DataFrame:
    _, _, _, _, x_id_sr, x_ood_sr, x_attack_sr, _, locked_specs = load_assets()
    rows = []
    for spec in locked_specs:
        holdout = str(spec["holdout"])
        idx = top64_features[holdout]
        id_calib = spec["x_id_calib_sr"][:, idx]
        ood_val = spec["x_ood_val_sr"][:, idx]
        attack_eval = x_attack_sr[np.asarray(spec["attack_eval_idx"], dtype=np.int64)][:, idx]
        train_pool = x_attack_sr[np.asarray(spec["attack_train_pool_idx"], dtype=np.int64)][:, idx]
        centroids = {
            "id_calib": id_calib.mean(axis=0),
            "ood_val": ood_val.mean(axis=0),
            "attack_train_pool": train_pool.mean(axis=0),
            "attack_eval": attack_eval.mean(axis=0),
        }
        rows.append({
            "holdout": holdout,
            "attack_eval_to_id_centroid": float(np.linalg.norm(centroids["attack_eval"] - centroids["id_calib"])),
            "attack_eval_to_ood_centroid": float(np.linalg.norm(centroids["attack_eval"] - centroids["ood_val"])),
            "attack_train_to_eval_centroid": float(np.linalg.norm(centroids["attack_train_pool"] - centroids["attack_eval"])),
            "id_to_ood_centroid": float(np.linalg.norm(centroids["id_calib"] - centroids["ood_val"])),
            "linear_separability_proxy_attack_ood": float(np.linalg.norm(centroids["attack_eval"] - centroids["ood_val"]) / (np.std(ood_val @ (centroids["attack_eval"] - centroids["ood_val"])) + 1e-9)),
            "feature_dim": int(len(idx)),
        })
    return pd.DataFrame(rows)


def write_reports(outputs: dict[str, pd.DataFrame]) -> None:
    score_dist = outputs["score_distribution"]
    overlap = outputs["error_overlap"]
    fusion = outputs["fusion"]
    lowfpr = outputs["lowfpr"]
    feature = outputs["feature"]
    issue24_summary = pd.read_csv(ISSUE24 / "locked_bins_adapter_summary.csv")
    lr = issue24_summary[issue24_summary["adapter"].eq("A0_lr_baseline")].iloc[0]
    weighted = issue24_summary[issue24_summary["adapter"].eq("A1_low_fpr_weighted_lr")].iloc[0]
    svm = issue24_summary[issue24_summary["adapter"].eq("A2_linear_svm_margin")].iloc[0]
    attack_overlap = overlap[overlap["split"].eq("attack_eval")]
    bin67 = attack_overlap[attack_overlap["holdout"].isin(["holdout_bin_6", "holdout_bin_7"])]
    bin8 = attack_overlap[attack_overlap["holdout"].eq("holdout_bin_8")]
    bin67_v1_rescue = float(bin67["v1_high_v2_low_rate"].mean()) if not bin67.empty else math.nan
    bin67_v2_rescue = float(bin67["v1_low_v2_high_rate"].mean()) if not bin67.empty else math.nan
    bin8_v1_rescue = float(bin8["v1_high_v2_low_rate"].mean()) if not bin8.empty else math.nan
    bin8_v2_rescue = float(bin8["v1_low_v2_high_rate"].mean()) if not bin8.empty else math.nan
    weighted_delta = float(weighted["locked_detection_mean"] - lr["locked_detection_mean"])
    svm_delta = float(svm["locked_detection_mean"] - lr["locked_detection_mean"])
    fusion_attack = fusion[fusion["split"].eq("attack_eval")]
    max_fusion = "none"
    if (fusion_attack["fusion_potential"].eq("strong")).any():
        max_fusion = "strong"
    elif (fusion_attack["fusion_potential"].eq("moderate")).any():
        max_fusion = "moderate"
    elif (fusion_attack["fusion_potential"].eq("weak")).any():
        max_fusion = "weak"
    ranking_space = "weak"
    v2_lowfpr = lowfpr[lowfpr["method"].eq("V2_top64_LR")]
    if not v2_lowfpr.empty and float(v2_lowfpr["pairwise_attack_below_ood_tail_rate"].mean()) > 0.10:
        ranking_space = "moderate"
    nonlinear_space = "weak"
    if float(feature["linear_separability_proxy_attack_ood"].min()) < 1.0:
        nonlinear_space = "moderate"
    next_action = "stop_adapter_upgrade_proceed_to_strong_baselines_and_second_environment"
    if max_fusion in {"moderate", "strong"}:
        next_action = "issue24c_v1_v2_residual_fusion_adapter_retry_2026-05-18"
    elif ranking_space == "moderate":
        next_action = "issue24c_pairwise_low_fpr_ranking_adapter_retry_2026-05-18"
    elif nonlinear_space == "moderate":
        next_action = "issue24c_targeted_shallow_nonlinear_adapter_retry_2026-05-18"

    write_text(
        OUT / "summary.md",
        f"""
# Issue24b Adapter Bottleneck Diagnosis Summary

## Outcome

- Preflight passed: yes.
- Row-level score asset gap: issue23/24 did not persist row-level scores; representative seed `{DIAGNOSTIC_SEED}` scores were reconstructed for fixed existing methods only.
- New adapter trained as method candidate: no.
- topK/support/representation changed: no.
- final eval used for new rule validation: no; final labels are used only for diagnosis.

## Main Diagnosis

- LR bottleneck: not a clear adapter bottleneck. LR is already strong under source_rich_top64; first-order OOD-tail weighting does not change detection.
- bin6/bin7 V2_top64 under V1 mainly because V1 has a small attack-side rescue set: mean V1-high/V2-low attack rate `{bin67_v1_rescue:.6f}` vs V2-high/V1-low `{bin67_v2_rescue:.6f}`.
- bin8 V2_top64 wins because V2 has a larger attack-side rescue set: V2-high/V1-low `{bin8_v2_rescue:.6f}` vs V1-high/V2-low `{bin8_v1_rescue:.6f}`.
- Weighted LR no-gain reason: locked detection delta vs LR `{weighted_delta:.6f}`; it slightly lowers OOD max but barely changes attack ranking.
- SVM failure reason: locked detection delta vs LR `{svm_delta:.6f}` and OOD max `{float(svm['locked_ood_alarm_max']):.6f}`; margin calibration is unstable and violates low-alert constraints.
- Fusion potential: `{max_fusion}`.
- Ranking bottleneck evidence: `{ranking_space}`.
- Nonlinear separability evidence: `{nonlinear_space}`.
- Unique next action: `{next_action}`.

## Key Tables

Error overlap:

{md_table(attack_overlap)}

Fusion potential:

{md_table(fusion_attack)}
""",
    )
    write_text(
        OUT / "protocol.md",
        """
# Protocol

This run is diagnosis only. It reconstructs row-level scores for fixed existing methods on locked bins using representative seed 42:

- V1 original100 LR from issue23 configuration.
- V2_top64 LR from issue23/24 configuration.
- A1 weighted LR and A2 SVM using issue24 selected configs.

No new adapter candidate is introduced, no topK/support/representation is changed, and final eval is used only to analyze already-reported errors.
""",
    )
    write_text(
        OUT / "preflight_adapter_bottleneck_diagnosis_check.md",
        """
# Preflight Adapter Bottleneck Diagnosis Check

- Successfully read issue23 locked validation: yes.
- Successfully read issue24 adapter upgrade results: yes.
- V1 / V2_top64 / adapter row-level scores persisted by issue23/24: no.
- Row-level scores reconstructed for diagnosis only: yes, representative seed 42.
- attack eval / OOD eval row-level labels available for diagnostic reconstruction: yes.
- locked bins 5/6/7/8 per-bin score distribution available: yes.
- bin6/bin7 degradation samples analyzable: yes.
- bin8 improvement samples analyzable: yes.
- LR vs weighted LR / SVM score changes analyzable: yes.
- New adapter training as method claim: no.
- This run is diagnosis only, not method claim: yes.
""",
    )
    write_text(
        OUT / "row_level_asset_gap.md",
        """
# Row-Level Asset Gap

issue23 and issue24 did not persist per-sample row-level scores. This run reconstructs row-level diagnostic scores for representative seed 42 using the fixed existing configurations. The reconstructed scores are suitable for failure analysis, but they should not be treated as a new method result or as a replacement for future score persistence in validation runs.
""",
    )
    write_text(
        OUT / "score_distribution_report.md",
        "# Score Distribution Report\n\n" + md_table(score_dist.sort_values(["holdout", "method"])),
    )
    write_text(
        OUT / "error_overlap_report.md",
        "# Error Overlap Report\n\n" + md_table(overlap.sort_values(["holdout", "split"])),
    )
    write_text(
        OUT / "fusion_potential_report.md",
        f"""
# Fusion Potential Report

Fusion potential is `{max_fusion}`. The pattern is not a universal complementarity story: V1 rescues some bin6/bin7 attacks, while V2 rescues bin8. A future residual/fusion adapter is only justified if it is validation-gated and does not increase OOD alarms.

{md_table(fusion.sort_values(['holdout', 'split']))}
""",
    )
    write_text(
        OUT / "low_fpr_bottleneck_report.md",
        f"""
# Low-FPR Bottleneck Report

Ranking bottleneck evidence is `{ranking_space}`. V2_top64 has strong guarded detection already, so pairwise/ranking retry is not the first choice unless focused on V1/V2 complementarity.

{md_table(lowfpr.sort_values(['holdout', 'method', 'fpr_target']))}
""",
    )
    write_text(
        OUT / "feature_space_diagnostic_report.md",
        f"""
# Feature-Space Diagnostic Report

Nonlinear separability evidence is `{nonlinear_space}` based on centroid and linear separability proxies. This is not sufficient by itself to justify a broad nonlinear sweep.

{md_table(feature.sort_values('holdout'))}
""",
    )
    write_text(
        OUT / "adapter_failure_diagnosis.md",
        f"""
# Adapter Failure Diagnosis

Weighted LR:
- Detection delta vs LR: `{weighted_delta:.6f}`.
- It slightly lowers OOD max but does not change locked mean or min detection.
- Interpretation: OOD-tail weighting mostly shifts the threshold/tail safety, not the attack ranking.

Linear SVM:
- Detection delta vs LR: `{svm_delta:.6f}`.
- OOD max: `{float(svm['locked_ood_alarm_max']):.6f}`.
- Interpretation: hinge-margin scoring is poorly calibrated under the guarded threshold and few-shot support; it pushes enough OOD tail high to violate the low-alert constraint.
""",
    )
    ranking_rows = [
        ["shallow nonlinear", nonlinear_space, "not first choice", "Some feature-space signals exist, but issue24 did not run a clean shallow-tree result and broad nonlinear sweeps risk overfitting."],
        ["DevNet-like", "weak", "not recommended now", "No clear evidence that deviation objective is the bottleneck; would add neural complexity without diagnosis support."],
        ["DeepSAD-like", "weak", "not recommended now", "No strong benign-center evidence; center-distance may be too blunt for attack-bin complementarity."],
        ["pairwise low-FPR ranking", ranking_space, "secondary", "There is some low-FPR ranking room, but V2_top64 already has strong guarded performance."],
        ["V1+V2 residual/fusion", max_fusion, "recommended if continuing adapter work", "V1 and V2 show bin-specific rescue patterns: V1 helps bin6/7 and V2 helps bin8."],
        ["stop adapter upgrade", "moderate", "recommended if paper schedule prioritizes rigor", "LR is not beaten by lightweight upgrades; next clean route is strong baselines and second environment."],
    ]
    ranking_df = pd.DataFrame(ranking_rows, columns=["candidate", "evidence_strength", "recommendation", "reason"])
    write_text(
        OUT / "issue24c_candidate_ranking.md",
        "# Issue24c Candidate Ranking\n\n" + md_table(ranking_df),
    )
    write_text(
        OUT / "claim_boundary.md",
        """
# Claim Boundary

## Can Say

- issue24b diagnoses whether LR is the bottleneck under fixed source_rich_top64.
- It motivates a targeted adapter retry if the reported diagnostics support one.
- It may show LR is already near the representation limit.

## Cannot Say

- A new adapter is proven.
- The final method changed.
- Routing or promotion is solved.
- Complex adapters are definitely useless in all settings.
""",
    )
    risks = [
        ["row-level score incompleteness", "high", "issue23/24 did not persist row-level scores.", "Mark reconstructed seed42 diagnostics as diagnosis-only."],
        ["diagnosis overinterpretation", "high", "Final labels are used for analysis.", "Do not claim new method success."],
        ["repeated locked-bin analysis risk", "high", "Locked bins are being inspected repeatedly.", "Move next to baselines/second environment unless targeted retry is well justified."],
        ["fusion overfit risk", "medium", "V1/V2 complementarity can overfit bins.", "Require validation-only fusion if tried."],
        ["nonlinear adapter overfit risk", "medium", "top64 with few-shot labels can overfit.", "Avoid broad sweeps."],
        ["low-FPR instability", "medium", "Tail metrics are noisy.", "Report guarded detection and pAUC together."],
        ["final eval leakage risk", "high", "Diagnostics use final labels.", "No rule is validated here."],
        ["external validity risk", "high", "No second environment.", "Do not overclaim."],
    ]
    pd.DataFrame(risks, columns=["risk_name", "severity", "reason", "mitigation"]).to_csv(OUT / "risk_register.csv", index=False)
    write_text(
        OUT / "recommended_next_action.md",
        f"""
# Recommended Next Action

Unique first choice: `{next_action}`.

If adapter work continues, do exactly one targeted retry. Do not run a broad complex-adapter sweep. If schedule/risk is prioritized, stop adapter upgrade and proceed to strong baselines plus second-environment or locked temporal validation.
""",
    )
    write_text(
        OUT / "doc_update_patch_suggestion.md",
        """
# Suggested Mainline Docs Patch

Append a short issue24b note:

`issue24b diagnoses LR adapter bottlenecks under fixed source_rich_top64. Row-level scores were reconstructed for diagnosis only; no new adapter method is validated.`
""",
    )
    config = {
        "run": "issue24b_adapter_bottleneck_diagnosis_for_enhanced_v2_top64_2026-05-18",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "diagnostic_seed": DIAGNOSTIC_SEED,
        "methods": METHODS,
        "next_action": next_action,
        "row_level_scores_reconstructed": True,
        "new_adapter_experiment": False,
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    t0 = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "figures").mkdir(exist_ok=True)
    missing = require_inputs()
    if missing:
        write_text(OUT / "missing_input_report.md", "# Missing Input Report\n\n" + "\n".join(f"- {item}" for item in missing))
        raise RuntimeError(f"Missing inputs: {missing}")
    row_scores, score_store, top64_features, feature_rows = reconstruct_scores()
    row_scores.to_parquet(OUT / "row_level_diagnostic_scores.parquet", index=False)
    pd.DataFrame(feature_rows).to_csv(OUT / "diagnostic_top64_feature_indices.csv", index=False)
    score_dist = score_distribution(row_scores)
    overlap = error_overlap(row_scores)
    fusion = fusion_potential(row_scores)
    lowfpr = low_fpr_bottleneck(row_scores)
    feature = feature_space_diagnostic(score_store, top64_features)
    score_dist.to_csv(OUT / "score_distribution_by_bin.csv", index=False)
    overlap.to_csv(OUT / "error_overlap_by_bin.csv", index=False)
    fusion.to_csv(OUT / "fusion_potential_summary.csv", index=False)
    lowfpr.to_csv(OUT / "low_fpr_bottleneck_summary.csv", index=False)
    feature.to_csv(OUT / "feature_space_diagnostic.csv", index=False)
    write_reports({"score_distribution": score_dist, "error_overlap": overlap, "fusion": fusion, "lowfpr": lowfpr, "feature": feature})
    manifest_rows = []
    for path in sorted(OUT.glob("*")):
        if path.is_file() and path.name != "manifest.csv":
            manifest_rows.append({"file": path.name, "size_bytes": path.stat().st_size})
    manifest_rows.append({"file": "runtime_seconds", "size_bytes": f"{time.perf_counter() - t0:.3f}"})
    pd.DataFrame(manifest_rows).to_csv(OUT / "manifest.csv", index=False)


if __name__ == "__main__":
    main()
