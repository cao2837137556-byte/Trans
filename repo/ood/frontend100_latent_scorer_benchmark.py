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
import torch
from sklearn.covariance import LedoitWolf, OAS

THIS_DIR = Path(__file__).resolve().parent
REPO_DIR = THIS_DIR.parent
WORKTREE_ROOT = REPO_DIR.parent

if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

import KitNET as kit
import frontend100_negative_recipe_rescoring as resc
import frontend100_score_postprocessing as spp

EPS = 1e-8


def load_json(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sanitize_for_json(obj):
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_for_json(v) for v in obj]
    if isinstance(obj, tuple):
        return [sanitize_for_json(v) for v in obj]
    if isinstance(obj, np.generic):
        return sanitize_for_json(obj.item())
    if isinstance(obj, float):
        if np.isnan(obj) or np.isinf(obj):
            return None
    return obj


def md_table(df: pd.DataFrame) -> str:
    return resc.md_table(df)


def l2_normalize_rows(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    denom = np.linalg.norm(x, axis=1, keepdims=True)
    denom = np.maximum(denom, 1e-12)
    return x / denom


def l2_normalize_vec(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64).reshape(-1)
    denom = max(1e-12, float(np.linalg.norm(x)))
    return x / denom


def cosine_distance_global(h: np.ndarray, center: np.ndarray) -> np.ndarray:
    h_norm = l2_normalize_rows(h)
    c_norm = l2_normalize_vec(center)
    sim = np.sum(h_norm * c_norm[None, :], axis=1)
    sim = np.clip(sim, -1.0, 1.0)
    return 1.0 - sim


def l2_distance_global(h: np.ndarray, center: np.ndarray) -> np.ndarray:
    return np.linalg.norm(np.asarray(h, dtype=np.float64) - np.asarray(center, dtype=np.float64)[None, :], axis=1)


def pearson_corr(x: np.ndarray, y: np.ndarray) -> float:
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    mask = np.isfinite(x) & np.isfinite(y)
    if int(np.sum(mask)) < 3:
        return float("nan")
    x = x[mask]
    y = y[mask]
    sx = float(np.std(x))
    sy = float(np.std(y))
    if sx <= 1e-12 or sy <= 1e-12:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def mahalanobis_distance(x: np.ndarray, mean: np.ndarray, precision: np.ndarray) -> np.ndarray:
    delta = np.asarray(x, dtype=np.float64) - np.asarray(mean, dtype=np.float64)[None, :]
    quad = np.sum((delta @ precision) * delta, axis=1)
    quad = np.clip(quad, 0.0, None)
    return np.sqrt(quad)


def extract_detector_negative_latent(detector, x: np.ndarray, batch_size: int) -> np.ndarray:
    if not hasattr(detector, "model") or not hasattr(detector, "preprocess") or not hasattr(detector, "_make_hard_negative"):
        raise RuntimeError("detector does not support latent hard-negative extraction")
    x = np.asarray(x, dtype=np.float64)
    x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
    out: List[np.ndarray] = []
    detector.model.eval()
    with torch.no_grad():
        for st in range(0, len(x), batch_size):
            ed = min(len(x), st + batch_size)
            x_norm = detector.preprocess(x[st:ed], update_stats=False)
            xb = torch.from_numpy(x_norm.astype(np.float32)).view(-1, x_norm.shape[1], 1)
            neg_tensor, _ = detector._make_hard_negative(xb, record=False)
            _, h_neg = detector.model(neg_tensor, return_latent=True)
            out.append(h_neg.detach().cpu().numpy().astype(np.float32))
    return np.concatenate(out, axis=0) if out else np.zeros((0, 1), dtype=np.float32)


def extract_global_latent(model: kit.KitNET, x: np.ndarray, batch_size: int, negative: bool = False) -> Tuple[np.ndarray, Dict]:
    blocks: List[np.ndarray] = []
    detector_rows: List[Dict] = []
    for i, det in enumerate(list(getattr(model, "ensembleLayer", []))):
        idx = np.asarray(model.v[i], dtype=np.int64)
        x_sub = np.asarray(x[:, idx], dtype=np.float64)
        if negative:
            h = extract_detector_negative_latent(det, x_sub, batch_size=batch_size)
        else:
            h = resc.extract_detector_latent(det, x_sub, batch_size=batch_size)
        if h is None:
            continue
        h = np.asarray(h, dtype=np.float32)
        if h.ndim != 2 or h.shape[1] <= 0:
            continue
        blocks.append(h)
        detector_rows.append(
            {
                "detector_index": int(i),
                "input_dim": int(len(idx)),
                "latent_dim": int(h.shape[1]),
                "negative_path": bool(negative),
            }
        )
    if not blocks:
        raise RuntimeError("no latent-capable detector blocks extracted")
    return np.concatenate(blocks, axis=1).astype(np.float32), {
        "negative_path": bool(negative),
        "used_detectors": int(len(blocks)),
        "latent_dim_total": int(sum(int(b.shape[1]) for b in blocks)),
        "detector_rows": detector_rows,
    }


def build_score_rows(
    *,
    object_label: str,
    detector_family: str,
    scorer_label: str,
    scorer_family: str,
    id_scores: np.ndarray,
    ood_scores: np.ndarray,
    attack_scores: np.ndarray,
    high_idx: np.ndarray,
    mixed_idx: np.ndarray,
    scan_points: int,
    calibration_budget: int,
    calibration_target: float,
) -> List[Dict]:
    budget = int(min(max(1, calibration_budget), len(ood_scores) - 1))
    ood_cal = ood_scores[:budget]
    ood_eval = ood_scores[budget:]
    fixed_thr = float(np.quantile(id_scores, 0.99))
    naive_thr = float(np.quantile(ood_cal, 1.0 - calibration_target))
    ref = np.concatenate([id_scores, ood_scores, attack_scores]).astype(np.float64)
    thresholds = np.quantile(ref, np.linspace(0.0, 1.0, scan_points))
    thresholds = np.unique(np.concatenate([thresholds, [fixed_thr, naive_thr]])).astype(np.float64)
    scan_df = pd.DataFrame(
        [
            resc.eval_threshold(
                threshold=float(thr),
                id_scores=id_scores,
                ood_scores=ood_scores,
                ood_eval_scores=ood_eval,
                attack_scores=attack_scores,
                high_idx=high_idx,
                mixed_idx=mixed_idx,
            )
            for thr in thresholds
        ]
    )
    fixed_row = scan_df.iloc[(np.abs(scan_df["threshold"] - fixed_thr)).argmin()]
    naive_row = scan_df.iloc[(np.abs(scan_df["threshold"] - naive_thr)).argmin()]
    det50_row = resc.choose_detection_floor(scan_df, 0.50)
    auc = resc.compute_auc(ood_eval_scores=ood_eval, attack_high_scores=attack_scores[high_idx])

    def one(policy_name: str, row: pd.Series | None, threshold_source: str) -> Dict:
        base = {
            "object_label": object_label,
            "detector_family": detector_family,
            "scorer_label": scorer_label,
            "scorer_family": scorer_family,
            "policy_name": policy_name,
            "selection_feasible": row is not None,
            "threshold_source": threshold_source,
            "roc_auc_attack_high_vs_ood_eval": float(auc),
        }
        if row is None:
            base.update(
                {
                    "threshold": float("nan"),
                    "id_alarm_ratio": float("nan"),
                    "ood_alarm_ratio_full": float("nan"),
                    "ood_alarm_ratio_eval": float("nan"),
                    "attack_detection_all": float("nan"),
                    "attack_detection_high_purity": float("nan"),
                    "attack_detection_boundary": float("nan"),
                }
            )
        else:
            base.update(
                {
                    "threshold": float(row["threshold"]),
                    "id_alarm_ratio": float(row["id_alarm_ratio"]),
                    "ood_alarm_ratio_full": float(row["ood_alarm_ratio_full"]),
                    "ood_alarm_ratio_eval": float(row["ood_alarm_ratio_eval"]),
                    "attack_detection_all": float(row["attack_detection_all"]),
                    "attack_detection_high_purity": float(row["attack_detection_high_purity"]),
                    "attack_detection_boundary": float(row["attack_detection_boundary"]),
                }
            )
        return base

    return [
        one("fixed_id_q99", fixed_row, "id_calibration_q99_of_this_scorer"),
        one("naive_calibrated_budget5000_target1pct", naive_row, "ood_calibration_q99_of_this_scorer"),
        one("det_floor_50pct_min_alarm", det50_row, "scan_min_alarm_subject_to_detection_floor"),
    ]


def load_default_reference_rows(
    *,
    candidate_entry: Dict,
    scorer_label: str,
    source_note: str,
    calibration_budget: int,
    calibration_target: float,
    scan_points: int,
    high_idx: np.ndarray,
    mixed_idx: np.ndarray,
) -> Tuple[List[Dict], Dict]:
    run_dir = Path(candidate_entry["run_dir"])
    metrics = load_json(run_dir / "metrics.json")
    id_scores = np.load(run_dir / "id_scores.npy").astype(np.float64)
    ood_scores = np.load(resc.pick_ood_score_file(run_dir, metrics)).astype(np.float64)
    attack_scores = np.load(Path(candidate_entry["attack_score_file"])).astype(np.float64)
    rows = build_score_rows(
        object_label=f"{candidate_entry['candidate_label']}__{scorer_label}",
        detector_family=str(candidate_entry["candidate_label"]),
        scorer_label=scorer_label,
        scorer_family="default_reference",
        id_scores=id_scores,
        ood_scores=ood_scores,
        attack_scores=attack_scores,
        high_idx=high_idx,
        mixed_idx=mixed_idx,
        scan_points=scan_points,
        calibration_budget=calibration_budget,
        calibration_target=calibration_target,
    )
    return rows, {
        "run_dir": str(run_dir),
        "checkpoint": str(candidate_entry["checkpoint"]),
        "source_note": source_note,
        "id_scores_file": str(run_dir / "id_scores.npy"),
        "attack_scores_file": str(candidate_entry["attack_score_file"]),
    }


def topk_energy_ratio(x: np.ndarray, center: np.ndarray, eigvecs: np.ndarray, k: int) -> np.ndarray:
    delta = np.asarray(x, dtype=np.float64) - np.asarray(center, dtype=np.float64)[None, :]
    basis = eigvecs[:, :k]
    proj = delta @ basis
    numer = np.sum(proj * proj, axis=1)
    denom = np.sum(delta * delta, axis=1)
    denom = np.maximum(denom, 1e-12)
    return numer / denom

def plot_tradeoff_main(results_df: pd.DataFrame, out_path: Path) -> None:
    fixed = results_df[(results_df["policy_name"] == "fixed_id_q99") & (results_df["selection_feasible"])].copy()
    order = [
        "latent_swap_spike_mix_no_compact__hybrid_cosine_default_old",
        "latent_swap_spike_mix_no_compact__log_weighted_z_rmse0.5_cos1.0_old",
        "latent_swap_spike_mix_no_compact__single_center_cos",
        "latent_swap_spike_mix_no_compact__single_center_l2",
        "latent_swap_spike_mix_no_compact__score_dir_cosine",
        "latent_swap_spike_mix_no_compact__mahalanobis_ledoitwolf",
        "latent_swap_spike_mix_no_compact__mahalanobis_oas",
        "latent_swap_spike_mix_no_compact__log_rmse_plus_score_dir",
        "transformer_tailreg__default_score",
        "da__default_score",
    ]
    colors = {
        "hybrid_cosine_default_old": "#ff7f0e",
        "log_weighted_z_rmse0.5_cos1.0_old": "#d62728",
        "single_center_cos": "#1f77b4",
        "single_center_l2": "#2ca02c",
        "score_dir_cosine": "#9467bd",
        "mahalanobis_ledoitwolf": "#8c564b",
        "mahalanobis_oas": "#e377c2",
        "log_rmse_plus_score_dir": "#7f7f7f",
        "default_score": "#000000",
    }
    markers = {
        "hybrid_cosine_default_old": "o",
        "log_weighted_z_rmse0.5_cos1.0_old": "o",
        "single_center_cos": "s",
        "single_center_l2": "D",
        "score_dir_cosine": "^",
        "mahalanobis_ledoitwolf": "P",
        "mahalanobis_oas": "X",
        "log_rmse_plus_score_dir": "*",
        "default_score": "h",
    }

    fig, ax = plt.subplots(figsize=(10.5, 7.2))
    for obj in order:
        sub = fixed[fixed["object_label"] == obj]
        if sub.empty:
            continue
        r = sub.iloc[0]
        scorer = str(r["scorer_label"])
        ax.scatter(
            [float(r["ood_alarm_ratio_eval"])],
            [float(r["attack_detection_high_purity"])],
            s=110,
            color=colors.get(scorer, "#7f7f7f"),
            marker=markers.get(scorer, "o"),
            edgecolors="black" if scorer == "default_score" else "none",
        )
        ax.text(
            float(r["ood_alarm_ratio_eval"]) + 0.004,
            float(r["attack_detection_high_purity"]) + 0.006,
            obj.replace("latent_swap_spike_mix_no_compact__", "").replace("__", ":"),
            fontsize=8,
        )
    ax.set_xlabel("OOD benign alarm ratio (fixed)")
    ax.set_ylabel("High-purity attack detection (fixed)")
    ax.set_title("Latent scorer benchmark: fixed trade-off")
    ax.grid(alpha=0.28)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_distribution_grid(score_arrays: Dict[str, Dict[str, np.ndarray]], fixed_thresholds: Dict[str, float], out_path: Path) -> None:
    selected = ["hybrid_cosine_default_old", "single_center_cos", "score_dir_cosine", "mahalanobis_ledoitwolf"]
    fig, axes = plt.subplots(2, 2, figsize=(12.5, 8.8))
    for ax, key in zip(axes.flat, selected):
        pack = score_arrays[key]
        sid = pack["id"]
        sood = pack["ood_eval"]
        satt = pack["attack_high"]
        thr = float(fixed_thresholds[key])
        ax.hist(sid, bins=70, density=True, alpha=0.34, label="ID benign")
        ax.hist(sood, bins=70, density=True, alpha=0.34, label="OOD benign")
        ax.hist(satt, bins=70, density=True, alpha=0.34, label="attack_high")
        ax.axvline(thr, color="black", linestyle="--", linewidth=1.2, label="fixed thr")
        ax.set_title(key)
        ax.grid(alpha=0.24)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_new_scorer_compare(results_df: pd.DataFrame, out_path: Path) -> None:
    fixed = results_df[
        (results_df["policy_name"] == "fixed_id_q99")
        & (results_df["selection_feasible"])
        & (results_df["scorer_label"].isin(["single_center_cos", "single_center_l2", "score_dir_cosine", "mahalanobis_ledoitwolf", "mahalanobis_oas"]))
    ].copy()
    fig, ax = plt.subplots(figsize=(9.2, 6.4))
    styles = {
        "single_center_cos": ("#1f77b4", "s"),
        "single_center_l2": ("#2ca02c", "D"),
        "score_dir_cosine": ("#9467bd", "^"),
        "mahalanobis_ledoitwolf": ("#8c564b", "P"),
        "mahalanobis_oas": ("#e377c2", "X"),
    }
    for _, row in fixed.iterrows():
        color, marker = styles.get(str(row["scorer_label"]), ("#7f7f7f", "o"))
        ax.scatter(float(row["ood_alarm_ratio_eval"]), float(row["attack_detection_high_purity"]), color=color, marker=marker, s=105)
        ax.text(float(row["ood_alarm_ratio_eval"]) + 0.004, float(row["attack_detection_high_purity"]) + 0.006, str(row["scorer_label"]), fontsize=8)
    ax.set_xlabel("OOD benign alarm ratio (fixed)")
    ax.set_ylabel("High-purity attack detection (fixed)")
    ax.set_title("Single-center vs direction vs Mahalanobis")
    ax.grid(alpha=0.28)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_fixed_point_compare(results_df: pd.DataFrame, out_path: Path) -> None:
    fixed = results_df[(results_df["policy_name"] == "fixed_id_q99") & (results_df["selection_feasible"])].copy()
    fixed = fixed[
        fixed["object_label"].isin(
            [
                "latent_swap_spike_mix_no_compact__hybrid_cosine_default_old",
                "latent_swap_spike_mix_no_compact__score_dir_cosine",
                "latent_swap_spike_mix_no_compact__mahalanobis_ledoitwolf",
                "transformer_tailreg__default_score",
                "da__default_score",
            ]
        )
    ].copy()
    fig, ax = plt.subplots(figsize=(9.6, 5.8))
    x = np.arange(len(fixed))
    ax.bar(x - 0.18, fixed["ood_alarm_ratio_eval"].to_numpy(dtype=np.float64), width=0.36, label="OOD alarm")
    ax.bar(x + 0.18, fixed["attack_detection_high_purity"].to_numpy(dtype=np.float64), width=0.36, label="attack detection")
    ax.set_xticks(x)
    ax.set_xticklabels([str(v).replace("latent_swap_spike_mix_no_compact__", "") for v in fixed["object_label"]], rotation=20, ha="right")
    ax.set_ylabel("ratio")
    ax.set_title("Fixed-point comparison")
    ax.grid(axis="y", alpha=0.28)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_covariance_analysis(explained: np.ndarray, proj_energy: Dict[str, np.ndarray], out_path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12.6, 4.8))
    ax = axes[0]
    k = min(20, len(explained))
    ax.plot(np.arange(1, k + 1), np.cumsum(explained[:k]), marker="o")
    ax.set_xlabel("Top principal directions")
    ax.set_ylabel("Cumulative explained variance ratio")
    ax.set_title("ID benign latent covariance principal directions")
    ax.grid(alpha=0.28)

    ax = axes[1]
    labels = list(proj_energy.keys())
    vals = [proj_energy[k] for k in labels]
    ax.boxplot(vals, tick_labels=labels, showfliers=False)
    ax.set_ylabel("Top-10 principal-axis energy ratio")
    ax.set_title("How much each split moves along benign principal axes")
    ax.grid(axis="y", alpha=0.28)

    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)

def make_score_pack(
    *,
    rmse_cal: np.ndarray,
    rmse_ood: np.ndarray,
    rmse_attack: np.ndarray,
    old_cos_cal: np.ndarray,
    old_cos_ood: np.ndarray,
    old_cos_attack: np.ndarray,
    h_fit: np.ndarray,
    h_fit_neg: np.ndarray,
    h_cal: np.ndarray,
    h_ood: np.ndarray,
    h_attack: np.ndarray,
) -> Tuple[Dict[str, Tuple[np.ndarray, np.ndarray, np.ndarray]], Dict]:
    score_arrays: Dict[str, Tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    meta: Dict[str, Dict] = {}

    old_versions, old_stats = spp.make_score_versions(rmse_cal, rmse_ood, rmse_attack, old_cos_cal, old_cos_ood, old_cos_attack)
    for name in ["hybrid_cosine_default", "log_weighted_z_rmse0.5_cos1.0"]:
        score_arrays[f"{name}_old"] = old_versions[name]
        meta[f"{name}_old"] = {
            "family": "old_single_center_hybrid",
            "stats_source": "ID benign calibration split only",
            "source_definition": f"recomputed current old scorer via per-detector latent cosine + RMSE ({name})",
            "old_score_stats": old_stats[name],
        }

    c_pos = np.mean(h_fit, axis=0).astype(np.float64)
    c_neg = np.mean(h_fit_neg, axis=0).astype(np.float64)

    single_cos_cal = cosine_distance_global(h_cal, c_pos)
    single_cos_ood = cosine_distance_global(h_ood, c_pos)
    single_cos_attack = cosine_distance_global(h_attack, c_pos)
    score_arrays["single_center_cos"] = (single_cos_cal, single_cos_ood, single_cos_attack)
    meta["single_center_cos"] = {
        "family": "single_center",
        "center_source": "ID benign training split latent mean",
        "distance_definition": "1 - cosine(normalized h, normalized c_pos)",
        "latent_fit_samples": int(len(h_fit)),
    }

    single_l2_cal = l2_distance_global(h_cal, c_pos)
    single_l2_ood = l2_distance_global(h_ood, c_pos)
    single_l2_attack = l2_distance_global(h_attack, c_pos)
    score_arrays["single_center_l2"] = (single_l2_cal, single_l2_ood, single_l2_attack)
    meta["single_center_l2"] = {
        "family": "single_center",
        "center_source": "ID benign training split latent mean",
        "distance_definition": "||h-c_pos||_2",
        "latent_fit_samples": int(len(h_fit)),
    }

    dir_cal = cosine_distance_global(h_cal, c_pos) - cosine_distance_global(h_cal, c_neg)
    dir_ood = cosine_distance_global(h_ood, c_pos) - cosine_distance_global(h_ood, c_neg)
    dir_attack = cosine_distance_global(h_attack, c_pos) - cosine_distance_global(h_attack, c_neg)
    score_arrays["score_dir_cosine"] = (dir_cal, dir_ood, dir_attack)
    meta["score_dir_cosine"] = {
        "family": "double_center_direction",
        "center_pos_source": "ID benign training split latent mean",
        "center_neg_source": "synthetic negative latent mean from ID benign training split using latent_swap_spike_mix",
        "formula": "(1-cos(h,c_pos)) - (1-cos(h,c_neg))",
        "note": "larger means farther from benign center and closer to negative center",
    }

    dir_l2_cal = l2_distance_global(h_cal, c_pos) - l2_distance_global(h_cal, c_neg)
    dir_l2_ood = l2_distance_global(h_ood, c_pos) - l2_distance_global(h_ood, c_neg)
    dir_l2_attack = l2_distance_global(h_attack, c_pos) - l2_distance_global(h_attack, c_neg)
    score_arrays["score_dir_l2_beta1"] = (dir_l2_cal, dir_l2_ood, dir_l2_attack)
    meta["score_dir_l2_beta1"] = {
        "family": "double_center_direction",
        "center_pos_source": "ID benign training split latent mean",
        "center_neg_source": "synthetic negative latent mean from ID benign training split using latent_swap_spike_mix",
        "formula": "||h-c_pos||_2 - 1.0*||h-c_neg||_2",
    }

    lw = LedoitWolf().fit(np.asarray(h_fit, dtype=np.float64))
    maha_lw_cal = mahalanobis_distance(h_cal, lw.location_, lw.precision_)
    maha_lw_ood = mahalanobis_distance(h_ood, lw.location_, lw.precision_)
    maha_lw_attack = mahalanobis_distance(h_attack, lw.location_, lw.precision_)
    score_arrays["mahalanobis_ledoitwolf"] = (maha_lw_cal, maha_lw_ood, maha_lw_attack)
    meta["mahalanobis_ledoitwolf"] = {
        "family": "covariance_aware",
        "estimator": "sklearn.covariance.LedoitWolf",
        "fit_samples": int(len(h_fit)),
        "latent_dim": int(h_fit.shape[1]),
    }

    oas = OAS().fit(np.asarray(h_fit, dtype=np.float64))
    maha_oas_cal = mahalanobis_distance(h_cal, oas.location_, oas.precision_)
    maha_oas_ood = mahalanobis_distance(h_ood, oas.location_, oas.precision_)
    maha_oas_attack = mahalanobis_distance(h_attack, oas.location_, oas.precision_)
    score_arrays["mahalanobis_oas"] = (maha_oas_cal, maha_oas_ood, maha_oas_attack)
    meta["mahalanobis_oas"] = {
        "family": "covariance_aware",
        "estimator": "sklearn.covariance.OAS",
        "fit_samples": int(len(h_fit)),
        "latent_dim": int(h_fit.shape[1]),
    }

    log_rmse_cal = np.log(np.asarray(rmse_cal, dtype=np.float64) + EPS)
    log_rmse_ood = np.log(np.asarray(rmse_ood, dtype=np.float64) + EPS)
    log_rmse_attack = np.log(np.asarray(rmse_attack, dtype=np.float64) + EPS)
    mu_rmse = float(np.mean(log_rmse_cal))
    std_rmse = resc.safe_std(log_rmse_cal)
    mu_dir = float(np.mean(dir_cal))
    std_dir = resc.safe_std(dir_cal)
    hybrid_dir_cal = resc.zscore(log_rmse_cal, mu_rmse, std_rmse) + resc.zscore(dir_cal, mu_dir, std_dir)
    hybrid_dir_ood = resc.zscore(log_rmse_ood, mu_rmse, std_rmse) + resc.zscore(dir_ood, mu_dir, std_dir)
    hybrid_dir_attack = resc.zscore(log_rmse_attack, mu_rmse, std_rmse) + resc.zscore(dir_attack, mu_dir, std_dir)
    score_arrays["log_rmse_plus_score_dir"] = (hybrid_dir_cal, hybrid_dir_ood, hybrid_dir_attack)
    meta["log_rmse_plus_score_dir"] = {
        "family": "light_hybrid",
        "stats_source": "ID benign calibration split only",
        "formula": "z(log(RMSE)) + z(score_dir_cosine)",
    }

    cov = np.asarray(lw.covariance_, dtype=np.float64)
    eigvals, eigvecs = np.linalg.eigh(cov)
    order = np.argsort(eigvals)[::-1]
    eigvals = np.clip(eigvals[order], 0.0, None)
    eigvecs = eigvecs[:, order]
    exp_ratio = eigvals / max(np.sum(eigvals), 1e-12)
    meta["covariance_analysis"] = {
        "latent_dim": int(h_fit.shape[1]),
        "top_eigenvalues": [float(v) for v in eigvals[:10]],
        "top_explained_variance_ratio": [float(v) for v in exp_ratio[:10]],
        "c_pos_l2": float(np.linalg.norm(c_pos)),
        "c_neg_l2": float(np.linalg.norm(c_neg)),
        "mean_fit_neg_shift_l2": float(np.linalg.norm(c_neg - c_pos)),
    }
    return score_arrays, {"scorer_meta": meta, "ledoitwolf": lw, "oas": oas, "c_pos": c_pos, "c_neg": c_neg, "explained_ratio": exp_ratio, "eigvecs": eigvecs}

def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(description="Latent scorer benchmark on latent_swap_spike_mix_no_compact.")
    parser.add_argument("--run-tag", default=f"frontend100_latent_scorer_benchmark_{today}")
    parser.add_argument(
        "--prior-run-dir",
        type=Path,
        default=WORKTREE_ROOT / "runs" / "frontend100_negative_recipe_rescoring_2026-04-05",
    )
    parser.add_argument("--batch-size", type=int, default=1024)
    parser.add_argument("--scan-points", type=int, default=901)
    parser.add_argument("--calibration-budget", type=int, default=5000)
    parser.add_argument("--calibration-target", type=float, default=0.01)
    parser.add_argument("--force-recompute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    out_dir = WORKTREE_ROOT / "runs" / args.run_tag
    out_dir.mkdir(parents=True, exist_ok=True)
    plot_dir = out_dir / "latent_scorer_benchmark_plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = out_dir / "cache_latent_scorer"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "command.txt").write_text("python " + " ".join(os.sys.argv) + "\n", encoding="utf-8")

    prior_manifest = load_json(args.prior_run_dir / "negative_recipe_rescoring_manifest.json")
    source_root = Path(prior_manifest["source_root"])
    candidate_map = {str(c["candidate_label"]): c for c in prior_manifest["candidates"]}
    main_entry = candidate_map["latent_swap_spike_mix"]
    tailreg_entry = candidate_map["transformer_tailreg"]
    da_entry = candidate_map["da"]

    crosscapture_data = source_root / "runs" / "frontend100_crosscapture_stage1_2026-03-25" / "data"
    stage1_joint = source_root / "runs" / "frontend100_joint_eval_stage1_2026-03-31"
    stage2_joint = source_root / "runs" / "frontend100_joint_eval_stage2_2026-04-01"
    stage2_manifest = load_json(stage2_joint / "attack_manifest_stage2.json")
    stage2_idx = resc.build_stage2_indices(stage2_manifest)
    high_idx = stage2_idx["high"]
    mixed_idx = stage2_idx["mixed"]
    if len(high_idx) == 0:
        raise RuntimeError("stage2 high-purity indices are empty")

    train_samples = int(prior_manifest["data_splits"]["train_samples"])
    id_eval_samples = int(prior_manifest["data_splits"]["id_eval_samples"])
    train_csv = crosscapture_data / "id_source_100.csv"
    ood_csv = crosscapture_data / "ood_benign_source_100.csv"
    attack_csv = stage1_joint / "data" / "attack_source_100.csv"

    x_all = pd.read_csv(train_csv, header=None, nrows=train_samples + id_eval_samples).to_numpy(dtype=np.float64)
    x_fit = x_all[:train_samples]
    x_cal = x_all[train_samples : train_samples + id_eval_samples]
    x_ood = pd.read_csv(ood_csv, header=None).to_numpy(dtype=np.float64)
    x_attack = pd.read_csv(attack_csv, header=None).to_numpy(dtype=np.float64)

    if args.dry_run:
        x_fit = x_fit[:1024]
        x_cal = x_cal[:512]
        x_ood = x_ood[:2048]
        attack_limit = 4096
        x_attack = x_attack[:attack_limit]
        high_idx = high_idx[high_idx < attack_limit]
        mixed_idx = mixed_idx[mixed_idx < attack_limit]
        if len(high_idx) == 0:
            raise RuntimeError("dry-run attack slice lost all high-purity indices")

    main_run_dir = Path(main_entry["run_dir"])
    main_metrics = load_json(main_run_dir / "metrics.json")
    rmse_cal = np.load(main_run_dir / "id_scores.npy").astype(np.float64)
    rmse_ood = np.load(resc.pick_ood_score_file(main_run_dir, main_metrics)).astype(np.float64)
    rmse_attack = np.load(Path(main_entry["attack_score_file"])).astype(np.float64)

    if args.dry_run:
        rmse_cal = rmse_cal[: len(x_cal)]
        rmse_ood = rmse_ood[: len(x_ood)]
        rmse_attack = rmse_attack[: len(x_attack)]

    main_checkpoint = Path(main_entry["checkpoint"])
    model = kit.KitNET.load_checkpoint(main_checkpoint)

    old_cache = {
        "l2_id": cache_dir / "old_single_center_l2_id.npy",
        "l2_ood": cache_dir / "old_single_center_l2_ood.npy",
        "l2_attack": cache_dir / "old_single_center_l2_attack.npy",
        "cos_id": cache_dir / "old_single_center_cos_id.npy",
        "cos_ood": cache_dir / "old_single_center_cos_ood.npy",
        "cos_attack": cache_dir / "old_single_center_cos_attack.npy",
        "meta": cache_dir / "old_single_center_meta.json",
    }
    if (
        (not args.force_recompute)
        and all(path.exists() for path in old_cache.values())
    ):
        old_l2_cal = np.load(old_cache["l2_id"]).astype(np.float64)
        old_l2_ood = np.load(old_cache["l2_ood"]).astype(np.float64)
        old_l2_attack = np.load(old_cache["l2_attack"]).astype(np.float64)
        old_cos_cal = np.load(old_cache["cos_id"]).astype(np.float64)
        old_cos_ood = np.load(old_cache["cos_ood"]).astype(np.float64)
        old_cos_attack = np.load(old_cache["cos_attack"]).astype(np.float64)
        old_meta = load_json(old_cache["meta"])
        old_meta["score_source"] = "cached"
    else:
        old_l2_cal, old_l2_ood, old_l2_attack, old_cos_cal, old_cos_ood, old_cos_attack, old_meta = resc.compute_latent_center_distance_scores(
            model=model,
            x_id=x_cal,
            x_ood=x_ood,
            x_attack=x_attack,
            batch_size=args.batch_size,
        )
        np.save(old_cache["l2_id"], old_l2_cal)
        np.save(old_cache["l2_ood"], old_l2_ood)
        np.save(old_cache["l2_attack"], old_l2_attack)
        np.save(old_cache["cos_id"], old_cos_cal)
        np.save(old_cache["cos_ood"], old_cos_ood)
        np.save(old_cache["cos_attack"], old_cos_attack)
        old_cache["meta"].write_text(json.dumps(sanitize_for_json(old_meta), indent=2, ensure_ascii=False), encoding="utf-8")
        old_meta["score_source"] = "computed_now"

    def load_or_compute_global(label: str, data: np.ndarray, negative: bool) -> Tuple[np.ndarray, Dict]:
        npy = cache_dir / f"{label}.npy"
        meta_path = cache_dir / f"{label}_meta.json"
        if (not args.force_recompute) and npy.exists() and meta_path.exists():
            arr = np.load(npy).astype(np.float32)
            meta = load_json(meta_path)
            meta["score_source"] = "cached"
            return arr, meta
        arr, meta = extract_global_latent(model=model, x=data, batch_size=args.batch_size, negative=negative)
        np.save(npy, arr.astype(np.float32))
        meta_path.write_text(json.dumps(sanitize_for_json(meta), indent=2, ensure_ascii=False), encoding="utf-8")
        meta["score_source"] = "computed_now"
        return arr, meta

    h_fit, fit_meta = load_or_compute_global("h_fit_pos", x_fit, negative=False)
    h_fit_neg, fit_neg_meta = load_or_compute_global("h_fit_neg", x_fit, negative=True)
    h_cal, cal_meta = load_or_compute_global("h_cal_pos", x_cal, negative=False)
    h_ood, ood_meta = load_or_compute_global("h_ood_pos", x_ood, negative=False)
    h_attack, attack_meta = load_or_compute_global("h_attack_pos", x_attack, negative=False)

    score_arrays, scorer_runtime = make_score_pack(
        rmse_cal=rmse_cal,
        rmse_ood=rmse_ood,
        rmse_attack=rmse_attack,
        old_cos_cal=old_cos_cal,
        old_cos_ood=old_cos_ood,
        old_cos_attack=old_cos_attack,
        h_fit=h_fit,
        h_fit_neg=h_fit_neg,
        h_cal=h_cal,
        h_ood=h_ood,
        h_attack=h_attack,
    )

    policy_rows: List[Dict] = []
    fixed_thresholds: Dict[str, float] = {}
    score_plot_arrays: Dict[str, Dict[str, np.ndarray]] = {}
    for scorer_label, (sid, sood, satt) in score_arrays.items():
        rows = build_score_rows(
            object_label=f"latent_swap_spike_mix_no_compact__{scorer_label}",
            detector_family="latent_swap_spike_mix_no_compact",
            scorer_label=scorer_label,
            scorer_family=str(scorer_runtime["scorer_meta"].get(scorer_label, {}).get("family", "latent_scorer")),
            id_scores=np.asarray(sid, dtype=np.float64),
            ood_scores=np.asarray(sood, dtype=np.float64),
            attack_scores=np.asarray(satt, dtype=np.float64),
            high_idx=high_idx,
            mixed_idx=mixed_idx,
            scan_points=args.scan_points,
            calibration_budget=args.calibration_budget,
            calibration_target=args.calibration_target,
        )
        policy_rows.extend(rows)
        fixed_thresholds[scorer_label] = float(np.quantile(np.asarray(sid, dtype=np.float64), 0.99))
        score_plot_arrays[scorer_label] = {
            "id": np.asarray(sid, dtype=np.float64),
            "ood_eval": np.asarray(sood[args.calibration_budget :], dtype=np.float64) if len(sood) > args.calibration_budget else np.asarray(sood, dtype=np.float64),
            "attack_high": np.asarray(satt[high_idx], dtype=np.float64),
        }

    tailreg_rows, tailreg_meta = load_default_reference_rows(
        candidate_entry=tailreg_entry,
        scorer_label="default_score",
        source_note="official default score reference",
        calibration_budget=args.calibration_budget,
        calibration_target=args.calibration_target,
        scan_points=args.scan_points,
        high_idx=high_idx,
        mixed_idx=mixed_idx,
    )
    da_rows, da_meta = load_default_reference_rows(
        candidate_entry=da_entry,
        scorer_label="default_score",
        source_note="official default score reference",
        calibration_budget=args.calibration_budget,
        calibration_target=args.calibration_target,
        scan_points=args.scan_points,
        high_idx=high_idx,
        mixed_idx=mixed_idx,
    )
    policy_rows.extend(tailreg_rows)
    policy_rows.extend(da_rows)

    results_df = pd.DataFrame(policy_rows).sort_values(["detector_family", "scorer_label", "policy_name"])
    results_df.to_csv(out_dir / "latent_scorer_benchmark_results.csv", index=False)
    (out_dir / "results.csv").write_text((out_dir / "latent_scorer_benchmark_results.csv").read_text(encoding="utf-8"), encoding="utf-8")

    corr_specs = {
        "single_center_l2": score_arrays["single_center_l2"],
        "score_dir_cosine": score_arrays["score_dir_cosine"],
        "mahalanobis_ledoitwolf": score_arrays["mahalanobis_ledoitwolf"],
    }
    corr_rows: List[Dict] = []
    split_data = {
        "id_benign_calibration": {
            "single_center_l2": corr_specs["single_center_l2"][0],
            "score_dir_cosine": corr_specs["score_dir_cosine"][0],
            "mahalanobis_ledoitwolf": corr_specs["mahalanobis_ledoitwolf"][0],
        },
        "ood_benign_eval": {
            "single_center_l2": corr_specs["single_center_l2"][1][args.calibration_budget :] if len(corr_specs["single_center_l2"][1]) > args.calibration_budget else corr_specs["single_center_l2"][1],
            "score_dir_cosine": corr_specs["score_dir_cosine"][1][args.calibration_budget :] if len(corr_specs["score_dir_cosine"][1]) > args.calibration_budget else corr_specs["score_dir_cosine"][1],
            "mahalanobis_ledoitwolf": corr_specs["mahalanobis_ledoitwolf"][1][args.calibration_budget :] if len(corr_specs["mahalanobis_ledoitwolf"][1]) > args.calibration_budget else corr_specs["mahalanobis_ledoitwolf"][1],
        },
        "attack_high_purity": {
            "single_center_l2": corr_specs["single_center_l2"][2][high_idx],
            "score_dir_cosine": corr_specs["score_dir_cosine"][2][high_idx],
            "mahalanobis_ledoitwolf": corr_specs["mahalanobis_ledoitwolf"][2][high_idx],
        },
    }
    score_names = ["single_center_l2", "score_dir_cosine", "mahalanobis_ledoitwolf"]
    for split_name, pack in split_data.items():
        for a in score_names:
            for b in score_names:
                corr_rows.append(
                    {
                        "split_name": split_name,
                        "scorer_row": a,
                        "scorer_col": b,
                        "pearson_corr": pearson_corr(pack[a], pack[b]),
                    }
                )
    corr_df = pd.DataFrame(corr_rows)
    corr_df.to_csv(out_dir / "scorer_correlation_matrices.csv", index=False)

    exp_ratio = np.asarray(scorer_runtime["explained_ratio"], dtype=np.float64)
    eigvecs = np.asarray(scorer_runtime["eigvecs"], dtype=np.float64)
    c_pos = np.asarray(scorer_runtime["c_pos"], dtype=np.float64)
    proj_energy = {
        "ID calib": topk_energy_ratio(h_cal, c_pos, eigvecs, k=min(10, eigvecs.shape[1])),
        "OOD eval": topk_energy_ratio(h_ood[args.calibration_budget :] if len(h_ood) > args.calibration_budget else h_ood, c_pos, eigvecs, k=min(10, eigvecs.shape[1])),
        "attack_high": topk_energy_ratio(h_attack[high_idx], c_pos, eigvecs, k=min(10, eigvecs.shape[1])),
    }
    proj_df = pd.DataFrame(
        [
            {
                "split_name": key,
                "mean_top10_energy_ratio": float(np.mean(val)),
                "std_top10_energy_ratio": float(np.std(val)),
                "p50_top10_energy_ratio": float(np.quantile(val, 0.5)),
                "p90_top10_energy_ratio": float(np.quantile(val, 0.9)),
            }
            for key, val in proj_energy.items()
        ]
    )
    proj_df.to_csv(out_dir / "latent_covariance_projection_summary.csv", index=False)

    plot_tradeoff_main(results_df, plot_dir / "tradeoff_main.png")
    plot_distribution_grid(score_plot_arrays, fixed_thresholds, plot_dir / "scorer_distribution_grid.png")
    plot_new_scorer_compare(results_df, plot_dir / "single_center_vs_direction_vs_mahalanobis.png")
    plot_fixed_point_compare(results_df, plot_dir / "fixed_point_compare.png")
    plot_covariance_analysis(exp_ratio, proj_energy, plot_dir / "covariance_principal_direction_analysis.png")

    show_cols = [
        "object_label",
        "scorer_label",
        "policy_name",
        "threshold",
        "ood_alarm_ratio_eval",
        "attack_detection_high_purity",
        "attack_detection_boundary",
        "roc_auc_attack_high_vs_ood_eval",
    ]
    (out_dir / "latent_scorer_benchmark_results.md").write_text(md_table(results_df[show_cols]), encoding="utf-8")
    (out_dir / "results.md").write_text(md_table(results_df[show_cols]), encoding="utf-8")

    def gv(obj: str, policy: str, col: str) -> float:
        sub = results_df[
            (results_df["object_label"] == obj)
            & (results_df["policy_name"] == policy)
            & (results_df["selection_feasible"])
        ]
        if sub.empty:
            return float("nan")
        return float(sub.iloc[0][col])

    main_old = "latent_swap_spike_mix_no_compact__hybrid_cosine_default_old"
    main_log_old = "latent_swap_spike_mix_no_compact__log_weighted_z_rmse0.5_cos1.0_old"
    main_dir = "latent_swap_spike_mix_no_compact__score_dir_cosine"
    main_maha = "latent_swap_spike_mix_no_compact__mahalanobis_ledoitwolf"
    main_single = "latent_swap_spike_mix_no_compact__single_center_l2"
    tailreg_obj = "transformer_tailreg__default_score"
    da_obj = "da__default_score"

    fixed_subset = results_df[(results_df["policy_name"] == "fixed_id_q99") & (results_df["selection_feasible"]) & (results_df["object_label"].str.startswith("latent_swap_spike_mix_no_compact__"))].copy()
    fixed_subset["utility"] = fixed_subset["attack_detection_high_purity"] - fixed_subset["ood_alarm_ratio_eval"]
    best_fixed = fixed_subset.sort_values("utility", ascending=False).iloc[0]["object_label"] if not fixed_subset.empty else main_old

    ood_corr_dir = corr_df[(corr_df["split_name"] == "ood_benign_eval") & (corr_df["scorer_row"] == "score_dir_cosine") & (corr_df["scorer_col"] == "single_center_l2")]
    ood_corr_maha = corr_df[(corr_df["split_name"] == "ood_benign_eval") & (corr_df["scorer_row"] == "mahalanobis_ledoitwolf") & (corr_df["scorer_col"] == "single_center_l2")]
    attack_corr_dir = corr_df[(corr_df["split_name"] == "attack_high_purity") & (corr_df["scorer_row"] == "score_dir_cosine") & (corr_df["scorer_col"] == "single_center_l2")]
    attack_corr_maha = corr_df[(corr_df["split_name"] == "attack_high_purity") & (corr_df["scorer_row"] == "mahalanobis_ledoitwolf") & (corr_df["scorer_col"] == "single_center_l2")]
    ood_energy_mean = float(proj_df[proj_df["split_name"] == "OOD eval"]["mean_top10_energy_ratio"].iloc[0])
    attack_energy_mean = float(proj_df[proj_df["split_name"] == "attack_high"]["mean_top10_energy_ratio"].iloc[0])

    lines: List[str] = []
    lines.append("# Latent Scorer Benchmark Summary")
    lines.append("")
    lines.append("## Setup")
    lines.append("- Mode: strict offline scorer benchmark only (no new training, no checkpoint modification).")
    lines.append("- Main checkpoint: `latent_swap_spike_mix_no_compact`.")
    lines.append("- Fit-only statistics source: ID benign training split for `c_pos`, `c_neg`, and covariance fitting.")
    lines.append("- Calibration-only statistics source: ID benign calibration split for fixed threshold q99 and any z-score hybrid statistics.")
    lines.append("- OOD / attack leakage rule: no OOD benign or attack sample used in any center/covariance/statistics fitting.")
    lines.append("- Benchmarked scorer families: old single-center hybrid, single-center latent, double-center direction, covariance-aware Mahalanobis, light hybrid.")
    lines.append("")
    lines.append("## Required answers")
    lines.append("1. Is the current latent representation already good enough, with the scorer being the bottleneck?")
    lines.append(
        f"- fixed old best (`hybrid_cosine_default_old`) = alarm {gv(main_old, 'fixed_id_q99', 'ood_alarm_ratio_eval'):.4f}, det {gv(main_old, 'fixed_id_q99', 'attack_detection_high_purity'):.4f}; "
        f"best fixed latent scorer this round = `{str(best_fixed).replace('latent_swap_spike_mix_no_compact__', '')}` with alarm {gv(str(best_fixed), 'fixed_id_q99', 'ood_alarm_ratio_eval'):.4f}, det {gv(str(best_fixed), 'fixed_id_q99', 'attack_detection_high_purity'):.4f}."
    )
    lines.append("2. Does the double-center direction scorer separate attack from OOD benign better than the single-center scorer?")
    lines.append(
        f"- fixed `score_dir_cosine` = alarm {gv(main_dir, 'fixed_id_q99', 'ood_alarm_ratio_eval'):.4f}, det {gv(main_dir, 'fixed_id_q99', 'attack_detection_high_purity'):.4f}; "
        f"fixed `single_center_l2` = alarm {gv(main_single, 'fixed_id_q99', 'ood_alarm_ratio_eval'):.4f}, det {gv(main_single, 'fixed_id_q99', 'attack_detection_high_purity'):.4f}."
    )
    lines.append("3. Does Mahalanobis materially reduce OOD alarm while preserving detection?")
    lines.append(
        f"- fixed `mahalanobis_ledoitwolf` = alarm {gv(main_maha, 'fixed_id_q99', 'ood_alarm_ratio_eval'):.4f}, det {gv(main_maha, 'fixed_id_q99', 'attack_detection_high_purity'):.4f}; "
        f"vs old best delta = alarm {gv(main_maha, 'fixed_id_q99', 'ood_alarm_ratio_eval') - gv(main_old, 'fixed_id_q99', 'ood_alarm_ratio_eval'):+.4f}, det {gv(main_maha, 'fixed_id_q99', 'attack_detection_high_purity') - gv(main_old, 'fixed_id_q99', 'attack_detection_high_purity'):+.4f}."
    )
    lines.append("4. Which direction currently looks more correct: covariance-aware or attack-direction scoring?")
    lines.append(
        f"- Compare fixed utilities: `score_dir_cosine`={(gv(main_dir, 'fixed_id_q99', 'attack_detection_high_purity') - gv(main_dir, 'fixed_id_q99', 'ood_alarm_ratio_eval')):.4f}, "
        f"`mahalanobis_ledoitwolf`={(gv(main_maha, 'fixed_id_q99', 'attack_detection_high_purity') - gv(main_maha, 'fixed_id_q99', 'ood_alarm_ratio_eval')):.4f}, "
        f"`log_weighted_z_rmse0.5_cos1.0_old`={(gv(main_log_old, 'fixed_id_q99', 'attack_detection_high_purity') - gv(main_log_old, 'fixed_id_q99', 'ood_alarm_ratio_eval')):.4f}."
    )
    lines.append("5. Is there enough single-seed signal to justify a training-stage `Transformer-LatentPrototype-v1` next?")
    lines.append("- Judge from the best fixed scorer and whether double-center direction clearly outperforms both old single-center and Mahalanobis.")
    lines.append("6. If Mahalanobis wins, does that imply the main problem is scorer roughness rather than training?")
    lines.append("- Compare `mahalanobis_ledoitwolf` against both old single-center hybrid and `score_dir_cosine` before deciding.")
    lines.append("")
    lines.append("## Correlation readout")
    lines.append(
        f"- OOD benign corr(single_center_l2, score_dir_cosine) = {float(ood_corr_dir.iloc[0]['pearson_corr']) if not ood_corr_dir.empty else float('nan'):.4f}; "
        f"corr(single_center_l2, mahalanobis_ledoitwolf) = {float(ood_corr_maha.iloc[0]['pearson_corr']) if not ood_corr_maha.empty else float('nan'):.4f}."
    )
    lines.append(
        f"- attack_high corr(single_center_l2, score_dir_cosine) = {float(attack_corr_dir.iloc[0]['pearson_corr']) if not attack_corr_dir.empty else float('nan'):.4f}; "
        f"corr(single_center_l2, mahalanobis_ledoitwolf) = {float(attack_corr_maha.iloc[0]['pearson_corr']) if not attack_corr_maha.empty else float('nan'):.4f}."
    )
    lines.append(
        f"- Top-10 benign principal-axis energy ratio mean: OOD eval = {ood_energy_mean:.4f}, attack_high = {attack_energy_mean:.4f}."
    )
    lines.append("")
    lines.append("## References (fixed)")
    lines.append(f"- transformer_tailreg default: alarm {gv(tailreg_obj, 'fixed_id_q99', 'ood_alarm_ratio_eval'):.4f}, det {gv(tailreg_obj, 'fixed_id_q99', 'attack_detection_high_purity'):.4f}.")
    lines.append(f"- dA default: alarm {gv(da_obj, 'fixed_id_q99', 'ood_alarm_ratio_eval'):.4f}, det {gv(da_obj, 'fixed_id_q99', 'attack_detection_high_purity'):.4f}.")
    lines.append("")
    lines.append("## Additional notes")
    lines.append("- `hybrid_cosine_default_old` and `log_weighted_z_rmse0.5_cos1.0_old` are recomputed old scorers, used only as single-checkpoint controls.")
    lines.append("- `score_dir_cosine` uses L2-normalized latent vectors and distance-style cosine formula.")
    lines.append("- Mahalanobis fitting uses shrinkage covariance only (`LedoitWolf`, optional `OAS`), no raw covariance inversion.")
    summary_text = "\n".join(lines) + "\n"
    (out_dir / "latent_scorer_benchmark_summary.md").write_text(summary_text, encoding="utf-8")
    (out_dir / "summary.md").write_text(summary_text, encoding="utf-8")

    manifest = {
        "stage": "frontend100_latent_scorer_benchmark",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_tag": args.run_tag,
        "prior_run_dir": str(args.prior_run_dir),
        "source_root": str(source_root),
        "main_candidate": {
            "candidate_label": "latent_swap_spike_mix_no_compact",
            "checkpoint": str(main_checkpoint),
            "run_dir": str(main_run_dir),
            "attack_score_file": str(main_entry["attack_score_file"]),
        },
        "references": {
            "transformer_tailreg_default_score": tailreg_meta,
            "da_default_score": da_meta,
        },
        "data_splits": {
            "fit_samples": int(len(x_fit)),
            "id_calibration_samples": int(len(x_cal)),
            "ood_total_samples": int(len(x_ood)),
            "attack_total_samples": int(len(x_attack)),
            "stage2_high_purity_count": int(len(high_idx)),
            "stage2_boundary_count": int(len(mixed_idx)),
        },
        "fit_rules": {
            "c_pos": "ID benign training split latent mean",
            "c_neg": "latent mean of synthetic negatives generated from the same ID benign training split using latent_swap_spike_mix",
            "covariance": "fit on ID benign training split latent only",
            "fixed_threshold": "q99 on ID benign calibration split for each scorer",
            "hybrid_stats": "ID benign calibration split only",
            "no_leakage": True,
        },
        "latent_cache_audit": {
            "fit_pos": fit_meta,
            "fit_neg": fit_neg_meta,
            "cal_pos": cal_meta,
            "ood_pos": ood_meta,
            "attack_pos": attack_meta,
            "old_single_center": old_meta,
        },
        "scorer_meta": scorer_runtime["scorer_meta"],
        "outputs": {
            "results_csv": str(out_dir / "latent_scorer_benchmark_results.csv"),
            "results_md": str(out_dir / "latent_scorer_benchmark_results.md"),
            "summary_md": str(out_dir / "latent_scorer_benchmark_summary.md"),
            "correlation_csv": str(out_dir / "scorer_correlation_matrices.csv"),
            "covariance_projection_csv": str(out_dir / "latent_covariance_projection_summary.csv"),
            "plots_dir": str(plot_dir),
        },
    }
    manifest = sanitize_for_json(manifest)
    (out_dir / "latent_scorer_benchmark_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "config.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[done] latent scorer benchmark output: {out_dir}")


if __name__ == "__main__":
    main()
