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


# row-major: family outer, short-scales inner (1s, 0.1s, 0.01s)
_SHORT_SCALE_IDS = np.asarray([2, 3, 4], dtype=np.int64)
_TOKEN_FAMILY_ID = np.repeat(np.arange(4), len(_SHORT_SCALE_IDS)).astype(np.int64)  # [12]
_TOKEN_SCALE_ID  = np.tile(_SHORT_SCALE_IDS, 4).astype(np.int64)                     # [12]

V6_INPUT_ALIGNED_CHANNEL_NAMES = [
    "mean_or_mean_rel",
    "cv_slog_raw",
    "logw_centered_family",
    "mean_rel_family",
    "std_or_std_rel",
    "logw_or_centered",
    "std_rel_family",
    "pcc_centered_family",
]

PROFILE_FAMILY_WEIGHTS = {
    "uniform":           np.asarray([1.0, 1.0, 1.0, 1.0], dtype=np.float32),
    "family_short_focus": np.asarray([0.80, 1.35, 0.80, 1.35], dtype=np.float32),
}
PROFILE_SCALE_WEIGHTS = {
    "uniform":           np.asarray([1.0, 1.0, 1.0, 1.0, 1.0], dtype=np.float32),
    "family_short_focus": np.asarray([0.55, 0.70, 0.95, 1.35, 1.45], dtype=np.float32),
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_v6_matrix(path: Path) -> np.ndarray:
    """Load expression_v6_input_aligned_v1_matrix [N,12,8]."""
    arr = np.load(path)
    if arr.ndim != 3 or arr.shape[1:] != (12, 8):
        raise RuntimeError(f"Expected [N,12,8], got {arr.shape} from {path}")
    return arr.astype(np.float32)


# ---------------------------------------------------------------------------
# Standardization
# ---------------------------------------------------------------------------

def standardize_tokens(x: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-channel (token × channel) standardization. Returns (z, mean, std)."""
    mean = x.mean(axis=0).astype(np.float32)         # [12,8]
    std  = np.maximum(x.std(axis=0), 1e-6).astype(np.float32)
    z    = ((x - mean[None]) / std[None]).astype(np.float32)
    return z, mean, std


def apply_standardize(x: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    return ((x - mean[None]) / std[None]).astype(np.float32)


# ---------------------------------------------------------------------------
# Token weight profile
# ---------------------------------------------------------------------------

def build_token_weights(profile: str) -> np.ndarray:
    fam_w   = PROFILE_FAMILY_WEIGHTS[profile]
    scale_w = PROFILE_SCALE_WEIGHTS[profile]
    out = np.asarray(
        [fam_w[int(f)] * scale_w[int(s)] for f, s in zip(_TOKEN_FAMILY_ID, _TOKEN_SCALE_ID)],
        dtype=np.float32,
    )
    return out / max(float(np.mean(out)), 1e-6)


# ---------------------------------------------------------------------------
# Model components
# ---------------------------------------------------------------------------

class ExpressionV3TokenEmbedding(nn.Module):
    """
    双分支 embedding：
      per-token  (ch0~ch5, 6维) → Linear(6, d_model)
      cross-scale (ch6~ch7, 2维) → Linear(2, d_model)
    两路加和后再叠加 family / scale positional embedding。
    """
    def __init__(self, d_model: int = 64):
        super().__init__()
        self.per_token_proj   = nn.Linear(6, d_model)
        self.cross_scale_proj = nn.Linear(2, d_model)
        self.family_emb = nn.Embedding(4, d_model)
        self.scale_emb  = nn.Embedding(5, d_model)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: [B, 12, 8]
        per   = self.per_token_proj(x[:, :, :6])    # [B, 20, d]
        cross = self.cross_scale_proj(x[:, :, 6:])  # [B, 20, d]

        family_ids = torch.as_tensor(_TOKEN_FAMILY_ID, dtype=torch.long, device=x.device)  # [12]
        scale_ids  = torch.as_tensor(_TOKEN_SCALE_ID, dtype=torch.long, device=x.device)    # [12]
        f_emb = self.family_emb(family_ids)  # [20, d]
        s_emb = self.scale_emb(scale_ids)    # [20, d]

        return per + cross + f_emb + s_emb   # [B, 20, d]


class ExpressionV3TransformerAE(nn.Module):
    def __init__(self, num_tokens: int, token_dim: int,
                 d_model: int = 64, nhead: int = 4, num_layers: int = 2):
        super().__init__()
        self.embedding = ExpressionV3TokenEmbedding(d_model)
        enc = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=max(128, d_model * 4),
            dropout=0.0,
            batch_first=True,
            activation="gelu",
        )
        self.encoder = nn.TransformerEncoder(enc, num_layers=int(num_layers))
        self.norm     = nn.LayerNorm(d_model)
        self.out_proj = nn.Sequential(
            nn.Linear(d_model, d_model), nn.GELU(), nn.Linear(d_model, token_dim)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.embedding(x)
        h = self.encoder(h)
        return self.out_proj(self.norm(h))


class ExpressionV3TokenMLPAE(nn.Module):
    def __init__(self, num_tokens: int, token_dim: int,
                 d_model: int = 64, bottleneck: int = 192):
        super().__init__()
        self.embedding  = ExpressionV3TokenEmbedding(d_model)
        self.num_tokens = int(num_tokens)
        self.d_model    = int(d_model)
        flat_dim        = num_tokens * d_model
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


# ---------------------------------------------------------------------------
# Loss & scoring
# ---------------------------------------------------------------------------

def token_rmse(pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    """Per-token RMSE [B, num_tokens] (all channels equally weighted)."""
    err = (pred - target) ** 2                           # [B, T, C]
    return torch.sqrt(torch.clamp(err.mean(dim=2), min=1e-12))  # [B, T]


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
    opt     = torch.optim.Adam(model.parameters(), lr=lr)
    weight_t = torch.as_tensor(token_weights, dtype=torch.float32, device=device).view(1, -1)
    ds      = TensorDataset(torch.from_numpy(x_train.astype(np.float32)))
    loader  = DataLoader(ds, batch_size=batch_size, shuffle=True, drop_last=False)
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
            xb   = torch.from_numpy(x[st : st + batch_size].astype(np.float32)).to(device)
            pred = model(xb)
            out.append(token_rmse(pred, xb).detach().cpu().numpy())
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
    # ── family-selective modes (families: 0=MI_dir, 1=HH, 2=HH_jit, 3=HpHp) ──
    if token_family_id is None:
        raise ValueError(f"token_family_id required for mode '{mode}'")
    if mode == "mi_dir_mean":
        mask = token_family_id == 0
        return token_scores[:, mask].mean(axis=1)
    if mode == "hphp_mean":
        mask = token_family_id == 3
        return token_scores[:, mask].mean(axis=1)
    if mode == "mi_hphp_mean":
        mask = np.isin(token_family_id, [0, 3])
        return token_scores[:, mask].mean(axis=1)
    if mode == "mi_hphp_short_mean":
        # MI_dir + HpHp, scales 0.1s and 0.01s (scale_id 3,4)
        mask = np.isin(token_family_id, [0, 3]) & np.isin(token_scale_id, [3, 4])
        return token_scores[:, mask].mean(axis=1)
    raise ValueError(mode)


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------

ID_CALIB_POLICY = "id_budget_calibrated_target1pct"


def id_budget_calibrate(
    score_id_eval: np.ndarray,
    score_ood_eval: np.ndarray,
    score_attack_high: np.ndarray,
    budget: int = 5000,
    target_alarm: float = 0.01,
    seed: int = 42,
    n_candidates: int = 4000,
) -> dict:
    """
    ID-budget calibration protocol（与主线 crosscapture_calibration 协议对称）：

    1. 从 ID eval 分数中随机取 budget 个样本作为 threshold 候选来源。
    2. 生成这些 ID 分数在 [0, 1] 上 n_candidates 个分位点作为候选阈值集合。
    3. 升序扫描候选阈值，找到**最小** T 使得 P(OOD_eval score > T) <= target_alarm。
       （最小化阈值 = 在满足 OOD alarm 约束的前提下，最大化 attack 检测力）
    4. 报告该阈值下的 calibrated_ood_alarm 和 calibrated_det。

    返回 dict 字段：
        threshold           最优阈值（若不可行则 nan）
        calibrated_ood_alarm OOD eval alarm rate at threshold
        calibrated_det      high-purity attack detection at threshold
        feasible            是否存在满足约束的阈值
    """
    rng = np.random.default_rng(seed)
    n_sub = min(budget, len(score_id_eval))
    idx = rng.choice(len(score_id_eval), n_sub, replace=False)
    id_sub = score_id_eval[idx].astype(np.float64)

    # 生成候选阈值（ID 分布的分位点）
    q_levels = np.linspace(0.0, 1.0, n_candidates + 1)[1:]  # 排除 0 分位（min 值不稳定）
    candidates = np.unique(np.quantile(id_sub, q_levels))

    # 升序扫描，找最小 T 满足 OOD alarm <= target
    for thr in sorted(candidates):
        alarm = float(np.mean(score_ood_eval > thr))
        if alarm <= target_alarm:
            return {
                "threshold":            float(thr),
                "calibrated_ood_alarm": alarm,
                "calibrated_det":       float(np.mean(score_attack_high > thr)),
                "feasible":             True,
            }

    # 不可行：即使最高 ID 分数也无法控制 OOD alarm
    thr_max = float(np.max(id_sub))
    alarm_max = float(np.mean(score_ood_eval > thr_max))
    return {
        "threshold":            thr_max,
        "calibrated_ood_alarm": alarm_max,
        "calibrated_det":       float(np.mean(score_attack_high > thr_max)),
        "feasible":             alarm_max <= target_alarm,
    }


def make_combined_summary(df: pd.DataFrame, calib_policy: str) -> pd.DataFrame:
    """
    将 fixed_id_q99 和 calib_policy 两套结果合并为一张宽表。
    输出列：object_label / detector_family / token_profile / score_label /
            fixed_alarm / fixed_det / calibrated_alarm / calibrated_det / AUC
    """
    KEY = ["object_label", "detector_family", "token_profile", "score_label"]

    fixed = df[df["policy_name"].eq("fixed_id_q99")].copy()
    calib = df[df["policy_name"].eq(calib_policy)].copy()

    fixed = fixed[KEY + ["ood_alarm_ratio_eval", "attack_detection_high_purity",
                          "roc_auc_attack_high_vs_ood_eval"]].rename(columns={
        "ood_alarm_ratio_eval":        "fixed_alarm",
        "attack_detection_high_purity": "fixed_det",
    })
    calib = calib[KEY + ["ood_alarm_ratio_eval", "attack_detection_high_purity",
                          "selection_feasible"]].rename(columns={
        "ood_alarm_ratio_eval":        "calibrated_alarm",
        "attack_detection_high_purity": "calibrated_det",
    })
    combined = fixed.merge(calib, on=KEY, how="left")
    # 排列列顺序
    col_order = KEY + [
        "fixed_alarm", "fixed_det",
        "calibrated_alarm", "calibrated_det",
        "selection_feasible",
        "roc_auc_attack_high_vs_ood_eval",
    ]
    return combined[[c for c in col_order if c in combined.columns]]


# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------

def plot_tradeoff(df: pd.DataFrame, out: Path) -> None:
    fixed = df[(df["policy_name"].eq("fixed_id_q99")) & (df["selection_feasible"].astype(bool))].copy()
    plt.figure(figsize=(11, 7))
    for _, r in fixed.iterrows():
        fam = str(r["detector_family"])
        if "transformer" in fam:
            color = "#1f77b4"
        elif "token_mlp" in fam:
            color = "#ff7f0e"
        else:
            color = "#7f7f7f"
        x = float(r["ood_alarm_ratio_eval"])
        y = float(r["attack_detection_high_purity"])
        plt.scatter(x, y, c=color, s=88)
        plt.text(x + 0.004, y + 0.006, str(r["object_label"]), fontsize=7)
    plt.xlabel("OOD benign alarm ratio (fixed q99)")
    plt.ylabel("High-purity attack detection")
    plt.title("Frontend-F2 expression_v6_input_aligned fixed trade-off")
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(out, dpi=180)
    plt.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    ap = argparse.ArgumentParser(description="Frontend-F2 expression_v6_input_aligned tokenizer v1.")
    ap.add_argument("--run-tag", default=f"frontend_f2_expression_v6_input_aligned_tokenizer_v1_{today}")
    ap.add_argument(
        "--benign-data-dir", type=Path,
        default=WORKTREE_ROOT / "runs" / "frontend_f2_expression_v6_input_aligned_crosscapture_stage1_2026-04-20" / "data",
        help="Directory containing id_source_expression_v6_input_aligned_v1_matrix.npy and ood_benign_source_expression_v6_input_aligned_v1_matrix.npy",
    )
    ap.add_argument(
        "--attack-data-dir", type=Path,
        default=WORKTREE_ROOT / "runs" / "frontend_f2_expression_v6_input_aligned_attack_source_2026-04-20" / "data",
        help="Directory containing attack_source_expression_v6_input_aligned_v1_matrix.npy",
    )
    ap.add_argument(
        "--stage2-manifest", type=Path,
        default=WORKTREE_ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master" / "runs" / "frontend100_joint_eval_stage2_2026-04-01" / "attack_manifest_stage2.json",
    )
    ap.add_argument("--seed",              type=int,   default=42)
    ap.add_argument("--epochs",            type=int,   default=20)
    ap.add_argument("--batch-size",        type=int,   default=256)
    ap.add_argument("--lr",                type=float, default=1e-3)
    ap.add_argument("--train-samples",     type=int,   default=8000)
    ap.add_argument("--id-eval-samples",   type=int,   default=5000)
    ap.add_argument("--calibration-budget", type=int,   default=5000)
    ap.add_argument("--calibration-target", type=float, default=0.01,
                    help="Target OOD alarm rate for ID-budget calibration (default 0.01 = 1%%)")
    ap.add_argument("--scan-points",        type=int,   default=1200)
    ap.add_argument("--d-model",           type=int,   default=64)
    ap.add_argument("--nhead",             type=int,   default=4)
    ap.add_argument("--num-layers",        type=int,   default=2)
    ap.add_argument("--token-mlp-bottleneck", type=int, default=192)
    ap.add_argument("--smoke-fit-n",       type=int,   default=0)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = ap.parse_args()

    tv3.set_seed(args.seed)
    out = WORKTREE_ROOT / "runs" / args.run_tag
    out.mkdir(parents=True, exist_ok=True)
    plot_dir = out / "frontend_f2_expression_v6_input_aligned_plots"
    plot_dir.mkdir(exist_ok=True)
    (out / "command.txt").write_text("python " + " ".join(sys.argv) + "\n", encoding="utf-8")

    # --- load data ---
    id_matrix  = load_v6_matrix(args.benign_data_dir / "id_source_expression_v6_input_aligned_v1_matrix.npy")
    ood_matrix = load_v6_matrix(args.benign_data_dir / "ood_benign_source_expression_v6_input_aligned_v1_matrix.npy")
    atk_matrix = load_v6_matrix(args.attack_data_dir  / "attack_source_expression_v6_input_aligned_v1_matrix.npy")
    stage2     = json.loads(args.stage2_manifest.read_text(encoding="utf-8-sig"))
    stage2_idx = resc.build_stage2_indices(stage2)

    token_family_id = _TOKEN_FAMILY_ID
    token_scale_id  = _TOKEN_SCALE_ID

    fit_n      = int(args.train_samples if args.smoke_fit_n <= 0 else min(args.train_samples, args.smoke_fit_n))
    id_eval_n  = int(args.id_eval_samples)

    x_train_raw = id_matrix[:fit_n]
    x_id_raw    = id_matrix[fit_n : fit_n + id_eval_n]
    x_ood_raw   = ood_matrix
    x_atk_raw   = atk_matrix

    x_train, mean_stat, std_stat = standardize_tokens(x_train_raw)
    x_id     = apply_standardize(x_id_raw,  mean_stat, std_stat)
    x_ood    = apply_standardize(x_ood_raw,  mean_stat, std_stat)
    x_attack = apply_standardize(x_atk_raw,  mean_stat, std_stat)

    N_TOKENS  = int(id_matrix.shape[1])
    TOKEN_DIM = int(id_matrix.shape[2])

    model_builders = [
        (
            "frontend_f2_expression_v6_input_aligned_transformer_v1",
            lambda: ExpressionV3TransformerAE(
                N_TOKENS, TOKEN_DIM,
                d_model=args.d_model, nhead=args.nhead, num_layers=args.num_layers,
            ),
        ),
        (
            "frontend_f2_expression_v6_input_aligned_token_mlp_control",
            lambda: ExpressionV3TokenMLPAE(
                N_TOKENS, TOKEN_DIM,
                d_model=args.d_model, bottleneck=args.token_mlp_bottleneck,
            ),
        ),
    ]
    score_modes = [
        ("token_mean",          "mean RMSE over all 12 expression_v6_input_aligned tokens"),
        ("short_scale_mean",    "mean RMSE over scale 0.1/0.01 tokens"),
        ("weighted_token_mean", "family/scale weighted RMSE over all 12 expression_v6_input_aligned tokens"),
        ("mi_dir_mean",         "mean RMSE over MI_dir family tokens only (family 0)"),
        ("hphp_mean",           "mean RMSE over HpHp family tokens only (family 3)"),
        ("mi_hphp_mean",        "mean RMSE over MI_dir+HpHp families only (families 0,3)"),
        ("mi_hphp_short_mean",  "mean RMSE over MI_dir+HpHp at short scales 0.1s+0.01s"),
    ]

    rows: List[Dict]       = []
    diagnostics: List[Dict] = []
    calib_budget = args.calibration_budget
    calib_target = args.calibration_target

    for profile in ["uniform", "family_short_focus"]:
        token_weights = build_token_weights(profile)
        for detector_family, builder in model_builders:
            print(f"[fit] {detector_family} profile={profile}", flush=True)
            model = builder()
            hist  = train_model(model, x_train, args.epochs, args.batch_size, args.lr,
                                 args.device, token_weights)
            id_token_scores  = score_token_rmse(model, x_id,     args.batch_size, args.device)
            ood_token_scores = score_token_rmse(model, x_ood,    args.batch_size, args.device)
            atk_token_scores = score_token_rmse(model, x_attack, args.batch_size, args.device)

            for mode, mode_desc in score_modes:
                sid  = aggregate_scores(id_token_scores,  token_scale_id, token_weights, mode, token_family_id)
                sood = aggregate_scores(ood_token_scores, token_scale_id, token_weights, mode, token_family_id)
                satt = aggregate_scores(atk_token_scores, token_scale_id, token_weights, mode, token_family_id)
                obj  = (
                    f"{detector_family.replace('frontend_f2_', '').replace('_control', '')}"
                    f"_{profile}_{mode}"
                )
                extra_meta = {
                    "source_mode":     "computed_now",
                    "token_profile":   profile,
                    "input_tensor":    "expression_v6_input_aligned_v1_matrix[12x8]",
                    "channel_names":   ",".join(V6_INPUT_ALIGNED_CHANNEL_NAMES),
                    "score_mode_desc": mode_desc,
                }

                # ── 标准评估（fixed_id_q99 + naive_calibrated OOD-budget + scan） ──
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
                        budget=calib_budget,
                        scan_points=args.scan_points,
                        extra=extra_meta,
                    )
                )

                # ── ID-budget calibration（与主线 crosscapture_calibration 对称协议） ──
                # OOD eval split: 去掉前 budget 行，与 naive_calibrated 的 eval 一致
                ood_eval_split = sood[calib_budget:]
                atk_high       = satt[stage2_idx["high"]]
                auc_val        = resc.compute_auc(
                    ood_eval_scores=ood_eval_split,
                    attack_high_scores=atk_high,
                )
                calib_result = id_budget_calibrate(
                    score_id_eval=sid,
                    score_ood_eval=ood_eval_split,
                    score_attack_high=atk_high,
                    budget=calib_budget,
                    target_alarm=calib_target,
                    seed=args.seed,
                )
                # 同时报告 id_alarm_ratio（固定阈值下 ID 自身的 alarm）
                thr = calib_result["threshold"]
                rows.append({
                    "object_label":                  obj,
                    "detector_family":               detector_family,
                    "score_label":                   mode,
                    "seed":                          args.seed,
                    "policy_name":                   ID_CALIB_POLICY,
                    "selection_feasible":            calib_result["feasible"],
                    "threshold_source":              (
                        f"min ID-eval q (budget={calib_budget}) "
                        f"s.t. ood_alarm<=target={calib_target:.3f}"
                    ),
                    "threshold":                     thr if np.isfinite(thr) else float("nan"),
                    "id_alarm_ratio":                float(np.mean(sid > thr)) if np.isfinite(thr) else float("nan"),
                    "ood_alarm_ratio_full":          float(np.mean(sood > thr)) if np.isfinite(thr) else float("nan"),
                    "ood_alarm_ratio_eval":          calib_result["calibrated_ood_alarm"],
                    "attack_detection_all":          float(np.mean(satt > thr)) if np.isfinite(thr) else float("nan"),
                    "attack_detection_high_purity":  calib_result["calibrated_det"],
                    "attack_detection_boundary":     float("nan"),
                    "roc_auc_attack_high_vs_ood_eval": float(auc_val),
                    **extra_meta,
                })

            diagnostics.append(
                {
                    "detector_family": detector_family,
                    "token_profile":   profile,
                    "train_loss_start": float(hist[0]),
                    "train_loss_end":   float(hist[-1]),
                    "train_loss_min":   float(np.min(hist)),
                    "num_tokens":       N_TOKENS,
                    "token_dim":        TOKEN_DIM,
                }
            )

    df   = pd.DataFrame(rows)
    diag = pd.DataFrame(diagnostics)
    df.to_csv(out / "frontend_f2_expression_v6_input_aligned_results.csv",      index=False)
    df.to_csv(out / "results.csv",                                 index=False)
    diag.to_csv(out / "frontend_f2_expression_v6_input_aligned_diagnostics.csv", index=False)
    plot_tradeoff(df, plot_dir / "fixed_tradeoff_frontend_f2_expression_v6_input_aligned.png")

    # ── 合并表：fixed + id_budget_calibrated ──────────────────────────────
    combined = make_combined_summary(df, calib_policy=ID_CALIB_POLICY)
    combined.to_csv(out / "frontend_f2_expression_v6_input_aligned_combined.csv", index=False)

    # ── Fixed-only 表（向后兼容） ──────────────────────────────────────────
    fixed = df[(df["policy_name"].eq("fixed_id_q99")) & (df["selection_feasible"].astype(bool))].copy()
    fixed_cols = [
        "object_label", "detector_family", "token_profile", "score_label",
        "ood_alarm_ratio_eval", "attack_detection_high_purity", "roc_auc_attack_high_vs_ood_eval",
    ]
    fixed_md = tv3.md_table(fixed[fixed_cols].sort_values(["detector_family", "object_label"]))

    # ── 合并表（summary.md 主体） ──────────────────────────────────────────
    sort_keys = ["detector_family", "object_label"]
    combined_sorted = combined.sort_values(sort_keys) if all(k in combined.columns for k in sort_keys) else combined
    combined_display_cols = [
        "object_label", "detector_family", "token_profile", "score_label",
        "fixed_alarm", "fixed_det",
        "calibrated_alarm", "calibrated_det",
        "selection_feasible",
        "roc_auc_attack_high_vs_ood_eval",
    ]
    combined_display = combined_sorted[[c for c in combined_display_cols if c in combined_sorted.columns]]
    combined_md = tv3.md_table(combined_display)

    target_pct = int(round(calib_target * 100))
    summary = "\n".join(
        [
            "# Frontend-F2 Expression v6 Input-Aligned Tokenizer v1",
            "",
            "- Data: Frontend-F2 expression_v6_input_aligned_v1 sources (`7-6` ID, `4-1` OOD, `34-1` attack).",
            "- Input tensor: `expression_v6_input_aligned_v1_matrix [12,8]` with dual-branch embedding "
            "(per-token 6ch + cross-scale 2ch) + family/scale positional.",
            f"- expression_v6_input_aligned channels: `{', '.join(V6_INPUT_ALIGNED_CHANNEL_NAMES)}`.",
            f"- Calibration: ID-eval budget={calib_budget}, target OOD alarm <= {calib_target:.2f} "
            f"({target_pct}%).",
            "",
            f"## Combined: fixed_alarm / fixed_det / calibrated_alarm / calibrated_det / AUC",
            f"(calibration policy: `{ID_CALIB_POLICY}`)",
            combined_md,
            "",
            "## Fixed q99 only (for reference)",
            fixed_md,
        ]
    ) + "\n"
    (out / "summary.md").write_text(summary, encoding="utf-8")

    cfg = {
        "stage":        "frontend_f2_expression_v6_input_aligned_tokenizer_v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_tag":      args.run_tag,
        "seed":         args.seed,
        "benign_data_dir":      str(args.benign_data_dir),
        "attack_data_dir":      str(args.attack_data_dir),
        "calibration_budget":   calib_budget,
        "calibration_target":   calib_target,
        "calibration_policy":   ID_CALIB_POLICY,
        "outputs": {
            "results":     str(out / "frontend_f2_expression_v6_input_aligned_results.csv"),
            "combined":    str(out / "frontend_f2_expression_v6_input_aligned_combined.csv"),
            "diagnostics": str(out / "frontend_f2_expression_v6_input_aligned_diagnostics.csv"),
            "summary":     str(out / "summary.md"),
            "plots":       str(plot_dir),
        },
    }
    (out / "expression_v6_input_aligned_metadata.json").write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out / "config.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[done] frontend-f2 expression_v6_input_aligned tokenizer output: {out}", flush=True)


if __name__ == "__main__":
    main()
