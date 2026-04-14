
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

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
from csv_input import load_numeric_csv


def load_json(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: Dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def sanitize_for_json(obj):
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_for_json(v) for v in obj]
    if isinstance(obj, tuple):
        return [sanitize_for_json(v) for v in obj]
    if isinstance(obj, np.generic):
        return sanitize_for_json(obj.item())
    if isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)):
        return None
    return obj


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


def compute_auc(pos_scores: np.ndarray, neg_scores: np.ndarray) -> float:
    y_true = np.concatenate([np.ones(len(pos_scores), dtype=np.int64), np.zeros(len(neg_scores), dtype=np.int64)])
    y_score = np.concatenate([pos_scores, neg_scores]).astype(np.float64)
    if len(np.unique(y_true)) < 2:
        return float("nan")
    try:
        from sklearn.metrics import roc_auc_score
    except Exception:
        return float("nan")
    return float(roc_auc_score(y_true, y_score))


def score_dataset(model: kit.KitNET, x: np.ndarray, name: str = "") -> np.ndarray:
    scores = np.zeros(len(x), dtype=np.float64)
    for i in range(len(x)):
        if i > 0 and i % 2000 == 0:
            print(f"  scoring {name}: {i}/{len(x)}")
        scores[i] = model.process(x[i])
    return scores


def run_stage1_probe(cmd: List[str]) -> None:
    print("[run] " + " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=str(WORKTREE_ROOT))


def score_uncertainty_mode(
    checkpoint: Path,
    mode: str,
    x_id: np.ndarray,
    x_ood: np.ndarray,
    x_attack: np.ndarray,
    cache_dir: Path,
    force_rescore: bool,
) -> Dict:
    prefix = f"uncertainty_{mode}"
    id_npy = cache_dir / f"{prefix}_id_scores.npy"
    ood_npy = cache_dir / f"{prefix}_ood_scores.npy"
    attack_npy = cache_dir / f"{prefix}_attack_scores.npy"
    diag_json = cache_dir / f"{prefix}_diagnostics.json"

    if (not force_rescore) and id_npy.exists() and ood_npy.exists() and attack_npy.exists() and diag_json.exists():
        return {
            "id_scores": np.load(id_npy).astype(np.float64),
            "ood_scores": np.load(ood_npy).astype(np.float64),
            "attack_scores": np.load(attack_npy).astype(np.float64),
            "diagnostics": load_json(diag_json),
            "score_files": {
                "id_scores": str(id_npy),
                "ood_scores": str(ood_npy),
                "attack_scores": str(attack_npy),
                "diagnostics": str(diag_json),
            },
        }

    model = kit.KitNET.load_checkpoint(checkpoint)
    if hasattr(model, "set_uncertainty_score_mode"):
        model.set_uncertainty_score_mode(mode)

    id_scores = score_dataset(model, x_id, name=f"{mode}/id")
    ood_scores = score_dataset(model, x_ood, name=f"{mode}/ood")
    attack_scores = score_dataset(model, x_attack, name=f"{mode}/attack")

    np.save(id_npy, id_scores)
    np.save(ood_npy, ood_scores)
    np.save(attack_npy, attack_scores)

    diagnostics = {}
    if hasattr(model, "get_uncertainty_diagnostics"):
        diagnostics = model.get_uncertainty_diagnostics()
    diagnostics = sanitize_for_json(diagnostics)
    save_json(diag_json, diagnostics)

    return {
        "id_scores": id_scores,
        "ood_scores": ood_scores,
        "attack_scores": attack_scores,
        "diagnostics": diagnostics,
        "score_files": {
            "id_scores": str(id_npy),
            "ood_scores": str(ood_npy),
            "attack_scores": str(attack_npy),
            "diagnostics": str(diag_json),
        },
    }


def plot_score_distribution(
    detector_label: str,
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
    plt.title(f"{detector_label}: ID/OOD/attack score distributions")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=170)
    plt.close()

def plot_compare_points(rows: pd.DataFrame, out_path: Path, title: str) -> None:
    policy_order = ["fixed_id_q99", "naive_calibrated_budget5000_target1pct", "det_floor_50pct_min_alarm"]
    marker_map = {
        "fixed_id_q99": "s",
        "naive_calibrated_budget5000_target1pct": "x",
        "det_floor_50pct_min_alarm": "o",
    }
    labels = rows["detector_label"].unique().tolist()
    palette = ["#1f77b4", "#2ca02c", "#9467bd", "#d62728", "#8c564b", "#17becf"]
    color_map = {lbl: palette[i % len(palette)] for i, lbl in enumerate(labels)}

    plt.figure(figsize=(9.2, 6.0))
    for lbl in labels:
        sub = rows[rows["detector_label"] == lbl]
        for pname in policy_order:
            p = sub[sub["policy_name"] == pname]
            if p.empty:
                continue
            r = p.iloc[0]
            x = float(r["ood_alarm_ratio_eval"])
            y = float(r["attack_detection_high_purity"])
            plt.scatter([x], [y], s=92, marker=marker_map[pname], color=color_map[lbl])
            short = {
                "fixed_id_q99": "fixed",
                "naive_calibrated_budget5000_target1pct": "naive",
                "det_floor_50pct_min_alarm": "det50",
            }[pname]
            plt.text(x + 0.003, y + 0.010, f"{lbl}:{short}", fontsize=8)

    plt.xlabel("OOD benign alarm ratio (eval split)")
    plt.ylabel("High-purity attack detection")
    plt.title(title)
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(out_path, dpi=170)
    plt.close()


def is_logvar_range_healthy(diag: Dict, margin: float = 0.25) -> bool:
    lo = diag.get("logvar_min_cfg", None)
    hi = diag.get("logvar_max_cfg", None)
    mn = diag.get("logvar_train_min_seen", None)
    mx = diag.get("logvar_train_max_seen", None)
    if lo is None or hi is None or mn is None or mx is None:
        return False
    lo = float(lo)
    hi = float(hi)
    mn = float(mn)
    mx = float(mx)
    if not np.isfinite(lo + hi + mn + mx):
        return False
    return (mn > lo + margin) and (mx < hi - margin)


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(description="Transformer-Uncertainty-v1 experiment on frontend100 stronger OOD.")
    parser.add_argument("--run-tag", default=f"frontend100_uncertainty_v1_{today}")
    parser.add_argument(
        "--source-root",
        type=Path,
        default=WORKTREE_ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--score-modes", default="error_only,uncertainty_only,combined_nll")
    parser.add_argument("--scan-points", type=int, default=901)
    parser.add_argument("--calibration-budget", type=int, default=5000)
    parser.add_argument("--calibration-target", type=float, default=0.01)
    parser.add_argument("--fixed-quantile", type=float, default=0.99)
    parser.add_argument("--max-ae", type=int, default=10)
    parser.add_argument("--fm-grace", type=int, default=2000)
    parser.add_argument("--ad-grace", type=int, default=6000)
    parser.add_argument("--train-samples", type=int, default=8000)
    parser.add_argument("--id-eval-samples", type=int, default=5000)
    parser.add_argument("--learning-rate", type=float, default=0.1)
    parser.add_argument("--hidden-ratio", type=float, default=0.75)
    parser.add_argument("--uncertainty-logvar-min", type=float, default=-8.0)
    parser.add_argument("--uncertainty-logvar-max", type=float, default=8.0)
    parser.add_argument("--force-retrain", action="store_true")
    parser.add_argument("--force-rescore", action="store_true")
    args = parser.parse_args()

    score_modes = [x.strip().lower() for x in args.score_modes.split(",") if x.strip()]
    score_modes = [m for m in score_modes if m in {"error_only", "uncertainty_only", "combined_nll"}]
    if not score_modes:
        raise ValueError("score-modes is empty after filtering")

    out_dir = WORKTREE_ROOT / "runs" / args.run_tag
    out_dir.mkdir(parents=True, exist_ok=True)
    plot_dir = out_dir / "uncertainty_v1_plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = out_dir / "cache_scores"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "command.txt").write_text("python " + " ".join(sys.argv) + "\n", encoding="utf-8")

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
    for p in [train_csv, ood_benign_csv, attack_csv]:
        if not p.exists():
            raise FileNotFoundError(f"Missing file: {p}")

    total_needed = args.train_samples + args.id_eval_samples
    x_all, train_load_info = load_numeric_csv(train_csv, nrows=total_needed, auto_drop_index_col0=True)
    if len(x_all) < total_needed:
        raise RuntimeError(f"Not enough rows in train csv: got {len(x_all)}, need {total_needed}")
    x_id = x_all[args.train_samples : args.train_samples + args.id_eval_samples]
    x_ood, ood_load_info = load_numeric_csv(ood_benign_csv, auto_drop_index_col0=True)
    x_attack = pd.read_csv(attack_csv, header=None).to_numpy(dtype=np.float64)
    if x_id.shape[1] != x_ood.shape[1] or x_id.shape[1] != x_attack.shape[1]:
        raise RuntimeError(
            f"feature dim mismatch: id={x_id.shape[1]}, ood={x_ood.shape[1]}, attack={x_attack.shape[1]}"
        )
    if len(x_attack) <= int(np.max(high_idx)):
        raise RuntimeError("attack_source_100 rows are fewer than stage2 high-purity indices")

    unc_rel_run_tag = f"{args.run_tag}/transformer_uncertainty_v1_seed{args.seed}"
    unc_run_dir = WORKTREE_ROOT / "runs" / unc_rel_run_tag
    stage1_cmd = [
        sys.executable,
        str(REPO_DIR / "ood" / "stage1_probe.py"),
        "--run-tag",
        unc_rel_run_tag,
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
        "transformer_uncertainty_v1",
        "--uncertainty-logvar-min",
        str(args.uncertainty_logvar_min),
        "--uncertainty-logvar-max",
        str(args.uncertainty_logvar_max),
        "--uncertainty-score-mode",
        "combined_nll",
        "--benign-dataset",
        f"iot23_ood_benign|{ood_benign_csv}",
        "--skip-attack",
    ]
    if args.force_retrain:
        stage1_cmd.append("--force-retrain")
    run_stage1_probe(stage1_cmd)

    unc_ckpt = Path(load_json(unc_run_dir / "config.json")["checkpoint"])

    entries: List[Dict] = []
    baseline_runs = {
        "transformer": source_root / "runs" / "frontend100_tailreg_stage1_2026-03-27" / f"transformer_seed{args.seed}",
        "da": source_root / "runs" / "frontend100_tailreg_stage1_2026-03-27" / f"da_seed{args.seed}",
    }
    baseline_attack_files = {
        "transformer": stage1_joint / "transformer_attack_scores.npy",
        "da": stage1_joint / "da_attack_scores.npy",
    }
    for det in ["transformer", "da"]:
        run_dir = baseline_runs[det]
        if not run_dir.exists():
            raise FileNotFoundError(f"Missing baseline run: {run_dir}")
        metrics = load_json(run_dir / "metrics.json")
        ood_name = list(metrics["ood_benign"].keys())[0]
        entries.append(
            {
                "detector": det,
                "detector_label": det,
                "score_mode": "error_only",
                "run_dir": str(run_dir),
                "checkpoint": str(load_json(run_dir / "config.json")["checkpoint"]),
                "id_scores": np.load(run_dir / "id_scores.npy").astype(np.float64),
                "ood_scores": np.load(run_dir / f"{ood_name}_scores.npy").astype(np.float64),
                "attack_scores": np.load(baseline_attack_files[det]).astype(np.float64),
                "diagnostics": {"enabled": False},
                "source_mode": "baseline_reuse",
                "score_files": {
                    "id_scores": str(run_dir / "id_scores.npy"),
                    "ood_scores": str(run_dir / f"{ood_name}_scores.npy"),
                    "attack_scores": str(baseline_attack_files[det]),
                },
            }
        )

    for mode in score_modes:
        mode_res = score_uncertainty_mode(
            checkpoint=unc_ckpt,
            mode=mode,
            x_id=x_id,
            x_ood=x_ood,
            x_attack=x_attack,
            cache_dir=cache_dir,
            force_rescore=args.force_rescore,
        )
        entries.append(
            {
                "detector": "transformer_uncertainty_v1",
                "detector_label": f"transformer_uncertainty_v1_{mode}",
                "score_mode": mode,
                "run_dir": str(unc_run_dir),
                "checkpoint": str(unc_ckpt),
                "id_scores": mode_res["id_scores"],
                "ood_scores": mode_res["ood_scores"],
                "attack_scores": mode_res["attack_scores"],
                "diagnostics": mode_res["diagnostics"],
                "source_mode": "uncertainty_rescore",
                "score_files": mode_res["score_files"],
            }
        )

    policy_rows: List[Dict] = []
    separation_rows: List[Dict] = []
    detector_info: Dict[str, Dict] = {}

    for ent in entries:
        det = ent["detector"]
        det_label = ent["detector_label"]
        mode = ent["score_mode"]
        id_scores = np.asarray(ent["id_scores"], dtype=np.float64)
        ood_scores = np.asarray(ent["ood_scores"], dtype=np.float64)
        attack_scores = np.asarray(ent["attack_scores"], dtype=np.float64)

        if np.any(~np.isfinite(id_scores)) or np.any(~np.isfinite(ood_scores)) or np.any(~np.isfinite(attack_scores)):
            raise RuntimeError(f"Non-finite scores detected in {det_label}")

        budget = int(min(max(1, args.calibration_budget), len(ood_scores) - 1))
        ood_cal = ood_scores[:budget]
        ood_eval = ood_scores[budget:]

        fixed_thr = float(np.quantile(id_scores, args.fixed_quantile))
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
                        "score_mode": mode,
                        "source_mode": ent["source_mode"],
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
                    "score_mode": mode,
                    "source_mode": ent["source_mode"],
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

        separation_rows.append(
            {
                "detector_label": det_label,
                "detector": det,
                "score_mode": mode,
                "attack_high_vs_ood_eval_roc_auc": compute_auc(attack_scores[high_idx], ood_eval),
                "attack_all_vs_ood_eval_roc_auc": compute_auc(attack_scores, ood_eval),
                "attack_high_mean": float(np.mean(attack_scores[high_idx])),
                "ood_eval_mean": float(np.mean(ood_eval)),
                "attack_high_p95": float(np.quantile(attack_scores[high_idx], 0.95)),
                "ood_eval_p95": float(np.quantile(ood_eval, 0.95)),
                "id_mean": float(np.mean(id_scores)),
                "fixed_threshold": fixed_thr,
                "naive_threshold": naive_thr,
                "nonfinite_count": int(
                    np.sum(~np.isfinite(id_scores)) + np.sum(~np.isfinite(ood_scores)) + np.sum(~np.isfinite(attack_scores))
                ),
            }
        )

        detector_info[det_label] = {
            "detector": det,
            "score_mode": mode,
            "run_dir": ent["run_dir"],
            "checkpoint": ent["checkpoint"],
            "source_mode": ent["source_mode"],
            "score_files": ent["score_files"],
            "diagnostics": ent["diagnostics"],
            "fixed_threshold": fixed_thr,
            "naive_threshold": naive_thr,
            "scan_threshold_count": int(len(thresholds)),
            "id_stats": score_stats(id_scores),
            "ood_stats": score_stats(ood_scores),
            "attack_stats": score_stats(attack_scores),
        }

        plot_score_distribution(
            detector_label=det_label,
            id_scores=id_scores,
            ood_scores=ood_scores,
            attack_scores=attack_scores,
            fixed_thr=fixed_thr,
            out_path=plot_dir / f"{det_label}_score_distribution.png",
        )

    results_df = pd.DataFrame(policy_rows).sort_values(["detector_label", "policy_name"])
    sep_df = pd.DataFrame(separation_rows).sort_values(["detector_label"])

    results_csv = out_dir / "uncertainty_v1_results.csv"
    sep_csv = out_dir / "uncertainty_v1_score_separation.csv"
    results_df.to_csv(results_csv, index=False)
    sep_df.to_csv(sep_csv, index=False)

    show_cols = [
        "detector_label",
        "score_mode",
        "policy_name",
        "threshold",
        "ood_alarm_ratio_eval",
        "attack_detection_high_purity",
        "attack_detection_boundary",
        "alarm_reduction_vs_fixed",
        "detection_retention_vs_fixed",
    ]
    (out_dir / "uncertainty_v1_results.md").write_text(md_table(results_df[show_cols]), encoding="utf-8")

    main_plot_df = results_df[
        results_df["detector_label"].isin(["transformer", "transformer_uncertainty_v1_combined_nll", "da"])
        & results_df["selection_feasible"]
    ].copy()
    if not main_plot_df.empty:
        plot_compare_points(
            main_plot_df,
            plot_dir / "transformer_vs_uncertainty_combined_vs_da.png",
            "Transformer vs Uncertainty-NLL vs dA",
        )

    mode_plot_df = results_df[
        results_df["detector_label"].isin(
            [
                "transformer_uncertainty_v1_error_only",
                "transformer_uncertainty_v1_uncertainty_only",
                "transformer_uncertainty_v1_combined_nll",
            ]
        )
        & results_df["selection_feasible"]
    ].copy()
    if not mode_plot_df.empty:
        plot_compare_points(
            mode_plot_df,
            plot_dir / "uncertainty_score_mode_compare.png",
            "Uncertainty-v1 score modes",
        )

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
    unc_fixed_alarm = getv("transformer_uncertainty_v1_combined_nll", "fixed_id_q99", "ood_alarm_ratio_eval")
    unc_fixed_det = getv("transformer_uncertainty_v1_combined_nll", "fixed_id_q99", "attack_detection_high_purity")

    error_auc = float(
        sep_df.loc[sep_df["detector_label"] == "transformer_uncertainty_v1_error_only", "attack_high_vs_ood_eval_roc_auc"].iloc[0]
    )
    combined_auc = float(
        sep_df.loc[sep_df["detector_label"] == "transformer_uncertainty_v1_combined_nll", "attack_high_vs_ood_eval_roc_auc"].iloc[0]
    )
    unc_diag = detector_info["transformer_uncertainty_v1_combined_nll"]["diagnostics"]
    naninf_train = int(unc_diag.get("nan_inf_train_events_total", 0) or 0)
    naninf_exec = int(unc_diag.get("nan_inf_exec_events_total", 0) or 0)
    logvar_healthy = is_logvar_range_healthy(unc_diag)

    summary_lines: List[str] = []
    summary_lines.append("# Transformer-Uncertainty-v1 Summary")
    summary_lines.append("")
    summary_lines.append("## Setup")
    summary_lines.append("- Mainline: original-frontend 100D + stronger OOD.")
    summary_lines.append(f"- Seed: {args.seed} (single-seed).")
    summary_lines.append("- Compared detectors: transformer / transformer_uncertainty_v1 / da.")
    summary_lines.append("- Scores: error-only, uncertainty-only, combined NLL.")
    summary_lines.append(
        f"- Combined score uses Gaussian NLL: 0.5*exp(-log_var)*(x-mu)^2 + 0.5*log_var with log_var clamp=[{args.uncertainty_logvar_min}, {args.uncertainty_logvar_max}]."
    )
    summary_lines.append("")
    summary_lines.append("## Stability Checks")
    summary_lines.append(f"- NaN/Inf: train={naninf_train}, exec={naninf_exec}.")
    summary_lines.append(
        f"- log_var range: train=[{unc_diag.get('logvar_train_min_seen')}, {unc_diag.get('logvar_train_max_seen')}], exec=[{unc_diag.get('logvar_exec_min_seen')}, {unc_diag.get('logvar_exec_max_seen')}]."
    )
    summary_lines.append(f"- log_var health: {'healthy' if logvar_healthy else 'edge-clamped/needs watch'}.")
    summary_lines.append("")
    summary_lines.append("## Fixed Threshold Core")
    summary_lines.append(f"- transformer: alarm={tf_fixed_alarm:.4f}, det={tf_fixed_det:.4f}")
    summary_lines.append(f"- transformer_uncertainty_v1_combined_nll: alarm={unc_fixed_alarm:.4f}, det={unc_fixed_det:.4f}")
    summary_lines.append(f"- da: alarm={da_fixed_alarm:.4f}, det={da_fixed_det:.4f}")
    summary_lines.append("")
    summary_lines.append("## Combined vs Error")
    summary_lines.append(
        f"- attack_high vs ood_eval ROC-AUC: combined={combined_auc:.4f}, error_only={error_auc:.4f}, delta={combined_auc - error_auc:+.4f}."
    )
    if np.isnan(combined_auc) or np.isnan(error_auc):
        summary_lines.append("- Verdict: separability unavailable/unstable.")
    elif combined_auc > error_auc + 0.01:
        summary_lines.append("- Verdict: combined NLL has better separability.")
    elif combined_auc < error_auc - 0.01:
        summary_lines.append("- Verdict: combined NLL is worse than error-only.")
    else:
        summary_lines.append("- Verdict: combined NLL and error-only are similar.")

    summary_lines.append("")
    summary_lines.append("## Notes")
    summary_lines.append("- This round uses NLL directly as anomaly score; no extra score-fusion tuning.")
    summary_lines.append("- Threshold policy comparison is reported separately (fixed/naive/det50).")

    summary_text = "\n".join(summary_lines) + "\n"
    (out_dir / "uncertainty_v1_summary.md").write_text(summary_text, encoding="utf-8")
    (out_dir / "summary.md").write_text(summary_text, encoding="utf-8")

    manifest = {
        "stage": "frontend100_transformer_uncertainty_v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_tag": args.run_tag,
        "source_root": str(source_root),
        "seed": args.seed,
        "score_modes": score_modes,
        "policy_set": ["fixed_id_q99", "naive_calibrated_budget5000_target1pct", "det_floor_50pct_min_alarm"],
        "calibration": {
            "budget": args.calibration_budget,
            "target_alarm": args.calibration_target,
            "scan_points": args.scan_points,
            "fixed_quantile": args.fixed_quantile,
        },
        "train_config": {
            "max_ae": args.max_ae,
            "fm_grace": args.fm_grace,
            "ad_grace": args.ad_grace,
            "train_samples": args.train_samples,
            "id_eval_samples": args.id_eval_samples,
            "learning_rate": args.learning_rate,
            "hidden_ratio": args.hidden_ratio,
            "uncertainty_logvar_min": args.uncertainty_logvar_min,
            "uncertainty_logvar_max": args.uncertainty_logvar_max,
            "force_retrain": bool(args.force_retrain),
            "force_rescore": bool(args.force_rescore),
        },
        "data_sources": {
            "train_csv": str(train_csv),
            "ood_benign_csv": str(ood_benign_csv),
            "attack_csv": str(attack_csv),
            "stage2_manifest": str(stage2_joint / "attack_manifest_stage2.json"),
            "train_load_info": train_load_info,
            "ood_load_info": ood_load_info,
            "uncertainty_run_dir": str(unc_run_dir),
            "uncertainty_checkpoint": str(unc_ckpt),
            "baseline_runs": {k: str(v) for k, v in baseline_runs.items()},
            "baseline_attack_scores": {k: str(v) for k, v in baseline_attack_files.items()},
        },
        "stage2_subsets": {
            "high_purity_count": int(len(high_idx)),
            "boundary_mixed_count": int(len(mixed_idx)),
            "strong_bins": stage2_manifest["selected_bins"]["strong_bins"],
            "mixed_bins": stage2_manifest["selected_bins"]["mixed_bins"],
        },
        "detector_info": detector_info,
        "outputs": {
            "results_csv": str(results_csv),
            "score_separation_csv": str(sep_csv),
            "results_md": str(out_dir / "uncertainty_v1_results.md"),
            "summary_md": str(out_dir / "uncertainty_v1_summary.md"),
            "plots_dir": str(plot_dir),
        },
    }
    manifest = sanitize_for_json(manifest)
    save_json(out_dir / "uncertainty_v1_config_manifest.json", manifest)
    save_json(out_dir / "config.json", manifest)

    print(f"[done] uncertainty-v1 experiment output: {out_dir}")


if __name__ == "__main__":
    main()
