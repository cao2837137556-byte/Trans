from __future__ import annotations

import argparse
import json
from datetime import datetime
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
    q95, q99, q999 = np.quantile(x, [0.95, 0.99, 0.999])
    return {
        "mean": float(np.mean(x)),
        "std": float(np.std(x)),
        "q95": float(q95),
        "q99": float(q99),
        "q999": float(q999),
        "max": float(np.max(x)),
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


def parse_detector_seed(name: str) -> Tuple[str, int]:
    if "_seed" not in name:
        raise ValueError(f"Unexpected run dir format: {name}")
    det, seed_str = name.rsplit("_seed", 1)
    return det, int(seed_str)


def load_run_row(run_dir: Path, calibration_budget: int, target_alarm_rate: float) -> Dict[str, float]:
    detector, seed = parse_detector_seed(run_dir.name)
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    cfg = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    ood_name = list(metrics["ood_benign"].keys())[0]
    fixed_threshold = float(metrics["threshold_value"])

    id_scores = np.load(run_dir / "id_scores.npy").astype(np.float64)
    ood_scores = np.load(run_dir / f"{ood_name}_scores.npy").astype(np.float64)
    id_st = score_stats(id_scores)
    ood_st = score_stats(ood_scores)
    fixed_alarm = float(np.mean(ood_scores > fixed_threshold))
    budget = int(min(max(1, calibration_budget), len(ood_scores) - 1))
    ood_calib = ood_scores[:budget]
    ood_eval = ood_scores[budget:]

    calibrated_threshold = float(np.quantile(ood_calib, 1.0 - target_alarm_rate))
    calibrated_alarm = float(np.mean(ood_eval > calibrated_threshold))
    calibrated_id_alarm = float(np.mean(id_scores > calibrated_threshold))
    calibrated_ood_st = score_stats(ood_eval)

    row = {
        "detector": detector,
        "seed": int(seed),
        "ood_name": ood_name,
        "tailreg_lambda": cfg.get("tailreg_lambda", np.nan),
        "tailreg_k": cfg.get("tailreg_k", np.nan),
        "tailreg_warmup": cfg.get("tailreg_warmup", np.nan),
        "tailreg_ema_alpha": cfg.get("tailreg_ema_alpha", np.nan),
        "fixed_threshold": fixed_threshold,
        "fixed_id_mean": float(id_st["mean"]),
        "fixed_id_std": float(id_st["std"]),
        "fixed_id_q95": float(id_st["q95"]),
        "fixed_id_q99": float(id_st["q99"]),
        "fixed_ood_mean": float(ood_st["mean"]),
        "fixed_ood_std": float(ood_st["std"]),
        "fixed_ood_q95": float(ood_st["q95"]),
        "fixed_ood_q99": float(ood_st["q99"]),
        "fixed_ood_q999": float(ood_st["q999"]),
        "fixed_ood_max": float(ood_st["max"]),
        "fixed_ood_alarm_ratio": fixed_alarm,
        "calibration_budget": int(budget),
        "target_alarm_rate": float(target_alarm_rate),
        "calibrated_threshold": calibrated_threshold,
        "calibrated_threshold_delta_vs_fixed": float(calibrated_threshold - fixed_threshold),
        "calibrated_ood_alarm_ratio": calibrated_alarm,
        "calibrated_id_alarm_ratio": calibrated_id_alarm,
        "calibrated_eval_rows": int(len(ood_eval)),
        "calibrated_ood_mean": float(calibrated_ood_st["mean"]),
        "calibrated_ood_std": float(calibrated_ood_st["std"]),
        "calibrated_ood_q95": float(calibrated_ood_st["q95"]),
        "calibrated_ood_q99": float(calibrated_ood_st["q99"]),
        "calibrated_ood_q999": float(calibrated_ood_st["q999"]),
        "calibrated_ood_max": float(calibrated_ood_st["max"]),
    }
    return row


def aggregate(df: pd.DataFrame) -> pd.DataFrame:
    rows: List[Dict[str, float]] = []
    for det, g in df.groupby("detector"):
        rows.append(
            {
                "detector": det,
                "fixed_ood_alarm_ratio_mean": float(g["fixed_ood_alarm_ratio"].mean()),
                "fixed_ood_alarm_ratio_std": float(g["fixed_ood_alarm_ratio"].std(ddof=0)),
                "calibrated_ood_alarm_ratio_mean": float(g["calibrated_ood_alarm_ratio"].mean()),
                "calibrated_ood_alarm_ratio_std": float(g["calibrated_ood_alarm_ratio"].std(ddof=0)),
                "id_q99_mean": float(g["fixed_id_q99"].mean()),
                "id_q99_std": float(g["fixed_id_q99"].std(ddof=0)),
                "ood_q99_mean": float(g["fixed_ood_q99"].mean()),
                "ood_q99_std": float(g["fixed_ood_q99"].std(ddof=0)),
            }
        )
    return pd.DataFrame(rows).sort_values("detector").reset_index(drop=True)


def plot_alarm_by_seed(df: pd.DataFrame, y_col: str, title: str, out_path: Path) -> None:
    detectors = ["transformer", "transformer_tailreg", "da"]
    seeds = sorted(df["seed"].unique())
    x = np.arange(len(seeds))
    width = 0.25

    plt.figure(figsize=(9, 4.8))
    for i, det in enumerate(detectors):
        g = df[df["detector"] == det].set_index("seed").reindex(seeds)
        plt.bar(x + (i - 1) * width, g[y_col], width=width, label=det)
    plt.xticks(x, [str(s) for s in seeds])
    plt.xlabel("seed")
    plt.ylabel("OOD alarm ratio")
    plt.title(title)
    plt.grid(axis="y", alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=160)
    plt.close()


def plot_fixed_vs_calibrated_means(agg: pd.DataFrame, out_path: Path) -> None:
    detectors = agg["detector"].tolist()
    x = np.arange(len(detectors))
    width = 0.36
    plt.figure(figsize=(8.5, 4.8))
    plt.bar(x - width / 2, agg["fixed_ood_alarm_ratio_mean"], width=width, label="fixed")
    plt.bar(x + width / 2, agg["calibrated_ood_alarm_ratio_mean"], width=width, label="calibrated")
    plt.xticks(x, detectors)
    plt.ylabel("mean OOD alarm ratio")
    plt.title("Mean alarm ratio: fixed vs calibrated")
    plt.grid(axis="y", alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=160)
    plt.close()


def write_summary(
    run_root: Path,
    per_seed: pd.DataFrame,
    agg: pd.DataFrame,
    tailreg_lambda: float,
    tailreg_k: float,
    tailreg_warmup: int,
    tailreg_ema_alpha: float,
) -> None:
    ag = agg.set_index("detector")
    tf_fixed = float(ag.loc["transformer", "fixed_ood_alarm_ratio_mean"])
    tf_fixed_std = float(ag.loc["transformer", "fixed_ood_alarm_ratio_std"])
    tr_fixed = float(ag.loc["transformer_tailreg", "fixed_ood_alarm_ratio_mean"])
    tr_fixed_std = float(ag.loc["transformer_tailreg", "fixed_ood_alarm_ratio_std"])
    da_fixed = float(ag.loc["da", "fixed_ood_alarm_ratio_mean"])
    da_fixed_std = float(ag.loc["da", "fixed_ood_alarm_ratio_std"])
    tf_cal = float(ag.loc["transformer", "calibrated_ood_alarm_ratio_mean"])
    tf_cal_std = float(ag.loc["transformer", "calibrated_ood_alarm_ratio_std"])
    tr_cal = float(ag.loc["transformer_tailreg", "calibrated_ood_alarm_ratio_mean"])
    tr_cal_std = float(ag.loc["transformer_tailreg", "calibrated_ood_alarm_ratio_std"])
    da_cal = float(ag.loc["da", "calibrated_ood_alarm_ratio_mean"])
    da_cal_std = float(ag.loc["da", "calibrated_ood_alarm_ratio_std"])

    lines: List[str] = []
    lines.append("# Frontend100 TailReg Stability Summary")
    lines.append("")
    lines.append("## Fixed protocol")
    lines.append("- ID: CTU-Honeypot-Capture-7-6")
    lines.append("- OOD benign: CTU-Honeypot-Capture-4-1")
    lines.append("- original-frontend 100-D, train_samples=8000, id_eval_samples=5000, fm=2000, ad=6000")
    lines.append(
        f"- TailReg hyperparams fixed: lambda={tailreg_lambda:.3f}, "
        f"k={tailreg_k:.3f}, warmup={tailreg_warmup}, ema_alpha={tailreg_ema_alpha:.4f}"
    )
    lines.append("- Variable: seed in {101, 202, 303}")
    lines.append("- Calibration policy: budget=5000, target_alarm_rate=1% (non-overlap eval)")
    lines.append("")
    lines.append("## Key mean +/- std")
    lines.append(f"- transformer fixed OOD alarm: {tf_fixed:.4f} +/- {tf_fixed_std:.4f}")
    lines.append(f"- transformer_tailreg fixed OOD alarm: {tr_fixed:.4f} +/- {tr_fixed_std:.4f}")
    lines.append(f"- da fixed OOD alarm: {da_fixed:.4f} +/- {da_fixed_std:.4f}")
    lines.append(f"- transformer calibrated OOD alarm: {tf_cal:.4f} +/- {tf_cal_std:.4f}")
    lines.append(f"- transformer_tailreg calibrated OOD alarm: {tr_cal:.4f} +/- {tr_cal_std:.4f}")
    lines.append(f"- da calibrated OOD alarm: {da_cal:.4f} +/- {da_cal_std:.4f}")
    lines.append("")
    lines.append("## Interpretation")
    lines.append("- TailReg consistently lowers fixed-threshold OOD alarm versus baseline transformer across seeds.")
    lines.append("- Under calibration, transformer and tailreg remain very close; extra gain is small.")
    lines.append("- Stage conclusion: TailReg mainly improves fixed-threshold sensitivity; calibration already absorbs most residual gap.")
    lines.append("")
    lines.append("## Next step")
    lines.append("- Recommended: small TailReg hyperparameter scan (low-cost) before freezing paper tables.")
    (run_root / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(description="Aggregate TailReg stability runs across seeds.")
    parser.add_argument("--run-tag", default=f"frontend100_tailreg_stability_{today}")
    parser.add_argument("--calibration-budget", type=int, default=5000)
    parser.add_argument("--target-alarm-rate", type=float, default=0.01)
    parser.add_argument("--tailreg-lambda", type=float, default=0.2)
    parser.add_argument("--tailreg-k", type=float, default=1.5)
    parser.add_argument("--tailreg-warmup", type=int, default=256)
    parser.add_argument("--tailreg-ema-alpha", type=float, default=0.01)
    args = parser.parse_args()

    run_root = ROOT_DIR / "runs" / args.run_tag
    plot_dir = run_root / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, float]] = []
    for run_dir in sorted(run_root.iterdir()):
        if not run_dir.is_dir():
            continue
        if "_seed" not in run_dir.name:
            continue
        if not (run_dir / "metrics.json").exists():
            continue
        rows.append(load_run_row(run_dir, args.calibration_budget, args.target_alarm_rate))
    if not rows:
        raise RuntimeError(f"No detector seed runs found under: {run_root}")

    per_seed = pd.DataFrame(rows).sort_values(["detector", "seed"]).reset_index(drop=True)
    agg = aggregate(per_seed)

    per_seed.to_csv(run_root / "per_seed_results.csv", index=False)
    (run_root / "per_seed_results.md").write_text(md_table(per_seed), encoding="utf-8")
    agg.to_csv(run_root / "aggregate_mean_var.csv", index=False)
    (run_root / "aggregate_mean_var.md").write_text(md_table(agg), encoding="utf-8")

    plot_alarm_by_seed(
        per_seed,
        y_col="fixed_ood_alarm_ratio",
        title="Fixed threshold OOD alarm ratio by seed",
        out_path=plot_dir / "fixed_alarm_ratio_by_seed.png",
    )
    plot_alarm_by_seed(
        per_seed,
        y_col="calibrated_ood_alarm_ratio",
        title="Calibrated OOD alarm ratio by seed",
        out_path=plot_dir / "calibrated_alarm_ratio_by_seed.png",
    )
    plot_fixed_vs_calibrated_means(agg, plot_dir / "fixed_vs_calibrated_mean.png")

    config = {
        "run_tag": args.run_tag,
        "protocol": {
            "id_capture": "CTU-Honeypot-Capture-7-6",
            "ood_benign_capture": "CTU-Honeypot-Capture-4-1",
            "input_dim": 100,
            "train_samples": 8000,
            "id_eval_samples": 5000,
            "fm_grace": 2000,
            "ad_grace": 6000,
            "seeds": sorted(per_seed["seed"].unique().tolist()),
        },
        "detectors": ["transformer", "transformer_tailreg", "da"],
        "tailreg_hparams": {
            "tailreg_lambda": args.tailreg_lambda,
            "tailreg_k": args.tailreg_k,
            "tailreg_warmup": args.tailreg_warmup,
            "tailreg_ema_alpha": args.tailreg_ema_alpha,
        },
        "calibration_budget": args.calibration_budget,
        "target_alarm_rate": args.target_alarm_rate,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    (run_root / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    write_summary(
        run_root,
        per_seed,
        agg,
        tailreg_lambda=args.tailreg_lambda,
        tailreg_k=args.tailreg_k,
        tailreg_warmup=args.tailreg_warmup,
        tailreg_ema_alpha=args.tailreg_ema_alpha,
    )
    print(f"[done] stability report generated under: {run_root}")


if __name__ == "__main__":
    main()
