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


FAMILY_NAMES = ["MI_dir", "HH", "HH_jit", "HpHp"]
KIND_NAMES = ["abs_short_0p1", "abs_short_0p01", "delta_local", "delta_mid", "delta_global"]
KIND_IDS = {name: i for i, name in enumerate(KIND_NAMES)}
CONTRAST_KIND_IDS = [KIND_IDS["delta_local"], KIND_IDS["delta_mid"], KIND_IDS["delta_global"]]
PROFILE_FAMILY_WEIGHTS = {
    "uniform": np.asarray([1.0, 1.0, 1.0, 1.0], dtype=np.float32),
    "contrast_family_focus": np.asarray([0.80, 1.35, 0.80, 1.35], dtype=np.float32),
}
PROFILE_KIND_WEIGHTS = {
    "uniform": np.asarray([1.0, 1.0, 1.0, 1.0, 1.0], dtype=np.float32),
    "contrast_family_focus": np.asarray([0.75, 0.90, 1.20, 1.50, 1.85], dtype=np.float32),
}


def load_structured_npz(path: Path) -> Dict[str, np.ndarray]:
    data = np.load(path)
    req = {"token_matrix", "token_slot_mask", "token_family_id", "token_scale_id"}
    missing = req - set(data.files)
    if missing:
        raise RuntimeError(f"Missing keys {sorted(missing)} in {path}")
    out = {k: data[k] for k in data.files}
    if out["token_matrix"].ndim != 3 or out["token_matrix"].shape[1:] != (20, 7):
        raise RuntimeError(f"Expected token_matrix [N,20,7], got {out['token_matrix'].shape} in {path}")
    return out


def build_family_scale_lookup(token_family_id: np.ndarray, token_scale_id: np.ndarray) -> Dict[Tuple[int, int], int]:
    lookup = {}
    for idx, (fam, scale) in enumerate(zip(token_family_id.tolist(), token_scale_id.tolist())):
        lookup[(int(fam), int(scale))] = idx
    for fam in range(4):
        for scale in range(5):
            if (fam, scale) not in lookup:
                raise RuntimeError(f"Missing token for family={fam}, scale={scale}")
    return lookup


def build_contrast_tokens(payload: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
    token_matrix = payload["token_matrix"].astype(np.float32)
    token_slot_mask = payload["token_slot_mask"].astype(np.float32)
    token_family_id = payload["token_family_id"].astype(np.int64)
    token_scale_id = payload["token_scale_id"].astype(np.int64)
    lookup = build_family_scale_lookup(token_family_id, token_scale_id)

    derived_tokens = []
    derived_masks = []
    derived_family_ids = []
    derived_kind_ids = []
    token_names = []

    for fam in range(4):
        idx5 = lookup[(fam, 0)]
        idx3 = lookup[(fam, 1)]
        idx1 = lookup[(fam, 2)]
        idx01 = lookup[(fam, 3)]
        idx001 = lookup[(fam, 4)]

        t5 = token_matrix[:, idx5, :]
        t3 = token_matrix[:, idx3, :]
        t1 = token_matrix[:, idx1, :]
        t01 = token_matrix[:, idx01, :]
        t001 = token_matrix[:, idx001, :]
        slot_mask = token_slot_mask[idx01, :].astype(np.float32)

        short_mean = 0.5 * (t01 + t001)
        long_mean = (t5 + t3 + t1) / 3.0
        token_values = [
            t01,
            t001,
            t001 - t01,
            short_mean - t1,
            short_mean - long_mean,
        ]

        for kind_name, vals in zip(KIND_NAMES, token_values):
            derived_tokens.append(vals)
            derived_masks.append(slot_mask)
            derived_family_ids.append(fam)
            derived_kind_ids.append(KIND_IDS[kind_name])
            token_names.append(f"{FAMILY_NAMES[fam]}::{kind_name}")

    out = {
        "token_matrix": np.stack(derived_tokens, axis=1).astype(np.float32),
        "token_slot_mask": np.stack(derived_masks, axis=0).astype(np.float32),
        "token_family_id": np.asarray(derived_family_ids, dtype=np.int64),
        "token_kind_id": np.asarray(derived_kind_ids, dtype=np.int64),
        "token_names": np.asarray(token_names, dtype=object),
    }
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


def build_token_weights(token_family_id: np.ndarray, token_kind_id: np.ndarray, profile: str) -> np.ndarray:
    fam_w = PROFILE_FAMILY_WEIGHTS[profile]
    kind_w = PROFILE_KIND_WEIGHTS[profile]
    out = np.asarray([fam_w[int(f)] * kind_w[int(k)] for f, k in zip(token_family_id, token_kind_id)], dtype=np.float32)
    return out / max(float(np.mean(out)), 1e-6)


class ContrastTransformerAE(nn.Module):
    def __init__(self, num_tokens: int, token_dim: int, token_family_id: np.ndarray, token_kind_id: np.ndarray, d_model: int = 64, nhead: int = 4, num_layers: int = 2):
        super().__init__()
        self.token_proj = nn.Linear(token_dim, d_model)
        self.family_emb = nn.Embedding(4, d_model)
        self.kind_emb = nn.Embedding(len(KIND_NAMES), d_model)
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
        self.register_buffer("token_kind_id", torch.tensor(token_kind_id, dtype=torch.long))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.token_proj(x)
        h = h + self.family_emb(self.token_family_id).unsqueeze(0) + self.kind_emb(self.token_kind_id).unsqueeze(0) + self.pos
        h = self.encoder(h)
        return self.out_proj(self.norm(h))


class ContrastTokenMLPAE(nn.Module):
    def __init__(self, num_tokens: int, token_dim: int, token_family_id: np.ndarray, token_kind_id: np.ndarray, d_model: int = 64, bottleneck: int = 192):
        super().__init__()
        self.token_proj = nn.Linear(token_dim, d_model)
        self.family_emb = nn.Embedding(4, d_model)
        self.kind_emb = nn.Embedding(len(KIND_NAMES), d_model)
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
        self.register_buffer("token_kind_id", torch.tensor(token_kind_id, dtype=torch.long))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.token_proj(x)
        h = h + self.family_emb(self.token_family_id).unsqueeze(0) + self.kind_emb(self.token_kind_id).unsqueeze(0) + self.pos
        b = h.size(0)
        h = self.mlp(h.reshape(b, self.num_tokens * self.d_model)).reshape(b, self.num_tokens, self.d_model)
        return self.out_proj(h)


def token_rmse(pred: torch.Tensor, target: torch.Tensor, slot_mask_t: torch.Tensor) -> torch.Tensor:
    err = (pred - target) ** 2
    denom = torch.clamp(slot_mask_t.sum(dim=1), min=1.0).view(1, -1)
    sse = (err * slot_mask_t.unsqueeze(0)).sum(dim=2)
    return torch.sqrt(torch.clamp(sse / denom, min=1e-12))


def train_model(model: nn.Module, x_train: np.ndarray, epochs: int, batch_size: int, lr: float, device: str, token_slot_mask: np.ndarray, token_weights: np.ndarray) -> List[float]:
    model.to(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    slot_mask_t = torch.as_tensor(token_slot_mask, dtype=torch.float32, device=device)
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
            loss = torch.mean(token_rmse(pred, xb, slot_mask_t) * weight_t)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            total += float(loss.detach().item()) * len(xb)
            count += len(xb)
        hist.append(total / max(1, count))
    return hist


def score_token_rmse(model: nn.Module, x: np.ndarray, batch_size: int, device: str, token_slot_mask: np.ndarray) -> np.ndarray:
    model.to(device)
    model.eval()
    slot_mask_t = torch.as_tensor(token_slot_mask, dtype=torch.float32, device=device)
    out = []
    with torch.no_grad():
        for st in range(0, len(x), batch_size):
            xb = torch.from_numpy(x[st : st + batch_size].astype(np.float32)).to(device)
            pred = model(xb)
            out.append(token_rmse(pred, xb, slot_mask_t).detach().cpu().numpy())
    return np.concatenate(out, axis=0).astype(np.float64)


def aggregate_scores(token_scores: np.ndarray, token_kind_id: np.ndarray, token_weights: np.ndarray, mode: str) -> np.ndarray:
    if mode == "contrast_mean":
        mask = np.isin(token_kind_id, CONTRAST_KIND_IDS)
        return token_scores[:, mask].mean(axis=1)
    if mode == "global_contrast_mean":
        mask = token_kind_id == KIND_IDS["delta_global"]
        return token_scores[:, mask].mean(axis=1)
    if mode == "weighted_contrast":
        mask = np.isin(token_kind_id, CONTRAST_KIND_IDS)
        w = token_weights[mask]
        w = w / max(float(np.mean(w)), 1e-6)
        return (token_scores[:, mask] * w.reshape(1, -1)).mean(axis=1)
    raise ValueError(mode)


def load_reference_rows() -> List[Dict]:
    refs = tv3.load_reference_rows()
    p1 = WORKTREE_ROOT / "runs" / "frontend_f2_structured_tokenizer_v1_smoke_2026-04-13" / "frontend_f2_results.csv"
    if p1.exists():
        df = pd.read_csv(p1)
        keep = {
            "structured_transformer_v1_uniform_z_short_mean_minus_long_mean_a1.50",
            "token_mlp_uniform_z_short_mean_minus_long_mean_a1.50",
        }
        refs.extend(df[df["object_label"].isin(keep)].to_dict("records"))
    p2 = WORKTREE_ROOT / "runs" / "frontend100_structured_frontend_v1_smoke_2026-04-13" / "structured_frontend_v1_results.csv"
    if p2.exists():
        df = pd.read_csv(p2)
        keep = {"transformer_v1_short_focus_z_short_mean_minus_long_mean_a1.50"}
        refs.extend(df[df["object_label"].isin(keep)].to_dict("records"))
    return refs


def plot_tradeoff(df: pd.DataFrame, out: Path) -> None:
    fixed = df[(df["policy_name"].eq("fixed_id_q99")) & (df["selection_feasible"].astype(bool))].copy()
    plt.figure(figsize=(11, 7))
    for _, r in fixed.iterrows():
        fam = str(r["detector_family"])
        if fam == "frontend_f2_contrast_transformer_v1":
            color = "#1f77b4"
        elif fam == "frontend_f2_contrast_token_mlp_control":
            color = "#ff7f0e"
        elif fam == "da":
            color = "#d62728"
        elif fam == "timescale_transformer_v1_2":
            color = "#17becf"
        elif fam == "structured_frontend_transformer_v1":
            color = "#9467bd"
        else:
            color = "#7f7f7f"
        x = float(r["ood_alarm_ratio_eval"])
        y = float(r["attack_detection_high_purity"])
        plt.scatter(x, y, c=color, s=88)
        plt.text(x + 0.004, y + 0.006, str(r["object_label"]), fontsize=7)
    plt.xlabel("OOD benign alarm ratio (fixed q99)")
    plt.ylabel("High-purity attack detection")
    plt.title("Frontend-F2 contrast-token v1 fixed trade-off")
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
    text += f"\n- `{run_tag}`: Frontend-F2 contrast-token v1 derives short-vs-long anomaly-increment tokens directly from structured caches and evaluates transformer/token-MLP backends on real `7-6/4-1/34-1` data; path: `runs/{run_tag}/`.\n"
    p.write_text(text, encoding="utf-8")


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    ap = argparse.ArgumentParser(description="Frontend-F2 contrast-token v1.")
    ap.add_argument("--run-tag", default=f"frontend_f2_contrast_tokenizer_v1_{today}")
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
    plot_dir = out / "frontend_f2_contrast_plots"
    plot_dir.mkdir(exist_ok=True)
    (out / "command.txt").write_text("python " + " ".join(sys.argv) + "\n", encoding="utf-8")

    id_src = load_structured_npz(args.structured_benign_run / "id_source_structured.npz")
    ood_src = load_structured_npz(args.structured_benign_run / "ood_benign_source_structured.npz")
    attack_src = load_structured_npz(args.structured_attack_run / "attack_source_structured.npz")
    stage2 = json.loads(args.stage2_manifest.read_text(encoding="utf-8-sig"))
    stage2_idx = resc.build_stage2_indices(stage2)

    contrast_id = build_contrast_tokens(id_src)
    contrast_ood = build_contrast_tokens(ood_src)
    contrast_attack = build_contrast_tokens(attack_src)

    token_slot_mask = contrast_id["token_slot_mask"]
    token_family_id = contrast_id["token_family_id"]
    token_kind_id = contrast_id["token_kind_id"]

    fit_n = int(args.train_samples if args.smoke_fit_n <= 0 else min(args.train_samples, args.smoke_fit_n))
    id_eval_n = int(args.id_eval_samples)
    x_train_raw = contrast_id["token_matrix"][:fit_n].astype(np.float32)
    x_id_raw = contrast_id["token_matrix"][fit_n : fit_n + id_eval_n].astype(np.float32)
    x_ood_raw = contrast_ood["token_matrix"].astype(np.float32)
    x_attack_raw = contrast_attack["token_matrix"].astype(np.float32)

    x_train, mean, std = standardize_tokens(x_train_raw, token_slot_mask)
    x_id = apply_standardize(x_id_raw, mean, std, token_slot_mask)
    x_ood = apply_standardize(x_ood_raw, mean, std, token_slot_mask)
    x_attack = apply_standardize(x_attack_raw, mean, std, token_slot_mask)

    rows: List[Dict] = []
    diagnostics: List[Dict] = []
    rows.extend(load_reference_rows())

    model_builders = [
        ("frontend_f2_contrast_transformer_v1", lambda: ContrastTransformerAE(20, 7, token_family_id, token_kind_id, d_model=args.d_model, nhead=args.nhead, num_layers=args.num_layers)),
        ("frontend_f2_contrast_token_mlp_control", lambda: ContrastTokenMLPAE(20, 7, token_family_id, token_kind_id, d_model=args.d_model, bottleneck=args.token_mlp_bottleneck)),
    ]
    score_modes = [
        ("contrast_mean", "mean RMSE over all contrast tokens"),
        ("global_contrast_mean", "mean RMSE over delta_global tokens only"),
        ("weighted_contrast", "family/kind weighted RMSE over all contrast tokens"),
    ]

    for profile in ["uniform", "contrast_family_focus"]:
        token_weights = build_token_weights(token_family_id, token_kind_id, profile)
        for detector_family, builder in model_builders:
            print(f"[fit] {detector_family} profile={profile}", flush=True)
            model = builder()
            hist = train_model(model, x_train, args.epochs, args.batch_size, args.lr, args.device, token_slot_mask, token_weights)
            id_token_scores = score_token_rmse(model, x_id, args.batch_size, args.device, token_slot_mask)
            ood_token_scores = score_token_rmse(model, x_ood, args.batch_size, args.device, token_slot_mask)
            attack_token_scores = score_token_rmse(model, x_attack, args.batch_size, args.device, token_slot_mask)
            for mode, mode_desc in score_modes:
                sid = aggregate_scores(id_token_scores, token_kind_id, token_weights, mode)
                sood = aggregate_scores(ood_token_scores, token_kind_id, token_weights, mode)
                satt = aggregate_scores(attack_token_scores, token_kind_id, token_weights, mode)
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
                            "input_tensor": "contrast_token_matrix[20x7]",
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
                }
            )

    df = pd.DataFrame(rows)
    diag = pd.DataFrame(diagnostics)
    df.to_csv(out / "frontend_f2_contrast_results.csv", index=False)
    df.to_csv(out / "results.csv", index=False)
    diag.to_csv(out / "frontend_f2_contrast_diagnostics.csv", index=False)
    plot_tradeoff(df, plot_dir / "fixed_tradeoff_frontend_f2_contrast.png")

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
            "# Frontend-F2 Contrast Tokenizer v1",
            "",
            "- Data: real Frontend-F2 structured caches (`7-6` ID, `4-1` OOD, `34-1` attack).",
            "- Input tensor: contrast tokens derived from short-vs-long anomaly increments.",
            "- Models: contrast transformer and token-MLP control.",
            "",
            "## Fixed q99",
            fixed_md,
        ]
    ) + "\n"
    (out / "frontend_f2_contrast_results.md").write_text("# Frontend-F2 Contrast Results\n\n## Fixed q99\n" + fixed_md + "\n", encoding="utf-8")
    (out / "summary.md").write_text(summary, encoding="utf-8")
    cfg = {
        "stage": "frontend_f2_contrast_tokenizer_v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_tag": args.run_tag,
        "seed": args.seed,
        "outputs": {
            "results": str(out / "frontend_f2_contrast_results.csv"),
            "diagnostics": str(out / "frontend_f2_contrast_diagnostics.csv"),
            "summary": str(out / "summary.md"),
            "plots": str(plot_dir),
        },
    }
    (out / "frontend_f2_contrast_manifest.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "config.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    append_map(args.run_tag)
    print(f"[done] frontend-f2 contrast tokenizer output: {out}", flush=True)


if __name__ == "__main__":
    main()

