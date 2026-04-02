from __future__ import annotations

import argparse
import json
import os
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch

REPO_DIR = Path(__file__).resolve().parents[1]
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

import KitNET as kit
from csv_input import load_numeric_csv
from paths import ROOT_DIR


def score_stats(scores: np.ndarray) -> Dict[str, float]:
    q = np.quantile(scores, [0.5, 0.9, 0.95, 0.99])
    return {
        "n": int(len(scores)),
        "mean": float(np.mean(scores)),
        "std": float(np.std(scores)),
        "var": float(np.var(scores)),
        "min": float(np.min(scores)),
        "q50": float(q[0]),
        "q90": float(q[1]),
        "q95": float(q[2]),
        "q99": float(q[3]),
        "max": float(np.max(scores)),
    }


def score_dataset(model: kit.KitNET, x: np.ndarray) -> np.ndarray:
    scores = np.zeros(len(x), dtype=np.float64)
    for i in range(len(x)):
        if i > 0 and i % 2000 == 0:
            print(f"  scoring progress: {i}/{len(x)}")
        scores[i] = model.process(x[i])
    return scores


def maybe_load_labels(path: Optional[Path], expected_len: int) -> Optional[np.ndarray]:
    if path is None or not path.exists():
        return None
    y = np.load(path)
    if len(y) != expected_len:
        return None
    return y.astype(np.int64)


def compute_auc(y_true: np.ndarray, y_score: np.ndarray) -> Optional[Dict[str, float]]:
    if y_true is None or len(np.unique(y_true)) < 2:
        return None
    try:
        from sklearn.metrics import average_precision_score, roc_auc_score
    except Exception:
        return None
    return {
        "roc_auc": float(roc_auc_score(y_true, y_score)),
        "pr_auc": float(average_precision_score(y_true, y_score)),
    }


def parse_dataset_arg(spec: str) -> Tuple[str, Path, Optional[Path]]:
    parts = spec.split("|")
    if len(parts) < 2:
        raise ValueError(f"Invalid dataset spec: {spec}")
    name = parts[0]
    csv_path = Path(parts[1])
    label_path = Path(parts[2]) if len(parts) > 2 and parts[2] else None
    return name, csv_path, label_path


def default_dataset_specs() -> Tuple[List[str], List[str]]:
    adapted = ROOT_DIR / "runs" / "ood_probe_2026-03-21" / "adapted"
    benign_specs = [
        f"iot23_benign|{adapted / 'iot23_benign_116.csv'}|{adapted / 'iot23_benign_labels.npy'}",
        f"ciciot2023_benign|{adapted / 'ciciot2023_benign_116.csv'}|{adapted / 'ciciot2023_benign_labels.npy'}",
    ]
    attack_specs = [
        f"iot23_mirai_attack|{adapted / 'iot23_mirai_malicious_116.csv'}|{adapted / 'iot23_mirai_malicious_labels.npy'}",
        f"ciciot2023_attack|{adapted / 'ciciot2023_attack_116.csv'}|{adapted / 'ciciot2023_attack_labels.npy'}",
    ]
    return benign_specs, attack_specs


def set_global_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(description="Stage-1 OOD probe with checkpoint persistence.")
    parser.add_argument("--run-tag", default=f"ood_probe_stage1_{today}")
    parser.add_argument("--train-csv", type=Path, default=ROOT_DIR / "my_gold_mirai.csv")
    parser.add_argument("--train-labels", type=Path, default=ROOT_DIR / "my_gold_labels.npy")
    parser.add_argument("--max-ae", type=int, default=10)
    parser.add_argument("--fm-grace", type=int, default=5000)
    parser.add_argument("--ad-grace", type=int, default=15000)
    parser.add_argument("--train-samples", type=int, default=20000)
    parser.add_argument("--id-eval-samples", type=int, default=20000)
    parser.add_argument("--learning-rate", type=float, default=0.1)
    parser.add_argument("--hidden-ratio", type=float, default=0.75)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--detector-backend",
        choices=["transformer", "transformer_tailreg", "da"],
        default="transformer",
    )
    parser.add_argument("--tailreg-lambda", type=float, default=0.1)
    parser.add_argument("--tailreg-k", type=float, default=2.0)
    parser.add_argument("--tailreg-warmup", type=int, default=512)
    parser.add_argument("--tailreg-ema-alpha", type=float, default=0.01)
    parser.add_argument("--threshold-quantile", type=float, default=0.99)
    parser.add_argument("--force-retrain", action="store_true")
    parser.add_argument("--skip-benign", action="store_true")
    parser.add_argument("--checkpoint", type=Path, default=None)
    parser.add_argument("--no-auto-drop-index-col0", action="store_true")
    parser.add_argument("--benign-dataset", action="append", default=None, help="name|csv|labels.npy")
    parser.add_argument("--attack-dataset", action="append", default=None, help="name|csv|labels.npy")
    parser.add_argument("--skip-attack", action="store_true")
    args = parser.parse_args()

    run_dir = ROOT_DIR / "runs" / args.run_tag
    run_dir.mkdir(parents=True, exist_ok=True)
    plot_dir = run_dir / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)

    ckpt_path = args.checkpoint or (run_dir / f"kitnet_{args.detector_backend}_seed{args.seed}.ckpt")
    command_line = "python " + " ".join(sys.argv)
    (run_dir / "command.txt").write_text(command_line + "\n", encoding="utf-8")
    set_global_seed(args.seed)

    total_needed = args.train_samples + args.id_eval_samples
    x_all, train_load_info = load_numeric_csv(
        args.train_csv,
        nrows=total_needed,
        auto_drop_index_col0=not args.no_auto_drop_index_col0,
    )
    if len(x_all) < args.train_samples:
        raise RuntimeError("Not enough rows in train CSV for requested train_samples.")
    print(
        f"Loaded train CSV: {args.train_csv} shape={x_all.shape} "
        f"raw_dim={train_load_info['raw_dim']} used_dim={train_load_info['used_dim']} "
        f"dropped_col0={train_load_info['dropped_col0']}"
    )

    y_all = None
    if args.train_labels.exists():
        y_tmp = np.load(args.train_labels)
        y_all = y_tmp[: len(x_all)].astype(np.int64)
        print(f"Loaded train labels: {args.train_labels} shape={y_all.shape}")

    if args.train_samples < args.fm_grace + args.ad_grace:
        raise RuntimeError("train_samples must be >= fm_grace + ad_grace.")

    if ckpt_path.exists() and not args.force_retrain:
        print(f"Loading checkpoint: {ckpt_path}")
        model = kit.KitNET.load_checkpoint(ckpt_path)
        train_runtime_s = None
    else:
        print("Training new model...")
        model = kit.KitNET(
            n=x_all.shape[1],
            max_autoencoder_size=args.max_ae,
            FM_grace_period=args.fm_grace,
            AD_grace_period=args.ad_grace,
            learning_rate=args.learning_rate,
            hidden_ratio=args.hidden_ratio,
            detector_backend=args.detector_backend,
            detector_seed=args.seed,
            tailreg_lambda=args.tailreg_lambda,
            tailreg_k=args.tailreg_k,
            tailreg_warmup=args.tailreg_warmup,
            tailreg_ema_alpha=args.tailreg_ema_alpha,
        )
        t0 = datetime.now()
        for i in range(args.train_samples):
            if i > 0 and i % 2000 == 0:
                print(f"  train progress: {i}/{args.train_samples}")
            model.process(x_all[i])
        train_runtime_s = (datetime.now() - t0).total_seconds()
        model.save_checkpoint(ckpt_path)
        print(f"Saved checkpoint: {ckpt_path}")

    # Reload once to verify load-path integrity.
    model = kit.KitNET.load_checkpoint(ckpt_path)
    print("Checkpoint reload verification passed.")

    id_start = args.train_samples
    id_end = min(len(x_all), id_start + args.id_eval_samples)
    x_id = x_all[id_start:id_end]
    id_scores = score_dataset(model, x_id)
    np.save(run_dir / "id_scores.npy", id_scores)

    id_labels = None
    if y_all is not None:
        id_labels = y_all[id_start:id_end]

    id_stats = score_stats(id_scores)
    id_metrics = compute_auc(id_labels, id_scores) if id_labels is not None else None

    if id_labels is not None and np.any(id_labels == 0):
        id_benign_scores = id_scores[id_labels == 0]
    else:
        id_benign_scores = id_scores
    threshold = float(np.quantile(id_benign_scores, args.threshold_quantile))

    default_benign, default_attack = default_dataset_specs()
    if args.skip_benign:
        benign_specs = []
    else:
        benign_specs = args.benign_dataset if args.benign_dataset is not None else default_benign
    if args.skip_attack:
        attack_specs = []
    else:
        attack_specs = args.attack_dataset if args.attack_dataset is not None else default_attack

    benign_results = {}
    attack_results = {}
    ood_all_scores = []
    ood_all_labels = []

    for spec in benign_specs:
        name, csv_path, label_path = parse_dataset_arg(spec)
        x, load_info = load_numeric_csv(
            csv_path,
            auto_drop_index_col0=not args.no_auto_drop_index_col0,
        )
        if x.shape[1] != x_all.shape[1]:
            raise RuntimeError(
                f"{name} dim mismatch: {x.shape[1]} != {x_all.shape[1]} "
                f"(raw_dim={load_info['raw_dim']} dropped_col0={load_info['dropped_col0']})"
            )
        scores = score_dataset(model, x)
        np.save(run_dir / f"{name}_scores.npy", scores)
        labels = maybe_load_labels(label_path, len(scores))
        stats = score_stats(scores)
        alarm_ratio = float(np.mean(scores > threshold))
        auc = compute_auc(labels, scores) if labels is not None else None
        benign_results[name] = {
            "csv": str(csv_path),
            "labels": None if label_path is None else str(label_path),
            "load_info": load_info,
            "stats": stats,
            "alarm_ratio_at_id_q99_threshold": alarm_ratio,
            "metrics": auc,
        }
        ood_all_scores.append(scores)
        if labels is not None:
            ood_all_labels.append(labels)

    for spec in attack_specs:
        name, csv_path, label_path = parse_dataset_arg(spec)
        x, load_info = load_numeric_csv(
            csv_path,
            auto_drop_index_col0=not args.no_auto_drop_index_col0,
        )
        if x.shape[1] != x_all.shape[1]:
            raise RuntimeError(
                f"{name} dim mismatch: {x.shape[1]} != {x_all.shape[1]} "
                f"(raw_dim={load_info['raw_dim']} dropped_col0={load_info['dropped_col0']})"
            )
        scores = score_dataset(model, x)
        np.save(run_dir / f"{name}_scores.npy", scores)
        labels = maybe_load_labels(label_path, len(scores))
        stats = score_stats(scores)
        auc = compute_auc(labels, scores) if labels is not None else None
        attack_results[name] = {
            "csv": str(csv_path),
            "labels": None if label_path is None else str(label_path),
            "load_info": load_info,
            "stats": stats,
            "metrics": auc,
        }
        ood_all_scores.append(scores)
        if labels is not None:
            ood_all_labels.append(labels)

    combined_ood_metrics = None
    if ood_all_scores and ood_all_labels:
        score_cat = np.concatenate(ood_all_scores)
        label_cat = np.concatenate(ood_all_labels)
        combined_ood_metrics = compute_auc(label_cat, score_cat)

    # Plot ID benign vs OOD benign histograms.
    plt.figure(figsize=(10, 5))
    eps = 1e-12
    plt.hist(np.log10(id_benign_scores + eps), bins=60, alpha=0.45, density=True, label="ID benign")
    for name, result in benign_results.items():
        s = np.load(run_dir / f"{name}_scores.npy")
        plt.hist(np.log10(s + eps), bins=60, alpha=0.35, density=True, label=f"{name}")
    plt.xlabel("log10(score)")
    plt.ylabel("density")
    plt.title("ID vs OOD Benign Score Distribution")
    plt.legend()
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(plot_dir / "hist_id_vs_ood_benign.png", dpi=150)
    plt.close()

    # Boxplot for fast visual drift check.
    box_data = [np.log10(id_benign_scores + eps)]
    box_labels = ["ID_benign"]
    for name in benign_results:
        s = np.load(run_dir / f"{name}_scores.npy")
        box_data.append(np.log10(s + eps))
        box_labels.append(name)
    plt.figure(figsize=(10, 5))
    plt.boxplot(box_data, tick_labels=box_labels, showfliers=False)
    plt.ylabel("log10(score)")
    plt.title("Score Drift Check (ID benign vs OOD benign)")
    plt.grid(axis="y", alpha=0.25)
    plt.tight_layout()
    plt.savefig(plot_dir / "boxplot_id_vs_ood_benign.png", dpi=150)
    plt.close()

    config = {
        "run_tag": args.run_tag,
        "train_csv": str(args.train_csv),
        "train_labels": str(args.train_labels),
        "max_ae": args.max_ae,
        "fm_grace": args.fm_grace,
        "ad_grace": args.ad_grace,
        "train_samples": args.train_samples,
        "id_eval_samples": args.id_eval_samples,
        "learning_rate": args.learning_rate,
        "hidden_ratio": args.hidden_ratio,
        "seed": args.seed,
        "detector_backend": args.detector_backend,
        "tailreg_lambda": args.tailreg_lambda,
        "tailreg_k": args.tailreg_k,
        "tailreg_warmup": args.tailreg_warmup,
        "tailreg_ema_alpha": args.tailreg_ema_alpha,
        "threshold_quantile": args.threshold_quantile,
        "skip_benign": args.skip_benign,
        "skip_attack": args.skip_attack,
        "no_auto_drop_index_col0": args.no_auto_drop_index_col0,
        "checkpoint": str(ckpt_path),
        "command": command_line,
        "cwd": os.getcwd(),
        "train_runtime_s": train_runtime_s,
        "train_load_info": train_load_info,
    }
    (run_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

    report = {
        "threshold_id_benign_q": args.threshold_quantile,
        "threshold_value": threshold,
        "id": {"stats": id_stats, "metrics": id_metrics},
        "ood_benign": benign_results,
        "ood_attack": attack_results,
        "ood_combined_metrics": combined_ood_metrics,
    }
    (run_dir / "metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        f"checkpoint: {ckpt_path}",
        f"id_threshold_q{args.threshold_quantile:.2f}: {threshold:.8f}",
        f"id_mean={id_stats['mean']:.8f} id_q99={id_stats['q99']:.8f}",
    ]
    for name, item in benign_results.items():
        st = item["stats"]
        lines.append(
            f"{name}: mean={st['mean']:.8f} q99={st['q99']:.8f} alarm_ratio={item['alarm_ratio_at_id_q99_threshold']:.4f}"
        )
    for name, item in attack_results.items():
        st = item["stats"]
        lines.append(f"{name}: mean={st['mean']:.8f} q99={st['q99']:.8f}")
    if id_metrics is not None:
        lines.append(f"id_roc_auc={id_metrics['roc_auc']:.6f} id_pr_auc={id_metrics['pr_auc']:.6f}")
    if combined_ood_metrics is not None:
        lines.append(
            f"ood_combined_roc_auc={combined_ood_metrics['roc_auc']:.6f} "
            f"ood_combined_pr_auc={combined_ood_metrics['pr_auc']:.6f}"
        )
    (run_dir / "summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[done] run dir: {run_dir}")


if __name__ == "__main__":
    main()
