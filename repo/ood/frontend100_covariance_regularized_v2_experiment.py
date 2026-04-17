from __future__ import annotations
import argparse, json, subprocess, sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf

THIS_DIR = Path(__file__).resolve().parent
REPO_DIR = THIS_DIR.parent
WORKTREE_ROOT = REPO_DIR.parent
for p in [THIS_DIR, REPO_DIR]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import frontend100_covariance_regularized_v1_experiment as v1
import frontend100_latent_scorer_benchmark as lsb
import frontend100_negative_recipe_rescoring as resc

NEGATIVE_RECIPE = "latent_swap_spike_mix"
OLD_BEST_SCORER = "log_weighted_z_rmse0.5_cos1.0"
MAHA_DIAGLOAD_PREFIX = "ledoitwolf_diagload"


def clean(obj):
    return v1.clean(obj)


def load_json(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def md_table(df: pd.DataFrame) -> str:
    return resc.md_table(df)


def tag_float(x: float) -> str:
    return str(float(x)).replace(".", "p")


def cfg_grid(limit: int) -> List[Dict]:
    grid = []
    for alpha_scale in [0.05, 0.1]:
        for lambda_tail in [0.1, 0.5]:
            grid.append({
                "ema_momentum": 0.99,
                "alpha_scale": float(alpha_scale),
                "lambda_tail": float(lambda_tail),
                "lambda_neg": 0.5,
                "lambda_floor": 0.01,
                "tau_mode": "mean2std",
                "tau_k": 2.0,
                "margin_neg": 1.0,
                "var_floor": 1e-3,
            })
    return grid[: int(limit)]


def cfg_label(cfg: Dict) -> str:
    return f"covregv2_as{tag_float(cfg['alpha_scale'])}_lt{tag_float(cfg['lambda_tail'])}_ln{tag_float(cfg['lambda_neg'])}_lf{tag_float(cfg['lambda_floor'])}"


def run_cmd(cmd: List[str]) -> None:
    print("[run] " + " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=str(WORKTREE_ROOT))


def stage1_cmd(args, rel_tag: str, train_csv: Path, train_labels: Path, ood_csv: Path | None, cfg: Dict, dry: bool) -> List[str]:
    cmd = [
        sys.executable, str(REPO_DIR / "ood" / "stage1_probe.py"), "--run-tag", rel_tag,
        "--train-csv", str(train_csv), "--train-labels", str(train_labels),
        "--max-ae", str(args.max_ae), "--fm-grace", "64" if dry else str(args.fm_grace),
        "--ad-grace", "192" if dry else str(args.ad_grace),
        "--train-samples", "256" if dry else str(args.train_samples),
        "--id-eval-samples", "128" if dry else str(args.id_eval_samples),
        "--learning-rate", str(args.learning_rate), "--hidden-ratio", str(args.hidden_ratio),
        "--seed", str(args.seed), "--detector-backend", "transformer_covariance_regularized_v2",
        "--latent-margin", str(args.latent_margin), "--latent-lambda", str(args.latent_lambda),
        "--latent-contrastive-mode", "covreg_v2", "--latent-pooling", str(args.latent_pooling),
        "--latent-warmup-steps", "64" if dry else str(args.latent_warmup_steps),
        "--latent-neg-prob-swap", "0.5", "--latent-neg-prob-permute", "0.0",
        "--latent-neg-prob-spike", "0.5", "--latent-neg-prob-replace", "0.0",
        "--latent-covreg-buffer-size", str(args.latent_covreg_buffer_size),
        "--latent-covreg-ema-momentum", str(cfg["ema_momentum"]),
        "--latent-covreg-alpha-scale", str(cfg["alpha_scale"]),
        "--latent-covreg-lambda-tail", str(cfg["lambda_tail"]),
        "--latent-covreg-lambda-neg", str(cfg["lambda_neg"]),
        "--latent-covreg-lambda-floor", str(cfg["lambda_floor"]),
        "--latent-covreg-tau-mode", str(cfg["tau_mode"]),
        "--latent-covreg-tau-k", str(cfg["tau_k"]),
        "--latent-covreg-margin-neg", str(cfg["margin_neg"]),
        "--latent-covreg-var-floor", str(cfg["var_floor"]),
    ]
    if ood_csv is not None:
        cmd.extend(["--benign-dataset", f"iot23_ood_benign|{ood_csv}"])
    if dry:
        cmd.extend(["--skip-benign", "--skip-attack", "--force-retrain"])
    else:
        cmd.append("--skip-attack")
        if args.force_retrain:
            cmd.append("--force-retrain")
    return cmd


def stable_mahalanobis_cholesky(x: np.ndarray, mean: np.ndarray, cov: np.ndarray, alpha_scale: float) -> Tuple[np.ndarray, Dict]:
    x = np.asarray(x, dtype=np.float64)
    mean = np.asarray(mean, dtype=np.float64).reshape(-1)
    cov = np.asarray(cov, dtype=np.float64)
    cov = 0.5 * (cov + cov.T)
    diag = np.clip(np.diag(cov), 1e-12, None)
    alpha = max(float(np.median(diag) * float(alpha_scale)), 1e-12)
    sigma = cov + alpha * np.eye(cov.shape[0], dtype=np.float64)
    sigma = 0.5 * (sigma + sigma.T)
    chol = None
    used = None
    for jitter in [1e-6, 1e-5, 1e-4]:
        try:
            chol = np.linalg.cholesky(sigma + jitter * np.eye(sigma.shape[0], dtype=np.float64))
            used = float(jitter)
            break
        except np.linalg.LinAlgError:
            chol = None
    if chol is None:
        raise RuntimeError("NumPy Cholesky failed after jitter fallback for offline diagload scorer")
    delta = x - mean[None, :]
    y = np.linalg.solve(chol, delta.T)
    score = np.sqrt(np.clip(np.sum(y * y, axis=0), 0.0, None))
    meta = {
        "alpha_scale": float(alpha_scale),
        "alpha": float(alpha),
        "jitter": used,
        "diag_min": float(np.min(diag)),
        "diag_median": float(np.median(diag)),
        "diag_max": float(np.max(diag)),
        "diag_condition_proxy": float(np.max(diag) / max(np.min(diag), 1e-12)),
        "floor_hit_ratio": float(np.mean(diag < alpha)),
    }
    return score, meta


def score_maha_diagload(checkpoint: Path, x_fit: np.ndarray, x_id: np.ndarray, x_ood: np.ndarray, x_attack: np.ndarray, cache_prefix: Path, batch_size: int, alpha_scale: float):
    suffix = f"_diagload_f{tag_float(alpha_scale)}"
    files = [cache_prefix.with_name(cache_prefix.name + suffix + s) for s in ["_id.npy", "_ood.npy", "_attack.npy", "_hcal.npy", "_meta.json"]]
    if all(p.exists() for p in files):
        meta = load_json(files[4])
        return np.load(files[0]), np.load(files[1]), np.load(files[2]), meta.get("fit_meta", {}), meta.get("cal_meta", {}), np.load(files[3]), meta
    model = __import__("KitNET").KitNET.load_checkpoint(checkpoint)
    h_fit, fit_meta = lsb.extract_global_latent(model=model, x=x_fit, batch_size=batch_size, negative=False)
    h_cal, cal_meta = lsb.extract_global_latent(model=model, x=x_id, batch_size=batch_size, negative=False)
    h_ood, ood_meta = lsb.extract_global_latent(model=model, x=x_ood, batch_size=batch_size, negative=False)
    h_attack, attack_meta = lsb.extract_global_latent(model=model, x=x_attack, batch_size=batch_size, negative=False)
    lw = LedoitWolf().fit(np.asarray(h_fit, dtype=np.float64))
    sid, diag_meta = stable_mahalanobis_cholesky(h_cal, lw.location_, lw.covariance_, alpha_scale)
    sood, _ = stable_mahalanobis_cholesky(h_ood, lw.location_, lw.covariance_, alpha_scale)
    satt, _ = stable_mahalanobis_cholesky(h_attack, lw.location_, lw.covariance_, alpha_scale)
    meta = {
        "score_version": f"ledoitwolf_diagload_f{tag_float(alpha_scale)}",
        "estimator": "sklearn.covariance.LedoitWolf + Cholesky solve + diagonal loading",
        "no_explicit_inverse": True,
        "fit_source": "ID benign training split only",
        "fit_samples": int(h_fit.shape[0]),
        "latent_dim": int(h_fit.shape[1]),
        "diagload_meta": diag_meta,
        "fit_meta": clean(fit_meta),
        "cal_meta": clean(cal_meta),
        "ood_meta": clean(ood_meta),
        "attack_meta": clean(attack_meta),
    }
    np.save(files[0], sid); np.save(files[1], sood); np.save(files[2], satt); np.save(files[3], h_cal)
    files[4].write_text(json.dumps(clean(meta), indent=2, ensure_ascii=False), encoding="utf-8")
    return sid, sood, satt, fit_meta, cal_meta, h_cal, meta


def add_rows(rows: List[Dict], label: str, scorer: str, family: str, scores, high_idx, mixed_idx, args, cfg: Dict, run_dir: Path, ckpt: Path) -> None:
    before = len(rows)
    rows.extend(lsb.build_score_rows(
        object_label=f"{label}__{scorer}", detector_family="covariance_regularized_v2", scorer_label=scorer, scorer_family=family,
        id_scores=scores[0], ood_scores=scores[1], attack_scores=scores[2], high_idx=high_idx, mixed_idx=mixed_idx,
        scan_points=args.scan_points, calibration_budget=args.calibration_budget, calibration_target=args.calibration_target,
    ))
    for r in rows[before:]:
        r.update({
            "source_mode": "trained_now", "variant": cfg_label(cfg),
            "alpha_scale": cfg["alpha_scale"], "lambda_tail": cfg["lambda_tail"], "lambda_neg": cfg["lambda_neg"], "lambda_floor": cfg["lambda_floor"],
            "ema_momentum": cfg["ema_momentum"], "run_dir": str(run_dir), "checkpoint": str(ckpt),
        })


def reference_rows() -> List[Dict]:
    rescue = WORKTREE_ROOT / "runs" / "frontend100_mahalanobis_rescue_2026-04-07" / "mahalanobis_rescue_results.csv"
    if not rescue.exists():
        return []
    df = pd.read_csv(rescue)
    keep = {
        "latent_swap_spike_mix_no_compact__log_weighted_z_rmse0.5_cos1.0_old",
        "covariance_regularized_v1_covreg_vm0p2_vx2p0_lv0p5_lc0p05__log_weighted_z_rmse0.5_cos1.0",
        "covreg_best__ledoitwolf_diagload_f0p2",
        "transformer_tailreg__default_score",
        "da__default_score",
    }
    rows = df[df["object_label"].isin(keep)].copy()
    rows["source_mode"] = "reuse_reference"
    rows["variant"] = rows.get("variant", "reference")
    return rows.to_dict("records")


def v2_diag(label: str, cfg: Dict, run_dir: Path, ckpt: Path, h_cal: np.ndarray, cal_meta: Dict, maha_meta: Dict) -> Dict:
    h = v1.block_layernorm(h_cal, (cal_meta or {}).get("detector_rows", []))
    var = np.var(h, axis=0) if h.size else np.asarray([0.0])
    q = np.quantile(var, [0.01, 0.05, 0.5, 0.95, 0.99])
    metrics = load_json(run_dir / "metrics.json") if (run_dir / "metrics.json").exists() else {}
    train_diag = metrics.get("latent_contrastive_diagnostics", {}) or {}
    return {
        "object_label": label,
        "alpha_scale": float(cfg["alpha_scale"]),
        "lambda_tail": float(cfg["lambda_tail"]),
        "lambda_neg": float(cfg["lambda_neg"]),
        "lambda_floor": float(cfg["lambda_floor"]),
        "ema_momentum": float(cfg["ema_momentum"]),
        "latent_dim": int(h.shape[1]) if h.ndim == 2 else 0,
        "samples": int(h.shape[0]) if h.ndim == 2 else 0,
        "var_mean": float(np.mean(var)), "var_min_observed": float(np.min(var)), "var_p01": float(q[0]), "var_p05": float(q[1]), "var_p50": float(q[2]), "var_p95": float(q[3]), "var_p99": float(q[4]), "var_max_observed": float(np.max(var)),
        "collapse_dims": int(np.sum(var < 1e-3)), "runaway_dims": int(np.sum(var > max(1.0, float(np.quantile(var, 0.95)) * 5.0))),
        "train_naninf_events": train_diag.get("latent_covreg_naninf_events_mean"),
        "train_v2_updates": train_diag.get("latent_covreg_v2_updates_mean"),
        "train_tail_loss": train_diag.get("latent_covreg_v2_tail_loss_mean"),
        "train_neg_loss": train_diag.get("latent_covreg_v2_neg_loss_mean"),
        "train_floor_loss": train_diag.get("latent_covreg_v2_floor_loss_mean"),
        "train_tau_ref": train_diag.get("latent_covreg_v2_tau_ref_mean"),
        "train_tail_hit_rate": train_diag.get("latent_covreg_v2_tail_hit_rate_mean"),
        "train_neg_violation_rate": train_diag.get("latent_covreg_v2_neg_violation_rate_mean"),
        "train_trace": train_diag.get("latent_covreg_v2_trace_mean"),
        "train_diag_condition_proxy": train_diag.get("latent_covreg_v2_diag_condition_proxy_mean"),
        "train_floor_hit_ratio": train_diag.get("latent_covreg_v2_floor_hit_ratio_mean"),
        "train_cholesky_failures": train_diag.get("latent_covreg_v2_cholesky_failures_mean"),
        "train_cholesky_total": train_diag.get("latent_covreg_v2_cholesky_total_mean"),
        "offline_diagload_floor_hit_ratio": (maha_meta or {}).get("diagload_meta", {}).get("floor_hit_ratio"),
        "offline_diagload_diag_condition_proxy": (maha_meta or {}).get("diagload_meta", {}).get("diag_condition_proxy"),
        "run_dir": str(run_dir), "checkpoint": str(ckpt),
    }


def plot_fixed(results: pd.DataFrame, out: Path) -> None:
    fixed = results[(results["policy_name"] == "fixed_id_q99") & (results["selection_feasible"])].copy()
    plt.figure(figsize=(11.2, 7.0))
    for _, r in fixed.iterrows():
        s = str(r["scorer_label"])
        color = "#d62728" if s == OLD_BEST_SCORER else ("#1f77b4" if "diagload" in s else "#555555")
        marker = "o" if "covariance_regularized_v2" in str(r["object_label"]) else "s"
        plt.scatter(float(r["ood_alarm_ratio_eval"]), float(r["attack_detection_high_purity"]), color=color, marker=marker, s=90)
        label = str(r["object_label"]).replace("covariance_regularized_v2_", "v2_").replace("covariance_regularized_v1_", "v1_").replace("latent_swap_spike_mix_no_compact", "no_compact")
        if "v2_" in label or "diagload_f0p2" in label or "no_compact" in label or "tailreg" in label or "da__" in label:
            plt.text(float(r["ood_alarm_ratio_eval"]) + 0.004, float(r["attack_detection_high_purity"]) + 0.006, f"{label}:{s}", fontsize=6.8)
    plt.xlabel("OOD benign alarm ratio (eval split, fixed q99)")
    plt.ylabel("High-purity attack detection")
    plt.title("Covariance-Regularized v2 fixed trade-off")
    plt.grid(alpha=0.25); plt.tight_layout(); plt.savefig(out, dpi=180); plt.close()


def plot_diag(diag: pd.DataFrame, plot_dir: Path) -> None:
    if diag.empty:
        return
    labels = diag["object_label"].astype(str).str.replace("covariance_regularized_v2_", "v2_", regex=False).tolist(); x = np.arange(len(diag))
    plt.figure(figsize=(10.0, 5.6))
    plt.bar(x - 0.22, diag["train_tail_hit_rate"].fillna(0).to_numpy(float), width=0.22, label="tail hit")
    plt.bar(x, diag["train_neg_violation_rate"].fillna(0).to_numpy(float), width=0.22, label="neg violation")
    plt.bar(x + 0.22, diag["offline_diagload_floor_hit_ratio"].fillna(0).to_numpy(float), width=0.22, label="diagload floor hit")
    plt.xticks(x, labels, rotation=25, ha="right"); plt.ylabel("ratio"); plt.title("Covreg v2 tail / negative / diagload diagnostics")
    plt.grid(axis="y", alpha=0.25); plt.legend(); plt.tight_layout(); plt.savefig(plot_dir / "benign_score_tail_diagnostics.png", dpi=180); plt.close()
    plt.figure(figsize=(10.0, 5.6))
    plt.bar(x - 0.2, diag["train_trace"].fillna(0).to_numpy(float), width=0.4, label="EMA cov trace")
    plt.bar(x + 0.2, np.log10(np.maximum(diag["train_diag_condition_proxy"].fillna(1).to_numpy(float), 1e-12)), width=0.4, label="log10 diag condition proxy")
    plt.xticks(x, labels, rotation=25, ha="right"); plt.title("EMA covariance diagnostics")
    plt.grid(axis="y", alpha=0.25); plt.legend(); plt.tight_layout(); plt.savefig(plot_dir / "ema_covariance_diagnostics.png", dpi=180); plt.close()


def append_map(run_tag: str) -> None:
    p = WORKTREE_ROOT / "runs" / "mainline_docs" / "mainline_experiment_map.md"
    if not p.exists():
        return
    text = p.read_text(encoding="utf-8")
    if f"`{run_tag}`" in text:
        return
    entry = f"\n- `{run_tag}`: Transformer-CovarianceRegularized-v2 single-seed minimal experiment; EMA covariance, Cholesky diagonal-loading score proxy, tail-aligned loss. Path: `runs/{run_tag}/`.\n"
    p.write_text(text.rstrip() + "\n" + entry, encoding="utf-8")


def run_dry(args, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True); plot_dir = out_dir / "covariance_regularized_v2_plots"; plot_dir.mkdir(exist_ok=True)
    (out_dir / "command.txt").write_text("python " + " ".join(sys.argv) + "\n", encoding="utf-8")
    root = args.source_root; data = root / "runs" / "frontend100_crosscapture_stage1_2026-03-25" / "data"; joint = root / "runs" / "frontend100_joint_eval_stage1_2026-03-31"
    train_csv, labels, attack_csv = data / "id_source_100.csv", data / "no_labels.npy", joint / "data" / "attack_source_100.csv"
    cfg = cfg_grid(1)[0]; rel = f"{args.run_tag}/smoke_{cfg_label(cfg)}_seed{args.seed}"
    run_cmd(stage1_cmd(args, rel, train_csv, labels, None, cfg, True))
    run_dir = WORKTREE_ROOT / "runs" / rel; ckpt = Path(load_json(run_dir / "config.json")["checkpoint"])
    x_all = pd.read_csv(train_csv, header=None, nrows=384).to_numpy(float); x_fit, x_id = x_all[:256], x_all[256:384]
    x_attack = pd.read_csv(attack_csv, header=None, nrows=128).to_numpy(float)
    x_ood = x_id.copy()
    rmse_attack = v1.score_attack(ckpt, x_attack, out_dir / "smoke_attack_rmse.npy")
    sid_old, sood_old, satt_old, _ = v1.score_oldbest(ckpt, run_dir, x_id, x_ood, x_attack, rmse_attack, out_dir / "smoke_old", 128)
    sid_m, sood_m, satt_m, _, cal_meta, h_cal, maha_meta = score_maha_diagload(ckpt, x_fit, x_id, x_ood, x_attack, out_dir / "smoke_maha", 128, cfg["alpha_scale"])
    diag = v2_diag("smoke_covreg_v2", cfg, run_dir, ckpt, h_cal, cal_meta, maha_meta)
    pd.DataFrame([diag]).to_csv(out_dir / "covariance_regularized_v2_diagnostics.csv", index=False)
    plt.figure(figsize=(6,4)); plt.scatter([np.mean(sood_old > np.quantile(sid_old, .99))], [np.mean(satt_old > np.quantile(sid_old, .99))], label="oldbest"); plt.scatter([np.mean(sood_m > np.quantile(sid_m, .99))], [np.mean(satt_m > np.quantile(sid_m, .99))], label="diagload")
    plt.xlabel("tiny alarm"); plt.ylabel("tiny detection"); plt.title("Cov-reg v2 smoke scorer check"); plt.grid(alpha=.25); plt.legend(); plt.tight_layout(); plt.savefig(plot_dir / "smoke_tradeoff.png", dpi=160); plt.close()
    lines = ["# Local Smoke Test Summary", "", "- Backend `transformer_covariance_regularized_v2` completed tiny training.", "- EMA covariance, Cholesky solve, diagonal loading, tail/neg/floor losses executed.", "- No explicit inverse is used in training proxy or offline diagload scorer.", f"- Smoke config: {cfg}.", f"- Cholesky failures mean: {diag.get('train_cholesky_failures')} / total {diag.get('train_cholesky_total')}.", f"- NaN/Inf events: {diag.get('train_naninf_events')}."]
    (out_dir / "local_smoketest_summary.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    manifest = {"stage":"frontend100_covariance_regularized_v2_smoketest", "generated_at":datetime.now().isoformat(timespec="seconds"), "run_tag":args.run_tag, "dry_run":True, "backend":"transformer_covariance_regularized_v2", "config":cfg, "smoke_run_dir":str(run_dir), "outputs":{"summary":str(out_dir / "local_smoketest_summary.md"), "plot":str(plot_dir / "smoke_tradeoff.png")}}
    (out_dir / "config.json").write_text(json.dumps(clean(manifest), indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[done] cov-reg v2 smoke output: {out_dir}", flush=True)


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    ap = argparse.ArgumentParser(description="Transformer-CovarianceRegularized-v2 single-seed minimal experiment.")
    ap.add_argument("--run-tag", default=f"frontend100_covariance_regularized_v2_{today}")
    ap.add_argument("--source-root", type=Path, default=WORKTREE_ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master")
    ap.add_argument("--seed", type=int, default=42); ap.add_argument("--max-ae", type=int, default=10); ap.add_argument("--fm-grace", type=int, default=2000); ap.add_argument("--ad-grace", type=int, default=6000)
    ap.add_argument("--train-samples", type=int, default=8000); ap.add_argument("--id-eval-samples", type=int, default=5000); ap.add_argument("--learning-rate", type=float, default=0.1); ap.add_argument("--hidden-ratio", type=float, default=0.75)
    ap.add_argument("--latent-margin", type=float, default=5.0); ap.add_argument("--latent-lambda", type=float, default=0.5); ap.add_argument("--latent-warmup-steps", type=int, default=1000); ap.add_argument("--latent-pooling", default="mean"); ap.add_argument("--latent-covreg-buffer-size", type=int, default=64)
    ap.add_argument("--scan-points", type=int, default=901); ap.add_argument("--calibration-budget", type=int, default=5000); ap.add_argument("--calibration-target", type=float, default=0.01); ap.add_argument("--batch-size", type=int, default=1024); ap.add_argument("--config-limit", type=int, default=4)
    ap.add_argument("--force-retrain", action="store_true"); ap.add_argument("--dry-run", action="store_true"); args = ap.parse_args()
    out_dir = WORKTREE_ROOT / "runs" / args.run_tag
    if args.dry_run:
        run_dry(args, out_dir); return
    out_dir.mkdir(parents=True, exist_ok=True); plot_dir = out_dir / "covariance_regularized_v2_plots"; plot_dir.mkdir(exist_ok=True); cache = out_dir / "cache_scores"; cache.mkdir(exist_ok=True)
    (out_dir / "command.txt").write_text("python " + " ".join(sys.argv) + "\n", encoding="utf-8")
    root = args.source_root; data = root / "runs" / "frontend100_crosscapture_stage1_2026-03-25" / "data"; joint1 = root / "runs" / "frontend100_joint_eval_stage1_2026-03-31"; joint2 = root / "runs" / "frontend100_joint_eval_stage2_2026-04-01"
    stage2 = load_json(joint2 / "attack_manifest_stage2.json"); idx = resc.build_stage2_indices(stage2); high_idx, mixed_idx = idx["high"], idx["mixed"]
    train_csv, labels, ood_csv, attack_csv = data / "id_source_100.csv", data / "no_labels.npy", data / "ood_benign_source_100.csv", joint1 / "data" / "attack_source_100.csv"
    x_all = pd.read_csv(train_csv, header=None, nrows=args.train_samples + args.id_eval_samples).to_numpy(float); x_fit, x_id = x_all[:args.train_samples], x_all[args.train_samples:args.train_samples+args.id_eval_samples]
    x_ood = pd.read_csv(ood_csv, header=None).to_numpy(float); x_attack = pd.read_csv(attack_csv, header=None).to_numpy(float)
    rows: List[Dict] = reference_rows(); diagnostics, covreg_runs = [], []
    for cfg in cfg_grid(args.config_limit):
        label = "covariance_regularized_v2_" + cfg_label(cfg); rel = f"{args.run_tag}/{label}_seed{args.seed}"; run_dir = WORKTREE_ROOT / "runs" / rel
        run_cmd(stage1_cmd(args, rel, train_csv, labels, ood_csv, cfg, False)); ckpt = Path(load_json(run_dir / "config.json")["checkpoint"])
        rmse_attack = v1.score_attack(ckpt, x_attack, cache / f"{label}_attack_rmse.npy")
        old = v1.score_oldbest(ckpt, run_dir, x_id, x_ood, x_attack, rmse_attack, cache / (label + "_old"), args.batch_size)
        maha = score_maha_diagload(ckpt, x_fit, x_id, x_ood, x_attack, cache / (label + "_maha"), args.batch_size, cfg["alpha_scale"])
        add_rows(rows, label, OLD_BEST_SCORER, "old_best_log_weighted_hybrid", old[:3], high_idx, mixed_idx, args, cfg, run_dir, ckpt)
        maha_scorer = f"ledoitwolf_diagload_f{tag_float(cfg['alpha_scale'])}"
        add_rows(rows, label, maha_scorer, "covariance_aware_diagload", maha[:3], high_idx, mixed_idx, args, cfg, run_dir, ckpt)
        sid_m, sood_m, satt_m, fit_meta, cal_meta, h_cal, maha_meta = maha
        diag = v2_diag(label, cfg, run_dir, ckpt, h_cal, cal_meta, maha_meta); diagnostics.append(diag)
        covreg_runs.append({"label":label, "config":cfg, "run_dir":str(run_dir), "checkpoint":str(ckpt), "oldbest_meta":clean(old[3]), "maha_meta":clean(maha_meta)})
    res = pd.DataFrame(rows).sort_values(["detector_family", "object_label", "scorer_label", "policy_name"]).reset_index(drop=True)
    res.to_csv(out_dir / "covariance_regularized_v2_results.csv", index=False); res.to_csv(out_dir / "results.csv", index=False)
    diag_df = pd.DataFrame(diagnostics); diag_df.to_csv(out_dir / "covariance_regularized_v2_diagnostics.csv", index=False)
    show = ["object_label", "detector_family", "scorer_label", "policy_name", "threshold", "ood_alarm_ratio_eval", "attack_detection_high_purity", "attack_detection_boundary", "roc_auc_attack_high_vs_ood_eval", "selection_feasible"]
    (out_dir / "covariance_regularized_v2_results.md").write_text(md_table(res[show]), encoding="utf-8"); (out_dir / "results.md").write_text(md_table(res[show]), encoding="utf-8")
    plot_fixed(res, plot_dir / "fixed_tradeoff_main.png"); plot_diag(diag_df, plot_dir)
    plot_fixed(res[res["object_label"].astype(str).str.contains("covariance_regularized_v1|covariance_regularized_v2|covreg_best|latent_swap", regex=True, na=False)], plot_dir / "v1_vs_v2_fixed_compare.png")
    plot_fixed(res[res["object_label"].astype(str).str.contains("covreg_best__ledoitwolf_diagload|covariance_regularized_v2", regex=True, na=False)], plot_dir / "v1_rescoring_vs_v2_fixed_compare.png")
    def gv(obj_sub, scorer_sub, pol, col):
        s = res[res["object_label"].astype(str).str.contains(obj_sub, regex=False) & res["scorer_label"].astype(str).str.contains(scorer_sub, regex=False) & (res["policy_name"] == pol) & (res["selection_feasible"])]
        return float("nan") if s.empty else float(s.iloc[0][col])
    f_v2 = res[(res["detector_family"] == "covariance_regularized_v2") & (res["policy_name"] == "fixed_id_q99") & (res["selection_feasible"])].copy()
    f_v2["utility"] = f_v2["attack_detection_high_purity"].astype(float) - f_v2["ood_alarm_ratio_eval"].astype(float)
    best = None if f_v2.empty else f_v2.sort_values(["utility", "attack_detection_high_purity"], ascending=[False, False]).iloc[0]
    no_obj = "latent_swap_spike_mix_no_compact__log_weighted_z_rmse0.5_cos1.0_old"; v1_old = "covariance_regularized_v1_covreg_vm0p2_vx2p0_lv0p5_lc0p05__log_weighted_z_rmse0.5_cos1.0"; v1_fix = "covreg_best__ledoitwolf_diagload_f0p2"; tail = "transformer_tailreg__default_score"; da = "da__default_score"
    lines = ["# Transformer-CovarianceRegularized-v2 Summary", "", "## Setup", "- Mainline: original-frontend 100D + stronger OOD.", f"- Seed: {args.seed}; single-seed mechanism validation.", f"- Negative recipe locked: `{NEGATIVE_RECIPE}` (swap=0.5, spike=0.5).", f"- Latent main loss fixed: margin={args.latent_margin}, lambda_margin={args.latent_lambda}, warmup_steps={args.latent_warmup_steps}.", "- v2 mechanism: EMA benign covariance buffer, full covariance diagonal loading, Cholesky-solve Mahalanobis score proxy, benign tail penalty, negative push-out, weak variance floor.", "- No torch.inverse / explicit inverse in training proxy; Cholesky jitter fallback is recorded.", "", "## Required answers"]
    if best is not None:
        lines.append(f"- Best v2 fixed row by det-alarm utility: `{best['object_label']}` / `{best['scorer_label']}` alarm={float(best['ood_alarm_ratio_eval']):.4f}, det={float(best['attack_detection_high_purity']):.4f}.")
        lines.append(f"- no_compact old-best fixed: alarm={gv(no_obj, 'log_weighted', 'fixed_id_q99', 'ood_alarm_ratio_eval'):.4f}, det={gv(no_obj, 'log_weighted', 'fixed_id_q99', 'attack_detection_high_purity'):.4f}.")
        lines.append(f"- covreg_v1 best old-best fixed: alarm={gv(v1_old, 'log_weighted', 'fixed_id_q99', 'ood_alarm_ratio_eval'):.4f}, det={gv(v1_old, 'log_weighted', 'fixed_id_q99', 'attack_detection_high_purity'):.4f}.")
        lines.append(f"- covreg_v1 + diagload_f0p2 fixed: alarm={gv(v1_fix, 'diagload_f0p2', 'fixed_id_q99', 'ood_alarm_ratio_eval'):.4f}, det={gv(v1_fix, 'diagload_f0p2', 'fixed_id_q99', 'attack_detection_high_purity'):.4f}.")
        lines.append(f"- transformer_tailreg fixed: alarm={gv(tail, 'default_score', 'fixed_id_q99', 'ood_alarm_ratio_eval'):.4f}, det={gv(tail, 'default_score', 'fixed_id_q99', 'attack_detection_high_purity'):.4f}; dA fixed: alarm={gv(da, 'default_score', 'fixed_id_q99', 'ood_alarm_ratio_eval'):.4f}, det={gv(da, 'default_score', 'fixed_id_q99', 'attack_detection_high_purity'):.4f}.")
    lines += ["", "## Diagnostics", md_table(diag_df[["object_label", "alpha_scale", "lambda_tail", "train_tail_hit_rate", "train_neg_violation_rate", "train_cholesky_failures", "train_cholesky_total", "train_diag_condition_proxy", "offline_diagload_floor_hit_ratio", "collapse_dims"]]), "", "## Decision", "- Use the fixed rows and diagnostics above to decide whether v2 has enough single-seed signal for a multi-seed follow-up."]
    summary = "\n".join(lines) + "\n"
    (out_dir / "covariance_regularized_v2_summary.md").write_text(summary, encoding="utf-8"); (out_dir / "summary.md").write_text(summary, encoding="utf-8")
    manifest = {"stage":"frontend100_covariance_regularized_v2", "generated_at":datetime.now().isoformat(timespec="seconds"), "run_tag":args.run_tag, "seed":args.seed, "source_root":str(root), "backend":"transformer_covariance_regularized_v2", "negative_recipe":NEGATIVE_RECIPE, "latent_main_loss":{"margin":args.latent_margin,"lambda_margin":args.latent_lambda,"warmup_steps":args.latent_warmup_steps,"pooling":args.latent_pooling}, "covreg_v2_mechanism":{"ema_covariance":True,"diagonal_loading":"alpha_scale * median(diag(Sigma_ema))","score_proxy":"Cholesky solve, no explicit inverse","tau_ref":"running mean + k*std","weak_var_floor":True}, "configs":cfg_grid(args.config_limit), "scorers":[OLD_BEST_SCORER,"ledoitwolf_diagload_f{alpha_scale}"], "policy_set":["fixed_id_q99","naive_calibrated_budget5000_target1pct","det_floor_50pct_min_alarm"], "data_sources":{"train_csv":str(train_csv),"ood_csv":str(ood_csv),"attack_csv":str(attack_csv),"stage2_manifest":str(joint2 / "attack_manifest_stage2.json")}, "covreg_runs":covreg_runs, "outputs":{"results_csv":str(out_dir / "covariance_regularized_v2_results.csv"),"results_md":str(out_dir / "covariance_regularized_v2_results.md"),"summary_md":str(out_dir / "covariance_regularized_v2_summary.md"),"diagnostics_csv":str(out_dir / "covariance_regularized_v2_diagnostics.csv"),"plots_dir":str(plot_dir)}}
    (out_dir / "covariance_regularized_v2_config_manifest.json").write_text(json.dumps(clean(manifest), indent=2, ensure_ascii=False), encoding="utf-8"); (out_dir / "config.json").write_text(json.dumps(clean(manifest), indent=2, ensure_ascii=False), encoding="utf-8")
    append_map(args.run_tag)
    print(f"[done] cov-reg v2 experiment output: {out_dir}", flush=True)


if __name__ == "__main__":
    main()

