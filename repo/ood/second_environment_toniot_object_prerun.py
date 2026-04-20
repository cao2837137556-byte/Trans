from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, TensorDataset

THIS_DIR = Path(__file__).resolve().parent
REPO_DIR = THIS_DIR.parent
for p in [THIS_DIR, REPO_DIR]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from paths import ARTIFACT_RUNS_DIR

import KitNET as kit
from frontend100_modern_tabular_baselines import FTTransformerAE


def clean(obj):
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean(v) for v in obj]
    if isinstance(obj, tuple):
        return [clean(v) for v in obj]
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, np.ndarray):
        return [clean(v) for v in obj.tolist()]
    if isinstance(obj, np.generic):
        return clean(obj.item())
    return obj


def eval_threshold(threshold: float, id_scores: np.ndarray, ood_scores: np.ndarray, attack_scores: np.ndarray) -> Dict[str, float]:
    return {
        "threshold": float(threshold),
        "id_alarm_ratio": float(np.mean(id_scores > threshold)),
        "ood_alarm_ratio": float(np.mean(ood_scores > threshold)),
        "attack_detection": float(np.mean(attack_scores > threshold)),
    }


def choose_detection_floor(df: pd.DataFrame, det_floor: float) -> pd.Series | None:
    cand = df[df["attack_detection"] >= det_floor].copy()
    if cand.empty:
        return None
    cand = cand.sort_values(["ood_alarm_ratio", "threshold"], ascending=[True, False])
    return cand.iloc[0]


def orientation_auc(ood_scores: np.ndarray, attack_scores: np.ndarray, score_sign: int) -> float:
    y = np.concatenate([np.zeros(len(ood_scores), dtype=np.int64), np.ones(len(attack_scores), dtype=np.int64)])
    s = score_sign * np.concatenate([ood_scores, attack_scores]).astype(np.float64)
    return float(roc_auc_score(y, s))


def choose_orientation(ood_scores: np.ndarray, attack_scores: np.ndarray) -> Tuple[int, float, float]:
    auc_plus = orientation_auc(ood_scores, attack_scores, 1)
    auc_minus = orientation_auc(ood_scores, attack_scores, -1)
    if auc_plus >= auc_minus:
        return 1, auc_plus, auc_minus
    return -1, auc_minus, auc_plus


def summarize_scores(name: str, id_scores: np.ndarray, ood_scores: np.ndarray, attack_scores: np.ndarray) -> Dict[str, float]:
    return {
        "object_label": name,
        "id_q50": float(np.quantile(id_scores, 0.5)),
        "id_q99": float(np.quantile(id_scores, 0.99)),
        "ood_q50": float(np.quantile(ood_scores, 0.5)),
        "ood_q99": float(np.quantile(ood_scores, 0.99)),
        "attack_q50": float(np.quantile(attack_scores, 0.5)),
        "attack_q99": float(np.quantile(attack_scores, 0.99)),
    }


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


def train_ft_autoencoder(
    x_train: np.ndarray,
    seed: int,
    epochs: int,
    batch_size: int,
    lr: float,
    weight_decay: float,
    patience: int,
    val_ratio: float,
    d_token: int,
    n_heads: int,
    n_blocks: int,
    latent_dim: int,
    decoder_hidden: int,
    attn_dropout: float,
    ffn_dropout: float,
    device: str,
) -> Tuple[FTTransformerAE, List[Dict[str, float]], int, float, float]:
    rng = np.random.default_rng(seed)
    idx = np.arange(len(x_train))
    rng.shuffle(idx)
    n_val = max(1, int(round(len(x_train) * val_ratio)))
    x_val = x_train[idx[:n_val]]
    x_fit = x_train[idx[n_val:]] if len(idx[n_val:]) else x_train[idx[:n_val]]

    model = FTTransformerAE(
        input_dim=x_train.shape[1],
        d_token=d_token,
        n_heads=n_heads,
        n_blocks=n_blocks,
        latent_dim=latent_dim,
        decoder_hidden=decoder_hidden,
        attn_dropout=attn_dropout,
        ffn_dropout=ffn_dropout,
    ).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    crit = nn.MSELoss()
    fit_loader = make_loader(x_fit, batch_size, True)
    val_loader = make_loader(x_val, batch_size, False)

    best_state = copy.deepcopy(model.state_dict())
    best_val = float("inf")
    best_epoch = 0
    bad = 0
    hist: List[Dict[str, float]] = []

    t0 = time.perf_counter()
    for epoch in range(1, epochs + 1):
        model.train()
        total = 0.0
        count = 0
        for (xb,) in fit_loader:
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
        hist.append({"epoch": float(epoch), "train_loss": float(train_loss), "val_loss": float(val_loss)})
        if val_loss < best_val - 1e-8:
            best_val = val_loss
            best_epoch = epoch
            best_state = copy.deepcopy(model.state_dict())
            bad = 0
        else:
            bad += 1
        if bad >= patience:
            break
    train_sec = float(time.perf_counter() - t0)
    model.load_state_dict(best_state)
    return model, hist, int(best_epoch), float(best_val), train_sec


def score_ft(model: nn.Module, x: np.ndarray, batch_size: int, device: str) -> np.ndarray:
    model.eval()
    out: List[np.ndarray] = []
    with torch.no_grad():
        for (xb,) in make_loader(x, batch_size, False):
            xb = xb.to(device)
            err = (model(xb) - xb) ** 2
            out.append(torch.sqrt(torch.mean(err, dim=1)).detach().cpu().numpy())
    return np.concatenate(out).astype(np.float64)


def train_kitnet_model(
    backend: str,
    x_train: np.ndarray,
    seed: int,
    fm_grace: int,
    ad_grace: int,
    learning_rate: float,
    hidden_ratio: float,
    max_ae: int,
) -> Tuple[kit.KitNET, float]:
    model = kit.KitNET(
        n=x_train.shape[1],
        max_autoencoder_size=max_ae,
        FM_grace_period=fm_grace,
        AD_grace_period=ad_grace,
        learning_rate=learning_rate,
        hidden_ratio=hidden_ratio,
        detector_backend=backend,
        detector_seed=seed,
    )
    t0 = time.perf_counter()
    for i in range(len(x_train)):
        if i > 0 and i % 2000 == 0:
            print(f"[{backend}] train progress: {i}/{len(x_train)}", flush=True)
        model.process(x_train[i])
    train_sec = float(time.perf_counter() - t0)
    return model, train_sec


def score_kitnet(model: kit.KitNET, x: np.ndarray, name: str) -> Tuple[np.ndarray, float]:
    t0 = time.perf_counter()
    scores = np.zeros(len(x), dtype=np.float64)
    for i in range(len(x)):
        if i > 0 and i % 2000 == 0:
            print(f"[{name}] score progress: {i}/{len(x)}", flush=True)
        scores[i] = float(model.executeAD(x[i]))
    infer_sec = float(time.perf_counter() - t0)
    return scores, infer_sec


def evaluate_object(
    object_label: str,
    raw_id: np.ndarray,
    raw_ood: np.ndarray,
    raw_attack: np.ndarray,
    naive_budget: int,
) -> Tuple[List[Dict[str, object]], Dict[str, object], Dict[str, float]]:
    sign, auc_chosen, auc_other = choose_orientation(raw_ood, raw_attack)
    orientation_name = "raw_score" if sign == 1 else "neg_raw_score"
    id_scores = sign * raw_id
    ood_scores = sign * raw_ood
    attack_scores = sign * raw_attack

    rows: List[Dict[str, object]] = []
    fixed = eval_threshold(float(np.quantile(id_scores, 0.99)), id_scores, ood_scores, attack_scores)
    rows.append(
        {
            "object_label": object_label,
            "policy_name": "fixed_id_q99",
            "score_orientation": orientation_name,
            "roc_auc_attack_vs_ood": float(auc_chosen),
            **fixed,
        }
    )

    budget = min(naive_budget, len(ood_scores))
    naive_thr = float(np.quantile(ood_scores[:budget], 0.99))
    naive = eval_threshold(naive_thr, id_scores, ood_scores, attack_scores)
    rows.append(
        {
            "object_label": object_label,
            "policy_name": f"naive_calibrated_budget{budget}_target1pct",
            "score_orientation": orientation_name,
            "roc_auc_attack_vs_ood": float(auc_chosen),
            **naive,
        }
    )

    grid = np.unique(np.quantile(np.concatenate([id_scores, ood_scores, attack_scores]), np.linspace(0.0, 1.0, 512)))
    scan_rows: List[Dict[str, float]] = []
    for thr in grid:
        row = eval_threshold(float(thr), id_scores, ood_scores, attack_scores)
        row["threshold"] = float(thr)
        scan_rows.append(row)
    det50 = choose_detection_floor(pd.DataFrame(scan_rows), det_floor=0.50)
    if det50 is not None:
        rows.append(
            {
                "object_label": object_label,
                "policy_name": "det_floor_50pct_min_alarm",
                "score_orientation": orientation_name,
                "roc_auc_attack_vs_ood": float(auc_chosen),
                **det50.to_dict(),
            }
        )

    polarity_row = {
        "object_label": object_label,
        "chosen_score": orientation_name,
        "chosen_sign": int(sign),
        "auc_chosen": float(auc_chosen),
        "auc_other_orientation": float(auc_other),
        "improvement_over_other": float(auc_chosen - auc_other),
    }
    stats_row = summarize_scores(object_label, id_scores, ood_scores, attack_scores)
    return rows, polarity_row, stats_row


def build_split(
    manifest_path: Path,
    csv_path: Path | None,
    label_col: str,
    normal_label: str,
    id_train_n: int | None,
    id_eval_n: int | None,
    ood_eval_n: int | None,
    attack_eval_n: int | None,
) -> Tuple[Dict[str, object], pd.DataFrame, List[str], np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    src_csv = csv_path if csv_path is not None else Path(manifest["csv_path"])
    df = pd.read_csv(src_csv, low_memory=False)
    if label_col not in df.columns:
        raise RuntimeError(f"Missing label column: {label_col}")

    id_indices_full = np.asarray(manifest["id_indices"], dtype=np.int64)
    ood_indices_full = np.asarray(manifest["ood_indices"], dtype=np.int64)
    attack_indices_full = np.asarray(manifest["attack_indices"], dtype=np.int64)

    id_train_n_eff = int(id_train_n) if id_train_n is not None else int(round(len(id_indices_full) * 2 / 3))
    id_eval_n_eff = int(id_eval_n) if id_eval_n is not None else (len(id_indices_full) - id_train_n_eff)
    if id_train_n_eff <= 0 or id_eval_n_eff <= 0:
        raise RuntimeError("id_train_n and id_eval_n must both be positive.")
    if id_train_n_eff + id_eval_n_eff > len(id_indices_full):
        raise RuntimeError(
            f"id_train_n + id_eval_n exceeds manifest id size: {id_train_n_eff} + {id_eval_n_eff} > {len(id_indices_full)}"
        )

    ood_eval_n_eff = int(ood_eval_n) if ood_eval_n is not None else len(ood_indices_full)
    attack_eval_n_eff = int(attack_eval_n) if attack_eval_n is not None else len(attack_indices_full)
    if ood_eval_n_eff <= 0 or attack_eval_n_eff <= 0:
        raise RuntimeError("ood_eval_n and attack_eval_n must both be positive.")

    id_train_idx = id_indices_full[:id_train_n_eff]
    id_eval_idx = id_indices_full[id_train_n_eff : id_train_n_eff + id_eval_n_eff]
    ood_eval_idx = ood_indices_full[:ood_eval_n_eff]
    attack_eval_idx = attack_indices_full[:attack_eval_n_eff]

    numeric_cols = [c for c in df.columns if c != label_col and pd.api.types.is_numeric_dtype(df[c])]
    if not numeric_cols:
        raise RuntimeError("No numeric columns available in TON CSV.")

    x_all = df[numeric_cols].to_numpy(dtype=np.float64)
    x_id_train = x_all[id_train_idx]
    x_id_eval = x_all[id_eval_idx]
    x_ood_eval = x_all[ood_eval_idx]
    x_attack_eval = x_all[attack_eval_idx]

    labels = df[label_col].astype(str).to_numpy()
    if not np.all(labels[id_train_idx] == normal_label):
        raise RuntimeError("id_train split contains non-normal rows.")
    if not np.all(labels[id_eval_idx] == normal_label):
        raise RuntimeError("id_eval split contains non-normal rows.")
    if np.any(labels[attack_eval_idx] == normal_label):
        raise RuntimeError("attack_eval split contains normal rows.")

    split_meta = {
        "manifest_path": str(manifest_path),
        "csv_path": str(src_csv),
        "label_col": label_col,
        "normal_label": normal_label,
        "id_manifest_total": int(len(id_indices_full)),
        "ood_manifest_total": int(len(ood_indices_full)),
        "attack_manifest_total": int(len(attack_indices_full)),
        "id_train_n": int(len(id_train_idx)),
        "id_eval_n": int(len(id_eval_idx)),
        "ood_eval_n": int(len(ood_eval_idx)),
        "attack_eval_n": int(len(attack_eval_idx)),
        "numeric_feature_n": int(len(numeric_cols)),
    }
    return split_meta, df, numeric_cols, x_id_train, x_id_eval, x_ood_eval, x_attack_eval


def main() -> None:
    parser = argparse.ArgumentParser(description="TON-IoT mainline object pre-run under fixed split manifest and policy family.")
    parser.add_argument("--run-tag", required=True)
    parser.add_argument(
        "--split-manifest",
        type=Path,
        default=ARTIFACT_RUNS_DIR / "second_environment_toniot_precheck_2026-04-20" / "split_manifest.json",
    )
    parser.add_argument("--csv-path", type=Path, default=None)
    parser.add_argument("--label-col", default="label")
    parser.add_argument("--normal-label", default="0")
    parser.add_argument("--id-train-n", type=int, default=20000)
    parser.add_argument("--id-eval-n", type=int, default=10000)
    parser.add_argument("--ood-eval-n", type=int, default=20000)
    parser.add_argument("--attack-eval-n", type=int, default=30000)
    parser.add_argument("--naive-budget", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--max-ae", type=int, default=10)
    parser.add_argument("--learning-rate", type=float, default=0.1)
    parser.add_argument("--hidden-ratio", type=float, default=0.75)
    parser.add_argument("--da-fm-grace", type=int, default=6000)
    parser.add_argument("--strongest-fm-grace", type=int, default=6000)
    parser.add_argument("--ft-epochs", type=int, default=30)
    parser.add_argument("--ft-batch-size", type=int, default=512)
    parser.add_argument("--ft-lr", type=float, default=1e-3)
    parser.add_argument("--ft-weight-decay", type=float, default=1e-6)
    parser.add_argument("--ft-patience", type=int, default=6)
    parser.add_argument("--ft-val-ratio", type=float, default=0.2)
    parser.add_argument("--ft-d-token", type=int, default=64)
    parser.add_argument("--ft-n-heads", type=int, default=8)
    parser.add_argument("--ft-n-blocks", type=int, default=3)
    parser.add_argument("--ft-latent-dim", type=int, default=64)
    parser.add_argument("--ft-decoder-hidden", type=int, default=256)
    parser.add_argument("--ft-attn-dropout", type=float, default=0.2)
    parser.add_argument("--ft-ffn-dropout", type=float, default=0.1)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    run_dir = ARTIFACT_RUNS_DIR / args.run_tag
    run_dir.mkdir(parents=True, exist_ok=True)

    split_meta, _, numeric_cols, x_id_train, x_id_eval, x_ood_eval, x_attack_eval = build_split(
        manifest_path=args.split_manifest,
        csv_path=args.csv_path,
        label_col=args.label_col,
        normal_label=str(args.normal_label),
        id_train_n=args.id_train_n,
        id_eval_n=args.id_eval_n,
        ood_eval_n=args.ood_eval_n,
        attack_eval_n=args.attack_eval_n,
    )

    scaler = StandardScaler().fit(x_id_train)
    x_id_train_z = scaler.transform(x_id_train).astype(np.float64)
    x_id_eval_z = scaler.transform(x_id_eval).astype(np.float64)
    x_ood_eval_z = scaler.transform(x_ood_eval).astype(np.float64)
    x_attack_eval_z = scaler.transform(x_attack_eval).astype(np.float64)

    result_rows: List[Dict[str, object]] = []
    polarity_rows: List[Dict[str, object]] = []
    score_stats_rows: List[Dict[str, float]] = []
    diag_rows: List[Dict[str, object]] = []

    # Object 1: dA
    da_fm = min(max(1, args.da_fm_grace), len(x_id_train_z) - 1)
    da_ad = len(x_id_train_z) - da_fm
    da_model, da_train_sec = train_kitnet_model(
        backend="da",
        x_train=x_id_train_z,
        seed=args.seed,
        fm_grace=da_fm,
        ad_grace=da_ad,
        learning_rate=args.learning_rate,
        hidden_ratio=args.hidden_ratio,
        max_ae=args.max_ae,
    )
    da_id_scores, da_id_infer_sec = score_kitnet(da_model, x_id_eval_z, "dA/id")
    da_ood_scores, da_ood_infer_sec = score_kitnet(da_model, x_ood_eval_z, "dA/ood")
    da_attack_scores, da_attack_infer_sec = score_kitnet(da_model, x_attack_eval_z, "dA/attack")
    rows, pol, stats = evaluate_object("dA", da_id_scores, da_ood_scores, da_attack_scores, args.naive_budget)
    result_rows.extend(rows)
    polarity_rows.append(pol)
    score_stats_rows.append(stats)
    diag_rows.append(
        {
            "object_label": "dA",
            "backend": "kitnet_da",
            "seed": int(args.seed),
            "train_sec": float(da_train_sec),
            "infer_sec_id_eval": float(da_id_infer_sec),
            "infer_sec_ood_eval": float(da_ood_infer_sec),
            "infer_sec_attack_eval": float(da_attack_infer_sec),
            "fm_grace": int(da_fm),
            "ad_grace": int(da_ad),
            "id_train_n": int(len(x_id_train_z)),
        }
    )

    # Object 2: current strongest candidate (migratable single-seed covreg-v2 line)
    strongest_fm = min(max(1, args.strongest_fm_grace), len(x_id_train_z) - 1)
    strongest_ad = len(x_id_train_z) - strongest_fm
    strongest_model, strongest_train_sec = train_kitnet_model(
        backend="transformer_covariance_regularized_v2",
        x_train=x_id_train_z,
        seed=args.seed,
        fm_grace=strongest_fm,
        ad_grace=strongest_ad,
        learning_rate=args.learning_rate,
        hidden_ratio=args.hidden_ratio,
        max_ae=args.max_ae,
    )
    st_id_scores, st_id_infer_sec = score_kitnet(strongest_model, x_id_eval_z, "strongest/id")
    st_ood_scores, st_ood_infer_sec = score_kitnet(strongest_model, x_ood_eval_z, "strongest/ood")
    st_attack_scores, st_attack_infer_sec = score_kitnet(strongest_model, x_attack_eval_z, "strongest/attack")
    rows, pol, stats = evaluate_object(
        "strongest_candidate_transformer_covreg_v2_seed101",
        st_id_scores,
        st_ood_scores,
        st_attack_scores,
        args.naive_budget,
    )
    result_rows.extend(rows)
    polarity_rows.append(pol)
    score_stats_rows.append(stats)
    diag_rows.append(
        {
            "object_label": "strongest_candidate_transformer_covreg_v2_seed101",
            "backend": "kitnet_transformer_covreg_v2",
            "seed": int(args.seed),
            "train_sec": float(strongest_train_sec),
            "infer_sec_id_eval": float(st_id_infer_sec),
            "infer_sec_ood_eval": float(st_ood_infer_sec),
            "infer_sec_attack_eval": float(st_attack_infer_sec),
            "fm_grace": int(strongest_fm),
            "ad_grace": int(strongest_ad),
            "id_train_n": int(len(x_id_train_z)),
        }
    )

    # Object 3: FT line
    device = args.device
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    ft_model, ft_hist, ft_best_epoch, ft_best_val, ft_train_sec = train_ft_autoencoder(
        x_train=x_id_train_z,
        seed=args.seed,
        epochs=args.ft_epochs,
        batch_size=args.ft_batch_size,
        lr=args.ft_lr,
        weight_decay=args.ft_weight_decay,
        patience=args.ft_patience,
        val_ratio=args.ft_val_ratio,
        d_token=args.ft_d_token,
        n_heads=args.ft_n_heads,
        n_blocks=args.ft_n_blocks,
        latent_dim=args.ft_latent_dim,
        decoder_hidden=args.ft_decoder_hidden,
        attn_dropout=args.ft_attn_dropout,
        ffn_dropout=args.ft_ffn_dropout,
        device=device,
    )
    ft_id_t0 = time.perf_counter()
    ft_id_scores = score_ft(ft_model, x_id_eval_z, args.ft_batch_size, device)
    ft_id_infer_sec = float(time.perf_counter() - ft_id_t0)
    ft_ood_t0 = time.perf_counter()
    ft_ood_scores = score_ft(ft_model, x_ood_eval_z, args.ft_batch_size, device)
    ft_ood_infer_sec = float(time.perf_counter() - ft_ood_t0)
    ft_attack_t0 = time.perf_counter()
    ft_attack_scores = score_ft(ft_model, x_attack_eval_z, args.ft_batch_size, device)
    ft_attack_infer_sec = float(time.perf_counter() - ft_attack_t0)

    rows, pol, stats = evaluate_object("ft_transformer_ae", ft_id_scores, ft_ood_scores, ft_attack_scores, args.naive_budget)
    result_rows.extend(rows)
    polarity_rows.append(pol)
    score_stats_rows.append(stats)
    diag_rows.append(
        {
            "object_label": "ft_transformer_ae",
            "backend": "ft_transformer_ae",
            "seed": int(args.seed),
            "train_sec": float(ft_train_sec),
            "infer_sec_id_eval": float(ft_id_infer_sec),
            "infer_sec_ood_eval": float(ft_ood_infer_sec),
            "infer_sec_attack_eval": float(ft_attack_infer_sec),
            "id_train_n": int(len(x_id_train_z)),
            "best_epoch": int(ft_best_epoch),
            "best_val_loss": float(ft_best_val),
            "device": str(device),
            "param_count": int(sum(p.numel() for p in ft_model.parameters())),
        }
    )

    results_df = pd.DataFrame(result_rows)
    polarity_df = pd.DataFrame(polarity_rows)
    score_stats_df = pd.DataFrame(score_stats_rows)
    diag_df = pd.DataFrame(diag_rows)
    ft_hist_df = pd.DataFrame(ft_hist)
    if not ft_hist_df.empty:
        ft_hist_df.insert(0, "object_label", "ft_transformer_ae")
        ft_hist_df.insert(1, "seed", int(args.seed))

    results_df.to_csv(run_dir / "object_prerun_results.csv", index=False)
    results_df.to_csv(run_dir / "results.csv", index=False)
    polarity_df.to_csv(run_dir / "object_polarity.csv", index=False)
    score_stats_df.to_csv(run_dir / "object_score_stats.csv", index=False)
    diag_df.to_csv(run_dir / "object_diagnostics.csv", index=False)
    ft_hist_df.to_csv(run_dir / "ft_training_history.csv", index=False)
    (run_dir / "feature_columns.txt").write_text("\n".join(numeric_cols) + "\n", encoding="utf-8")
    (run_dir / "split_used_summary.json").write_text(json.dumps(clean(split_meta), indent=2) + "\n", encoding="utf-8")
    (run_dir / "command.txt").write_text(" ".join(sys.argv) + "\n", encoding="utf-8")

    config = {
        "run_tag": args.run_tag,
        "split_manifest": str(args.split_manifest),
        "csv_path": None if args.csv_path is None else str(args.csv_path),
        "label_col": args.label_col,
        "normal_label": str(args.normal_label),
        "id_train_n": int(args.id_train_n),
        "id_eval_n": int(args.id_eval_n),
        "ood_eval_n": int(args.ood_eval_n),
        "attack_eval_n": int(args.attack_eval_n),
        "naive_budget": int(args.naive_budget),
        "seed": int(args.seed),
        "max_ae": int(args.max_ae),
        "learning_rate": float(args.learning_rate),
        "hidden_ratio": float(args.hidden_ratio),
        "da_fm_grace": int(args.da_fm_grace),
        "strongest_fm_grace": int(args.strongest_fm_grace),
        "ft": {
            "epochs": int(args.ft_epochs),
            "batch_size": int(args.ft_batch_size),
            "lr": float(args.ft_lr),
            "weight_decay": float(args.ft_weight_decay),
            "patience": int(args.ft_patience),
            "val_ratio": float(args.ft_val_ratio),
            "d_token": int(args.ft_d_token),
            "n_heads": int(args.ft_n_heads),
            "n_blocks": int(args.ft_n_blocks),
            "latent_dim": int(args.ft_latent_dim),
            "decoder_hidden": int(args.ft_decoder_hidden),
            "attn_dropout": float(args.ft_attn_dropout),
            "ffn_dropout": float(args.ft_ffn_dropout),
        },
        "device": str(args.device),
    }
    run_spec = {
        "stage": "second_environment_toniot_object_prerun",
        "goal": "Run A-line required objects (dA + strongest candidate + FT) on TON fallback with fixed split and policy family.",
        "objects": ["dA", "strongest_candidate_transformer_covreg_v2_seed101", "ft_transformer_ae"],
        "policies": ["fixed_id_q99", f"naive_calibrated_budget{min(args.naive_budget, args.ood_eval_n)}_target1pct", "det_floor_50pct_min_alarm"],
    }
    (run_dir / "config.json").write_text(json.dumps(clean(config), indent=2) + "\n", encoding="utf-8")
    (run_dir / "run_spec.json").write_text(json.dumps(clean(run_spec), indent=2) + "\n", encoding="utf-8")

    lines = [
        "# TON-IoT Mainline Object Pre-Run Summary",
        "",
        f"- Run tag: `{args.run_tag}`",
        f"- Split manifest: `{args.split_manifest}`",
        f"- Split used: ID-train={split_meta['id_train_n']}, ID-eval={split_meta['id_eval_n']}, OOD-eval={split_meta['ood_eval_n']}, attack-eval={split_meta['attack_eval_n']}",
        f"- Numeric feature count: `{split_meta['numeric_feature_n']}`",
        "",
        "## Polarity",
    ]
    for _, row in polarity_df.sort_values("object_label").iterrows():
        lines.append(
            f"- `{row['object_label']}`: chosen `{row['chosen_score']}`, auc={float(row['auc_chosen']):.6f}, "
            f"other={float(row['auc_other_orientation']):.6f}, delta={float(row['improvement_over_other']):.6f}"
        )
    lines += ["", "## Policy Results"]
    for _, row in results_df.sort_values(["object_label", "policy_name"]).iterrows():
        lines.append(
            f"- `{row['object_label']}` / `{row['policy_name']}`: "
            f"ood_alarm={float(row['ood_alarm_ratio']):.6f}, "
            f"attack_det={float(row['attack_detection']):.6f}, "
            f"id_alarm={float(row['id_alarm_ratio']):.6f}, "
            f"auc={float(row['roc_auc_attack_vs_ood']):.6f}"
        )
    lines += [
        "",
        "## Note",
        "- This node is a local prereun for object comparability and orientation consistency before formal second-environment submission.",
    ]
    (run_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "run_dir": str(run_dir),
                "objects": ["dA", "strongest_candidate_transformer_covreg_v2_seed101", "ft_transformer_ae"],
                "id_train_n": int(split_meta["id_train_n"]),
                "id_eval_n": int(split_meta["id_eval_n"]),
                "ood_eval_n": int(split_meta["ood_eval_n"]),
                "attack_eval_n": int(split_meta["attack_eval_n"]),
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
