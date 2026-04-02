from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def load_json(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_seed(name: str) -> int:
    idx = name.rfind("seed")
    if idx < 0:
        return -1
    return int(name[idx + 4 :])


def detect_backend(run_name: str) -> str:
    if run_name.startswith("transformer_"):
        return "transformer"
    if run_name.startswith("da_"):
        return "da"
    raise ValueError(f"unexpected run dir name: {run_name}")


def summarize_runs(root: Path) -> pd.DataFrame:
    rows: List[Dict] = []
    for run_dir in sorted(root.iterdir()):
        if not run_dir.is_dir():
            continue
        metrics_path = run_dir / "metrics.json"
        if not metrics_path.exists():
            continue
        metrics = load_json(metrics_path)
        detector = detect_backend(run_dir.name)
        seed = parse_seed(run_dir.name)
        id_stats = metrics["id"]["stats"]
        ood = metrics["ood_benign"]["iot23_ood_benign"]
        ood_stats = ood["stats"]
        rows.append(
            {
                "run_dir": str(run_dir),
                "detector": detector,
                "seed": int(seed),
                "id_mean": float(id_stats["mean"]),
                "id_std": float(id_stats["std"]),
                "id_q95": float(id_stats["q95"]),
                "id_q99": float(id_stats["q99"]),
                "ood_mean": float(ood_stats["mean"]),
                "ood_std": float(ood_stats["std"]),
                "ood_q95": float(ood_stats["q95"]),
                "ood_q99": float(ood_stats["q99"]),
                "ood_max": float(ood_stats["max"]),
                "ood_alarm_ratio": float(ood["alarm_ratio_at_id_q99_threshold"]),
            }
        )
    if not rows:
        raise RuntimeError(f"No run metrics found under {root}")
    return pd.DataFrame(rows).sort_values(["detector", "seed"]).reset_index(drop=True)


def markdown_table(df: pd.DataFrame) -> str:
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


def aggregate_stats(df: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        "ood_alarm_ratio",
        "id_q99",
        "ood_q99",
        "id_mean",
        "ood_mean",
        "id_std",
        "ood_std",
        "ood_max",
    ]
    rows: List[Dict] = []
    for det, g in df.groupby("detector"):
        for m in metrics:
            vals = g[m].to_numpy(dtype=np.float64)
            rows.append(
                {
                    "detector": det,
                    "metric": m,
                    "mean": float(np.mean(vals)),
                    "std": float(np.std(vals, ddof=0)),
                    "var": float(np.var(vals, ddof=0)),
                }
            )
    return pd.DataFrame(rows)


def plot_alarm_ratio_by_seed(df: pd.DataFrame, out_path: Path) -> None:
    seeds = sorted(df["seed"].unique())
    x = np.arange(len(seeds))
    width = 0.36
    plt.figure(figsize=(8, 4.5))
    for i, det in enumerate(["transformer", "da"]):
        g = df[df["detector"] == det].set_index("seed").reindex(seeds)
        shift = -width / 2 if det == "transformer" else width / 2
        plt.bar(x + shift, g["ood_alarm_ratio"], width=width, label=det)
    plt.xticks(x, [str(s) for s in seeds])
    plt.xlabel("seed")
    plt.ylabel("OOD benign alarm ratio @ ID q99")
    plt.title("Frontend100 Stability: Alarm Ratio by Seed")
    plt.ylim(0, max(0.02, df["ood_alarm_ratio"].max() * 1.4))
    plt.grid(axis="y", alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=160)
    plt.close()


def plot_q99_by_seed(df: pd.DataFrame, out_path: Path) -> None:
    seeds = sorted(df["seed"].unique())
    plt.figure(figsize=(8, 4.5))
    for det, marker in [("transformer", "o"), ("da", "s")]:
        g = df[df["detector"] == det].set_index("seed").reindex(seeds)
        plt.plot(seeds, g["id_q99"], marker=marker, label=f"{det}-id_q99")
        plt.plot(seeds, g["ood_q99"], marker=marker, linestyle="--", label=f"{det}-ood_q99")
    plt.xlabel("seed")
    plt.ylabel("score q99")
    plt.title("Frontend100 Stability: ID q99 vs OOD q99")
    plt.grid(alpha=0.25)
    plt.legend(ncol=2, fontsize=9)
    plt.tight_layout()
    plt.savefig(out_path, dpi=160)
    plt.close()


def plot_boxplot(df: pd.DataFrame, out_path: Path) -> None:
    eps = 1e-12
    box_data = []
    labels = []
    for det in ["transformer", "da"]:
        run_dirs = [Path(p) for p in df[df["detector"] == det]["run_dir"].tolist()]
        id_scores = np.concatenate([np.load(r / "id_scores.npy") for r in run_dirs])
        ood_scores = np.concatenate([np.load(r / "iot23_ood_benign_scores.npy") for r in run_dirs])
        box_data.append(np.log10(id_scores + eps))
        labels.append(f"{det}-ID")
        box_data.append(np.log10(ood_scores + eps))
        labels.append(f"{det}-OOD")
    plt.figure(figsize=(9, 4.8))
    plt.boxplot(box_data, tick_labels=labels, showfliers=False)
    plt.ylabel("log10(score)")
    plt.title("Frontend100 Stability: ID vs OOD benign")
    plt.grid(axis="y", alpha=0.25)
    plt.tight_layout()
    plt.savefig(out_path, dpi=160)
    plt.close()


def mean_std_line(agg: pd.DataFrame, det: str, metric: str) -> str:
    row = agg[(agg["detector"] == det) & (agg["metric"] == metric)].iloc[0]
    return f"{row['mean']:.6f} +- {row['std']:.6f}"


def build_summary(root: Path, per_seed: pd.DataFrame, agg: pd.DataFrame) -> None:
    lines: List[str] = []
    lines.append("# Frontend100 OOD Stability Summary")
    lines.append("")
    lines.append("## Fixed protocol and variables")
    lines.append("- Fixed: ID/OOD source files, packet slices, 100-D features, train/eval sizes, threshold protocol (ID q99).")
    lines.append("- Variables only: `seed in {101,202,303}` and `detector_backend in {transformer, da}`.")
    lines.append("")
    lines.append("## Per-seed results")
    show_cols = [
        "detector",
        "seed",
        "id_mean",
        "id_std",
        "id_q95",
        "id_q99",
        "ood_mean",
        "ood_std",
        "ood_q95",
        "ood_q99",
        "ood_max",
        "ood_alarm_ratio",
    ]
    lines.append(markdown_table(per_seed[show_cols]))
    lines.append("")
    lines.append("## Aggregate mean/std/var")
    lines.append(markdown_table(agg[["detector", "metric", "mean", "std", "var"]]))
    lines.append("")
    lines.append("## Key aggregate stats")
    lines.append(
        f"- Transformer OOD alarm ratio: {mean_std_line(agg, 'transformer', 'ood_alarm_ratio')}"
    )
    lines.append(f"- dA OOD alarm ratio: {mean_std_line(agg, 'da', 'ood_alarm_ratio')}")
    lines.append(f"- Transformer ID q99: {mean_std_line(agg, 'transformer', 'id_q99')}")
    lines.append(f"- dA ID q99: {mean_std_line(agg, 'da', 'id_q99')}")
    lines.append(f"- Transformer OOD q99: {mean_std_line(agg, 'transformer', 'ood_q99')}")
    lines.append(f"- dA OOD q99: {mean_std_line(agg, 'da', 'ood_q99')}")
    lines.append("")
    lines.append("## Interpretation")
    lines.append("- OOD benign alarm ratios stay low across seeds for both detectors (no adapter-style explosion).")
    lines.append("- Transformer and dA are both stable under this fallback protocol; transformer is slightly lower in OOD alarm ratio.")
    lines.append("- OOD mean/std are dominated by rare extreme spikes (large max), so use q95/q99 + alarm ratio as primary indicators.")
    lines.append("- Relative to adapter-chain conclusions, this cleaner 100-D chain supports a milder open-world instability statement.")
    lines.append("")
    lines.append("## Outputs")
    lines.append("- per_seed_results.csv / per_seed_results.md")
    lines.append("- aggregate_mean_var.csv / aggregate_mean_var.md")
    lines.append("- plots/alarm_ratio_by_seed.png")
    lines.append("- plots/q99_by_seed.png")
    lines.append("- plots/id_vs_ood_boxplot.png")
    (root / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate frontend100 OOD stability runs.")
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()

    root = args.root
    root.mkdir(parents=True, exist_ok=True)
    plot_dir = root / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)

    per_seed = summarize_runs(root)
    agg = aggregate_stats(per_seed)

    per_seed.to_csv(root / "per_seed_results.csv", index=False)
    agg.to_csv(root / "aggregate_mean_var.csv", index=False)
    (root / "per_seed_results.md").write_text(
        markdown_table(
            per_seed[
                [
                    "detector",
                    "seed",
                    "id_mean",
                    "id_std",
                    "id_q95",
                    "id_q99",
                    "ood_mean",
                    "ood_std",
                    "ood_q95",
                    "ood_q99",
                    "ood_max",
                    "ood_alarm_ratio",
                ]
            ]
        ),
        encoding="utf-8",
    )
    (root / "aggregate_mean_var.md").write_text(
        markdown_table(agg[["detector", "metric", "mean", "std", "var"]]),
        encoding="utf-8",
    )

    plot_alarm_ratio_by_seed(per_seed, plot_dir / "alarm_ratio_by_seed.png")
    plot_q99_by_seed(per_seed, plot_dir / "q99_by_seed.png")
    plot_boxplot(per_seed, plot_dir / "id_vs_ood_boxplot.png")
    build_summary(root, per_seed, agg)
    print(f"[done] frontend100 stability summary: {root / 'summary.md'}")


if __name__ == "__main__":
    main()
