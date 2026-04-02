from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = REPO_DIR.parent


def stats(x: np.ndarray) -> Dict[str, float]:
    q95, q99 = np.quantile(x, [0.95, 0.99])
    return {
        "mean": float(np.mean(x)),
        "std": float(np.std(x)),
        "q95": float(q95),
        "q99": float(q99),
    }


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


def load_run(run_dir: Path) -> Dict[str, object]:
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    ood_name = list(metrics["ood_benign"].keys())[0]
    return {
        "run_dir": str(run_dir),
        "metrics": metrics,
        "ood_name": ood_name,
        "id_scores": np.load(run_dir / "id_scores.npy").astype(np.float64),
        "ood_scores": np.load(run_dir / f"{ood_name}_scores.npy").astype(np.float64),
    }


def build_rows(
    detector: str,
    record: Dict[str, object],
    calibration_budget: int,
    target_alarm_rate: float,
) -> List[Dict[str, object]]:
    metrics = record["metrics"]
    id_scores = record["id_scores"]
    ood_scores = record["ood_scores"]

    id_st = stats(id_scores)
    ood_st = stats(ood_scores)
    fixed_thr = float(metrics["threshold_value"])
    fixed_ood_alarm = float(metrics["ood_benign"][record["ood_name"]]["alarm_ratio_at_id_q99_threshold"])
    fixed_id_alarm = float(np.mean(id_scores > fixed_thr))

    rows: List[Dict[str, object]] = []
    rows.append(
        {
            "detector": detector,
            "policy": "fixed_id_q99",
            "calibration_budget": 0,
            "target_alarm_rate": np.nan,
            "threshold": fixed_thr,
            "threshold_delta_vs_fixed": 0.0,
            "id_alarm_ratio": fixed_id_alarm,
            "ood_alarm_ratio": fixed_ood_alarm,
            "eval_rows": int(len(ood_scores)),
            "id_mean": id_st["mean"],
            "id_q95": id_st["q95"],
            "id_q99": id_st["q99"],
            "ood_mean": ood_st["mean"],
            "ood_q95": ood_st["q95"],
            "ood_q99": ood_st["q99"],
        }
    )

    budget = int(min(max(1, calibration_budget), len(ood_scores) - 1))
    ood_calib = ood_scores[:budget]
    ood_eval = ood_scores[budget:]
    ood_eval_stats = stats(ood_eval)
    calibrated_thr = float(np.quantile(ood_calib, 1.0 - target_alarm_rate))
    calibrated_ood_alarm = float(np.mean(ood_eval > calibrated_thr))
    calibrated_id_alarm = float(np.mean(id_scores > calibrated_thr))
    rows.append(
        {
            "detector": detector,
            "policy": "calib_budget_target",
            "calibration_budget": budget,
            "target_alarm_rate": float(target_alarm_rate),
            "threshold": calibrated_thr,
            "threshold_delta_vs_fixed": float(calibrated_thr - fixed_thr),
            "id_alarm_ratio": calibrated_id_alarm,
            "ood_alarm_ratio": calibrated_ood_alarm,
            "eval_rows": int(len(ood_eval)),
            "id_mean": id_st["mean"],
            "id_q95": id_st["q95"],
            "id_q99": id_st["q99"],
            "ood_mean": ood_eval_stats["mean"],
            "ood_q95": ood_eval_stats["q95"],
            "ood_q99": ood_eval_stats["q99"],
        }
    )
    return rows


def plot_alarm_ratio(df: pd.DataFrame, out_path: Path) -> None:
    detectors = ["transformer", "transformer_tailreg", "da"]
    x = np.arange(len(detectors))
    width = 0.35

    fixed = []
    calib = []
    for det in detectors:
        fixed.append(float(df[(df["detector"] == det) & (df["policy"] == "fixed_id_q99")]["ood_alarm_ratio"].iloc[0]))
        calib.append(float(df[(df["detector"] == det) & (df["policy"] == "calib_budget_target")]["ood_alarm_ratio"].iloc[0]))

    plt.figure(figsize=(8.5, 4.8))
    plt.bar(x - width / 2, fixed, width=width, label="fixed ID q99")
    plt.bar(x + width / 2, calib, width=width, label="calibrated")
    plt.xticks(x, detectors)
    plt.ylabel("OOD benign alarm ratio")
    plt.title("Detector comparison: fixed vs calibrated threshold")
    plt.grid(axis="y", alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=160)
    plt.close()


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(description="Build fixed-vs-calibrated comparison for tail-reg stage1 runs.")
    parser.add_argument("--run-tag", default=f"frontend100_tailreg_stage1_{today}")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--calibration-budget", type=int, default=5000)
    parser.add_argument("--target-alarm-rate", type=float, default=0.01)
    args = parser.parse_args()

    run_root = ROOT_DIR / "runs" / args.run_tag
    plot_dir = run_root / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)

    run_map = {
        "transformer": run_root / f"transformer_seed{args.seed}",
        "transformer_tailreg": run_root / f"transformer_tailreg_seed{args.seed}",
        "da": run_root / f"da_seed{args.seed}",
    }
    for det, path in run_map.items():
        if not path.exists():
            raise FileNotFoundError(f"Missing run dir for {det}: {path}")

    rows: List[Dict[str, object]] = []
    for det, path in run_map.items():
        rows.extend(build_rows(det, load_run(path), args.calibration_budget, args.target_alarm_rate))

    df = pd.DataFrame(rows)
    df.to_csv(run_root / "detector_compare_fixed_vs_calibrated.csv", index=False)
    (run_root / "detector_compare_fixed_vs_calibrated.md").write_text(md_table(df), encoding="utf-8")

    plot_alarm_ratio(df, plot_dir / "alarm_ratio_fixed_vs_calibrated.png")

    fixed = df[df["policy"] == "fixed_id_q99"].set_index("detector")
    calib = df[df["policy"] == "calib_budget_target"].set_index("detector")
    tf_fixed = float(fixed.loc["transformer", "ood_alarm_ratio"])
    tf_tail_fixed = float(fixed.loc["transformer_tailreg", "ood_alarm_ratio"])
    da_fixed = float(fixed.loc["da", "ood_alarm_ratio"])
    tf_cal = float(calib.loc["transformer", "ood_alarm_ratio"])
    tf_tail_cal = float(calib.loc["transformer_tailreg", "ood_alarm_ratio"])
    da_cal = float(calib.loc["da", "ood_alarm_ratio"])

    lines: List[str] = []
    lines.append("# Frontend100 Tail-Regularized Transformer Stage1 Summary")
    lines.append("")
    lines.append("## Protocol")
    lines.append("- ID: CTU-Honeypot-Capture-7-6")
    lines.append("- OOD benign: CTU-Honeypot-Capture-4-1")
    lines.append("- Input: original-frontend 100-D")
    lines.append("- train_samples=8000, id_eval_samples=5000, fm=2000, ad=6000, seed=42")
    lines.append("- Compared detectors: transformer / transformer_tailreg / da")
    lines.append("")
    lines.append("## Calibration policy")
    lines.append(
        f"- Unsupervised OOD calibration: budget={args.calibration_budget}, "
        f"target_alarm_rate={args.target_alarm_rate:.4f}, non-overlap eval."
    )
    lines.append("")
    lines.append("## Key results")
    lines.append(
        f"- Fixed threshold OOD alarm: transformer={tf_fixed:.4f}, "
        f"transformer_tailreg={tf_tail_fixed:.4f}, da={da_fixed:.4f}"
    )
    lines.append(
        f"- Calibrated OOD alarm: transformer={tf_cal:.4f}, "
        f"transformer_tailreg={tf_tail_cal:.4f}, da={da_cal:.4f}"
    )
    lines.append(
        f"- Tail-reg fixed-threshold delta vs transformer: {tf_tail_fixed - tf_fixed:+.4f} "
        f"({(tf_tail_fixed - tf_fixed) * 100:+.2f} pp)"
    )
    lines.append(
        f"- Tail-reg calibrated delta vs transformer: {tf_tail_cal - tf_cal:+.4f} "
        f"({(tf_tail_cal - tf_cal) * 100:+.2f} pp)"
    )
    lines.append(
        f"- Gap to dA (fixed): transformer={tf_fixed - da_fixed:+.4f}, "
        f"tailreg={tf_tail_fixed - da_fixed:+.4f}"
    )
    lines.append(
        f"- Gap to dA (calibrated): transformer={tf_cal - da_cal:+.4f}, "
        f"tailreg={tf_tail_cal - da_cal:+.4f}"
    )
    lines.append("")
    lines.append("## Interpretation")
    lines.append("- Tail-regularization improves fixed-threshold sensitivity for stronger OOD.")
    lines.append("- Under strong calibration, both transformer variants are close and gap to dA is already small.")
    lines.append("- This indicates the change mainly helps fixed-threshold robustness; calibrated residual gap change is limited in this first version.")
    (run_root / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    config = {
        "run_tag": args.run_tag,
        "seed": args.seed,
        "calibration_budget": args.calibration_budget,
        "target_alarm_rate": args.target_alarm_rate,
        "detector_run_dirs": {k: str(v) for k, v in run_map.items()},
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    (run_root / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(f"[done] wrote report under: {run_root}")


if __name__ == "__main__":
    main()
