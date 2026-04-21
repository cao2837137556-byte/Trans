from __future__ import annotations

import argparse
import copy
import json
import random
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
    if isinstance(obj, np.ndarray):
        return [clean(v) for v in obj.tolist()]
    if isinstance(obj, np.generic):
        return clean(obj.item())
    if isinstance(obj, Path):
        return str(obj)
    return obj


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def choose_orientation(ood_scores: np.ndarray, attack_scores: np.ndarray) -> Tuple[int, float, float]:
    y = np.concatenate([np.zeros(len(ood_scores), dtype=np.int64), np.ones(len(attack_scores), dtype=np.int64)])
    s_pos = np.concatenate([ood_scores, attack_scores])
    s_neg = -s_pos
    auc_pos = float(roc_auc_score(y, s_pos))
    auc_neg = float(roc_auc_score(y, s_neg))
    if auc_pos >= auc_neg:
        return 1, auc_pos, auc_neg
    return -1, auc_neg, auc_pos


def eval_threshold(thr: float, id_scores: np.ndarray, ood_scores: np.ndarray, attack_scores: np.ndarray) -> Dict[str, float]:
    return {
        "threshold": float(thr),
        "id_alarm_ratio": float(np.mean(id_scores > thr)),
        "ood_alarm_ratio": float(np.mean(ood_scores > thr)),
        "attack_detection": float(np.mean(attack_scores > thr)),
    }


def evaluate_policies(id_scores: np.ndarray, ood_scores: np.ndarray, attack_scores: np.ndarray, naive_budget: int) -> List[Dict[str, float]]:
    rows: List[Dict[str, float]] = []
    fixed_thr = float(np.quantile(id_scores, 0.99))
    rows.append({"policy_name": "fixed_id_q99", **eval_threshold(fixed_thr, id_scores, ood_scores, attack_scores)})
    budget = min(int(naive_budget), len(ood_scores))
    naive_thr = float(np.quantile(ood_scores[:budget], 0.99))
    rows.append(
        {
            "policy_name": f"naive_calibrated_budget{budget}_target1pct",
            **eval_threshold(naive_thr, id_scores, ood_scores, attack_scores),
        }
    )
    return rows


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


def train_ft(
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
) -> Tuple[nn.Module, float]:
    set_seed(seed)
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
    bad = 0
    t0 = time.perf_counter()
    for _epoch in range(1, epochs + 1):
        model.train()
        for (xb,) in fit_loader:
            xb = xb.to(device)
            opt.zero_grad()
            loss = crit(model(xb), xb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
        val_loss = eval_loss(model, val_loader, device)
        if val_loss < best_val - 1e-8:
            best_val = val_loss
            best_state = copy.deepcopy(model.state_dict())
            bad = 0
        else:
            bad += 1
        if bad >= patience:
            break
    model.load_state_dict(best_state)
    return model, float(time.perf_counter() - t0)


def score_ft(model: nn.Module, x: np.ndarray, batch_size: int, device: str) -> np.ndarray:
    model.eval()
    out: List[np.ndarray] = []
    with torch.no_grad():
        for (xb,) in make_loader(x, batch_size, False):
            xb = xb.to(device)
            err = (model(xb) - xb) ** 2
            s = torch.sqrt(torch.mean(err, dim=1)).detach().cpu().numpy().astype(np.float64)
            s = np.nan_to_num(s, nan=1e-6, posinf=1e6, neginf=-1e6)
            out.append(s)
    return np.concatenate(out).astype(np.float64)


def train_da(
    x_train: np.ndarray,
    seed: int,
    fm_grace: int,
    max_ae: int,
    learning_rate: float,
    hidden_ratio: float,
) -> Tuple[kit.KitNET, float]:
    fm = min(max(1, fm_grace), len(x_train) - 1)
    ad = len(x_train) - fm
    model = kit.KitNET(
        n=x_train.shape[1],
        max_autoencoder_size=max_ae,
        FM_grace_period=fm,
        AD_grace_period=ad,
        learning_rate=learning_rate,
        hidden_ratio=hidden_ratio,
        detector_backend="da",
        detector_seed=seed,
    )
    t0 = time.perf_counter()
    for i in range(len(x_train)):
        if i > 0 and i % 2000 == 0:
            print(f"[dA] train progress: {i}/{len(x_train)}", flush=True)
        model.process(x_train[i])
    return model, float(time.perf_counter() - t0)


def score_da(model: kit.KitNET, x: np.ndarray, name: str) -> np.ndarray:
    out = np.zeros(len(x), dtype=np.float64)
    for i in range(len(x)):
        if i > 0 and i % 2000 == 0:
            print(f"[dA/{name}] score progress: {i}/{len(x)}", flush=True)
        v = float(model.executeAD(x[i]))
        if not np.isfinite(v):
            v = 1e-6
        out[i] = v
    return out


def build_split(
    manifest_path: Path,
    csv_path: Path | None,
    label_col: str,
    normal_label: str,
    id_train_n: int,
    id_eval_n: int,
    ood_eval_n: int,
    attack_eval_n: int,
) -> Tuple[List[str], np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    src_csv = csv_path if csv_path is not None else Path(manifest["csv_path"])
    df = pd.read_csv(src_csv, low_memory=False)
    if label_col not in df.columns:
        raise RuntimeError(f"Missing label col: {label_col}")

    id_idx_full = np.asarray(manifest["id_indices"], dtype=np.int64)
    ood_idx_full = np.asarray(manifest["ood_indices"], dtype=np.int64)
    attack_idx_full = np.asarray(manifest["attack_indices"], dtype=np.int64)

    if id_train_n + id_eval_n > len(id_idx_full):
        raise RuntimeError("id_train_n + id_eval_n exceeds ID pool.")
    if ood_eval_n > len(ood_idx_full):
        raise RuntimeError("ood_eval_n exceeds OOD pool.")
    if attack_eval_n > len(attack_idx_full):
        raise RuntimeError("attack_eval_n exceeds attack pool.")

    id_train_idx = id_idx_full[:id_train_n]
    id_eval_idx = id_idx_full[id_train_n : id_train_n + id_eval_n]
    ood_eval_idx = ood_idx_full[:ood_eval_n]
    attack_eval_idx = attack_idx_full[:attack_eval_n]

    labels = df[label_col].astype(str).to_numpy()
    if not np.all(labels[id_train_idx] == str(normal_label)):
        raise RuntimeError("id_train includes non-normal samples.")
    if not np.all(labels[id_eval_idx] == str(normal_label)):
        raise RuntimeError("id_eval includes non-normal samples.")
    if np.any(labels[attack_eval_idx] == str(normal_label)):
        raise RuntimeError("attack_eval includes normal samples.")

    numeric_cols = [c for c in df.columns if c != label_col and pd.api.types.is_numeric_dtype(df[c])]
    if not numeric_cols:
        raise RuntimeError("No numeric cols.")
    x = df[numeric_cols].to_numpy(dtype=np.float64)
    return numeric_cols, x[id_train_idx], x[id_eval_idx], x[ood_eval_idx], x[attack_eval_idx]


def signed_log1p(x: np.ndarray) -> np.ndarray:
    return np.sign(x) * np.log1p(np.abs(x))


def make_feature_view(
    view_name: str,
    x_id_train: np.ndarray,
    x_id_eval: np.ndarray,
    x_ood_eval: np.ndarray,
    x_attack_eval: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict[str, object]]:
    if view_name == "standard_zscore":
        scaler = StandardScaler().fit(x_id_train)
        return (
            scaler.transform(x_id_train).astype(np.float64),
            scaler.transform(x_id_eval).astype(np.float64),
            scaler.transform(x_ood_eval).astype(np.float64),
            scaler.transform(x_attack_eval).astype(np.float64),
            {"view": view_name},
        )
    if view_name == "winsor_zscore":
        low = np.quantile(x_id_train, 0.005, axis=0)
        high = np.quantile(x_id_train, 0.995, axis=0)
        tr = np.clip(x_id_train, low, high)
        te = np.clip(x_id_eval, low, high)
        oe = np.clip(x_ood_eval, low, high)
        ae = np.clip(x_attack_eval, low, high)
        scaler = StandardScaler().fit(tr)
        return (
            scaler.transform(tr).astype(np.float64),
            scaler.transform(te).astype(np.float64),
            scaler.transform(oe).astype(np.float64),
            scaler.transform(ae).astype(np.float64),
            {"view": view_name, "winsor_low_q": 0.005, "winsor_high_q": 0.995},
        )
    if view_name == "signed_log1p_zscore":
        tr = signed_log1p(x_id_train)
        te = signed_log1p(x_id_eval)
        oe = signed_log1p(x_ood_eval)
        ae = signed_log1p(x_attack_eval)
        scaler = StandardScaler().fit(tr)
        return (
            scaler.transform(tr).astype(np.float64),
            scaler.transform(te).astype(np.float64),
            scaler.transform(oe).astype(np.float64),
            scaler.transform(ae).astype(np.float64),
            {"view": view_name},
        )
    raise ValueError(f"Unsupported feature view: {view_name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Minimal model-expression coupling probe on TON split.")
    parser.add_argument("--run-tag", required=True)
    parser.add_argument(
        "--split-manifest",
        type=Path,
        default=ARTIFACT_RUNS_DIR / "second_environment_toniot_precheck_2026-04-20" / "split_manifest.json",
    )
    parser.add_argument("--csv-path", type=Path, default=None)
    parser.add_argument("--label-col", default="label")
    parser.add_argument("--normal-label", default="0")
    parser.add_argument("--id-train-n", type=int, default=4000)
    parser.add_argument("--id-eval-n", type=int, default=2000)
    parser.add_argument("--ood-eval-n", type=int, default=5000)
    parser.add_argument("--attack-eval-n", type=int, default=5000)
    parser.add_argument("--naive-budget", type=int, default=5000)
    parser.add_argument("--feature-views", default="standard_zscore,winsor_zscore,signed_log1p_zscore")
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--da-fm-grace", type=int, default=1000)
    parser.add_argument("--max-ae", type=int, default=10)
    parser.add_argument("--learning-rate", type=float, default=0.1)
    parser.add_argument("--hidden-ratio", type=float, default=0.75)
    parser.add_argument("--ft-epochs", type=int, default=6)
    parser.add_argument("--ft-batch-size", type=int, default=512)
    parser.add_argument("--ft-lr", type=float, default=1e-3)
    parser.add_argument("--ft-weight-decay", type=float, default=1e-6)
    parser.add_argument("--ft-patience", type=int, default=4)
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
    score_dir = run_dir / "scores"
    score_dir.mkdir(exist_ok=True)

    feature_views = [v.strip() for v in args.feature_views.split(",") if v.strip()]
    numeric_cols, x_id_train_raw, x_id_eval_raw, x_ood_eval_raw, x_attack_eval_raw = build_split(
        manifest_path=args.split_manifest,
        csv_path=args.csv_path,
        label_col=args.label_col,
        normal_label=str(args.normal_label),
        id_train_n=args.id_train_n,
        id_eval_n=args.id_eval_n,
        ood_eval_n=args.ood_eval_n,
        attack_eval_n=args.attack_eval_n,
    )

    result_rows: List[Dict[str, object]] = []
    pol_rows: List[Dict[str, object]] = []
    view_rows: List[Dict[str, object]] = []
    diag_rows: List[Dict[str, object]] = []

    device = args.device
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"

    for view_name in feature_views:
        print(f"[view] {view_name}", flush=True)
        x_id_train, x_id_eval, x_ood_eval, x_attack_eval, view_meta = make_feature_view(
            view_name, x_id_train_raw, x_id_eval_raw, x_ood_eval_raw, x_attack_eval_raw
        )
        view_rows.append(
            {
                "feature_view": view_name,
                "id_train_n": int(len(x_id_train)),
                "id_eval_n": int(len(x_id_eval)),
                "ood_eval_n": int(len(x_ood_eval)),
                "attack_eval_n": int(len(x_attack_eval)),
                "n_features": int(x_id_train.shape[1]),
                "id_train_mean_abs": float(np.mean(np.abs(x_id_train))),
                "id_train_max_abs": float(np.max(np.abs(x_id_train))),
                **view_meta,
            }
        )

        # dA
        da_model, da_train_sec = train_da(
            x_id_train,
            seed=args.seed,
            fm_grace=args.da_fm_grace,
            max_ae=args.max_ae,
            learning_rate=args.learning_rate,
            hidden_ratio=args.hidden_ratio,
        )
        da_id = score_da(da_model, x_id_eval, f"{view_name}/id")
        da_ood = score_da(da_model, x_ood_eval, f"{view_name}/ood")
        da_attack = score_da(da_model, x_attack_eval, f"{view_name}/attack")
        np.save(score_dir / f"{view_name}_dA_id.npy", da_id)
        np.save(score_dir / f"{view_name}_dA_ood.npy", da_ood)
        np.save(score_dir / f"{view_name}_dA_attack.npy", da_attack)
        da_sign, da_auc, da_auc_other = choose_orientation(da_ood, da_attack)
        da_id_s = da_sign * da_id
        da_ood_s = da_sign * da_ood
        da_attack_s = da_sign * da_attack
        pol_rows.append(
            {
                "feature_view": view_name,
                "object_label": "dA",
                "chosen_orientation": "raw_score" if da_sign == 1 else "neg_raw_score",
                "chosen_sign": int(da_sign),
                "auc_chosen": float(da_auc),
                "auc_other_orientation": float(da_auc_other),
            }
        )
        for row in evaluate_policies(da_id_s, da_ood_s, da_attack_s, args.naive_budget):
            result_rows.append(
                {
                    "feature_view": view_name,
                    "object_label": "dA",
                    "roc_auc_attack_vs_ood": float(da_auc),
                    **row,
                }
            )
        diag_rows.append({"feature_view": view_name, "object_label": "dA", "train_sec": float(da_train_sec)})

        # FT
        ft_model, ft_train_sec = train_ft(
            x_train=x_id_train,
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
        ft_id = score_ft(ft_model, x_id_eval, args.ft_batch_size, device)
        ft_ood = score_ft(ft_model, x_ood_eval, args.ft_batch_size, device)
        ft_attack = score_ft(ft_model, x_attack_eval, args.ft_batch_size, device)
        np.save(score_dir / f"{view_name}_ft_id.npy", ft_id)
        np.save(score_dir / f"{view_name}_ft_ood.npy", ft_ood)
        np.save(score_dir / f"{view_name}_ft_attack.npy", ft_attack)
        ft_sign, ft_auc, ft_auc_other = choose_orientation(ft_ood, ft_attack)
        ft_id_s = ft_sign * ft_id
        ft_ood_s = ft_sign * ft_ood
        ft_attack_s = ft_sign * ft_attack
        pol_rows.append(
            {
                "feature_view": view_name,
                "object_label": "ft_transformer_ae",
                "chosen_orientation": "raw_score" if ft_sign == 1 else "neg_raw_score",
                "chosen_sign": int(ft_sign),
                "auc_chosen": float(ft_auc),
                "auc_other_orientation": float(ft_auc_other),
            }
        )
        for row in evaluate_policies(ft_id_s, ft_ood_s, ft_attack_s, args.naive_budget):
            result_rows.append(
                {
                    "feature_view": view_name,
                    "object_label": "ft_transformer_ae",
                    "roc_auc_attack_vs_ood": float(ft_auc),
                    **row,
                }
            )
        diag_rows.append(
            {
                "feature_view": view_name,
                "object_label": "ft_transformer_ae",
                "train_sec": float(ft_train_sec),
                "param_count": int(sum(p.numel() for p in ft_model.parameters())),
                "device": str(device),
            }
        )

    result_df = pd.DataFrame(result_rows)
    pol_df = pd.DataFrame(pol_rows)
    view_df = pd.DataFrame(view_rows)
    diag_df = pd.DataFrame(diag_rows)

    result_df.to_csv(run_dir / "coupling_probe_results.csv", index=False)
    result_df.to_csv(run_dir / "results.csv", index=False)
    pol_df.to_csv(run_dir / "coupling_probe_polarity.csv", index=False)
    view_df.to_csv(run_dir / "coupling_probe_view_stats.csv", index=False)
    diag_df.to_csv(run_dir / "coupling_probe_diagnostics.csv", index=False)
    (run_dir / "feature_columns.txt").write_text("\n".join(numeric_cols) + "\n", encoding="utf-8")
    (run_dir / "command.txt").write_text(" ".join(sys.argv) + "\n", encoding="utf-8")

    config = {
        "run_tag": args.run_tag,
        "split_manifest": str(args.split_manifest),
        "csv_path": None if args.csv_path is None else str(args.csv_path),
        "feature_views": feature_views,
        "seed": int(args.seed),
        "id_train_n": int(args.id_train_n),
        "id_eval_n": int(args.id_eval_n),
        "ood_eval_n": int(args.ood_eval_n),
        "attack_eval_n": int(args.attack_eval_n),
        "naive_budget": int(args.naive_budget),
    }
    run_spec = {
        "stage": "second_environment_toniot_coupling_probe",
        "goal": "Verify whether FT under-detection is sensitive to front-expression transformations under fixed split and policy.",
        "models": ["dA", "ft_transformer_ae"],
    }
    (run_dir / "config.json").write_text(json.dumps(clean(config), indent=2), encoding="utf-8")
    (run_dir / "run_spec.json").write_text(json.dumps(clean(run_spec), indent=2), encoding="utf-8")

    lines = [
        "# TON Coupling Probe Summary",
        "",
        f"- Run tag: `{args.run_tag}`",
        f"- Feature views: `{', '.join(feature_views)}`",
        f"- Split: ID-train={args.id_train_n}, ID-eval={args.id_eval_n}, OOD-eval={args.ood_eval_n}, attack-eval={args.attack_eval_n}",
        "",
        "## FT fixed_id_q99",
    ]
    ft_fixed = result_df[(result_df["object_label"] == "ft_transformer_ae") & (result_df["policy_name"] == "fixed_id_q99")]
    for _, r in ft_fixed.sort_values("feature_view").iterrows():
        lines.append(
            f"- `{r['feature_view']}`: ood_alarm={float(r['ood_alarm_ratio']):.6f}, "
            f"attack_det={float(r['attack_detection']):.6f}, id_alarm={float(r['id_alarm_ratio']):.6f}, auc={float(r['roc_auc_attack_vs_ood']):.6f}"
        )
    lines += ["", "## FT naive_budget5000"]
    ft_naive = result_df[
        (result_df["object_label"] == "ft_transformer_ae")
        & (result_df["policy_name"] == f"naive_calibrated_budget{min(args.naive_budget, args.ood_eval_n)}_target1pct")
    ]
    for _, r in ft_naive.sort_values("feature_view").iterrows():
        lines.append(
            f"- `{r['feature_view']}`: ood_alarm={float(r['ood_alarm_ratio']):.6f}, "
            f"attack_det={float(r['attack_detection']):.6f}, id_alarm={float(r['id_alarm_ratio']):.6f}, auc={float(r['roc_auc_attack_vs_ood']):.6f}"
        )
    (run_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({"run_dir": str(run_dir)}, ensure_ascii=True))


if __name__ == "__main__":
    main()
