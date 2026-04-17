from __future__ import annotations

import argparse
import copy
import json
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, TensorDataset

THIS_DIR = Path(__file__).resolve().parent
REPO_DIR = THIS_DIR.parent
WORKTREE_ROOT = REPO_DIR.parent
REMOTE_PROJECT_ROOT = Path(os.environ["REMOTE_PROJECT_ROOT"]) if os.environ.get("REMOTE_PROJECT_ROOT") else None
for p in [THIS_DIR, REPO_DIR]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from paths import ARTIFACT_RUNS_DIR, TRACKED_RUNS_DIR

import frontend100_external_baselines as ext
import frontend100_negative_recipe_rescoring as resc


def resolve_artifact_runs_root() -> Path:
    if REMOTE_PROJECT_ROOT is not None:
        return REMOTE_PROJECT_ROOT / "runs"
    return ARTIFACT_RUNS_DIR


def resolve_output_dir(run_tag: str) -> Path:
    # In bundled HPC runs, the script lives under <run_dir>/repo/ood/*.py and
    # WORKTREE_ROOT points at <run_dir>. Writing to WORKTREE_ROOT/runs/<run_tag>
    # would incorrectly create a nested runs/ directory. Detect that layout and
    # write directly into <run_dir> instead.
    if (WORKTREE_ROOT / "job.slurm").exists() and (WORKTREE_ROOT / "repo").exists() and WORKTREE_ROOT.name == run_tag:
        return WORKTREE_ROOT
    return resolve_artifact_runs_root() / run_tag


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def choose_device(device: str) -> str:
    return "cuda" if device == "auto" and torch.cuda.is_available() else ("cpu" if device == "auto" else device)


class NumTokenizer(nn.Module):
    def __init__(self, n_features: int, d_token: int):
        super().__init__()
        self.w = nn.Parameter(torch.empty(n_features, d_token))
        self.b = nn.Parameter(torch.zeros(n_features, d_token))
        nn.init.normal_(self.w, std=0.02)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x.unsqueeze(-1) * self.w.unsqueeze(0) + self.b.unsqueeze(0)


class FTBlock(nn.Module):
    def __init__(self, d_token: int, n_heads: int, attn_dropout: float, ffn_dropout: float):
        super().__init__()
        self.n1 = nn.LayerNorm(d_token)
        self.attn = nn.MultiheadAttention(d_token, n_heads, dropout=attn_dropout, batch_first=True)
        self.d1 = nn.Dropout(attn_dropout)
        self.n2 = nn.LayerNorm(d_token)
        self.ff = nn.Sequential(
            nn.Linear(d_token, d_token * 4),
            nn.GELU(),
            nn.Dropout(ffn_dropout),
            nn.Linear(d_token * 4, d_token),
        )
        self.d2 = nn.Dropout(ffn_dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        y = self.n1(x)
        y, _ = self.attn(y, y, y, need_weights=False)
        x = x + self.d1(y)
        y = self.n2(x)
        return x + self.d2(self.ff(y))


class FTTransformerAE(nn.Module):
    def __init__(self, input_dim: int, d_token: int, n_heads: int, n_blocks: int, latent_dim: int, decoder_hidden: int, attn_dropout: float, ffn_dropout: float):
        super().__init__()
        if d_token % n_heads != 0:
            raise ValueError("d_token must be divisible by n_heads")
        self.tokenizer = NumTokenizer(input_dim, d_token)
        self.cls = nn.Parameter(torch.zeros(1, 1, d_token))
        self.blocks = nn.ModuleList([FTBlock(d_token, n_heads, attn_dropout, ffn_dropout) for _ in range(n_blocks)])
        self.norm = nn.LayerNorm(d_token)
        self.to_latent = nn.Linear(d_token, latent_dim)
        self.decoder = nn.Sequential(
            nn.LayerNorm(latent_dim),
            nn.Linear(latent_dim, decoder_hidden),
            nn.GELU(),
            nn.Dropout(ffn_dropout),
            nn.Linear(decoder_hidden, decoder_hidden),
            nn.GELU(),
            nn.Dropout(ffn_dropout),
            nn.Linear(decoder_hidden, input_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        tok = self.tokenizer(x)
        h = torch.cat([self.cls.expand(len(x), -1, -1), tok], dim=1)
        for blk in self.blocks:
            h = blk(h)
        z = self.to_latent(self.norm(h)[:, 0, :])
        return self.decoder(z)


class ResBlock(nn.Module):
    def __init__(self, d_hidden: int, dropout: float):
        super().__init__()
        self.net = nn.Sequential(
            nn.LayerNorm(d_hidden),
            nn.Linear(d_hidden, d_hidden * 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_hidden * 2, d_hidden),
            nn.Dropout(dropout),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.net(x)


class TabularResNetAE(nn.Module):
    def __init__(self, input_dim: int, d_hidden: int, n_blocks: int, latent_dim: int, decoder_hidden: int, dropout: float):
        super().__init__()
        self.in_proj = nn.Linear(input_dim, d_hidden)
        self.blocks = nn.ModuleList([ResBlock(d_hidden, dropout) for _ in range(n_blocks)])
        self.out_norm = nn.LayerNorm(d_hidden)
        self.to_latent = nn.Linear(d_hidden, latent_dim)
        self.decoder = nn.Sequential(
            nn.LayerNorm(latent_dim),
            nn.Linear(latent_dim, decoder_hidden),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(decoder_hidden, decoder_hidden),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(decoder_hidden, input_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.in_proj(x)
        for blk in self.blocks:
            h = blk(h)
        z = self.to_latent(self.out_norm(h))
        return self.decoder(z)


def make_model(name: str, input_dim: int, args: argparse.Namespace) -> nn.Module:
    if name == "ft_transformer_ae":
        return FTTransformerAE(input_dim, args.ft_d_token, args.ft_n_heads, args.ft_n_blocks, args.latent_dim, args.decoder_hidden, args.ft_attn_dropout, args.ft_ffn_dropout)
    if name == "rtdl_resnet_ae":
        return TabularResNetAE(input_dim, args.resnet_d_hidden, args.resnet_n_blocks, args.latent_dim, args.decoder_hidden, args.resnet_dropout)
    raise ValueError(name)


def split_train_val(x: np.ndarray, val_ratio: float, seed: int) -> Tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    idx = np.arange(len(x))
    rng.shuffle(idx)
    n_val = max(1, int(round(len(x) * val_ratio)))
    return x[idx[n_val:]] if len(idx[n_val:]) else x[idx[:n_val]], x[idx[:n_val]]


def make_loader(x: np.ndarray, batch_size: int, shuffle: bool) -> DataLoader:
    return DataLoader(TensorDataset(torch.from_numpy(x.astype(np.float32))), batch_size=batch_size, shuffle=shuffle, drop_last=False)


def eval_loss(model: nn.Module, loader: DataLoader, device: str) -> float:
    crit = nn.MSELoss(reduction="sum")
    model.eval()
    total = 0.0
    count = 0
    with torch.no_grad():
        for (xb,) in loader:
            xb = xb.to(device)
            total += float(crit(model(xb), xb).item())
            count += int(np.prod(xb.shape))
    return total / max(1, count)


def train_model(model: nn.Module, x_train: np.ndarray, x_val: np.ndarray, args: argparse.Namespace, device: str) -> Tuple[nn.Module, List[Dict], float, int]:
    model = model.to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    crit = nn.MSELoss()
    train_loader = make_loader(x_train, args.batch_size, True)
    val_loader = make_loader(x_val, args.batch_size, False)
    best_state = copy.deepcopy(model.state_dict())
    best_val = float("inf")
    best_epoch = 0
    bad = 0
    hist: List[Dict] = []
    for epoch in range(1, args.epochs + 1):
        model.train()
        total = 0.0
        count = 0
        for (xb,) in train_loader:
            xb = xb.to(device)
            opt.zero_grad()
            loss = crit(model(xb), xb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            total += float(loss.item()) * len(xb)
            count += len(xb)
        train_loss = total / max(1, count)
        val_loss = eval_loss(model, val_loader, device)
        hist.append({"epoch": epoch, "train_loss": train_loss, "val_loss": val_loss})
        if val_loss < best_val - 1e-8:
            best_val = val_loss
            best_epoch = epoch
            best_state = copy.deepcopy(model.state_dict())
            bad = 0
        else:
            bad += 1
        if bad >= args.patience:
            break
    model.load_state_dict(best_state)
    return model, hist, float(best_val), int(best_epoch)


def score_model(model: nn.Module, x: np.ndarray, batch_size: int, device: str) -> np.ndarray:
    model = model.to(device)
    model.eval()
    out: List[np.ndarray] = []
    with torch.no_grad():
        for (xb,) in make_loader(x, batch_size, False):
            xb = xb.to(device)
            err = (model(xb) - xb) ** 2
            out.append(torch.sqrt(torch.mean(err, dim=1)).detach().cpu().numpy())
    return np.concatenate(out).astype(np.float64)


def bench_model(model: nn.Module, x: np.ndarray, batch_size: int, device: str, repeats: int) -> Dict[str, float]:
    loader = make_loader(x, batch_size, False)
    model = model.to(device)
    model.eval()

    def run_once() -> float:
        st = time.perf_counter()
        with torch.no_grad():
            for (xb,) in loader:
                xb = xb.to(device)
                _ = torch.sqrt(torch.mean((model(xb) - xb) ** 2, dim=1))
        if device.startswith("cuda"):
            torch.cuda.synchronize()
        return time.perf_counter() - st

    run_once()
    times = [run_once() for _ in range(max(1, repeats))]
    elapsed = float(np.mean(times))
    return {"elapsed_sec_mean": elapsed, "ms_per_sample_mean": 1000.0 * elapsed / max(1, len(x)), "samples_per_sec_mean": float(len(x) / max(elapsed, 1e-12))}


def load_deep_svdd_rows(path: Path, seeds: Iterable[int]) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    keep = {"fixed_id_q99", "naive_calibrated_budget5000_target1pct", "det_floor_50pct_min_alarm"}
    out = df[(df["row_type"].eq("per_seed")) & (df["object_label"].eq("deep_svdd")) & (df["policy_name"].isin(keep)) & (df["seed"].isin(list(seeds)))].copy()
    if not out.empty:
        out["source_mode"] = "reused_existing_deep_svdd_reference"
        out["baseline_category"] = "external_unsupervised"
    return out


def load_frozen_refs(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    rows = []
    for _, r in df.iterrows():
        obj = str(r["object_label"])
        if obj not in {"dA fixed_id_q0p995", "Transformer ensemble mean_gate_rawq0p999/fixed_id_q0p995"}:
            continue
        rows.append({
            "row_type": "aggregate",
            "object_label": "transformer_ensemble_main_candidate" if "Transformer ensemble" in obj else "dA fixed_id_q0p995",
            "detector_family": "transformer_ensemble" if "Transformer ensemble" in obj else "dA",
            "score_label": "mean_gate_rawq0p999" if "Transformer ensemble" in obj else "default_score",
            "policy_name": "fixed_id_q995",
            "ood_alarm_ratio_eval_mean": float(r["ood_alarm"]),
            "ood_alarm_ratio_eval_std": np.nan,
            "attack_detection_high_purity_mean": float(r["high_purity_detection"]),
            "attack_detection_high_purity_std": np.nan,
            "id_alarm_ratio_mean": float(r["id_alarm"]),
            "id_alarm_ratio_std": np.nan,
            "roc_auc_attack_high_vs_ood_eval_mean": float(r["roc_auc"]),
            "roc_auc_attack_high_vs_ood_eval_std": np.nan,
            "baseline_category": "frozen_reference",
            "training_mode": "frozen_existing_reference",
            "uses_attack_labels": False,
            "source_mode": "final_candidate_audit_aggregate",
        })
    return pd.DataFrame(rows)


def plot_policy(agg: pd.DataFrame, policy: str, out: Path, title: str) -> None:
    df = agg[agg["policy_name"].eq(policy)].copy()
    if df.empty:
        return
    colors = {"modern_tabular_unsupervised": "#1f77b4", "external_unsupervised": "#2ca02c", "existing_reference": "#7f7f7f", "frozen_reference": "#d62728"}
    marks = {"modern_tabular_unsupervised": "o", "external_unsupervised": "s", "existing_reference": "^", "frozen_reference": "D"}
    fig, ax = plt.subplots(figsize=(10.5, 7.0))
    for _, r in df.iterrows():
        cat = str(r.get("baseline_category", "existing_reference"))
        x = float(r["ood_alarm_ratio_eval_mean"])
        y = float(r["attack_detection_high_purity_mean"])
        xerr = 0.0 if pd.isna(r.get("ood_alarm_ratio_eval_std")) else float(r["ood_alarm_ratio_eval_std"])
        yerr = 0.0 if pd.isna(r.get("attack_detection_high_purity_std")) else float(r["attack_detection_high_purity_std"])
        ax.errorbar([x], [y], xerr=[xerr], yerr=[yerr], fmt=marks.get(cat, "o"), color=colors.get(cat, "#9467bd"), capsize=3)
        ax.text(x + 0.004, y + 0.006, str(r["object_label"]), fontsize=8)
    ax.set_xlabel("OOD benign alarm ratio")
    ax.set_ylabel("High-purity attack detection")
    ax.set_title(title)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out, dpi=180)
    plt.close(fig)


def plot_training_curves(history_df: pd.DataFrame, model_name: str, out: Path) -> None:
    df = history_df[history_df["model"].eq(model_name)].copy()
    if df.empty:
        return
    fig, ax = plt.subplots(figsize=(9.5, 5.6))
    for seed in sorted(df["seed"].unique()):
        d = df[df["seed"].eq(seed)]
        ax.plot(d["epoch"], d["train_loss"], label=f"seed{seed} train")
        ax.plot(d["epoch"], d["val_loss"], linestyle="--", label=f"seed{seed} val")
    ax.set_xlabel("epoch")
    ax.set_ylabel("MSE loss")
    ax.set_title(f"{model_name} training curves")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=180)
    plt.close(fig)


def append_map(run_tag: str) -> None:
    p = TRACKED_RUNS_DIR / "mainline_docs" / "mainline_experiment_map.md"
    if not p.exists():
        return
    text = p.read_text(encoding="utf-8-sig")
    if f"`{run_tag}`" in text:
        return
    text += f"\n- `{run_tag}`: Modern tabular deep baselines on original-frontend 100D stronger OOD (`FT-Transformer AE`, `RTDL-ResNet AE`); path: `runs/{run_tag}/`.\n"
    p.write_text(text, encoding="utf-8")


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    ap = argparse.ArgumentParser(description="Modern tabular deep baselines for frontend100 stronger OOD.")
    ap.add_argument("--run-tag", default=f"frontend100_modern_tabular_baselines_{today}")
    ap.add_argument("--source-root", type=Path, default=WORKTREE_ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master")
    ap.add_argument("--stage2-indices-json", type=Path, default=None)
    ap.add_argument("--models", default="ft_transformer_ae,rtdl_resnet_ae")
    ap.add_argument("--seeds", default="101,202,303")
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--batch-size", type=int, default=512)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--weight-decay", type=float, default=1e-6)
    ap.add_argument("--patience", type=int, default=8)
    ap.add_argument("--val-ratio", type=float, default=0.2)
    ap.add_argument("--device", default="auto")
    ap.add_argument("--smoke-fit-n", type=int, default=0)
    ap.add_argument("--calibration-budget", type=int, default=5000)
    ap.add_argument("--scan-points", type=int, default=1200)
    ap.add_argument("--benchmark-repeats", type=int, default=3)
    ap.add_argument("--ft-d-token", type=int, default=64)
    ap.add_argument("--ft-n-heads", type=int, default=8)
    ap.add_argument("--ft-n-blocks", type=int, default=3)
    ap.add_argument("--ft-attn-dropout", type=float, default=0.2)
    ap.add_argument("--ft-ffn-dropout", type=float, default=0.1)
    ap.add_argument("--resnet-d-hidden", type=int, default=256)
    ap.add_argument("--resnet-n-blocks", type=int, default=4)
    ap.add_argument("--resnet-dropout", type=float, default=0.1)
    ap.add_argument("--latent-dim", type=int, default=64)
    ap.add_argument("--decoder-hidden", type=int, default=256)
    ap.add_argument("--skip-register", action="store_true")
    args = ap.parse_args()

    seeds = [int(x) for x in args.seeds.split(",") if x.strip()]
    models = [x.strip() for x in args.models.split(",") if x.strip()]
    device = choose_device(args.device)
    artifact_runs_root = resolve_artifact_runs_root()
    out = resolve_output_dir(args.run_tag)
    plot_dir = out / "modern_tabular_plots"
    ckpt_dir = out / "checkpoints"
    out.mkdir(parents=True, exist_ok=True)
    plot_dir.mkdir(exist_ok=True)
    ckpt_dir.mkdir(exist_ok=True)
    (out / "command.txt").write_text("python " + " ".join(sys.argv) + "\n", encoding="utf-8")

    data = args.source_root / "runs" / "frontend100_crosscapture_stage1_2026-03-25" / "data"
    x_all = pd.read_csv(data / "id_source_100.csv", header=None, nrows=13000).to_numpy(np.float64)
    x_fit = x_all[:8000]
    if args.smoke_fit_n > 0:
        x_fit = x_fit[: min(len(x_fit), args.smoke_fit_n)]
    x_id = x_all[8000:13000]
    x_ood = pd.read_csv(data / "ood_benign_source_100.csv", header=None).to_numpy(np.float64)
    x_attack = pd.read_csv(args.source_root / "runs" / "frontend100_joint_eval_stage1_2026-03-31" / "data" / "attack_source_100.csv", header=None).to_numpy(np.float64)
    if args.stage2_indices_json is not None:
        stage2_idx_payload = json.loads(args.stage2_indices_json.read_text(encoding="utf-8"))
        idx = {
            "high": np.asarray(stage2_idx_payload["high"], dtype=np.int64),
            "mixed": np.asarray(stage2_idx_payload["mixed"], dtype=np.int64),
        }
    else:
        stage2 = json.loads((args.source_root / "runs" / "frontend100_joint_eval_stage2_2026-04-01" / "attack_manifest_stage2.json").read_text(encoding="utf-8-sig"))
        idx = resc.build_stage2_indices(stage2)
    scaler = StandardScaler().fit(x_fit)
    x_fit_z = scaler.transform(x_fit).astype(np.float32)
    x_id_z = scaler.transform(x_id).astype(np.float32)
    x_ood_z = scaler.transform(x_ood).astype(np.float32)
    x_attack_z = scaler.transform(x_attack).astype(np.float32)
    x_bench = np.vstack([x_id_z, x_ood_z[: len(x_id_z)], x_attack_z[: len(x_id_z)]])

    rows: List[Dict] = []
    diag_rows: List[Dict] = []
    hist_rows: List[Dict] = []
    cost_rows: List[Dict] = []
    for model_name in models:
        for seed in seeds:
            print(f"[fit] {model_name} seed={seed}", flush=True)
            set_seed(seed)
            x_train_z, x_val_z = split_train_val(x_fit_z, args.val_ratio, seed)
            model = make_model(model_name, x_fit.shape[1], args)
            t0 = time.perf_counter()
            model, hist, best_val, best_epoch = train_model(model, x_train_z, x_val_z, args, device)
            train_time = time.perf_counter() - t0
            ckpt = ckpt_dir / f"{model_name}_seed{seed}.pt"
            torch.save({"model": model_name, "seed": seed, "state_dict": model.state_dict()}, ckpt)
            ckpt_bytes = int(ckpt.stat().st_size)
            n_params = int(sum(p.numel() for p in model.parameters()))
            sid = score_model(model, x_id_z, args.batch_size, device)
            sood = score_model(model, x_ood_z, args.batch_size, device)
            satt = score_model(model, x_attack_z, args.batch_size, device)
            bench = bench_model(model, x_bench, args.batch_size, device, args.benchmark_repeats)
            rows.extend(ext.eval_scores(model_name, model_name, "recon_rmse", seed, sid, sood, satt, idx["high"], idx["mixed"], args.calibration_budget, args.scan_points, {
                "baseline_category": "modern_tabular_unsupervised",
                "training_mode": "unsupervised_id_only_reconstruction",
                "uses_attack_labels": False,
                "source_mode": "computed_now",
                "checkpoint_bytes": ckpt_bytes,
                "torch_param_count": n_params,
                "train_time_sec": float(train_time),
                "infer_ms_per_sample": float(bench["ms_per_sample_mean"]),
            }))
            q995 = float(np.quantile(sid, 0.995))
            q995_row = resc.eval_threshold(q995, sid, sood, sood[args.calibration_budget:], satt, idx["high"], idx["mixed"])
            rows.append({
                "row_type": "per_seed",
                "object_label": model_name,
                "detector_family": model_name,
                "score_label": "recon_rmse",
                "seed": seed,
                "policy_name": "fixed_id_q995",
                "selection_feasible": True,
                "threshold_source": "ID benign q99.5",
                "roc_auc_attack_high_vs_ood_eval": float(resc.compute_auc(sood[args.calibration_budget:], satt[idx["high"]])),
                **q995_row,
                "baseline_category": "modern_tabular_unsupervised",
                "training_mode": "unsupervised_id_only_reconstruction",
                "uses_attack_labels": False,
                "source_mode": "computed_now",
                "checkpoint_bytes": ckpt_bytes,
                "torch_param_count": n_params,
                "train_time_sec": float(train_time),
                "infer_ms_per_sample": float(bench["ms_per_sample_mean"]),
            })
            hist_rows.extend([{"model": model_name, "seed": seed, **r} for r in hist])
            diag_rows.append({
                "model": model_name,
                "seed": seed,
                "best_epoch": best_epoch,
                "best_val_loss": best_val,
                "train_time_sec": train_time,
                "checkpoint_bytes": ckpt_bytes,
                "torch_param_count": n_params,
                "id_score_mean": float(np.mean(sid)),
                "ood_score_mean": float(np.mean(sood)),
                "attack_score_mean": float(np.mean(satt)),
                **bench,
            })
            cost_rows.append({"object_label": model_name, "seed": seed, "checkpoint_bytes": ckpt_bytes, "torch_param_count": n_params, "train_time_sec": train_time, **bench})

    rows.extend(ext.load_reference_rows(artifact_runs_root / "frontend100_locked_candidate_multiseed_2026-04-06" / "multiseed_locked_candidate_results.csv", seeds).to_dict("records"))
    rows.extend(load_deep_svdd_rows(artifact_runs_root / "frontend100_deep_svdd_baseline_2026-04-09" / "deep_svdd_results.csv", seeds).to_dict("records"))
    per = pd.DataFrame(rows)
    agg = ext.aggregate(per)
    frozen = load_frozen_refs(artifact_runs_root / "frontend100_final_candidate_audit_2026-04-08" / "final_candidate_main_table.csv")
    if not frozen.empty:
        agg = pd.concat([agg, frozen], ignore_index=True, sort=False)
    hist_df = pd.DataFrame(hist_rows)
    diag_df = pd.DataFrame(diag_rows)
    cost_df = pd.DataFrame(cost_rows)
    cost_agg = cost_df.groupby("object_label", as_index=False)[["checkpoint_bytes", "torch_param_count", "train_time_sec", "ms_per_sample_mean", "samples_per_sec_mean"]].mean(numeric_only=True)

    per.to_csv(out / "modern_tabular_results.csv", index=False)
    per.to_csv(out / "results.csv", index=False)
    agg.to_csv(out / "modern_tabular_aggregate.csv", index=False)
    diag_df.to_csv(out / "modern_tabular_diagnostics.csv", index=False)
    hist_df.to_csv(out / "modern_tabular_training_history.csv", index=False)
    cost_df.to_csv(out / "modern_tabular_costs.csv", index=False)
    cost_agg.to_csv(out / "modern_tabular_costs_aggregate.csv", index=False)

    plot_policy(agg, "fixed_id_q99", plot_dir / "fixed_tradeoff_modern_tabular_q99.png", "Modern tabular baselines vs references (fixed ID q99)")
    plot_policy(agg, "fixed_id_q995", plot_dir / "fixed_tradeoff_modern_tabular_q995.png", "Modern tabular baselines vs frozen references (fixed ID q995)")
    ext.plot_bar(agg, "fixed_id_q99", "attack_detection_high_purity", plot_dir / "fixed_detection_bar_q99.png", "Fixed q99 high-purity attack detection")
    ext.plot_bar(agg, "fixed_id_q99", "ood_alarm_ratio_eval", plot_dir / "fixed_alarm_bar_q99.png", "Fixed q99 OOD benign alarm")
    for model_name in models:
        plot_training_curves(hist_df, model_name, plot_dir / f"training_curves_{model_name}.png")

    q99 = agg[agg["policy_name"].eq("fixed_id_q99")].copy()
    q995 = agg[agg["policy_name"].eq("fixed_id_q995")].copy()
    cols99 = ["object_label", "baseline_category", "ood_alarm_ratio_eval_mean", "ood_alarm_ratio_eval_std", "attack_detection_high_purity_mean", "attack_detection_high_purity_std", "roc_auc_attack_high_vs_ood_eval_mean"]
    cols995 = ["object_label", "baseline_category", "ood_alarm_ratio_eval_mean", "attack_detection_high_purity_mean", "id_alarm_ratio_mean", "roc_auc_attack_high_vs_ood_eval_mean"]
    (out / "modern_tabular_results.md").write_text("# Modern Tabular Baseline Results\n\n## Fixed q99 Aggregate\n" + ext.md_table(q99[cols99].sort_values("object_label")) + "\n\n## Fixed q995 Aggregate\n" + ext.md_table(q995[cols995].sort_values("object_label")) + "\n\n## Cost Aggregate\n" + ext.md_table(cost_agg.sort_values("object_label")) + "\n", encoding="utf-8")
    model_text = ", ".join(f"`{m}`" for m in models)
    summary = "\n".join([
        "# Modern Tabular Baseline Summary",
        "",
        "- Data: original-frontend 100D + stronger OOD protocol.",
        f"- Models: {model_text}.",
        "- Training: ID-only reconstruction with ID validation early stopping.",
        f"- Seeds: `{','.join(str(s) for s in seeds)}`.",
        f"- Device: `{device}`.",
        "",
        "## Fixed q99 Aggregate",
        ext.md_table(q99[cols99].sort_values("object_label")),
        "",
        "## Fixed q995 Aggregate",
        ext.md_table(q995[cols995].sort_values("object_label")),
        "",
        "## Interpretation",
        "- Use this run to decide whether modern tabular deep baselines materially threaten the stronger-OOD covariance-tail story.",
        "- Frozen strongest paper candidate remains `transformer_ensemble_main_candidate` under fixed_id_q995.",
    ]) + "\n"
    (out / "modern_tabular_summary.md").write_text(summary, encoding="utf-8")
    (out / "summary.md").write_text(summary, encoding="utf-8")
    cfg = {
        "stage": "frontend100_modern_tabular_baselines",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_tag": args.run_tag,
        "models": models,
        "seeds": seeds,
        "stage2_indices_json": str(args.stage2_indices_json) if args.stage2_indices_json is not None else None,
        "outputs": {
            "results": str(out / "modern_tabular_results.csv"),
            "aggregate": str(out / "modern_tabular_aggregate.csv"),
            "summary": str(out / "summary.md"),
            "plots": str(plot_dir),
        },
    }
    (out / "modern_tabular_manifest.json").write_text(json.dumps(ext.clean(cfg), indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "config.json").write_text(json.dumps(ext.clean(cfg), indent=2, ensure_ascii=False), encoding="utf-8")
    if not args.skip_register:
        append_map(args.run_tag)
    print(f"[done] modern tabular baseline output: {out}", flush=True)


if __name__ == "__main__":
    main()

