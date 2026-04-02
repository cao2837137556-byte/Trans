from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = REPO_DIR.parent

TAILREG_NAME_RE = re.compile(r"^tailreg_l(?P<lam>\d+(?:\.\d+)?)_k(?P<k>\d+(?:\.\d+)?)_seed(?P<seed>\d+)$")


def score_stats(x: np.ndarray) -> Dict[str, float]:
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
        vals: List[str] = []
        for c in cols:
            v = row[c]
            if isinstance(v, float):
                vals.append(f"{v:.6f}")
            else:
                vals.append(str(v))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"


def parse_tailreg_name(name: str) -> Optional[Tuple[float, float, int]]:
    m = TAILREG_NAME_RE.match(name)
    if not m:
        return None
    return float(m.group("lam")), float(m.group("k")), int(m.group("seed"))


def load_run_metrics(
    run_dir: Path,
    detector_name: str,
    calibration_budget: int,
    target_alarm_rate: float,
    lam: Optional[float] = None,
    k: Optional[float] = None,
) -> Dict[str, object]:
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    ood_name = list(metrics["ood_benign"].keys())[0]
    id_scores = np.load(run_dir / "id_scores.npy").astype(np.float64)
    ood_scores = np.load(run_dir / f"{ood_name}_scores.npy").astype(np.float64)

    fixed_threshold = float(metrics["threshold_value"])
    fixed_alarm = float(np.mean(ood_scores > fixed_threshold))

    budget = int(min(max(1, calibration_budget), len(ood_scores) - 1))
    ood_cal = ood_scores[:budget]
    ood_eval = ood_scores[budget:]
    calibrated_threshold = float(np.quantile(ood_cal, 1.0 - target_alarm_rate))
    calibrated_alarm = float(np.mean(ood_eval > calibrated_threshold))

    id_st = score_stats(id_scores)
    ood_st = score_stats(ood_scores)
    ood_eval_st = score_stats(ood_eval)
    return {
        "detector": detector_name,
        "seed": int(metrics.get("config", {}).get("seed", 42)),
        "tailreg_lambda": lam,
        "tailreg_k": k,
        "fixed_threshold": fixed_threshold,
        "fixed_ood_alarm_ratio": fixed_alarm,
        "calibrated_threshold": calibrated_threshold,
        "calibrated_ood_alarm_ratio": calibrated_alarm,
        "calibration_budget": budget,
        "target_alarm_rate": target_alarm_rate,
        "id_mean": id_st["mean"],
        "id_std": id_st["std"],
        "id_q95": id_st["q95"],
        "id_q99": id_st["q99"],
        "ood_mean": ood_st["mean"],
        "ood_std": ood_st["std"],
        "ood_q95": ood_st["q95"],
        "ood_q99": ood_st["q99"],
        "ood_eval_mean": ood_eval_st["mean"],
        "ood_eval_std": ood_eval_st["std"],
        "ood_eval_q95": ood_eval_st["q95"],
        "ood_eval_q99": ood_eval_st["q99"],
        "run_dir": str(run_dir),
    }


def plot_heatmap(df: pd.DataFrame, value_col: str, out_path: Path, title: str) -> None:
    piv = df.pivot(index="tailreg_lambda", columns="tailreg_k", values=value_col).sort_index().sort_index(axis=1)
    arr = piv.to_numpy(dtype=np.float64)
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    im = ax.imshow(arr, cmap="viridis")
    ax.set_xticks(np.arange(len(piv.columns)))
    ax.set_xticklabels([str(v) for v in piv.columns])
    ax.set_yticks(np.arange(len(piv.index)))
    ax.set_yticklabels([str(v) for v in piv.index])
    ax.set_xlabel("tailreg_k")
    ax.set_ylabel("tailreg_lambda")
    ax.set_title(title)
    for i in range(arr.shape[0]):
        for j in range(arr.shape[1]):
            ax.text(j, i, f"{arr[i, j]:.3f}", ha="center", va="center", color="white", fontsize=9)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def plot_detector_compare(compare_df: pd.DataFrame, out_path: Path) -> None:
    order = ["transformer", "transformer_tailreg_best", "da"]
    sub = compare_df.set_index("detector").reindex(order)
    x = np.arange(len(order))
    width = 0.35
    plt.figure(figsize=(7.5, 4.5))
    plt.bar(x - width / 2, sub["fixed_ood_alarm_ratio"], width=width, label="fixed")
    plt.bar(x + width / 2, sub["calibrated_ood_alarm_ratio"], width=width, label="calibrated")
    plt.xticks(x, order)
    plt.ylabel("OOD benign alarm ratio")
    plt.title("Best TailReg vs transformer/da")
    plt.grid(axis="y", alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=160)
    plt.close()


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(description="Build report for small TailReg hyper-parameter scan.")
    parser.add_argument("--run-tag", default=f"frontend100_tailreg_hparam_scan_{today}")
    parser.add_argument("--baseline-run", default="runs/frontend100_tailreg_stage1_2026-03-27/transformer_seed42")
    parser.add_argument("--da-run", default="runs/frontend100_tailreg_stage1_2026-03-27/da_seed42")
    parser.add_argument("--calibration-budget", type=int, default=5000)
    parser.add_argument("--target-alarm-rate", type=float, default=0.01)
    args = parser.parse_args()

    run_root = ROOT_DIR / "runs" / args.run_tag
    plot_dir = run_root / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, object]] = []
    for child in sorted(run_root.iterdir()):
        if not child.is_dir():
            continue
        parsed = parse_tailreg_name(child.name)
        if parsed is None:
            continue
        lam, k, _seed = parsed
        rows.append(
            load_run_metrics(
                child,
                detector_name="transformer_tailreg",
                calibration_budget=args.calibration_budget,
                target_alarm_rate=args.target_alarm_rate,
                lam=lam,
                k=k,
            )
        )

    if not rows:
        raise RuntimeError(f"No tailreg run dirs found under {run_root}")

    per_cfg = pd.DataFrame(rows).sort_values(["tailreg_lambda", "tailreg_k"]).reset_index(drop=True)
    per_cfg.to_csv(run_root / "per_config_results.csv", index=False)
    (run_root / "per_config_results.md").write_text(md_table(per_cfg), encoding="utf-8")

    best_fixed = per_cfg.sort_values("fixed_ood_alarm_ratio").iloc[0]
    best_cal = per_cfg.sort_values("calibrated_ood_alarm_ratio").iloc[0]

    baseline = load_run_metrics(
        ROOT_DIR / args.baseline_run,
        detector_name="transformer",
        calibration_budget=args.calibration_budget,
        target_alarm_rate=args.target_alarm_rate,
    )
    da = load_run_metrics(
        ROOT_DIR / args.da_run,
        detector_name="da",
        calibration_budget=args.calibration_budget,
        target_alarm_rate=args.target_alarm_rate,
    )
    best_tail = dict(best_fixed)
    best_tail["detector"] = "transformer_tailreg_best"
    compare_df = pd.DataFrame([baseline, best_tail, da])[
        [
            "detector",
            "tailreg_lambda",
            "tailreg_k",
            "fixed_threshold",
            "fixed_ood_alarm_ratio",
            "calibrated_threshold",
            "calibrated_ood_alarm_ratio",
            "id_q99",
            "ood_q99",
        ]
    ]
    compare_df.to_csv(run_root / "detector_compare_fixed_vs_calibrated.csv", index=False)
    (run_root / "detector_compare_fixed_vs_calibrated.md").write_text(md_table(compare_df), encoding="utf-8")

    plot_heatmap(
        per_cfg,
        "fixed_ood_alarm_ratio",
        plot_dir / "tailreg_fixed_alarm_heatmap.png",
        "TailReg fixed-threshold OOD alarm",
    )
    plot_heatmap(
        per_cfg,
        "calibrated_ood_alarm_ratio",
        plot_dir / "tailreg_calibrated_alarm_heatmap.png",
        "TailReg calibrated OOD alarm",
    )
    plot_detector_compare(compare_df, plot_dir / "detector_compare_fixed_vs_calibrated.png")

    lines: List[str] = []
    lines.append("# Frontend100 TailReg Hyper-Parameter Scan Summary")
    lines.append("")
    lines.append("## Fixed protocol")
    lines.append("- ID: CTU-Honeypot-Capture-7-6")
    lines.append("- OOD benign: CTU-Honeypot-Capture-4-1")
    lines.append("- original-frontend 100-D, train_samples=8000, id_eval_samples=5000, fm=2000, ad=6000, seed=42")
    lines.append("- TailReg scan grid: lambda in {0.1, 0.2}, k in {1.0, 1.5}; warmup=256, ema_alpha=0.01")
    lines.append(f"- Calibration eval: budget={args.calibration_budget}, target_alarm_rate={args.target_alarm_rate:.4f}")
    lines.append("")
    lines.append("## Best configs")
    lines.append(
        f"- Best fixed alarm: lambda={best_fixed['tailreg_lambda']}, k={best_fixed['tailreg_k']}, "
        f"fixed_ood_alarm={best_fixed['fixed_ood_alarm_ratio']:.4f}"
    )
    lines.append(
        f"- Best calibrated alarm: lambda={best_cal['tailreg_lambda']}, k={best_cal['tailreg_k']}, "
        f"calibrated_ood_alarm={best_cal['calibrated_ood_alarm_ratio']:.4f}"
    )
    lines.append("")
    lines.append("## Baseline comparison (seed=42)")
    lines.append(
        f"- transformer fixed/calibrated: {baseline['fixed_ood_alarm_ratio']:.4f} / "
        f"{baseline['calibrated_ood_alarm_ratio']:.4f}"
    )
    lines.append(
        f"- best tailreg fixed/calibrated: {best_tail['fixed_ood_alarm_ratio']:.4f} / "
        f"{best_tail['calibrated_ood_alarm_ratio']:.4f}"
    )
    lines.append(
        f"- da fixed/calibrated: {da['fixed_ood_alarm_ratio']:.4f} / "
        f"{da['calibrated_ood_alarm_ratio']:.4f}"
    )
    lines.append("")
    lines.append("## Recommendation")
    lines.append("- Use the best fixed-threshold config for next multi-seed stability check.")
    (run_root / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    scan_config = {
        "run_tag": args.run_tag,
        "baseline_run": args.baseline_run,
        "da_run": args.da_run,
        "calibration_budget": args.calibration_budget,
        "target_alarm_rate": args.target_alarm_rate,
        "best_fixed": {
            "tailreg_lambda": float(best_fixed["tailreg_lambda"]),
            "tailreg_k": float(best_fixed["tailreg_k"]),
            "fixed_ood_alarm_ratio": float(best_fixed["fixed_ood_alarm_ratio"]),
        },
        "best_calibrated": {
            "tailreg_lambda": float(best_cal["tailreg_lambda"]),
            "tailreg_k": float(best_cal["tailreg_k"]),
            "calibrated_ood_alarm_ratio": float(best_cal["calibrated_ood_alarm_ratio"]),
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    (run_root / "scan_report_config.json").write_text(json.dumps(scan_config, indent=2), encoding="utf-8")
    print(f"[done] report generated under: {run_root}")


if __name__ == "__main__":
    main()
