from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch

REPO_DIR = Path(__file__).resolve().parents[1]
WORKTREE_ROOT = REPO_DIR.parent

if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

import KitNET as kit


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
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, row in df.iterrows():
        vals: List[str] = []
        for c in cols:
            v = row[c]
            if isinstance(v, float):
                vals.append(f"{v:.6f}")
            else:
                vals.append(str(v))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"


def score_stats(x: np.ndarray) -> Dict[str, float]:
    x = np.asarray(x, dtype=np.float64)
    q = np.quantile(x, [0.01, 0.05, 0.5, 0.95, 0.99])
    return {
        "n": int(len(x)),
        "mean": float(np.mean(x)),
        "std": float(np.std(x)),
        "min": float(np.min(x)),
        "p01": float(q[0]),
        "p05": float(q[1]),
        "p50": float(q[2]),
        "p95": float(q[3]),
        "p99": float(q[4]),
        "max": float(np.max(x)),
    }


def _resolve_stage2_source_tsv(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.exists():
        return path

    normalized = raw_path.replace("\\", "/")
    basename = normalized.rsplit("/", 1)[-1]
    suffix = normalized.split("runs/", 1)[1] if "runs/" in normalized else None

    candidate_roots: List[Path] = []
    for env_key in ("SOURCE_ROOT", "REMOTE_PROJECT_ROOT"):
        raw_root = os.environ.get(env_key)
        if raw_root:
            candidate_roots.append(Path(raw_root))

    candidate_paths: List[Path] = []
    for root in candidate_roots:
        if suffix is not None:
            suffix_path = Path(*[part for part in suffix.split("/") if part])
            candidate_paths.append(root / suffix_path)
            candidate_paths.append(root / "runs" / suffix_path)
        candidate_paths.append(root / "runs" / "frontend100_joint_eval_stage1_2026-03-31" / "extract_attack_34_1" / basename)

    for cand in candidate_paths:
        if cand.exists():
            return cand

    raise FileNotFoundError(
        f"Stage2 source TSV not found. raw={raw_path!r}; candidates={[str(p) for p in candidate_paths]}"
    )


def build_stage2_indices(stage2_manifest: Dict) -> Dict[str, np.ndarray]:
    tsv_path = _resolve_stage2_source_tsv(stage2_manifest["source_tsv"])
    use_first_n = int(stage2_manifest["use_first_n"])
    bin_seconds = int(stage2_manifest["bin_seconds"])
    strong_bins = np.array(stage2_manifest["selected_bins"]["strong_bins"], dtype=np.int64)
    mixed_bins = np.array(stage2_manifest["selected_bins"]["mixed_bins"], dtype=np.int64)

    pkt = pd.read_csv(tsv_path, sep="\t", usecols=["frame.time_epoch"], nrows=use_first_n)
    ts = pd.to_numeric(pkt["frame.time_epoch"], errors="coerce").to_numpy(dtype=np.float64)
    ts = ts[np.isfinite(ts)]
    ts0 = float(np.min(ts))
    bins = ((ts - ts0) // bin_seconds).astype(np.int64)

    return {
        "all": np.arange(len(ts), dtype=np.int64),
        "high": np.where(np.isin(bins, strong_bins))[0],
        "mixed": np.where(np.isin(bins, mixed_bins))[0],
    }


def eval_threshold(
    threshold: float,
    id_scores: np.ndarray,
    ood_scores: np.ndarray,
    ood_eval_scores: np.ndarray,
    attack_scores: np.ndarray,
    high_idx: np.ndarray,
    mixed_idx: np.ndarray,
) -> Dict[str, float]:
    return {
        "threshold": float(threshold),
        "id_alarm_ratio": float(np.mean(id_scores > threshold)),
        "ood_alarm_ratio_full": float(np.mean(ood_scores > threshold)),
        "ood_alarm_ratio_eval": float(np.mean(ood_eval_scores > threshold)),
        "attack_detection_all": float(np.mean(attack_scores > threshold)),
        "attack_detection_high_purity": float(np.mean(attack_scores[high_idx] > threshold)),
        "attack_detection_boundary": float(np.mean(attack_scores[mixed_idx] > threshold)) if len(mixed_idx) > 0 else float("nan"),
    }


def choose_detection_floor(df: pd.DataFrame, det_floor: float) -> Optional[pd.Series]:
    cand = df[df["attack_detection_high_purity"] >= det_floor].copy()
    if cand.empty:
        return None
    cand = cand.sort_values(["ood_alarm_ratio_eval", "threshold"], ascending=[True, False])
    return cand.iloc[0]


def safe_std(x: np.ndarray) -> float:
    s = float(np.std(np.asarray(x, dtype=np.float64)))
    return float(max(s, 1e-12))


def zscore(x: np.ndarray, mu: float, sigma: float) -> np.ndarray:
    return (x - float(mu)) / float(max(1e-12, sigma))


def roc_auc_manual(y_true: np.ndarray, y_score: np.ndarray) -> float:
    y = np.asarray(y_true, dtype=np.int64)
    s = np.asarray(y_score, dtype=np.float64)
    mask = np.isfinite(s)
    y = y[mask]
    s = s[mask]
    n = len(y)
    if n == 0:
        return float("nan")
    pos = int(np.sum(y == 1))
    neg = int(np.sum(y == 0))
    if pos == 0 or neg == 0:
        return float("nan")
    order = np.argsort(s, kind="mergesort")
    ranks = np.zeros(n, dtype=np.float64)
    i = 0
    while i < n:
        j = i + 1
        while j < n and s[order[j]] == s[order[i]]:
            j += 1
        avg_rank = 0.5 * (i + (j - 1)) + 1.0
        ranks[order[i:j]] = avg_rank
        i = j
    sum_pos = float(np.sum(ranks[y == 1]))
    auc = (sum_pos - pos * (pos + 1) / 2.0) / (pos * neg)
    return float(auc)


def compute_auc(ood_eval_scores: np.ndarray, attack_high_scores: np.ndarray) -> float:
    y = np.concatenate(
        [
            np.zeros(len(ood_eval_scores), dtype=np.int64),
            np.ones(len(attack_high_scores), dtype=np.int64),
        ]
    )
    s = np.concatenate([ood_eval_scores, attack_high_scores]).astype(np.float64)
    try:
        from sklearn.metrics import roc_auc_score

        return float(roc_auc_score(y, s))
    except Exception:
        return roc_auc_manual(y, s)


def pick_ood_score_file(run_dir: Path, metrics: Dict) -> Path:
    ood_benign = metrics.get("ood_benign", {}) or {}
    if not isinstance(ood_benign, dict) or len(ood_benign) == 0:
        raise RuntimeError(f"Cannot find OOD benign dataset key in metrics: {run_dir / 'metrics.json'}")
    ood_name = list(ood_benign.keys())[0]
    return run_dir / f"{ood_name}_scores.npy"


def _sigmoid(z: np.ndarray) -> np.ndarray:
    z = np.clip(z, -50.0, 50.0)
    return 1.0 / (1.0 + np.exp(-z))


def _latent_transformer(detector, x: np.ndarray, batch_size: int) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
    if not bool(getattr(detector, "fitted", True)):
        x_norm = np.zeros_like(x, dtype=np.float64)
    else:
        denom = np.asarray(detector.norm_max, dtype=np.float64) - np.asarray(detector.norm_min, dtype=np.float64) + 1e-16
        x_norm = (x - np.asarray(detector.norm_min, dtype=np.float64)) / denom
        x_norm = np.nan_to_num(x_norm, nan=0.0, posinf=0.0, neginf=0.0)

    out: List[np.ndarray] = []
    detector.model.eval()
    with torch.no_grad():
        for st in range(0, len(x_norm), batch_size):
            ed = min(len(x_norm), st + batch_size)
            xb = torch.from_numpy(x_norm[st:ed].astype(np.float32)).view(-1, x_norm.shape[1], 1)
            _, h = detector.model(xb, return_latent=True)
            out.append(h.detach().cpu().numpy().astype(np.float32))
    return np.concatenate(out, axis=0) if out else np.zeros((0, 1), dtype=np.float32)


def _latent_da(detector, x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
    denom = np.asarray(detector.norm_max, dtype=np.float64) - np.asarray(detector.norm_min, dtype=np.float64) + 1e-16
    x_norm = (x - np.asarray(detector.norm_min, dtype=np.float64)) / denom
    x_norm = np.nan_to_num(x_norm, nan=0.0, posinf=0.0, neginf=0.0)
    z = np.dot(x_norm, np.asarray(detector.W, dtype=np.float64)) + np.asarray(detector.hbias, dtype=np.float64)
    h = _sigmoid(z)
    return h.astype(np.float32)


def extract_detector_latent(detector, x: np.ndarray, batch_size: int) -> Optional[np.ndarray]:
    if hasattr(detector, "model") and hasattr(detector, "preprocess"):
        return _latent_transformer(detector, x, batch_size=batch_size)
    if hasattr(detector, "get_hidden_values") and hasattr(detector, "W"):
        return _latent_da(detector, x)
    return None


def cosine_distance(h: np.ndarray, c: np.ndarray) -> np.ndarray:
    hn = np.linalg.norm(h, axis=1)
    cn = float(np.linalg.norm(c))
    denom = np.maximum(hn * max(cn, 1e-12), 1e-12)
    sim = np.sum(h * c[None, :], axis=1) / denom
    sim = np.clip(sim, -1.0, 1.0)
    return 1.0 - sim


def compute_latent_center_distance_scores(
    model: kit.KitNET,
    x_id: np.ndarray,
    x_ood: np.ndarray,
    x_attack: np.ndarray,
    batch_size: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict]:
    ens = list(getattr(model, "ensembleLayer", []))
    if len(ens) == 0:
        raise RuntimeError("model has empty ensembleLayer; cannot extract latent score.")

    l2_id = np.zeros(len(x_id), dtype=np.float64)
    l2_ood = np.zeros(len(x_ood), dtype=np.float64)
    l2_attack = np.zeros(len(x_attack), dtype=np.float64)
    cos_id = np.zeros(len(x_id), dtype=np.float64)
    cos_ood = np.zeros(len(x_ood), dtype=np.float64)
    cos_attack = np.zeros(len(x_attack), dtype=np.float64)

    used_detectors = 0
    center_saved = 0
    center_offline = 0
    center_meta_rows: List[Dict] = []

    for i, det in enumerate(ens):
        idx = np.asarray(model.v[i], dtype=np.int64)
        h_id = extract_detector_latent(det, x_id[:, idx], batch_size=batch_size)
        h_ood = extract_detector_latent(det, x_ood[:, idx], batch_size=batch_size)
        h_attack = extract_detector_latent(det, x_attack[:, idx], batch_size=batch_size)
        if h_id is None or h_ood is None or h_attack is None:
            continue
        if h_id.ndim != 2 or h_ood.ndim != 2 or h_attack.ndim != 2:
            continue
        if h_id.shape[1] <= 0:
            continue

        center = None
        center_src = "offline_mean_center_from_id_benign_eval"
        if hasattr(det, "latent_center"):
            c0 = getattr(det, "latent_center", None)
            if c0 is not None:
                c_arr = c0.detach().cpu().numpy() if torch.is_tensor(c0) else np.asarray(c0)
                c_arr = np.asarray(c_arr, dtype=np.float32).reshape(-1)
                if c_arr.shape[0] == h_id.shape[1] and np.all(np.isfinite(c_arr)):
                    center = c_arr
                    center_src = "saved_center_from_checkpoint"

        if center is None:
            center = np.mean(h_id, axis=0).astype(np.float32)
            center = np.nan_to_num(center, nan=0.0, posinf=0.0, neginf=0.0)
            center_offline += 1
        else:
            center_saved += 1

        d_id = np.linalg.norm(h_id - center[None, :], axis=1)
        d_ood = np.linalg.norm(h_ood - center[None, :], axis=1)
        d_attack = np.linalg.norm(h_attack - center[None, :], axis=1)
        c_id = cosine_distance(h_id, center)
        c_ood = cosine_distance(h_ood, center)
        c_attack = cosine_distance(h_attack, center)

        l2_id += d_id.astype(np.float64)
        l2_ood += d_ood.astype(np.float64)
        l2_attack += d_attack.astype(np.float64)
        cos_id += c_id.astype(np.float64)
        cos_ood += c_ood.astype(np.float64)
        cos_attack += c_attack.astype(np.float64)
        used_detectors += 1
        center_meta_rows.append(
            {
                "detector_index": int(i),
                "latent_dim": int(h_id.shape[1]),
                "center_source": center_src,
                "center_l2": float(np.linalg.norm(center)),
                "center_absmax": float(np.max(np.abs(center))),
            }
        )

    if used_detectors <= 0:
        raise RuntimeError("no latent-capable detectors found in ensemble.")

    inv = 1.0 / float(used_detectors)
    l2_id *= inv
    l2_ood *= inv
    l2_attack *= inv
    cos_id *= inv
    cos_ood *= inv
    cos_attack *= inv

    meta = {
        "used_detectors": int(used_detectors),
        "saved_center_detectors": int(center_saved),
        "offline_center_detectors": int(center_offline),
        "center_source_rule": "saved center if available, else offline mean center from ID benign evaluation split",
        "center_rows": center_meta_rows,
    }
    return l2_id, l2_ood, l2_attack, cos_id, cos_ood, cos_attack, meta


def maybe_log_transform(arr_list: List[np.ndarray]) -> Tuple[List[np.ndarray], str]:
    cat = np.concatenate([a[np.isfinite(a)] for a in arr_list if len(a) > 0]) if arr_list else np.array([])
    if len(cat) == 0:
        return arr_list, "score"
    p01 = float(np.quantile(cat, 0.01))
    p99 = float(np.quantile(cat, 0.99))
    if p01 > 0 and p99 / max(p01, 1e-12) > 1e3:
        out = [np.log10(np.clip(a, 1e-12, None)) for a in arr_list]
        return out, "log10(score)"
    return arr_list, "score"


def plot_distribution(
    candidate_label: str,
    score_label: str,
    id_scores: np.ndarray,
    ood_eval_scores: np.ndarray,
    attack_high_scores: np.ndarray,
    fixed_thr: float,
    out_path: Path,
) -> None:
    idv, oodv, atkv = np.asarray(id_scores, dtype=np.float64), np.asarray(ood_eval_scores, dtype=np.float64), np.asarray(
        attack_high_scores, dtype=np.float64
    )
    [idp, oodp, atkp], xlab = maybe_log_transform([idv, oodv, atkv])
    thr_plot = float(np.log10(max(fixed_thr, 1e-12))) if xlab.startswith("log10") else float(fixed_thr)

    plt.figure(figsize=(8.6, 5.0))
    plt.hist(idp, bins=70, density=True, alpha=0.38, label="ID benign")
    plt.hist(oodp, bins=70, density=True, alpha=0.33, label="OOD benign (eval)")
    plt.hist(atkp, bins=70, density=True, alpha=0.33, label="attack high-purity")
    plt.axvline(thr_plot, color="black", linestyle="--", linewidth=1.1, label="fixed threshold")
    plt.xlabel(xlab)
    plt.ylabel("density")
    plt.title(f"{candidate_label} | {score_label} distribution")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=170)
    plt.close()


def plot_tradeoff_by_score(results_df: pd.DataFrame, out_path: Path) -> None:
    score_order = ["rmse", "latent_l2", "latent_cosine", "hybrid_l2", "hybrid_cosine"]
    policy_marker = {
        "fixed_id_q99": "s",
        "naive_calibrated_budget5000_target1pct": "x",
        "det_floor_50pct_min_alarm": "o",
    }
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#17becf", "#e377c2"]
    candidates = sorted(results_df["candidate_label"].unique().tolist())
    color_map = {c: colors[i % len(colors)] for i, c in enumerate(candidates)}

    fig, axes = plt.subplots(1, len(score_order), figsize=(24, 4.6), sharex=False, sharey=False)
    for j, score_type in enumerate(score_order):
        ax = axes[j]
        sub = results_df[(results_df["score_type"] == score_type) & (results_df["selection_feasible"])].copy()
        for c in candidates:
            csub = sub[sub["candidate_label"] == c]
            if csub.empty:
                continue
            for pol, mk in policy_marker.items():
                r = csub[csub["policy_name"] == pol]
                if r.empty:
                    continue
                x = float(r.iloc[0]["ood_alarm_ratio_eval"])
                y = float(r.iloc[0]["attack_detection_high_purity"])
                ax.scatter(x, y, color=color_map[c], marker=mk, s=70, alpha=0.95)
                if pol == "fixed_id_q99":
                    ax.text(x + 0.003, y + 0.008, c, fontsize=7)
        ax.set_title(score_type)
        ax.set_xlabel("OOD benign alarm")
        if j == 0:
            ax.set_ylabel("High-purity attack detection")
        ax.grid(alpha=0.25)
    handles = []
    labels = []
    for pol, mk in policy_marker.items():
        h = plt.Line2D([0], [0], marker=mk, color="black", linestyle="None")
        handles.append(h)
        labels.append(pol.replace("_", " "))
    fig.legend(handles, labels, loc="lower center", ncol=3, frameon=False)
    fig.suptitle("Recipe x score x policy trade-off", fontsize=14)
    plt.tight_layout(rect=[0, 0.08, 1, 0.95])
    plt.savefig(out_path, dpi=180)
    plt.close()


def plot_auc_heatmap(auc_df: pd.DataFrame, out_path: Path) -> None:
    if auc_df.empty:
        return
    score_order = ["rmse", "latent_l2", "latent_cosine", "hybrid_l2", "hybrid_cosine"]
    piv = auc_df.pivot(index="candidate_label", columns="score_type", values="roc_auc_attack_high_vs_ood_eval").reindex(columns=score_order)
    vals = piv.to_numpy(dtype=np.float64)
    plt.figure(figsize=(9.5, max(3.8, 0.6 * len(piv))))
    im = plt.imshow(vals, aspect="auto", cmap="viridis", vmin=np.nanmin(vals), vmax=np.nanmax(vals))
    plt.colorbar(im, fraction=0.025, pad=0.02, label="ROC-AUC")
    plt.xticks(np.arange(len(score_order)), score_order, rotation=20, ha="right")
    plt.yticks(np.arange(len(piv.index)), piv.index.tolist())
    for i in range(vals.shape[0]):
        for j in range(vals.shape[1]):
            v = vals[i, j]
            if np.isfinite(v):
                plt.text(j, i, f"{v:.3f}", ha="center", va="center", fontsize=8, color="white")
    plt.title("attack_high vs OOD_eval ROC-AUC")
    plt.tight_layout()
    plt.savefig(out_path, dpi=180)
    plt.close()


def plot_correlation_scatter(
    candidate_label: str,
    rmse: np.ndarray,
    l2: np.ndarray,
    cos: np.ndarray,
    out_path: Path,
    sample_cap: int = 4000,
) -> Dict[str, float]:
    x = np.asarray(rmse, dtype=np.float64)
    y = np.asarray(l2, dtype=np.float64)
    z = np.asarray(cos, dtype=np.float64)
    mask = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
    x = x[mask]
    y = y[mask]
    z = z[mask]
    if len(x) == 0:
        corr_rmse_l2 = float("nan")
        corr_rmse_cos = float("nan")
        corr_l2_cos = float("nan")
    else:
        corr_rmse_l2 = float(np.corrcoef(x, y)[0, 1])
        corr_rmse_cos = float(np.corrcoef(x, z)[0, 1])
        corr_l2_cos = float(np.corrcoef(y, z)[0, 1])
    if len(x) > sample_cap:
        rng = np.random.default_rng(42)
        idx = np.sort(rng.choice(len(x), size=sample_cap, replace=False))
        x = x[idx]
        y = y[idx]
        z = z[idx]
    fig, axes = plt.subplots(1, 3, figsize=(14.4, 4.0))
    axes[0].scatter(x, y, s=7, alpha=0.35)
    axes[0].set_xlabel("RMSE")
    axes[0].set_ylabel("Latent-L2")
    axes[0].set_title(f"corr={corr_rmse_l2:.3f}" if np.isfinite(corr_rmse_l2) else "corr=nan")
    axes[1].scatter(x, z, s=7, alpha=0.35)
    axes[1].set_xlabel("RMSE")
    axes[1].set_ylabel("Latent-Cosine")
    axes[1].set_title(f"corr={corr_rmse_cos:.3f}" if np.isfinite(corr_rmse_cos) else "corr=nan")
    axes[2].scatter(y, z, s=7, alpha=0.35)
    axes[2].set_xlabel("Latent-L2")
    axes[2].set_ylabel("Latent-Cosine")
    axes[2].set_title(f"corr={corr_l2_cos:.3f}" if np.isfinite(corr_l2_cos) else "corr=nan")
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.suptitle(f"{candidate_label}: score correlation")
    plt.tight_layout()
    plt.savefig(out_path, dpi=175)
    plt.close()
    return {
        "corr_rmse_l2": corr_rmse_l2,
        "corr_rmse_cos": corr_rmse_cos,
        "corr_l2_cos": corr_l2_cos,
    }


@dataclass
class Candidate:
    detector: str
    candidate_label: str
    run_dir: Path
    checkpoint: Path
    attack_score_file: Path
    source_mode: str
    notes: str


def build_candidates(
    source_root: Path,
    latent_v1_dir: Path,
    neg_sem_dir: Path,
    seed: int,
    extra_candidates: Optional[List[Candidate]] = None,
) -> List[Candidate]:
    stage1_joint = source_root / "runs" / "frontend100_joint_eval_stage1_2026-03-31"
    base_transformer_dir = source_root / "runs" / "frontend100_tailreg_stage1_2026-03-27" / f"transformer_seed{seed}"
    base_tailreg_dir = source_root / "runs" / "frontend100_tailreg_hparam_scan_2026-03-28" / f"tailreg_l0.2_k1.0_seed{seed}"
    base_da_dir = source_root / "runs" / "frontend100_tailreg_stage1_2026-03-27" / f"da_seed{seed}"

    v1_manifest = load_json(latent_v1_dir / "latent_contrastive_v1_config_manifest.json")
    v1_label = str(v1_manifest.get("recommended", {}).get("detector_label", "transformer_latent_contrastive_v1_m5.0_l0.5"))
    v1_info = (v1_manifest.get("detector_info", {}) or {}).get(v1_label, {})
    if not v1_info:
        raise RuntimeError(f"Cannot resolve latent_contrastive_v1_best from {latent_v1_dir}")

    neg_manifest = load_json(neg_sem_dir / "negative_semantics_ablation_manifest.json")
    neg_info = neg_manifest.get("detector_info", {}) or {}
    for key in ["latent_swap_spike_mix", "latent_swap_only"]:
        if key not in neg_info:
            raise RuntimeError(f"Cannot resolve {key} in {neg_sem_dir}")

    default_candidates = [
        Candidate(
            detector="transformer_latent_contrastive_v1_best",
            candidate_label="latent_contrastive_v1_best",
            run_dir=Path(v1_info["run_dir"]),
            checkpoint=Path(v1_info["checkpoint"]),
            attack_score_file=Path(v1_info["attack_score_file"]),
            source_mode="reuse_manifest_v1_best",
            notes=f"detector_label={v1_label}",
        ),
        Candidate(
            detector="transformer_latent_semantics",
            candidate_label="latent_swap_spike_mix",
            run_dir=Path(neg_info["latent_swap_spike_mix"]["run_dir"]),
            checkpoint=Path(neg_info["latent_swap_spike_mix"]["checkpoint"]),
            attack_score_file=Path(neg_info["latent_swap_spike_mix"]["attack_score_file"]),
            source_mode="reuse_negative_semantics",
            notes="recipe=swap+spike",
        ),
        Candidate(
            detector="transformer_latent_semantics",
            candidate_label="latent_swap_only",
            run_dir=Path(neg_info["latent_swap_only"]["run_dir"]),
            checkpoint=Path(neg_info["latent_swap_only"]["checkpoint"]),
            attack_score_file=Path(neg_info["latent_swap_only"]["attack_score_file"]),
            source_mode="reuse_negative_semantics",
            notes="recipe=swap_only",
        ),
        Candidate(
            detector="transformer_tailreg",
            candidate_label="transformer_tailreg",
            run_dir=base_tailreg_dir,
            checkpoint=Path(load_json(base_tailreg_dir / "config.json")["checkpoint"]),
            attack_score_file=stage1_joint / "transformer_tailreg_attack_scores.npy",
            source_mode="reuse_baseline",
            notes="baseline",
        ),
        Candidate(
            detector="transformer",
            candidate_label="transformer",
            run_dir=base_transformer_dir,
            checkpoint=Path(load_json(base_transformer_dir / "config.json")["checkpoint"]),
            attack_score_file=stage1_joint / "transformer_attack_scores.npy",
            source_mode="reuse_baseline",
            notes="baseline",
        ),
        Candidate(
            detector="da",
            candidate_label="da",
            run_dir=base_da_dir,
            checkpoint=Path(load_json(base_da_dir / "config.json")["checkpoint"]),
            attack_score_file=stage1_joint / "da_attack_scores.npy",
            source_mode="reuse_baseline",
            notes="reference",
        ),
    ]
    if extra_candidates:
        seen = {c.candidate_label for c in default_candidates}
        for c in extra_candidates:
            if c.candidate_label in seen:
                continue
            default_candidates.append(c)
            seen.add(c.candidate_label)
    return default_candidates


def parse_extra_candidate(spec: str) -> Candidate:
    parts = spec.split("|")
    if len(parts) != 7:
        raise ValueError(
            "--extra-candidate must be: candidate_label|detector|run_dir|checkpoint|attack_score_file|source_mode|notes"
        )
    candidate_label, detector, run_dir, checkpoint, attack_score_file, source_mode, notes = [p.strip() for p in parts]
    if not candidate_label:
        raise ValueError("candidate_label cannot be empty in --extra-candidate")
    return Candidate(
        detector=detector,
        candidate_label=candidate_label,
        run_dir=Path(run_dir),
        checkpoint=Path(checkpoint),
        attack_score_file=Path(attack_score_file),
        source_mode=source_mode,
        notes=notes,
    )


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(
        description="Strict offline rescoring for key latent recipes (RMSE vs latent/hybrid scores)."
    )
    parser.add_argument("--run-tag", default=f"frontend100_negative_recipe_rescoring_{today}")
    parser.add_argument(
        "--source-root",
        type=Path,
        default=WORKTREE_ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master",
    )
    parser.add_argument(
        "--latent-v1-dir",
        type=Path,
        default=WORKTREE_ROOT / "runs" / "frontend100_latent_contrastive_v1_2026-04-04",
    )
    parser.add_argument(
        "--negative-semantics-dir",
        type=Path,
        default=WORKTREE_ROOT / "runs" / "frontend100_negative_semantics_ablation_2026-04-05",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--scan-points", type=int, default=901)
    parser.add_argument("--calibration-budget", type=int, default=5000)
    parser.add_argument("--calibration-target", type=float, default=0.01)
    parser.add_argument("--det-floor", type=float, default=0.50)
    parser.add_argument("--batch-size", type=int, default=1024)
    parser.add_argument("--force-recompute-latent", action="store_true")
    parser.add_argument(
        "--extra-candidate",
        action="append",
        default=None,
        help="candidate_label|detector|run_dir|checkpoint|attack_score_file|source_mode|notes",
    )
    args = parser.parse_args()

    out_dir = WORKTREE_ROOT / "runs" / args.run_tag
    out_dir.mkdir(parents=True, exist_ok=True)
    plot_dir = out_dir / "negative_recipe_rescoring_plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = out_dir / "cache_rescored_scores"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "command.txt").write_text("python " + " ".join(os.sys.argv) + "\n", encoding="utf-8")

    source_root = args.source_root
    crosscapture_data = source_root / "runs" / "frontend100_crosscapture_stage1_2026-03-25" / "data"
    stage1_joint = source_root / "runs" / "frontend100_joint_eval_stage1_2026-03-31"
    stage2_joint = source_root / "runs" / "frontend100_joint_eval_stage2_2026-04-01"
    stage2_manifest = load_json(stage2_joint / "attack_manifest_stage2.json")
    stage2_idx = build_stage2_indices(stage2_manifest)
    high_idx = stage2_idx["high"]
    mixed_idx = stage2_idx["mixed"]
    if len(high_idx) == 0:
        raise RuntimeError("stage2 high-purity indices are empty")

    ablation_manifest = load_json(args.negative_semantics_dir / "negative_semantics_ablation_manifest.json")
    train_samples = int(((ablation_manifest.get("train_config", {}) or {}).get("train_samples", 8000)))
    id_eval_samples = int(((ablation_manifest.get("train_config", {}) or {}).get("id_eval_samples", 5000)))

    train_csv = crosscapture_data / "id_source_100.csv"
    ood_benign_csv = crosscapture_data / "ood_benign_source_100.csv"
    attack_csv = stage1_joint / "data" / "attack_source_100.csv"
    if not train_csv.exists():
        raise FileNotFoundError(f"Missing train csv: {train_csv}")
    if not ood_benign_csv.exists():
        raise FileNotFoundError(f"Missing OOD benign csv: {ood_benign_csv}")
    if not attack_csv.exists():
        raise FileNotFoundError(f"Missing attack csv: {attack_csv}")

    x_train_all = pd.read_csv(train_csv, header=None, nrows=train_samples + id_eval_samples).to_numpy(dtype=np.float64)
    if len(x_train_all) < train_samples + id_eval_samples:
        raise RuntimeError("train csv rows fewer than expected train+id_eval.")
    x_id = x_train_all[train_samples : train_samples + id_eval_samples]
    x_ood = pd.read_csv(ood_benign_csv, header=None).to_numpy(dtype=np.float64)
    x_attack = pd.read_csv(attack_csv, header=None).to_numpy(dtype=np.float64)

    if len(x_attack) <= int(np.max(high_idx)):
        raise RuntimeError("attack csv rows fewer than stage2 high-purity index max.")

    extra_candidates = [parse_extra_candidate(s) for s in (args.extra_candidate or [])]
    candidates = build_candidates(
        source_root=source_root,
        latent_v1_dir=args.latent_v1_dir,
        neg_sem_dir=args.negative_semantics_dir,
        seed=args.seed,
        extra_candidates=extra_candidates,
    )

    score_types = ["rmse", "latent_l2", "latent_cosine", "hybrid_l2", "hybrid_cosine"]
    policy_rows: List[Dict] = []
    auc_rows: List[Dict] = []
    corr_rows: List[Dict] = []
    center_manifest: Dict[str, Dict] = {}
    zstats_manifest: Dict[str, Dict] = {}

    for cand in candidates:
        if not cand.run_dir.exists():
            raise FileNotFoundError(f"Missing run dir for {cand.candidate_label}: {cand.run_dir}")
        if not cand.checkpoint.exists():
            raise FileNotFoundError(f"Missing checkpoint for {cand.candidate_label}: {cand.checkpoint}")
        if not cand.attack_score_file.exists():
            raise FileNotFoundError(f"Missing attack score file for {cand.candidate_label}: {cand.attack_score_file}")

        metrics = load_json(cand.run_dir / "metrics.json")
        rmse_id = np.load(cand.run_dir / "id_scores.npy").astype(np.float64)
        rmse_ood = np.load(pick_ood_score_file(cand.run_dir, metrics)).astype(np.float64)
        rmse_attack = np.load(cand.attack_score_file).astype(np.float64)

        if len(rmse_id) != len(x_id):
            raise RuntimeError(
                f"ID score length mismatch for {cand.candidate_label}: {len(rmse_id)} vs feature {len(x_id)}"
            )
        if len(rmse_ood) != len(x_ood):
            raise RuntimeError(
                f"OOD score length mismatch for {cand.candidate_label}: {len(rmse_ood)} vs feature {len(x_ood)}"
            )
        if len(rmse_attack) != len(x_attack):
            raise RuntimeError(
                f"attack score length mismatch for {cand.candidate_label}: {len(rmse_attack)} vs feature {len(x_attack)}"
            )

        latent_cache_prefix = cache_dir / f"{cand.candidate_label}_latent"
        latent_id_file = latent_cache_prefix.with_name(latent_cache_prefix.name + "_id_l2.npy")
        latent_ood_file = latent_cache_prefix.with_name(latent_cache_prefix.name + "_ood_l2.npy")
        latent_attack_file = latent_cache_prefix.with_name(latent_cache_prefix.name + "_attack_l2.npy")
        cos_id_file = latent_cache_prefix.with_name(latent_cache_prefix.name + "_id_cos.npy")
        cos_ood_file = latent_cache_prefix.with_name(latent_cache_prefix.name + "_ood_cos.npy")
        cos_attack_file = latent_cache_prefix.with_name(latent_cache_prefix.name + "_attack_cos.npy")
        center_meta_file = latent_cache_prefix.with_name(latent_cache_prefix.name + "_center_meta.json")

        if (
            (not args.force_recompute_latent)
            and latent_id_file.exists()
            and latent_ood_file.exists()
            and latent_attack_file.exists()
            and cos_id_file.exists()
            and cos_ood_file.exists()
            and cos_attack_file.exists()
            and center_meta_file.exists()
        ):
            latent_id = np.load(latent_id_file).astype(np.float64)
            latent_ood = np.load(latent_ood_file).astype(np.float64)
            latent_attack = np.load(latent_attack_file).astype(np.float64)
            cos_id = np.load(cos_id_file).astype(np.float64)
            cos_ood = np.load(cos_ood_file).astype(np.float64)
            cos_attack = np.load(cos_attack_file).astype(np.float64)
            center_meta = load_json(center_meta_file)
            center_meta["score_source"] = "cached"
        else:
            model = kit.KitNET.load_checkpoint(cand.checkpoint)
            latent_id, latent_ood, latent_attack, cos_id, cos_ood, cos_attack, center_meta = compute_latent_center_distance_scores(
                model=model,
                x_id=x_id,
                x_ood=x_ood,
                x_attack=x_attack,
                batch_size=args.batch_size,
            )
            np.save(latent_id_file, latent_id)
            np.save(latent_ood_file, latent_ood)
            np.save(latent_attack_file, latent_attack)
            np.save(cos_id_file, cos_id)
            np.save(cos_ood_file, cos_ood)
            np.save(cos_attack_file, cos_attack)
            center_meta["score_source"] = "computed_now"
            center_meta_file.write_text(json.dumps(sanitize_for_json(center_meta), indent=2, ensure_ascii=False), encoding="utf-8")

        rmse_mu = float(np.mean(rmse_id))
        rmse_sigma = safe_std(rmse_id)
        l2_mu = float(np.mean(latent_id))
        l2_sigma = safe_std(latent_id)
        cos_mu = float(np.mean(cos_id))
        cos_sigma = safe_std(cos_id)
        zstats_manifest[cand.candidate_label] = {
            "source": "ID benign evaluation split only",
            "rmse_mu": rmse_mu,
            "rmse_sigma": rmse_sigma,
            "l2_mu": l2_mu,
            "l2_sigma": l2_sigma,
            "cos_mu": cos_mu,
            "cos_sigma": cos_sigma,
            "id_eval_samples": int(len(rmse_id)),
        }

        hybrid_l2_id = zscore(rmse_id, rmse_mu, rmse_sigma) + zscore(latent_id, l2_mu, l2_sigma)
        hybrid_l2_ood = zscore(rmse_ood, rmse_mu, rmse_sigma) + zscore(latent_ood, l2_mu, l2_sigma)
        hybrid_l2_attack = zscore(rmse_attack, rmse_mu, rmse_sigma) + zscore(latent_attack, l2_mu, l2_sigma)
        hybrid_cos_id = zscore(rmse_id, rmse_mu, rmse_sigma) + zscore(cos_id, cos_mu, cos_sigma)
        hybrid_cos_ood = zscore(rmse_ood, rmse_mu, rmse_sigma) + zscore(cos_ood, cos_mu, cos_sigma)
        hybrid_cos_attack = zscore(rmse_attack, rmse_mu, rmse_sigma) + zscore(cos_attack, cos_mu, cos_sigma)

        score_pack = {
            "rmse": (rmse_id, rmse_ood, rmse_attack),
            "latent_l2": (latent_id, latent_ood, latent_attack),
            "latent_cosine": (cos_id, cos_ood, cos_attack),
            "hybrid_l2": (hybrid_l2_id, hybrid_l2_ood, hybrid_l2_attack),
            "hybrid_cosine": (hybrid_cos_id, hybrid_cos_ood, hybrid_cos_attack),
        }

        center_manifest[cand.candidate_label] = {
            "checkpoint": str(cand.checkpoint),
            "used_rule": center_meta.get("center_source_rule", ""),
            "used_detectors": int(center_meta.get("used_detectors", 0)),
            "saved_center_detectors": int(center_meta.get("saved_center_detectors", 0)),
            "offline_center_detectors": int(center_meta.get("offline_center_detectors", 0)),
            "score_source": center_meta.get("score_source", ""),
            "center_rows_preview": (center_meta.get("center_rows", []) or [])[:8],
        }

        # Distribution plots (required: RMSE / L2 / Cosine)
        for stype, sdisplay in [("rmse", "RMSE"), ("latent_l2", "Latent-L2"), ("latent_cosine", "Latent-Cosine")]:
            sid, sood, satt = score_pack[stype]
            budget = int(min(max(1, args.calibration_budget), len(sood) - 1))
            ood_eval = sood[budget:]
            fixed_thr = float(metrics["threshold_value"]) if stype == "rmse" else float(np.quantile(sid, 0.99))
            plot_distribution(
                candidate_label=cand.candidate_label,
                score_label=sdisplay,
                id_scores=sid,
                ood_eval_scores=ood_eval,
                attack_high_scores=satt[high_idx],
                fixed_thr=fixed_thr,
                out_path=plot_dir / f"distribution_{cand.candidate_label}_{stype}.png",
            )

        # Correlation analysis (RMSE/L2/Cosine)
        budget_tmp = int(min(max(1, args.calibration_budget), len(rmse_ood) - 1))
        corr_all_rmse = np.concatenate([rmse_id, rmse_ood[budget_tmp:], rmse_attack[high_idx]])
        corr_all_l2 = np.concatenate([latent_id, latent_ood[budget_tmp:], latent_attack[high_idx]])
        corr_all_cos = np.concatenate([cos_id, cos_ood[budget_tmp:], cos_attack[high_idx]])
        corr = plot_correlation_scatter(
            candidate_label=cand.candidate_label,
            rmse=corr_all_rmse,
            l2=corr_all_l2,
            cos=corr_all_cos,
            out_path=plot_dir / f"score_correlation_{cand.candidate_label}.png",
        )
        corr_rows.append(
            {
                "candidate_label": cand.candidate_label,
                "corr_rmse_l2": corr["corr_rmse_l2"],
                "corr_rmse_cos": corr["corr_rmse_cos"],
                "corr_l2_cos": corr["corr_l2_cos"],
            }
        )

        for stype in score_types:
            sid, sood, satt = score_pack[stype]
            budget = int(min(max(1, args.calibration_budget), len(sood) - 1))
            ood_cal = sood[:budget]
            ood_eval = sood[budget:]

            if stype == "rmse":
                fixed_thr = float(metrics["threshold_value"])
                fixed_src = "official_metrics_threshold"
            else:
                fixed_thr = float(np.quantile(sid, 0.99))
                fixed_src = "id_q99_of_this_score"
            naive_thr = float(np.quantile(ood_cal, 1.0 - args.calibration_target))

            ref = np.concatenate([sid, sood, satt]).astype(np.float64)
            thresholds = np.quantile(ref, np.linspace(0.0, 1.0, args.scan_points))
            thresholds = np.unique(np.concatenate([thresholds, [fixed_thr, naive_thr]])).astype(np.float64)
            scan_rows = [
                eval_threshold(
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
            scan_df = pd.DataFrame(scan_rows)
            fixed_row = scan_df.iloc[(np.abs(scan_df["threshold"] - fixed_thr)).argmin()]
            naive_row = scan_df.iloc[(np.abs(scan_df["threshold"] - naive_thr)).argmin()]
            det50_row = choose_detection_floor(scan_df, args.det_floor)

            fixed_alarm = float(fixed_row["ood_alarm_ratio_eval"])
            fixed_det = float(fixed_row["attack_detection_high_purity"])

            def add_policy(policy_name: str, row: Optional[pd.Series], thr_src: str) -> None:
                if row is None:
                    policy_rows.append(
                        {
                            "candidate_label": cand.candidate_label,
                            "detector": cand.detector,
                            "source_mode": cand.source_mode,
                            "notes": cand.notes,
                            "score_type": stype,
                            "policy_name": policy_name,
                            "selection_feasible": False,
                            "threshold": float("nan"),
                            "threshold_source": thr_src,
                            "id_alarm_ratio": float("nan"),
                            "ood_alarm_ratio_full": float("nan"),
                            "ood_alarm_ratio_eval": float("nan"),
                            "attack_detection_all": float("nan"),
                            "attack_detection_high_purity": float("nan"),
                            "attack_detection_boundary": float("nan"),
                            "alarm_reduction_vs_fixed": float("nan"),
                            "detection_retention_vs_fixed": float("nan"),
                            "fixed_alarm_ref": fixed_alarm,
                            "fixed_detection_ref": fixed_det,
                        }
                    )
                    return

                alarm = float(row["ood_alarm_ratio_eval"])
                det_hp = float(row["attack_detection_high_purity"])
                policy_rows.append(
                    {
                        "candidate_label": cand.candidate_label,
                        "detector": cand.detector,
                        "source_mode": cand.source_mode,
                        "notes": cand.notes,
                        "score_type": stype,
                        "policy_name": policy_name,
                        "selection_feasible": True,
                        "threshold": float(row["threshold"]),
                        "threshold_source": thr_src,
                        "id_alarm_ratio": float(row["id_alarm_ratio"]),
                        "ood_alarm_ratio_full": float(row["ood_alarm_ratio_full"]),
                        "ood_alarm_ratio_eval": alarm,
                        "attack_detection_all": float(row["attack_detection_all"]),
                        "attack_detection_high_purity": det_hp,
                        "attack_detection_boundary": float(row["attack_detection_boundary"]),
                        "alarm_reduction_vs_fixed": float(fixed_alarm - alarm),
                        "detection_retention_vs_fixed": float(det_hp / max(1e-12, fixed_det)),
                        "fixed_alarm_ref": fixed_alarm,
                        "fixed_detection_ref": fixed_det,
                    }
                )

            add_policy("fixed_id_q99", fixed_row, fixed_src)
            add_policy("naive_calibrated_budget5000_target1pct", naive_row, "ood_cal_q99_of_this_score")
            add_policy("det_floor_50pct_min_alarm", det50_row, "scan_min_alarm_subject_to_detection_floor")

            auc_rows.append(
                {
                    "candidate_label": cand.candidate_label,
                    "score_type": stype,
                    "roc_auc_attack_high_vs_ood_eval": compute_auc(ood_eval_scores=ood_eval, attack_high_scores=satt[high_idx]),
                }
            )

    results_df = pd.DataFrame(policy_rows).sort_values(["candidate_label", "score_type", "policy_name"])
    auc_df = pd.DataFrame(auc_rows).sort_values(["candidate_label", "score_type"])
    corr_df = pd.DataFrame(corr_rows).sort_values("candidate_label")

    results_csv = out_dir / "negative_recipe_rescoring_results.csv"
    results_df.to_csv(results_csv, index=False)
    auc_df.to_csv(out_dir / "negative_recipe_rescoring_auc.csv", index=False)
    corr_df.to_csv(out_dir / "negative_recipe_rescoring_correlations.csv", index=False)

    show_cols = [
        "candidate_label",
        "score_type",
        "policy_name",
        "threshold",
        "ood_alarm_ratio_eval",
        "attack_detection_high_purity",
        "attack_detection_boundary",
        "alarm_reduction_vs_fixed",
        "detection_retention_vs_fixed",
    ]
    (out_dir / "negative_recipe_rescoring_results.md").write_text(md_table(results_df[show_cols]), encoding="utf-8")

    plot_tradeoff_by_score(results_df, plot_dir / "recipe_score_policy_tradeoff.png")
    plot_auc_heatmap(auc_df, plot_dir / "attack_vs_ood_roc_auc_heatmap.png")

    def gv(cand: str, stype: str, policy: str, col: str) -> float:
        sub = results_df[
            (results_df["candidate_label"] == cand)
            & (results_df["score_type"] == stype)
            & (results_df["policy_name"] == policy)
            & (results_df["selection_feasible"])
        ]
        if sub.empty:
            return float("nan")
        return float(sub.iloc[0][col])

    key_candidates = ["latent_contrastive_v1_best", "latent_swap_spike_mix", "latent_swap_only"]
    fixed_util_rows = []
    for c in key_candidates:
        for st in score_types:
            alarm = gv(c, st, "fixed_id_q99", "ood_alarm_ratio_eval")
            det = gv(c, st, "fixed_id_q99", "attack_detection_high_purity")
            util = det - alarm if np.isfinite(alarm) and np.isfinite(det) else float("nan")
            fixed_util_rows.append((c, st, alarm, det, util))
    fixed_util_df = pd.DataFrame(
        fixed_util_rows,
        columns=["candidate_label", "score_type", "alarm", "detection", "utility"],
    )

    spike_rmse_alarm = gv("latent_swap_spike_mix", "rmse", "fixed_id_q99", "ood_alarm_ratio_eval")
    spike_best_non_rmse = fixed_util_df[fixed_util_df["candidate_label"] == "latent_swap_spike_mix"].sort_values(
        "utility", ascending=False
    )
    spike_best_non_rmse = spike_best_non_rmse[spike_best_non_rmse["score_type"] != "rmse"]
    spike_best_row = spike_best_non_rmse.iloc[0] if not spike_best_non_rmse.empty else None

    rec_score_df = fixed_util_df[fixed_util_df["candidate_label"].isin(key_candidates)].groupby("score_type", as_index=False)["utility"].mean()
    rec_score_df = rec_score_df.sort_values("utility", ascending=False)
    rec_score = str(rec_score_df.iloc[0]["score_type"]) if not rec_score_df.empty else "rmse"

    lines: List[str] = []
    lines.append("# Negative Recipe Rescoring Summary")
    lines.append("")
    lines.append("## Setup")
    lines.append("- Mode: strict offline rescoring only (no new training, no checkpoint modification).")
    lines.append("- Mainline: original-frontend 100D + stronger OOD.")
    lines.append("- Candidates: latent_contrastive_v1_best / latent_swap_spike_mix / latent_swap_only / transformer_tailreg / transformer / da.")
    lines.append("- Score families: RMSE, Latent-L2, Latent-Cosine, Hybrid-L2, Hybrid-Cosine.")
    lines.append("- Policies: fixed_id_q99, naive_calibrated_budget5000_target1pct, det_floor_50pct_min_alarm.")
    lines.append("- Hybrid z-score stats source: ID benign evaluation split only (strict no OOD/attack leakage).")
    lines.append("- Center rule: use saved center if checkpoint contains explicit center; otherwise offline mean center from ID benign split only.")
    lines.append("")
    lines.append("## Required answers")
    lines.append("1. Was there a case where recipe is useful but RMSE scoring underestimates it?")
    if spike_best_row is None:
        lines.append("- Evidence insufficient (no valid non-RMSE fixed point for latent_swap_spike_mix).")
    else:
        lines.append(
            f"- latent_swap_spike_mix: fixed RMSE alarm={spike_rmse_alarm:.4f}; best non-RMSE ({spike_best_row['score_type']}) "
            f"alarm={float(spike_best_row['alarm']):.4f}, det={float(spike_best_row['detection']):.4f}, utility={float(spike_best_row['utility']):.4f}."
        )
    lines.append("2. Should latent_swap_spike_mix be kept as next main candidate?")
    if spike_best_row is not None and np.isfinite(float(spike_best_row["utility"])) and float(spike_best_row["utility"]) > float(
        gv("latent_contrastive_v1_best", "rmse", "fixed_id_q99", "attack_detection_high_purity")
        - gv("latent_contrastive_v1_best", "rmse", "fixed_id_q99", "ood_alarm_ratio_eval")
    ):
        lines.append("- Keep as conditional candidate under better score rule (not under RMSE-only).")
    else:
        lines.append("- Keep as secondary candidate only; current evidence does not support replacing v1_best as primary.")
    lines.append("3. Should latent_swap_only be dropped?")
    swap_only_best = fixed_util_df[fixed_util_df["candidate_label"] == "latent_swap_only"]["utility"].max()
    if np.isfinite(swap_only_best) and swap_only_best > -0.02:
        lines.append("- Not yet; retain as low-risk baseline recipe for multi-seed sanity checks.")
    else:
        lines.append("- Can be deprioritized if compute is tight; utility remains weak in this rescoring round.")
    lines.append("4. Which score is currently most recommended?")
    lines.append(f"- Recommended by mean fixed utility on latent recipes: `{rec_score}`.")
    lines.append("5. What is the next best step?")
    if rec_score in {"latent_l2", "latent_cosine", "hybrid_l2", "hybrid_cosine"}:
        lines.append("- Move to minimal multi-seed on best recipe + best score; compactness can be re-stacked only after score rule is fixed.")
    else:
        lines.append("- Continue improving negative semantics first; current gains are not primarily from scoring.")
    lines.append("")
    lines.append("## Additional observations")
    lines.append("- Naive calibration remains prone to near-zero detection across several candidate-score pairs.")
    lines.append("- Constrained det_floor=50% still provides healthier operating points than naive in most candidate-score pairs.")
    lines.append("- See `negative_recipe_rescoring_auc.csv` and `negative_recipe_rescoring_correlations.csv` for score-separation and complementarity details.")
    summary_text = "\n".join(lines) + "\n"
    (out_dir / "negative_recipe_rescoring_summary.md").write_text(summary_text, encoding="utf-8")
    (out_dir / "summary.md").write_text(summary_text, encoding="utf-8")

    manifest = {
        "stage": "frontend100_negative_recipe_rescoring",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_tag": args.run_tag,
        "source_root": str(source_root),
        "seed": int(args.seed),
        "no_training": True,
        "no_checkpoint_modification": True,
        "scan_points": int(args.scan_points),
        "calibration": {
            "budget": int(args.calibration_budget),
            "target_alarm": float(args.calibration_target),
            "det_floor": float(args.det_floor),
        },
        "data_splits": {
            "train_samples": int(train_samples),
            "id_eval_samples": int(id_eval_samples),
            "ood_total_samples": int(len(x_ood)),
            "attack_total_samples": int(len(x_attack)),
            "stage2_high_purity_count": int(len(high_idx)),
            "stage2_boundary_count": int(len(mixed_idx)),
        },
        "candidates": [
            {
                "candidate_label": c.candidate_label,
                "detector": c.detector,
                "run_dir": str(c.run_dir),
                "checkpoint": str(c.checkpoint),
                "attack_score_file": str(c.attack_score_file),
                "source_mode": c.source_mode,
                "notes": c.notes,
            }
            for c in candidates
        ],
        "score_definitions": {
            "rmse": "existing reconstruction error score from run artifacts",
            "latent_l2": "mean over ensemble detectors: ||h_i(x)-c_i||_2",
            "latent_cosine": "mean over ensemble detectors: 1-cos(h_i(x), c_i)",
            "hybrid_l2": "z(RMSE)+z(Latent-L2), z stats from ID benign eval only",
            "hybrid_cosine": "z(RMSE)+z(Latent-Cosine), z stats from ID benign eval only",
        },
        "center_source_audit": center_manifest,
        "zscore_source_audit": zstats_manifest,
        "outputs": {
            "results_csv": str(results_csv),
            "results_md": str(out_dir / "negative_recipe_rescoring_results.md"),
            "summary_md": str(out_dir / "negative_recipe_rescoring_summary.md"),
            "auc_csv": str(out_dir / "negative_recipe_rescoring_auc.csv"),
            "correlation_csv": str(out_dir / "negative_recipe_rescoring_correlations.csv"),
            "plots_dir": str(plot_dir),
        },
    }
    manifest = sanitize_for_json(manifest)
    (out_dir / "negative_recipe_rescoring_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out_dir / "config.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[done] offline rescoring output: {out_dir}")


if __name__ == "__main__":
    main()
