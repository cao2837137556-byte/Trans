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
    policy_order = [
        "fixed_id_q99",
        "naive_calibrated_budget5000_target1pct",
        "det_floor_50pct_min_alarm",
    ]
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


def plot_fixed_distribution_compare(
    detector_data: Dict[str, Dict],
    labels: List[str],
    out_path: Path,
) -> None:
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


def run_stage1_probe(cmd: List[str]) -> None:
    print("[run] " + " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=str(WORKTREE_ROOT))


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(description="Minimal MAE+TailReg-v1 experiment on frontend100 stronger OOD.")
    parser.add_argument("--run-tag", default=f"frontend100_mae_tailreg_v1_{today}")
    parser.add_argument(
        "--source-root",
        type=Path,
        default=WORKTREE_ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--mask-ratios", default="0.3,0.4")
    parser.add_argument("--reuse-mae-run-tag", default="frontend100_mae_v1_2026-04-03")
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
    parser.add_argument("--tailreg-lambda", type=float, default=0.2)
    parser.add_argument("--tailreg-k", type=float, default=1.0)
    parser.add_argument("--tailreg-warmup", type=int, default=256)
    parser.add_argument("--tailreg-ema-alpha", type=float, default=0.01)
    parser.add_argument("--force-retrain", action="store_true")
    args = parser.parse_args()

    mask_ratios = [float(x.strip()) for x in args.mask_ratios.split(",") if x.strip()]
    if not mask_ratios:
        raise ValueError("mask-ratios is empty")

    out_dir = WORKTREE_ROOT / "runs" / args.run_tag
    out_dir.mkdir(parents=True, exist_ok=True)
    plot_dir = out_dir / "mae_tailreg_v1_plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = out_dir / "cache_attack_scores"
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

    train_csv = crosscapture_data / "id_source_100.csv"
    train_labels = crosscapture_data / "no_labels.npy"  # optional path, can be absent.
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

    # Train MAE+TailReg variants (main task).
    mae_tailreg_entries: List[Dict] = []
    for mask_ratio in mask_ratios:
        det_label = f"transformer_mae_tailreg_v1_m{mask_ratio:.1f}"
        rel_run_tag = f"{args.run_tag}/{det_label}_seed{args.seed}"
        run_dir = WORKTREE_ROOT / "runs" / rel_run_tag

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
            "transformer_mae_tailreg_v1",
            "--mae-mask-ratio",
            str(mask_ratio),
            "--tailreg-lambda",
            str(args.tailreg_lambda),
            "--tailreg-k",
            str(args.tailreg_k),
            "--tailreg-warmup",
            str(args.tailreg_warmup),
            "--tailreg-ema-alpha",
            str(args.tailreg_ema_alpha),
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

        mae_tailreg_entries.append(
            {
                "detector": "transformer_mae_tailreg_v1",
                "detector_label": det_label,
                "mask_ratio": float(mask_ratio),
                "run_dir": run_dir,
                "checkpoint": ckpt,
                "attack_scores": attack_scores,
                "attack_score_file": attack_score_file,
                "source_mode": "trained_now",
            }
        )

    # Build unified detector entries.
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
                "mask_ratio": float("nan"),
                "run_dir": run_dir,
                "checkpoint": Path(load_json(run_dir / "config.json")["checkpoint"]),
                "attack_scores": np.load(af).astype(np.float64),
                "attack_score_file": af,
                "source_mode": "baseline_reuse",
            }
        )

    # Reuse MAE-v1 runs from previous round.
    mae_v1_root = WORKTREE_ROOT / "runs" / args.reuse_mae_run_tag
    if not mae_v1_root.exists():
        raise FileNotFoundError(f"Missing MAE-v1 run root: {mae_v1_root}")
    for mask_ratio in mask_ratios:
        lbl = f"transformer_mae_v1_m{mask_ratio:.1f}"
        run_dir = mae_v1_root / f"{lbl}_seed{args.seed}"
        if not run_dir.exists():
            raise FileNotFoundError(f"Missing MAE-v1 run dir: {run_dir}")
        cfg = load_json(run_dir / "config.json")
        ckpt = Path(cfg["checkpoint"])
        old_cache = mae_v1_root / "cache_attack_scores" / f"{lbl}_seed{args.seed}_attack_scores.npy"
        local_cache = cache_dir / f"{lbl}_seed{args.seed}_attack_scores.npy"
        if old_cache.exists():
            attack_scores = np.load(old_cache).astype(np.float64)
            attack_file = old_cache
        else:
            attack_scores = score_attack(ckpt, attack_x, local_cache)
            attack_file = local_cache
        entries.append(
            {
                "detector": "transformer_mae_v1",
                "detector_label": lbl,
                "mask_ratio": float(mask_ratio),
                "run_dir": run_dir,
                "checkpoint": ckpt,
                "attack_scores": attack_scores,
                "attack_score_file": attack_file,
                "source_mode": "mae_v1_reuse",
            }
        )

    entries.extend(mae_tailreg_entries)

    policy_rows: List[Dict] = []
    detector_info: Dict[str, Dict] = {}
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
                        "mask_ratio": ent["mask_ratio"],
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
                    "mask_ratio": ent["mask_ratio"],
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
            "mask_ratio": ent["mask_ratio"],
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
        }

    results_df = pd.DataFrame(policy_rows).sort_values(["detector_label", "policy_name"])
    results_df.to_csv(out_dir / "mae_tailreg_v1_results.csv", index=False)

    # Recommend MAE+TailReg mask by fixed-point detection (tie-break lower alarm).
    mt_fixed = results_df[
        (results_df["detector"] == "transformer_mae_tailreg_v1")
        & (results_df["policy_name"] == "fixed_id_q99")
        & (results_df["selection_feasible"])
    ].copy()
    if mt_fixed.empty:
        raise RuntimeError("No feasible fixed-point results for transformer_mae_tailreg_v1")
    best_mt_row = mt_fixed.sort_values(
        ["attack_detection_high_purity", "ood_alarm_ratio_eval"],
        ascending=[False, True],
    ).iloc[0]
    best_mask_ratio = float(best_mt_row["mask_ratio"])
    best_mt_label = str(best_mt_row["detector_label"])
    best_mae_label = f"transformer_mae_v1_m{best_mask_ratio:.1f}"

    # Main compare plots for each mask setting.
    for mask_ratio in mask_ratios:
        m = float(mask_ratio)
        labels = [
            "transformer",
            f"transformer_mae_v1_m{m:.1f}",
            f"transformer_mae_tailreg_v1_m{m:.1f}",
            "da",
        ]
        labels = [x for x in labels if x in results_df["detector_label"].unique()]
        plot_rows = results_df[
            results_df["detector_label"].isin(labels)
            & results_df["selection_feasible"]
            & results_df["policy_name"].isin(
                ["fixed_id_q99", "naive_calibrated_budget5000_target1pct", "det_floor_50pct_min_alarm"]
            )
        ].copy()
        plot_threeway_compare(
            plot_rows,
            plot_dir / f"main_compare_m{m:.1f}.png",
            title=f"Transformer vs MAE vs MAE+TailReg vs dA (mask={m:.1f})",
        )

    # Required fixed-threshold distribution and attack-segment plots.
    compare_labels = ["transformer", best_mae_label, best_mt_label, "da"]
    plot_fixed_distribution_compare(detector_info, compare_labels, plot_dir / "fixed_threshold_score_distribution_compare.png")
    plot_attack_segment_compare(detector_info, compare_labels, high_idx, plot_dir / "attack_segment_compare.png")

    # Markdown table.
    show_cols = [
        "detector",
        "detector_label",
        "mask_ratio",
        "source_mode",
        "policy_name",
        "threshold",
        "ood_alarm_ratio_eval",
        "attack_detection_high_purity",
        "attack_detection_boundary",
        "alarm_reduction_vs_fixed",
        "detection_retention_vs_fixed",
    ]
    (out_dir / "mae_tailreg_v1_results.md").write_text(
        md_table(results_df[show_cols]),
        encoding="utf-8",
    )

    # Summary values.
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
    da_fixed_alarm = getv("da", "fixed_id_q99", "ood_alarm_ratio_eval")
    da_fixed_det = getv("da", "fixed_id_q99", "attack_detection_high_purity")
    mae_fixed_alarm = getv(best_mae_label, "fixed_id_q99", "ood_alarm_ratio_eval")
    mae_fixed_det = getv(best_mae_label, "fixed_id_q99", "attack_detection_high_purity")
    mt_fixed_alarm = getv(best_mt_label, "fixed_id_q99", "ood_alarm_ratio_eval")
    mt_fixed_det = getv(best_mt_label, "fixed_id_q99", "attack_detection_high_purity")

    lines: List[str] = []
    lines.append("# MAE+TailReg-v1 Summary")
    lines.append("")
    lines.append("## Setup")
    lines.append("- Mainline: original-frontend 100D + stronger OOD.")
    lines.append(f"- Seed: {args.seed} (single-seed minimal check).")
    lines.append(f"- mask ratios: {mask_ratios}.")
    lines.append(
        f"- TailReg params: lambda={args.tailreg_lambda}, k={args.tailreg_k}, warmup={args.tailreg_warmup}, ema_alpha={args.tailreg_ema_alpha}."
    )
    lines.append("- Compared: transformer / transformer_tailreg / transformer_mae_v1 / transformer_mae_tailreg_v1 / da.")
    lines.append("- Policies: fixed, naive calibrated (budget=5000,target=1%), det_floor=50%.")
    lines.append("")
    lines.append("## Core Numbers (recommended mask)")
    lines.append(f"- Recommended MAE+TailReg mask: {best_mask_ratio:.1f}")
    lines.append(f"- fixed transformer: alarm={tf_fixed_alarm:.4f}, det={tf_fixed_det:.4f}")
    lines.append(f"- fixed {best_mae_label}: alarm={mae_fixed_alarm:.4f}, det={mae_fixed_det:.4f}")
    lines.append(f"- fixed {best_mt_label}: alarm={mt_fixed_alarm:.4f}, det={mt_fixed_det:.4f}")
    lines.append(f"- fixed da: alarm={da_fixed_alarm:.4f}, det={da_fixed_det:.4f}")
    lines.append("")
    lines.append("## Required Answers")
    lines.append("1. MAE+TailReg 相比 MAE-v1，fixed 下 detection 是否回升?")
    lines.append(f"- delta_det = {mt_fixed_det - mae_fixed_det:+.4f}.")
    lines.append("2. MAE+TailReg 是否保住 MAE-v1 的低 alarm 优势?")
    lines.append(f"- delta_alarm = {mt_fixed_alarm - mae_fixed_alarm:+.4f}.")
    lines.append("3. 相比原始 transformer，是否同时改善 alarm 与 detection?")
    lines.append(
        f"- vs transformer: delta_alarm={mt_fixed_alarm - tf_fixed_alarm:+.4f}, delta_det={mt_fixed_det - tf_fixed_det:+.4f}."
    )
    lines.append("4. 相比 dA，差距缩小还是仍明显落后?")
    lines.append(
        f"- vs dA: delta_alarm={mt_fixed_alarm - da_fixed_alarm:+.4f}, delta_det={mt_fixed_det - da_fixed_det:+.4f}."
    )
    lines.append("5. mask=0.3 还是 0.4 更值得进入多 seed?")
    lines.append(f"- Recommended now: mask={best_mask_ratio:.1f}.")
    lines.append("")
    lines.append("## Summary Questions")
    lines.append("1. MAE+TailReg 是否更接近可用修复版 Transformer?")
    lines.append("- 以 fixed 与 det50 联合观察，若 det回升且 alarm不明显反弹，则更接近可用。")
    lines.append("2. 修回的是 detection 还是局部好转?")
    lines.append("- 重点看 fixed-detection 与 det50 operating point 是否同时改善。")
    lines.append("3. 是否足以成为下一轮多 seed 第一候选?")
    lines.append("- 若上述两点成立，可进入多 seed；否则先继续微调。")
    lines.append("4. 若不足，短板主要在哪?")
    lines.append("- 通过 delta_det 与 delta_alarm 直接定位 detection仍低 / alarm反弹。")
    lines.append("5. 下一步建议")
    lines.append("- 建议先以推荐 mask 做最小多 seed；若边界明显则先微调 MAE+TailReg 再扩 seed。")
    summary_text = "\n".join(lines) + "\n"
    (out_dir / "mae_tailreg_v1_summary.md").write_text(summary_text, encoding="utf-8")
    (out_dir / "summary.md").write_text(summary_text, encoding="utf-8")

    detector_info_small = {}
    for k, v in detector_info.items():
        detector_info_small[k] = {
            "detector": v["detector"],
            "mask_ratio": v["mask_ratio"],
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
        }

    manifest = {
        "stage": "frontend100_transformer_mae_tailreg_v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_tag": args.run_tag,
        "source_root": str(source_root),
        "seed": args.seed,
        "mask_ratios": mask_ratios,
        "reuse_mae_run_tag": args.reuse_mae_run_tag,
        "policy_set": [
            "fixed_id_q99",
            "naive_calibrated_budget5000_target1pct",
            "det_floor_50pct_min_alarm",
        ],
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
            "tailreg_lambda": args.tailreg_lambda,
            "tailreg_k": args.tailreg_k,
            "tailreg_warmup": args.tailreg_warmup,
            "tailreg_ema_alpha": args.tailreg_ema_alpha,
            "force_retrain": bool(args.force_retrain),
        },
        "data_sources": {
            "train_csv": str(train_csv),
            "ood_benign_csv": str(ood_benign_csv),
            "attack_csv": str(attack_csv),
            "stage2_manifest": str(stage2_joint / "attack_manifest_stage2.json"),
            "baseline_runs": {k: str(v) for k, v in baseline_runs.items()},
            "baseline_attack_scores": {k: str(v) for k, v in baseline_attack.items()},
        },
        "stage2_subsets": {
            "high_purity_count": int(len(high_idx)),
            "boundary_mixed_count": int(len(mixed_idx)),
            "strong_bins": stage2_manifest["selected_bins"]["strong_bins"],
            "mixed_bins": stage2_manifest["selected_bins"]["mixed_bins"],
        },
        "detector_info": detector_info_small,
        "recommended_mask_ratio": best_mask_ratio,
        "recommended_mae_label": best_mae_label,
        "recommended_mae_tailreg_label": best_mt_label,
        "outputs": {
            "results_csv": str(out_dir / "mae_tailreg_v1_results.csv"),
            "results_md": str(out_dir / "mae_tailreg_v1_results.md"),
            "summary_md": str(out_dir / "mae_tailreg_v1_summary.md"),
            "plots_dir": str(plot_dir),
        },
    }
    manifest = sanitize_for_json(manifest)
    (out_dir / "mae_tailreg_v1_config_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (out_dir / "config.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"[done] mae+tailreg v1 experiment output: {out_dir}")


if __name__ == "__main__":
    main()
