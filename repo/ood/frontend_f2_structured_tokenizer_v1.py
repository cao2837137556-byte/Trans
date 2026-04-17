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


SCALE_LOSS_PROFILES = {
    "uniform": np.asarray([1.0, 1.0, 1.0, 1.0, 1.0], dtype=np.float32),
    "short_focus": np.asarray([0.50, 0.50, 0.75, 1.50, 1.75], dtype=np.float32),
}


def load_structured_npz(path: Path) -> Dict[str, np.ndarray]:
    data = np.load(path)
    req = {"token_matrix", "token_slot_mask", "token_family_id", "token_scale_id", "flat_features"}
    missing = req - set(data.files)
    if missing:
        raise RuntimeError(f"Missing keys {sorted(missing)} in {path}")
    out = {k: data[k] for k in data.files}
    if out["token_matrix"].ndim != 3 or out["token_matrix"].shape[1:] != (20, 7):
        raise RuntimeError(f"Expected token_matrix [N,20,7], got {out['token_matrix'].shape} in {path}")
    if out["token_slot_mask"].shape != (20, 7):
        raise RuntimeError(f"Expected token_slot_mask [20,7], got {out['token_slot_mask'].shape} in {path}")
    return out


def standardize_tokens(x: np.ndarray, slot_mask: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = x.mean(axis=0).astype(np.float32)
    std = np.maximum(x.std(axis=0), 1e-6).astype(np.float32)
    mean = mean * slot_mask
    std = np.where(slot_mask > 0, std, 1.0).astype(np.float32)
    z = ((x - mean[None, :, :]) / std[None, :, :]).astype(np.float32)
    z *= slot_mask[None, :, :]
    return z, mean, std


def apply_standardize(x: np.ndarray, mean: np.ndarray, std: np.ndarray, slot_mask: np.ndarray) -> np.ndarray:
    z = ((x - mean[None, :, :]) / std[None, :, :]).astype(np.float32)
    z *= slot_mask[None, :, :]
    return z


def build_scale_masks(token_scale_id: np.ndarray, token_slot_mask: np.ndarray) -> Tuple[List[np.ndarray], np.ndarray]:
    scale_masks = []
    for scale_idx in range(5):
        m = (token_scale_id[:, None] == scale_idx).astype(np.float32) * token_slot_mask
        scale_masks.append(m.astype(np.float32))
    return scale_masks, np.asarray([m.sum() for m in scale_masks], dtype=np.float32)


class F2StructuredTransformerAE(nn.Module):
    def __init__(self, num_tokens: int, token_dim: int, family_count: int, scale_count: int, token_family_id: np.ndarray, token_scale_id: np.ndarray, d_model: int = 64, nhead: int = 4, num_layers: int = 2):
        super().__init__()
        self.token_proj = nn.Linear(token_dim, d_model)
        self.family_emb = nn.Embedding(family_count, d_model)
        self.scale_emb = nn.Embedding(scale_count, d_model)
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
        self.decoder = nn.Sequential(
            nn.Linear(d_model, d_model),
            nn.GELU(),
            nn.Linear(d_model, token_dim),
        )
        self.register_buffer("token_family_id", torch.tensor(token_family_id, dtype=torch.long))
        self.register_buffer("token_scale_id", torch.tensor(token_scale_id, dtype=torch.long))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.token_proj(x)
        h = h + self.family_emb(self.token_family_id).unsqueeze(0) + self.scale_emb(self.token_scale_id).unsqueeze(0) + self.pos
        h = self.encoder(h)
        return self.decoder(self.norm(h))


class F2TokenMLPAE(nn.Module):
    def __init__(self, num_tokens: int, token_dim: int, family_count: int, scale_count: int, token_family_id: np.ndarray, token_scale_id: np.ndarray, d_model: int = 64, bottleneck: int = 192):
        super().__init__()
        self.token_proj = nn.Linear(token_dim, d_model)
        self.family_emb = nn.Embedding(family_count, d_model)
        self.scale_emb = nn.Embedding(scale_count, d_model)
        self.pos = nn.Parameter(torch.zeros(1, num_tokens, d_model))
        flat_dim = num_tokens * d_model
        self.mlp = nn.Sequential(
            nn.LayerNorm(flat_dim),
            nn.Linear(flat_dim, bottleneck),
            nn.GELU(),
            nn.Linear(bottleneck, flat_dim),
            nn.GELU(),
        )
        self.out_proj = nn.Sequential(
            nn.LayerNorm(d_model),
            nn.Linear(d_model, token_dim),
        )
        self.register_buffer("token_family_id", torch.tensor(token_family_id, dtype=torch.long))
        self.register_buffer("token_scale_id", torch.tensor(token_scale_id, dtype=torch.long))
        self.num_tokens = int(num_tokens)
        self.d_model = int(d_model)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.token_proj(x)
        h = h + self.family_emb(self.token_family_id).unsqueeze(0) + self.scale_emb(self.token_scale_id).unsqueeze(0) + self.pos
        b = h.size(0)
        h = self.mlp(h.reshape(b, self.num_tokens * self.d_model)).reshape(b, self.num_tokens, self.d_model)
        return self.out_proj(h)


def scale_rmse(pred: torch.Tensor, target: torch.Tensor, scale_masks_t: List[torch.Tensor], scale_counts_t: torch.Tensor) -> torch.Tensor:
    err = (pred - target) ** 2
    out = []
    for mask, denom in zip(scale_masks_t, scale_counts_t):
        sse = (err * mask.unsqueeze(0)).sum(dim=(1, 2))
        out.append(torch.sqrt(torch.clamp(sse / torch.clamp(denom, min=1.0), min=1e-12)))
    return torch.stack(out, dim=1)


def train_model(model: nn.Module, x_train: np.ndarray, epochs: int, batch_size: int, lr: float, device: str, scale_masks: List[np.ndarray], scale_counts: np.ndarray, scale_weights: np.ndarray) -> List[float]:
    model.to(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    weights_t = torch.as_tensor(scale_weights, dtype=torch.float32, device=device).view(1, -1)
    weights_t = weights_t / torch.clamp(weights_t.mean(), min=1e-6)
    scale_masks_t = [torch.as_tensor(m, dtype=torch.float32, device=device) for m in scale_masks]
    scale_counts_t = torch.as_tensor(scale_counts, dtype=torch.float32, device=device)
    ds = TensorDataset(torch.from_numpy(x_train.astype(np.float32)))
    loader = DataLoader(ds, batch_size=batch_size, shuffle=True, drop_last=False)
    history: List[float] = []
    for _ in range(int(epochs)):
        model.train()
        total = 0.0
        count = 0
        for (xb,) in loader:
            xb = xb.to(device)
            opt.zero_grad()
            pred = model(xb)
            rmse = scale_rmse(pred, xb, scale_masks_t, scale_counts_t)
            loss = torch.mean(rmse * weights_t)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            total += float(loss.detach().item()) * len(xb)
            count += len(xb)
        history.append(total / max(1, count))
    return history


def score_model_per_scale(model: nn.Module, x: np.ndarray, batch_size: int, device: str, scale_masks: List[np.ndarray], scale_counts: np.ndarray) -> np.ndarray:
    model.to(device)
    model.eval()
    scale_masks_t = [torch.as_tensor(m, dtype=torch.float32, device=device) for m in scale_masks]
    scale_counts_t = torch.as_tensor(scale_counts, dtype=torch.float32, device=device)
    out = []
    with torch.no_grad():
        for st in range(0, len(x), batch_size):
            xb = torch.from_numpy(x[st : st + batch_size].astype(np.float32)).to(device)
            pred = model(xb)
            out.append(scale_rmse(pred, xb, scale_masks_t, scale_counts_t).detach().cpu().numpy())
    return np.concatenate(out, axis=0).astype(np.float64)


def aggregate_scale_scores(per_scale: np.ndarray, mode: str, id_mean: np.ndarray | None = None, id_std: np.ndarray | None = None) -> np.ndarray:
    if mode == "short_mean":
        return per_scale[:, [3, 4]].mean(axis=1)
    if mode.startswith("z_short_mean_minus_long_mean_a"):
        if id_mean is None or id_std is None:
            raise ValueError(f"{mode} requires id_mean/id_std")
        alpha = float(mode.split("_a", 1)[1])
        z = (per_scale - id_mean.reshape(1, -1)) / np.maximum(id_std.reshape(1, -1), 1e-6)
        return z[:, [3, 4]].mean(axis=1) - alpha * z[:, [0, 1, 2]].mean(axis=1)
    raise ValueError(mode)


def load_reference_rows() -> List[Dict]:
    refs = tv3.load_reference_rows()
    p = WORKTREE_ROOT / "runs" / "frontend100_structured_frontend_v1_smoke_2026-04-13" / "structured_frontend_v1_results.csv"
    if p.exists():
        df = pd.read_csv(p)
        keep = {
            "transformer_v1_short_focus_z_short_mean_minus_long_mean_a1.50",
            "token_mlp_short_focus_z_short_mean_minus_long_mean_a1.50",
            "flat_ae_100d_uniform_z_short_mean_minus_long_mean_a1.50",
        }
        refs.extend(df[df["object_label"].isin(keep)].to_dict("records"))
    return refs


def plot_tradeoff(df: pd.DataFrame, out: Path) -> None:
    fixed = df[(df["policy_name"] == "fixed_id_q99") & (df["selection_feasible"].astype(bool))].copy()
    plt.figure(figsize=(11.0, 7.0))
    for _, r in fixed.iterrows():
        fam = str(r["detector_family"])
        if fam == "frontend_f2_structured_transformer_v1":
            color = "#1f77b4"
        elif fam == "frontend_f2_token_mlp_control":
            color = "#ff7f0e"
        elif fam.startswith("timescale_"):
            color = "#17becf"
        elif fam == "da":
            color = "#d62728"
        elif fam == "transformer":
            color = "#7f7f7f"
        elif fam == "transformer_tailreg":
            color = "#9467bd"
        else:
            color = "#8c564b"
        x = float(r["ood_alarm_ratio_eval"])
        y = float(r["attack_detection_high_purity"])
        plt.scatter(x, y, c=color, s=88)
        plt.text(x + 0.004, y + 0.006, str(r["object_label"]), fontsize=7)
    plt.xlabel("OOD benign alarm ratio (fixed q99)")
    plt.ylabel("High-purity attack detection")
    plt.title("Frontend-F2 structured tokenizer v1 fixed trade-off")
    plt.grid(alpha=0.25)
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
    text += f"\n- `{run_tag}`: Frontend-F2 structured tokenizer v1 on real structured caches (`7-6` ID, `4-1` OOD, `34-1` attack), using token family/scale embeddings and short-vs-long contrast scoring; path: `runs/{run_tag}/`.\n"
    p.write_text(text, encoding="utf-8")


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    ap = argparse.ArgumentParser(description="Frontend-F2 structured tokenizer v1.")
    ap.add_argument("--run-tag", default=f"frontend_f2_structured_tokenizer_v1_{today}")
    ap.add_argument("--source-root", type=Path, default=WORKTREE_ROOT)
    ap.add_argument("--structured-benign-run", type=Path, default=WORKTREE_ROOT / "runs" / "frontend_f2_crosscapture_stage1_2026-04-13" / "data")
    ap.add_argument("--structured-attack-run", type=Path, default=WORKTREE_ROOT / "runs" / "frontend_f2_attack_source_2026-04-13" / "data")
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
    plot_dir = out / "frontend_f2_plots"
    plot_dir.mkdir(exist_ok=True)
    (out / "command.txt").write_text("python " + " ".join(sys.argv) + "\n", encoding="utf-8")

    benign_root = args.structured_benign_run
    attack_root = args.structured_attack_run
    id_src = load_structured_npz(benign_root / "id_source_structured.npz")
    ood_src = load_structured_npz(benign_root / "ood_benign_source_structured.npz")
    attack_src = load_structured_npz(attack_root / "attack_source_structured.npz")
    stage2 = json.loads(args.stage2_manifest.read_text(encoding="utf-8-sig"))
    stage2_idx = resc.build_stage2_indices(stage2)

    if not np.array_equal(id_src["token_slot_mask"], ood_src["token_slot_mask"]):
        raise RuntimeError("ID/OOD token_slot_mask mismatch")
    if not np.array_equal(id_src["token_slot_mask"], attack_src["token_slot_mask"]):
        raise RuntimeError("Attack token_slot_mask mismatch")

    slot_mask = id_src["token_slot_mask"].astype(np.float32)
    token_family_id = id_src["token_family_id"].astype(np.int64)
    token_scale_id = id_src["token_scale_id"].astype(np.int64)
    scale_masks, scale_counts = build_scale_masks(token_scale_id, slot_mask)

    fit_n = int(args.train_samples if args.smoke_fit_n <= 0 else min(args.train_samples, args.smoke_fit_n))
    id_eval_n = int(args.id_eval_samples)
    x_train_raw = id_src["token_matrix"][:fit_n].astype(np.float32)
    x_id_raw = id_src["token_matrix"][fit_n : fit_n + id_eval_n].astype(np.float32)
    x_ood_raw = ood_src["token_matrix"].astype(np.float32)
    x_attack_raw = attack_src["token_matrix"].astype(np.float32)

    x_train, mean, std = standardize_tokens(x_train_raw, slot_mask)
    x_id = apply_standardize(x_id_raw, mean, std, slot_mask)
    x_ood = apply_standardize(x_ood_raw, mean, std, slot_mask)
    x_attack = apply_standardize(x_attack_raw, mean, std, slot_mask)

    rows: List[Dict] = []
    diagnostics: List[Dict] = []
    rows.extend(load_reference_rows())

    model_builders = [
        ("frontend_f2_structured_transformer_v1", lambda: F2StructuredTransformerAE(20, 7, 4, 5, token_family_id, token_scale_id, d_model=args.d_model, nhead=args.nhead, num_layers=args.num_layers)),
        ("frontend_f2_token_mlp_control", lambda: F2TokenMLPAE(20, 7, 4, 5, token_family_id, token_scale_id, d_model=args.d_model, bottleneck=args.token_mlp_bottleneck)),
    ]
    score_modes = [
        ("short_mean", "mean over short scales 0.1/0.01"),
        ("z_short_mean_minus_long_mean_a1.50", "ID-z normalized short mean minus 1.50 x long mean"),
    ]

    for loss_name, scale_weights in SCALE_LOSS_PROFILES.items():
        for detector_family, builder in model_builders:
            print(f"[fit] {detector_family} loss={loss_name}", flush=True)
            model = builder()
            hist = train_model(model, x_train, args.epochs, args.batch_size, args.lr, args.device, scale_masks, scale_counts, scale_weights)
            id_scales = score_model_per_scale(model, x_id, args.batch_size, args.device, scale_masks, scale_counts)
            ood_scales = score_model_per_scale(model, x_ood, args.batch_size, args.device, scale_masks, scale_counts)
            attack_scales = score_model_per_scale(model, x_attack, args.batch_size, args.device, scale_masks, scale_counts)
            id_mean = id_scales.mean(axis=0)
            id_std = np.maximum(id_scales.std(axis=0), 1e-6)
            for mode, mode_desc in score_modes:
                sid = aggregate_scale_scores(id_scales, mode, id_mean=id_mean, id_std=id_std)
                sood = aggregate_scale_scores(ood_scales, mode, id_mean=id_mean, id_std=id_std)
                satt = aggregate_scale_scores(attack_scales, mode, id_mean=id_mean, id_std=id_std)
                obj = f"{detector_family.replace('frontend_f2_', '').replace('_control', '')}_{loss_name}_{mode}"
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
                            "loss_profile": loss_name,
                            "scale_weights": ",".join(f"{float(v):.2f}" for v in scale_weights),
                            "num_tokens": 20,
                            "input_tensor": "token_matrix[20x7]",
                            "score_mode_desc": mode_desc,
                        },
                    )
                )
            diagnostics.append(
                {
                    "detector_family": detector_family,
                    "loss_profile": loss_name,
                    "train_loss_start": float(hist[0]),
                    "train_loss_end": float(hist[-1]),
                    "train_loss_min": float(np.min(hist)),
                    "num_tokens": 20,
                }
            )

    df = pd.DataFrame(rows)
    diag = pd.DataFrame(diagnostics)
    df.to_csv(out / "frontend_f2_results.csv", index=False)
    df.to_csv(out / "results.csv", index=False)
    diag.to_csv(out / "frontend_f2_diagnostics.csv", index=False)
    plot_tradeoff(df, plot_dir / "fixed_tradeoff_frontend_f2.png")

    fixed = df[(df["policy_name"] == "fixed_id_q99") & (df["selection_feasible"].astype(bool))].copy()
    cols = [
        "object_label",
        "detector_family",
        "loss_profile",
        "score_label",
        "ood_alarm_ratio_eval",
        "attack_detection_high_purity",
        "roc_auc_attack_high_vs_ood_eval",
    ]
    fixed_md = tv3.md_table(fixed[cols].sort_values(["detector_family", "object_label"]))
    summary = "\n".join(
        [
            "# Frontend-F2 Structured Tokenizer v1",
            "",
            "- Data: Frontend-F2 real structured caches (`7-6` ID, `4-1` OOD, `34-1` attack).",
            "- Input tensor: `token_matrix [20,7]` with token family/scale embeddings.",
            "- Scorer: `short_mean` and `z_short_mean_minus_long_mean_a1.50`.",
            f"- Seed: `{args.seed}`.",
            "",
            "## Fixed q99",
            fixed_md,
        ]
    ) + "\n"
    (out / "frontend_f2_results.md").write_text("# Frontend-F2 Results\n\n## Fixed q99\n" + fixed_md + "\n", encoding="utf-8")
    (out / "summary.md").write_text(summary, encoding="utf-8")
    cfg = {
        "stage": "frontend_f2_structured_tokenizer_v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_tag": args.run_tag,
        "seed": args.seed,
        "structured_benign_run": str(args.structured_benign_run),
        "structured_attack_run": str(args.structured_attack_run),
        "outputs": {
            "results": str(out / "frontend_f2_results.csv"),
            "diagnostics": str(out / "frontend_f2_diagnostics.csv"),
            "summary": str(out / "summary.md"),
            "plots": str(plot_dir),
        },
    }
    (out / "frontend_f2_manifest.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "config.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    append_map(args.run_tag)
    print(f"[done] frontend-f2 tokenizer output: {out}", flush=True)


if __name__ == "__main__":
    main()

