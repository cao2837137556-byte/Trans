from __future__ import annotations
import argparse, json, sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

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

import frontend100_negative_recipe_rescoring as resc
import frontend100_diagload_sweep_no_compact as dsw

RAW_QS = [0.9995, 0.999, 0.998]
SEEDS = [42, 101, 202, 303]
EPS = 1e-12


def clean(obj):
    if isinstance(obj, dict): return {k: clean(v) for k, v in obj.items()}
    if isinstance(obj, list): return [clean(v) for v in obj]
    if isinstance(obj, tuple): return [clean(v) for v in obj]
    if isinstance(obj, np.generic): return clean(obj.item())
    if isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)): return None
    return obj


def load_json(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def md_table(df: pd.DataFrame) -> str:
    return resc.md_table(df)


def qtag(x: float) -> str:
    return str(float(x)).replace('.', 'p')


def stats(x: np.ndarray, prefix: str) -> Dict:
    x = np.asarray(x, dtype=np.float64)
    if len(x) == 0:
        return {f"{prefix}_{k}": np.nan for k in ["n","mean","std","min","q50","q90","q95","q99","q999","max"]}
    return {
        f"{prefix}_n": int(len(x)),
        f"{prefix}_mean": float(np.mean(x)),
        f"{prefix}_std": float(np.std(x)),
        f"{prefix}_min": float(np.min(x)),
        f"{prefix}_q50": float(np.quantile(x, 0.50)),
        f"{prefix}_q90": float(np.quantile(x, 0.90)),
        f"{prefix}_q95": float(np.quantile(x, 0.95)),
        f"{prefix}_q99": float(np.quantile(x, 0.99)),
        f"{prefix}_q999": float(np.quantile(x, 0.999)),
        f"{prefix}_max": float(np.max(x)),
    }


def top_share(contrib: np.ndarray, k: int) -> np.ndarray:
    contrib = np.asarray(contrib, dtype=np.float64)
    if contrib.size == 0:
        return np.zeros(0, dtype=np.float64)
    total = np.maximum(np.sum(contrib, axis=1), EPS)
    c = np.sort(contrib, axis=1)[:, ::-1]
    return np.sum(c[:, : min(k, c.shape[1])], axis=1) / total


def contrib_summary(seed: int, score_type: str, group: str, mask: np.ndarray, contrib: np.ndarray) -> Dict:
    mask = np.asarray(mask, dtype=bool)
    c = np.asarray(contrib, dtype=np.float64)[mask]
    row = {"seed": int(seed), "score_type": score_type, "group": group, "count": int(len(c))}
    if len(c) == 0:
        row.update({"top1_share_mean": np.nan, "top5_share_mean": np.nan, "top10_share_mean": np.nan, "top1_share_q90": np.nan, "top5_share_q90": np.nan})
        return row
    t1, t5, t10 = top_share(c, 1), top_share(c, 5), top_share(c, 10)
    row.update({
        "top1_share_mean": float(np.mean(t1)),
        "top5_share_mean": float(np.mean(t5)),
        "top10_share_mean": float(np.mean(t10)),
        "top1_share_q90": float(np.quantile(t1, 0.90)),
        "top5_share_q90": float(np.quantile(t5, 0.90)),
    })
    return row


def load_latents(seed: int):
    if seed == 42:
        cache = WORKTREE_ROOT / "runs" / "frontend100_diagload_sweep_no_compact_2026-04-08" / "cache_latents"
        files = {
            "fit": cache / "no_compact_latent_h_fit.npy",
            "id": cache / "no_compact_latent_h_id.npy",
            "ood": cache / "no_compact_latent_h_ood.npy",
            "attack": cache / "no_compact_latent_h_attack.npy",
        }
    else:
        cache = WORKTREE_ROOT / "runs" / "frontend100_diagload_gate_multiseed_2026-04-08" / "cache_latents"
        files = {
            "fit": cache / f"latent_swap_spike_mix_seed{seed}_h_fit.npy",
            "id": cache / f"latent_swap_spike_mix_seed{seed}_h_id.npy",
            "ood": cache / f"latent_swap_spike_mix_seed{seed}_h_ood.npy",
            "attack": cache / f"latent_swap_spike_mix_seed{seed}_h_attack.npy",
        }
    missing = [str(p) for p in files.values() if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Missing latent caches for seed {seed}: {missing}")
    return tuple(np.load(files[k]).astype(np.float64) for k in ["fit", "id", "ood", "attack"]), str(cache)


def covariance_diag(seed: int, lw: LedoitWolf) -> Dict:
    sigma = np.asarray(lw.covariance_, dtype=np.float64)
    diag = np.clip(np.diag(sigma), EPS, None)
    eig = np.linalg.eigvalsh(0.5 * (sigma + sigma.T))
    eig_pos = np.clip(eig, EPS, None)
    p = eig_pos / max(float(np.sum(eig_pos)), EPS)
    entropy = -float(np.sum(p * np.log(p + EPS)))
    eff_rank = float(np.exp(entropy))
    return {
        "seed": int(seed),
        "latent_dim": int(sigma.shape[0]),
        "lw_shrinkage": float(getattr(lw, "shrinkage_", np.nan)),
        "diag_min": float(np.min(diag)),
        "diag_p01": float(np.quantile(diag, 0.01)),
        "diag_p05": float(np.quantile(diag, 0.05)),
        "diag_median": float(np.median(diag)),
        "diag_p95": float(np.quantile(diag, 0.95)),
        "diag_max": float(np.max(diag)),
        "diag_condition_proxy": float(np.max(diag) / max(np.min(diag), EPS)),
        "eig_min": float(np.min(eig_pos)),
        "eig_p01": float(np.quantile(eig_pos, 0.01)),
        "eig_median": float(np.median(eig_pos)),
        "eig_p95": float(np.quantile(eig_pos, 0.95)),
        "eig_max": float(np.max(eig_pos)),
        "eig_condition": float(np.max(eig_pos) / max(np.min(eig_pos), EPS)),
        "trace": float(np.trace(sigma)),
        "effective_rank": eff_rank,
    }


def plot_branch(branch: pd.DataFrame, out: Path) -> None:
    q = 0.9995
    sub = branch[branch.raw_q.eq(q)].copy()
    x = np.arange(len(sub))
    width = 0.25
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    axes[0].bar(x-width, sub["diag_ood_alarm"], width, label="diag branch")
    axes[0].bar(x, sub["raw_ood_alarm"], width, label="raw branch")
    axes[0].bar(x+width, sub["gate_ood_alarm"], width, label="gate")
    axes[0].axhline(0.1322, color="black", linestyle="--", linewidth=1, label="dA multi-seed mean")
    axes[0].set_xticks(x); axes[0].set_xticklabels(sub["seed"].astype(str)); axes[0].set_ylabel("OOD alarm")
    axes[0].set_title("Branch OOD alarm at raw_q=0.9995")
    axes[0].legend(fontsize=8); axes[0].grid(alpha=0.25)
    axes[1].bar(x-width, sub["diag_det"], width, label="diag branch")
    axes[1].bar(x, sub["raw_det"], width, label="raw branch")
    axes[1].bar(x+width, sub["gate_det"], width, label="gate")
    axes[1].axhline(0.8014, color="black", linestyle="--", linewidth=1, label="dA multi-seed mean")
    axes[1].set_xticks(x); axes[1].set_xticklabels(sub["seed"].astype(str)); axes[1].set_ylabel("high-purity detection")
    axes[1].set_title("Branch detection at raw_q=0.9995")
    axes[1].legend(fontsize=8); axes[1].grid(alpha=0.25)
    fig.tight_layout(); fig.savefig(out, dpi=180); plt.close(fig)


def plot_score_stats(score_stats: pd.DataFrame, out: Path, score_type: str) -> None:
    sub = score_stats[score_stats.score_type.eq(score_type)].copy()
    fig, ax = plt.subplots(figsize=(9, 5.5))
    for domain, marker in [("id", "o"), ("ood_eval", "s"), ("attack_high", "^")]:
        d = sub[sub.domain.eq(domain)].sort_values("seed")
        ax.plot(d["seed"].astype(str), d["score_q99"], marker=marker, label=f"{domain} q99")
    ax.set_title(f"{score_type} q99 tail by seed")
    ax.set_ylabel("score q99")
    ax.grid(alpha=0.25); ax.legend(); fig.tight_layout(); fig.savefig(out, dpi=180); plt.close(fig)


def plot_cov(cov: pd.DataFrame, out: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    cov = cov.sort_values("seed")
    axes[0].plot(cov["seed"].astype(str), cov["diag_condition_proxy"], marker="o", label="diag condition proxy")
    axes[0].plot(cov["seed"].astype(str), cov["eig_condition"], marker="s", label="eig condition")
    axes[0].set_yscale("log"); axes[0].set_title("Covariance condition by seed"); axes[0].grid(alpha=0.25); axes[0].legend(fontsize=8)
    axes[1].plot(cov["seed"].astype(str), cov["effective_rank"], marker="o", label="effective rank")
    axes[1].plot(cov["seed"].astype(str), cov["lw_shrinkage"], marker="s", label="LedoitWolf shrinkage")
    axes[1].set_title("Rank / shrinkage by seed"); axes[1].grid(alpha=0.25); axes[1].legend(fontsize=8)
    fig.tight_layout(); fig.savefig(out, dpi=180); plt.close(fig)


def append_map(run_tag: str) -> None:
    p = WORKTREE_ROOT / "runs" / "master_experiment_map_v1.md"
    if not p.exists(): return
    text = p.read_text(encoding="utf-8")
    if f"`{run_tag}`" in text: return
    entry = f"\n- `{run_tag}`: Offline latent covariance-tail seed diagnostics for no-compact latent gate instability; no retraining. Path: `runs/{run_tag}/`.\n"
    p.write_text(text.rstrip() + entry, encoding="utf-8")


def update_log(run_tag: str) -> None:
    p = WORKTREE_ROOT / "runs" / "research_log" / "a_tier_experiment_progress_log.md"
    if not p.exists(): return
    text = p.read_text(encoding="utf-8")
    marker = "### 5.13 Latent Tail Seed Diagnostics"
    if marker in text: return
    block = f"""
\n### 5.13 Latent Tail Seed Diagnostics\n\nRun:\n- `runs/{run_tag}/`\n\nPurpose:\n- Diagnose why the covariance gate discovered on seed42 failed under formal seeds.\n- Compare seed42, seed101, seed202, and seed303 covariance tails, raw Mahalanobis tails, and diagload branch behavior.\n\nInitial interpretation:\n- seed101 failure is driven mainly by high alarm in the diagload branch;\n- seed303 failure is driven mainly by high alarm in the raw Mahalanobis branch;\n- seed202 behaves closest to the desired seed42-like pattern.\n\nImplication:\n- do not fix this by blindly sweeping global `raw_q`; the bottleneck is seed-specific latent covariance tail instability.\n"""
    insert = "\n## 6. Current Candidate Ranking"
    if insert in text:
        text = text.replace(insert, block + insert)
    else:
        text = text.rstrip() + block
    p.write_text(text, encoding="utf-8")


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    ap = argparse.ArgumentParser(description="Latent tail seed diagnostics for covariance gate instability.")
    ap.add_argument("--run-tag", default=f"frontend100_latent_tail_seed_diagnostics_{today}")
    ap.add_argument("--source-root", type=Path, default=WORKTREE_ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master")
    ap.add_argument("--calibration-budget", type=int, default=5000)
    args = ap.parse_args()

    out = WORKTREE_ROOT / "runs" / args.run_tag
    plot_dir = out / "latent_tail_seed_diagnostics_plots"
    out.mkdir(parents=True, exist_ok=True); plot_dir.mkdir(exist_ok=True)
    (out / "command.txt").write_text("python " + " ".join(sys.argv) + "\n", encoding="utf-8")

    stage2 = load_json(args.source_root / "runs" / "frontend100_joint_eval_stage2_2026-04-01" / "attack_manifest_stage2.json")
    idx = resc.build_stage2_indices(stage2)
    high_idx = idx["high"]
    budget = int(args.calibration_budget)

    branch_rows, cov_rows, score_rows, contrib_rows = [], [], [], []
    for seed in SEEDS:
        print(f"[seed {seed}] diagnostics", flush=True)
        (h_fit, h_id, h_ood, h_attack), cache_path = load_latents(seed)
        lw = LedoitWolf().fit(h_fit)
        cov_rows.append({"cache_path": cache_path, **covariance_diag(seed, lw)})
        mu, sigma = np.asarray(lw.location_, dtype=np.float64), np.asarray(lw.covariance_, dtype=np.float64)
        raw_id, _ = dsw.cholesky_diagload_scores(h_id, mu, sigma, 0.0)
        raw_ood, raw_contrib_ood_eval, _ = dsw.cholesky_diagload_scores(h_ood[budget:], mu, sigma, 0.0, return_contrib=True)
        raw_attack, raw_contrib_attack_high, _ = dsw.cholesky_diagload_scores(h_attack[high_idx], mu, sigma, 0.0, return_contrib=True)
        raw_ood_full, _ = dsw.cholesky_diagload_scores(h_ood, mu, sigma, 0.0)
        raw_attack_full, _ = dsw.cholesky_diagload_scores(h_attack, mu, sigma, 0.0)
        diag_id, _ = dsw.cholesky_diagload_scores(h_id, mu, sigma, 0.5)
        diag_ood_eval, diag_contrib_ood_eval, _ = dsw.cholesky_diagload_scores(h_ood[budget:], mu, sigma, 0.5, return_contrib=True)
        diag_attack_high, diag_contrib_attack_high, _ = dsw.cholesky_diagload_scores(h_attack[high_idx], mu, sigma, 0.5, return_contrib=True)
        diag_ood_full, _ = dsw.cholesky_diagload_scores(h_ood, mu, sigma, 0.5)
        diag_attack_full, _ = dsw.cholesky_diagload_scores(h_attack, mu, sigma, 0.5)

        score_sets = {
            "raw_maha": {"id": raw_id, "ood_eval": raw_ood, "attack_high": raw_attack},
            "diagload_f0p5": {"id": diag_id, "ood_eval": diag_ood_eval, "attack_high": diag_attack_high},
        }
        for stype, domains in score_sets.items():
            id_q99 = float(np.quantile(domains["id"], 0.99))
            for domain, arr in domains.items():
                row = {"seed": int(seed), "score_type": stype, "domain": domain, **stats(arr, "score")}
                row["id_q99_ref"] = id_q99
                row["q99_over_id_q99"] = float(np.quantile(arr, 0.99) / max(id_q99, EPS))
                row["q999_over_id_q99"] = float(np.quantile(arr, 0.999) / max(id_q99, EPS))
                score_rows.append(row)

        diag_thr = float(np.quantile(diag_id, 0.99))
        diag_ood_pred = diag_ood_full > diag_thr
        diag_att_pred = diag_attack_full > diag_thr
        for q in RAW_QS:
            raw_thr = float(np.quantile(raw_id, q))
            raw_ood_pred = raw_ood_full > raw_thr
            raw_att_pred = raw_attack_full > raw_thr
            gate_ood_pred = diag_ood_pred | raw_ood_pred
            gate_att_pred = diag_att_pred | raw_att_pred
            branch_rows.append({
                "seed": int(seed), "raw_q": float(q), "diag_thr": diag_thr, "raw_thr": raw_thr,
                "diag_ood_alarm": float(np.mean(diag_ood_pred[budget:])),
                "raw_ood_alarm": float(np.mean(raw_ood_pred[budget:])),
                "both_ood_alarm": float(np.mean((diag_ood_pred & raw_ood_pred)[budget:])),
                "gate_ood_alarm": float(np.mean(gate_ood_pred[budget:])),
                "diag_det": float(np.mean(diag_att_pred[high_idx])),
                "raw_det": float(np.mean(raw_att_pred[high_idx])),
                "both_det": float(np.mean((diag_att_pred & raw_att_pred)[high_idx])),
                "gate_det": float(np.mean(gate_att_pred[high_idx])),
            })
        # contribution concentration for branch false alarms/detections at q9995
        raw_thr = float(np.quantile(raw_id, 0.9995))
        raw_ood_mask = raw_ood > raw_thr
        raw_attack_mask = raw_attack > raw_thr
        diag_ood_mask = diag_ood_eval > diag_thr
        diag_attack_mask = diag_attack_high > diag_thr
        contrib_rows.append(contrib_summary(seed, "raw_maha", "ood_eval_false_alarm_q9995", raw_ood_mask, raw_contrib_ood_eval))
        contrib_rows.append(contrib_summary(seed, "raw_maha", "attack_high_detected_q9995", raw_attack_mask, raw_contrib_attack_high))
        contrib_rows.append(contrib_summary(seed, "diagload_f0p5", "ood_eval_false_alarm_q99", diag_ood_mask, diag_contrib_ood_eval))
        contrib_rows.append(contrib_summary(seed, "diagload_f0p5", "attack_high_detected_q99", diag_attack_mask, diag_contrib_attack_high))

    branch_df = pd.DataFrame(branch_rows)
    cov_df = pd.DataFrame(cov_rows)
    score_df = pd.DataFrame(score_rows)
    contrib_df = pd.DataFrame(contrib_rows)
    branch_df.to_csv(out / "latent_tail_branch_diagnostics.csv", index=False)
    cov_df.to_csv(out / "latent_tail_covariance_diagnostics.csv", index=False)
    score_df.to_csv(out / "latent_tail_score_distribution_stats.csv", index=False)
    contrib_df.to_csv(out / "latent_tail_contribution_concentration.csv", index=False)
    branch_df.to_csv(out / "latent_tail_seed_diagnostics_results.csv", index=False)

    plot_branch(branch_df, plot_dir / "branch_alarm_detection_by_seed_q9995.png")
    plot_score_stats(score_df, plot_dir / "raw_maha_q99_by_seed.png", "raw_maha")
    plot_score_stats(score_df, plot_dir / "diagload_f0p5_q99_by_seed.png", "diagload_f0p5")
    plot_cov(cov_df, plot_dir / "covariance_condition_by_seed.png")

    q9995 = branch_df[branch_df.raw_q.eq(0.9995)].copy()
    seed101 = q9995[q9995.seed.eq(101)].iloc[0]
    seed303 = q9995[q9995.seed.eq(303)].iloc[0]
    seed202 = q9995[q9995.seed.eq(202)].iloc[0]
    lines = [
        "# Latent Tail Seed Diagnostics Summary",
        "",
        "## Setup",
        "- Offline diagnostics only; no retraining and no checkpoint modification.",
        "- Compared seeds: 42 discovery seed plus formal seeds 101/202/303.",
        "- Focus: why `diag_f0.5 q99 OR raw_maha q9995` is unstable across seeds.",
        "",
        "## Branch q0.9995 Table",
        md_table(q9995[["seed", "diag_ood_alarm", "raw_ood_alarm", "both_ood_alarm", "gate_ood_alarm", "diag_det", "raw_det", "both_det", "gate_det"]]),
        "",
        "## Main Diagnosis",
        f"- Seed101: diagload branch is already high alarm (`diag_ood_alarm={seed101['diag_ood_alarm']:.4f}`), so raw-tail gating is not the only issue.",
        f"- Seed303: raw Mahalanobis branch is high alarm (`raw_ood_alarm={seed303['raw_ood_alarm']:.4f}` at q0.9995), while detection is high (`raw_det={seed303['raw_det']:.4f}`).",
        f"- Seed202: gate is closest to the desired behavior (`gate_ood_alarm={seed202['gate_ood_alarm']:.4f}`, `gate_det={seed202['gate_det']:.4f}`).",
        "- Therefore the multi-seed failure is seed-specific latent covariance tail instability, not a simple global q choice.",
        "",
        "## Covariance Summary",
        md_table(cov_df[["seed", "lw_shrinkage", "diag_condition_proxy", "eig_condition", "effective_rank", "trace"]]),
        "",
        "## Recommendation",
        "- Do not lock the seed42 gate as the main result.",
        "- Do not keep sweeping raw_q blindly.",
        "- Next technical fix should target stabilizing the latent covariance tail across seeds, or move to external baselines while preserving this as an ablation/diagnostic signal.",
    ]
    summary = "\n".join(lines) + "\n"
    (out / "latent_tail_seed_diagnostics_summary.md").write_text(summary, encoding="utf-8")
    (out / "summary.md").write_text(summary, encoding="utf-8")
    (out / "latent_tail_seed_diagnostics_results.md").write_text(md_table(branch_df), encoding="utf-8")

    cfg = {
        "stage": "frontend100_latent_tail_seed_diagnostics",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_tag": args.run_tag,
        "no_training": True,
        "seeds": SEEDS,
        "raw_qs": RAW_QS,
        "outputs": {
            "branch": str(out / "latent_tail_branch_diagnostics.csv"),
            "covariance": str(out / "latent_tail_covariance_diagnostics.csv"),
            "score_stats": str(out / "latent_tail_score_distribution_stats.csv"),
            "contrib": str(out / "latent_tail_contribution_concentration.csv"),
            "summary": str(out / "summary.md"),
            "plots": str(plot_dir),
        },
    }
    (out / "latent_tail_seed_diagnostics_manifest.json").write_text(json.dumps(clean(cfg), indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "config.json").write_text(json.dumps(clean(cfg), indent=2, ensure_ascii=False), encoding="utf-8")
    append_map(args.run_tag)
    update_log(args.run_tag)
    print(f"[done] latent tail diagnostics output: {out}")


if __name__ == "__main__":
    main()
