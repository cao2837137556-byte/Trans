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
from torch.utils.data import DataLoader, Dataset

THIS_DIR = Path(__file__).resolve().parent
REPO_DIR = THIS_DIR.parent
WORKTREE_ROOT = REPO_DIR.parent
for p in [THIS_DIR, REPO_DIR]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import frontend100_negative_recipe_rescoring as resc
import frontend100_timescale_tokenizer_v1_3 as tv3


TOKEN_FAMILY_ID = np.repeat(np.arange(4), 5).astype(np.int64)
TOKEN_SCALE_ID = np.tile(np.arange(5), 4).astype(np.int64)
ID_CALIB_POLICY = "id_budget_calibrated_target1pct"

V3_CHANNEL_NAMES = [
    "mean_slog",
    "std_slog",
    "dispersion_slog",
    "number_log",
    "cov_sign",
    "pcc_slog",
    "burst_ratio",
    "dispersion_delta_slog",
]

PROFILE_FAMILY_WEIGHTS = {
    "uniform": np.asarray([1.0, 1.0, 1.0, 1.0], dtype=np.float32),
    "family_short_focus": np.asarray([0.80, 1.35, 0.80, 1.35], dtype=np.float32),
}
PROFILE_SCALE_WEIGHTS = {
    "uniform": np.asarray([1.0, 1.0, 1.0, 1.0, 1.0], dtype=np.float32),
    "family_short_focus": np.asarray([0.55, 0.70, 0.95, 1.35, 1.45], dtype=np.float32),
}


def load_v3_matrix(path: Path) -> np.ndarray:
    arr = np.load(path)
    if arr.ndim != 3 or arr.shape[1:] != (20, 8):
        raise RuntimeError(f"Expected [N,20,8], got {arr.shape} from {path}")
    return arr.astype(np.float32)


def standardize_tokens(x: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = x.mean(axis=0).astype(np.float32)
    std = np.maximum(x.std(axis=0), 1e-6).astype(np.float32)
    z = ((x - mean[None]) / std[None]).astype(np.float32)
    return z, mean, std


def apply_standardize(x: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    return ((x - mean[None]) / std[None]).astype(np.float32)


class TemporalPredictionDataset(Dataset):
    """Causal windows: rows [t-K, t) predict row t."""

    def __init__(self, z_matrix: np.ndarray, window_size: int, target_start: int, target_end: int):
        if z_matrix.ndim != 3 or z_matrix.shape[1:] != (20, 8):
            raise RuntimeError(f"Expected standardized matrix [N,20,8], got {z_matrix.shape}")
        self.z_matrix = z_matrix.astype(np.float32, copy=False)
        self.window_size = int(window_size)
        self.target_start = max(int(target_start), self.window_size)
        self.target_end = min(int(target_end), len(z_matrix))
        self.length = max(0, self.target_end - self.target_start)

    def __len__(self) -> int:
        return self.length

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        target_idx = self.target_start + int(idx)
        hist = self.z_matrix[target_idx - self.window_size : target_idx]
        target = self.z_matrix[target_idx]
        return torch.from_numpy(hist), torch.from_numpy(target)


class TemporalTokenEmbedding(nn.Module):
    def __init__(self, d_model: int = 64, window_size: int = 5):
        super().__init__()
        self.per_token_proj = nn.Linear(6, d_model)
        self.cross_scale_proj = nn.Linear(2, d_model)
        self.family_emb = nn.Embedding(4, d_model)
        self.scale_emb = nn.Embedding(5, d_model)
        self.time_emb = nn.Embedding(window_size, d_model)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: [B,K,20,8]
        _, k, _, _ = x.shape
        per = self.per_token_proj(x[..., :6])
        cross = self.cross_scale_proj(x[..., 6:])

        family_ids = torch.as_tensor(TOKEN_FAMILY_ID, dtype=torch.long, device=x.device)
        scale_ids = torch.as_tensor(TOKEN_SCALE_ID, dtype=torch.long, device=x.device)
        time_ids = torch.arange(k, dtype=torch.long, device=x.device)

        f_emb = self.family_emb(family_ids).view(1, 1, 20, -1)
        s_emb = self.scale_emb(scale_ids).view(1, 1, 20, -1)
        t_emb = self.time_emb(time_ids).view(1, k, 1, -1)
        return per + cross + f_emb + s_emb + t_emb


class TemporalTransformerPredictor(nn.Module):
    def __init__(self, d_model: int = 64, nhead: int = 4, num_layers: int = 2, window_size: int = 5):
        super().__init__()
        self.embedding = TemporalTokenEmbedding(d_model=d_model, window_size=window_size)
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
        self.out_proj = nn.Sequential(nn.Linear(d_model, d_model), nn.GELU(), nn.Linear(d_model, 8))

    def forward(self, hist: torch.Tensor) -> torch.Tensor:
        # hist: [B,K,20,8], target is not part of the input.
        b, k, t, _ = hist.shape
        h = self.embedding(hist).reshape(b, k * t, -1)
        h = self.encoder(h).reshape(b, k, t, -1)
        last_context = h[:, -1, :, :]
        return self.out_proj(self.norm(last_context))


def build_token_weights(profile: str) -> np.ndarray:
    fam_w = PROFILE_FAMILY_WEIGHTS[profile]
    scale_w = PROFILE_SCALE_WEIGHTS[profile]
    out = np.asarray(
        [fam_w[int(f)] * scale_w[int(s)] for f, s in zip(TOKEN_FAMILY_ID, TOKEN_SCALE_ID)],
        dtype=np.float32,
    )
    return out / max(float(np.mean(out)), 1e-6)


def token_rmse(pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    err = (pred - target) ** 2
    return torch.sqrt(torch.clamp(err.mean(dim=2), min=1e-12))


def train_model(
    model: nn.Module,
    ds: Dataset,
    epochs: int,
    batch_size: int,
    lr: float,
    device: str,
    token_weights: np.ndarray,
) -> List[float]:
    model.to(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    weight_t = torch.as_tensor(token_weights, dtype=torch.float32, device=device).view(1, -1)
    loader = DataLoader(ds, batch_size=batch_size, shuffle=True, drop_last=False)
    hist: List[float] = []
    for _ in range(int(epochs)):
        model.train()
        total, count = 0.0, 0
        for xb, yb in loader:
            xb = xb.to(device)
            yb = yb.to(device)
            opt.zero_grad()
            pred = model(xb)
            loss = torch.mean(token_rmse(pred, yb) * weight_t)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            total += float(loss.detach().item()) * len(xb)
            count += len(xb)
        hist.append(total / max(1, count))
    return hist


def score_token_rmse(model: nn.Module, ds: Dataset, batch_size: int, device: str) -> np.ndarray:
    model.to(device)
    model.eval()
    out = []
    loader = DataLoader(ds, batch_size=batch_size, shuffle=False, drop_last=False)
    with torch.no_grad():
        for xb, yb in loader:
            xb = xb.to(device)
            yb = yb.to(device)
            pred = model(xb)
            out.append(token_rmse(pred, yb).detach().cpu().numpy())
    if not out:
        return np.zeros((0, 20), dtype=np.float64)
    return np.concatenate(out, axis=0).astype(np.float64)


def aggregate_scores(
    token_scores: np.ndarray,
    token_scale_id: np.ndarray,
    token_weights: np.ndarray,
    mode: str,
    token_family_id: np.ndarray | None = None,
) -> np.ndarray:
    if mode == "token_mean":
        return token_scores.mean(axis=1)
    if mode == "short_scale_mean":
        mask = np.isin(token_scale_id, [3, 4])
        return token_scores[:, mask].mean(axis=1)
    if mode == "weighted_token_mean":
        w = token_weights / max(float(np.mean(token_weights)), 1e-6)
        return (token_scores * w.reshape(1, -1)).mean(axis=1)
    if token_family_id is None:
        raise ValueError(f"token_family_id required for mode '{mode}'")
    if mode == "mi_dir_mean":
        return token_scores[:, token_family_id == 0].mean(axis=1)
    if mode == "hphp_mean":
        return token_scores[:, token_family_id == 3].mean(axis=1)
    if mode == "mi_hphp_mean":
        return token_scores[:, np.isin(token_family_id, [0, 3])].mean(axis=1)
    if mode == "mi_hphp_short_mean":
        mask = np.isin(token_family_id, [0, 3]) & np.isin(token_scale_id, [3, 4])
        return token_scores[:, mask].mean(axis=1)
    raise ValueError(mode)


def id_budget_calibrate(
    score_id_eval: np.ndarray,
    score_ood_eval: np.ndarray,
    score_attack_high: np.ndarray,
    budget: int = 5000,
    target_alarm: float = 0.01,
    seed: int = 42,
    n_candidates: int = 4000,
) -> dict:
    rng = np.random.default_rng(seed)
    n_sub = min(budget, len(score_id_eval))
    idx = rng.choice(len(score_id_eval), n_sub, replace=False)
    id_sub = score_id_eval[idx].astype(np.float64)
    q_levels = np.linspace(0.0, 1.0, n_candidates + 1)[1:]
    candidates = np.unique(np.quantile(id_sub, q_levels))
    for thr in sorted(candidates):
        alarm = float(np.mean(score_ood_eval > thr))
        if alarm <= target_alarm:
            return {
                "threshold": float(thr),
                "calibrated_ood_alarm": alarm,
                "calibrated_det": float(np.mean(score_attack_high > thr)),
                "feasible": True,
            }
    thr_max = float(np.max(id_sub))
    alarm_max = float(np.mean(score_ood_eval > thr_max))
    return {
        "threshold": thr_max,
        "calibrated_ood_alarm": alarm_max,
        "calibrated_det": float(np.mean(score_attack_high > thr_max)),
        "feasible": alarm_max <= target_alarm,
    }


def make_combined_summary(df: pd.DataFrame, calib_policy: str) -> pd.DataFrame:
    key = ["object_label", "detector_family", "token_profile", "score_label"]
    fixed = df[df["policy_name"].eq("fixed_id_q99")].copy()
    calib = df[df["policy_name"].eq(calib_policy)].copy()
    fixed = fixed[key + ["ood_alarm_ratio_eval", "attack_detection_high_purity", "roc_auc_attack_high_vs_ood_eval"]].rename(
        columns={"ood_alarm_ratio_eval": "fixed_alarm", "attack_detection_high_purity": "fixed_det"}
    )
    calib = calib[key + ["ood_alarm_ratio_eval", "attack_detection_high_purity", "selection_feasible"]].rename(
        columns={"ood_alarm_ratio_eval": "calibrated_alarm", "attack_detection_high_purity": "calibrated_det"}
    )
    combined = fixed.merge(calib, on=key, how="left")
    col_order = key + [
        "fixed_alarm",
        "fixed_det",
        "calibrated_alarm",
        "calibrated_det",
        "selection_feasible",
        "roc_auc_attack_high_vs_ood_eval",
    ]
    return combined[[c for c in col_order if c in combined.columns]]


def adjusted_stage2_indices(stage2_idx: dict, window_size: int, attack_len: int) -> dict:
    out = {}
    for key, values in stage2_idx.items():
        arr = np.asarray(values, dtype=np.int64)
        arr = arr[(arr >= window_size) & (arr < attack_len)]
        out[key] = (arr - window_size).astype(np.int64)
    return out


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    ap = argparse.ArgumentParser(description="Frontend-F2.5 causal temporal tokenizer smoke.")
    ap.add_argument("--run-tag", default=f"frontend_f2_5_temporal_smoke_{today}")
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
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = ap.parse_args()

    if args.window_size < 1:
        raise ValueError("--window-size must be >= 1")

    tv3.set_seed(args.seed)
    out = WORKTREE_ROOT / "runs" / args.run_tag
    out.mkdir(parents=True, exist_ok=True)
    (out / "command.txt").write_text("python " + " ".join(sys.argv) + "\n", encoding="utf-8")

    id_raw = load_v3_matrix(args.benign_data_dir / "id_source_expression_v3_matrix.npy")
    ood_raw = load_v3_matrix(args.benign_data_dir / "ood_benign_source_expression_v3_matrix.npy")
    atk_raw = load_v3_matrix(args.attack_data_dir / "attack_source_expression_v3_matrix.npy")

    fit_n = min(int(args.train_samples), len(id_raw))
    id_eval_end = min(len(id_raw), fit_n + int(args.id_eval_samples))
    x_train_stat = id_raw[:fit_n]
    _, mean_stat, std_stat = standardize_tokens(x_train_stat)
    id_z = apply_standardize(id_raw, mean_stat, std_stat)
    ood_z = apply_standardize(ood_raw, mean_stat, std_stat)
    atk_z = apply_standardize(atk_raw, mean_stat, std_stat)

    train_ds = TemporalPredictionDataset(id_z, args.window_size, args.window_size, fit_n)
    id_eval_ds = TemporalPredictionDataset(id_z, args.window_size, fit_n, id_eval_end)
    ood_ds = TemporalPredictionDataset(ood_z, args.window_size, args.window_size, len(ood_z))
    atk_ds = TemporalPredictionDataset(atk_z, args.window_size, args.window_size, len(atk_z))
    if len(train_ds) <= 0 or len(id_eval_ds) <= 0 or len(ood_ds) <= 0 or len(atk_ds) <= 0:
        raise RuntimeError("Temporal dataset is empty; reduce --window-size or check input matrices.")

    stage2 = json.loads(args.stage2_manifest.read_text(encoding="utf-8-sig"))
    stage2_idx = adjusted_stage2_indices(resc.build_stage2_indices(stage2), args.window_size, len(atk_raw))
    if len(stage2_idx["high"]) == 0:
        raise RuntimeError("No high-purity attack samples remain after temporal window offset.")

    score_modes = [
        ("token_mean", "mean RMSE over all 20 expression_v3 temporal-predicted tokens"),
        ("short_scale_mean", "mean RMSE over scale 0.1/0.01 tokens"),
        ("weighted_token_mean", "family/scale weighted RMSE over all 20 tokens"),
        ("mi_dir_mean", "mean RMSE over MI_dir family tokens only"),
        ("hphp_mean", "mean RMSE over HpHp family tokens only"),
        ("mi_hphp_mean", "mean RMSE over MI_dir+HpHp families only"),
        ("mi_hphp_short_mean", "mean RMSE over MI_dir+HpHp at short scales 0.1s+0.01s"),
    ]

    rows: List[Dict] = []
    diagnostics: List[Dict] = []
    for profile in ["uniform", "family_short_focus"]:
        token_weights = build_token_weights(profile)
        detector_family = "frontend_f2_5_temporal_transformer_v1"
        print(f"[fit] {detector_family} profile={profile}", flush=True)
        model = TemporalTransformerPredictor(
            d_model=args.d_model,
            nhead=args.nhead,
            num_layers=args.num_layers,
            window_size=args.window_size,
        )
        hist = train_model(model, train_ds, args.epochs, args.batch_size, args.lr, args.device, token_weights)

        id_token_scores = score_token_rmse(model, id_eval_ds, args.batch_size, args.device)
        ood_token_scores = score_token_rmse(model, ood_ds, args.batch_size, args.device)
        atk_token_scores = score_token_rmse(model, atk_ds, args.batch_size, args.device)

        for mode, mode_desc in score_modes:
            sid = aggregate_scores(id_token_scores, TOKEN_SCALE_ID, token_weights, mode, TOKEN_FAMILY_ID)
            sood = aggregate_scores(ood_token_scores, TOKEN_SCALE_ID, token_weights, mode, TOKEN_FAMILY_ID)
            satt = aggregate_scores(atk_token_scores, TOKEN_SCALE_ID, token_weights, mode, TOKEN_FAMILY_ID)
            obj = f"f2_5_temporal_transformer_{profile}_{mode}"
            extra_meta = {
                "source_mode": "computed_now",
                "token_profile": profile,
                "input_tensor": f"expression_v3 temporal history[{args.window_size}] -> current[20x8]",
                "channel_names": ",".join(V3_CHANNEL_NAMES),
                "score_mode_desc": mode_desc,
                "temporal_window_size": args.window_size,
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

            ood_eval_split = sood[args.calibration_budget :]
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
                "train_temporal_samples": int(len(train_ds)),
                "id_eval_temporal_samples": int(len(id_eval_ds)),
                "ood_temporal_samples": int(len(ood_ds)),
                "attack_temporal_samples": int(len(atk_ds)),
            }
        )

    df = pd.DataFrame(rows)
    diag = pd.DataFrame(diagnostics)
    df.to_csv(out / "frontend_f2_5_temporal_results.csv", index=False)
    df.to_csv(out / "results.csv", index=False)
    diag.to_csv(out / "frontend_f2_5_temporal_diagnostics.csv", index=False)
    combined = make_combined_summary(df, calib_policy=ID_CALIB_POLICY)
    combined.to_csv(out / "frontend_f2_5_temporal_combined.csv", index=False)

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
            "# Frontend-F2.5 Temporal Transformer Smoke",
            "",
            "- Data: Frontend-F2 expression_v3 sources (`7-6` ID, `4-1` OOD, `34-1` attack).",
            f"- Temporal task: causal history window K={args.window_size} predicts current frame.",
            "- Target frame is not included in model input.",
            f"- Calibration: ID-eval budget={args.calibration_budget}, target OOD alarm <= {args.calibration_target:.2f} ({target_pct}%).",
            "",
            "## Combined: fixed_alarm / fixed_det / calibrated_alarm / calibrated_det / AUC",
            f"(calibration policy: `{ID_CALIB_POLICY}`)",
            combined_md,
        ]
    ) + "\n"
    (out / "summary.md").write_text(summary, encoding="utf-8")

    cfg = {
        "stage": "frontend_f2_5_temporal_tokenizer",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_tag": args.run_tag,
        "seed": args.seed,
        "window_size": args.window_size,
        "benign_data_dir": str(args.benign_data_dir),
        "attack_data_dir": str(args.attack_data_dir),
        "stage2_manifest": str(args.stage2_manifest),
        "calibration_budget": args.calibration_budget,
        "calibration_target": args.calibration_target,
        "calibration_policy": ID_CALIB_POLICY,
        "outputs": {
            "results": str(out / "frontend_f2_5_temporal_results.csv"),
            "combined": str(out / "frontend_f2_5_temporal_combined.csv"),
            "diagnostics": str(out / "frontend_f2_5_temporal_diagnostics.csv"),
            "summary": str(out / "summary.md"),
        },
    }
    (out / "frontend_f2_5_temporal_metadata.json").write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out / "config.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[done] frontend-f2.5 temporal output: {out}", flush=True)


if __name__ == "__main__":
    main()
