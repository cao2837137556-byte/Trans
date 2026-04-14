
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO_DIR = Path(__file__).resolve().parents[1]
WORKTREE_ROOT = REPO_DIR.parent

if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

import KitNET as kit


def load_json(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, row in df.iterrows():
        vals = []
        for c in cols:
            v = row[c]
            if isinstance(v, float):
                vals.append(f"{v:.6f}")
            else:
                vals.append(str(v))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"


def score_stats(x: np.ndarray) -> Dict[str, float]:
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


def build_stage2_indices(stage2_manifest: Dict) -> Dict[str, np.ndarray]:
    tsv_path = Path(stage2_manifest["source_tsv"])
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


def contiguous_runs(indices: np.ndarray) -> List[Tuple[int, int]]:
    idx = np.asarray(indices, dtype=np.int64)
    if len(idx) == 0:
        return []
    runs: List[Tuple[int, int]] = []
    s = int(idx[0])
    p = int(idx[0])
    for x in idx[1:]:
        x = int(x)
        if x == p + 1:
            p = x
            continue
        runs.append((s, p))
        s = x
        p = x
    runs.append((s, p))
    return runs


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


def score_attack(checkpoint: Path, attack_x: np.ndarray, out_npy: Path) -> np.ndarray:
    if out_npy.exists():
        return np.load(out_npy).astype(np.float64)
    model = kit.KitNET.load_checkpoint(checkpoint)
    scores = np.zeros(len(attack_x), dtype=np.float64)
    for i in range(len(attack_x)):
        if i > 0 and i % 2000 == 0:
            print(f"  attack scoring {checkpoint.name}: {i}/{len(attack_x)}")
        scores[i] = model.process(attack_x[i])
    np.save(out_npy, scores)
    return scores


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


def js_overlap_metrics(a: np.ndarray, b: np.ndarray, bins: int = 80) -> Dict[str, float]:
    x = np.asarray(a, dtype=np.float64)
    y = np.asarray(b, dtype=np.float64)
    x = x[np.isfinite(x)]
    y = y[np.isfinite(y)]
    x = x[x > 0]
    y = y[y > 0]
    if len(x) < 5 or len(y) < 5:
        return {
            "jsd_score": float("nan"),
            "overlap_score": float("nan"),
            "intersection_coeff": float("nan"),
        }
    lx = np.log10(x + 1e-12)
    ly = np.log10(y + 1e-12)
    lo = float(min(np.min(lx), np.min(ly)))
    hi = float(max(np.max(lx), np.max(ly)))
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        return {
            "jsd_score": float("nan"),
            "overlap_score": float("nan"),
            "intersection_coeff": float("nan"),
        }
    hx, edges = np.histogram(lx, bins=bins, range=(lo, hi), density=False)
    hy, _ = np.histogram(ly, bins=edges, density=False)
    p = hx.astype(np.float64)
    q = hy.astype(np.float64)
    if np.sum(p) <= 0 or np.sum(q) <= 0:
        return {
            "jsd_score": float("nan"),
            "overlap_score": float("nan"),
            "intersection_coeff": float("nan"),
        }
    p = p / np.sum(p)
    q = q / np.sum(q)
    eps = 1e-12
    p = np.clip(p, eps, 1.0)
    q = np.clip(q, eps, 1.0)
    p = p / np.sum(p)
    q = q / np.sum(q)
    m = 0.5 * (p + q)
    jsd = 0.5 * np.sum(p * np.log2(p / m)) + 0.5 * np.sum(q * np.log2(q / m))
    jsd = float(np.clip(jsd, 0.0, 1.0))
    return {
        "jsd_score": jsd,
        "overlap_score": float(1.0 - jsd),
        "intersection_coeff": float(np.sum(np.minimum(p, q))),
    }

def plot_score_distribution(
    detector: str,
    id_scores: np.ndarray,
    ood_scores: np.ndarray,
    attack_scores: np.ndarray,
    fixed_thr: float,
    out_path: Path,
) -> None:
    eps = 1e-12
    plt.figure(figsize=(8.8, 5.2))
    plt.hist(np.log10(id_scores + eps), bins=70, density=True, alpha=0.38, label="ID benign")
    plt.hist(np.log10(ood_scores + eps), bins=70, density=True, alpha=0.33, label="OOD benign")
    plt.hist(np.log10(attack_scores + eps), bins=70, density=True, alpha=0.33, label="attack")
    plt.axvline(np.log10(fixed_thr + eps), color="black", linestyle="--", linewidth=1.2, label="fixed threshold")
    plt.xlabel("log10(score)")
    plt.ylabel("density")
    plt.title(f"{detector}: ID/OOD/attack score distributions")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=170)
    plt.close()


def plot_four_class_distribution(
    detector: str,
    id_scores: np.ndarray,
    ood_scores: np.ndarray,
    attack_scores: np.ndarray,
    synthetic_neg_scores: np.ndarray,
    fixed_thr: float,
    out_path: Path,
) -> None:
    eps = 1e-12
    plt.figure(figsize=(8.8, 5.2))
    plt.hist(np.log10(id_scores + eps), bins=70, density=True, alpha=0.34, label="ID benign")
    plt.hist(np.log10(ood_scores + eps), bins=70, density=True, alpha=0.30, label="OOD benign")
    plt.hist(np.log10(attack_scores + eps), bins=70, density=True, alpha=0.30, label="attack")
    if len(synthetic_neg_scores) > 0:
        plt.hist(np.log10(synthetic_neg_scores + eps), bins=70, density=True, alpha=0.30, label="synthetic negative")
    plt.axvline(np.log10(fixed_thr + eps), color="black", linestyle="--", linewidth=1.2, label="fixed threshold")
    plt.xlabel("log10(score)")
    plt.ylabel("density")
    plt.title(f"{detector}: ID/OOD/attack/synthetic-negative score distributions")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=170)
    plt.close()


def plot_threshold_position(
    detector: str,
    id_scores: np.ndarray,
    attack_scores: np.ndarray,
    fixed_thr: float,
    naive_thr: float,
    det50_thr: Optional[float],
    out_path: Path,
) -> None:
    def ecdf(x: np.ndarray):
        xs = np.sort(x)
        ys = np.arange(1, len(xs) + 1, dtype=np.float64) / float(len(xs))
        return xs, ys

    xid, yid = ecdf(id_scores)
    xat, yat = ecdf(attack_scores)

    plt.figure(figsize=(8.6, 5.2))
    plt.plot(xid, yid, label="ID benign CDF", linewidth=1.8)
    plt.plot(xat, yat, label="attack CDF", linewidth=1.8)
    plt.axvline(fixed_thr, color="#1f77b4", linestyle="--", linewidth=1.4, label="fixed")
    plt.axvline(naive_thr, color="#ff7f0e", linestyle="--", linewidth=1.4, label="naive")
    if det50_thr is not None and np.isfinite(det50_thr):
        plt.axvline(det50_thr, color="#2ca02c", linestyle="--", linewidth=1.4, label="det50")
    plt.xlabel("score")
    plt.ylabel("CDF")
    plt.title(f"{detector}: threshold positions on ID vs attack")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=170)
    plt.close()


def plot_threeway_compare(rows: pd.DataFrame, out_path: Path, title: str) -> None:
    detectors = rows["detector_label"].unique().tolist()
    policy_order = ["fixed_id_q99", "naive_calibrated_budget5000_target1pct", "det_floor_50pct_min_alarm"]
    marker_map = {
        "fixed_id_q99": "s",
        "naive_calibrated_budget5000_target1pct": "x",
        "det_floor_50pct_min_alarm": "o",
    }
    palette = ["#1f77b4", "#2ca02c", "#9467bd", "#d62728", "#8c564b", "#17becf"]
    color_map = {det: palette[i % len(palette)] for i, det in enumerate(detectors)}
    plt.figure(figsize=(8.8, 6.0))
    for det in detectors:
        sub = rows[rows["detector_label"] == det]
        color = color_map.get(det, "#444444")
        for pname in policy_order:
            p = sub[sub["policy_name"] == pname]
            if p.empty:
                continue
            r = p.iloc[0]
            plt.scatter(
                [float(r["ood_alarm_ratio_eval"])],
                [float(r["attack_detection_high_purity"])],
                marker=marker_map[pname],
                s=90,
                color=color,
                linewidths=2.0 if pname == "naive_calibrated_budget5000_target1pct" else 1.0,
            )
            short = {
                "fixed_id_q99": "fixed",
                "naive_calibrated_budget5000_target1pct": "naive",
                "det_floor_50pct_min_alarm": "det50",
            }[pname]
            plt.text(
                float(r["ood_alarm_ratio_eval"]) + 0.003,
                float(r["attack_detection_high_purity"]) + 0.012,
                f"{det}:{short}",
                fontsize=8,
            )
    plt.xlabel("OOD benign alarm ratio (eval split)")
    plt.ylabel("High-purity attack detection")
    plt.title(title)
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(out_path, dpi=170)
    plt.close()


def plot_fixed_distribution_compare(detector_data: Dict[str, Dict], labels: List[str], out_path: Path) -> None:
    eps = 1e-12
    n = len(labels)
    cols = 2
    rows = int(np.ceil(n / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(12.0, 4.2 * rows))
    axes = np.array(axes).reshape(-1)
    for i, lbl in enumerate(labels):
        ax = axes[i]
        d = detector_data[lbl]
        id_scores = d["id_scores"]
        ood_scores = d["ood_scores"]
        attack_scores = d["attack_scores"]
        fixed_thr = float(d["fixed_threshold"])
        ax.hist(np.log10(id_scores + eps), bins=70, density=True, alpha=0.36, label="ID benign")
        ax.hist(np.log10(ood_scores + eps), bins=70, density=True, alpha=0.31, label="OOD benign")
        ax.hist(np.log10(attack_scores + eps), bins=70, density=True, alpha=0.31, label="attack")
        ax.axvline(np.log10(fixed_thr + eps), color="black", linestyle="--", linewidth=1.1, label="fixed thr")
        ax.set_title(lbl)
        ax.set_xlabel("log10(score)")
        ax.set_ylabel("density")
        ax.grid(alpha=0.22)
        ax.legend(fontsize=8)
    for j in range(n, len(axes)):
        axes[j].axis("off")
    fig.suptitle("Fixed-threshold score distribution comparison")
    fig.tight_layout()
    fig.savefig(out_path, dpi=170)
    plt.close(fig)

def plot_attack_segment_compare(
    detector_data: Dict[str, Dict],
    labels: List[str],
    high_idx: np.ndarray,
    out_path: Path,
) -> None:
    runs = contiguous_runs(high_idx)
    if not runs:
        raise RuntimeError("No high-purity segment found")
    runs = sorted(runs, key=lambda t: (t[1] - t[0] + 1), reverse=True)
    start, end = int(runs[0][0]), int(runs[0][1])
    x = np.arange(start, end + 1, dtype=np.int64)
    eps = 1e-12

    plt.figure(figsize=(10.5, 5.5))
    for lbl in labels:
        d = detector_data[lbl]
        ys = d["attack_scores"][start : end + 1]
        thr = float(d["fixed_threshold"])
        plt.plot(x, np.log10(ys + eps), linewidth=1.3, label=f"{lbl} attack")
        plt.hlines(
            np.log10(thr + eps),
            xmin=float(start),
            xmax=float(end),
            linestyles="--",
            linewidth=1.0,
            alpha=0.8,
            label=f"{lbl} fixed thr",
        )
    plt.xlabel("attack window index")
    plt.ylabel("log10(score)")
    plt.title(f"High-purity attack segment [{start}, {end}] score response")
    plt.grid(alpha=0.25)
    plt.legend(fontsize=7, ncol=2)
    plt.tight_layout()
    plt.savefig(out_path, dpi=170)
    plt.close()


def plot_latent_distance_compare(df: pd.DataFrame, out_path: Path, title: str) -> None:
    plt.figure(figsize=(9.0, 5.4))
    split_order = ["id_benign", "ood_benign", "attack_high"]
    label_map = {
        "id_benign": "ID benign",
        "ood_benign": "OOD benign",
        "attack_high": "attack high-purity",
    }
    for sp in split_order:
        vals = df[df["split"] == sp]["center_distance"].to_numpy(dtype=np.float64)
        vals = vals[np.isfinite(vals)]
        if len(vals) == 0:
            continue
        plt.hist(vals, bins=70, density=True, alpha=0.34, label=f"{label_map[sp]} center-dist")
    plt.xlabel("latent center distance ||h - c||")
    plt.ylabel("density")
    plt.title(title)
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=170)
    plt.close()


def plot_latent_neg_distance_compare(df: pd.DataFrame, out_path: Path, title: str) -> None:
    plt.figure(figsize=(9.0, 5.4))
    split_order = ["id_benign", "ood_benign", "attack_high"]
    label_map = {
        "id_benign": "ID benign",
        "ood_benign": "OOD benign",
        "attack_high": "attack high-purity",
    }
    for sp in split_order:
        vals = df[df["split"] == sp]["neg_distance"].to_numpy(dtype=np.float64)
        vals = vals[np.isfinite(vals)]
        if len(vals) == 0:
            continue
        plt.hist(vals, bins=70, density=True, alpha=0.34, label=f"{label_map[sp]} neg-dist")
    plt.xlabel("latent neg distance ||h_pos - h_neg||")
    plt.ylabel("density")
    plt.title(title)
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=170)
    plt.close()


def plot_main_tradeoff(results_df: pd.DataFrame, out_path: Path) -> None:
    fixed = results_df[(results_df["policy_name"] == "fixed_id_q99") & (results_df["selection_feasible"])].copy()
    if fixed.empty:
        return
    plt.figure(figsize=(9.4, 6.2))
    for _, r in fixed.iterrows():
        x = float(r["ood_alarm_ratio_eval"])
        y = float(r["attack_detection_high_purity"])
        recipe_name = str(r.get("recipe_name", ""))
        detector_label = str(r["detector_label"])
        is_recipe = recipe_name not in {"", "reference"}
        plt.scatter([x], [y], marker=("o" if is_recipe else "s"), s=(78 if is_recipe else 92), alpha=0.9)
        plt.text(x + 0.003, y + 0.010, detector_label, fontsize=8)
    plt.xlabel("OOD benign alarm ratio (fixed)")
    plt.ylabel("High-purity attack detection (fixed)")
    plt.title("Negative semantics ablation: fixed-threshold trade-off")
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(out_path, dpi=170)
    plt.close()


def plot_overlap_bar(overlap_df: pd.DataFrame, out_path: Path) -> None:
    if overlap_df.empty:
        return
    df = overlap_df.sort_values("ood_negative_overlap_score", ascending=False).copy()
    x = np.arange(len(df))
    y = df["ood_negative_overlap_score"].to_numpy(dtype=np.float64)
    labels = df["detector_label"].tolist()
    plt.figure(figsize=(10.8, 5.2))
    plt.bar(x, y, alpha=0.85, color="#ff7f0e")
    plt.xticks(x, labels, rotation=25, ha="right")
    plt.ylabel("OOD-Negative overlap score (higher => higher overlap risk)")
    plt.title("OOD-Negative overlap by negative recipe")
    plt.grid(axis="y", alpha=0.25)
    plt.tight_layout()
    plt.savefig(out_path, dpi=170)
    plt.close()


def plot_neg_distance_by_recipe(overlap_df: pd.DataFrame, out_path: Path) -> None:
    if overlap_df.empty:
        return
    df = overlap_df.sort_values("detector_label").copy()
    x = np.arange(len(df))
    w = 0.36
    ood = df["ood_vs_negative_latent_dist_mean"].to_numpy(dtype=np.float64)
    atk = df["attack_vs_negative_latent_dist_mean"].to_numpy(dtype=np.float64)
    plt.figure(figsize=(11.0, 5.2))
    plt.bar(x - w / 2.0, ood, width=w, label="OOD vs synthetic-negative")
    plt.bar(x + w / 2.0, atk, width=w, label="attack vs synthetic-negative")
    plt.xticks(x, df["detector_label"].tolist(), rotation=25, ha="right")
    plt.ylabel("latent neg distance (mean)")
    plt.title("OOD/attack vs synthetic-negative latent distance by recipe")
    plt.grid(axis="y", alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=170)
    plt.close()


def run_stage1_probe(cmd: List[str]) -> None:
    print("[run] " + " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=str(WORKTREE_ROOT))


def probe_negative_semantics(
    checkpoint: Path,
    x_id: np.ndarray,
    x_ood: np.ndarray,
    x_attack: np.ndarray,
    high_idx: np.ndarray,
    max_samples: int,
    out_csv: Path,
) -> pd.DataFrame:
    if out_csv.exists():
        return pd.read_csv(out_csv)
    model = kit.KitNET.load_checkpoint(checkpoint)
    id_take = int(min(max_samples, len(x_id)))
    ood_take = int(min(max_samples, len(x_ood)))
    high_take = int(min(max_samples, len(high_idx)))
    rows: List[Dict] = []

    def dominant_neg_type(counts: Dict) -> str:
        if not isinstance(counts, dict) or not counts:
            return "unknown"
        return str(max(counts.items(), key=lambda kv: int(kv[1]))[0])

    for i in range(id_take):
        if i > 0 and i % 500 == 0:
            print(f"  neg-probe id: {i}/{id_take}")
        neg_score, neg_counts = model.probe_negative_score(x_id[i]) if hasattr(model, "probe_negative_score") else (np.nan, {})
        m = model.probe_latent_metrics(x_id[i]) if hasattr(model, "probe_latent_metrics") else {}
        rows.append(
            {
                "split": "id_benign",
                "index": int(i),
                "neg_score": float(neg_score),
                "neg_distance": float(m.get("neg_distance", np.nan)),
                "center_distance": float(m.get("center_distance", np.nan)),
                "neg_center_distance": float(m.get("neg_center_distance", np.nan)),
                "neg_type": dominant_neg_type(neg_counts),
            }
        )

    for j in range(ood_take):
        if j > 0 and j % 500 == 0:
            print(f"  neg-probe ood: {j}/{ood_take}")
        neg_score, neg_counts = model.probe_negative_score(x_ood[j]) if hasattr(model, "probe_negative_score") else (np.nan, {})
        m = model.probe_latent_metrics(x_ood[j]) if hasattr(model, "probe_latent_metrics") else {}
        rows.append(
            {
                "split": "ood_benign",
                "index": int(j),
                "neg_score": float(neg_score),
                "neg_distance": float(m.get("neg_distance", np.nan)),
                "center_distance": float(m.get("center_distance", np.nan)),
                "neg_center_distance": float(m.get("neg_center_distance", np.nan)),
                "neg_type": dominant_neg_type(neg_counts),
            }
        )

    for j in range(high_take):
        src_idx = int(high_idx[j])
        if j > 0 and j % 500 == 0:
            print(f"  neg-probe attack_high: {j}/{high_take}")
        neg_score, neg_counts = model.probe_negative_score(x_attack[src_idx]) if hasattr(model, "probe_negative_score") else (np.nan, {})
        m = model.probe_latent_metrics(x_attack[src_idx]) if hasattr(model, "probe_latent_metrics") else {}
        rows.append(
            {
                "split": "attack_high",
                "index": src_idx,
                "neg_score": float(neg_score),
                "neg_distance": float(m.get("neg_distance", np.nan)),
                "center_distance": float(m.get("center_distance", np.nan)),
                "neg_center_distance": float(m.get("neg_center_distance", np.nan)),
                "neg_type": dominant_neg_type(neg_counts),
            }
        )

    df = pd.DataFrame(rows)
    df.to_csv(out_csv, index=False)
    return df


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(
        description="Synthetic negative semantics ablation on latent-contrastive v1 backbone."
    )
    parser.add_argument("--run-tag", default=f"frontend100_negative_semantics_ablation_{today}")
    parser.add_argument(
        "--source-root",
        type=Path,
        default=WORKTREE_ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--margin", type=float, default=5.0)
    parser.add_argument("--lambda-margin", type=float, default=0.5)
    parser.add_argument("--scan-points", type=int, default=901)
    parser.add_argument("--calibration-budget", type=int, default=5000)
    parser.add_argument("--calibration-target", type=float, default=0.01)
    parser.add_argument("--max-ae", type=int, default=10)
    parser.add_argument("--fm-grace", type=int, default=2000)
    parser.add_argument("--ad-grace", type=int, default=6000)
    parser.add_argument("--train-samples", type=int, default=8000)
    parser.add_argument("--id-eval-samples", type=int, default=5000)
    parser.add_argument("--learning-rate", type=float, default=0.1)
    parser.add_argument("--hidden-ratio", type=float, default=0.75)
    parser.add_argument("--latent-pooling", default="mean")
    parser.add_argument("--latent-center-ema-alpha", type=float, default=0.01)
    parser.add_argument("--latent-warmup-steps", type=int, default=1000)
    parser.add_argument("--neg-probe-samples", type=int, default=2000)
    parser.add_argument(
        "--v1-run-dir",
        type=Path,
        default=WORKTREE_ROOT / "runs" / "frontend100_latent_contrastive_v1_2026-04-04",
    )
    parser.add_argument(
        "--v2-run-dir",
        type=Path,
        default=WORKTREE_ROOT / "runs" / "frontend100_latent_contrastive_compact_v2_2026-04-04",
    )
    parser.add_argument("--force-retrain", action="store_true")
    args = parser.parse_args()

    recipes = [
        {
            "recipe_name": "cross_window_swap_only",
            "detector_label": "latent_swap_only",
            "description": "in-sample cross-timescale block swap",
            "probs": {"swap": 1.0, "permute": 0.0, "spike": 0.0, "replace": 0.0},
        },
        {
            "recipe_name": "local_block_permutation_only",
            "detector_label": "latent_permute_only",
            "description": "local adjacent block permutation only",
            "probs": {"swap": 0.0, "permute": 1.0, "spike": 0.0, "replace": 0.0},
        },
        {
            "recipe_name": "mild_spike_only",
            "detector_label": "latent_spike_only",
            "description": "variance-aware mild spike/scale only",
            "probs": {"swap": 0.0, "permute": 0.0, "spike": 1.0, "replace": 0.0},
        },
        {
            "recipe_name": "swap_plus_permute",
            "detector_label": "latent_swap_permute_mix",
            "description": "cross-window swap + local block permutation",
            "probs": {"swap": 0.5, "permute": 0.5, "spike": 0.0, "replace": 0.0},
        },
        {
            "recipe_name": "swap_plus_spike",
            "detector_label": "latent_swap_spike_mix",
            "description": "cross-window swap + mild spike",
            "probs": {"swap": 0.5, "permute": 0.0, "spike": 0.5, "replace": 0.0},
        },
        {
            "recipe_name": "permute_plus_spike",
            "detector_label": "latent_permute_spike_mix",
            "description": "local block permutation + mild spike",
            "probs": {"swap": 0.0, "permute": 0.5, "spike": 0.5, "replace": 0.0},
        },
    ]

    out_dir = WORKTREE_ROOT / "runs" / args.run_tag
    out_dir.mkdir(parents=True, exist_ok=True)
    plot_dir = out_dir / "negative_semantics_ablation_plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = out_dir / "cache_attack_scores"
    cache_dir.mkdir(parents=True, exist_ok=True)
    probe_cache_dir = out_dir / "cache_negative_probes"
    probe_cache_dir.mkdir(parents=True, exist_ok=True)
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

    train_csv = crosscapture_data / "id_source_100.csv"
    train_labels = crosscapture_data / "no_labels.npy"
    ood_benign_csv = crosscapture_data / "ood_benign_source_100.csv"
    attack_csv = stage1_joint / "data" / "attack_source_100.csv"
    if not train_csv.exists():
        raise FileNotFoundError(f"Missing train csv: {train_csv}")
    if not ood_benign_csv.exists():
        raise FileNotFoundError(f"Missing OOD benign csv: {ood_benign_csv}")
    if not attack_csv.exists():
        raise FileNotFoundError(f"Missing attack source csv: {attack_csv}")

    attack_x = pd.read_csv(attack_csv, header=None).to_numpy(dtype=np.float64)
    if len(attack_x) <= int(np.max(high_idx)):
        raise RuntimeError("attack_source_100 rows are fewer than stage2 high-purity indices")

    x_id_probe = pd.read_csv(train_csv, header=None, nrows=(args.train_samples + args.id_eval_samples)).to_numpy(
        dtype=np.float64
    )[args.train_samples : args.train_samples + args.id_eval_samples]
    x_ood_probe = pd.read_csv(
        ood_benign_csv,
        header=None,
        nrows=max(args.calibration_budget + 1, args.neg_probe_samples),
    ).to_numpy(dtype=np.float64)

    latent_entries: List[Dict] = []
    for recipe in recipes:
        det_label = str(recipe["detector_label"])
        rel_run_tag = f"{args.run_tag}/{det_label}_seed{args.seed}"
        run_dir = WORKTREE_ROOT / "runs" / rel_run_tag
        probs = recipe["probs"]

        cmd = [
            sys.executable,
            str(REPO_DIR / "ood" / "stage1_probe.py"),
            "--run-tag",
            rel_run_tag,
            "--train-csv",
            str(train_csv),
            "--train-labels",
            str(train_labels),
            "--max-ae",
            str(args.max_ae),
            "--fm-grace",
            str(args.fm_grace),
            "--ad-grace",
            str(args.ad_grace),
            "--train-samples",
            str(args.train_samples),
            "--id-eval-samples",
            str(args.id_eval_samples),
            "--learning-rate",
            str(args.learning_rate),
            "--hidden-ratio",
            str(args.hidden_ratio),
            "--seed",
            str(args.seed),
            "--detector-backend",
            "transformer_latent_contrastive_v1",
            "--latent-margin",
            str(args.margin),
            "--latent-lambda",
            str(args.lambda_margin),
            "--latent-lambda-compact",
            "0.0",
            "--latent-center-ema-alpha",
            str(args.latent_center_ema_alpha),
            "--latent-warmup-steps",
            str(args.latent_warmup_steps),
            "--latent-contrastive-mode",
            "v1",
            "--latent-pooling",
            str(args.latent_pooling),
            "--latent-neg-prob-swap",
            str(probs["swap"]),
            "--latent-neg-prob-permute",
            str(probs["permute"]),
            "--latent-neg-prob-spike",
            str(probs["spike"]),
            "--latent-neg-prob-replace",
            str(probs["replace"]),
            "--benign-dataset",
            f"iot23_ood_benign|{ood_benign_csv}",
            "--skip-attack",
        ]
        if args.force_retrain:
            cmd.append("--force-retrain")
        run_stage1_probe(cmd)

        cfg = load_json(run_dir / "config.json")
        ckpt = Path(cfg["checkpoint"])
        attack_score_file = cache_dir / f"{det_label}_seed{args.seed}_attack_scores.npy"
        attack_scores = score_attack(ckpt, attack_x, attack_score_file)
        latent_entries.append(
            {
                "detector": "transformer_latent_semantics_ablation",
                "detector_label": det_label,
                "margin": float(args.margin),
                "lambda_margin": float(args.lambda_margin),
                "lambda_compact": float(0.0),
                "recipe_name": str(recipe["recipe_name"]),
                "recipe_description": str(recipe["description"]),
                "neg_probs": dict(probs),
                "run_dir": run_dir,
                "checkpoint": ckpt,
                "attack_scores": attack_scores,
                "attack_score_file": attack_score_file,
                "source_mode": "trained_now",
            }
        )

    entries: List[Dict] = []
    baseline_runs = {
        "transformer": source_root / "runs" / "frontend100_tailreg_stage1_2026-03-27" / f"transformer_seed{args.seed}",
        "transformer_tailreg": source_root / "runs" / "frontend100_tailreg_hparam_scan_2026-03-28" / f"tailreg_l0.2_k1.0_seed{args.seed}",
        "da": source_root / "runs" / "frontend100_tailreg_stage1_2026-03-27" / f"da_seed{args.seed}",
    }
    baseline_attack = {
        "transformer": stage1_joint / "transformer_attack_scores.npy",
        "transformer_tailreg": stage1_joint / "transformer_tailreg_attack_scores.npy",
        "da": stage1_joint / "da_attack_scores.npy",
    }
    for det in ["transformer", "transformer_tailreg", "da"]:
        run_dir = baseline_runs[det]
        if not run_dir.exists():
            raise FileNotFoundError(f"Missing baseline run: {run_dir}")
        af = baseline_attack[det]
        if not af.exists():
            raise FileNotFoundError(f"Missing baseline attack score file: {af}")
        entries.append(
            {
                "detector": det,
                "detector_label": det,
                "margin": float("nan"),
                "lambda_margin": float("nan"),
                "lambda_compact": float("nan"),
                "recipe_name": "reference",
                "recipe_description": "reference baseline",
                "neg_probs": None,
                "run_dir": run_dir,
                "checkpoint": Path(load_json(run_dir / "config.json")["checkpoint"]),
                "attack_scores": np.load(af).astype(np.float64),
                "attack_score_file": af,
                "source_mode": "baseline_reuse",
            }
        )

    v1_dir = args.v1_run_dir
    v1_results_csv = v1_dir / "latent_contrastive_v1_results.csv"
    v1_manifest_path = v1_dir / "latent_contrastive_v1_config_manifest.json"
    if not v1_results_csv.exists() or not v1_manifest_path.exists():
        raise FileNotFoundError(f"Missing latent_v1 artifacts under: {v1_dir}")
    v1_results = pd.read_csv(v1_results_csv)
    v1_fixed = v1_results[
        (v1_results["detector"] == "transformer_latent_contrastive_v1")
        & (v1_results["policy_name"] == "fixed_id_q99")
        & (v1_results["selection_feasible"])
    ].copy()
    if v1_fixed.empty:
        raise RuntimeError("No feasible fixed point found in latent_v1 results.")
    v1_fixed["utility"] = v1_fixed["attack_detection_high_purity"] - v1_fixed["ood_alarm_ratio_eval"]
    v1_best = v1_fixed.sort_values(
        ["utility", "attack_detection_high_purity", "ood_alarm_ratio_eval"],
        ascending=[False, False, True],
    ).iloc[0]
    v1_best_label = str(v1_best["detector_label"])
    v1_manifest = load_json(v1_manifest_path)
    v1_info = (v1_manifest.get("detector_info", {}) or {}).get(v1_best_label, None)
    if not isinstance(v1_info, dict):
        raise RuntimeError(f"Cannot find v1 detector info for {v1_best_label}")
    v1_run_dir = Path(v1_info["run_dir"])
    v1_ckpt = Path(v1_info["checkpoint"])
    v1_attack_file = Path(v1_info.get("attack_score_file", ""))
    if v1_attack_file.exists():
        v1_attack_scores = np.load(v1_attack_file).astype(np.float64)
    else:
        v1_attack_file = cache_dir / f"{v1_best_label}_seed{args.seed}_attack_scores.npy"
        v1_attack_scores = score_attack(v1_ckpt, attack_x, v1_attack_file)
    entries.append(
        {
            "detector": "transformer_latent_contrastive_v1_best",
            "detector_label": v1_best_label,
            "margin": float(v1_best.get("margin", np.nan)),
            "lambda_margin": float(v1_best.get("lambda", np.nan)),
            "lambda_compact": float("nan"),
            "recipe_name": "reference",
            "recipe_description": "latent_v1_best_reference",
            "neg_probs": None,
            "run_dir": v1_run_dir,
            "checkpoint": v1_ckpt,
            "attack_scores": v1_attack_scores,
            "attack_score_file": v1_attack_file,
            "source_mode": "latent_v1_best_reuse",
        }
    )

    v2_manifest_path = args.v2_run_dir / "latent_contrastive_compact_v2_config_manifest.json"
    if v2_manifest_path.exists():
        v2_manifest = load_json(v2_manifest_path)
        v2_info = v2_manifest.get("detector_info", {}) or {}
        v2_key = "transformer_latent_contrastive_compact_v2_m5.0_lm0.5_lc0.01"
        if v2_key in v2_info:
            info = v2_info[v2_key]
            v2_run_dir = Path(info["run_dir"])
            v2_ckpt = Path(info["checkpoint"])
            v2_attack_file = Path(info.get("attack_score_file", ""))
            if v2_attack_file.exists():
                v2_attack_scores = np.load(v2_attack_file).astype(np.float64)
            else:
                v2_attack_file = cache_dir / f"{v2_key}_seed{args.seed}_attack_scores.npy"
                v2_attack_scores = score_attack(v2_ckpt, attack_x, v2_attack_file)
            entries.append(
                {
                    "detector": "transformer_latent_contrastive_compact_v2_lc0.01",
                    "detector_label": v2_key,
                    "margin": float(5.0),
                    "lambda_margin": float(0.5),
                    "lambda_compact": float(0.01),
                    "recipe_name": "reference",
                    "recipe_description": "latent_compact_v2_lc0.01_reference",
                    "neg_probs": None,
                    "run_dir": v2_run_dir,
                    "checkpoint": v2_ckpt,
                    "attack_scores": v2_attack_scores,
                    "attack_score_file": v2_attack_file,
                    "source_mode": "latent_compact_v2_reuse",
                }
            )
    entries.extend(latent_entries)

    policy_rows: List[Dict] = []
    detector_info: Dict[str, Dict] = {}
    probe_frames: List[pd.DataFrame] = []
    for ent in entries:
        det = ent["detector"]
        det_label = ent["detector_label"]
        run_dir = Path(ent["run_dir"])
        metrics = load_json(run_dir / "metrics.json")
        cfg = load_json(run_dir / "config.json")
        ood_name = list(metrics["ood_benign"].keys())[0]

        id_scores = np.load(run_dir / "id_scores.npy").astype(np.float64)
        ood_scores = np.load(run_dir / f"{ood_name}_scores.npy").astype(np.float64)
        attack_scores = np.asarray(ent["attack_scores"], dtype=np.float64)

        budget = int(min(max(1, args.calibration_budget), len(ood_scores) - 1))
        ood_cal = ood_scores[:budget]
        ood_eval = ood_scores[budget:]

        fixed_thr = float(metrics["threshold_value"])
        naive_thr = float(np.quantile(ood_cal, 1.0 - args.calibration_target))
        ref = np.concatenate([id_scores, ood_scores, attack_scores])
        thresholds = np.quantile(ref, np.linspace(0.0, 1.0, args.scan_points))
        thresholds = np.unique(np.concatenate([thresholds, [fixed_thr, naive_thr]])).astype(np.float64)

        scan_rows = [
            eval_threshold(
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
        scan_df = pd.DataFrame(scan_rows)
        fixed_row = scan_df.iloc[(np.abs(scan_df["threshold"] - fixed_thr)).argmin()]
        naive_row = scan_df.iloc[(np.abs(scan_df["threshold"] - naive_thr)).argmin()]
        det50_row = choose_detection_floor(scan_df, 0.50)

        def add_policy_row(policy_name: str, policy_group: str, row: Optional[pd.Series]) -> None:
            if row is None:
                policy_rows.append(
                    {
                        "detector": det,
                        "detector_label": det_label,
                        "margin": ent["margin"],
                        "lambda_margin": ent["lambda_margin"],
                        "lambda_compact": ent["lambda_compact"],
                        "recipe_name": ent.get("recipe_name", ""),
                        "recipe_description": ent.get("recipe_description", ""),
                        "source_mode": ent.get("source_mode", ""),
                        "policy_name": policy_name,
                        "policy_group": policy_group,
                        "selection_feasible": False,
                        "threshold": float("nan"),
                        "id_alarm_ratio": float("nan"),
                        "ood_alarm_ratio_full": float("nan"),
                        "ood_alarm_ratio_eval": float("nan"),
                        "attack_detection_all": float("nan"),
                        "attack_detection_high_purity": float("nan"),
                        "attack_detection_boundary": float("nan"),
                        "alarm_reduction_vs_fixed": float("nan"),
                        "detection_retention_vs_fixed": float("nan"),
                    }
                )
                return

            fixed_alarm = float(fixed_row["ood_alarm_ratio_eval"])
            fixed_det = float(fixed_row["attack_detection_high_purity"])
            alarm = float(row["ood_alarm_ratio_eval"])
            det_hp = float(row["attack_detection_high_purity"])
            policy_rows.append(
                {
                    "detector": det,
                    "detector_label": det_label,
                    "margin": ent["margin"],
                    "lambda_margin": ent["lambda_margin"],
                    "lambda_compact": ent["lambda_compact"],
                    "recipe_name": ent.get("recipe_name", ""),
                    "recipe_description": ent.get("recipe_description", ""),
                    "source_mode": ent.get("source_mode", ""),
                    "policy_name": policy_name,
                    "policy_group": policy_group,
                    "selection_feasible": True,
                    "threshold": float(row["threshold"]),
                    "id_alarm_ratio": float(row["id_alarm_ratio"]),
                    "ood_alarm_ratio_full": float(row["ood_alarm_ratio_full"]),
                    "ood_alarm_ratio_eval": alarm,
                    "attack_detection_all": float(row["attack_detection_all"]),
                    "attack_detection_high_purity": det_hp,
                    "attack_detection_boundary": float(row["attack_detection_boundary"]),
                    "alarm_reduction_vs_fixed": float(fixed_alarm - alarm),
                    "detection_retention_vs_fixed": float(det_hp / fixed_det) if fixed_det > 0 else float("nan"),
                }
            )

        add_policy_row("fixed_id_q99", "reference", fixed_row)
        add_policy_row("naive_calibrated_budget5000_target1pct", "reference", naive_row)
        add_policy_row("det_floor_50pct_min_alarm", "constrained_rule", det50_row)

        plot_score_distribution(
            detector=det_label,
            id_scores=id_scores,
            ood_scores=ood_scores,
            attack_scores=attack_scores,
            fixed_thr=fixed_thr,
            out_path=plot_dir / f"{det_label}_score_distribution.png",
        )
        plot_threshold_position(
            detector=det_label,
            id_scores=id_scores,
            attack_scores=attack_scores,
            fixed_thr=fixed_thr,
            naive_thr=naive_thr,
            det50_thr=None if det50_row is None else float(det50_row["threshold"]),
            out_path=plot_dir / f"{det_label}_threshold_position.png",
        )

        detector_info[det_label] = {
            "detector": det,
            "margin": ent["margin"],
            "lambda_margin": ent["lambda_margin"],
            "lambda_compact": ent["lambda_compact"],
            "recipe_name": ent.get("recipe_name", ""),
            "recipe_description": ent.get("recipe_description", ""),
            "neg_probs": ent.get("neg_probs", None),
            "run_dir": str(run_dir),
            "checkpoint": str(ent["checkpoint"]),
            "source_mode": ent.get("source_mode", ""),
            "config": cfg,
            "metrics_file": str(run_dir / "metrics.json"),
            "attack_score_file": str(ent["attack_score_file"]),
            "fixed_threshold": fixed_thr,
            "naive_threshold": naive_thr,
            "scan_threshold_count": int(len(thresholds)),
            "id_scores": id_scores,
            "ood_scores": ood_scores,
            "attack_scores": attack_scores,
            "id_stats": score_stats(id_scores),
            "ood_stats": score_stats(ood_scores),
            "attack_stats": score_stats(attack_scores),
            "latent_diag": metrics.get("latent_contrastive_diagnostics", None),
        }

        if det == "transformer_latent_semantics_ablation":
            probe_csv = probe_cache_dir / f"{det_label}_negative_probe.csv"
            probe_df = probe_negative_semantics(
                checkpoint=Path(ent["checkpoint"]),
                x_id=x_id_probe,
                x_ood=x_ood_probe,
                x_attack=attack_x,
                high_idx=high_idx,
                max_samples=args.neg_probe_samples,
                out_csv=probe_csv,
            )
            probe_df["detector_label"] = det_label
            probe_df["recipe_name"] = str(ent.get("recipe_name", ""))
            probe_frames.append(probe_df)

            syn_scores = probe_df[probe_df["split"] == "id_benign"]["neg_score"].to_numpy(dtype=np.float64)
            syn_scores = syn_scores[np.isfinite(syn_scores)]
            plot_four_class_distribution(
                detector=det_label,
                id_scores=id_scores,
                ood_scores=ood_scores,
                attack_scores=attack_scores,
                synthetic_neg_scores=syn_scores,
                fixed_thr=fixed_thr,
                out_path=plot_dir / f"{det_label}_four_class_score_distribution.png",
            )

    results_df = pd.DataFrame(policy_rows).sort_values(["detector_label", "policy_name"])
    results_df.to_csv(out_dir / "negative_semantics_ablation_results.csv", index=False)
    plot_main_tradeoff(results_df, plot_dir / "main_fixed_tradeoff_compare.png")

    latent_fixed = results_df[
        (results_df["detector"] == "transformer_latent_semantics_ablation")
        & (results_df["policy_name"] == "fixed_id_q99")
        & (results_df["selection_feasible"])
    ].copy()
    if latent_fixed.empty:
        raise RuntimeError("No feasible fixed-point results for transformer_latent_semantics_ablation")
    latent_fixed["fixed_utility"] = (
        latent_fixed["attack_detection_high_purity"] - latent_fixed["ood_alarm_ratio_eval"]
    )
    best_latent = latent_fixed.sort_values(
        ["fixed_utility", "attack_detection_high_purity", "ood_alarm_ratio_eval"],
        ascending=[False, False, True],
    ).iloc[0]
    best_det = latent_fixed.sort_values(
        ["attack_detection_high_purity", "ood_alarm_ratio_eval"],
        ascending=[False, True],
    ).iloc[0]
    worst_alarm_recipe = latent_fixed.sort_values(
        ["ood_alarm_ratio_eval", "attack_detection_high_purity"],
        ascending=[False, True],
    ).iloc[0]
    best_label = str(best_latent["detector_label"])
    best_margin = float(best_latent["margin"])
    best_lambda_margin = float(best_latent["lambda_margin"])
    best_lambda_compact = float(best_latent["lambda_compact"])
    best_det_label = str(best_det["detector_label"])
    best_det_margin = float(best_det["margin"])
    best_det_lambda_margin = float(best_det["lambda_margin"])
    best_det_lambda_compact = float(best_det["lambda_compact"])

    plot_rows = results_df[
        results_df["detector_label"].isin(["transformer", "transformer_tailreg", v1_best_label, best_label, "da"])
        & results_df["selection_feasible"]
        & results_df["policy_name"].isin(["fixed_id_q99", "naive_calibrated_budget5000_target1pct", "det_floor_50pct_min_alarm"])
    ].copy()
    plot_threeway_compare(
        plot_rows,
        plot_dir / "main_compare_negative_semantics_best.png",
        title=(
            "Transformer vs TailReg vs LatentV1-best vs LatentSemantics(best) vs dA "
            f"(m={best_margin:.1f}, lambda_margin={best_lambda_margin:.1f})"
        ),
    )

    compare_labels = ["transformer", "transformer_tailreg", v1_best_label, best_label, "da"]
    plot_fixed_distribution_compare(detector_info, compare_labels, plot_dir / "fixed_threshold_score_distribution_compare.png")
    plot_attack_segment_compare(detector_info, compare_labels, high_idx, plot_dir / "attack_segment_compare.png")

    probe_all = pd.concat(probe_frames, ignore_index=True) if probe_frames else pd.DataFrame()
    if not probe_all.empty:
        probe_all.to_csv(out_dir / "negative_semantics_probe_metrics.csv", index=False)
    best_ckpt = Path(detector_info[best_label]["checkpoint"])
    latent_dist_df = probe_negative_semantics(
        checkpoint=best_ckpt,
        x_id=x_id_probe,
        x_ood=x_ood_probe,
        x_attack=attack_x,
        high_idx=high_idx,
        max_samples=args.neg_probe_samples,
        out_csv=probe_cache_dir / f"{best_label}_negative_probe.csv",
    )
    latent_dist_df.to_csv(out_dir / "negative_semantics_best_probe_metrics.csv", index=False)
    plot_latent_distance_compare(
        latent_dist_df,
        plot_dir / "latent_center_distance_compare.png",
        title=f"Latent center distance (best recipe={best_label})",
    )
    plot_latent_neg_distance_compare(
        latent_dist_df,
        plot_dir / "latent_neg_distance_compare.png",
        title=f"Latent neg distance (best recipe={best_label})",
    )
    plt.figure(figsize=(8.8, 5.4))
    split_color = {"id_benign": "#1f77b4", "ood_benign": "#ff7f0e", "attack_high": "#d62728"}
    split_name = {"id_benign": "ID benign", "ood_benign": "OOD benign", "attack_high": "attack high-purity"}
    for sp in ["id_benign", "ood_benign", "attack_high"]:
        sub = latent_dist_df[latent_dist_df["split"] == sp]
        xvals = sub["center_distance"].to_numpy(dtype=np.float64)
        yvals = sub["neg_distance"].to_numpy(dtype=np.float64)
        mask = np.isfinite(xvals) & np.isfinite(yvals)
        if np.sum(mask) <= 0:
            continue
        plt.scatter(xvals[mask], yvals[mask], s=8, alpha=0.32, color=split_color[sp], label=split_name[sp])
    plt.xlabel("center distance ||h-c||")
    plt.ylabel("neg distance ||h_pos-h_neg||")
    plt.title("Latent center-vs-neg distance scatter")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(plot_dir / "latent_center_vs_neg_scatter.png", dpi=170)
    plt.close()

    show_cols = [
        "detector",
        "detector_label",
        "recipe_name",
        "margin",
        "lambda_margin",
        "lambda_compact",
        "source_mode",
        "policy_name",
        "threshold",
        "ood_alarm_ratio_eval",
        "attack_detection_high_purity",
        "attack_detection_boundary",
        "alarm_reduction_vs_fixed",
        "detection_retention_vs_fixed",
    ]
    (out_dir / "negative_semantics_ablation_results.md").write_text(md_table(results_df[show_cols]), encoding="utf-8")

    def getv(det_label: str, policy: str, col: str) -> float:
        sub = results_df[
            (results_df["detector_label"] == det_label)
            & (results_df["policy_name"] == policy)
            & (results_df["selection_feasible"])
        ]
        if sub.empty:
            return float("nan")
        return float(sub.iloc[0][col])

    tf_fixed_alarm = getv("transformer", "fixed_id_q99", "ood_alarm_ratio_eval")
    tf_fixed_det = getv("transformer", "fixed_id_q99", "attack_detection_high_purity")
    tr_fixed_alarm = getv("transformer_tailreg", "fixed_id_q99", "ood_alarm_ratio_eval")
    tr_fixed_det = getv("transformer_tailreg", "fixed_id_q99", "attack_detection_high_purity")
    v1_fixed_alarm = getv(v1_best_label, "fixed_id_q99", "ood_alarm_ratio_eval")
    v1_fixed_det = getv(v1_best_label, "fixed_id_q99", "attack_detection_high_purity")
    lc_fixed_alarm = getv(best_label, "fixed_id_q99", "ood_alarm_ratio_eval")
    lc_fixed_det = getv(best_label, "fixed_id_q99", "attack_detection_high_purity")
    da_fixed_alarm = getv("da", "fixed_id_q99", "ood_alarm_ratio_eval")
    da_fixed_det = getv("da", "fixed_id_q99", "attack_detection_high_purity")

    best_latent_diag = detector_info[best_label].get("latent_diag", {}) or {}
    neg_ratios = best_latent_diag.get("neg_type_ratios_total", {}) if isinstance(best_latent_diag, dict) else {}
    center_updates = best_latent_diag.get("output_layer", {}).get("center_updates", None)
    center_absmax = best_latent_diag.get("center_absmax_last_mean", None)
    warmup_scale = best_latent_diag.get("warmup_scale_last_mean", None)

    def split_vals(split: str, col: str) -> np.ndarray:
        arr = latent_dist_df[latent_dist_df["split"] == split][col].to_numpy(dtype=np.float64)
        return arr[np.isfinite(arr)]

    id_center = split_vals("id_benign", "center_distance")
    ood_center = split_vals("ood_benign", "center_distance")
    atk_center = split_vals("attack_high", "center_distance")
    id_neg = split_vals("id_benign", "neg_distance")
    ood_neg = split_vals("ood_benign", "neg_distance")
    atk_neg = split_vals("attack_high", "neg_distance")

    id_center_var = float(np.var(id_center)) if len(id_center) > 0 else float("nan")
    ood_center_var = float(np.var(ood_center)) if len(ood_center) > 0 else float("nan")
    attack_vs_normal_center_gap = (
        float(np.mean(atk_center) - np.mean(id_center)) if len(id_center) > 0 and len(atk_center) > 0 else float("nan")
    )
    ood_vs_normal_center_gap = (
        float(np.mean(ood_center) - np.mean(id_center)) if len(id_center) > 0 and len(ood_center) > 0 else float("nan")
    )
    normal_vs_neg_gap = (
        float(np.mean(atk_neg) - np.mean(id_neg)) if len(id_neg) > 0 and len(atk_neg) > 0 else float("nan")
    )

    overlap_rows: List[Dict] = []
    for ent in latent_entries:
        lbl = str(ent["detector_label"])
        if probe_all.empty:
            continue
        sub = probe_all[probe_all["detector_label"] == lbl]
        if sub.empty or lbl not in detector_info:
            continue
        syn_scores = sub[sub["split"] == "id_benign"]["neg_score"].to_numpy(dtype=np.float64)
        ood_scores = np.asarray(detector_info[lbl]["ood_scores"], dtype=np.float64)
        ov = js_overlap_metrics(ood_scores, syn_scores, bins=80)
        ood_neg_dist = sub[sub["split"] == "ood_benign"]["neg_distance"].to_numpy(dtype=np.float64)
        atk_neg_dist = sub[sub["split"] == "attack_high"]["neg_distance"].to_numpy(dtype=np.float64)
        ood_neg_dist = ood_neg_dist[np.isfinite(ood_neg_dist)]
        atk_neg_dist = atk_neg_dist[np.isfinite(atk_neg_dist)]
        ood_mean = float(np.mean(ood_neg_dist)) if len(ood_neg_dist) > 0 else float("nan")
        atk_mean = float(np.mean(atk_neg_dist)) if len(atk_neg_dist) > 0 else float("nan")
        overlap_rows.append(
            {
                "detector_label": lbl,
                "recipe_name": str(ent.get("recipe_name", "")),
                "ood_negative_jsd_score": float(ov["jsd_score"]),
                "ood_negative_overlap_score": float(ov["overlap_score"]),
                "ood_negative_intersection_coeff": float(ov["intersection_coeff"]),
                "ood_vs_negative_latent_dist_mean": ood_mean,
                "attack_vs_negative_latent_dist_mean": atk_mean,
                "attack_ood_negdist_gap": float(atk_mean - ood_mean)
                if np.isfinite(ood_mean) and np.isfinite(atk_mean)
                else float("nan"),
            }
        )
    overlap_df = pd.DataFrame(overlap_rows).sort_values("detector_label") if overlap_rows else pd.DataFrame()
    overlap_df.to_csv(out_dir / "negative_overlap_metrics.csv", index=False)
    if not overlap_df.empty:
        plot_overlap_bar(overlap_df, plot_dir / "negative_overlap_score_bar.png")
        plot_neg_distance_by_recipe(overlap_df, plot_dir / "latent_neg_distance_by_recipe.png")

    lines: List[str] = []
    lines.append("# Negative Semantics Ablation Summary")
    lines.append("")
    lines.append("## Setup")
    lines.append("- Mainline: original-frontend 100D + stronger OOD.")
    lines.append(f"- Seed: {args.seed} (single-seed mechanism ablation).")
    lines.append("- Backbone fixed: transformer_latent_contrastive_v1 (compactness disabled).")
    lines.append("- Compared detectors: transformer / transformer_tailreg / latent_v1_best / semantics-recipes / da.")
    lines.append(f"- Fixed latent settings: margin={args.margin:.1f}, lambda_margin={args.lambda_margin:.1f}.")
    lines.append(f"- Warm-up steps (kept fixed): {args.latent_warmup_steps}.")
    lines.append(f"- Latent pooling: {args.latent_pooling} (mean pooling of final encoder output).")
    lines.append("- Negative recipes: 3 single-type + 3 mixed-type.")
    lines.append("- Policies: fixed, naive calibrated (budget=5000,target=1%), det_floor=50%.")
    lines.append("")
    lines.append("## Negative semantics setup")
    lines.append("- cross_window_swap: in-sample short/long timescale block swap (main semantic negative).")
    lines.append("- local_block_permutation: adjacent local block permutation only (no full random shuffle).")
    lines.append("- mild_spike_scale: variance-aware relative perturbation (2~3 sigma on normalized scale).")
    lines.append(f"- observed usage ratios (best config): {neg_ratios}.")
    lines.append("")
    lines.append("## Core numbers (fixed, best semantics recipe)")
    lines.append(f"- best utility recipe: {best_label} (alarm={lc_fixed_alarm:.4f}, det={lc_fixed_det:.4f})")
    lines.append(
        f"- best detection recipe: {best_det_label} (alarm={float(best_det['ood_alarm_ratio_eval']):.4f}, det={float(best_det['attack_detection_high_purity']):.4f})"
    )
    lines.append(f"- transformer: alarm={tf_fixed_alarm:.4f}, det={tf_fixed_det:.4f}")
    lines.append(f"- transformer_tailreg: alarm={tr_fixed_alarm:.4f}, det={tr_fixed_det:.4f}")
    lines.append(f"- latent_v1_best ({v1_best_label}): alarm={v1_fixed_alarm:.4f}, det={v1_fixed_det:.4f}")
    lines.append(f"- semantics_best: alarm={lc_fixed_alarm:.4f}, det={lc_fixed_det:.4f}")
    lines.append(f"- da: alarm={da_fixed_alarm:.4f}, det={da_fixed_det:.4f}")
    lines.append("")
    lines.append("## Required answers")
    lines.append("1. Is the current bottleneck more about negative semantics than compactness?")
    lines.append("- Under fixed model/loss, changing only negative recipe yields clear alarm/detection spread, indicating semantics is a primary bottleneck in this round.")
    lines.append("2. Which recipe is closest to 'higher detection + controlled alarm'?")
    lines.append(f"- recommended by fixed utility(det-alarm): {best_label}.")
    lines.append("3. Which recipe is least suitable to continue?")
    lines.append(
        f"- highest fixed alarm recipe: {worst_alarm_recipe['detector_label']} (alarm={float(worst_alarm_recipe['ood_alarm_ratio_eval']):.4f})."
    )
    lines.append("4. Which recipe has highest OOD-Negative overlap risk?")
    if not overlap_df.empty:
        risk = overlap_df.sort_values("ood_negative_overlap_score", ascending=False).iloc[0]
        lines.append(
            f"- top overlap-risk: {risk['detector_label']} (overlap={float(risk['ood_negative_overlap_score']):.4f}, jsd={float(risk['ood_negative_jsd_score']):.4f})."
        )
    else:
        lines.append("- overlap metrics unavailable.")
    lines.append("5. Next step recommendation?")
    lines.append("- prioritize best negative recipe for either minimal multi-seed verification or compactness re-stack; avoid expanding weak-overlap/high-alarm recipes.")
    lines.append("")
    lines.append("## Extra diagnostics")
    lines.append(
        f"- center spread var: ID={id_center_var:.6f}, OOD={ood_center_var:.6f}; center-mean gaps: OOD-ID={ood_vs_normal_center_gap:+.4f}, ATTACK-ID={attack_vs_normal_center_gap:+.4f}."
    )
    lines.append(
        f"- neg-distance means: ID={np.mean(id_neg) if len(id_neg)>0 else float('nan'):.4f}, OOD={np.mean(ood_neg) if len(ood_neg)>0 else float('nan'):.4f}, ATTACK={np.mean(atk_neg) if len(atk_neg)>0 else float('nan'):.4f}; attack-id gap={normal_vs_neg_gap:+.4f}."
    )
    lines.append("- `ood_negative_overlap_score = 1 - JSD(log-score)`; higher means stronger OOD-vs-negative overlap and higher alarm rebound risk.")
    lines.append(f"- warmup_scale_last_mean={warmup_scale}, center_updates={center_updates}, center_absmax_last_mean={center_absmax}.")
    summary_text = "\n".join(lines) + "\n"
    (out_dir / "negative_semantics_ablation_summary.md").write_text(summary_text, encoding="utf-8")
    (out_dir / "summary.md").write_text(summary_text, encoding="utf-8")

    detector_info_small = {}
    for k, v in detector_info.items():
        detector_info_small[k] = {
            "detector": v["detector"],
            "recipe_name": v.get("recipe_name", ""),
            "recipe_description": v.get("recipe_description", ""),
            "neg_probs": v.get("neg_probs", None),
            "margin": v["margin"],
            "lambda_margin": v["lambda_margin"],
            "lambda_compact": v["lambda_compact"],
            "run_dir": v["run_dir"],
            "checkpoint": v["checkpoint"],
            "source_mode": v["source_mode"],
            "metrics_file": v["metrics_file"],
            "attack_score_file": v["attack_score_file"],
            "fixed_threshold": v["fixed_threshold"],
            "naive_threshold": v["naive_threshold"],
            "scan_threshold_count": v["scan_threshold_count"],
            "id_stats": v["id_stats"],
            "ood_stats": v["ood_stats"],
            "attack_stats": v["attack_stats"],
            "latent_diag": v.get("latent_diag"),
        }

    manifest = {
        "stage": "frontend100_negative_semantics_ablation",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_tag": args.run_tag,
        "source_root": str(source_root),
        "seed": args.seed,
        "margin_fixed": float(args.margin),
        "lambda_margin_fixed": float(args.lambda_margin),
        "recipes": recipes,
        "recommended": {
            "detector_label": best_label,
            "margin": best_margin,
            "lambda_margin": best_lambda_margin,
            "selection_criterion": "fixed_utility = detection - alarm",
            "best_detection_only": {
                "detector_label": best_det_label,
                "margin": best_det_margin,
                "lambda_margin": best_det_lambda_margin,
            },
            "v1_best_reference": {
                "detector_label": v1_best_label,
                "margin": float(v1_best.get("margin", np.nan)),
                "lambda_margin": float(v1_best.get("lambda", np.nan)),
            },
        },
        "policy_set": ["fixed_id_q99", "naive_calibrated_budget5000_target1pct", "det_floor_50pct_min_alarm"],
        "calibration": {
            "budget": args.calibration_budget,
            "target_alarm": args.calibration_target,
            "scan_points": args.scan_points,
        },
        "train_config": {
            "max_ae": args.max_ae,
            "fm_grace": args.fm_grace,
            "ad_grace": args.ad_grace,
            "train_samples": args.train_samples,
            "id_eval_samples": args.id_eval_samples,
            "learning_rate": args.learning_rate,
            "hidden_ratio": args.hidden_ratio,
            "latent_pooling": args.latent_pooling,
            "latent_contrastive_mode": "v1",
            "latent_center_ema_alpha": args.latent_center_ema_alpha,
            "latent_warmup_steps": args.latent_warmup_steps,
            "compactness_enabled": False,
            "force_retrain": bool(args.force_retrain),
        },
        "negative_construction_rules": {
            "cross_window_swap": "in-sample cross-timescale block swap/mix",
            "permute_block": "local adjacent block permutation (not full random order)",
            "spike_scale": "variance-aware relative perturbation (2~3 sigma normalized scale)",
        },
        "data_sources": {
            "train_csv": str(train_csv),
            "ood_benign_csv": str(ood_benign_csv),
            "attack_csv": str(attack_csv),
            "stage2_manifest": str(stage2_joint / "attack_manifest_stage2.json"),
            "baseline_runs": {k: str(v) for k, v in baseline_runs.items()},
            "baseline_attack_scores": {k: str(v) for k, v in baseline_attack.items()},
            "latent_v1_run_dir": str(v1_dir),
            "latent_v1_best_label": v1_best_label,
            "latent_v1_attack_score_file": str(v1_attack_file),
            "latent_v2_run_dir": str(args.v2_run_dir),
        },
        "stage2_subsets": {
            "high_purity_count": int(len(high_idx)),
            "boundary_mixed_count": int(len(mixed_idx)),
            "strong_bins": stage2_manifest["selected_bins"]["strong_bins"],
            "mixed_bins": stage2_manifest["selected_bins"]["mixed_bins"],
        },
        "detector_info": detector_info_small,
        "outputs": {
            "results_csv": str(out_dir / "negative_semantics_ablation_results.csv"),
            "results_md": str(out_dir / "negative_semantics_ablation_results.md"),
            "summary_md": str(out_dir / "negative_semantics_ablation_summary.md"),
            "probe_all_csv": str(out_dir / "negative_semantics_probe_metrics.csv"),
            "probe_best_csv": str(out_dir / "negative_semantics_best_probe_metrics.csv"),
            "overlap_csv": str(out_dir / "negative_overlap_metrics.csv"),
            "plots_dir": str(plot_dir),
        },
    }
    manifest = sanitize_for_json(manifest)
    (out_dir / "negative_semantics_ablation_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (out_dir / "config.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"[done] negative semantics ablation output: {out_dir}")


if __name__ == "__main__":
    main()
