
from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

THIS_DIR = Path(__file__).resolve().parent
REPO_DIR = THIS_DIR.parent
WORKTREE_ROOT = REPO_DIR.parent
for path in [THIS_DIR, REPO_DIR]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from paths import ARTIFACT_RUNS_DIR, TRACKED_RUNS_DIR

import frontend100_negative_recipe_rescoring as resc
import frontend100_temporal_frontend_v1 as tfv1


class RecurrentAE(nn.Module):
    def __init__(self, feature_dim: int, hidden_dim: int = 64, latent_dim: int = 32, cell: str = "lstm"):
        super().__init__()
        self.cell = cell.lower()
        rnn_cls = nn.LSTM if self.cell == "lstm" else nn.GRU
        self.encoder = rnn_cls(input_size=feature_dim, hidden_size=hidden_dim, num_layers=1, batch_first=True)
        self.to_latent = nn.Linear(hidden_dim, latent_dim)
        self.from_latent = nn.Linear(latent_dim, hidden_dim)
        self.decoder = rnn_cls(input_size=feature_dim, hidden_size=hidden_dim, num_layers=1, batch_first=True)
        self.out = nn.Linear(hidden_dim, feature_dim)

    def forward(self, x):
        _, h = self.encoder(x)
        if self.cell == "lstm":
            h_last = h[0][-1]
        else:
            h_last = h[-1]
        z = torch.tanh(self.to_latent(h_last))
        h0 = torch.tanh(self.from_latent(z)).unsqueeze(0).contiguous()
        dec_in = torch.zeros_like(x)
        if self.cell == "lstm":
            c0 = torch.zeros_like(h0)
            dec_out, _ = self.decoder(dec_in, (h0, c0))
        else:
            dec_out, _ = self.decoder(dec_in, h0)
        return self.out(dec_out)


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def clean(obj):
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean(v) for v in obj]
    if isinstance(obj, tuple):
        return [clean(v) for v in obj]
    if isinstance(obj, np.generic):
        return clean(obj.item())
    if isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)):
        return None
    return obj


def md_table(df: pd.DataFrame) -> str:
    return resc.md_table(df)


def train_model(model: nn.Module, x_train: np.ndarray, epochs: int, batch_size: int, lr: float, device: str) -> List[float]:
    model.to(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    crit = nn.MSELoss()
    ds = TensorDataset(torch.from_numpy(x_train.astype(np.float32)))
    loader = DataLoader(ds, batch_size=batch_size, shuffle=True, drop_last=False)
    losses = []
    model.train()
    for _ in range(int(epochs)):
        total = 0.0
        count = 0
        for (xb,) in loader:
            xb = xb.to(device)
            opt.zero_grad()
            out = model(xb)
            loss = crit(out, xb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            total += float(loss.detach().item()) * len(xb)
            count += len(xb)
        losses.append(total / max(1, count))
    return losses


def score_model(model: nn.Module, x: np.ndarray, batch_size: int, device: str):
    model.to(device)
    model.eval()
    full_scores = []
    last_scores = []
    with torch.no_grad():
        for st in range(0, len(x), batch_size):
            xb = torch.from_numpy(x[st:st+batch_size].astype(np.float32)).to(device)
            out = model(xb)
            err = (out - xb) ** 2
            full_scores.append(torch.sqrt(torch.mean(err, dim=(1,2))).cpu().numpy())
            last_scores.append(torch.sqrt(torch.mean(err[:, -1, :], dim=1)).cpu().numpy())
    return np.concatenate(full_scores).astype(np.float64), np.concatenate(last_scores).astype(np.float64)


def aggregate(df: pd.DataFrame) -> pd.DataFrame:
    metrics = ["id_alarm_ratio", "ood_alarm_ratio_eval", "attack_detection_high_purity", "attack_detection_boundary", "roc_auc_attack_high_vs_ood_eval"]
    agg = df.groupby(["object_label", "detector_family", "score_label", "policy_name", "L"], dropna=False, as_index=False)[metrics].agg(["mean", "std", "count"]).reset_index()
    cols = []
    for c in agg.columns:
        if isinstance(c, tuple):
            cols.append(c[0] if c[1] == "" else f"{c[0]}_{c[1]}")
        else:
            cols.append(str(c))
    agg.columns = cols
    return agg


def plot_fixed(agg: pd.DataFrame, out: Path):
    fixed = agg[agg["policy_name"].eq("fixed_id_q99")].copy()
    fig, ax = plt.subplots(figsize=(11, 7))
    for _, r in fixed.iterrows():
        x = float(r["ood_alarm_ratio_eval_mean"])
        y = float(r["attack_detection_high_purity_mean"])
        xerr = 0.0 if pd.isna(r.get("ood_alarm_ratio_eval_std")) else float(r["ood_alarm_ratio_eval_std"])
        yerr = 0.0 if pd.isna(r.get("attack_detection_high_purity_std")) else float(r["attack_detection_high_purity_std"])
        label = str(r["object_label"])
        ax.errorbar([x], [y], xerr=[xerr], yerr=[yerr], fmt="o", capsize=3)
        ax.text(x+0.004, y+0.006, label, fontsize=8)
    ax.axvline(0.1322, color="black", ls="--", lw=1, label="dA alarm mean")
    ax.axhline(0.8014, color="black", ls=":", lw=1, label="dA det mean")
    ax.set_xlabel("OOD benign alarm ratio (fixed q99)")
    ax.set_ylabel("High-purity attack detection")
    ax.set_title("Recurrent deep baselines on temporal original-100D windows")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=180)
    plt.close(fig)


def plot_by_l(agg: pd.DataFrame, out: Path):
    fixed = agg[agg["policy_name"].eq("fixed_id_q99")].copy()
    fig, ax = plt.subplots(figsize=(9, 6))
    for label, g in fixed.groupby("detector_family"):
        g = g[g["score_label"].eq("rmse_last_window")].sort_values("L")
        if g.empty:
            continue
        ax.plot(g["L"], g["ood_alarm_ratio_eval_mean"], marker="o", label=f"{label} alarm")
        ax.plot(g["L"], g["attack_detection_high_purity_mean"], marker="^", ls="--", label=f"{label} det")
    ax.axhline(0.1322, color="black", ls="--", lw=1, alpha=0.6)
    ax.axhline(0.8014, color="black", ls=":", lw=1, alpha=0.6)
    ax.set_xlabel("sequence length L")
    ax.set_ylabel("ratio")
    ax.set_title("Recurrent baseline fixed metrics vs L")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=180)
    plt.close(fig)


def append_map(run_tag: str) -> None:
    p = TRACKED_RUNS_DIR / "master_experiment_map_v1.md"
    if not p.exists():
        return
    text = p.read_text(encoding="utf-8")
    if f"`{run_tag}`" in text:
        return
    entry = f"\n- `{run_tag}`: Multi-seed LSTM-AE/GRU-AE deep sequence baselines on stacked original 100D windows; path: `runs/{run_tag}/`.\n"
    p.write_text(text.rstrip() + entry, encoding="utf-8")


def update_log(run_tag: str, best_line: str) -> None:
    p = TRACKED_RUNS_DIR / "research_log" / "a_tier_experiment_progress_log.md"
    if not p.exists():
        return
    text = p.read_text(encoding="utf-8")
    marker = "### 5.19 Recurrent Deep Sequence Baselines"
    block = f"""

{marker}

Run:
- `runs/{run_tag}/`

Purpose:
- Add a minimal deep sequence baseline layer for A-tier comparison risk: `LSTM-AE` and `GRU-AE` on stacked original 100D windows.
- This is an unsupervised ID-benign-only baseline, not a Transformer modification.

Current result:
- {best_line}

Interpretation:
- If recurrent AEs fail under stronger OOD fixed q99, the evaluation setting is not trivially solved by generic sequence autoencoders.
- If they beat dA, they become required baselines for the paper and Transformer claims must be positioned accordingly.
"""
    if marker in text:
        head, tail = text.split(marker, 1)
        nxt = tail.find("\n### ", 5)
        text = head.rstrip() + "\n\n" + block.strip() + (tail[nxt:] if nxt >= 0 else "\n")
    else:
        insert = "\n## 6. Current Candidate Ranking"
        text = text.replace(insert, block + "\n" + insert) if insert in text else text.rstrip() + block
    p.write_text(text, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="LSTM-AE / GRU-AE deep sequence baselines for frontend100 stronger OOD.")
    ap.add_argument("--run-tag", default="frontend100_recurrent_deep_baselines_2026-04-08")
    ap.add_argument("--source-root", type=Path, default=WORKTREE_ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master")
    ap.add_argument("--seeds", default="101,202,303")
    ap.add_argument("--lengths", default="4,8")
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--batch-size", type=int, default=256)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--train-samples", type=int, default=8000)
    ap.add_argument("--id-eval-samples", type=int, default=5000)
    ap.add_argument("--calibration-budget", type=int, default=5000)
    ap.add_argument("--scan-points", type=int, default=1000)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = ap.parse_args()

    seeds = [int(x) for x in args.seeds.split(",") if x.strip()]
    lengths = [int(x) for x in args.lengths.split(",") if x.strip()]
    out = ARTIFACT_RUNS_DIR / args.run_tag
    out.mkdir(parents=True, exist_ok=True)
    plot_dir = out / "recurrent_deep_baseline_plots"
    plot_dir.mkdir(exist_ok=True)
    (out / "command.txt").write_text("python " + " ".join(sys.argv) + "\n", encoding="utf-8")

    source = args.source_root
    data = source / "runs" / "frontend100_crosscapture_stage1_2026-03-25" / "data"
    max_l = max(lengths)
    id_rows_needed = args.train_samples + args.id_eval_samples + max_l - 1
    x_id_src = pd.read_csv(data / "id_source_100.csv", header=None, nrows=id_rows_needed).to_numpy(np.float32)
    x_ood_src = pd.read_csv(data / "ood_benign_source_100.csv", header=None).to_numpy(np.float32)
    attack_csv = source / "runs" / "frontend100_joint_eval_stage1_2026-03-31" / "data" / "attack_source_100.csv"
    x_attack_src = pd.read_csv(attack_csv, header=None).to_numpy(np.float32)
    stage2 = tfv1.load_json(source / "runs" / "frontend100_joint_eval_stage2_2026-04-01" / "attack_manifest_stage2.json")
    stage2_idx = resc.build_stage2_indices(stage2)

    rows: List[Dict] = []
    diagnostics: List[Dict] = []
    for L in lengths:
        seq_id_all = tfv1.make_sequences(x_id_src[: args.train_samples + args.id_eval_samples + L - 1], L)
        x_train = seq_id_all[: args.train_samples]
        x_id = seq_id_all[args.train_samples : args.train_samples + args.id_eval_samples]
        x_ood = tfv1.make_sequences(x_ood_src, L)
        x_attack = tfv1.make_sequences(x_attack_src, L)
        high = stage2_idx["high"] - (L - 1)
        high = high[(high >= 0) & (high < len(x_attack))]
        mixed = stage2_idx["mixed"] - (L - 1)
        mixed = mixed[(mixed >= 0) & (mixed < len(x_attack))]
        mean = x_train.reshape(-1, x_train.shape[-1]).mean(axis=0)
        std = np.maximum(x_train.reshape(-1, x_train.shape[-1]).std(axis=0), 1e-6)
        z_train = tfv1.standardize_seq(x_train, mean, std)
        z_id = tfv1.standardize_seq(x_id, mean, std)
        z_ood = tfv1.standardize_seq(x_ood, mean, std)
        z_attack = tfv1.standardize_seq(x_attack, mean, std)
        for seed in seeds:
            set_seed(seed)
            for cell in ["lstm", "gru"]:
                print(f"[L={L} seed={seed}] train {cell.upper()}-AE", flush=True)
                model = RecurrentAE(feature_dim=x_train.shape[-1], hidden_dim=64, latent_dim=32, cell=cell)
                losses = train_model(model, z_train, args.epochs, args.batch_size, args.lr, args.device)
                id_full, id_last = score_model(model, z_id, args.batch_size, args.device)
                ood_full, ood_last = score_model(model, z_ood, args.batch_size, args.device)
                attack_full, attack_last = score_model(model, z_attack, args.batch_size, args.device)
                for score_label, sid, sood, satt in [
                    ("rmse_last_window", id_last, ood_last, attack_last),
                    ("rmse_full_sequence", id_full, ood_full, attack_full),
                ]:
                    rows.extend(tfv1.eval_scores(
                        object_label=f"{cell}_ae_L{L}_{'last' if 'last' in score_label else 'full'}",
                        detector_family=f"{cell}_ae",
                        score_label=score_label,
                        variant=f"L{L}_seed{seed}",
                        score_id=sid,
                        score_ood=sood,
                        score_attack=satt,
                        high_idx=high,
                        mixed_idx=mixed,
                        budget=args.calibration_budget,
                        scan_points=args.scan_points,
                        extra={"L": L, "seed": seed, "epochs": args.epochs, "device": args.device},
                    ))
                diagnostics.append({
                    "detector_family": f"{cell}_ae",
                    "object_base": f"{cell}_ae_L{L}",
                    "L": L,
                    "seed": seed,
                    "train_loss_start": float(losses[0]),
                    "train_loss_end": float(losses[-1]),
                    "train_loss_min": float(np.min(losses)),
                    "high_idx_n": int(len(high)),
                    "mixed_idx_n": int(len(mixed)),
                })

    result = pd.DataFrame(rows)
    agg = aggregate(result)
    result.to_csv(out / "recurrent_deep_baseline_results.csv", index=False)
    result.to_csv(out / "results.csv", index=False)
    agg.to_csv(out / "recurrent_deep_baseline_aggregate.csv", index=False)
    pd.DataFrame(diagnostics).to_csv(out / "recurrent_deep_baseline_diagnostics.csv", index=False)
    (out / "recurrent_deep_baseline_results.md").write_text(
        "# Recurrent Deep Baseline Results\n\n## Aggregate\n" + md_table(agg) + "\n\n## Per-seed\n" + md_table(result[["object_label", "seed", "policy_name", "ood_alarm_ratio_eval", "attack_detection_high_purity", "id_alarm_ratio", "roc_auc_attack_high_vs_ood_eval"]]),
        encoding="utf-8",
    )
    plot_fixed(agg, plot_dir / "fixed_tradeoff_recurrent_deep_baselines.png")
    plot_by_l(agg, plot_dir / "fixed_metrics_vs_L_recurrent.png")

    fixed = agg[agg["policy_name"].eq("fixed_id_q99")].copy()
    fixed = fixed.sort_values(["ood_alarm_ratio_eval_mean", "attack_detection_high_purity_mean"], ascending=[True, False])
    hit = fixed[(fixed["ood_alarm_ratio_eval_mean"] <= 0.1322) & (fixed["attack_detection_high_purity_mean"] >= 0.8014)]
    if hit.empty:
        best = fixed.iloc[0]
        best_line = f"No recurrent AE baseline beats dA fixed region; lowest-alarm `{best['object_label']}` has alarm={best['ood_alarm_ratio_eval_mean']:.4f}, det={best['attack_detection_high_purity_mean']:.4f}."
    else:
        best = hit.sort_values(["attack_detection_high_purity_mean", "ood_alarm_ratio_eval_mean"], ascending=[False, True]).iloc[0]
        best_line = f"Recurrent baseline hit `{best['object_label']}` has alarm={best['ood_alarm_ratio_eval_mean']:.4f}, det={best['attack_detection_high_purity_mean']:.4f}."

    summary = "\n".join([
        "# Recurrent Deep Sequence Baseline Summary",
        "",
        "- Models: `LSTM-AE` and `GRU-AE`.",
        f"- Seeds: `{seeds}`; lengths: `{lengths}`; epochs: `{args.epochs}`.",
        "- Training uses ID benign only; evaluation uses the same stronger OOD/high-purity attack protocol.",
        f"- {best_line}",
        "",
        "## Fixed q99 Aggregate",
        md_table(fixed[["object_label", "detector_family", "score_label", "L", "ood_alarm_ratio_eval_mean", "ood_alarm_ratio_eval_std", "attack_detection_high_purity_mean", "attack_detection_high_purity_std", "roc_auc_attack_high_vs_ood_eval_mean"]]),
        "",
        "## Interpretation",
        "- This is a baseline-risk check for A-tier framing. It should not be used as a Transformer improvement unless it beats both dA and the current covariance ensemble operating region.",
    ]) + "\n"
    (out / "summary.md").write_text(summary, encoding="utf-8")
    (out / "recurrent_deep_baseline_summary.md").write_text(summary, encoding="utf-8")

    cfg = {
        "stage": "frontend100_recurrent_deep_baselines",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_tag": args.run_tag,
        "models": ["lstm_ae", "gru_ae"],
        "seeds": seeds,
        "lengths": lengths,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "lr": args.lr,
        "device": args.device,
        "training_data": "ID benign only",
        "outputs": {"summary": str(out / "summary.md"), "results": str(out / "recurrent_deep_baseline_results.csv"), "plots": str(plot_dir)},
    }
    (out / "config.json").write_text(json.dumps(clean(cfg), indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "recurrent_deep_baseline_manifest.json").write_text(json.dumps(clean(cfg), indent=2, ensure_ascii=False), encoding="utf-8")
    append_map(args.run_tag)
    update_log(args.run_tag, best_line)
    print(f"[done] recurrent deep baseline output: {out}", flush=True)


if __name__ == "__main__":
    main()
