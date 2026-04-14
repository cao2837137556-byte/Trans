from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

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
for p in [THIS_DIR, REPO_DIR]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import frontend100_negative_recipe_rescoring as resc


class TemporalTransformerAE(nn.Module):
    def __init__(self, feature_dim: int, seq_len: int, d_model: int = 64, nhead: int = 4, num_layers: int = 1):
        super().__init__()
        self.feature_dim = int(feature_dim)
        self.seq_len = int(seq_len)
        self.in_proj = nn.Linear(feature_dim, d_model)
        self.pos = nn.Parameter(torch.zeros(1, seq_len, d_model))
        enc = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=max(128, d_model * 4),
            dropout=0.0,
            batch_first=True,
            activation="gelu",
        )
        self.encoder = nn.TransformerEncoder(enc, num_layers=num_layers)
        self.out_proj = nn.Linear(d_model, feature_dim)

    def forward(self, x):
        h = self.in_proj(x) + self.pos
        h = self.encoder(h)
        return self.out_proj(h)


class FlattenAE(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int = 256, bottleneck: int = 64):
        super().__init__()
        hidden_dim = int(min(max(64, hidden_dim), max(64, input_dim)))
        bottleneck = int(min(max(16, bottleneck), hidden_dim))
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, bottleneck),
            nn.ReLU(),
            nn.Linear(bottleneck, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, input_dim),
        )

    def forward(self, x):
        return self.net(x)


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


def load_json(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def md_table(df: pd.DataFrame) -> str:
    return resc.md_table(df)


def make_sequences(x: np.ndarray, L: int) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    n, d = x.shape
    if n < L:
        raise ValueError(f"Need at least L rows; got {n}, L={L}")
    # Sliding-window view is read-only; copy to keep torch conversion safe.
    return np.lib.stride_tricks.sliding_window_view(x, window_shape=L, axis=0).transpose(0, 2, 1).copy()


def standardize_seq(x: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    return ((x - mean.reshape(1, 1, -1)) / std.reshape(1, 1, -1)).astype(np.float32)


def standardize_flat(x: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    z = x.reshape(len(x), -1)
    return ((z - mean.reshape(1, -1)) / std.reshape(1, -1)).astype(np.float32)


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


def score_temporal(model: nn.Module, x: np.ndarray, batch_size: int, device: str) -> Tuple[np.ndarray, np.ndarray]:
    model.to(device)
    model.eval()
    full_scores = []
    last_scores = []
    with torch.no_grad():
        for st in range(0, len(x), batch_size):
            xb = torch.from_numpy(x[st : st + batch_size].astype(np.float32)).to(device)
            out = model(xb)
            err = (out - xb) ** 2
            full = torch.sqrt(torch.mean(err, dim=(1, 2))).detach().cpu().numpy()
            last = torch.sqrt(torch.mean(err[:, -1, :], dim=1)).detach().cpu().numpy()
            full_scores.append(full)
            last_scores.append(last)
    return np.concatenate(full_scores).astype(np.float64), np.concatenate(last_scores).astype(np.float64)


def score_flat(model: nn.Module, x_seq: np.ndarray, mean: np.ndarray, std: np.ndarray, batch_size: int, device: str) -> Tuple[np.ndarray, np.ndarray]:
    z = standardize_flat(x_seq, mean, std)
    model.to(device)
    model.eval()
    full_scores = []
    last_scores = []
    d = x_seq.shape[-1]
    with torch.no_grad():
        for st in range(0, len(z), batch_size):
            xb = torch.from_numpy(z[st : st + batch_size].astype(np.float32)).to(device)
            out = model(xb)
            err = (out - xb) ** 2
            full = torch.sqrt(torch.mean(err, dim=1)).detach().cpu().numpy()
            last = torch.sqrt(torch.mean(err[:, -d:], dim=1)).detach().cpu().numpy()
            full_scores.append(full)
            last_scores.append(last)
    return np.concatenate(full_scores).astype(np.float64), np.concatenate(last_scores).astype(np.float64)


def eval_scores(
    object_label: str,
    detector_family: str,
    score_label: str,
    variant: str,
    score_id: np.ndarray,
    score_ood: np.ndarray,
    score_attack: np.ndarray,
    high_idx: np.ndarray,
    mixed_idx: np.ndarray,
    budget: int,
    scan_points: int,
    extra: Dict,
) -> List[Dict]:
    rows = []
    ood_eval = score_ood[budget:]
    auc = resc.compute_auc(ood_eval_scores=ood_eval, attack_high_scores=score_attack[high_idx])
    for policy, thr, source in [
        ("fixed_id_q99", float(np.quantile(score_id, 0.99)), "ID benign q99"),
        (
            "naive_calibrated_budget5000_target1pct",
            float(np.quantile(score_ood[: min(budget, len(score_ood) - 1)], 0.99)),
            "first 5000 OOD benign q99",
        ),
    ]:
        row = resc.eval_threshold(
            threshold=thr,
            id_scores=score_id,
            ood_scores=score_ood,
            ood_eval_scores=ood_eval,
            attack_scores=score_attack,
            high_idx=high_idx,
            mixed_idx=mixed_idx,
        )
        rows.append(
            {
                "object_label": object_label,
                "detector_family": detector_family,
                "score_label": score_label,
                "variant": variant,
                "policy_name": policy,
                "selection_feasible": True,
                "threshold_source": source,
                "roc_auc_attack_high_vs_ood_eval": float(auc),
                **row,
                **extra,
            }
        )
    all_scores = np.concatenate([score_id, score_ood, score_attack]).astype(np.float64)
    thresholds = np.unique(np.quantile(all_scores, np.linspace(0, 1, scan_points)))
    scan = []
    for thr in thresholds:
        row = resc.eval_threshold(
            threshold=float(thr),
            id_scores=score_id,
            ood_scores=score_ood,
            ood_eval_scores=ood_eval,
            attack_scores=score_attack,
            high_idx=high_idx,
            mixed_idx=mixed_idx,
        )
        row["threshold"] = float(thr)
        scan.append(row)
    det50 = resc.choose_detection_floor(pd.DataFrame(scan), 0.5)
    if det50 is not None:
        rows.append(
            {
                "object_label": object_label,
                "detector_family": detector_family,
                "score_label": score_label,
                "variant": variant,
                "policy_name": "det_floor_50pct_min_alarm",
                "selection_feasible": True,
                "threshold_source": "min OOD alarm subject to high-purity detection >= 50%",
                "roc_auc_attack_high_vs_ood_eval": float(auc),
                **det50.to_dict(),
                **extra,
            }
        )
    return rows


def load_reference_rows() -> List[Dict]:
    refs = []
    p = WORKTREE_ROOT / "runs" / "frontend100_covariance_regularized_v1_2026-04-07" / "covariance_regularized_v1_results.csv"
    if not p.exists():
        return refs
    df = pd.read_csv(p)
    keep = {
        "da__default_score",
        "transformer__default_score",
        "transformer_tailreg__default_score",
        "latent_swap_spike_mix_no_compact__log_weighted_z_rmse0.5_cos1.0_old",
    }
    ref = df[df["object_label"].isin(keep)].copy()
    ref["variant"] = "seed42_reference_100d"
    ref["source_mode"] = "reused_reference"
    refs.extend(ref.to_dict("records"))
    return refs


def plot_tradeoff(df: pd.DataFrame, out: Path) -> None:
    fixed = df[(df["policy_name"] == "fixed_id_q99") & (df["selection_feasible"].astype(bool))].copy()
    plt.figure(figsize=(10.5, 6.8))
    for _, r in fixed.iterrows():
        obj = str(r["object_label"])
        if obj.startswith("temporal_transformer"):
            color, marker = "#1f77b4", "o"
        elif obj.startswith("flatten_ae"):
            color, marker = "#ff7f0e", "^"
        elif obj.startswith("da__"):
            color, marker = "#d62728", "s"
        else:
            color, marker = "#7f7f7f", "x"
        plt.scatter(r["ood_alarm_ratio_eval"], r["attack_detection_high_purity"], c=color, marker=marker, s=80)
        plt.text(r["ood_alarm_ratio_eval"] + 0.004, r["attack_detection_high_purity"] + 0.006, obj, fontsize=8)
    plt.axvline(0.1209, color="black", linestyle="--", linewidth=1, alpha=0.55, label="dA seed42 alarm")
    plt.axhline(0.7896, color="black", linestyle=":", linewidth=1, alpha=0.55, label="dA seed42 det")
    plt.xlabel("OOD benign alarm ratio (fixed q99)")
    plt.ylabel("High-purity attack detection")
    plt.title("Temporal frontend v1 fixed trade-off")
    plt.grid(alpha=0.25)
    plt.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(out, dpi=180)
    plt.close()


def plot_by_l(df: pd.DataFrame, out: Path) -> None:
    fixed = df[(df["policy_name"] == "fixed_id_q99") & df["object_label"].str.contains("_last")].copy()
    fixed = fixed[fixed["detector_family"].isin(["temporal_transformer_v1", "flatten_ae_temporal_control"])]
    if fixed.empty:
        return
    plt.figure(figsize=(8.5, 5.5))
    for fam, g in fixed.groupby("detector_family"):
        g = g.sort_values("L")
        plt.plot(g["L"], g["ood_alarm_ratio_eval"], marker="o", label=f"{fam} alarm")
        plt.plot(g["L"], g["attack_detection_high_purity"], marker="^", linestyle="--", label=f"{fam} det")
    plt.axhline(0.1209, color="black", linestyle="--", linewidth=1, alpha=0.5)
    plt.axhline(0.7896, color="black", linestyle=":", linewidth=1, alpha=0.5)
    plt.xlabel("temporal length L")
    plt.ylabel("ratio")
    plt.title("Temporal frontend fixed metrics vs L")
    plt.grid(alpha=0.25)
    plt.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(out, dpi=180)
    plt.close()


def append_map(run_tag: str) -> None:
    p = WORKTREE_ROOT / "runs" / "master_experiment_map_v1.md"
    if not p.exists():
        return
    text = p.read_text(encoding="utf-8")
    if f"`{run_tag}`" in text:
        return
    entry = f"\n- `{run_tag}`: Transformer TemporalFrontend-v1 single-seed minimal experiment on stacked original 100D windows; path: `runs/{run_tag}/`.\n"
    p.write_text(text.rstrip() + entry, encoding="utf-8")


def update_research_log(run_tag: str, block: str) -> None:
    p = WORKTREE_ROOT / "runs" / "research_log" / "a_tier_experiment_progress_log.md"
    if not p.exists():
        return
    text = p.read_text(encoding="utf-8")
    marker = "### 5.16 Temporal Frontend v1"
    if marker in text:
        return
    insert = "\n## 6. Current Candidate Ranking"
    entry = f"\n{marker}\n\nRun:\n- `runs/{run_tag}/`\n\n{block}\n"
    if insert in text:
        text = text.replace(insert, entry + "\n" + insert)
    else:
        text = text.rstrip() + entry
    p.write_text(text, encoding="utf-8")


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    ap = argparse.ArgumentParser(description="Temporal frontend v1: stack original 100D windows for Transformer.")
    ap.add_argument("--run-tag", default=f"frontend100_temporal_frontend_v1_{today}")
    ap.add_argument("--source-root", type=Path, default=WORKTREE_ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--lengths", default="4,8,16")
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--batch-size", type=int, default=256)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--train-samples", type=int, default=8000)
    ap.add_argument("--id-eval-samples", type=int, default=5000)
    ap.add_argument("--calibration-budget", type=int, default=5000)
    ap.add_argument("--scan-points", type=int, default=1200)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = ap.parse_args()

    set_seed(args.seed)
    lengths = [int(x) for x in args.lengths.split(",") if x.strip()]
    out = WORKTREE_ROOT / "runs" / args.run_tag
    out.mkdir(parents=True, exist_ok=True)
    plot_dir = out / "temporal_frontend_v1_plots"
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
    stage2 = load_json(source / "runs" / "frontend100_joint_eval_stage2_2026-04-01" / "attack_manifest_stage2.json")
    stage2_idx = resc.build_stage2_indices(stage2)

    rows: List[Dict] = []
    diagnostics: List[Dict] = []
    rows.extend(load_reference_rows())
    for L in lengths:
        print(f"[L={L}] build sequences", flush=True)
        seq_id_all = make_sequences(x_id_src[: args.train_samples + args.id_eval_samples + L - 1], L)
        x_train = seq_id_all[: args.train_samples]
        x_id = seq_id_all[args.train_samples : args.train_samples + args.id_eval_samples]
        x_ood = make_sequences(x_ood_src, L)
        x_attack = make_sequences(x_attack_src, L)
        high = stage2_idx["high"] - (L - 1)
        high = high[(high >= 0) & (high < len(x_attack))]
        mixed = stage2_idx["mixed"] - (L - 1)
        mixed = mixed[(mixed >= 0) & (mixed < len(x_attack))]

        mean = x_train.reshape(-1, x_train.shape[-1]).mean(axis=0)
        std = x_train.reshape(-1, x_train.shape[-1]).std(axis=0)
        std = np.maximum(std, 1e-6)
        z_train = standardize_seq(x_train, mean, std)
        z_id = standardize_seq(x_id, mean, std)
        z_ood = standardize_seq(x_ood, mean, std)
        z_attack = standardize_seq(x_attack, mean, std)

        print(f"[L={L}] train temporal transformer", flush=True)
        model = TemporalTransformerAE(feature_dim=x_train.shape[-1], seq_len=L, d_model=64)
        losses = train_model(model, z_train, args.epochs, args.batch_size, args.lr, args.device)
        id_full, id_last = score_temporal(model, z_id, args.batch_size, args.device)
        ood_full, ood_last = score_temporal(model, z_ood, args.batch_size, args.device)
        attack_full, attack_last = score_temporal(model, z_attack, args.batch_size, args.device)
        for score_name, sid, sood, satt in [
            ("rmse_last_window", id_last, ood_last, attack_last),
            ("rmse_full_sequence", id_full, ood_full, attack_full),
        ]:
            rows.extend(
                eval_scores(
                    object_label=f"temporal_transformer_L{L}_{'last' if 'last' in score_name else 'full'}",
                    detector_family="temporal_transformer_v1",
                    score_label=score_name,
                    variant=f"L{L}",
                    score_id=sid,
                    score_ood=sood,
                    score_attack=satt,
                    high_idx=high,
                    mixed_idx=mixed,
                    budget=args.calibration_budget,
                    scan_points=args.scan_points,
                    extra={"L": L, "seed": args.seed, "epochs": args.epochs, "device": args.device},
                )
            )
        diagnostics.append(
            {
                "object_label": f"temporal_transformer_L{L}",
                "L": L,
                "train_loss_start": float(losses[0]),
                "train_loss_end": float(losses[-1]),
                "train_loss_min": float(np.min(losses)),
                "high_idx_n": int(len(high)),
                "mixed_idx_n": int(len(mixed)),
            }
        )

        print(f"[L={L}] train flatten AE control", flush=True)
        flat_mean = x_train.reshape(len(x_train), -1).mean(axis=0)
        flat_std = np.maximum(x_train.reshape(len(x_train), -1).std(axis=0), 1e-6)
        flat_train = standardize_flat(x_train, flat_mean, flat_std)
        flat_model = FlattenAE(input_dim=flat_train.shape[1], hidden_dim=256, bottleneck=64)
        flat_losses = train_model(flat_model, flat_train, args.epochs, args.batch_size, args.lr, args.device)
        fid_full, fid_last = score_flat(flat_model, x_id, flat_mean, flat_std, args.batch_size, args.device)
        food_full, food_last = score_flat(flat_model, x_ood, flat_mean, flat_std, args.batch_size, args.device)
        fatt_full, fatt_last = score_flat(flat_model, x_attack, flat_mean, flat_std, args.batch_size, args.device)
        for score_name, sid, sood, satt in [
            ("rmse_last_window", fid_last, food_last, fatt_last),
            ("rmse_full_sequence", fid_full, food_full, fatt_full),
        ]:
            rows.extend(
                eval_scores(
                    object_label=f"flatten_ae_L{L}_{'last' if 'last' in score_name else 'full'}",
                    detector_family="flatten_ae_temporal_control",
                    score_label=score_name,
                    variant=f"L{L}",
                    score_id=sid,
                    score_ood=sood,
                    score_attack=satt,
                    high_idx=high,
                    mixed_idx=mixed,
                    budget=args.calibration_budget,
                    scan_points=args.scan_points,
                    extra={"L": L, "seed": args.seed, "epochs": args.epochs, "device": args.device},
                )
            )
        diagnostics.append(
            {
                "object_label": f"flatten_ae_L{L}",
                "L": L,
                "train_loss_start": float(flat_losses[0]),
                "train_loss_end": float(flat_losses[-1]),
                "train_loss_min": float(np.min(flat_losses)),
                "high_idx_n": int(len(high)),
                "mixed_idx_n": int(len(mixed)),
            }
        )

    df = pd.DataFrame(rows)
    df.to_csv(out / "temporal_frontend_v1_results.csv", index=False)
    df.to_csv(out / "results.csv", index=False)
    diag = pd.DataFrame(diagnostics)
    diag.to_csv(out / "temporal_frontend_v1_diagnostics.csv", index=False)
    results_md = "# Temporal Frontend v1 Results\n\n"
    results_md += md_table(
        df[
            [
                "object_label",
                "detector_family",
                "score_label",
                "policy_name",
                "L",
                "ood_alarm_ratio_eval",
                "attack_detection_high_purity",
                "roc_auc_attack_high_vs_ood_eval",
                "selection_feasible",
            ]
        ]
        .sort_values(["policy_name", "object_label"])
        .fillna("")
    )
    (out / "temporal_frontend_v1_results.md").write_text(results_md, encoding="utf-8")
    plot_tradeoff(df, plot_dir / "fixed_tradeoff_temporal_frontend_v1.png")
    plot_by_l(df, plot_dir / "fixed_metrics_vs_L.png")

    fixed = df[(df["policy_name"].eq("fixed_id_q99")) & df["selection_feasible"].astype(bool)].copy()
    fixed_sorted = fixed.sort_values(["ood_alarm_ratio_eval", "attack_detection_high_purity"], ascending=[True, False])
    summary = "# Transformer TemporalFrontend-v1 Summary\n\n"
    summary += "- This is a single-seed minimal experiment.\n"
    summary += "- Original 100D frontend is unchanged; only consecutive windows are stacked as temporal context.\n"
    summary += "- Temporal Transformer uses true time tokens `[L,100D]`; flatten AE is the control for simply seeing `L*100D` context.\n\n"
    summary += "## Fixed q99 Results\n\n"
    summary += md_table(
        fixed[
            [
                "object_label",
                "detector_family",
                "score_label",
                "L",
                "ood_alarm_ratio_eval",
                "attack_detection_high_purity",
                "roc_auc_attack_high_vs_ood_eval",
            ]
        ].sort_values("object_label").fillna("")
    )
    best = fixed_sorted.head(1).iloc[0]
    summary += "\n## Current Reading\n\n"
    summary += f"- Best low-alarm fixed point: `{best['object_label']}` with alarm `{best['ood_alarm_ratio_eval']:.4f}` and detection `{best['attack_detection_high_purity']:.4f}`.\n"
    summary += "- Compare against seed42 dA reference: alarm `0.1209`, detection `0.7896`.\n"
    summary += "- If temporal Transformer improves detection without exploding alarm, it is worth multi-seed; otherwise temporal stacking alone is not enough.\n"
    (out / "temporal_frontend_v1_summary.md").write_text(summary, encoding="utf-8")
    (out / "summary.md").write_text(summary, encoding="utf-8")

    cfg = {
        "stage": "frontend100_temporal_frontend_v1",
        "run_tag": args.run_tag,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "seed": args.seed,
        "lengths": lengths,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "lr": args.lr,
        "device": args.device,
        "data_protocol": "original-frontend 100D + temporal stacking; stronger OOD eval unchanged",
        "train_samples": args.train_samples,
        "id_eval_samples": args.id_eval_samples,
        "outputs": {
            "results": str(out / "temporal_frontend_v1_results.csv"),
            "diagnostics": str(out / "temporal_frontend_v1_diagnostics.csv"),
            "summary": str(out / "summary.md"),
            "plots": str(plot_dir),
        },
    }
    (out / "temporal_frontend_v1_config_manifest.json").write_text(json.dumps(clean(cfg), indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "config.json").write_text(json.dumps(clean(cfg), indent=2, ensure_ascii=False), encoding="utf-8")
    append_map(args.run_tag)
    update_research_log(
        args.run_tag,
        "- Minimal temporal stacking experiment: original 100D features are unchanged, but Transformer sees short `[L,100D]` sequences.\n"
        "- Includes flatten AE temporal control to test whether gains come from temporal context alone or Transformer sequence bias.",
    )
    print(f"[done] temporal frontend output: {out}", flush=True)


if __name__ == "__main__":
    main()
