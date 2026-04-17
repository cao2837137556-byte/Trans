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

import KitNET as kit
import frontend100_latent_scorer_benchmark as lsb
import frontend100_negative_recipe_rescoring as resc
import frontend100_score_postprocessing as spp

NEGATIVE_RECIPE = "latent_swap_spike_mix"
PRIMARY_SCORER = "log_weighted_z_rmse0.5_cos1.0"
MAHA_SCORER = "mahalanobis_ledoitwolf"


def load_json(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


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
    return resc.md_table(df)


def tag_float(x: float) -> str:
    return str(float(x)).replace(".", "p")


def cfg_grid(limit: int) -> List[Dict]:
    grid = [
        {"var_min": 0.2, "var_max": 1.5, "lambda_var": 0.1, "lambda_corr": 0.01},
        {"var_min": 0.2, "var_max": 1.5, "lambda_var": 0.5, "lambda_corr": 0.05},
        {"var_min": 0.2, "var_max": 2.0, "lambda_var": 0.1, "lambda_corr": 0.01},
        {"var_min": 0.2, "var_max": 2.0, "lambda_var": 0.5, "lambda_corr": 0.05},
    ]
    return grid[: int(limit)]


def cfg_label(cfg: Dict) -> str:
    return f"covreg_vm{tag_float(cfg['var_min'])}_vx{tag_float(cfg['var_max'])}_lv{tag_float(cfg['lambda_var'])}_lc{tag_float(cfg['lambda_corr'])}"


def run_cmd(cmd: List[str]) -> None:
    print("[run] " + " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=str(WORKTREE_ROOT))


def score_attack(checkpoint: Path, x: np.ndarray, out_npy: Path) -> np.ndarray:
    if out_npy.exists():
        return np.load(out_npy).astype(np.float64)
    model = kit.KitNET.load_checkpoint(checkpoint)
    scores = np.zeros(len(x), dtype=np.float64)
    for i in range(len(x)):
        if i > 0 and i % 2000 == 0:
            print(f"  attack scoring {checkpoint.name}: {i}/{len(x)}", flush=True)
        scores[i] = model.process(x[i])
    np.save(out_npy, scores)
    return scores


def stage1_cmd(args, rel_tag: str, train_csv: Path, train_labels: Path, ood_csv: Path | None, cfg: Dict, dry: bool) -> List[str]:
    cmd = [
        sys.executable, str(REPO_DIR / "ood" / "stage1_probe.py"), "--run-tag", rel_tag,
        "--train-csv", str(train_csv), "--train-labels", str(train_labels),
        "--max-ae", str(args.max_ae), "--fm-grace", "64" if dry else str(args.fm_grace),
        "--ad-grace", "192" if dry else str(args.ad_grace),
        "--train-samples", "256" if dry else str(args.train_samples),
        "--id-eval-samples", "128" if dry else str(args.id_eval_samples),
        "--learning-rate", str(args.learning_rate), "--hidden-ratio", str(args.hidden_ratio),
        "--seed", str(args.seed), "--detector-backend", "transformer_covariance_regularized_v1",
        "--latent-margin", str(args.latent_margin), "--latent-lambda", str(args.latent_lambda),
        "--latent-contrastive-mode", "covreg_v1", "--latent-pooling", str(args.latent_pooling),
        "--latent-warmup-steps", "64" if dry else str(args.latent_warmup_steps),
        "--latent-neg-prob-swap", "0.5", "--latent-neg-prob-permute", "0.0",
        "--latent-neg-prob-spike", "0.5", "--latent-neg-prob-replace", "0.0",
        "--latent-lambda-var", str(cfg["lambda_var"]), "--latent-lambda-corr", str(cfg["lambda_corr"]),
        "--latent-var-min", str(cfg["var_min"]), "--latent-var-max", str(cfg["var_max"]),
        "--latent-covreg-buffer-size", str(args.latent_covreg_buffer_size),
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

def block_layernorm(h: np.ndarray, rows: List[Dict] | None) -> np.ndarray:
    h = np.asarray(h, dtype=np.float64)
    if h.ndim != 2 or h.shape[0] == 0:
        return h
    if not rows:
        mu = np.mean(h, axis=1, keepdims=True)
        sig = np.sqrt(np.var(h, axis=1, keepdims=True) + 1e-5)
        return (h - mu) / sig
    out, off = [], 0
    for r in rows:
        d = int(r.get("latent_dim", 0))
        b = h[:, off : off + d]
        off += d
        if d <= 0 or b.shape[1] != d:
            continue
        mu = np.mean(b, axis=1, keepdims=True)
        sig = np.sqrt(np.var(b, axis=1, keepdims=True) + 1e-5)
        out.append((b - mu) / sig)
    return np.concatenate(out, axis=1) if out else block_layernorm(h, None)


def geom_diag(label: str, h_cal: np.ndarray, cal_meta: Dict, cfg: Dict, train_diag: Dict) -> Dict:
    h = block_layernorm(h_cal, (cal_meta or {}).get("detector_rows", []))
    var = np.var(h, axis=0)
    q = np.quantile(var, [0.01, 0.05, 0.5, 0.95, 0.99])
    hz = (h - np.mean(h, axis=0, keepdims=True)) / np.sqrt(np.maximum(np.var(h, axis=0, keepdims=True), 1e-8))
    corr = (hz.T @ hz) / max(1, h.shape[0])
    corr = np.nan_to_num(corr, nan=0.0, posinf=0.0, neginf=0.0)
    off = corr[~np.eye(corr.shape[0], dtype=bool)]
    vmin, vmax = float(cfg["var_min"]), float(cfg["var_max"])
    finite = np.isfinite(h)
    return {
        "object_label": label,
        "diag_source": "ID benign calibration latent, per-detector block layernorm",
        "lambda_var": float(cfg["lambda_var"]),
        "lambda_corr": float(cfg["lambda_corr"]),
        "var_min_target": vmin,
        "var_max_target": vmax,
        "latent_dim": int(h.shape[1]),
        "samples": int(h.shape[0]),
        "var_mean": float(np.mean(var)),
        "var_std": float(np.std(var)),
        "var_min_observed": float(np.min(var)),
        "var_p01": float(q[0]),
        "var_p05": float(q[1]),
        "var_p50": float(q[2]),
        "var_p95": float(q[3]),
        "var_p99": float(q[4]),
        "var_max_observed": float(np.max(var)),
        "var_inrange_ratio": float(np.mean((var >= vmin) & (var <= vmax))),
        "var_below_min_ratio": float(np.mean(var < vmin)),
        "var_above_max_ratio": float(np.mean(var > vmax)),
        "collapse_dims": int(np.sum(var < max(1e-12, vmin * 0.05))),
        "runaway_dims": int(np.sum(var > vmax * 5.0)),
        "corr_offdiag_abs_mean": float(np.mean(np.abs(off))) if off.size else 0.0,
        "corr_offdiag_sq_mean": float(np.mean(off * off)) if off.size else 0.0,
        "nan_count": int(np.sum(~finite)),
        "inf_count": int(np.sum(np.isinf(h))),
        "train_covreg_naninf_events_total": train_diag.get("latent_covreg_naninf_events_mean"),
        "train_var_hinge_loss_mean": train_diag.get("latent_var_hinge_loss_mean"),
        "train_corr_loss_mean": train_diag.get("latent_corr_loss_mean"),
        "train_var_inrange_mean": train_diag.get("latent_var_inrange_ratio_mean"),
        "train_corr_offdiag_sq_mean": train_diag.get("latent_corr_offdiag_sq_mean"),
    }


def score_oldbest(checkpoint: Path, run_dir: Path, x_id: np.ndarray, x_ood: np.ndarray, x_attack: np.ndarray, rmse_attack: np.ndarray, cache_prefix: Path, batch_size: int):
    files = [cache_prefix.with_name(cache_prefix.name + suffix) for suffix in ["_old_id.npy", "_old_ood.npy", "_old_attack.npy", "_old_meta.json"]]
    if all(p.exists() for p in files):
        return np.load(files[0]), np.load(files[1]), np.load(files[2]), load_json(files[3])
    model = kit.KitNET.load_checkpoint(checkpoint)
    if (run_dir / "id_scores.npy").exists():
        rmse_id = np.load(run_dir / "id_scores.npy").astype(np.float64)
    else:
        rmse_id = np.asarray([model.process(x) for x in x_id], dtype=np.float64)
    try:
        metrics = load_json(run_dir / "metrics.json")
        rmse_ood = np.load(resc.pick_ood_score_file(run_dir, metrics)).astype(np.float64)
    except Exception:
        rmse_ood = np.asarray([model.process(x) for x in x_ood], dtype=np.float64)
    _, _, _, cos_id, cos_ood, cos_attack, latent_meta = resc.compute_latent_center_distance_scores(model=model, x_id=x_id, x_ood=x_ood, x_attack=x_attack, batch_size=batch_size)
    versions, stats = spp.make_score_versions(rmse_id, rmse_ood, rmse_attack, cos_id, cos_ood, cos_attack)
    sid, sood, satt = versions[PRIMARY_SCORER]
    meta = {"score_version": PRIMARY_SCORER, "stats_source": "ID benign calibration split only", "score_stats": stats.get(PRIMARY_SCORER, {}), "latent_meta": clean(latent_meta)}
    np.save(files[0], sid); np.save(files[1], sood); np.save(files[2], satt)
    files[3].write_text(json.dumps(clean(meta), indent=2, ensure_ascii=False), encoding="utf-8")
    return sid, sood, satt, meta


def score_maha(checkpoint: Path, x_fit: np.ndarray, x_id: np.ndarray, x_ood: np.ndarray, x_attack: np.ndarray, cache_prefix: Path, batch_size: int):
    files = [cache_prefix.with_name(cache_prefix.name + suffix) for suffix in ["_maha_id.npy", "_maha_ood.npy", "_maha_attack.npy", "_hcal.npy", "_maha_meta.json"]]
    if all(p.exists() for p in files):
        meta = load_json(files[4])
        return np.load(files[0]), np.load(files[1]), np.load(files[2]), meta.get("fit_meta", {}), meta.get("cal_meta", {}), np.load(files[3])
    model = kit.KitNET.load_checkpoint(checkpoint)
    h_fit, fit_meta = lsb.extract_global_latent(model=model, x=x_fit, batch_size=batch_size, negative=False)
    h_cal, cal_meta = lsb.extract_global_latent(model=model, x=x_id, batch_size=batch_size, negative=False)
    h_ood, ood_meta = lsb.extract_global_latent(model=model, x=x_ood, batch_size=batch_size, negative=False)
    h_attack, attack_meta = lsb.extract_global_latent(model=model, x=x_attack, batch_size=batch_size, negative=False)
    lw = LedoitWolf().fit(np.asarray(h_fit, dtype=np.float64))
    sid = lsb.mahalanobis_distance(h_cal, lw.location_, lw.precision_)
    sood = lsb.mahalanobis_distance(h_ood, lw.location_, lw.precision_)
    satt = lsb.mahalanobis_distance(h_attack, lw.location_, lw.precision_)
    meta = {"score_version": MAHA_SCORER, "estimator": "sklearn.covariance.LedoitWolf", "fit_source": "ID benign training split only", "fit_samples": int(h_fit.shape[0]), "latent_dim": int(h_fit.shape[1]), "fit_meta": clean(fit_meta), "cal_meta": clean(cal_meta), "ood_meta": clean(ood_meta), "attack_meta": clean(attack_meta)}
    np.save(files[0], sid); np.save(files[1], sood); np.save(files[2], satt); np.save(files[3], h_cal)
    files[4].write_text(json.dumps(clean(meta), indent=2, ensure_ascii=False), encoding="utf-8")
    return sid, sood, satt, fit_meta, cal_meta, h_cal


def add_rows(rows: List[Dict], label: str, scorer: str, family: str, scores, high_idx, mixed_idx, args, cfg: Dict, run_dir: Path, ckpt: Path) -> None:
    before = len(rows)
    rows.extend(lsb.build_score_rows(object_label=f"{label}__{scorer}", detector_family="covariance_regularized_v1", scorer_label=scorer, scorer_family=family, id_scores=scores[0], ood_scores=scores[1], attack_scores=scores[2], high_idx=high_idx, mixed_idx=mixed_idx, scan_points=args.scan_points, calibration_budget=args.calibration_budget, calibration_target=args.calibration_target))
    for r in rows[before:]:
        r.update({"source_mode": "trained_now", "variant": cfg_label(cfg), "var_min": cfg["var_min"], "var_max": cfg["var_max"], "lambda_var": cfg["lambda_var"], "lambda_corr": cfg["lambda_corr"], "run_dir": str(run_dir), "checkpoint": str(ckpt)})

def reference_rows(prior_manifest: Dict, high_idx: np.ndarray, mixed_idx: np.ndarray, args) -> List[Dict]:
    cmap = {str(c["candidate_label"]): c for c in prior_manifest["candidates"]}
    rows: List[Dict] = []
    bench = WORKTREE_ROOT / "runs" / "frontend100_latent_scorer_benchmark_2026-04-06" / "latent_scorer_benchmark_results.csv"
    if bench.exists():
        df = pd.read_csv(bench)
        keep = ["latent_swap_spike_mix_no_compact__log_weighted_z_rmse0.5_cos1.0_old", "latent_swap_spike_mix_no_compact__mahalanobis_ledoitwolf"]
        rows.extend(df[df["object_label"].isin(keep)].to_dict("records"))
    for key in ["transformer", "transformer_tailreg", "da"]:
        rr, _ = lsb.load_default_reference_rows(candidate_entry=cmap[key], scorer_label="default_score", source_note="official default score reference", calibration_budget=args.calibration_budget, calibration_target=args.calibration_target, scan_points=args.scan_points, high_idx=high_idx, mixed_idx=mixed_idx)
        rows.extend(rr)
    for r in rows:
        r.setdefault("source_mode", "reuse_reference"); r.setdefault("variant", "reference")
    return rows


def plot_fixed(results: pd.DataFrame, out: Path) -> None:
    fixed = results[(results["policy_name"] == "fixed_id_q99") & (results["selection_feasible"])].copy()
    colors = {"default_score": "#444444", PRIMARY_SCORER: "#d62728", PRIMARY_SCORER + "_old": "#d62728", MAHA_SCORER: "#1f77b4"}
    marks = {"default_score": "s", PRIMARY_SCORER: "o", PRIMARY_SCORER + "_old": "o", MAHA_SCORER: "P"}
    plt.figure(figsize=(10.5, 6.8))
    for _, r in fixed.iterrows():
        s = str(r["scorer_label"]); label = str(r["object_label"]).replace("covariance_regularized_v1_", "covreg_").replace("latent_swap_spike_mix_no_compact__", "no_compact__")
        plt.scatter([float(r["ood_alarm_ratio_eval"])], [float(r["attack_detection_high_purity"])], color=colors.get(s, "#777777"), marker=marks.get(s, "o"), s=90)
        if "covreg" in label or "no_compact" in label or "tailreg" in label or "da__" in label:
            plt.text(float(r["ood_alarm_ratio_eval"]) + 0.004, float(r["attack_detection_high_purity"]) + 0.006, f"{label}:{s}", fontsize=7.2)
    plt.xlabel("OOD benign alarm ratio (eval split, fixed q99)"); plt.ylabel("High-purity attack detection")
    plt.title("Covariance-Regularized v1 fixed trade-off"); plt.grid(alpha=0.25); plt.tight_layout(); plt.savefig(out, dpi=180); plt.close()


def plot_bar(results: pd.DataFrame, out: Path) -> None:
    fixed = results[(results["policy_name"] == "fixed_id_q99") & (results["selection_feasible"])].copy()
    fixed = fixed[fixed["object_label"].str.contains("covariance_regularized_v1|latent_swap_spike_mix_no_compact", regex=True) & fixed["scorer_label"].isin([PRIMARY_SCORER, PRIMARY_SCORER + "_old", MAHA_SCORER])].copy()
    labels = fixed["object_label"].astype(str).str.replace("covariance_regularized_v1_", "covreg_", regex=False).str.replace("latent_swap_spike_mix_no_compact__", "no_compact__", regex=False).tolist()
    x = np.arange(len(fixed)); plt.figure(figsize=(max(10.0, len(fixed) * 0.65), 5.6))
    plt.bar(x - 0.18, fixed["ood_alarm_ratio_eval"].to_numpy(float), width=0.36, label="OOD alarm")
    plt.bar(x + 0.18, fixed["attack_detection_high_purity"].to_numpy(float), width=0.36, label="attack detection")
    plt.xticks(x, labels, rotation=25, ha="right"); plt.ylabel("ratio"); plt.title("Baseline latent vs covariance-regularized latent")
    plt.grid(axis="y", alpha=0.25); plt.legend(); plt.tight_layout(); plt.savefig(out, dpi=180); plt.close()


def plot_diag(diag: pd.DataFrame, plot_dir: Path) -> None:
    labels = diag["object_label"].astype(str).str.replace("covariance_regularized_v1_", "covreg_", regex=False).tolist(); x = np.arange(len(diag))
    p05, p50, p95 = diag["var_p05"].to_numpy(float), diag["var_p50"].to_numpy(float), diag["var_p95"].to_numpy(float)
    plt.figure(figsize=(9.6, 5.3)); plt.errorbar(x, p50, yerr=[p50 - p05, p95 - p50], fmt="o", capsize=4)
    plt.axhline(float(diag["var_min_target"].iloc[0]), color="red", linestyle="--", label="var_min")
    plt.xticks(x, labels, rotation=25, ha="right"); plt.ylabel("benign latent variance, p50 with p05-p95"); plt.title("Benign variance distribution after cov-reg")
    plt.grid(axis="y", alpha=0.25); plt.legend(); plt.tight_layout(); plt.savefig(plot_dir / "benign_variance_distribution.png", dpi=180); plt.close()
    plt.figure(figsize=(9.6, 5.3)); plt.bar(x - 0.18, diag["corr_offdiag_abs_mean"].to_numpy(float), width=0.36, label="abs mean"); plt.bar(x + 0.18, diag["corr_offdiag_sq_mean"].to_numpy(float), width=0.36, label="sq mean")
    plt.xticks(x, labels, rotation=25, ha="right"); plt.ylabel("off-diagonal correlation"); plt.title("Off-diagonal decorrelation diagnostics")
    plt.grid(axis="y", alpha=0.25); plt.legend(); plt.tight_layout(); plt.savefig(plot_dir / "offdiag_correlation_stats.png", dpi=180); plt.close()


def plot_maha(packs: Dict[str, Dict], out: Path) -> None:
    n = len(packs); fig, axes = plt.subplots(n, 1, figsize=(9.5, max(3.0, 3.0 * n)))
    if n == 1: axes = [axes]
    for ax, (label, p) in zip(axes, packs.items()):
        ax.hist(p["id"], bins=70, density=True, alpha=0.34, label="ID benign"); ax.hist(p["ood_eval"], bins=70, density=True, alpha=0.34, label="OOD eval"); ax.hist(p["attack_high"], bins=70, density=True, alpha=0.34, label="attack_high")
        ax.axvline(p["fixed_thr"], color="black", linestyle="--", linewidth=1.0, label="fixed q99"); ax.set_title(label); ax.grid(alpha=0.22)
    axes[0].legend(ncol=4, fontsize=8); fig.suptitle("Mahalanobis score distributions"); fig.tight_layout(rect=[0, 0, 1, 0.97]); fig.savefig(out, dpi=180); plt.close(fig)


def append_map(run_tag: str) -> None:
    p = WORKTREE_ROOT / "runs" / "mainline_docs" / "mainline_experiment_map.md"
    if not p.exists(): return
    text = p.read_text(encoding="utf-8")
    if f"`{run_tag}`" in text: return
    entry = f"\n- `{run_tag}`: Transformer-CovarianceRegularized-v1 single-seed minimal experiment; two-sided variance hinge + off-diagonal decorrelation, old-best and Mahalanobis scoring. Path: `runs/{run_tag}/`.\n"
    p.write_text(text.rstrip() + "\n" + entry, encoding="utf-8")

def run_dry(args, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True); plot_dir = out_dir / "covariance_regularized_v1_plots"; plot_dir.mkdir(exist_ok=True)
    (out_dir / "command.txt").write_text("python " + " ".join(sys.argv) + "\n", encoding="utf-8")
    root = args.source_root; data = root / "runs" / "frontend100_crosscapture_stage1_2026-03-25" / "data"; joint = root / "runs" / "frontend100_joint_eval_stage1_2026-03-31"
    train_csv, labels, ood_csv, attack_csv = data / "id_source_100.csv", data / "no_labels.npy", data / "ood_benign_source_100.csv", joint / "data" / "attack_source_100.csv"
    cfg = cfg_grid(1)[0]; rel = f"{args.run_tag}/smoke_{cfg_label(cfg)}_seed{args.seed}"
    run_cmd(stage1_cmd(args, rel, train_csv, labels, None, cfg, True))
    run_dir = WORKTREE_ROOT / "runs" / rel; ckpt = Path(load_json(run_dir / "config.json")["checkpoint"])
    x_all = pd.read_csv(train_csv, header=None, nrows=384).to_numpy(float); x_fit, x_id = x_all[:256], x_all[256:384]
    x_ood = pd.read_csv(ood_csv, header=None, nrows=128).to_numpy(float); x_attack = pd.read_csv(attack_csv, header=None, nrows=128).to_numpy(float)
    rmse_attack = score_attack(ckpt, x_attack, out_dir / "smoke_attack_rmse.npy")
    sid_old, sood_old, satt_old, _ = score_oldbest(ckpt, run_dir, x_id, x_ood, x_attack, rmse_attack, out_dir / "smoke", 128)
    sid_m, sood_m, satt_m, _, cal_meta, h_cal = score_maha(ckpt, x_fit, x_id, x_ood, x_attack, out_dir / "smoke", 128)
    train_diag = load_json(run_dir / "metrics.json").get("latent_contrastive_diagnostics", {})
    diag = geom_diag("smoke_covreg", h_cal, cal_meta, cfg, train_diag); pd.DataFrame([diag]).to_csv(out_dir / "covariance_regularized_v1_diagnostics.csv", index=False)
    plt.figure(figsize=(6,4)); plt.scatter([np.mean(sood_old > np.quantile(sid_old, .99))], [np.mean(satt_old > np.quantile(sid_old, .99))], label="oldbest"); plt.scatter([np.mean(sood_m > np.quantile(sid_m, .99))], [np.mean(satt_m > np.quantile(sid_m, .99))], label="maha")
    plt.xlabel("tiny OOD alarm"); plt.ylabel("tiny attack detection"); plt.title("Cov-reg smoke scorer check"); plt.grid(alpha=.25); plt.legend(); plt.tight_layout(); plt.savefig(plot_dir / "smoke_tradeoff.png", dpi=160); plt.close()
    lines = ["# Local Smoke Test Summary", "", "- Backend `transformer_covariance_regularized_v1` completed tiny training.", "- Two-sided variance hinge and off-diagonal correlation paths executed.", "- Old-best scorer and Mahalanobis-LedoitWolf scorer both executed on tiny ID/OOD/attack slices.", f"- Smoke config: {cfg}.", f"- Smoke oldbest fixed threshold: {float(np.quantile(sid_old, .99)):.6f}.", f"- Smoke Mahalanobis fixed threshold: {float(np.quantile(sid_m, .99)):.6f}.", f"- Variance in-range ratio: {diag['var_inrange_ratio']:.6f}.", f"- NaN count={diag['nan_count']}, Inf count={diag['inf_count']}."]
    (out_dir / "local_smoketest_summary.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    manifest = {"stage":"frontend100_covariance_regularized_v1_smoketest", "generated_at":datetime.now().isoformat(timespec="seconds"), "run_tag":args.run_tag, "dry_run":True, "backend":"transformer_covariance_regularized_v1", "config":cfg, "smoke_run_dir":str(run_dir), "outputs":{"summary":str(out_dir / "local_smoketest_summary.md"), "plot":str(plot_dir / "smoke_tradeoff.png")}}
    (out_dir / "config.json").write_text(json.dumps(clean(manifest), indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[done] cov-reg smoke output: {out_dir}", flush=True)


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    ap = argparse.ArgumentParser(description="Transformer-CovarianceRegularized-v1 single-seed minimal experiment.")
    ap.add_argument("--run-tag", default=f"frontend100_covariance_regularized_v1_{today}"); ap.add_argument("--source-root", type=Path, default=WORKTREE_ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master")
    ap.add_argument("--seed", type=int, default=42); ap.add_argument("--max-ae", type=int, default=10); ap.add_argument("--fm-grace", type=int, default=2000); ap.add_argument("--ad-grace", type=int, default=6000)
    ap.add_argument("--train-samples", type=int, default=8000); ap.add_argument("--id-eval-samples", type=int, default=5000); ap.add_argument("--learning-rate", type=float, default=0.1); ap.add_argument("--hidden-ratio", type=float, default=0.75)
    ap.add_argument("--latent-margin", type=float, default=5.0); ap.add_argument("--latent-lambda", type=float, default=0.5); ap.add_argument("--latent-warmup-steps", type=int, default=1000); ap.add_argument("--latent-pooling", default="mean"); ap.add_argument("--latent-covreg-buffer-size", type=int, default=64)
    ap.add_argument("--scan-points", type=int, default=901); ap.add_argument("--calibration-budget", type=int, default=5000); ap.add_argument("--calibration-target", type=float, default=0.01); ap.add_argument("--batch-size", type=int, default=1024); ap.add_argument("--config-limit", type=int, default=4)
    ap.add_argument("--force-retrain", action="store_true"); ap.add_argument("--dry-run", action="store_true"); args = ap.parse_args()
    out_dir = WORKTREE_ROOT / "runs" / args.run_tag
    if args.dry_run: run_dry(args, out_dir); return
    out_dir.mkdir(parents=True, exist_ok=True); plot_dir = out_dir / "covariance_regularized_v1_plots"; plot_dir.mkdir(exist_ok=True); cache = out_dir / "cache_scores"; cache.mkdir(exist_ok=True)
    (out_dir / "command.txt").write_text("python " + " ".join(sys.argv) + "\n", encoding="utf-8")
    root = args.source_root; data = root / "runs" / "frontend100_crosscapture_stage1_2026-03-25" / "data"; joint1 = root / "runs" / "frontend100_joint_eval_stage1_2026-03-31"; joint2 = root / "runs" / "frontend100_joint_eval_stage2_2026-04-01"
    stage2 = load_json(joint2 / "attack_manifest_stage2.json"); idx = resc.build_stage2_indices(stage2); high_idx, mixed_idx = idx["high"], idx["mixed"]
    train_csv, labels, ood_csv, attack_csv = data / "id_source_100.csv", data / "no_labels.npy", data / "ood_benign_source_100.csv", joint1 / "data" / "attack_source_100.csv"
    x_all = pd.read_csv(train_csv, header=None, nrows=args.train_samples + args.id_eval_samples).to_numpy(float); x_fit, x_id = x_all[:args.train_samples], x_all[args.train_samples:args.train_samples+args.id_eval_samples]
    x_ood = pd.read_csv(ood_csv, header=None).to_numpy(float); x_attack = pd.read_csv(attack_csv, header=None).to_numpy(float)
    prior = load_json(WORKTREE_ROOT / "runs" / "frontend100_negative_recipe_rescoring_2026-04-05" / "negative_recipe_rescoring_manifest.json")
    rows = reference_rows(prior, high_idx, mixed_idx, args)
    diagnostics, covreg_runs, packs = [], [], {}
    for cfg in cfg_grid(args.config_limit):
        label = "covariance_regularized_v1_" + cfg_label(cfg); rel = f"{args.run_tag}/{label}_seed{args.seed}"; run_dir = WORKTREE_ROOT / "runs" / rel
        run_cmd(stage1_cmd(args, rel, train_csv, labels, ood_csv, cfg, False)); ckpt = Path(load_json(run_dir / "config.json")["checkpoint"])
        rmse_attack = score_attack(ckpt, x_attack, cache / f"{label}_attack_rmse.npy")
        old = score_oldbest(ckpt, run_dir, x_id, x_ood, x_attack, rmse_attack, cache / label, args.batch_size)
        maha = score_maha(ckpt, x_fit, x_id, x_ood, x_attack, cache / label, args.batch_size)
        add_rows(rows, label, PRIMARY_SCORER, "old_best_log_weighted_hybrid", old[:3], high_idx, mixed_idx, args, cfg, run_dir, ckpt)
        add_rows(rows, label, MAHA_SCORER, "covariance_aware", maha[:3], high_idx, mixed_idx, args, cfg, run_dir, ckpt)
        sid_m, sood_m, satt_m, fit_meta, cal_meta, h_cal = maha; train_diag = load_json(run_dir / "metrics.json").get("latent_contrastive_diagnostics", {})
        diag = geom_diag(label, h_cal, cal_meta, cfg, train_diag); diag.update({"run_dir":str(run_dir), "checkpoint":str(ckpt)}); diagnostics.append(diag)
        covreg_runs.append({"label":label, "config":cfg, "run_dir":str(run_dir), "checkpoint":str(ckpt), "oldbest_meta":clean(old[3]), "mahalanobis_fit_meta":clean(fit_meta), "mahalanobis_cal_meta":clean(cal_meta)})
        packs[label + "__" + MAHA_SCORER] = {"id":sid_m, "ood_eval":sood_m[args.calibration_budget:] if len(sood_m)>args.calibration_budget else sood_m, "attack_high":satt_m[high_idx], "fixed_thr":float(np.quantile(sid_m, .99))}
    res = pd.DataFrame(rows); res = res.sort_values(["detector_family", "object_label", "scorer_label", "policy_name"]).reset_index(drop=True); res.to_csv(out_dir / "covariance_regularized_v1_results.csv", index=False); res.to_csv(out_dir / "results.csv", index=False)
    diag_df = pd.DataFrame(diagnostics).sort_values(["lambda_var", "lambda_corr", "var_max_target"]).reset_index(drop=True); diag_df.to_csv(out_dir / "covariance_regularized_v1_diagnostics.csv", index=False)
    show = ["object_label", "detector_family", "scorer_label", "policy_name", "threshold", "ood_alarm_ratio_eval", "attack_detection_high_purity", "attack_detection_boundary", "roc_auc_attack_high_vs_ood_eval", "selection_feasible"]
    (out_dir / "covariance_regularized_v1_results.md").write_text(md_table(res[show]), encoding="utf-8"); (out_dir / "results.md").write_text(md_table(res[show]), encoding="utf-8")
    plot_fixed(res, plot_dir / "fixed_tradeoff_main.png"); plot_bar(res, plot_dir / "baseline_vs_covreg_fixed_compare.png"); plot_diag(diag_df, plot_dir); plot_maha(packs, plot_dir / "mahalanobis_score_distribution_covreg.png")
    def gv(obj, scorer, pol, col):
        s = res[(res["object_label"]==obj) & (res["scorer_label"]==scorer) & (res["policy_name"]==pol) & (res["selection_feasible"])]
        return float("nan") if s.empty else float(s.iloc[0][col])
    f_old = res[(res["detector_family"]=="covariance_regularized_v1") & (res["scorer_label"]==PRIMARY_SCORER) & (res["policy_name"]=="fixed_id_q99") & (res["selection_feasible"])].copy(); f_old["utility"] = f_old["attack_detection_high_purity"] - f_old["ood_alarm_ratio_eval"]
    f_maha = res[(res["detector_family"]=="covariance_regularized_v1") & (res["scorer_label"]==MAHA_SCORER) & (res["policy_name"]=="fixed_id_q99") & (res["selection_feasible"])].copy(); f_maha["utility"] = f_maha["attack_detection_high_purity"] - f_maha["ood_alarm_ratio_eval"]
    best_old = None if f_old.empty else f_old.sort_values(["utility", "attack_detection_high_purity"], ascending=[False, False]).iloc[0]
    best_maha = None if f_maha.empty else f_maha.sort_values(["utility", "attack_detection_high_purity"], ascending=[False, False]).iloc[0]
    no_old, no_maha, tail, da = "latent_swap_spike_mix_no_compact__log_weighted_z_rmse0.5_cos1.0_old", "latent_swap_spike_mix_no_compact__mahalanobis_ledoitwolf", "transformer_tailreg__default_score", "da__default_score"
    lines = ["# Transformer-CovarianceRegularized-v1 Summary", "", "## Setup", "- Mainline: original-frontend 100D + stronger OOD.", f"- Seed: {args.seed} (single-seed mechanism validation).", f"- Negative recipe locked: `{NEGATIVE_RECIPE}` (swap=0.5, spike=0.5, permute=0, replace=0).", f"- Latent main loss fixed: margin={args.latent_margin}, lambda_margin={args.latent_lambda}, warmup_steps={args.latent_warmup_steps}.", "- Added training regularizer: two-sided variance hinge + lightweight off-diagonal correlation penalty on benign latent rolling buffer.", "- No log-variance minimization, no MAE, no prototype/double-center training, no compactness.", "- Evaluation scorers: old best `log_weighted_z_rmse0.5_cos1.0` and `mahalanobis_ledoitwolf`.", "", "## Required answers"]
    if best_old is not None:
        lines += ["1. Fixed old-best scorer vs latent no-compact:", f"- no_compact: alarm={gv(no_old, 'log_weighted_z_rmse0.5_cos1.0_old', 'fixed_id_q99', 'ood_alarm_ratio_eval'):.4f}, det={gv(no_old, 'log_weighted_z_rmse0.5_cos1.0_old', 'fixed_id_q99', 'attack_detection_high_purity'):.4f}; best cov-reg (`{best_old['object_label']}`): alarm={float(best_old['ood_alarm_ratio_eval']):.4f}, det={float(best_old['attack_detection_high_purity']):.4f}.", "2. Fixed old-best scorer vs tailreg and dA:", f"- tailreg: alarm={gv(tail, 'default_score', 'fixed_id_q99', 'ood_alarm_ratio_eval'):.4f}, det={gv(tail, 'default_score', 'fixed_id_q99', 'attack_detection_high_purity'):.4f}; dA: alarm={gv(da, 'default_score', 'fixed_id_q99', 'ood_alarm_ratio_eval'):.4f}, det={gv(da, 'default_score', 'fixed_id_q99', 'attack_detection_high_purity'):.4f}; best cov-reg delta vs dA: alarm={float(best_old['ood_alarm_ratio_eval']) - gv(da, 'default_score', 'fixed_id_q99', 'ood_alarm_ratio_eval'):+.4f}, det={float(best_old['attack_detection_high_purity']) - gv(da, 'default_score', 'fixed_id_q99', 'attack_detection_high_purity'):+.4f}."]
    if best_maha is not None:
        lines += ["3. Mahalanobis geometry check:", f"- no_compact Mahalanobis: alarm={gv(no_maha, 'mahalanobis_ledoitwolf', 'fixed_id_q99', 'ood_alarm_ratio_eval'):.4f}, det={gv(no_maha, 'mahalanobis_ledoitwolf', 'fixed_id_q99', 'attack_detection_high_purity'):.4f}; best cov-reg Mahalanobis (`{best_maha['object_label']}`): alarm={float(best_maha['ood_alarm_ratio_eval']):.4f}, det={float(best_maha['attack_detection_high_purity']):.4f}."]
    lines += ["4. Collapse/runaway diagnostics:", f"- min var_inrange_ratio={float(diag_df['var_inrange_ratio'].min()):.4f}, max collapse_dims={int(diag_df['collapse_dims'].max())}, max runaway_dims={int(diag_df['runaway_dims'].max())}, max NaN={int(diag_df['nan_count'].max())}, max Inf={int(diag_df['inf_count'].max())}.", "5. Off-diagonal decorrelation:", f"- corr_offdiag_sq_mean range={float(diag_df['corr_offdiag_sq_mean'].min()):.6f} to {float(diag_df['corr_offdiag_sq_mean'].max()):.6f}; see diagnostics CSV.", "", "## Diagnostics table", md_table(diag_df[["object_label", "lambda_var", "lambda_corr", "var_min_target", "var_max_target", "var_inrange_ratio", "var_p50", "var_max_observed", "corr_offdiag_sq_mean", "collapse_dims", "runaway_dims", "nan_count", "inf_count"]]), "", "## Decision", "- Use the fixed and Mahalanobis rows above to decide whether this single-seed mechanism warrants a multi-seed follow-up."]
    summary = "\n".join(lines) + "\n"; (out_dir / "covariance_regularized_v1_summary.md").write_text(summary, encoding="utf-8"); (out_dir / "summary.md").write_text(summary, encoding="utf-8")
    manifest = {"stage":"frontend100_covariance_regularized_v1", "generated_at":datetime.now().isoformat(timespec="seconds"), "run_tag":args.run_tag, "seed":args.seed, "source_root":str(root), "backend":"transformer_covariance_regularized_v1", "negative_recipe":NEGATIVE_RECIPE, "latent_main_loss":{"margin":args.latent_margin, "lambda_margin":args.latent_lambda, "warmup_steps":args.latent_warmup_steps, "pooling":args.latent_pooling}, "covreg_mechanism":{"loss_var_hinge":"mean(relu(var_i-var_max))+mean(relu(var_min-var_i))", "loss_corr":"mean(off_diagonal(correlation_matrix)^2)", "buffer_size":args.latent_covreg_buffer_size, "no_log_variance_minimization":True}, "configs":cfg_grid(args.config_limit), "scorers":[PRIMARY_SCORER, MAHA_SCORER], "policy_set":["fixed_id_q99", "naive_calibrated_budget5000_target1pct", "det_floor_50pct_min_alarm"], "calibration":{"budget":args.calibration_budget, "target_alarm":args.calibration_target, "scan_points":args.scan_points}, "data_sources":{"train_csv":str(train_csv), "ood_csv":str(ood_csv), "attack_csv":str(attack_csv), "stage2_manifest":str(joint2 / "attack_manifest_stage2.json")}, "covreg_runs":covreg_runs, "outputs":{"results_csv":str(out_dir / "covariance_regularized_v1_results.csv"), "results_md":str(out_dir / "covariance_regularized_v1_results.md"), "summary_md":str(out_dir / "covariance_regularized_v1_summary.md"), "diagnostics_csv":str(out_dir / "covariance_regularized_v1_diagnostics.csv"), "plots_dir":str(plot_dir)}}
    (out_dir / "covariance_regularized_v1_config_manifest.json").write_text(json.dumps(clean(manifest), indent=2, ensure_ascii=False), encoding="utf-8"); (out_dir / "config.json").write_text(json.dumps(clean(manifest), indent=2, ensure_ascii=False), encoding="utf-8")
    append_map(args.run_tag); print(f"[done] cov-reg experiment output: {out_dir}", flush=True)

if __name__ == "__main__":
    main()

