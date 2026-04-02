from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = REPO_DIR.parent


def score_stats(x: np.ndarray) -> Dict[str, float]:
    q = np.quantile(x, [0.95, 0.99, 0.999])
    return {
        "n": int(len(x)),
        "mean": float(np.mean(x)),
        "std": float(np.std(x)),
        "q95": float(q[0]),
        "q99": float(q[1]),
        "q999": float(q[2]),
        "max": float(np.max(x)),
    }


def load_scores(run_dir: Path) -> Tuple[np.ndarray, np.ndarray, str]:
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    ood_name = list(metrics["ood_benign"].keys())[0]
    id_scores = np.load(run_dir / "id_scores.npy").astype(np.float64)
    ood_scores = np.load(run_dir / f"{ood_name}_scores.npy").astype(np.float64)
    return id_scores, ood_scores, ood_name


def md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = []
    lines.append("| " + " | ".join(cols) + " |")
    lines.append("|" + "|".join(["---"] * len(cols)) + "|")
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


def evaluate_policies(
    detector: str,
    id_scores: np.ndarray,
    ood_scores: np.ndarray,
    id_q: float,
    calib_n: int,
    target_alarm: float,
) -> List[Dict]:
    rows: List[Dict] = []
    id_stat = score_stats(id_scores)
    ood_stat_full = score_stats(ood_scores)

    # Policy A: fixed ID q99 threshold.
    thr_fixed = float(np.quantile(id_scores, id_q))
    rows.append(
        {
            "detector": detector,
            "threshold_policy": "fixed_id_q99",
            "threshold_value": thr_fixed,
            "calibration_rows": 0,
            "target_alarm_rate": np.nan,
            "id_alarm_ratio": float(np.mean(id_scores > thr_fixed)),
            "ood_alarm_ratio_eval": float(np.mean(ood_scores > thr_fixed)),
            "ood_alarm_ratio_full": float(np.mean(ood_scores > thr_fixed)),
            "id_mean": id_stat["mean"],
            "id_std": id_stat["std"],
            "id_q95": id_stat["q95"],
            "id_q99": id_stat["q99"],
            "ood_mean": ood_stat_full["mean"],
            "ood_std": ood_stat_full["std"],
            "ood_q95": ood_stat_full["q95"],
            "ood_q99": ood_stat_full["q99"],
            "ood_q999": ood_stat_full["q999"],
            "ood_max": ood_stat_full["max"],
        }
    )

    # Policy B: unsupervised OOD-aware threshold adaptation via calibration split.
    calib_n = int(min(max(1, calib_n), len(ood_scores) - 1))
    ood_calib = ood_scores[:calib_n]
    ood_eval = ood_scores[calib_n:]
    thr_adapt = float(np.quantile(ood_calib, 1.0 - target_alarm))
    rows.append(
        {
            "detector": detector,
            "threshold_policy": "ood_target_alarm_calib",
            "threshold_value": thr_adapt,
            "calibration_rows": int(calib_n),
            "target_alarm_rate": float(target_alarm),
            "id_alarm_ratio": float(np.mean(id_scores > thr_adapt)),
            "ood_alarm_ratio_eval": float(np.mean(ood_eval > thr_adapt)),
            "ood_alarm_ratio_full": float(np.mean(ood_scores > thr_adapt)),
            "id_mean": id_stat["mean"],
            "id_std": id_stat["std"],
            "id_q95": id_stat["q95"],
            "id_q99": id_stat["q99"],
            "ood_mean": ood_stat_full["mean"],
            "ood_std": ood_stat_full["std"],
            "ood_q95": ood_stat_full["q95"],
            "ood_q99": ood_stat_full["q99"],
            "ood_q999": ood_stat_full["q999"],
            "ood_max": ood_stat_full["max"],
        }
    )
    return rows


def plot_alarm_ratio(df: pd.DataFrame, out_path: Path) -> None:
    order = ["transformer", "da"]
    policies = ["fixed_id_q99", "ood_target_alarm_calib"]
    x = np.arange(len(order))
    width = 0.35
    plt.figure(figsize=(7.8, 4.5))
    for i, p in enumerate(policies):
        vals = []
        for d in order:
            row = df[(df["detector"] == d) & (df["threshold_policy"] == p)].iloc[0]
            vals.append(float(row["ood_alarm_ratio_eval"]))
        shift = -width / 2 if i == 0 else width / 2
        plt.bar(x + shift, vals, width=width, label=p)
        for j, v in enumerate(vals):
            plt.text(x[j] + shift, v + 0.005, f"{v:.3f}", ha="center", va="bottom", fontsize=9)
    plt.xticks(x, order)
    plt.ylabel("OOD benign alarm ratio")
    plt.title("Threshold policy comparison (cross-capture, eval split)")
    plt.grid(axis="y", alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=160)
    plt.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Threshold adaptation baseline on frontend100 cross-capture scores.")
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--run-tag", required=True)
    parser.add_argument("--id-quantile", type=float, default=0.99)
    parser.add_argument("--ood-calibration-rows", type=int, default=5000)
    parser.add_argument("--target-alarm-rate", type=float, default=0.05)
    args = parser.parse_args()

    run_dir = ROOT_DIR / "runs" / args.run_tag
    run_dir.mkdir(parents=True, exist_ok=True)
    plot_dir = run_dir / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)

    detectors = {
        "transformer": args.source_root / "transformer_seed42",
        "da": args.source_root / "da_seed42",
    }

    rows: List[Dict] = []
    for det, det_run in detectors.items():
        id_scores, ood_scores, _ = load_scores(det_run)
        rows.extend(
            evaluate_policies(
                detector=det,
                id_scores=id_scores,
                ood_scores=ood_scores,
                id_q=args.id_quantile,
                calib_n=args.ood_calibration_rows,
                target_alarm=args.target_alarm_rate,
            )
        )

    df = pd.DataFrame(rows)
    df.to_csv(run_dir / "threshold_comparison.csv", index=False)
    (run_dir / "threshold_comparison.md").write_text(md_table(df), encoding="utf-8")
    plot_alarm_ratio(df, plot_dir / "threshold_policy_alarm_ratio.png")
    print(f"[done] threshold comparison written to: {run_dir}")


if __name__ == "__main__":
    main()
