from __future__ import annotations

import argparse
import json
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
import frontend100_timescale_tokenizer_v1_3 as tv3


PROFILE_FAMILY_WEIGHTS = {
    "uniform": np.asarray([1.0, 1.0, 1.0, 1.0], dtype=np.float32),
    "family_short_focus": np.asarray([0.80, 1.35, 0.80, 1.35], dtype=np.float32),
}
PROFILE_SCALE_WEIGHTS = {
    "uniform": np.asarray([1.0, 1.0, 1.0, 1.0, 1.0], dtype=np.float32),
    "family_short_focus": np.asarray([0.55, 0.70, 0.95, 1.35, 1.45], dtype=np.float32),
}


def load_structured_npz(path: Path) -> Dict[str, np.ndarray]:
    data = np.load(path)
    req = {
        "expression_v2_matrix",
        "expression_v2_flat",
        "expression_v2_channel_mask",
        "expression_v2_family_id",
        "expression_v2_scale_id",
        "expression_v2_channel_names",
    }
    missing = req - set(data.files)
    if missing:
        raise RuntimeError(f"Missing keys {sorted(missing)} in {path}")
    out = {k: data[k] for k in data.files}
    if out["expression_v2_matrix"].ndim != 3 or out["expression_v2_matrix"].shape[1:] != (20, 5):
        raise RuntimeError(f"Expected expression_v2_matrix [N,20,5], got {out['expression_v2_matrix'].shape} in {path}")
    if out["expression_v2_channel_mask"].shape != (20, 5):
        raise RuntimeError(f"Expected expression_v2_channel_mask [20,5], got {out['expression_v2_channel_mask'].shape} in {path}")
    return out


def standardize_tokens(x: np.ndarray, channel_mask: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = x.mean(axis=0).astype(np.float32)
    std = np.maximum(x.std(axis=0), 1e-6).astype(np.float32)
    mean = mean * channel_mask
    std = np.where(channel_mask > 0, std, 1.0).astype(np.float32)
    z = ((x - mean[None, :, :]) / std[None, :, :]).astype(np.float32)
    z *= channel_mask[None, :, :]
    return z, mean, std


def apply_standardize(x: np.ndarray, mean: np.ndarray, std: np.ndarray, channel_mask: np.ndarray) -> np.ndarray:
    z = ((x - mean[None, :, :]) / std[None, :, :]).astype(np.float32)
    z *= channel_mask[None, :, :]
    return z


def build_token_weights(token_family_id: np.ndarray, token_scale_id: np.ndarray, profile: str) -> np.ndarray:
    fam_w = PROFILE_FAMILY_WEIGHTS[profile]
    scale_w = PROFILE_SCALE_WEIGHTS[profile]
    out = np.asarray([fam_w[int(f)] * scale_w[int(s)] for f, s in zip(token_family_id, token_scale_id)], dtype=np.float32)
    return out / max(float(np.mean(out)), 1e-6)


class ExpressionV2TransformerAE(nn.Module):
    def __init__(self, num_tokens: int, token_dim: int, token_family_id: np.ndarray, token_scale_id: np.ndarray, d_model: int = 64, nhead: int = 4, num_layers: int = 2):
        super().__init__()
        self.token_proj = nn.Linear(token_dim, d_model)
        self.family_emb = nn.Embedding(4, d_model)
        self.scale_emb = nn.Embedding(5, d_model)
        self.pos = nn.Parameter(torch.zeros(1, num_tokens, d_model))
        enc = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=max(128, d_model * 4),
            dropout=0.0,
            batch_first=True,
            activation="gelu",
        )
        self.encoder = nn.TransformerEncoder(enc, num_layers=int(num_layers))
        self.norm = nn.LayerNorm(d_model)
        self.out_proj = nn.Sequential(nn.Linear(d_model, d_model), nn.GELU(), nn.Linear(d_model, token_dim))
        self.register_buffer("token_family_id", torch.tensor(token_family_id, dtype=torch.long))
        self.register_buffer("token_scale_id", torch.tensor(token_scale_id, dtype=torch.long))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.token_proj(x)
        h = h + self.family_emb(self.token_family_id).unsqueeze(0) + self.scale_emb(self.token_scale_id).unsqueeze(0) + self.pos
        h = self.encoder(h)
        return self.out_proj(self.norm(h))


class ExpressionV2TokenMLPAE(nn.Module):
    def __init__(self, num_tokens: int, token_dim: int, token_family_id: np.ndarray, token_scale_id: np.ndarray, d_model: int = 64, bottleneck: int = 192):
        super().__init__()
        self.token_proj = nn.Linear(token_dim, d_model)
        self.family_emb = nn.Embedding(4, d_model)
        self.scale_emb = nn.Embedding(5, d_model)
        self.pos = nn.Parameter(torch.zeros(1, num_tokens, d_model))
        flat_dim = num_tokens * d_model
        self.num_tokens = int(num_tokens)
        self.d_model = int(d_model)
        self.mlp = nn.Sequential(
            nn.LayerNorm(flat_dim),
            nn.Linear(flat_dim, bottleneck),
            nn.GELU(),
            nn.Linear(bottleneck, flat_dim),
            nn.GELU(),
        )
        self.out_proj = nn.Sequential(nn.LayerNorm(d_model), nn.Linear(d_model, token_dim))
        self.register_buffer("token_family_id", torch.tensor(token_family_id, dtype=torch.long))
        self.register_buffer("token_scale_id", torch.tensor(token_scale_id, dtype=torch.long))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.token_proj(x)
        h = h + self.family_emb(self.token_family_id).unsqueeze(0) + self.scale_emb(self.token_scale_id).unsqueeze(0) + self.pos
        b = h.size(0)
        h = self.mlp(h.reshape(b, self.num_tokens * self.d_model)).reshape(b, self.num_tokens, self.d_model)
        return self.out_proj(h)


def token_rmse(pred: torch.Tensor, target: torch.Tensor, channel_mask_t: torch.Tensor) -> torch.Tensor:
    err = (pred - target) ** 2
    denom = torch.clamp(channel_mask_t.sum(dim=1), min=1.0).view(1, -1)
    sse = (err * channel_mask_t.unsqueeze(0)).sum(dim=2)
    return torch.sqrt(torch.clamp(sse / denom, min=1e-12))


def train_model(model: nn.Module, x_train: np.ndarray, epochs: int, batch_size: int, lr: float, device: str, channel_mask: np.ndarray, token_weights: np.ndarray) -> List[float]:
    model.to(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    channel_mask_t = torch.as_tensor(channel_mask, dtype=torch.float32, device=device)
    weight_t = torch.as_tensor(token_weights, dtype=torch.float32, device=device).view(1, -1)
    ds = TensorDataset(torch.from_numpy(x_train.astype(np.float32)))
    loader = DataLoader(ds, batch_size=batch_size, shuffle=True, drop_last=False)
    hist: List[float] = []
    for _ in range(int(epochs)):
        model.train()
        total = 0.0
        count = 0
        for (xb,) in loader:
            xb = xb.to(device)
            opt.zero_grad()
            pred = model(xb)
            loss = torch.mean(token_rmse(pred, xb, channel_mask_t) * weight_t)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            total += float(loss.detach().item()) * len(xb)
            count += len(xb)
        hist.append(total / max(1, count))
    return hist


def score_token_rmse(model: nn.Module, x: np.ndarray, batch_size: int, device: str, channel_mask: np.ndarray) -> np.ndarray:
    model.to(device)
    model.eval()
    channel_mask_t = torch.as_tensor(channel_mask, dtype=torch.float32, device=device)
    out = []
    with torch.no_grad():
        for st in range(0, len(x), batch_size):
            xb = torch.from_numpy(x[st : st + batch_size].astype(np.float32)).to(device)
            pred = model(xb)
            out.append(token_rmse(pred, xb, channel_mask_t).detach().cpu().numpy())
    return np.concatenate(out, axis=0).astype(np.float64)


def aggregate_scores(token_scores: np.ndarray, token_scale_id: np.ndarray, token_weights: np.ndarray, mode: str) -> np.ndarray:
    if mode == "token_mean":
        return token_scores.mean(axis=1)
    if mode == "short_scale_mean":
        mask = np.isin(token_scale_id, [3, 4])
        return token_scores[:, mask].mean(axis=1)
    if mode == "weighted_token_mean":
        w = token_weights / max(float(np.mean(token_weights)), 1e-6)
        return (token_scores * w.reshape(1, -1)).mean(axis=1)
    raise ValueError(mode)


def plot_tradeoff(df: pd.DataFrame, out: Path) -> None:
    fixed = df[(df["policy_name"].eq("fixed_id_q99")) & (df["selection_feasible"].astype(bool))].copy()
    plt.figure(figsize=(11, 7))
    for _, r in fixed.iterrows():
        fam = str(r["detector_family"])
        if fam == "frontend_f2_expression_v2_transformer_v1":
            color = "#1f77b4"
        elif fam == "frontend_f2_expression_v2_token_mlp_control":
            color = "#ff7f0e"
        else:
            color = "#7f7f7f"
        x = float(r["ood_alarm_ratio_eval"])
        y = float(r["attack_detection_high_purity"])
        plt.scatter(x, y, c=color, s=88)
        plt.text(x + 0.004, y + 0.006, str(r["object_label"]), fontsize=7)
    plt.xlabel("OOD benign alarm ratio (fixed q99)")
    plt.ylabel("High-purity attack detection")
    plt.title("Frontend-F2 expression_v2 fixed trade-off")
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(out, dpi=180)
    plt.close()


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    ap = argparse.ArgumentParser(description="Frontend-F2 expression_v2 tokenizer v1.")
    ap.add_argument("--run-tag", default=f"frontend_f2_expression_v2_tokenizer_v1_{today}")
    ap.add_argument("--structured-benign-run", type=Path, default=WORKTREE_ROOT / "runs" / "frontend_f2_expression_v2_crosscapture_stage1_2026-04-14" / "data")
    ap.add_argument("--structured-attack-run", type=Path, default=WORKTREE_ROOT / "runs" / "frontend_f2_expression_v2_attack_source_2026-04-14" / "data")
    ap.add_argument("--stage2-manifest", type=Path, default=WORKTREE_ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master" / "runs" / "frontend100_joint_eval_stage2_2026-04-01" / "attack_manifest_stage2.json")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--batch-size", type=int, default=256)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--train-samples", type=int, default=8000)
    ap.add_argument("--id-eval-samples", type=int, default=5000)
    ap.add_argument("--calibration-budget", type=int, default=5000)
    ap.add_argument("--scan-points", type=int, default=1200)
    ap.add_argument("--d-model", type=int, default=64)
    ap.add_argument("--nhead", type=int, default=4)
    ap.add_argument("--num-layers", type=int, default=2)
    ap.add_argument("--token-mlp-bottleneck", type=int, default=192)
    ap.add_argument("--smoke-fit-n", type=int, default=0)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = ap.parse_args()

    tv3.set_seed(args.seed)
    out = WORKTREE_ROOT / "runs" / args.run_tag
    out.mkdir(parents=True, exist_ok=True)
    plot_dir = out / "frontend_f2_expression_v2_plots"
    plot_dir.mkdir(exist_ok=True)
    (out / "command.txt").write_text("python " + " ".join(sys.argv) + "\n", encoding="utf-8")

    id_src = load_structured_npz(args.structured_benign_run / "id_source_structured.npz")
    ood_src = load_structured_npz(args.structured_benign_run / "ood_benign_source_structured.npz")
    attack_src = load_structured_npz(args.structured_attack_run / "attack_source_structured.npz")
    stage2 = json.loads(args.stage2_manifest.read_text(encoding="utf-8-sig"))
    stage2_idx = resc.build_stage2_indices(stage2)

    channel_mask = id_src["expression_v2_channel_mask"].astype(np.float32)
    token_family_id = id_src["expression_v2_family_id"].astype(np.int64)
    token_scale_id = id_src["expression_v2_scale_id"].astype(np.int64)
    channel_names = [str(x) for x in id_src["expression_v2_channel_names"].tolist()]

    fit_n = int(args.train_samples if args.smoke_fit_n <= 0 else min(args.train_samples, args.smoke_fit_n))
    id_eval_n = int(args.id_eval_samples)
    x_train_raw = id_src["expression_v2_matrix"][:fit_n].astype(np.float32)
    x_id_raw = id_src["expression_v2_matrix"][fit_n : fit_n + id_eval_n].astype(np.float32)
    x_ood_raw = ood_src["expression_v2_matrix"].astype(np.float32)
    x_attack_raw = attack_src["expression_v2_matrix"].astype(np.float32)

    x_train, mean, std = standardize_tokens(x_train_raw, channel_mask)
    x_id = apply_standardize(x_id_raw, mean, std, channel_mask)
    x_ood = apply_standardize(x_ood_raw, mean, std, channel_mask)
    x_attack = apply_standardize(x_attack_raw, mean, std, channel_mask)

    rows: List[Dict] = []
    diagnostics: List[Dict] = []

    model_builders = [
        ("frontend_f2_expression_v2_transformer_v1", lambda: ExpressionV2TransformerAE(20, 5, token_family_id, token_scale_id, d_model=args.d_model, nhead=args.nhead, num_layers=args.num_layers)),
        ("frontend_f2_expression_v2_token_mlp_control", lambda: ExpressionV2TokenMLPAE(20, 5, token_family_id, token_scale_id, d_model=args.d_model, bottleneck=args.token_mlp_bottleneck)),
    ]
    score_modes = [
        ("token_mean", "mean RMSE over all 20 expression_v2 tokens"),
        ("short_scale_mean", "mean RMSE over scale 0.1/0.01 tokens"),
        ("weighted_token_mean", "family/scale weighted RMSE over all 20 expression_v2 tokens"),
    ]

    for profile in ["uniform", "family_short_focus"]:
        token_weights = build_token_weights(token_family_id, token_scale_id, profile)
        for detector_family, builder in model_builders:
            print(f"[fit] {detector_family} profile={profile}", flush=True)
            model = builder()
            hist = train_model(model, x_train, args.epochs, args.batch_size, args.lr, args.device, channel_mask, token_weights)
            id_token_scores = score_token_rmse(model, x_id, args.batch_size, args.device, channel_mask)
            ood_token_scores = score_token_rmse(model, x_ood, args.batch_size, args.device, channel_mask)
            attack_token_scores = score_token_rmse(model, x_attack, args.batch_size, args.device, channel_mask)
            for mode, mode_desc in score_modes:
                sid = aggregate_scores(id_token_scores, token_scale_id, token_weights, mode)
                sood = aggregate_scores(ood_token_scores, token_scale_id, token_weights, mode)
                satt = aggregate_scores(attack_token_scores, token_scale_id, token_weights, mode)
                obj = f"{detector_family.replace('frontend_f2_', '').replace('_control', '')}_{profile}_{mode}"
                rows.extend(
                    tv3.eval_scores(
                        object_label=obj,
                        detector_family=detector_family,
                        score_label=mode,
                        seed=args.seed,
                        score_id=sid,
                        score_ood=sood,
                        score_attack=satt,
                        high_idx=stage2_idx["high"],
                        mixed_idx=stage2_idx["mixed"],
                        budget=args.calibration_budget,
                        scan_points=args.scan_points,
                        extra={
                            "source_mode": "computed_now",
                            "token_profile": profile,
                            "input_tensor": "expression_v2_matrix[20x5]",
                            "channel_names": ",".join(channel_names),
                            "score_mode_desc": mode_desc,
                        },
                    )
                )
            diagnostics.append(
                {
                    "detector_family": detector_family,
                    "token_profile": profile,
                    "train_loss_start": float(hist[0]),
                    "train_loss_end": float(hist[-1]),
                    "train_loss_min": float(np.min(hist)),
                    "num_tokens": 20,
                    "token_dim": 5,
                }
            )

    df = pd.DataFrame(rows)
    diag = pd.DataFrame(diagnostics)
    df.to_csv(out / "frontend_f2_expression_v2_results.csv", index=False)
    df.to_csv(out / "results.csv", index=False)
    diag.to_csv(out / "frontend_f2_expression_v2_diagnostics.csv", index=False)
    plot_tradeoff(df, plot_dir / "fixed_tradeoff_frontend_f2_expression_v2.png")

    fixed = df[(df["policy_name"].eq("fixed_id_q99")) & (df["selection_feasible"].astype(bool))].copy()
    cols = [
        "object_label",
        "detector_family",
        "token_profile",
        "score_label",
        "ood_alarm_ratio_eval",
        "attack_detection_high_purity",
        "roc_auc_attack_high_vs_ood_eval",
    ]
    fixed_md = tv3.md_table(fixed[cols].sort_values(["detector_family", "object_label"]))
    summary = "\n".join(
        [
            "# Frontend-F2 Expression v2 Tokenizer v1",
            "",
            "- Data: Frontend-F2 expression_v2 sources (`7-6` ID, `4-1` OOD, `34-1` attack).",
            "- Input tensor: `expression_v2_matrix [20,5]` with family/scale embeddings.",
            f"- expression_v2 channels: `{', '.join(channel_names)}`.",
            "",
            "## Fixed q99",
            fixed_md,
        ]
    ) + "\n"
    (out / "summary.md").write_text(summary, encoding="utf-8")
    cfg = {
        "stage": "frontend_f2_expression_v2_tokenizer_v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_tag": args.run_tag,
        "seed": args.seed,
        "structured_benign_run": str(args.structured_benign_run),
        "structured_attack_run": str(args.structured_attack_run),
        "outputs": {
            "results": str(out / "frontend_f2_expression_v2_results.csv"),
            "diagnostics": str(out / "frontend_f2_expression_v2_diagnostics.csv"),
            "summary": str(out / "summary.md"),
            "plots": str(plot_dir),
        },
    }
    (out / "frontend_f2_expression_v2_manifest.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "config.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[done] frontend-f2 expression_v2 tokenizer output: {out}", flush=True)


if __name__ == "__main__":
    main()
