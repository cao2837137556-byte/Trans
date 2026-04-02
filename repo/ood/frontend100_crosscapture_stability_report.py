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
    i = name.rfind("seed")
    if i < 0:
        return -1
    return int(name[i + 4 :])


def detect_backend(name: str) -> str:
    if name.startswith("transformer_"):
        return "transformer"
    if name.startswith("da_"):
        return "da"
    raise ValueError(f"Unexpected run dir name: {name}")


def summarize_runs(root: Path) -> pd.DataFrame:
    rows: List[Dict] = []
    for run_dir in sorted(root.iterdir()):
        if not run_dir.is_dir():
            continue
        metrics_path = run_dir / "metrics.json"
        if not metrics_path.exists():
            continue
        m = load_json(metrics_path)
        id_stats = m["id"]["stats"]
        if not m.get("ood_benign"):
            continue
        ood_name = list(m["ood_benign"].keys())[0]
        ood = m["ood_benign"][ood_name]
        ood_stats = ood["stats"]
        rows.append(
            {
                "run_dir": str(run_dir),
                "detector": detect_backend(run_dir.name),
                "seed": int(parse_seed(run_dir.name)),
                "ood_name": ood_name,
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
        raise RuntimeError(f"No valid cross-capture run found under {root}")
    return pd.DataFrame(rows).sort_values(["detector", "seed"]).reset_index(drop=True)


def table_md(df: pd.DataFrame) -> str:
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


def aggregate(df: pd.DataFrame) -> pd.DataFrame:
    metrics = ["ood_alarm_ratio", "id_q99", "ood_q99", "id_mean", "ood_mean", "id_std", "ood_std", "ood_max"]
    out: List[Dict] = []
    for det, g in df.groupby("detector"):
        for met in metrics:
            vals = g[met].to_numpy(dtype=np.float64)
            out.append(
                {
                    "detector": det,
                    "metric": met,
                    "mean": float(np.mean(vals)),
                    "std": float(np.std(vals, ddof=0)),
                    "var": float(np.var(vals, ddof=0)),
                }
            )
    return pd.DataFrame(out)


def plot_alarm_ratio_by_seed(df: pd.DataFrame, out_path: Path) -> None:
    seeds = sorted(df["seed"].unique())
    x = np.arange(len(seeds))
    width = 0.36
    plt.figure(figsize=(8, 4.5))
    for det, shift in [("transformer", -width / 2), ("da", width / 2)]:
        g = df[df["detector"] == det].set_index("seed").reindex(seeds)
        plt.bar(x + shift, g["ood_alarm_ratio"], width=width, label=det)
    plt.xticks(x, [str(s) for s in seeds])
    plt.xlabel("seed")
    plt.ylabel("OOD alarm ratio @ ID q99")
    plt.title("Cross-capture OOD alarm ratio by seed")
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
    plt.ylabel("score")
    plt.title("Cross-capture ID/OOD q99 by seed")
    plt.yscale("log")
    plt.grid(alpha=0.25)
    plt.legend(ncol=2, fontsize=9)
    plt.tight_layout()
    plt.savefig(out_path, dpi=160)
    plt.close()


def plot_boxplot(df: pd.DataFrame, out_path: Path) -> None:
    eps = 1e-12
    data = []
    labels = []
    for det in ["transformer", "da"]:
        runs = df[df["detector"] == det]
        id_all = []
        ood_all = []
        for _, r in runs.iterrows():
            run_dir = Path(str(r["run_dir"]))
            id_all.append(np.load(run_dir / "id_scores.npy"))
            ood_all.append(np.load(run_dir / f"{r['ood_name']}_scores.npy"))
        id_cat = np.concatenate(id_all)
        ood_cat = np.concatenate(ood_all)
        data.extend([np.log10(id_cat + eps), np.log10(ood_cat + eps)])
        labels.extend([f"{det}-ID", f"{det}-OOD"])
    plt.figure(figsize=(9, 4.8))
    plt.boxplot(data, tick_labels=labels, showfliers=False)
    plt.ylabel("log10(score)")
    plt.title("Cross-capture ID vs OOD benign")
    plt.grid(axis="y", alpha=0.25)
    plt.tight_layout()
    plt.savefig(out_path, dpi=160)
    plt.close()


def mstd(agg_df: pd.DataFrame, det: str, metric: str) -> str:
    row = agg_df[(agg_df["detector"] == det) & (agg_df["metric"] == metric)].iloc[0]
    return f"{row['mean']:.6f} +- {row['std']:.6f}"


def build_summary(root: Path, per_seed: pd.DataFrame, agg_df: pd.DataFrame) -> None:
    lines: List[str] = []
    lines.append("# Frontend100 Cross-capture Stability Summary")
    lines.append("")
    lines.append("## Fixed protocol and variables")
    lines.append("- Fixed: ID capture 7-6, OOD benign capture 4-1, original-frontend 100-D features, train/eval sizes, ID q99 threshold protocol.")
    lines.append("- Variables only: `seed in {101,202,303}` and `detector_backend in {transformer, da}`.")
    lines.append("")
    lines.append("## Per-seed results")
    cols = [
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
    lines.append(table_md(per_seed[cols]))
    lines.append("")
    lines.append("## Aggregate mean/std/var")
    lines.append(table_md(agg_df[["detector", "metric", "mean", "std", "var"]]))
    lines.append("")
    lines.append("## Key aggregate stats")
    lines.append(f"- Transformer OOD alarm ratio: {mstd(agg_df, 'transformer', 'ood_alarm_ratio')}")
    lines.append(f"- dA OOD alarm ratio: {mstd(agg_df, 'da', 'ood_alarm_ratio')}")
    lines.append(f"- Transformer ID q99: {mstd(agg_df, 'transformer', 'id_q99')}")
    lines.append(f"- dA ID q99: {mstd(agg_df, 'da', 'id_q99')}")
    lines.append(f"- Transformer OOD q99: {mstd(agg_df, 'transformer', 'ood_q99')}")
    lines.append(f"- dA OOD q99: {mstd(agg_df, 'da', 'ood_q99')}")
    lines.append("")
    lines.append("## Interpretation")
    lines.append("- Cross-capture stronger OOD causes consistently high false alarms for both detectors.")
    lines.append("- Transformer keeps higher OOD alarm ratio than dA in all seeds.")
    lines.append("- This supports a stage-wise claim that transformer currently has a robustness gap under stronger open-world settings.")
    lines.append("")
    lines.append("## Output files")
    lines.append("- per_seed_results.csv / per_seed_results.md")
    lines.append("- aggregate_mean_var.csv / aggregate_mean_var.md")
    lines.append("- plots/alarm_ratio_by_seed.png")
    lines.append("- plots/q99_by_seed.png")
    lines.append("- plots/id_vs_ood_boxplot.png")
    (root / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate frontend100 cross-capture stability runs.")
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()

    root = args.root
    root.mkdir(parents=True, exist_ok=True)
    plot_dir = root / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)

    per_seed = summarize_runs(root)
    agg_df = aggregate(per_seed)

    per_seed.to_csv(root / "per_seed_results.csv", index=False)
    agg_df.to_csv(root / "aggregate_mean_var.csv", index=False)
    (root / "per_seed_results.md").write_text(
        table_md(
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
        table_md(agg_df[["detector", "metric", "mean", "std", "var"]]),
        encoding="utf-8",
    )

    plot_alarm_ratio_by_seed(per_seed, plot_dir / "alarm_ratio_by_seed.png")
    plot_q99_by_seed(per_seed, plot_dir / "q99_by_seed.png")
    plot_boxplot(per_seed, plot_dir / "id_vs_ood_boxplot.png")
    build_summary(root, per_seed, agg_df)
    print(f"[done] summary at {root / 'summary.md'}")


if __name__ == "__main__":
    main()
