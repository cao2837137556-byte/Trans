from __future__ import annotations
import argparse, json, sys
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

EPS = 1e-12
DEFAULT_F_VALUES = [0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.2]


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


def load_json(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def md_table(df: pd.DataFrame) -> str:
    return resc.md_table(df)


def tag_float(x: float) -> str:
    return str(float(x)).replace(".", "p")


def parse_f_values(text: str) -> List[float]:
    if not text:
        return DEFAULT_F_VALUES
    return [float(x.strip()) for x in text.split(",") if x.strip()]


def load_or_extract_latents(args, cache_dir: Path, x_fit, x_id, x_ood, x_attack) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "h_fit": cache_dir / "no_compact_latent_h_fit.npy",
        "h_id": cache_dir / "no_compact_latent_h_id.npy",
        "h_ood": cache_dir / "no_compact_latent_h_ood.npy",
        "h_attack": cache_dir / "no_compact_latent_h_attack.npy",
        "meta": cache_dir / "no_compact_latent_latent_meta.json",
    }
    if all(p.exists() for p in files.values()):
        return (
            np.load(files["h_fit"]).astype(np.float64),
            np.load(files["h_id"]).astype(np.float64),
            np.load(files["h_ood"]).astype(np.float64),
            np.load(files["h_attack"]).astype(np.float64),
            load_json(files["meta"]),
        )
    manifest = load_json(WORKTREE_ROOT / "runs" / "frontend100_negative_recipe_rescoring_2026-04-05" / "negative_recipe_rescoring_manifest.json")
    cmap = {c["candidate_label"]: c for c in manifest["candidates"]}
    ckpt = Path(cmap["latent_swap_spike_mix"]["checkpoint"])
    model = kit.KitNET.load_checkpoint(ckpt)
    h_fit, fit_meta = lsb.extract_global_latent(model, x_fit, args.batch_size, negative=False)
    h_id, id_meta = lsb.extract_global_latent(model, x_id, args.batch_size, negative=False)
    h_ood, ood_meta = lsb.extract_global_latent(model, x_ood, args.batch_size, negative=False)
    h_attack, attack_meta = lsb.extract_global_latent(model, x_attack, args.batch_size, negative=False)
    np.save(files["h_fit"], h_fit); np.save(files["h_id"], h_id); np.save(files["h_ood"], h_ood); np.save(files["h_attack"], h_attack)
    meta = {"checkpoint": str(ckpt), "fit_meta": clean(fit_meta), "id_meta": clean(id_meta), "ood_meta": clean(ood_meta), "attack_meta": clean(attack_meta)}
    files["meta"].write_text(json.dumps(clean(meta), indent=2, ensure_ascii=False), encoding="utf-8")
    return h_fit.astype(np.float64), h_id.astype(np.float64), h_ood.astype(np.float64), h_attack.astype(np.float64), meta


def cholesky_diagload_scores(x: np.ndarray, mu: np.ndarray, sigma: np.ndarray, f: float, return_contrib: bool = False):
    x = np.asarray(x, dtype=np.float64)
    mu = np.asarray(mu, dtype=np.float64).reshape(-1)
    sigma = np.asarray(sigma, dtype=np.float64)
    diag = np.clip(np.diag(sigma), EPS, None)
    diagload = float(f) * np.diag(diag)
    sigma_reg = sigma + diagload
    sigma_reg = 0.5 * (sigma_reg + sigma_reg.T)
    chol = None
    jitter_used = None
    for jitter in [1e-6, 1e-5, 1e-4]:
        try:
            chol = np.linalg.cholesky(sigma_reg + jitter * np.eye(sigma_reg.shape[0], dtype=np.float64))
            jitter_used = jitter
            break
        except np.linalg.LinAlgError:
            chol = None
    if chol is None:
        raise RuntimeError(f"Cholesky failed after jitter fallback for f={f}")
    delta = x - mu[None, :]
    y = np.linalg.solve(chol, delta.T)
    contrib = y * y
    score = np.sqrt(np.clip(np.sum(contrib, axis=0), 0.0, None))
    meta = {
        "f": float(f),
        "jitter": float(jitter_used),
        "diag_min": float(np.min(diag)),
        "diag_p01": float(np.quantile(diag, 0.01)),
        "diag_p05": float(np.quantile(diag, 0.05)),
        "diag_median": float(np.median(diag)),
        "diag_p95": float(np.quantile(diag, 0.95)),
        "diag_max": float(np.max(diag)),
        "diag_condition_proxy": float(np.max(diag) / max(np.min(diag), EPS)),
        "loading_trace_ratio": float(np.trace(diagload) / max(np.trace(sigma), EPS)),
    }
    if return_contrib:
        return score, contrib.T, meta
    return score, meta


def add_score_rows(rows: List[Dict], object_label: str, scorer_label: str, scorer_family: str, sid, sood, satt, high_idx, mixed_idx, args, extra: Dict | None = None) -> None:
    before = len(rows)
    rows.extend(lsb.build_score_rows(
        object_label=f"{object_label}__{scorer_label}",
        detector_family="latent_swap_spike_mix_no_compact",
        scorer_label=scorer_label,
        scorer_family=scorer_family,
        id_scores=sid,
        ood_scores=sood,
        attack_scores=satt,
        high_idx=high_idx,
        mixed_idx=mixed_idx,
        scan_points=args.scan_points,
        calibration_budget=args.calibration_budget,
        calibration_target=args.calibration_target,
    ))
    for r in rows[before:]:
        if extra:
            r.update(extra)


def load_reference_rows() -> List[Dict]:
    refs: List[Dict] = []
    covres = WORKTREE_ROOT / "runs" / "frontend100_covariance_regularized_v1_2026-04-07" / "covariance_regularized_v1_results.csv"
    if covres.exists():
        df = pd.read_csv(covres)
        keep = {
            "latent_swap_spike_mix_no_compact__log_weighted_z_rmse0.5_cos1.0_old",
            "transformer_tailreg__default_score",
            "da__default_score",
        }
        r = df[df["object_label"].isin(keep)].copy()
        r["source_mode"] = "reuse_reference"
        refs.extend(r.to_dict("records"))
    return refs


def contribution_summary(f: float, score_eval: np.ndarray, contrib_eval: np.ndarray, top_n: int = 200) -> Dict:
    if len(score_eval) == 0 or contrib_eval.size == 0:
        return {"f": float(f), "top_n": 0}
    n = int(min(top_n, len(score_eval)))
    top_idx = np.argsort(score_eval)[-n:]
    c = np.asarray(contrib_eval[top_idx], dtype=np.float64)
    total = np.maximum(np.sum(c, axis=1), EPS)
    shares = np.sort(c, axis=1)[:, ::-1] / total[:, None]
    return {
        "f": float(f),
        "top_n": n,
        "ood_eval_score_top_mean": float(np.mean(score_eval[top_idx])),
        "ood_eval_score_top_min": float(np.min(score_eval[top_idx])),
        "ood_eval_score_top_max": float(np.max(score_eval[top_idx])),
        "top1_contrib_share_mean": float(np.mean(shares[:, 0])),
        "top5_contrib_share_mean": float(np.mean(np.sum(shares[:, : min(5, shares.shape[1])], axis=1))),
        "top10_contrib_share_mean": float(np.mean(np.sum(shares[:, : min(10, shares.shape[1])], axis=1))),
    }


def plot_f_lines(fixed_table: pd.DataFrame, plot_dir: Path) -> None:
    sweep = fixed_table[fixed_table["is_sweep"]].sort_values("f")
    for col, ylabel, fname in [
        ("ood_alarm_ratio_eval", "fixed OOD benign alarm", "f_vs_alarm.png"),
        ("attack_detection_high_purity", "fixed high-purity attack detection", "f_vs_detection.png"),
    ]:
        plt.figure(figsize=(7.6, 5.0))
        plt.plot(sweep["f"], sweep[col], marker="o", linewidth=1.8)
        plt.axhline(0.1209 if "alarm" in col else 0.7896, color="black", linestyle="--", linewidth=1.0, label="dA fixed ref")
        if "alarm" in col:
            plt.axhline(0.15, color="red", linestyle=":", linewidth=1.0, label="alarm 0.15 target")
        else:
            plt.axhline(0.80, color="red", linestyle=":", linewidth=1.0, label="det 0.80 target")
        plt.xlabel("diagload f in Sigma + f*diag(Sigma)")
        plt.ylabel(ylabel)
        plt.title(ylabel + " vs diagload f")
        plt.grid(alpha=0.25); plt.legend(); plt.tight_layout(); plt.savefig(plot_dir / fname, dpi=180); plt.close()


def plot_tradeoff(results: pd.DataFrame, policy: str, out: Path, title: str) -> None:
    df = results[(results["policy_name"] == policy) & (results["selection_feasible"])].copy()
    plt.figure(figsize=(9.5, 6.2))
    for _, r in df.iterrows():
        obj = str(r["object_label"])
        scorer = str(r["scorer_label"])
        is_sweep = "diagload_f" in scorer or "mahalanobis_raw_cholesky" in scorer
        if is_sweep:
            color, marker, size = "#1f77b4", "o", 80
        elif "da__" in obj:
            color, marker, size = "#d62728", "s", 90
        elif "tailreg" in obj:
            color, marker, size = "#9467bd", "s", 80
        else:
            color, marker, size = "#2ca02c", "D", 80
        plt.scatter(float(r["ood_alarm_ratio_eval"]), float(r["attack_detection_high_purity"]), color=color, marker=marker, s=size)
        label = scorer.replace("mahalanobis_diagload_f", "f=").replace("mahalanobis_raw_cholesky", "raw").replace("log_weighted_z_rmse0.5_cos1.0_old", "old-best")
        if is_sweep or "da__" in obj or "tailreg" in obj or "old-best" in label:
            plt.text(float(r["ood_alarm_ratio_eval"]) + 0.004, float(r["attack_detection_high_purity"]) + 0.006, label, fontsize=7.5)
    plt.xlabel("OOD benign alarm ratio (eval split)")
    plt.ylabel("High-purity attack detection")
    plt.title(title)
    plt.grid(alpha=0.25); plt.tight_layout(); plt.savefig(out, dpi=180); plt.close()


def append_map(run_tag: str) -> None:
    p = WORKTREE_ROOT / "runs" / "master_experiment_map_v1.md"
    if not p.exists():
        return
    text = p.read_text(encoding="utf-8")
    if f"`{run_tag}`" in text:
        return
    entry = f"\n- `{run_tag}`: Offline no-compact latent Mahalanobis diagonal-loading sweep; no retraining. Path: `runs/{run_tag}/`.\n"
    p.write_text(text.rstrip() + "\n" + entry, encoding="utf-8")


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    ap = argparse.ArgumentParser(description="No-compact latent Mahalanobis diagload sweep, offline only.")
    ap.add_argument("--run-tag", default=f"frontend100_diagload_sweep_no_compact_{today}")
    ap.add_argument("--source-root", type=Path, default=WORKTREE_ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master")
    ap.add_argument("--f-values", default=",".join(str(x) for x in DEFAULT_F_VALUES))
    ap.add_argument("--scan-points", type=int, default=901)
    ap.add_argument("--calibration-budget", type=int, default=5000)
    ap.add_argument("--calibration-target", type=float, default=0.01)
    ap.add_argument("--batch-size", type=int, default=1024)
    ap.add_argument("--train-samples", type=int, default=8000)
    ap.add_argument("--id-eval-samples", type=int, default=5000)
    args = ap.parse_args()

    out = WORKTREE_ROOT / "runs" / args.run_tag
    out.mkdir(parents=True, exist_ok=True)
    plot_dir = out / "diagload_sweep_plots"
    plot_dir.mkdir(exist_ok=True)
    cache = out / "cache_latents"
    cache.mkdir(exist_ok=True)
    (out / "command.txt").write_text("python " + " ".join(sys.argv) + "\n", encoding="utf-8")

    # Reuse prior no-compact latent cache when present.
    prior_cache = WORKTREE_ROOT / "runs" / "frontend100_mahalanobis_rescue_2026-04-07" / "cache_latents"
    for name in ["no_compact_latent_h_fit.npy", "no_compact_latent_h_id.npy", "no_compact_latent_h_ood.npy", "no_compact_latent_h_attack.npy", "no_compact_latent_latent_meta.json"]:
        src = prior_cache / name
        dst = cache / name
        if src.exists() and not dst.exists():
            dst.write_bytes(src.read_bytes())

    root = args.source_root
    data = root / "runs" / "frontend100_crosscapture_stage1_2026-03-25" / "data"
    joint1 = root / "runs" / "frontend100_joint_eval_stage1_2026-03-31"
    joint2 = root / "runs" / "frontend100_joint_eval_stage2_2026-04-01"
    train_csv = data / "id_source_100.csv"
    ood_csv = data / "ood_benign_source_100.csv"
    attack_csv = joint1 / "data" / "attack_source_100.csv"
    stage2 = load_json(joint2 / "attack_manifest_stage2.json")
    idx = resc.build_stage2_indices(stage2)
    high_idx, mixed_idx = idx["high"], idx["mixed"]

    # Only used if cache is missing.
    x_all = pd.read_csv(train_csv, header=None, nrows=args.train_samples + args.id_eval_samples).to_numpy(float)
    x_fit_raw, x_id_raw = x_all[: args.train_samples], x_all[args.train_samples : args.train_samples + args.id_eval_samples]
    x_ood_raw = pd.read_csv(ood_csv, header=None).to_numpy(float)
    x_attack_raw = pd.read_csv(attack_csv, header=None).to_numpy(float)
    h_fit, h_id, h_ood, h_attack, latent_meta = load_or_extract_latents(args, cache, x_fit_raw, x_id_raw, x_ood_raw, x_attack_raw)

    lw = LedoitWolf().fit(np.asarray(h_fit, dtype=np.float64))
    mu = np.asarray(lw.location_, dtype=np.float64)
    sigma = np.asarray(lw.covariance_, dtype=np.float64)
    f_values = parse_f_values(args.f_values)

    rows: List[Dict] = load_reference_rows()
    diag_rows: List[Dict] = []
    contrib_rows: List[Dict] = []

    for f in [0.0] + f_values:
        scorer = "mahalanobis_raw_cholesky" if float(f) == 0.0 else f"mahalanobis_diagload_f{tag_float(f)}"
        sid, meta_id = cholesky_diagload_scores(h_id, mu, sigma, f, return_contrib=False)
        sood, meta_ood = cholesky_diagload_scores(h_ood, mu, sigma, f, return_contrib=False)
        satt, meta_att = cholesky_diagload_scores(h_attack, mu, sigma, f, return_contrib=False)
        add_score_rows(
            rows,
            "latent_swap_spike_mix_no_compact",
            scorer,
            "mahalanobis_diagload_sweep",
            sid,
            sood,
            satt,
            high_idx,
            mixed_idx,
            args,
            extra={"f": float(f), "source_mode": "offline_rescore", "diagload_definition": "Sigma + f*diag(Sigma)", "no_explicit_inverse": True, **{f"id_{k}": v for k, v in meta_id.items()}},
        )
        eval_scores = sood[args.calibration_budget:] if len(sood) > args.calibration_budget else sood
        _, contrib_eval, _ = cholesky_diagload_scores(h_ood[args.calibration_budget:] if len(h_ood) > args.calibration_budget else h_ood, mu, sigma, f, return_contrib=True)
        csum = contribution_summary(f, eval_scores, contrib_eval, top_n=200)
        csum.update({"scorer_label": scorer})
        contrib_rows.append(csum)
        diag_rows.append({"scorer_label": scorer, "f": float(f), **meta_id, **csum})

    res = pd.DataFrame(rows).sort_values(["detector_family", "object_label", "scorer_label", "policy_name"]).reset_index(drop=True)
    res.to_csv(out / "diagload_sweep_results.csv", index=False)
    res.to_csv(out / "results.csv", index=False)
    pd.DataFrame(diag_rows).to_csv(out / "diagload_sweep_diagnostics.csv", index=False)
    pd.DataFrame(contrib_rows).to_csv(out / "diagload_sweep_contribution_summary.csv", index=False)

    show = ["object_label", "detector_family", "scorer_label", "policy_name", "threshold", "ood_alarm_ratio_eval", "attack_detection_high_purity", "attack_detection_boundary", "roc_auc_attack_high_vs_ood_eval", "selection_feasible"]
    (out / "diagload_sweep_results.md").write_text(md_table(res[show]), encoding="utf-8")
    (out / "results.md").write_text(md_table(res[show]), encoding="utf-8")

    fixed = res[(res["policy_name"] == "fixed_id_q99") & (res["selection_feasible"])].copy()
    fixed["is_sweep"] = fixed["scorer_label"].astype(str).str.contains("diagload_f|raw_cholesky", regex=True)
    sweep_fixed = fixed[fixed["is_sweep"]].copy()
    plot_f_lines(sweep_fixed[sweep_fixed["scorer_label"] != "mahalanobis_raw_cholesky"], plot_dir)
    plot_tradeoff(res, "fixed_id_q99", plot_dir / "fixed_tradeoff_diagload_sweep.png", "No-compact latent: fixed trade-off diagload sweep")
    plot_tradeoff(res, "det_floor_50pct_min_alarm", plot_dir / "det50_tradeoff_diagload_sweep.png", "No-compact latent: det50 trade-off diagload sweep")

    def gv(obj_contains: str, scorer_contains: str, policy: str, col: str) -> float:
        s = res[res["object_label"].astype(str).str.contains(obj_contains, regex=False) & res["scorer_label"].astype(str).str.contains(scorer_contains, regex=False) & (res["policy_name"] == policy) & (res["selection_feasible"])]
        return float("nan") if s.empty else float(s.iloc[0][col])

    sweep_only = fixed[fixed["scorer_label"].astype(str).str.contains("diagload_f", regex=True)].copy()
    sweep_only["utility"] = sweep_only["attack_detection_high_purity"].astype(float) - sweep_only["ood_alarm_ratio_eval"].astype(float)
    best = None if sweep_only.empty else sweep_only.sort_values(["utility", "attack_detection_high_purity"], ascending=[False, False]).iloc[0]
    pass_a = sweep_only[(sweep_only["ood_alarm_ratio_eval"].astype(float) < 0.15) & (sweep_only["attack_detection_high_purity"].astype(float) > 0.80)]
    pass_b = sweep_only[(sweep_only["ood_alarm_ratio_eval"].astype(float).between(0.12, 0.15)) & (sweep_only["attack_detection_high_purity"].astype(float).between(0.78, 0.805))]
    near_alarm = sweep_only.iloc[(np.abs(sweep_only["ood_alarm_ratio_eval"].astype(float).to_numpy() - 0.13)).argmin()] if not sweep_only.empty else None
    beats_old = sweep_only[(sweep_only["ood_alarm_ratio_eval"].astype(float) < 0.1857) & (sweep_only["attack_detection_high_purity"].astype(float) > 0.8233)]

    lines = [
        "# No-Compact Latent Mahalanobis Diagload Sweep Summary",
        "",
        "## Setup",
        "- Offline rescoring only: no retraining and no checkpoint modification.",
        "- Object: `latent_swap_spike_mix_no_compact`.",
        "- Covariance estimator: `sklearn.covariance.LedoitWolf`, fitted on ID benign latent training split only.",
        "- Diagload definition: `Sigma_reg = Sigma + f * diag(Sigma)`.",
        "- Mahalanobis score computation: Cholesky solve with jitter fallback; no explicit matrix inverse.",
        f"- Swept f values: {f_values} plus raw f=0 reference.",
        "",
        "## Fixed anchors",
        f"- dA fixed: alarm={gv('da__default_score', 'default_score', 'fixed_id_q99', 'ood_alarm_ratio_eval'):.4f}, det={gv('da__default_score', 'default_score', 'fixed_id_q99', 'attack_detection_high_purity'):.4f}.",
        f"- transformer_tailreg fixed: alarm={gv('transformer_tailreg__default_score', 'default_score', 'fixed_id_q99', 'ood_alarm_ratio_eval'):.4f}, det={gv('transformer_tailreg__default_score', 'default_score', 'fixed_id_q99', 'attack_detection_high_purity'):.4f}.",
        f"- no_compact old-best fixed: alarm={gv('latent_swap_spike_mix_no_compact__log_weighted', 'log_weighted', 'fixed_id_q99', 'ood_alarm_ratio_eval'):.4f}, det={gv('latent_swap_spike_mix_no_compact__log_weighted', 'log_weighted', 'fixed_id_q99', 'attack_detection_high_purity'):.4f}.",
        f"- raw Mahalanobis fixed: alarm={gv('latent_swap_spike_mix_no_compact__mahalanobis_raw_cholesky', 'mahalanobis_raw_cholesky', 'fixed_id_q99', 'ood_alarm_ratio_eval'):.4f}, det={gv('latent_swap_spike_mix_no_compact__mahalanobis_raw_cholesky', 'mahalanobis_raw_cholesky', 'fixed_id_q99', 'attack_detection_high_purity'):.4f}.",
        "",
        "## Sweep decision",
    ]
    if best is not None:
        lines.append(f"- Best diagload row by det-alarm utility: `{best['scorer_label']}` fixed alarm={float(best['ood_alarm_ratio_eval']):.4f}, det={float(best['attack_detection_high_purity']):.4f}, AUC={float(best['roc_auc_attack_high_vs_ood_eval']):.4f}.")
    lines.append(f"- Situation A (alarm < 0.15 and det > 0.80): {'PASS' if not pass_a.empty else 'FAIL'}.")
    if not pass_a.empty:
        a = pass_a.sort_values(["ood_alarm_ratio_eval", "attack_detection_high_purity"], ascending=[True, False]).iloc[0]
        lines.append(f"  - Best A candidate: `{a['scorer_label']}` alarm={float(a['ood_alarm_ratio_eval']):.4f}, det={float(a['attack_detection_high_purity']):.4f}.")
    lines.append(f"- Situation B (alarm 0.12-0.15 and det about 0.78-0.80): {'PASS' if not pass_b.empty else 'FAIL'}.")
    if near_alarm is not None:
        lines.append(f"- Closest sweep point to alarm=0.13: `{near_alarm['scorer_label']}` alarm={float(near_alarm['ood_alarm_ratio_eval']):.4f}, det={float(near_alarm['attack_detection_high_purity']):.4f}.")
    lines.append(f"- Situation D (beats old-best alarm 0.1857 and det 0.8233): {'PASS' if not beats_old.empty else 'FAIL'}.")
    if not beats_old.empty:
        d = beats_old.sort_values(["ood_alarm_ratio_eval", "attack_detection_high_purity"], ascending=[True, False]).iloc[0]
        lines.append(f"  - Best D candidate: `{d['scorer_label']}` alarm={float(d['ood_alarm_ratio_eval']):.4f}, det={float(d['attack_detection_high_purity']):.4f}.")
    lines += [
        "",
        "## Required answer",
        "1. Is no-compact latent only missing a good diagload f? Judge from Situation A/B/D above.",
        "2. Optimal f is the best fixed utility row unless a stricter deployment threshold is selected.",
        "3. If all low-alarm points have detection below target, scorer-only diagload is insufficient and Step 2 is needed.",
        "",
        "## Fixed sweep table",
        md_table(sweep_only[["scorer_label", "f", "ood_alarm_ratio_eval", "attack_detection_high_purity", "roc_auc_attack_high_vs_ood_eval"]] if "f" in sweep_only.columns else sweep_only[["scorer_label", "ood_alarm_ratio_eval", "attack_detection_high_purity", "roc_auc_attack_high_vs_ood_eval"]]),
    ]
    summary = "\n".join(lines) + "\n"
    (out / "diagload_sweep_summary.md").write_text(summary, encoding="utf-8")
    (out / "summary.md").write_text(summary, encoding="utf-8")

    manifest = {
        "stage": "frontend100_diagload_sweep_no_compact",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_tag": args.run_tag,
        "no_training": True,
        "object": "latent_swap_spike_mix_no_compact",
        "estimator": "LedoitWolf fitted on ID benign latent training split only",
        "diagload_definition": "Sigma_reg = Sigma + f * diag(Sigma)",
        "score_compute": "Cholesky solve with jitter fallback; no explicit inverse",
        "f_values": f_values,
        "data_sources": {"train_csv": str(train_csv), "ood_csv": str(ood_csv), "attack_csv": str(attack_csv), "stage2_manifest": str(joint2 / "attack_manifest_stage2.json")},
        "latent_meta": clean(latent_meta),
        "outputs": {
            "results_csv": str(out / "diagload_sweep_results.csv"),
            "results_md": str(out / "diagload_sweep_results.md"),
            "summary_md": str(out / "diagload_sweep_summary.md"),
            "diagnostics_csv": str(out / "diagload_sweep_diagnostics.csv"),
            "contribution_summary_csv": str(out / "diagload_sweep_contribution_summary.csv"),
            "plots_dir": str(plot_dir),
        },
    }
    (out / "diagload_sweep_manifest.json").write_text(json.dumps(clean(manifest), indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "config.json").write_text(json.dumps(clean(manifest), indent=2, ensure_ascii=False), encoding="utf-8")
    append_map(args.run_tag)
    print(f"[done] diagload sweep output: {out}", flush=True)


if __name__ == "__main__":
    main()
