from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

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
from frontend_f2_5_temporal_tokenizer import (
    ID_CALIB_POLICY,
    TOKEN_FAMILY_ID,
    TOKEN_SCALE_ID,
    V3_CHANNEL_NAMES,
    aggregate_scores,
    build_token_weights,
    id_budget_calibrate,
    load_v3_matrix,
    make_combined_summary,
)


def compute_innovation_matrix(
    x: np.ndarray,
    window_size: int,
    eps: float = 1e-6,
    clip: float = 8.0,
) -> np.ndarray:
    """
    Convert expression_v3 [N,20,8] into current-vs-history innovation rows.
    Output row i corresponds to original target row i + window_size.
    """
    if x.ndim != 3 or x.shape[1:] != (20, 8):
        raise RuntimeError(f"Expected [N,20,8], got {x.shape}")
    k = int(window_size)
    if k < 1 or len(x) <= k:
        raise ValueError(f"Invalid window_size={k} for matrix length={len(x)}")

    x64 = x.astype(np.float64, copy=False)
    zero = np.zeros((1, x64.shape[1], x64.shape[2]), dtype=np.float64)
    csum = np.concatenate([zero, np.cumsum(x64, axis=0)], axis=0)
    csum2 = np.concatenate([zero, np.cumsum(x64 * x64, axis=0)], axis=0)

    hist_sum = csum[k: len(x)] - csum[: len(x) - k]
    hist_sum2 = csum2[k: len(x)] - csum2[: len(x) - k]
    mean = hist_sum / float(k)
    var = np.maximum(hist_sum2 / float(k) - mean * mean, eps)
    target = x64[k:]
    innov = (target - mean) / np.sqrt(var)
    innov = np.nan_to_num(innov, nan=0.0, posinf=0.0, neginf=0.0)
    innov = np.clip(innov, -float(clip), float(clip)).astype(np.float32)
    return innov


def standardize_tokens(x: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = x.mean(axis=0).astype(np.float32)
    std = np.maximum(x.std(axis=0), 1e-6).astype(np.float32)
    z = ((x - mean[None]) / std[None]).astype(np.float32)
    return z, mean, std


def apply_standardize(x: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    return ((x - mean[None]) / std[None]).astype(np.float32)


def innovation_audit(x: np.ndarray) -> dict:
    finite = np.isfinite(x)
    abs_finite = np.abs(x[finite])
    return {
        "shape": list(x.shape),
        "nan_count": int(np.isnan(x).sum()),
        "inf_count": int(np.isinf(x).sum()),
        "max_abs": float(np.max(abs_finite)) if abs_finite.size else 0.0,
        "p99_abs": float(np.percentile(abs_finite, 99)) if abs_finite.size else 0.0,
    }


class InnovationTokenEmbedding(nn.Module):
    def __init__(self, d_model: int = 64):
        super().__init__()
        self.per_token_proj = nn.Linear(6, d_model)
        self.cross_scale_proj = nn.Linear(2, d_model)
        self.family_emb = nn.Embedding(4, d_model)
        self.scale_emb = nn.Embedding(5, d_model)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        per = self.per_token_proj(x[:, :, :6])
        cross = self.cross_scale_proj(x[:, :, 6:])
        family_ids = torch.as_tensor(TOKEN_FAMILY_ID, dtype=torch.long, device=x.device)
        scale_ids = torch.as_tensor(TOKEN_SCALE_ID, dtype=torch.long, device=x.device)
        f_emb = self.family_emb(family_ids)
        s_emb = self.scale_emb(scale_ids)
        return per + cross + f_emb + s_emb


class InnovationTransformerAE(nn.Module):
    def __init__(self, token_dim: int = 8, d_model: int = 64, nhead: int = 4, num_layers: int = 2):
        super().__init__()
        self.embedding = InnovationTokenEmbedding(d_model)
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

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.embedding(x)
        h = self.encoder(h)
        return self.out_proj(self.norm(h))


class InnovationTokenMLPAE(nn.Module):
    def __init__(self, token_dim: int = 8, d_model: int = 64, bottleneck: int = 192):
        super().__init__()
        self.embedding = InnovationTokenEmbedding(d_model)
        self.num_tokens = 20
        self.d_model = int(d_model)
        flat_dim = self.num_tokens * self.d_model
        self.mlp = nn.Sequential(
            nn.LayerNorm(flat_dim),
            nn.Linear(flat_dim, bottleneck),
            nn.GELU(),
            nn.Linear(bottleneck, flat_dim),
            nn.GELU(),
        )
        self.out_proj = nn.Sequential(nn.LayerNorm(d_model), nn.Linear(d_model, token_dim))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.embedding(x)
        b = h.size(0)
        h = self.mlp(h.reshape(b, self.num_tokens * self.d_model)).reshape(b, self.num_tokens, self.d_model)
        return self.out_proj(h)


def token_rmse(pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    err = (pred - target) ** 2
    return torch.sqrt(torch.clamp(err.mean(dim=2), min=1e-12))


def train_model(
    model: nn.Module,
    x_train: np.ndarray,
    epochs: int,
    batch_size: int,
    lr: float,
    device: str,
    token_weights: np.ndarray,
) -> List[float]:
    model.to(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    weight_t = torch.as_tensor(token_weights, dtype=torch.float32, device=device).view(1, -1)
    ds = TensorDataset(torch.from_numpy(x_train.astype(np.float32)))
    loader = DataLoader(ds, batch_size=batch_size, shuffle=True, drop_last=False)
    hist: List[float] = []
    for _ in range(int(epochs)):
        model.train()
        total, count = 0.0, 0
        for (xb,) in loader:
            xb = xb.to(device)
            opt.zero_grad()
            pred = model(xb)
            loss = torch.mean(token_rmse(pred, xb) * weight_t)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            total += float(loss.detach().item()) * len(xb)
            count += len(xb)
        hist.append(total / max(1, count))
    return hist


def score_token_rmse(model: nn.Module, x: np.ndarray, batch_size: int, device: str) -> np.ndarray:
    model.to(device)
    model.eval()
    out = []
    with torch.no_grad():
        for st in range(0, len(x), batch_size):
            xb = torch.from_numpy(x[st: st + batch_size].astype(np.float32)).to(device)
            pred = model(xb)
            out.append(token_rmse(pred, xb).detach().cpu().numpy())
    return np.concatenate(out, axis=0).astype(np.float64)


def adjusted_stage2_indices(stage2_idx: dict, window_size: int, attack_len: int) -> dict:
    out = {}
    for key, values in stage2_idx.items():
        arr = np.asarray(values, dtype=np.int64)
        arr = arr[(arr >= window_size) & (arr < attack_len)]
        out[key] = (arr - window_size).astype(np.int64)
    return out


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    ap = argparse.ArgumentParser(description="Frontend-F2.6 innovation tokenizer smoke.")
    ap.add_argument("--run-tag", default=f"frontend_f2_6_innovation_smoke_{today}")
    ap.add_argument(
        "--benign-data-dir",
        type=Path,
        default=WORKTREE_ROOT / "runs" / "frontend_f2_expression_v3_crosscapture_stage1_2026-04-16" / "data",
    )
    ap.add_argument(
        "--attack-data-dir",
        type=Path,
        default=WORKTREE_ROOT / "runs" / "frontend_f2_expression_v3_attack_source_2026-04-16" / "data",
    )
    ap.add_argument(
        "--stage2-manifest",
        type=Path,
        default=WORKTREE_ROOT.parents[1]
        / "KitNET-py-master"
        / "KitNET-py-master"
        / "runs"
        / "frontend100_joint_eval_stage2_2026-04-01"
        / "attack_manifest_stage2.json",
    )
    ap.add_argument("--window-size", type=int, default=5)
    ap.add_argument("--innovation-clip", type=float, default=8.0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--batch-size", type=int, default=256)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--train-samples", type=int, default=8000)
    ap.add_argument("--id-eval-samples", type=int, default=5000)
    ap.add_argument("--calibration-budget", type=int, default=5000)
    ap.add_argument("--calibration-target", type=float, default=0.01)
    ap.add_argument("--scan-points", type=int, default=1200)
    ap.add_argument("--d-model", type=int, default=64)
    ap.add_argument("--nhead", type=int, default=4)
    ap.add_argument("--num-layers", type=int, default=2)
    ap.add_argument("--token-mlp-bottleneck", type=int, default=192)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = ap.parse_args()

    tv3.set_seed(args.seed)
    out = WORKTREE_ROOT / "runs" / args.run_tag
    out.mkdir(parents=True, exist_ok=True)
    (out / "command.txt").write_text("python " + " ".join(sys.argv) + "\n", encoding="utf-8")

    id_raw = load_v3_matrix(args.benign_data_dir / "id_source_expression_v3_matrix.npy")
    ood_raw = load_v3_matrix(args.benign_data_dir / "ood_benign_source_expression_v3_matrix.npy")
    atk_raw = load_v3_matrix(args.attack_data_dir / "attack_source_expression_v3_matrix.npy")

    print(f"[innovation] window={args.window_size} clip={args.innovation_clip}", flush=True)
    id_innov = compute_innovation_matrix(id_raw, args.window_size, clip=args.innovation_clip)
    ood_innov = compute_innovation_matrix(ood_raw, args.window_size, clip=args.innovation_clip)
    atk_innov = compute_innovation_matrix(atk_raw, args.window_size, clip=args.innovation_clip)

    fit_n = min(int(args.train_samples), len(id_innov))
    id_eval_end = min(len(id_innov), fit_n + int(args.id_eval_samples))
    x_train_raw = id_innov[:fit_n]
    x_id_raw = id_innov[fit_n:id_eval_end]
    x_ood_raw = ood_innov
    x_atk_raw = atk_innov

    x_train, mean_stat, std_stat = standardize_tokens(x_train_raw)
    x_id = apply_standardize(x_id_raw, mean_stat, std_stat)
    x_ood = apply_standardize(x_ood_raw, mean_stat, std_stat)
    x_attack = apply_standardize(x_atk_raw, mean_stat, std_stat)

    stage2 = json.loads(args.stage2_manifest.read_text(encoding="utf-8-sig"))
    stage2_idx = adjusted_stage2_indices(resc.build_stage2_indices(stage2), args.window_size, len(atk_raw))
    if len(stage2_idx["high"]) == 0:
        raise RuntimeError("No high-purity attack samples remain after innovation window offset.")

    model_builders = [
        (
            "frontend_f2_6_innovation_transformer_v1",
            lambda: InnovationTransformerAE(
                token_dim=8,
                d_model=args.d_model,
                nhead=args.nhead,
                num_layers=args.num_layers,
            ),
        ),
        (
            "frontend_f2_6_innovation_token_mlp_control",
            lambda: InnovationTokenMLPAE(
                token_dim=8,
                d_model=args.d_model,
                bottleneck=args.token_mlp_bottleneck,
            ),
        ),
    ]
    score_modes = [
        ("token_mean", "mean RMSE over all 20 innovation tokens"),
        ("short_scale_mean", "mean RMSE over scale 0.1/0.01 tokens"),
        ("weighted_token_mean", "family/scale weighted RMSE over all 20 innovation tokens"),
        ("mi_dir_mean", "mean RMSE over MI_dir family tokens only"),
        ("hphp_mean", "mean RMSE over HpHp family tokens only"),
        ("mi_hphp_mean", "mean RMSE over MI_dir+HpHp families only"),
        ("mi_hphp_short_mean", "mean RMSE over MI_dir+HpHp at short scales 0.1s+0.01s"),
    ]

    rows: List[Dict] = []
    diagnostics: List[Dict] = []
    for profile in ["uniform", "family_short_focus"]:
        token_weights = build_token_weights(profile)
        for detector_family, builder in model_builders:
            print(f"[fit] {detector_family} profile={profile}", flush=True)
            model = builder()
            hist = train_model(model, x_train, args.epochs, args.batch_size, args.lr, args.device, token_weights)
            id_token_scores = score_token_rmse(model, x_id, args.batch_size, args.device)
            ood_token_scores = score_token_rmse(model, x_ood, args.batch_size, args.device)
            atk_token_scores = score_token_rmse(model, x_attack, args.batch_size, args.device)

            for mode, mode_desc in score_modes:
                sid = aggregate_scores(id_token_scores, TOKEN_SCALE_ID, token_weights, mode, TOKEN_FAMILY_ID)
                sood = aggregate_scores(ood_token_scores, TOKEN_SCALE_ID, token_weights, mode, TOKEN_FAMILY_ID)
                satt = aggregate_scores(atk_token_scores, TOKEN_SCALE_ID, token_weights, mode, TOKEN_FAMILY_ID)
                obj = f"{detector_family.replace('frontend_f2_6_', 'f2_6_').replace('_control', '')}_{profile}_{mode}"
                extra_meta = {
                    "source_mode": "computed_now",
                    "token_profile": profile,
                    "input_tensor": f"expression_v3 innovation(window={args.window_size})[20x8]",
                    "channel_names": ",".join(V3_CHANNEL_NAMES),
                    "score_mode_desc": mode_desc,
                    "innovation_window_size": args.window_size,
                    "innovation_clip": args.innovation_clip,
                }
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
                        extra=extra_meta,
                    )
                )

                ood_eval_split = sood[args.calibration_budget:]
                atk_high = satt[stage2_idx["high"]]
                auc_val = resc.compute_auc(ood_eval_scores=ood_eval_split, attack_high_scores=atk_high)
                calib_result = id_budget_calibrate(
                    score_id_eval=sid,
                    score_ood_eval=ood_eval_split,
                    score_attack_high=atk_high,
                    budget=args.calibration_budget,
                    target_alarm=args.calibration_target,
                    seed=args.seed,
                )
                thr = calib_result["threshold"]
                rows.append(
                    {
                        "object_label": obj,
                        "detector_family": detector_family,
                        "score_label": mode,
                        "seed": args.seed,
                        "policy_name": ID_CALIB_POLICY,
                        "selection_feasible": calib_result["feasible"],
                        "threshold_source": (
                            f"min ID-eval q (budget={args.calibration_budget}) "
                            f"s.t. ood_alarm<=target={args.calibration_target:.3f}"
                        ),
                        "threshold": thr if np.isfinite(thr) else float("nan"),
                        "id_alarm_ratio": float(np.mean(sid > thr)) if np.isfinite(thr) else float("nan"),
                        "ood_alarm_ratio_full": float(np.mean(sood > thr)) if np.isfinite(thr) else float("nan"),
                        "ood_alarm_ratio_eval": calib_result["calibrated_ood_alarm"],
                        "attack_detection_all": float(np.mean(satt > thr)) if np.isfinite(thr) else float("nan"),
                        "attack_detection_high_purity": calib_result["calibrated_det"],
                        "attack_detection_boundary": float("nan"),
                        "roc_auc_attack_high_vs_ood_eval": float(auc_val),
                        **extra_meta,
                    }
                )

            diagnostics.append(
                {
                    "detector_family": detector_family,
                    "token_profile": profile,
                    "train_loss_start": float(hist[0]),
                    "train_loss_end": float(hist[-1]),
                    "train_loss_min": float(np.min(hist)),
                    "window_size": int(args.window_size),
                    "train_samples": int(len(x_train)),
                    "id_eval_samples": int(len(x_id)),
                    "ood_samples": int(len(x_ood)),
                    "attack_samples": int(len(x_attack)),
                }
            )

    df = pd.DataFrame(rows)
    diag = pd.DataFrame(diagnostics)
    df.to_csv(out / "frontend_f2_6_innovation_results.csv", index=False)
    df.to_csv(out / "results.csv", index=False)
    diag.to_csv(out / "frontend_f2_6_innovation_diagnostics.csv", index=False)
    combined = make_combined_summary(df, calib_policy=ID_CALIB_POLICY)
    combined.to_csv(out / "frontend_f2_6_innovation_combined.csv", index=False)

    audit_payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "window_size": int(args.window_size),
        "innovation_clip": float(args.innovation_clip),
        "id": innovation_audit(id_innov),
        "ood_benign": innovation_audit(ood_innov),
        "attack": innovation_audit(atk_innov),
    }
    (out / "innovation_audit.json").write_text(json.dumps(audit_payload, indent=2), encoding="utf-8")

    combined_display_cols = [
        "object_label",
        "detector_family",
        "token_profile",
        "score_label",
        "fixed_alarm",
        "fixed_det",
        "calibrated_alarm",
        "calibrated_det",
        "selection_feasible",
        "roc_auc_attack_high_vs_ood_eval",
    ]
    combined_md = tv3.md_table(combined[[c for c in combined_display_cols if c in combined.columns]])
    target_pct = int(round(args.calibration_target * 100))
    summary = "\n".join(
        [
            "# Frontend-F2.6 Innovation Tokenizer Smoke",
            "",
            "- Data: Frontend-F2 expression_v3 sources (`7-6` ID, `4-1` OOD, `34-1` attack).",
            f"- Innovation: current frame minus rolling mean over previous K={args.window_size}, divided by rolling std.",
            f"- Innovation clip: +/-{args.innovation_clip:g}.",
            "- Model and scoring: same frontend-f2 tokenizer protocol, using innovation tensor [20,8].",
            f"- Calibration: ID-eval budget={args.calibration_budget}, target OOD alarm <= {args.calibration_target:.2f} ({target_pct}%).",
            "",
            "## Combined: fixed_alarm / fixed_det / calibrated_alarm / calibrated_det / AUC",
            f"(calibration policy: `{ID_CALIB_POLICY}`)",
            combined_md,
        ]
    ) + "\n"
    (out / "summary.md").write_text(summary, encoding="utf-8")

    cfg = {
        "stage": "frontend_f2_6_innovation_tokenizer_v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_tag": args.run_tag,
        "seed": args.seed,
        "window_size": args.window_size,
        "innovation_clip": args.innovation_clip,
        "benign_data_dir": str(args.benign_data_dir),
        "attack_data_dir": str(args.attack_data_dir),
        "stage2_manifest": str(args.stage2_manifest),
        "calibration_budget": args.calibration_budget,
        "calibration_target": args.calibration_target,
        "calibration_policy": ID_CALIB_POLICY,
        "outputs": {
            "results": str(out / "frontend_f2_6_innovation_results.csv"),
            "combined": str(out / "frontend_f2_6_innovation_combined.csv"),
            "diagnostics": str(out / "frontend_f2_6_innovation_diagnostics.csv"),
            "summary": str(out / "summary.md"),
            "audit": str(out / "innovation_audit.json"),
        },
    }
    (out / "frontend_f2_6_innovation_metadata.json").write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out / "config.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[done] frontend-f2.6 innovation output: {out}", flush=True)


if __name__ == "__main__":
    main()
