from __future__ import annotations

import argparse
import gc
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
try:
    import psutil
except ImportError:
    psutil = None
from sklearn.covariance import LedoitWolf

THIS_DIR = Path(__file__).resolve().parent
REPO_DIR = THIS_DIR.parent
WORKTREE_ROOT = REPO_DIR.parent
for p in [THIS_DIR, REPO_DIR]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from paths import ARTIFACT_RUNS_DIR, TRACKED_RUNS_DIR

import KitNET as kit
import frontend100_latent_scorer_benchmark as lsb
import frontend100_negative_recipe_rescoring as resc
import frontend100_diagload_sweep_no_compact as dsw

FORMAL_SEEDS = [101, 202, 303]


def clean(obj):
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean(v) for v in obj]
    if isinstance(obj, tuple):
        return [clean(v) for v in obj]
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, np.ndarray):
        return [clean(v) for v in obj.tolist()]
    if isinstance(obj, np.generic):
        return clean(obj.item())
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


def load_json(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_workload(source_root: Path, id_n: int, ood_n: int, attack_n: int) -> Dict[str, np.ndarray]:
    data = source_root / "runs" / "frontend100_crosscapture_stage1_2026-03-25" / "data"
    attack_root = source_root / "runs" / "frontend100_joint_eval_stage1_2026-03-31" / "data"
    stage2_root = source_root / "runs" / "frontend100_joint_eval_stage2_2026-04-01" / "attack_manifest_stage2.json"
    x_all = pd.read_csv(data / "id_source_100.csv", header=None, nrows=8000 + id_n).to_numpy(np.float64)
    x_id = x_all[8000 : 8000 + id_n]
    x_ood_full = pd.read_csv(data / "ood_benign_source_100.csv", header=None).to_numpy(np.float64)
    x_ood = x_ood_full[5000 : 5000 + ood_n]
    x_attack_full = pd.read_csv(attack_root / "attack_source_100.csv", header=None).to_numpy(np.float64)
    stage2 = load_json(stage2_root)
    idx = resc.build_stage2_indices(stage2)
    high = idx["high"][:attack_n]
    x_attack = x_attack_full[high]
    x = np.concatenate([x_id, x_ood, x_attack], axis=0).astype(np.float64)
    return {
        "x": x,
        "id": x_id,
        "ood": x_ood,
        "attack": x_attack,
        "n_total": int(len(x)),
        "n_id": int(len(x_id)),
        "n_ood": int(len(x_ood)),
        "n_attack": int(len(x_attack)),
    }


def score_dA(model: kit.KitNET, x: np.ndarray) -> np.ndarray:
    out = np.zeros(len(x), dtype=np.float64)
    for i in range(len(x)):
        out[i] = model.executeAD(x[i])
    return out


def prepare_seed_gate(seed: int, batch_size: int) -> Dict:
    cache = ARTIFACT_RUNS_DIR / "frontend100_diagload_gate_multiseed_2026-04-08" / "cache_latents"
    prefix = cache / f"latent_swap_spike_mix_seed{seed}"
    h_fit = np.load(str(prefix) + "_h_fit.npy").astype(np.float64)
    h_id = np.load(str(prefix) + "_h_id.npy").astype(np.float64)
    lw = LedoitWolf().fit(h_fit)
    mu = lw.location_.astype(np.float64)
    sigma = lw.covariance_.astype(np.float64)
    raw_id, _ = dsw.cholesky_diagload_scores(h_id, mu, sigma, 0.0)
    diag_id, _ = dsw.cholesky_diagload_scores(h_id, mu, sigma, 0.5)
    raw_thr = float(np.quantile(raw_id, 0.999))
    diag_thr = float(np.quantile(diag_id, 0.99))
    ckpt = ARTIFACT_RUNS_DIR / "frontend100_locked_candidate_multiseed_2026-04-06" / f"latent_swap_spike_mix_seed{seed}" / f"kitnet_transformer_latent_contrastive_v1_seed{seed}.ckpt"
    model = kit.KitNET.load_checkpoint(ckpt)
    return {
        "seed": seed,
        "model": model,
        "mu": mu,
        "sigma": sigma,
        "raw_thr": raw_thr,
        "diag_thr": diag_thr,
        "batch_size": batch_size,
        "checkpoint": str(ckpt),
        "checkpoint_bytes": int(ckpt.stat().st_size),
    }


def score_seed_gate(prep: Dict, x: np.ndarray) -> np.ndarray:
    h, _ = lsb.extract_global_latent(prep["model"], x, prep["batch_size"], negative=False)
    raw, _ = dsw.cholesky_diagload_scores(h, prep["mu"], prep["sigma"], 0.0)
    diag, _ = dsw.cholesky_diagload_scores(h, prep["mu"], prep["sigma"], 0.5)
    return np.maximum(diag / prep["diag_thr"], raw / prep["raw_thr"])


def benchmark_callable(name: str, fn, repeats: int, warmup: int, n_samples: int) -> pd.DataFrame:
    proc = psutil.Process(os.getpid()) if psutil is not None else None
    rows = []
    for rep in range(warmup + repeats):
        gc.collect()
        rss_before = (proc.memory_info().rss / (1024 ** 2)) if proc is not None else float("nan")
        t0 = time.perf_counter()
        scores = fn()
        dt = time.perf_counter() - t0
        rss_after = (proc.memory_info().rss / (1024 ** 2)) if proc is not None else float("nan")
        if rep >= warmup:
            rows.append({
                "object_label": name,
                "repeat_idx": rep - warmup,
                "n_samples": int(n_samples),
                "elapsed_sec": float(dt),
                "ms_per_sample": float(dt * 1000.0 / max(n_samples, 1)),
                "samples_per_sec": float(n_samples / max(dt, 1e-12)),
                "rss_before_mb": float(rss_before),
                "rss_after_mb": float(rss_after),
                "rss_delta_mb": float(rss_after - rss_before),
                "score_mean": float(np.mean(scores)),
                "score_std": float(np.std(scores)),
            })
    return pd.DataFrame(rows)


def append_map(run_tag: str) -> None:
    p = TRACKED_RUNS_DIR / "mainline_docs" / "mainline_experiment_map.md"
    if not p.exists():
        return
    text = p.read_text(encoding="utf-8")
    if f"`{run_tag}`" in text:
        return
    text = text.rstrip() + f"\n- `{run_tag}`: Runtime/throughput benchmark for dA, single-seed Transformer latent gate, and 3-seed Transformer ensemble on the fixed stronger-OOD workload. Path: `runs/{run_tag}/`.\n"
    p.write_text(text, encoding="utf-8")


def update_log(run_tag: str, line: str) -> None:
    p = TRACKED_RUNS_DIR / "research_log" / "a_tier_experiment_progress_log.md"
    if not p.exists():
        return
    text = p.read_text(encoding="utf-8")
    marker = "### 5.24 Runtime And Cost Benchmark"
    block = f"""

{marker}

Run:
- `runs/{run_tag}/`

Purpose:
- Add real wall-clock evidence for the current final candidate package.
- Quantify the deployment cost gap between dA, single-seed Transformer latent gate, and the 3-seed covariance-aware Transformer ensemble.

Current result:
- {line}

Interpretation:
- Use this to support the cost/deployment section of the paper. The ensemble must be described as a higher-cost but higher-detection operating-region remedy, not a free win.
"""
    insert = "\n## 6. Current Candidate Ranking"
    if marker in text:
        head, tail = text.split(marker, 1)
        nxt = tail.find("\n### ", 5)
        text = head.rstrip() + "\n\n" + block.strip() + (tail[nxt:] if nxt >= 0 else "\n")
    elif insert in text:
        text = text.replace(insert, block + "\n" + insert)
    else:
        text = text.rstrip() + block
    p.write_text(text, encoding="utf-8")


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    ap = argparse.ArgumentParser(description="Runtime benchmark for final Transformer candidate vs dA.")
    ap.add_argument("--run-tag", default=f"frontend100_runtime_benchmark_{today}")
    ap.add_argument("--source-root", type=Path, default=WORKTREE_ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master")
    ap.add_argument("--id-n", type=int, default=3000)
    ap.add_argument("--ood-n", type=int, default=3000)
    ap.add_argument("--attack-n", type=int, default=3000)
    ap.add_argument("--batch-size", type=int, default=1024)
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--warmup", type=int, default=1)
    args = ap.parse_args()

    out = ARTIFACT_RUNS_DIR / args.run_tag
    out.mkdir(parents=True, exist_ok=True)
    plot_dir = out / "runtime_benchmark_plots"
    plot_dir.mkdir(exist_ok=True)
    (out / "command.txt").write_text("python " + " ".join(sys.argv) + "\n", encoding="utf-8")

    workload = build_workload(args.source_root, args.id_n, args.ood_n, args.attack_n)
    x = workload["x"]

    rows = []

    da_ckpt = WORKTREE_ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master" / "runs" / "frontend100_tailreg_bestcfg_stability_2026-03-28" / "da_seed101" / "kitnet_da_seed101.ckpt"
    da_model = kit.KitNET.load_checkpoint(da_ckpt)
    rows.append(benchmark_callable("dA_seed101_q99_runtime", lambda: score_dA(da_model, x), args.repeats, args.warmup, len(x)))

    seed101 = prepare_seed_gate(101, args.batch_size)
    gate_id_seed101 = score_seed_gate(seed101, workload["id"])
    gate_thr_seed101 = float(np.quantile(gate_id_seed101, 0.995))
    rows.append(benchmark_callable(
        "transformer_latent_seed101_gate_runtime",
        lambda: (score_seed_gate(seed101, x) > gate_thr_seed101).astype(np.float64),
        args.repeats,
        args.warmup,
        len(x),
    ))

    ensemble_preps = [prepare_seed_gate(seed, args.batch_size) for seed in FORMAL_SEEDS]
    ensemble_id_scores = [score_seed_gate(prep, workload["id"]) for prep in ensemble_preps]
    ensemble_thr = float(np.quantile(np.mean(np.stack(ensemble_id_scores, axis=0), axis=0), 0.995))

    def ensemble_fn():
        vals = [score_seed_gate(prep, x) for prep in ensemble_preps]
        score = np.mean(np.stack(vals, axis=0), axis=0)
        return (score > ensemble_thr).astype(np.float64)

    rows.append(benchmark_callable(
        "transformer_latent_ensemble3_gate_runtime",
        ensemble_fn,
        args.repeats,
        args.warmup,
        len(x),
    ))

    per = pd.concat(rows, ignore_index=True)
    agg = per.groupby("object_label", as_index=False).agg(
        n_samples=("n_samples", "first"),
        elapsed_sec_mean=("elapsed_sec", "mean"),
        elapsed_sec_std=("elapsed_sec", "std"),
        ms_per_sample_mean=("ms_per_sample", "mean"),
        ms_per_sample_std=("ms_per_sample", "std"),
        samples_per_sec_mean=("samples_per_sec", "mean"),
        samples_per_sec_std=("samples_per_sec", "std"),
        rss_before_mb_mean=("rss_before_mb", "mean"),
        rss_after_mb_mean=("rss_after_mb", "mean"),
        rss_delta_mb_mean=("rss_delta_mb", "mean"),
    )

    fixed_cost = pd.read_csv(ARTIFACT_RUNS_DIR / "frontend100_final_candidate_audit_2026-04-08" / "final_candidate_cost_table.csv")
    cost_map = {
        "dA_seed101_q99_runtime": fixed_cost[fixed_cost["object_label"].eq("dA single seed")].iloc[0],
        "transformer_latent_seed101_gate_runtime": fixed_cost[fixed_cost["object_label"].eq("Transformer latent single seed")].iloc[0],
        "transformer_latent_ensemble3_gate_runtime": fixed_cost[fixed_cost["object_label"].eq("Transformer latent 3-seed ensemble")].iloc[0],
    }
    agg["relative_forward_passes"] = agg["object_label"].map(lambda k: float(cost_map[k]["relative_forward_passes"]))
    agg["checkpoint_bytes"] = agg["object_label"].map(lambda k: int(cost_map[k]["checkpoint_bytes"]))
    agg["torch_param_count"] = agg["object_label"].map(lambda k: int(cost_map[k]["torch_param_count"]))
    agg["throughput_vs_dA"] = agg["samples_per_sec_mean"] / float(agg.loc[agg["object_label"].eq("dA_seed101_q99_runtime"), "samples_per_sec_mean"].iloc[0])
    agg["latency_vs_dA"] = agg["ms_per_sample_mean"] / float(agg.loc[agg["object_label"].eq("dA_seed101_q99_runtime"), "ms_per_sample_mean"].iloc[0])

    per.to_csv(out / "runtime_benchmark_per_repeat.csv", index=False)
    agg.to_csv(out / "runtime_benchmark_results.csv", index=False)
    agg.to_csv(out / "results.csv", index=False)

    fig, ax = plt.subplots(figsize=(9, 5.6))
    order = agg.sort_values("ms_per_sample_mean")
    ax.bar(order["object_label"], order["ms_per_sample_mean"], yerr=order["ms_per_sample_std"].fillna(0.0), capsize=3)
    ax.set_ylabel("ms per sample")
    ax.set_title("Runtime benchmark: latency")
    ax.grid(axis="y", alpha=0.25)
    plt.xticks(rotation=20, ha="right")
    fig.tight_layout()
    fig.savefig(plot_dir / "runtime_ms_per_sample.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5.6))
    order = agg.sort_values("samples_per_sec_mean", ascending=False)
    ax.bar(order["object_label"], order["samples_per_sec_mean"], yerr=order["samples_per_sec_std"].fillna(0.0), capsize=3)
    ax.set_ylabel("samples per second")
    ax.set_title("Runtime benchmark: throughput")
    ax.grid(axis="y", alpha=0.25)
    plt.xticks(rotation=20, ha="right")
    fig.tight_layout()
    fig.savefig(plot_dir / "runtime_samples_per_sec.png", dpi=180)
    plt.close(fig)

    best = agg.sort_values("samples_per_sec_mean", ascending=False)
    line = (
        f"dA latency={float(agg.loc[agg.object_label.eq('dA_seed101_q99_runtime'),'ms_per_sample_mean'].iloc[0]):.4f} ms/sample; "
        f"single-seed Transformer gate={float(agg.loc[agg.object_label.eq('transformer_latent_seed101_gate_runtime'),'ms_per_sample_mean'].iloc[0]):.4f}; "
        f"3-seed ensemble={float(agg.loc[agg.object_label.eq('transformer_latent_ensemble3_gate_runtime'),'ms_per_sample_mean'].iloc[0]):.4f}."
    )
    summary = "\n".join([
        "# Runtime Benchmark Summary",
        "",
        "- No new training. This benchmark only measures inference/runtime cost for the final candidate stack.",
        f"- Workload: {workload['n_total']} windows total ({workload['n_id']} ID eval + {workload['n_ood']} OOD eval + {workload['n_attack']} attack-high).",
        f"- Repeats: {args.repeats} after {args.warmup} warmup run(s).",
        f"- {line}",
        "",
        "## Aggregate",
        md_table(agg),
        "",
        "## Interpretation",
        "- Use this table in the deployment/cost section of the paper.",
        "- The main candidate must be described as a higher-cost covariance-aware ensemble remedy, not a free improvement.",
    ]) + "\n"
    (out / "runtime_benchmark_summary.md").write_text(summary, encoding="utf-8")
    (out / "summary.md").write_text(summary, encoding="utf-8")
    cfg = {
        "stage": "frontend100_runtime_benchmark",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_tag": args.run_tag,
        "workload": clean(workload),
        "repeats": int(args.repeats),
        "warmup": int(args.warmup),
        "batch_size": int(args.batch_size),
        "outputs": {
            "summary": str(out / "summary.md"),
            "per_repeat": str(out / "runtime_benchmark_per_repeat.csv"),
            "aggregate": str(out / "runtime_benchmark_results.csv"),
            "plots": str(plot_dir),
        },
    }
    (out / "runtime_benchmark_manifest.json").write_text(json.dumps(clean(cfg), indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "config.json").write_text(json.dumps(clean(cfg), indent=2, ensure_ascii=False), encoding="utf-8")
    append_map(args.run_tag)
    update_log(args.run_tag, line)
    print(f"[done] runtime benchmark output: {out}")


if __name__ == "__main__":
    main()


