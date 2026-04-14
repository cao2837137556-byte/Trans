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
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, TensorDataset

THIS_DIR = Path(__file__).resolve().parent
REPO_DIR = THIS_DIR.parent
WORKTREE_ROOT = REPO_DIR.parent
for p in [THIS_DIR, REPO_DIR]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from paths import ARTIFACT_RUNS_DIR, TRACKED_RUNS_DIR


class Encoder(nn.Module):
    def __init__(self, input_dim: int, hidden_dims: List[int], latent_dim: int):
        super().__init__()
        dims = [input_dim] + hidden_dims
        layers: List[nn.Module] = []
        for din, dout in zip(dims[:-1], dims[1:]):
            layers.extend([nn.Linear(din, dout), nn.ReLU(inplace=True)])
        layers.append(nn.Linear(dims[-1], latent_dim))
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class AutoEncoder(nn.Module):
    def __init__(self, input_dim: int, hidden_dims: List[int], latent_dim: int):
        super().__init__()
        self.encoder = Encoder(input_dim=input_dim, hidden_dims=hidden_dims, latent_dim=latent_dim)
        rev = [latent_dim] + list(reversed(hidden_dims)) + [input_dim]
        layers: List[nn.Module] = []
        for idx, (din, dout) in enumerate(zip(rev[:-1], rev[1:])):
            layers.append(nn.Linear(din, dout))
            if idx < len(rev) - 2:
                layers.append(nn.ReLU(inplace=True))
        self.decoder = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.decoder(self.encoder(x))


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


def build_stage2_indices(stage2_manifest: Dict) -> Dict[str, np.ndarray]:
    tsv_path = Path(stage2_manifest["source_tsv"])
    use_first_n = int(stage2_manifest["use_first_n"])
    bin_seconds = int(stage2_manifest["bin_seconds"])
    strong_bins = np.array(stage2_manifest["selected_bins"]["strong_bins"], dtype=np.int64)
    mixed_bins = np.array(stage2_manifest["selected_bins"]["mixed_bins"], dtype=np.int64)
    pkt = pd.read_csv(tsv_path, sep="\t", usecols=["frame.time_epoch"], nrows=use_first_n)
    ts = pd.to_numeric(pkt["frame.time_epoch"], errors="coerce").to_numpy(dtype=np.float64)
    ts = ts[np.isfinite(ts)]
    ts0 = float(np.min(ts))
    bins = ((ts - ts0) // bin_seconds).astype(np.int64)
    return {
        "all": np.arange(len(ts), dtype=np.int64),
        "high": np.where(np.isin(bins, strong_bins))[0],
        "mixed": np.where(np.isin(bins, mixed_bins))[0],
    }


def eval_threshold(
    threshold: float,
    id_scores: np.ndarray,
    ood_scores: np.ndarray,
    ood_eval_scores: np.ndarray,
    attack_scores: np.ndarray,
    high_idx: np.ndarray,
    mixed_idx: np.ndarray,
) -> Dict[str, float]:
    return {
        "threshold": float(threshold),
        "id_alarm_ratio": float(np.mean(id_scores > threshold)),
        "ood_alarm_ratio_full": float(np.mean(ood_scores > threshold)),
        "ood_alarm_ratio_eval": float(np.mean(ood_eval_scores > threshold)),
        "attack_detection_all": float(np.mean(attack_scores > threshold)),
        "attack_detection_high_purity": float(np.mean(attack_scores[high_idx] > threshold)),
        "attack_detection_boundary": float(np.mean(attack_scores[mixed_idx] > threshold)) if len(mixed_idx) > 0 else float("nan"),
    }


def choose_detection_floor(df: pd.DataFrame, det_floor: float) -> pd.Series | None:
    cand = df[df["attack_detection_high_purity"] >= det_floor].copy()
    if cand.empty:
        return None
    cand = cand.sort_values(["ood_alarm_ratio_eval", "threshold"], ascending=[True, False])
    return cand.iloc[0]


def compute_auc(ood_eval_scores: np.ndarray, attack_high_scores: np.ndarray) -> float:
    y = np.concatenate(
        [
            np.zeros(len(ood_eval_scores), dtype=np.int64),
            np.ones(len(attack_high_scores), dtype=np.int64),
        ]
    )
    s = np.concatenate([ood_eval_scores, attack_high_scores]).astype(np.float64)
    return float(roc_auc_score(y, s))


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def make_loader(x: np.ndarray, batch_size: int, shuffle: bool) -> DataLoader:
    ds = TensorDataset(torch.from_numpy(x.astype(np.float32)))
    return DataLoader(ds, batch_size=batch_size, shuffle=shuffle, drop_last=False)


def choose_device(device: str) -> str:
    if device != "auto":
        return device
    return "cuda" if torch.cuda.is_available() else "cpu"


def init_center(model: Encoder, loader: DataLoader, device: str, eps: float = 1e-3) -> torch.Tensor:
    model.eval()
    total = 0
    c = None
    with torch.no_grad():
        for (xb,) in loader:
            xb = xb.to(device)
            z = model(xb)
            part = torch.sum(z, dim=0)
            c = part if c is None else c + part
            total += len(xb)
    c = c / max(total, 1)
    c[(torch.abs(c) < eps) & (c < 0)] = -eps
    c[(torch.abs(c) < eps) & (c > 0)] = eps
    return c.detach()


def train_autoencoder(
    model: AutoEncoder,
    x_train: np.ndarray,
    epochs: int,
    batch_size: int,
    lr: float,
    device: str,
) -> List[float]:
    loader = make_loader(x_train, batch_size=batch_size, shuffle=True)
    model.to(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    crit = nn.MSELoss()
    losses: List[float] = []
    for _ in range(int(epochs)):
        model.train()
        total = 0.0
        count = 0
        for (xb,) in loader:
            xb = xb.to(device)
            opt.zero_grad()
            recon = model(xb)
            loss = crit(recon, xb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            opt.step()
            total += float(loss.detach().item()) * len(xb)
            count += len(xb)
        losses.append(total / max(count, 1))
    return losses


def train_svdd(
    encoder: Encoder,
    x_train: np.ndarray,
    center: torch.Tensor,
    epochs: int,
    batch_size: int,
    lr: float,
    weight_decay: float,
    device: str,
) -> List[float]:
    loader = make_loader(x_train, batch_size=batch_size, shuffle=True)
    encoder.to(device)
    center = center.to(device)
    opt = torch.optim.Adam(encoder.parameters(), lr=lr, weight_decay=weight_decay)
    losses: List[float] = []
    for _ in range(int(epochs)):
        encoder.train()
        total = 0.0
        count = 0
        for (xb,) in loader:
            xb = xb.to(device)
            opt.zero_grad()
            z = encoder(xb)
            dist = torch.sum((z - center[None, :]) ** 2, dim=1)
            loss = dist.mean()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(encoder.parameters(), 5.0)
            opt.step()
            total += float(loss.detach().item()) * len(xb)
            count += len(xb)
        losses.append(total / max(count, 1))
    return losses


def score_svdd(encoder: Encoder, center: torch.Tensor, x: np.ndarray, batch_size: int, device: str) -> np.ndarray:
    encoder.to(device)
    center = center.to(device)
    encoder.eval()
    out: List[np.ndarray] = []
    with torch.no_grad():
        for st in range(0, len(x), batch_size):
            xb = torch.from_numpy(x[st : st + batch_size].astype(np.float32)).to(device)
            z = encoder(xb)
            dist = torch.sum((z - center[None, :]) ** 2, dim=1)
            out.append(dist.detach().cpu().numpy().astype(np.float64))
    return np.concatenate(out, axis=0) if out else np.zeros((0,), dtype=np.float64)


def eval_scores(
    object_label: str,
    detector_family: str,
    score_label: str,
    seed: int,
    id_scores: np.ndarray,
    ood_scores: np.ndarray,
    attack_scores: np.ndarray,
    high_idx: np.ndarray,
    mixed_idx: np.ndarray,
    budget: int,
    scan_points: int,
    extra: Dict,
) -> List[Dict]:
    rows: List[Dict] = []
    ood_eval = ood_scores[budget:]
    auc = compute_auc(ood_eval_scores=ood_eval, attack_high_scores=attack_scores[high_idx])

    fixed_thr = float(np.quantile(id_scores, 0.99))
    row = eval_threshold(
        threshold=fixed_thr,
        id_scores=id_scores,
        ood_scores=ood_scores,
        ood_eval_scores=ood_eval,
        attack_scores=attack_scores,
        high_idx=high_idx,
        mixed_idx=mixed_idx,
    )
    rows.append(
        {
            "row_type": "per_seed",
            "object_label": object_label,
            "detector_family": detector_family,
            "score_label": score_label,
            "seed": seed,
            "policy_name": "fixed_id_q99",
            "selection_feasible": True,
            "threshold_source": "ID benign q99",
            "roc_auc_attack_high_vs_ood_eval": float(auc),
            **row,
            **extra,
        }
    )

    calib_n = int(min(max(1, budget), len(ood_scores) - 1))
    naive_thr = float(np.quantile(ood_scores[:calib_n], 0.99))
    row = eval_threshold(
        threshold=naive_thr,
        id_scores=id_scores,
        ood_scores=ood_scores,
        ood_eval_scores=ood_eval,
        attack_scores=attack_scores,
        high_idx=high_idx,
        mixed_idx=mixed_idx,
    )
    rows.append(
        {
            "row_type": "per_seed",
            "object_label": object_label,
            "detector_family": detector_family,
            "score_label": score_label,
            "seed": seed,
            "policy_name": "naive_calibrated_budget5000_target1pct",
            "selection_feasible": True,
            "threshold_source": "first 5000 OOD benign q99",
            "roc_auc_attack_high_vs_ood_eval": float(auc),
            **row,
            **extra,
        }
    )

    all_scores = np.concatenate([id_scores, ood_scores, attack_scores]).astype(np.float64)
    thresholds = np.unique(np.quantile(all_scores, np.linspace(0.0, 1.0, int(scan_points))))
    scan_rows = []
    for thr in thresholds:
        er = eval_threshold(
            threshold=float(thr),
            id_scores=id_scores,
            ood_scores=ood_scores,
            ood_eval_scores=ood_eval,
            attack_scores=attack_scores,
            high_idx=high_idx,
            mixed_idx=mixed_idx,
        )
        er["threshold"] = float(thr)
        scan_rows.append(er)
    scan_df = pd.DataFrame(scan_rows)
    det50 = choose_detection_floor(scan_df, 0.50)
    if det50 is None:
        rows.append(
            {
                "row_type": "per_seed",
                "object_label": object_label,
                "detector_family": detector_family,
                "score_label": score_label,
                "seed": seed,
                "policy_name": "det_floor_50pct_min_alarm",
                "selection_feasible": False,
                "threshold_source": "attack high-purity scan",
                "roc_auc_attack_high_vs_ood_eval": float(auc),
                **extra,
            }
        )
    else:
        rows.append(
            {
                "row_type": "per_seed",
                "object_label": object_label,
                "detector_family": detector_family,
                "score_label": score_label,
                "seed": seed,
                "policy_name": "det_floor_50pct_min_alarm",
                "selection_feasible": True,
                "threshold_source": "min OOD eval alarm subject to high-purity detection >= 50%",
                "roc_auc_attack_high_vs_ood_eval": float(auc),
                **det50.to_dict(),
                **extra,
            }
        )
    return rows


def aggregate(df: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        "id_alarm_ratio",
        "ood_alarm_ratio_eval",
        "attack_detection_high_purity",
        "attack_detection_boundary",
        "roc_auc_attack_high_vs_ood_eval",
    ]
    agg = (
        df.groupby(["object_label", "detector_family", "score_label", "policy_name"], as_index=False)[metrics]
        .agg(["mean", "std", "count"])
        .reset_index()
    )
    cols = []
    for c in agg.columns:
        if isinstance(c, tuple):
            cols.append(c[0] if c[1] == "" else f"{c[0]}_{c[1]}")
        else:
            cols.append(str(c))
    agg.columns = cols
    meta_cols = [c for c in ["baseline_category", "training_mode", "uses_attack_labels", "source_mode"] if c in df.columns]
    if meta_cols:
        meta = df.groupby(["object_label", "detector_family", "score_label", "policy_name"], as_index=False)[meta_cols].first()
        agg = agg.merge(meta, on=["object_label", "detector_family", "score_label", "policy_name"], how="left")
    return agg


def load_reference_rows(locked: Path, seeds: List[int]) -> pd.DataFrame:
    if not locked.exists():
        return pd.DataFrame()
    df = pd.read_csv(locked)
    keep_objects = {
        "da__default_score",
        "transformer_tailreg__default_score",
        "transformer__default_score",
        "latent_swap_spike_mix__log_weighted_z_rmse0.5_cos1.0",
    }
    keep_policies = {"fixed_id_q99", "naive_calibrated_budget5000_target1pct", "det_floor_50pct_min_alarm"}
    r = df[
        (df["row_type"].eq("per_seed"))
        & (df["object_label"].isin(keep_objects))
        & (df["policy_name"].isin(keep_policies))
        & (df["seed"].isin(seeds))
    ].copy()
    if r.empty:
        return r
    r["source_mode"] = "reused_existing_transformer_da_reference"
    r["baseline_category"] = "existing_reference"
    r["uses_attack_labels"] = False
    r["training_mode"] = "existing_reference"
    return r


def plot_fixed_tradeoff(agg: pd.DataFrame, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(10.5, 7.0))
    fixed = agg[agg["policy_name"].eq("fixed_id_q99")].copy()
    colors = {
        "existing_reference": "#7f7f7f",
        "external_unsupervised": "#1f77b4",
    }
    for _, r in fixed.iterrows():
        obj = str(r["object_label"])
        cat = str(r.get("baseline_category", "existing_reference"))
        color = colors.get(cat, "#2ca02c")
        marker = "^" if cat == "existing_reference" else "o"
        ax.errorbar(
            [float(r["ood_alarm_ratio_eval_mean"])],
            [float(r["attack_detection_high_purity_mean"])],
            xerr=[0.0 if pd.isna(r.get("ood_alarm_ratio_eval_std")) else float(r["ood_alarm_ratio_eval_std"])],
            yerr=[0.0 if pd.isna(r.get("attack_detection_high_purity_std")) else float(r["attack_detection_high_purity_std"])],
            fmt=marker,
            color=color,
            capsize=3,
        )
        label = obj.replace("__default_score", "").replace("__log_weighted_z_rmse0.5_cos1.0", "")
        ax.text(float(r["ood_alarm_ratio_eval_mean"]) + 0.004, float(r["attack_detection_high_purity_mean"]) + 0.006, label, fontsize=8)
    ax.axvline(0.1322, color="black", linestyle="--", linewidth=1, alpha=0.55, label="dA multiseed alarm mean")
    ax.axhline(0.8014, color="black", linestyle=":", linewidth=1, alpha=0.55, label="dA multiseed det mean")
    ax.set_xlabel("OOD benign alarm ratio (fixed q99, mean +/- std)")
    ax.set_ylabel("High-purity attack detection (fixed q99, mean +/- std)")
    ax.set_title("Deep SVDD fixed-threshold comparison")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=180)
    plt.close(fig)


def plot_training_curves(curves: Dict[str, List[float]], out: Path) -> None:
    fig, ax = plt.subplots(figsize=(10.5, 6.2))
    for label, values in curves.items():
        ax.plot(np.arange(1, len(values) + 1), values, label=label)
    ax.set_xlabel("epoch")
    ax.set_ylabel("loss")
    ax.set_title("Deep SVDD training curves")
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
    entry = f"\n- `{run_tag}`: Multi-seed Deep SVDD baseline on original-frontend 100D stronger OOD; ID-benign-only training with AE pretrain and center-distance scoring. Path: `runs/{run_tag}/`.\n"
    p.write_text(text.rstrip() + entry, encoding="utf-8")


def update_research_log(run_tag: str) -> None:
    p = TRACKED_RUNS_DIR / "research_log" / "a_tier_experiment_progress_log.md"
    if not p.exists():
        return
    text = p.read_text(encoding="utf-8")
    marker = "### 5.23 Deep SVDD Baseline"
    if marker in text:
        return
    insert = "\n## 6. Current Candidate Ranking"
    block = f"""

{marker}

Run:
- `runs/{run_tag}/`

Purpose:
- Add one modern deep one-class baseline on the same original-frontend 100D stronger OOD protocol.
- Reduce A-tier baseline risk beyond dA / recurrent AE / classical sklearn detectors.

Interpretation target:
- If Deep SVDD fails under fixed thresholds, stronger OOD remains genuinely difficult even for a modern deep one-class baseline.
- If Deep SVDD is strong, it becomes a required main baseline for Transformer positioning.
"""
    if insert in text:
        text = text.replace(insert, block + "\n" + insert)
    else:
        text = text.rstrip() + block
    p.write_text(text, encoding="utf-8")


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    ap = argparse.ArgumentParser(description="Deep SVDD baseline for frontend100 stronger OOD.")
    ap.add_argument("--run-tag", default=f"frontend100_deep_svdd_baseline_{today}")
    ap.add_argument("--source-root", type=Path, default=WORKTREE_ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master")
    ap.add_argument("--id-csv", type=Path, default=None)
    ap.add_argument("--ood-csv", type=Path, default=None)
    ap.add_argument("--attack-csv", type=Path, default=None)
    ap.add_argument("--stage2-indices-json", type=Path, default=None)
    ap.add_argument("--reference-results-csv", type=Path, default=None)
    ap.add_argument("--seeds", default="101,202,303")
    ap.add_argument("--calibration-budget", type=int, default=5000)
    ap.add_argument("--scan-points", type=int, default=1200)
    ap.add_argument("--hidden-dims", default="128,64")
    ap.add_argument("--latent-dim", type=int, default=32)
    ap.add_argument("--pretrain-epochs", type=int, default=30)
    ap.add_argument("--svdd-epochs", type=int, default=60)
    ap.add_argument("--batch-size", type=int, default=512)
    ap.add_argument("--pretrain-lr", type=float, default=1e-3)
    ap.add_argument("--svdd-lr", type=float, default=5e-4)
    ap.add_argument("--weight-decay", type=float, default=1e-6)
    ap.add_argument("--device", default="auto")
    ap.add_argument("--smoke-fit-n", type=int, default=0, help="Optional smaller fit size for smoke test.")
    ap.add_argument("--skip-register", action="store_true")
    args = ap.parse_args()

    seeds = [int(x) for x in args.seeds.split(",") if x.strip()]
    hidden_dims = [int(x) for x in args.hidden_dims.split(",") if x.strip()]
    device = choose_device(args.device)

    out = ARTIFACT_RUNS_DIR / args.run_tag
    out.mkdir(parents=True, exist_ok=True)
    plot_dir = out / "deep_svdd_plots"
    plot_dir.mkdir(exist_ok=True)
    (out / "command.txt").write_text("python " + " ".join(sys.argv) + "\n", encoding="utf-8")

    source = args.source_root
    if args.id_csv is not None:
        id_csv = args.id_csv
        ood_csv = args.ood_csv
        attack_csv = args.attack_csv
        stage2_idx_payload = json.loads(args.stage2_indices_json.read_text(encoding="utf-8"))
        idx = {
            "high": np.array(stage2_idx_payload["high"], dtype=np.int64),
            "mixed": np.array(stage2_idx_payload["mixed"], dtype=np.int64),
        }
    else:
        data = source / "runs" / "frontend100_crosscapture_stage1_2026-03-25" / "data"
        id_csv = data / "id_source_100.csv"
        ood_csv = data / "ood_benign_source_100.csv"
        attack_csv = source / "runs" / "frontend100_joint_eval_stage1_2026-03-31" / "data" / "attack_source_100.csv"
        stage2 = json.loads((source / "runs" / "frontend100_joint_eval_stage2_2026-04-01" / "attack_manifest_stage2.json").read_text(encoding="utf-8"))
        idx = build_stage2_indices(stage2)

    x_all = pd.read_csv(id_csv, header=None, nrows=13000).to_numpy(np.float64)
    x_fit = x_all[:8000]
    if args.smoke_fit_n > 0:
        x_fit = x_fit[: min(len(x_fit), args.smoke_fit_n)]
    x_id = x_all[8000:13000]
    x_ood = pd.read_csv(ood_csv, header=None).to_numpy(np.float64)
    x_attack = pd.read_csv(attack_csv, header=None).to_numpy(np.float64)
    high_idx = idx["high"]
    mixed_idx = idx["mixed"]

    rows: List[Dict] = []
    curve_payload: Dict[str, List[float]] = {}
    diagnostics: List[Dict] = []
    for seed in seeds:
        set_seed(seed)
        scaler = StandardScaler().fit(x_fit)
        x_fit_s = scaler.transform(x_fit).astype(np.float32)
        x_id_s = scaler.transform(x_id).astype(np.float32)
        x_ood_s = scaler.transform(x_ood).astype(np.float32)
        x_attack_s = scaler.transform(x_attack).astype(np.float32)

        ae = AutoEncoder(input_dim=x_fit.shape[1], hidden_dims=hidden_dims, latent_dim=args.latent_dim)
        pre_losses = train_autoencoder(
            model=ae,
            x_train=x_fit_s,
            epochs=args.pretrain_epochs,
            batch_size=args.batch_size,
            lr=args.pretrain_lr,
            device=device,
        )
        encoder = ae.encoder
        fit_loader = make_loader(x_fit_s, batch_size=args.batch_size, shuffle=False)
        center = init_center(encoder, fit_loader, device=device)
        svdd_losses = train_svdd(
            encoder=encoder,
            x_train=x_fit_s,
            center=center,
            epochs=args.svdd_epochs,
            batch_size=args.batch_size,
            lr=args.svdd_lr,
            weight_decay=args.weight_decay,
            device=device,
        )
        sid = score_svdd(encoder=encoder, center=center, x=x_id_s, batch_size=args.batch_size, device=device)
        sood = score_svdd(encoder=encoder, center=center, x=x_ood_s, batch_size=args.batch_size, device=device)
        satt = score_svdd(encoder=encoder, center=center, x=x_attack_s, batch_size=args.batch_size, device=device)
        curve_payload[f"seed{seed}_pretrain"] = pre_losses
        curve_payload[f"seed{seed}_svdd"] = svdd_losses
        diagnostics.append(
            {
                "seed": seed,
                "device": device,
                "fit_n": int(len(x_fit_s)),
                "center_norm": float(torch.linalg.norm(center).cpu().item()),
                "pretrain_loss_first": float(pre_losses[0]) if pre_losses else None,
                "pretrain_loss_last": float(pre_losses[-1]) if pre_losses else None,
                "svdd_loss_first": float(svdd_losses[0]) if svdd_losses else None,
                "svdd_loss_last": float(svdd_losses[-1]) if svdd_losses else None,
                "id_score_mean": float(np.mean(sid)),
                "ood_score_mean": float(np.mean(sood)),
                "attack_score_mean": float(np.mean(satt)),
            }
        )
        rows.extend(
            eval_scores(
                object_label="deep_svdd",
                detector_family="deep_svdd",
                score_label="default_score",
                seed=seed,
                id_scores=sid,
                ood_scores=sood,
                attack_scores=satt,
                high_idx=high_idx,
                mixed_idx=mixed_idx,
                budget=args.calibration_budget,
                scan_points=args.scan_points,
                extra={
                    "baseline_category": "external_unsupervised",
                    "training_mode": "unsupervised_id_only",
                    "uses_attack_labels": False,
                    "source_mode": "computed_now",
                },
            )
        )

    reference_results_csv = args.reference_results_csv or (
        ARTIFACT_RUNS_DIR / "frontend100_locked_candidate_multiseed_2026-04-06" / "multiseed_locked_candidate_results.csv"
    )
    ref = load_reference_rows(reference_results_csv, seeds)
    if not ref.empty:
        rows.extend(ref.to_dict("records"))

    per = pd.DataFrame(rows)
    agg = aggregate(per)
    diag_df = pd.DataFrame(diagnostics)
    per.to_csv(out / "deep_svdd_results.csv", index=False)
    per.to_csv(out / "results.csv", index=False)
    agg.to_csv(out / "deep_svdd_aggregate.csv", index=False)
    diag_df.to_csv(out / "deep_svdd_diagnostics.csv", index=False)

    results_md = "# Deep SVDD Baseline Results\n\n"
    results_md += "## Aggregate\n" + md_table(agg) + "\n\n"
    results_md += "## Per-seed fixed rows\n" + md_table(
        per[per["policy_name"].eq("fixed_id_q99")][
            [
                "object_label",
                "seed",
                "ood_alarm_ratio_eval",
                "attack_detection_high_purity",
                "roc_auc_attack_high_vs_ood_eval",
                "id_alarm_ratio",
            ]
        ].sort_values(["object_label", "seed"])
    )
    (out / "deep_svdd_results.md").write_text(results_md, encoding="utf-8")

    plot_fixed_tradeoff(agg, plot_dir / "fixed_tradeoff_deep_svdd.png")
    plot_training_curves(curve_payload, plot_dir / "deep_svdd_training_curves.png")

    fixed = agg[agg["policy_name"].eq("fixed_id_q99")].copy()
    deep_fixed = fixed[fixed["object_label"].eq("deep_svdd")]
    dA_fixed = fixed[fixed["object_label"].eq("da__default_score")]
    latent_fixed = fixed[fixed["object_label"].eq("latent_swap_spike_mix__log_weighted_z_rmse0.5_cos1.0")]
    def maybe_fmt(df: pd.DataFrame, col: str) -> str:
        return "nan" if df.empty else f"{float(df.iloc[0][col]):.4f}"

    summary_lines = [
        "# Deep SVDD Baseline Summary",
        "",
        "- Data: original-frontend 100D + stronger OOD protocol.",
        "- Training: Deep SVDD with AE pretrain; ID benign fit split only.",
        f"- Seeds: `{','.join(str(s) for s in seeds)}`.",
        f"- Device: `{device}`.",
        "",
        "## Fixed q99 Aggregate",
        md_table(
            fixed[
                [
                    "object_label",
                    "ood_alarm_ratio_eval_mean",
                    "ood_alarm_ratio_eval_std",
                    "attack_detection_high_purity_mean",
                    "attack_detection_high_purity_std",
                    "roc_auc_attack_high_vs_ood_eval_mean",
                ]
            ].sort_values("object_label")
        ),
        "",
        "## Interpretation",
        f"- Deep SVDD fixed: alarm={maybe_fmt(deep_fixed,'ood_alarm_ratio_eval_mean')}, det={maybe_fmt(deep_fixed,'attack_detection_high_purity_mean')}.",
        f"- dA fixed ref: alarm={maybe_fmt(dA_fixed,'ood_alarm_ratio_eval_mean')}, det={maybe_fmt(dA_fixed,'attack_detection_high_purity_mean')}.",
        f"- latent log-weighted ref: alarm={maybe_fmt(latent_fixed,'ood_alarm_ratio_eval_mean')}, det={maybe_fmt(latent_fixed,'attack_detection_high_purity_mean')}.",
        "- Use this run to decide whether a modern deep one-class baseline materially threatens the current Transformer narrative.",
    ]
    summary = "\n".join(summary_lines) + "\n"
    (out / "deep_svdd_summary.md").write_text(summary, encoding="utf-8")
    (out / "summary.md").write_text(summary, encoding="utf-8")

    cfg = {
        "stage": "frontend100_deep_svdd_baseline",
        "run_tag": args.run_tag,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_root": str(source),
        "id_csv": str(id_csv),
        "ood_csv": str(ood_csv),
        "attack_csv": str(attack_csv),
        "stage2_indices_json": str(args.stage2_indices_json) if args.stage2_indices_json is not None else None,
        "reference_results_csv": str(reference_results_csv),
        "seeds": seeds,
        "data_protocol": "original-frontend 100D + stronger OOD",
        "fit_n": int(len(x_fit)),
        "id_eval_n": int(len(x_id)),
        "ood_n": int(len(x_ood)),
        "attack_n": int(len(x_attack)),
        "attack_high_n": int(len(high_idx)),
        "attack_mixed_n": int(len(mixed_idx)),
        "hidden_dims": hidden_dims,
        "latent_dim": int(args.latent_dim),
        "pretrain_epochs": int(args.pretrain_epochs),
        "svdd_epochs": int(args.svdd_epochs),
        "batch_size": int(args.batch_size),
        "pretrain_lr": float(args.pretrain_lr),
        "svdd_lr": float(args.svdd_lr),
        "weight_decay": float(args.weight_decay),
        "device": device,
        "outputs": {
            "results": str(out / "deep_svdd_results.csv"),
            "aggregate": str(out / "deep_svdd_aggregate.csv"),
            "diagnostics": str(out / "deep_svdd_diagnostics.csv"),
            "summary": str(out / "summary.md"),
            "plots": str(plot_dir),
        },
    }
    (out / "deep_svdd_manifest.json").write_text(json.dumps(clean(cfg), indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "config.json").write_text(json.dumps(clean(cfg), indent=2, ensure_ascii=False), encoding="utf-8")
    if not args.skip_register:
        append_map(args.run_tag)
        update_research_log(args.run_tag)
    print(f"[done] deep svdd output: {out}", flush=True)


if __name__ == "__main__":
    main()
