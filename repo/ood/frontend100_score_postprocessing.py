from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
REPO_DIR = THIS_DIR.parent
WORKTREE_ROOT = REPO_DIR.parent

if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

import frontend100_negative_recipe_rescoring as resc

EPS = 1e-8
MAD_SCALE = 1.4826

CANDIDATE_ORDER = ["latent_swap_spike_mix", "transformer_tailreg", "transformer", "da"]
SCORE_SPECS = [
    {"score_version": "hybrid_cosine_default", "family": "zscore", "a": 1.0, "b": 1.0, "label": "z(1.0,1.0)"},
    {"score_version": "weighted_z_rmse0.5_cos1.0", "family": "zscore", "a": 0.5, "b": 1.0, "label": "z(0.5,1.0)"},
    {"score_version": "weighted_z_rmse0.25_cos1.0", "family": "zscore", "a": 0.25, "b": 1.0, "label": "z(0.25,1.0)"},
    {"score_version": "pure_cosine_z", "family": "zscore", "a": 0.0, "b": 1.0, "label": "z(0.0,1.0)"},
    {"score_version": "weighted_z_rmse1.0_cos0.5", "family": "zscore", "a": 1.0, "b": 0.5, "label": "z(1.0,0.5)"},
    {"score_version": "log_hybrid_cosine", "family": "log_zscore", "a": 1.0, "b": 1.0, "label": "log+z(1.0,1.0)"},
    {"score_version": "log_weighted_z_rmse0.5_cos1.0", "family": "log_zscore", "a": 0.5, "b": 1.0, "label": "log+z(0.5,1.0)"},
    {"score_version": "log_pure_cosine_z", "family": "log_zscore", "a": 0.0, "b": 1.0, "label": "log+z(0.0,1.0)"},
    {"score_version": "robust_hybrid_cosine_mad", "family": "robust_mad", "a": 1.0, "b": 1.0, "label": "MAD(1.0,1.0)"},
    {"score_version": "robust_weighted_rmse0.5_cos1.0", "family": "robust_mad", "a": 0.5, "b": 1.0, "label": "MAD(0.5,1.0)"},
    {"score_version": "robust_pure_cosine_mad", "family": "robust_mad", "a": 0.0, "b": 1.0, "label": "MAD(0.0,1.0)"},
]


def load_candidate_map(prior_manifest: Dict) -> Dict[str, Dict]:
    return {str(c["candidate_label"]): c for c in prior_manifest.get("candidates", [])}


def candidate_style(candidate_label: str) -> Dict[str, str]:
    mapping = {
        "latent_swap_spike_mix": {"color": "#d62728", "marker": "o"},
        "transformer_tailreg": {"color": "#1f77b4", "marker": "s"},
        "transformer": {"color": "#2ca02c", "marker": "^"},
        "da": {"color": "#9467bd", "marker": "D"},
    }
    return mapping.get(candidate_label, {"color": "#7f7f7f", "marker": "o"})


def family_color(family: str) -> str:
    return {
        "zscore": "#1f77b4",
        "log_zscore": "#ff7f0e",
        "robust_mad": "#2ca02c",
    }.get(family, "#7f7f7f")


def safe_read_npy(path: Path) -> np.ndarray:
    return np.load(path).astype(np.float64)


def robust_params(x: np.ndarray) -> Tuple[float, float]:
    x = np.asarray(x, dtype=np.float64)
    med = float(np.median(x))
    mad = float(np.median(np.abs(x - med)))
    scale = max(EPS, MAD_SCALE * mad)
    return med, scale


def robust_z(x: np.ndarray, med: float, scale: float) -> np.ndarray:
    return (np.asarray(x, dtype=np.float64) - med) / max(EPS, scale)


def log_transform(x: np.ndarray) -> np.ndarray:
    return np.log(np.asarray(x, dtype=np.float64) + EPS)


def make_score_versions(rmse_id: np.ndarray, rmse_ood: np.ndarray, rmse_attack: np.ndarray, cos_id: np.ndarray, cos_ood: np.ndarray, cos_attack: np.ndarray) -> Tuple[Dict[str, Tuple[np.ndarray, np.ndarray, np.ndarray]], Dict[str, Dict]]:
    versions: Dict[str, Tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    stats: Dict[str, Dict] = {}

    rmse_mu = float(np.mean(rmse_id))
    rmse_sigma = resc.safe_std(rmse_id)
    cos_mu = float(np.mean(cos_id))
    cos_sigma = resc.safe_std(cos_id)

    log_rmse_id = log_transform(rmse_id)
    log_rmse_ood = log_transform(rmse_ood)
    log_rmse_attack = log_transform(rmse_attack)
    log_cos_id = log_transform(cos_id)
    log_cos_ood = log_transform(cos_ood)
    log_cos_attack = log_transform(cos_attack)
    log_rmse_mu = float(np.mean(log_rmse_id))
    log_rmse_sigma = resc.safe_std(log_rmse_id)
    log_cos_mu = float(np.mean(log_cos_id))
    log_cos_sigma = resc.safe_std(log_cos_id)

    rmse_med, rmse_mad_scale = robust_params(rmse_id)
    cos_med, cos_mad_scale = robust_params(cos_id)

    for spec in SCORE_SPECS:
        name = str(spec["score_version"])
        family = str(spec["family"])
        a = float(spec["a"])
        b = float(spec["b"])
        if family == "zscore":
            sid = a * resc.zscore(rmse_id, rmse_mu, rmse_sigma) + b * resc.zscore(cos_id, cos_mu, cos_sigma)
            sood = a * resc.zscore(rmse_ood, rmse_mu, rmse_sigma) + b * resc.zscore(cos_ood, cos_mu, cos_sigma)
            satt = a * resc.zscore(rmse_attack, rmse_mu, rmse_sigma) + b * resc.zscore(cos_attack, cos_mu, cos_sigma)
            stats[name] = {
                "family": family,
                "rmse_weight": a,
                "cosine_weight": b,
                "stats_source": "ID benign evaluation split only",
                "rmse_mu": rmse_mu,
                "rmse_sigma": rmse_sigma,
                "cos_mu": cos_mu,
                "cos_sigma": cos_sigma,
            }
        elif family == "log_zscore":
            sid = a * resc.zscore(log_rmse_id, log_rmse_mu, log_rmse_sigma) + b * resc.zscore(log_cos_id, log_cos_mu, log_cos_sigma)
            sood = a * resc.zscore(log_rmse_ood, log_rmse_mu, log_rmse_sigma) + b * resc.zscore(log_cos_ood, log_cos_mu, log_cos_sigma)
            satt = a * resc.zscore(log_rmse_attack, log_rmse_mu, log_rmse_sigma) + b * resc.zscore(log_cos_attack, log_cos_mu, log_cos_sigma)
            stats[name] = {
                "family": family,
                "rmse_weight": a,
                "cosine_weight": b,
                "stats_source": "ID benign evaluation split only",
                "rmse_mu": log_rmse_mu,
                "rmse_sigma": log_rmse_sigma,
                "cos_mu": log_cos_mu,
                "cos_sigma": log_cos_sigma,
                "transform": "log(x+1e-8)",
            }
        elif family == "robust_mad":
            sid = a * robust_z(rmse_id, rmse_med, rmse_mad_scale) + b * robust_z(cos_id, cos_med, cos_mad_scale)
            sood = a * robust_z(rmse_ood, rmse_med, rmse_mad_scale) + b * robust_z(cos_ood, cos_med, cos_mad_scale)
            satt = a * robust_z(rmse_attack, rmse_med, rmse_mad_scale) + b * robust_z(cos_attack, cos_med, cos_mad_scale)
            stats[name] = {
                "family": family,
                "rmse_weight": a,
                "cosine_weight": b,
                "stats_source": "ID benign evaluation split only",
                "rmse_median": rmse_med,
                "rmse_mad_scale": rmse_mad_scale,
                "cos_median": cos_med,
                "cos_mad_scale": cos_mad_scale,
                "formula": "(x-median)/(MAD*1.4826+1e-8)",
            }
        else:
            raise ValueError(f"unknown family: {family}")
        versions[name] = (sid.astype(np.float64), sood.astype(np.float64), satt.astype(np.float64))

    return versions, stats


def policy_rows_for_score(candidate_label: str, detector: str, source_mode: str, notes: str, score_version: str, spec: Dict, sid: np.ndarray, sood: np.ndarray, satt: np.ndarray, high_idx: np.ndarray, mixed_idx: np.ndarray, scan_points: int, budget: int, target_alarm: float) -> List[Dict]:
    budget = int(min(max(1, budget), len(sood) - 1))
    ood_cal = sood[:budget]
    ood_eval = sood[budget:]
    fixed_thr = float(np.quantile(sid, 0.99))
    naive_thr = float(np.quantile(ood_cal, 1.0 - target_alarm))

    ref = np.concatenate([sid, sood, satt]).astype(np.float64)
    thresholds = np.quantile(ref, np.linspace(0.0, 1.0, scan_points))
    thresholds = np.unique(np.concatenate([thresholds, [fixed_thr, naive_thr]])).astype(np.float64)
    scan_df = pd.DataFrame(
        [
            resc.eval_threshold(
                threshold=float(thr),
                id_scores=sid,
                ood_scores=sood,
                ood_eval_scores=ood_eval,
                attack_scores=satt,
                high_idx=high_idx,
                mixed_idx=mixed_idx,
            )
            for thr in thresholds
        ]
    )
    fixed_row = scan_df.iloc[(np.abs(scan_df["threshold"] - fixed_thr)).argmin()]
    naive_row = scan_df.iloc[(np.abs(scan_df["threshold"] - naive_thr)).argmin()]
    det50_row = resc.choose_detection_floor(scan_df, 0.50)

    def one_row(policy_name: str, row: pd.Series | None, thr_src: str) -> Dict:
        base = {
            "candidate_label": candidate_label,
            "detector": detector,
            "source_mode": source_mode,
            "notes": notes,
            "score_version": score_version,
            "score_family": str(spec["family"]),
            "rmse_weight": float(spec["a"]),
            "cosine_weight": float(spec["b"]),
            "selection_feasible": row is not None,
            "policy_name": policy_name,
            "threshold_source": thr_src,
        }
        if row is None:
            base.update({
                "threshold": float("nan"),
                "id_alarm_ratio": float("nan"),
                "ood_alarm_ratio_full": float("nan"),
                "ood_alarm_ratio_eval": float("nan"),
                "attack_detection_all": float("nan"),
                "attack_detection_high_purity": float("nan"),
                "attack_detection_boundary": float("nan"),
                "roc_auc_attack_high_vs_ood_eval": resc.compute_auc(ood_eval_scores=ood_eval, attack_high_scores=satt[high_idx]),
            })
        else:
            base.update({
                "threshold": float(row["threshold"]),
                "id_alarm_ratio": float(row["id_alarm_ratio"]),
                "ood_alarm_ratio_full": float(row["ood_alarm_ratio_full"]),
                "ood_alarm_ratio_eval": float(row["ood_alarm_ratio_eval"]),
                "attack_detection_all": float(row["attack_detection_all"]),
                "attack_detection_high_purity": float(row["attack_detection_high_purity"]),
                "attack_detection_boundary": float(row["attack_detection_boundary"]),
                "roc_auc_attack_high_vs_ood_eval": resc.compute_auc(ood_eval_scores=ood_eval, attack_high_scores=satt[high_idx]),
            })
        return base

    return [
        one_row("fixed_id_q99", fixed_row, "id_q99_of_this_score"),
        one_row("naive_calibrated_budget5000_target1pct", naive_row, "ood_cal_q99_of_this_score"),
        one_row("det_floor_50pct_min_alarm", det50_row, "scan_min_alarm_subject_to_detection_floor"),
    ]


def add_default_deltas(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["alarm_delta_vs_default_same_policy"] = np.nan
    out["detection_delta_vs_default_same_policy"] = np.nan
    keys = ["candidate_label", "policy_name"]
    for key, grp in out.groupby(keys):
        default = grp[grp["score_version"] == "hybrid_cosine_default"]
        if default.empty:
            continue
        def_alarm = float(default.iloc[0]["ood_alarm_ratio_eval"])
        def_det = float(default.iloc[0]["attack_detection_high_purity"])
        idx = grp.index
        out.loc[idx, "alarm_delta_vs_default_same_policy"] = out.loc[idx, "ood_alarm_ratio_eval"] - def_alarm
        out.loc[idx, "detection_delta_vs_default_same_policy"] = out.loc[idx, "attack_detection_high_purity"] - def_det
    return out


def plot_main_tradeoff(results_df: pd.DataFrame, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 8))
    main = results_df[results_df["candidate_label"] == "latent_swap_spike_mix"].copy()
    policy_markers = {
        "fixed_id_q99": "o",
        "naive_calibrated_budget5000_target1pct": "x",
        "det_floor_50pct_min_alarm": "s",
    }
    for _, row in main.iterrows():
        ax.scatter(
            float(row["ood_alarm_ratio_eval"]),
            float(row["attack_detection_high_purity"]),
            color=family_color(str(row["score_family"])),
            marker=policy_markers.get(str(row["policy_name"]), "o"),
            s=85,
            alpha=0.9,
        )
        if str(row["policy_name"]) == "fixed_id_q99":
            ax.text(float(row["ood_alarm_ratio_eval"]) + 0.004, float(row["attack_detection_high_purity"]) + 0.004, str(row["score_version"]), fontsize=8)

    controls = results_df[
        (results_df["candidate_label"].isin(["transformer_tailreg", "transformer", "da"]))
        & (results_df["score_version"] == "hybrid_cosine_default")
    ].copy()
    for _, row in controls.iterrows():
        style = candidate_style(str(row["candidate_label"]))
        ax.scatter(
            float(row["ood_alarm_ratio_eval"]),
            float(row["attack_detection_high_purity"]),
            color=style["color"],
            marker=style["marker"],
            s=120,
            edgecolors="black",
            linewidths=0.8,
        )
        ax.text(float(row["ood_alarm_ratio_eval"]) + 0.004, float(row["attack_detection_high_purity"]) + 0.004, f"{row['candidate_label']}:{row['policy_name']}", fontsize=8)

    ax.set_xlabel("OOD benign alarm ratio (eval split)")
    ax.set_ylabel("High-purity attack detection")
    ax.set_title("Score-postprocessing trade-off on latent_swap_spike_mix")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_selected_distributions(raw_scores: Dict[str, Dict[str, np.ndarray]], out_path: Path) -> None:
    selected = ["hybrid_cosine_default", "pure_cosine_z", "log_hybrid_cosine", "robust_hybrid_cosine_mad"]
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    for ax, key in zip(axes.flat, selected):
        pack = raw_scores[key]
        sid = pack["id"]
        sood = pack["ood_eval"]
        satt = pack["attack_high"]
        thr = float(np.quantile(pack["id"], 0.99))
        bins = 60
        ax.hist(sid, bins=bins, density=True, alpha=0.35, label="ID benign")
        ax.hist(sood, bins=bins, density=True, alpha=0.35, label="OOD benign")
        ax.hist(satt, bins=bins, density=True, alpha=0.35, label="attack_high")
        ax.axvline(thr, color="black", linestyle="--", linewidth=1.2, label="fixed q99")
        ax.set_title(key)
        ax.grid(alpha=0.25)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_auc(results_df: pd.DataFrame, out_path: Path) -> None:
    fixed_df = results_df[results_df["policy_name"] == "fixed_id_q99"].copy()
    order = fixed_df.sort_values(["candidate_label", "roc_auc_attack_high_vs_ood_eval"], ascending=[True, False])
    labels = [f"{r.candidate_label}\n{r.score_version}" for _, r in order.iterrows()]
    values = order["roc_auc_attack_high_vs_ood_eval"].to_numpy(dtype=np.float64)
    colors = [family_color(str(v)) for v in order["score_family"]]
    fig, ax = plt.subplots(figsize=(12, max(5, 0.28 * len(order))))
    y = np.arange(len(order))
    ax.barh(y, values, color=colors)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("ROC-AUC (attack_high vs OOD_eval)")
    ax.set_xlim(0.0, 1.0)
    ax.grid(axis="x", alpha=0.3)
    ax.set_title("ROC-AUC by candidate and score version")
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_correlation(rmse: np.ndarray, cos: np.ndarray, out_path: Path) -> Dict[str, float]:
    x = np.asarray(rmse, dtype=np.float64)
    y = np.asarray(cos, dtype=np.float64)
    corr = float(np.corrcoef(x, y)[0, 1]) if len(x) > 1 else float("nan")
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.scatter(x, y, s=6, alpha=0.15)
    ax.set_xlabel("RMSE")
    ax.set_ylabel("Cosine distance")
    ax.set_title(f"RMSE vs Cosine (corr={corr:.4f})")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)
    return {"corr_rmse_cos": corr}


def plot_pure_vs_mixed(results_df: pd.DataFrame, out_path: Path) -> None:
    fixed = results_df[
        (results_df["candidate_label"] == "latent_swap_spike_mix")
        & (results_df["policy_name"] == "fixed_id_q99")
        & (results_df["score_version"].isin(["hybrid_cosine_default", "weighted_z_rmse0.5_cos1.0", "weighted_z_rmse0.25_cos1.0", "pure_cosine_z", "log_hybrid_cosine", "robust_hybrid_cosine_mad"]))
    ].copy()
    fig, ax = plt.subplots(figsize=(9, 7))
    for _, row in fixed.iterrows():
        style = family_color(str(row["score_family"]))
        ax.scatter(float(row["ood_alarm_ratio_eval"]), float(row["attack_detection_high_purity"]), color=style, s=100)
        ax.text(float(row["ood_alarm_ratio_eval"]) + 0.004, float(row["attack_detection_high_purity"]) + 0.004, str(row["score_version"]), fontsize=8)
    ax.set_xlabel("OOD benign alarm ratio (fixed)")
    ax.set_ylabel("High-purity attack detection (fixed)")
    ax.set_title("Pure cosine vs mixed hybrid on latent_swap_spike_mix")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def summarize(results_df: pd.DataFrame) -> str:
    fixed = results_df[(results_df["candidate_label"] == "latent_swap_spike_mix") & (results_df["policy_name"] == "fixed_id_q99") & (results_df["selection_feasible"])].copy()
    default_row = fixed[fixed["score_version"] == "hybrid_cosine_default"].iloc[0]
    best_fixed = fixed.assign(utility=fixed["attack_detection_high_purity"] - fixed["ood_alarm_ratio_eval"]).sort_values("utility", ascending=False).iloc[0]
    best_log = fixed[fixed["score_family"] == "log_zscore"].assign(utility=fixed[fixed["score_family"] == "log_zscore"]["attack_detection_high_purity"] - fixed[fixed["score_family"] == "log_zscore"]["ood_alarm_ratio_eval"]).sort_values("utility", ascending=False)
    best_robust = fixed[fixed["score_family"] == "robust_mad"].assign(utility=fixed[fixed["score_family"] == "robust_mad"]["attack_detection_high_purity"] - fixed[fixed["score_family"] == "robust_mad"]["ood_alarm_ratio_eval"]).sort_values("utility", ascending=False)
    pure = fixed[fixed["score_version"] == "pure_cosine_z"].iloc[0]

    def row_text(row: pd.Series) -> str:
        return f"alarm={float(row['ood_alarm_ratio_eval']):.4f}, det={float(row['attack_detection_high_purity']):.4f}"

    log_text = "n/a"
    if not best_log.empty:
        r = best_log.iloc[0]
        log_text = f"{r['score_version']} ({row_text(r)})"
    robust_text = "n/a"
    if not best_robust.empty:
        r = best_robust.iloc[0]
        robust_text = f"{r['score_version']} ({row_text(r)})"

    controls = []
    for cand in ["transformer_tailreg", "transformer", "da"]:
        sub = results_df[(results_df["candidate_label"] == cand) & (results_df["score_version"] == "hybrid_cosine_default") & (results_df["policy_name"] == "fixed_id_q99")]
        if not sub.empty:
            r = sub.iloc[0]
            controls.append(f"- {cand}: {row_text(r)}")

    main_issue = "score combination" if float(best_fixed["ood_alarm_ratio_eval"]) < float(default_row["ood_alarm_ratio_eval"]) - 0.02 else "recipe/representation"
    worth_multiseed = float(best_fixed["ood_alarm_ratio_eval"]) <= float(default_row["ood_alarm_ratio_eval"]) - 0.03 and float(best_fixed["attack_detection_high_purity"]) >= float(default_row["attack_detection_high_purity"]) - 0.03

    lines: List[str] = []
    lines.append("# Score Postprocessing Summary")
    lines.append("")
    lines.append("## Setup")
    lines.append("- Mode: offline score-postprocessing only; no new training, no checkpoint modification.")
    lines.append("- Main candidate: `latent_swap_spike_mix`.")
    lines.append("- Controls: `transformer_tailreg`, `transformer`, `da`.")
    lines.append("- Stats source for all z/MAD scaling: ID benign evaluation split only (strict no OOD/attack leakage).")
    lines.append("- Fixed threshold definition for every score version: that score's ID-benign q99.")
    lines.append("")
    lines.append("## Required answers")
    lines.append("1. Is there a score version that lowers alarm materially vs current default hybrid_cosine while preserving most detection?")
    lines.append(f"- Default `hybrid_cosine_default`: {row_text(default_row)}.")
    lines.append(f"- Best fixed utility: `{best_fixed['score_version']}` with {row_text(best_fixed)}.")
    lines.append("2. Did log-transform help with the heavy-tail problem?")
    lines.append(f"- Best log variant: {log_text}.")
    lines.append("3. Is MAD-based scaling more stable than ordinary z-score?")
    lines.append(f"- Best MAD variant: {robust_text}.")
    lines.append("4. What is the main information source now?")
    if float(pure["ood_alarm_ratio_eval"]) < float(default_row["ood_alarm_ratio_eval"]) and float(pure["attack_detection_high_purity"]) + 0.1 < float(default_row["attack_detection_high_purity"]):
        lines.append("- Cosine distance is cleaner for alarm control, but RMSE still contributes substantial attack lift at fixed threshold; current issue is combination/threshold interaction, not pure redundancy.")
    else:
        lines.append("- Cosine remains the primary latent signal; RMSE is not redundant but must be down-weighted or transformed carefully.")
    lines.append("5. Does pure cosine beat most hybrid combinations?")
    lines.append(f"- `pure_cosine_z`: {row_text(pure)}.")
    lines.append("6. Is this ready for multi-seed?")
    lines.append(f"- {'Yes, if the best fixed trade-off is a clear improvement over default.' if worth_multiseed else 'Not yet; scoring helps, but the best fixed trade-off is not clean enough to lock for multi-seed.'}")
    lines.append("")
    lines.append("## Controls (fixed, default hybrid_cosine)")
    lines.extend(controls)
    lines.append("")
    lines.append("## Judgment")
    lines.append(f"- Current alarm issue is more consistent with `{main_issue}` than with pure model collapse.")
    lines.append("- See `score_postprocessing_results.csv` for all policy rows and `score_postprocessing_delta_vs_default.csv` for per-policy deltas.")
    return "\n".join(lines) + "\n"


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(description="Offline score-postprocessing diagnosis on latent_swap_spike_mix.")
    parser.add_argument("--run-tag", default=f"frontend100_score_postprocessing_{today}")
    parser.add_argument("--prior-run-dir", type=Path, default=WORKTREE_ROOT / "runs" / "frontend100_negative_recipe_rescoring_2026-04-05")
    parser.add_argument("--scan-points", type=int, default=901)
    parser.add_argument("--calibration-budget", type=int, default=5000)
    parser.add_argument("--calibration-target", type=float, default=0.01)
    parser.add_argument("--det-floor", type=float, default=0.50)
    args = parser.parse_args()

    prior_dir = args.prior_run_dir
    manifest = resc.load_json(prior_dir / "negative_recipe_rescoring_manifest.json")
    candidate_map = load_candidate_map(manifest)
    missing = [c for c in CANDIDATE_ORDER if c not in candidate_map]
    if missing:
        raise RuntimeError(f"Missing candidates in prior manifest: {missing}")

    out_dir = WORKTREE_ROOT / "runs" / args.run_tag
    out_dir.mkdir(parents=True, exist_ok=True)
    plot_dir = out_dir / "score_postprocessing_plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "command.txt").write_text("python " + " ".join(os.sys.argv) + "\n", encoding="utf-8")

    source_root = Path(manifest["source_root"])
    stage2_joint = source_root / "runs" / "frontend100_joint_eval_stage2_2026-04-01"
    stage2_manifest = resc.load_json(stage2_joint / "attack_manifest_stage2.json")
    stage2_idx = resc.build_stage2_indices(stage2_manifest)
    high_idx = stage2_idx["high"]
    mixed_idx = stage2_idx["mixed"]
    cache_dir = prior_dir / "cache_rescored_scores"

    all_rows: List[Dict] = []
    stats_manifest: Dict[str, Dict] = {}
    correlation_rows: List[Dict] = []
    selected_distribution_scores: Dict[str, Dict[str, np.ndarray]] = {}

    for cand_label in CANDIDATE_ORDER:
        info = candidate_map[cand_label]
        run_dir = Path(info["run_dir"])
        attack_score_file = Path(info["attack_score_file"])
        metrics = resc.load_json(run_dir / "metrics.json")
        rmse_id = safe_read_npy(run_dir / "id_scores.npy")
        rmse_ood = safe_read_npy(resc.pick_ood_score_file(run_dir, metrics))
        rmse_attack = safe_read_npy(attack_score_file)
        cos_id = safe_read_npy(cache_dir / f"{cand_label}_latent_id_cos.npy")
        cos_ood = safe_read_npy(cache_dir / f"{cand_label}_latent_ood_cos.npy")
        cos_attack = safe_read_npy(cache_dir / f"{cand_label}_latent_attack_cos.npy")

        versions, score_stats = make_score_versions(rmse_id, rmse_ood, rmse_attack, cos_id, cos_ood, cos_attack)
        stats_manifest[cand_label] = score_stats

        all_rmse = np.concatenate([rmse_id, rmse_ood[int(min(max(1, args.calibration_budget), len(rmse_ood) - 1)):], rmse_attack[high_idx]])
        all_cos = np.concatenate([cos_id, cos_ood[int(min(max(1, args.calibration_budget), len(cos_ood) - 1)):], cos_attack[high_idx]])
        corr = plot_correlation(all_rmse, all_cos, plot_dir / f"correlation_rmse_vs_cosine_{cand_label}.png")
        corr["candidate_label"] = cand_label
        correlation_rows.append(corr)

        for spec in SCORE_SPECS:
            score_version = str(spec["score_version"])
            sid, sood, satt = versions[score_version]
            rows = policy_rows_for_score(
                candidate_label=cand_label,
                detector=str(info["detector"]),
                source_mode=str(info["source_mode"]),
                notes=str(info["notes"]),
                score_version=score_version,
                spec=spec,
                sid=sid,
                sood=sood,
                satt=satt,
                high_idx=high_idx,
                mixed_idx=mixed_idx,
                scan_points=args.scan_points,
                budget=args.calibration_budget,
                target_alarm=args.calibration_target,
            )
            all_rows.extend(rows)

            if cand_label == "latent_swap_spike_mix" and score_version in {"hybrid_cosine_default", "pure_cosine_z", "log_hybrid_cosine", "robust_hybrid_cosine_mad"}:
                budget = int(min(max(1, args.calibration_budget), len(sood) - 1))
                selected_distribution_scores[score_version] = {
                    "id": sid,
                    "ood_eval": sood[budget:],
                    "attack_high": satt[high_idx],
                }

    results_df = pd.DataFrame(all_rows).sort_values(["candidate_label", "score_version", "policy_name"])
    results_df = add_default_deltas(results_df)
    fixed_df = results_df[results_df["policy_name"] == "fixed_id_q99"].copy()

    delta_df = results_df[
        [
            "candidate_label",
            "score_version",
            "policy_name",
            "ood_alarm_ratio_eval",
            "attack_detection_high_purity",
            "alarm_delta_vs_default_same_policy",
            "detection_delta_vs_default_same_policy",
            "roc_auc_attack_high_vs_ood_eval",
        ]
    ].copy()

    plot_main_tradeoff(results_df, plot_dir / "tradeoff_main.png")
    plot_selected_distributions(selected_distribution_scores, plot_dir / "score_distribution_selected.png")
    plot_auc(fixed_df, plot_dir / "roc_auc_fixed.png")
    plot_pure_vs_mixed(results_df, plot_dir / "pure_cosine_vs_mixed_fixed.png")

    summary_text = summarize(results_df)
    results_csv = out_dir / "score_postprocessing_results.csv"
    results_df.to_csv(results_csv, index=False)
    delta_df.to_csv(out_dir / "score_postprocessing_delta_vs_default.csv", index=False)
    pd.DataFrame(correlation_rows).to_csv(out_dir / "score_postprocessing_correlations.csv", index=False)

    show_cols = [
        "candidate_label",
        "score_version",
        "policy_name",
        "ood_alarm_ratio_eval",
        "attack_detection_high_purity",
        "alarm_delta_vs_default_same_policy",
        "detection_delta_vs_default_same_policy",
        "roc_auc_attack_high_vs_ood_eval",
    ]
    (out_dir / "score_postprocessing_results.md").write_text(resc.md_table(results_df[show_cols]), encoding="utf-8")
    (out_dir / "score_postprocessing_summary.md").write_text(summary_text, encoding="utf-8")
    (out_dir / "summary.md").write_text(summary_text, encoding="utf-8")

    manifest_out = {
        "stage": "frontend100_score_postprocessing",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_tag": args.run_tag,
        "prior_run_dir": str(prior_dir),
        "source_root": str(source_root),
        "main_candidate": "latent_swap_spike_mix",
        "controls": ["transformer_tailreg", "transformer", "da"],
        "score_specs": SCORE_SPECS,
        "calibration": {
            "budget": int(args.calibration_budget),
            "target_alarm": float(args.calibration_target),
            "det_floor": float(args.det_floor),
        },
        "fixed_threshold_rule": "For each score version, use that score's ID-benign q99.",
        "stats_leakage_rule": "All z-score / log-z / MAD statistics are computed from ID benign evaluation split only.",
        "candidate_score_stats": resc.sanitize_for_json(stats_manifest),
        "outputs": {
            "results_csv": str(results_csv),
            "results_md": str(out_dir / "score_postprocessing_results.md"),
            "summary_md": str(out_dir / "score_postprocessing_summary.md"),
            "delta_csv": str(out_dir / "score_postprocessing_delta_vs_default.csv"),
            "correlation_csv": str(out_dir / "score_postprocessing_correlations.csv"),
            "plots_dir": str(plot_dir),
        },
    }
    manifest_text = json.dumps(resc.sanitize_for_json(manifest_out), indent=2, ensure_ascii=False)
    (out_dir / "score_postprocessing_manifest.json").write_text(manifest_text, encoding="utf-8")
    (out_dir / "config.json").write_text(manifest_text, encoding="utf-8")

    print(f"[done] score-postprocessing output: {out_dir}")


if __name__ == "__main__":
    main()
