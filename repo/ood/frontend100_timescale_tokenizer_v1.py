from __future__ import annotations

import argparse
import json
import random
import re
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

SCALES = ["5", "3", "1", "0.1", "0.01"]
SCALE_RE = re.compile(r"^[A-Za-z0-9_]+?_(5|3|1|0\.1|0\.01)_.+$")


class TimescaleTransformerAE(nn.Module):
    def __init__(self, feature_dim: int, seq_len: int, d_model: int = 64, nhead: int = 4, num_layers: int = 2, dropout: float = 0.0):
        super().__init__()
        self.feature_dim = int(feature_dim)
        self.seq_len = int(seq_len)
        self.in_proj = nn.Linear(feature_dim, d_model)
        self.pos = nn.Parameter(torch.zeros(1, seq_len, d_model))
        enc = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=max(128, d_model * 4),
            dropout=float(dropout),
            batch_first=True,
            activation="gelu",
        )
        self.encoder = nn.TransformerEncoder(enc, num_layers=int(num_layers))
        self.out_proj = nn.Linear(d_model, feature_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.in_proj(x) + self.pos
        h = self.encoder(h)
        return self.out_proj(h)


class TimescaleTokenMLPAE(nn.Module):
    def __init__(self, feature_dim: int, seq_len: int, d_model: int = 64, bottleneck: int = 96):
        super().__init__()
        self.seq_len = int(seq_len)
        self.feature_dim = int(feature_dim)
        self.in_proj = nn.Sequential(
            nn.Linear(feature_dim, d_model),
            nn.GELU(),
            nn.Linear(d_model, d_model),
        )
        flat_dim = self.seq_len * d_model
        bottleneck = int(min(max(32, bottleneck), max(64, flat_dim)))
        self.bottleneck = nn.Sequential(
            nn.LayerNorm(flat_dim),
            nn.Linear(flat_dim, bottleneck),
            nn.GELU(),
            nn.Linear(bottleneck, flat_dim),
            nn.GELU(),
        )
        self.out_proj = nn.Sequential(
            nn.Linear(d_model, d_model),
            nn.GELU(),
            nn.Linear(d_model, feature_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.in_proj(x)
        b, s, d = h.shape
        h = self.bottleneck(h.reshape(b, s * d)).reshape(b, s, d)
        return self.out_proj(h)


class FlatAE(nn.Module):
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

    def forward(self, x: torch.Tensor) -> torch.Tensor:
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
    return json.loads(path.read_text(encoding="utf-8-sig"))


def md_table(df: pd.DataFrame) -> str:
    return resc.md_table(df)


def parse_header_scale(header: str) -> str:
    m = SCALE_RE.match(header)
    if not m:
        raise ValueError(f"Header does not match timescale pattern: {header}")
    return str(m.group(1))


def build_timescale_index_map(headers: List[str]) -> Tuple[List[int], Dict[str, List[int]]]:
    groups: Dict[str, List[int]] = {s: [] for s in SCALES}
    for i, h in enumerate(headers):
        groups[parse_header_scale(h)].append(i)
    counts = {k: len(v) for k, v in groups.items()}
    if len(set(counts.values())) != 1:
        raise ValueError(f"Uneven timescale group sizes: {counts}")
    if counts[SCALES[0]] * len(SCALES) != len(headers):
        raise ValueError(f"Timescale regrouping does not cover all headers: {counts}, total={len(headers)}")
    order: List[int] = []
    for s in SCALES:
        order.extend(groups[s])
    return order, groups


def regroup_by_timescale(x: np.ndarray, order: List[int], token_dim: int) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    z = x[:, order]
    return z.reshape(len(z), len(SCALES), token_dim)


def standardize_flat(x: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    return ((x - mean.reshape(1, -1)) / std.reshape(1, -1)).astype(np.float32)


def train_model(model: nn.Module, x_train: np.ndarray, epochs: int, batch_size: int, lr: float, device: str) -> List[float]:
    model.to(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    crit = nn.MSELoss()
    ds = TensorDataset(torch.from_numpy(x_train.astype(np.float32)))
    loader = DataLoader(ds, batch_size=batch_size, shuffle=True, drop_last=False)
    losses: List[float] = []
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


def score_token_model(model: nn.Module, x: np.ndarray, batch_size: int, device: str) -> np.ndarray:
    model.to(device)
    model.eval()
    out: List[np.ndarray] = []
    with torch.no_grad():
        for st in range(0, len(x), batch_size):
            xb = torch.from_numpy(x[st : st + batch_size].astype(np.float32)).to(device)
            err = (model(xb) - xb) ** 2
            score = torch.sqrt(torch.mean(err, dim=(1, 2))).detach().cpu().numpy()
            out.append(score)
    return np.concatenate(out).astype(np.float64)


def score_flat_model(model: nn.Module, x: np.ndarray, batch_size: int, device: str) -> np.ndarray:
    model.to(device)
    model.eval()
    out: List[np.ndarray] = []
    with torch.no_grad():
        for st in range(0, len(x), batch_size):
            xb = torch.from_numpy(x[st : st + batch_size].astype(np.float32)).to(device)
            err = (model(xb) - xb) ** 2
            score = torch.sqrt(torch.mean(err, dim=1)).detach().cpu().numpy()
            out.append(score)
    return np.concatenate(out).astype(np.float64)


def eval_scores(
    object_label: str,
    detector_family: str,
    score_label: str,
    seed: int,
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
                "seed": seed,
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
                "seed": seed,
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
    refs: List[Dict] = []
    p = WORKTREE_ROOT / "runs" / "frontend100_covariance_regularized_v1_2026-04-07" / "covariance_regularized_v1_results.csv"
    if p.exists():
        df = pd.read_csv(p)
        keep = {
            "da__default_score",
            "transformer__default_score",
            "transformer_tailreg__default_score",
            "latent_swap_spike_mix_no_compact__log_weighted_z_rmse0.5_cos1.0_old",
        }
        ref = df[df["object_label"].isin(keep)].copy()
        ref["source_mode"] = "reused_reference"
        refs.extend(ref.to_dict("records"))
    return refs


def plot_tradeoff(df: pd.DataFrame, out: Path) -> None:
    fixed = df[(df["policy_name"] == "fixed_id_q99") & (df["selection_feasible"].astype(bool))].copy()
    plt.figure(figsize=(10.5, 6.8))
    colors = {
        "timescale_transformer_v1": "#1f77b4",
        "timescale_token_mlp_control": "#ff7f0e",
        "flat_ae_100d_control": "#2ca02c",
        "da": "#d62728",
        "transformer": "#7f7f7f",
        "transformer_tailreg": "#9467bd",
        "latent_swap_spike_mix_no_compact": "#8c564b",
    }
    marks = {
        "timescale_transformer_v1": "o",
        "timescale_token_mlp_control": "^",
        "flat_ae_100d_control": "s",
        "da": "D",
        "transformer": "x",
        "transformer_tailreg": "P",
        "latent_swap_spike_mix_no_compact": "*",
    }
    for _, r in fixed.iterrows():
        fam = str(r["detector_family"])
        color = colors.get(fam, "#7f7f7f")
        marker = marks.get(fam, "o")
        x = float(r["ood_alarm_ratio_eval"])
        y = float(r["attack_detection_high_purity"])
        plt.scatter(x, y, c=color, marker=marker, s=88)
        plt.text(x + 0.004, y + 0.006, str(r["object_label"]), fontsize=8)
    plt.xlabel("OOD benign alarm ratio (fixed q99)")
    plt.ylabel("High-purity attack detection")
    plt.title("Timescale tokenizer v1 fixed trade-off")
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(out, dpi=180)
    plt.close()


def plot_distribution(id_scores: np.ndarray, ood_scores: np.ndarray, attack_scores: np.ndarray, threshold: float, out: Path, title: str) -> None:
    plt.figure(figsize=(9.5, 5.8))
    bins = 70
    plt.hist(id_scores, bins=bins, density=True, alpha=0.35, label="ID benign")
    plt.hist(ood_scores, bins=bins, density=True, alpha=0.35, label="OOD benign eval")
    plt.hist(attack_scores, bins=bins, density=True, alpha=0.35, label="attack high")
    plt.axvline(threshold, color="black", linestyle="--", linewidth=1.2, label="fixed q99")
    plt.xlabel("score")
    plt.ylabel("density")
    plt.title(title)
    plt.grid(alpha=0.2)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out, dpi=180)
    plt.close()


def append_map(run_tag: str) -> None:
    p = WORKTREE_ROOT / "runs" / "mainline_docs" / "mainline_experiment_map.md"
    if not p.exists():
        return
    text = p.read_text(encoding="utf-8")
    if f"`{run_tag}`" in text:
        return
    entry = f"\n- `{run_tag}`: Frontend100 TimescaleTokenizer-v1 single-seed minimal experiment with header-aware 5x20 regrouping; path: `runs/{run_tag}/`.\n"
    p.write_text(text.rstrip() + entry, encoding="utf-8")


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    ap = argparse.ArgumentParser(description="Header-aware timescale tokenizer v1 for frontend100.")
    ap.add_argument("--run-tag", default=f"frontend100_timescale_tokenizer_v1_{today}")
    ap.add_argument("--source-root", type=Path, default=WORKTREE_ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master")
    ap.add_argument(
        "--header-path",
        type=Path,
        default=WORKTREE_ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master" / "runs" / "frontend100_crosscapture_stage1_2026-03-25" / "extract_id_7_6" / "feature_headers.txt",
    )
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--batch-size", type=int, default=256)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--train-samples", type=int, default=8000)
    ap.add_argument("--id-eval-samples", type=int, default=5000)
    ap.add_argument("--calibration-budget", type=int, default=5000)
    ap.add_argument("--scan-points", type=int, default=1200)
    ap.add_argument("--d-model", type=int, default=64)
    ap.add_argument("--num-layers", type=int, default=2)
    ap.add_argument("--nhead", type=int, default=4)
    ap.add_argument("--token-mlp-bottleneck", type=int, default=96)
    ap.add_argument("--flat-hidden-dim", type=int, default=256)
    ap.add_argument("--flat-bottleneck", type=int, default=64)
    ap.add_argument("--smoke-fit-n", type=int, default=0)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = ap.parse_args()

    set_seed(args.seed)
    out = WORKTREE_ROOT / "runs" / args.run_tag
    out.mkdir(parents=True, exist_ok=True)
    plot_dir = out / "timescale_tokenizer_v1_plots"
    plot_dir.mkdir(exist_ok=True)
    (out / "command.txt").write_text("python " + " ".join(sys.argv) + "\n", encoding="utf-8")

    headers = [ln.strip() for ln in args.header_path.read_text(encoding="utf-8-sig").splitlines() if ln.strip()]
    order, groups = build_timescale_index_map(headers)
    token_dim = len(groups[SCALES[0]])

    source = args.source_root
    data = source / "runs" / "frontend100_crosscapture_stage1_2026-03-25" / "data"
    fit_n = int(args.train_samples if args.smoke_fit_n <= 0 else min(args.train_samples, args.smoke_fit_n))
    id_rows_needed = fit_n + args.id_eval_samples
    x_id_src = pd.read_csv(data / "id_source_100.csv", header=None, nrows=id_rows_needed).to_numpy(np.float32)
    x_ood_src = pd.read_csv(data / "ood_benign_source_100.csv", header=None).to_numpy(np.float32)
    attack_csv = source / "runs" / "frontend100_joint_eval_stage1_2026-03-31" / "data" / "attack_source_100.csv"
    x_attack_src = pd.read_csv(attack_csv, header=None).to_numpy(np.float32)
    stage2 = load_json(source / "runs" / "frontend100_joint_eval_stage2_2026-04-01" / "attack_manifest_stage2.json")
    stage2_idx = resc.build_stage2_indices(stage2)

    x_train = x_id_src[:fit_n]
    x_id = x_id_src[fit_n : fit_n + args.id_eval_samples]
    x_ood = x_ood_src
    x_attack = x_attack_src

    mean = x_train.mean(axis=0)
    std = np.maximum(x_train.std(axis=0), 1e-6)
    z_train_flat = standardize_flat(x_train, mean, std)
    z_id_flat = standardize_flat(x_id, mean, std)
    z_ood_flat = standardize_flat(x_ood, mean, std)
    z_attack_flat = standardize_flat(x_attack, mean, std)

    z_train_tok = regroup_by_timescale(z_train_flat, order, token_dim)
    z_id_tok = regroup_by_timescale(z_id_flat, order, token_dim)
    z_ood_tok = regroup_by_timescale(z_ood_flat, order, token_dim)
    z_attack_tok = regroup_by_timescale(z_attack_flat, order, token_dim)

    high = stage2_idx["high"]
    mixed = stage2_idx["mixed"]

    rows: List[Dict] = []
    diagnostics: List[Dict] = []
    rows.extend(load_reference_rows())

    print("[fit] timescale transformer", flush=True)
    tfm = TimescaleTransformerAE(feature_dim=token_dim, seq_len=len(SCALES), d_model=args.d_model, nhead=args.nhead, num_layers=args.num_layers)
    tfm_losses = train_model(tfm, z_train_tok, args.epochs, args.batch_size, args.lr, args.device)
    tfm_id = score_token_model(tfm, z_id_tok, args.batch_size, args.device)
    tfm_ood = score_token_model(tfm, z_ood_tok, args.batch_size, args.device)
    tfm_attack = score_token_model(tfm, z_attack_tok, args.batch_size, args.device)
    rows.extend(
        eval_scores(
            object_label="timescale_transformer_token_v1",
            detector_family="timescale_transformer_v1",
            score_label="rmse_full_tokens",
            seed=args.seed,
            score_id=tfm_id,
            score_ood=tfm_ood,
            score_attack=tfm_attack,
            high_idx=high,
            mixed_idx=mixed,
            budget=args.calibration_budget,
            scan_points=args.scan_points,
            extra={"seq_len": len(SCALES), "token_dim": token_dim, "source_mode": "computed_now"},
        )
    )
    diagnostics.append(
        {
            "object_label": "timescale_transformer_token_v1",
            "train_loss_start": float(tfm_losses[0]),
            "train_loss_end": float(tfm_losses[-1]),
            "train_loss_min": float(np.min(tfm_losses)),
            "token_dim": token_dim,
            "seq_len": len(SCALES),
        }
    )

    print("[fit] timescale token mlp control", flush=True)
    mlp = TimescaleTokenMLPAE(feature_dim=token_dim, seq_len=len(SCALES), d_model=args.d_model, bottleneck=args.token_mlp_bottleneck)
    mlp_losses = train_model(mlp, z_train_tok, args.epochs, args.batch_size, args.lr, args.device)
    mlp_id = score_token_model(mlp, z_id_tok, args.batch_size, args.device)
    mlp_ood = score_token_model(mlp, z_ood_tok, args.batch_size, args.device)
    mlp_attack = score_token_model(mlp, z_attack_tok, args.batch_size, args.device)
    rows.extend(
        eval_scores(
            object_label="timescale_token_mlp_v1",
            detector_family="timescale_token_mlp_control",
            score_label="rmse_full_tokens",
            seed=args.seed,
            score_id=mlp_id,
            score_ood=mlp_ood,
            score_attack=mlp_attack,
            high_idx=high,
            mixed_idx=mixed,
            budget=args.calibration_budget,
            scan_points=args.scan_points,
            extra={"seq_len": len(SCALES), "token_dim": token_dim, "source_mode": "computed_now"},
        )
    )
    diagnostics.append(
        {
            "object_label": "timescale_token_mlp_v1",
            "train_loss_start": float(mlp_losses[0]),
            "train_loss_end": float(mlp_losses[-1]),
            "train_loss_min": float(np.min(mlp_losses)),
            "token_dim": token_dim,
            "seq_len": len(SCALES),
        }
    )

    print("[fit] flat 100d ae control", flush=True)
    flat = FlatAE(input_dim=z_train_flat.shape[1], hidden_dim=args.flat_hidden_dim, bottleneck=args.flat_bottleneck)
    flat_losses = train_model(flat, z_train_flat, args.epochs, args.batch_size, args.lr, args.device)
    flat_id = score_flat_model(flat, z_id_flat, args.batch_size, args.device)
    flat_ood = score_flat_model(flat, z_ood_flat, args.batch_size, args.device)
    flat_attack = score_flat_model(flat, z_attack_flat, args.batch_size, args.device)
    rows.extend(
        eval_scores(
            object_label="flat_ae_100d_control",
            detector_family="flat_ae_100d_control",
            score_label="rmse_flat_100d",
            seed=args.seed,
            score_id=flat_id,
            score_ood=flat_ood,
            score_attack=flat_attack,
            high_idx=high,
            mixed_idx=mixed,
            budget=args.calibration_budget,
            scan_points=args.scan_points,
            extra={"seq_len": 1, "token_dim": z_train_flat.shape[1], "source_mode": "computed_now"},
        )
    )
    diagnostics.append(
        {
            "object_label": "flat_ae_100d_control",
            "train_loss_start": float(flat_losses[0]),
            "train_loss_end": float(flat_losses[-1]),
            "train_loss_min": float(np.min(flat_losses)),
            "token_dim": int(z_train_flat.shape[1]),
            "seq_len": 1,
        }
    )

    df = pd.DataFrame(rows)
    diag = pd.DataFrame(diagnostics)
    df.to_csv(out / "timescale_tokenizer_v1_results.csv", index=False)
    df.to_csv(out / "results.csv", index=False)
    diag.to_csv(out / "timescale_tokenizer_v1_diagnostics.csv", index=False)

    fixed = df[(df["policy_name"].eq("fixed_id_q99")) & (df["selection_feasible"].astype(bool))].copy()
    fixed_ours = fixed[fixed["detector_family"].isin(["timescale_transformer_v1", "timescale_token_mlp_control", "flat_ae_100d_control"])].copy()
    results_md = "# Timescale Tokenizer v1 Results\n\n"
    results_md += md_table(
        fixed[
            [
                "object_label",
                "detector_family",
                "score_label",
                "ood_alarm_ratio_eval",
                "attack_detection_high_purity",
                "roc_auc_attack_high_vs_ood_eval",
            ]
        ].sort_values(["ood_alarm_ratio_eval", "attack_detection_high_purity"], ascending=[True, False]).fillna("")
    )
    (out / "timescale_tokenizer_v1_results.md").write_text(results_md, encoding="utf-8")

    plot_tradeoff(df, plot_dir / "fixed_tradeoff_timescale_tokenizer_v1.png")
    if not fixed_ours.empty:
        best = fixed_ours.sort_values(["ood_alarm_ratio_eval", "attack_detection_high_purity"], ascending=[True, False]).iloc[0]
        best_id = best["object_label"]
        best_scores = {
            "timescale_transformer_token_v1": (tfm_id, tfm_ood[args.calibration_budget :], tfm_attack[high]),
            "timescale_token_mlp_v1": (mlp_id, mlp_ood[args.calibration_budget :], mlp_attack[high]),
            "flat_ae_100d_control": (flat_id, flat_ood[args.calibration_budget :], flat_attack[high]),
        }
        if best_id in best_scores:
            sid, sood_eval, satt_high = best_scores[best_id]
            thr = float(np.quantile(sid, 0.99))
            plot_distribution(sid, sood_eval, satt_high, thr, plot_dir / "score_distribution_best_model.png", f"{best_id} score distribution (fixed q99)")

    summary = "# Frontend100 Timescale Tokenizer v1 Summary\n\n"
    summary += "- Single-seed minimal experiment on original frontend100.\n"
    summary += "- 100D input is regrouped by feature headers into `5 x 20` timescale tokens (`5,3,1,0.1,0.01`).\n"
    summary += "- This is header-aware regrouping, not naive reshape.\n"
    summary += "- Controls: token-MLP without attention, and flat 100D AE.\n\n"
    summary += "## Fixed q99 Results\n\n"
    summary += md_table(
        fixed[
            [
                "object_label",
                "detector_family",
                "ood_alarm_ratio_eval",
                "attack_detection_high_purity",
                "roc_auc_attack_high_vs_ood_eval",
            ]
        ].sort_values(["ood_alarm_ratio_eval", "attack_detection_high_purity"], ascending=[True, False]).fillna("")
    )
    summary += "\n## Interpretation\n\n"
    if not fixed_ours.empty:
        best = fixed_ours.sort_values(["ood_alarm_ratio_eval", "attack_detection_high_purity"], ascending=[True, False]).iloc[0]
        summary += f"- Best tokenizer-side point: `{best['object_label']}` with alarm `{best['ood_alarm_ratio_eval']:.4f}` and detection `{best['attack_detection_high_purity']:.4f}`.\n"
    summary += "- Compare this line against `da`, `transformer`, `transformer_tailreg`, and latent no-compact references under the same fixed-q99 policy.\n"
    summary += "- Success criterion: lower OOD benign alarm than flat 100D control without obvious detection collapse.\n"
    (out / "timescale_tokenizer_v1_summary.md").write_text(summary, encoding="utf-8")
    (out / "summary.md").write_text(summary, encoding="utf-8")

    cfg = {
        "stage": "frontend100_timescale_tokenizer_v1",
        "run_tag": args.run_tag,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "seed": args.seed,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "lr": args.lr,
        "device": args.device,
        "header_path": str(args.header_path),
        "scales": SCALES,
        "group_sizes": {k: len(v) for k, v in groups.items()},
        "smoke_fit_n": int(args.smoke_fit_n),
        "outputs": {
            "results": str(out / "timescale_tokenizer_v1_results.csv"),
            "diagnostics": str(out / "timescale_tokenizer_v1_diagnostics.csv"),
            "summary": str(out / "summary.md"),
            "plots": str(plot_dir),
        },
    }
    (out / "timescale_tokenizer_v1_config_manifest.json").write_text(json.dumps(clean(cfg), indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "config.json").write_text(json.dumps(clean(cfg), indent=2, ensure_ascii=False), encoding="utf-8")
    append_map(args.run_tag)
    print(f"[done] timescale tokenizer output: {out}", flush=True)


if __name__ == "__main__":
    main()

