
from __future__ import annotations

import argparse
import json
import sys
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
for path in [THIS_DIR, REPO_DIR]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import frontend100_diagload_sweep_no_compact as dsw
import frontend100_negative_recipe_rescoring as resc

BASE_CACHE = WORKTREE_ROOT / "runs" / "frontend100_diagload_gate_multiseed_2026-04-08" / "cache_latents"
FORMAL_SEEDS = [101, 202, 303]
RAW_QS = [0.9995, 0.999, 0.998]
BASE_F = 0.5


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


def tag_num(x: float) -> str:
    return str(float(x)).replace(".", "p")


def compute_auc(ood_eval: np.ndarray, attack_high: np.ndarray) -> float:
    return float(resc.compute_auc(ood_eval_scores=ood_eval, attack_high_scores=attack_high))


def eval_at_threshold(score_id, score_ood, score_attack, high_idx, mixed_idx, budget, threshold, policy_name, source, extra):
    ood_eval = score_ood[budget:]
    row = resc.eval_threshold(
        threshold=float(threshold),
        id_scores=score_id,
        ood_scores=score_ood,
        ood_eval_scores=ood_eval,
        attack_scores=score_attack,
        high_idx=high_idx,
        mixed_idx=mixed_idx,
    )
    out = {
        "policy_name": policy_name,
        "threshold_source": source,
        "selection_feasible": True,
        "roc_auc_attack_high_vs_ood_eval": compute_auc(ood_eval, score_attack[high_idx]),
        **row,
    }
    out.update(extra)
    return out


def choose_det50_threshold(score_id, score_ood, score_attack, high_idx, mixed_idx, budget, extra):
    # Use quantile grid over ID/OOD/attack scores; no label-derived threshold beyond the det-floor policy itself.
    combined = np.concatenate([score_id, score_ood, score_attack[high_idx]])
    qs = np.linspace(0.0, 1.0, 1001)
    thrs = np.unique(np.quantile(combined[np.isfinite(combined)], qs))
    rows = []
    for thr in thrs:
        rows.append(eval_at_threshold(score_id, score_ood, score_attack, high_idx, mixed_idx, budget, thr, "det_floor_50pct_min_alarm", "scan_min_alarm_subject_to_detection_floor", extra))
    df = pd.DataFrame(rows)
    cand = df[df["attack_detection_high_purity"] >= 0.5].copy()
    if cand.empty:
        out = rows[-1]
        out["selection_feasible"] = False
        return out
    cand = cand.sort_values(["ood_alarm_ratio_eval", "threshold"], ascending=[True, False])
    return cand.iloc[0].to_dict()


def evaluate_score(score_id, score_ood, score_attack, high_idx, mixed_idx, budget, extra, fixed_threshold=None, fixed_source=None):
    rows = []
    if fixed_threshold is None:
        fixed_threshold = float(np.quantile(score_id, 0.99))
        fixed_source = "id_q99_of_ensemble_score"
    rows.append(eval_at_threshold(score_id, score_ood, score_attack, high_idx, mixed_idx, budget, fixed_threshold, "fixed", fixed_source, extra))
    naive_thr = float(np.quantile(score_ood[:budget], 0.99)) if budget > 0 else float(np.quantile(score_id, 0.99))
    rows.append(eval_at_threshold(score_id, score_ood, score_attack, high_idx, mixed_idx, budget, naive_thr, "naive_ood_calib_q99", "ood_calibration_q99_budget5000", extra))
    rows.append(choose_det50_threshold(score_id, score_ood, score_attack, high_idx, mixed_idx, budget, extra))
    return rows


def load_seed_scores(seed: int):
    prefix = BASE_CACHE / f"latent_swap_spike_mix_seed{seed}"
    h_fit = np.load(str(prefix) + "_h_fit.npy").astype(np.float64)
    h_id = np.load(str(prefix) + "_h_id.npy").astype(np.float64)
    h_ood = np.load(str(prefix) + "_h_ood.npy").astype(np.float64)
    h_attack = np.load(str(prefix) + "_h_attack.npy").astype(np.float64)
    lw = LedoitWolf().fit(h_fit)
    mu = lw.location_
    sigma = lw.covariance_
    raw = {}
    diag = {}
    for name, h in [("id", h_id), ("ood", h_ood), ("attack", h_attack)]:
        raw[name], _ = dsw.cholesky_diagload_scores(h, mu, sigma, 0.0)
        diag[name], _ = dsw.cholesky_diagload_scores(h, mu, sigma, BASE_F)
    info = {
        "seed": seed,
        "latent_dim": int(h_fit.shape[1]),
        "n_id": int(h_id.shape[0]),
        "n_ood": int(h_ood.shape[0]),
        "n_attack": int(h_attack.shape[0]),
        "diag_q99": float(np.quantile(diag["id"], 0.99)),
        "raw_q9995": float(np.quantile(raw["id"], 0.9995)),
        "raw_q999": float(np.quantile(raw["id"], 0.999)),
        "raw_q998": float(np.quantile(raw["id"], 0.998)),
    }
    return raw, diag, info


def aggregate_results(df: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        "id_alarm_ratio",
        "ood_alarm_ratio_eval",
        "attack_detection_high_purity",
        "attack_detection_boundary",
        "roc_auc_attack_high_vs_ood_eval",
    ]
    agg = df.groupby(["object_label", "score_label", "policy_name"], as_index=False)[metrics].agg(["mean", "std", "count"]).reset_index()
    cols = []
    for c in agg.columns:
        if isinstance(c, tuple):
            cols.append(c[0] if c[1] == "" else f"{c[0]}_{c[1]}")
        else:
            cols.append(str(c))
    agg.columns = cols
    return agg


def plot_fixed(df_fixed: pd.DataFrame, out: Path):
    fig, ax = plt.subplots(figsize=(10, 7))
    for _, r in df_fixed.iterrows():
        ax.scatter(float(r["ood_alarm_ratio_eval"]), float(r["attack_detection_high_purity"]), s=70)
        ax.text(float(r["ood_alarm_ratio_eval"]) + 0.004, float(r["attack_detection_high_purity"]) + 0.004, str(r["object_label"]), fontsize=8)
    ax.axvline(0.1322, color="black", ls="--", lw=1, alpha=0.7, label="dA multiseed alarm mean")
    ax.axhline(0.8014, color="black", ls=":", lw=1, alpha=0.7, label="dA multiseed det mean")
    ax.set_xlabel("OOD benign alarm ratio")
    ax.set_ylabel("High-purity attack detection")
    ax.set_title("Seed-ensemble latent/covariance decision rules (fixed)")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=180)
    plt.close(fig)


def plot_bar(df_fixed: pd.DataFrame, out: Path):
    top = df_fixed.sort_values(["ood_alarm_ratio_eval", "attack_detection_high_purity"], ascending=[True, False]).head(18).copy()
    labels = top["object_label"].tolist()
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.bar(x - 0.18, top["ood_alarm_ratio_eval"], width=0.36, label="OOD alarm")
    ax.bar(x + 0.18, top["attack_detection_high_purity"], width=0.36, label="attack det")
    ax.axhline(0.1322, color="tab:red", ls="--", lw=1, label="dA alarm mean")
    ax.axhline(0.8014, color="tab:green", ls=":", lw=1, label="dA det mean")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=55, ha="right", fontsize=8)
    ax.set_ylim(0, 1.05)
    ax.set_title("Fixed metrics for seed-ensemble rules")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=180)
    plt.close(fig)


def append_map(run_tag: str):
    p = WORKTREE_ROOT / "runs" / "master_experiment_map_v1.md"
    if not p.exists():
        return
    text = p.read_text(encoding="utf-8")
    if f"`{run_tag}`" in text:
        return
    entry = f"\n- `{run_tag}`: Offline seed-ensemble test for latent covariance tail instability; no retraining; uses formal seeds 101/202/303 cached latents. Path: `runs/{run_tag}/`.\n"
    p.write_text(text.rstrip() + entry, encoding="utf-8")


def update_research_log(run_tag: str, best_line: str):
    p = WORKTREE_ROOT / "runs" / "research_log" / "a_tier_experiment_progress_log.md"
    if not p.exists():
        return
    text = p.read_text(encoding="utf-8")
    marker = "### 5.17 Latent Seed Ensemble Stability Check"
    block = f"""

{marker}

Run:
- `runs/{run_tag}/`

Purpose:
- Test whether seed-specific latent covariance tail failures can be stabilized without new training by ensembling formal seeds `101/202/303`.
- This is a diagnostic/upper-bound style experiment, not yet a deployment-simple final model.

Current result:
- {best_line}

Interpretation:
- If ensemble stabilizes alarm while preserving detection, the main problem is seed-specific tail geometry and a training-side stability loss should mimic the ensemble effect.
- If ensemble does not stabilize the trade-off, the issue is deeper than seed-specific threshold tails.
"""
    if marker in text:
        head, tail = text.split(marker, 1)
        # Preserve everything after the next section marker if present.
        next_idx = tail.find("\n### ", 5)
        if next_idx >= 0:
            text = head.rstrip() + "\n\n" + block.strip() + tail[next_idx:]
        else:
            text = head.rstrip() + "\n\n" + block.strip() + "\n"
    else:
        insert = "\n## 6. Current Candidate Ranking"
        if insert in text:
            text = text.replace(insert, block + "\n" + insert)
        else:
            text = text.rstrip() + block
    p.write_text(text, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Offline seed-ensemble test for latent covariance tail stability.")
    ap.add_argument("--run-tag", default="frontend100_latent_seed_ensemble_2026-04-08")
    ap.add_argument("--calibration-budget", type=int, default=5000)
    args = ap.parse_args()

    out = WORKTREE_ROOT / "runs" / args.run_tag
    out.mkdir(parents=True, exist_ok=True)
    plot_dir = out / "latent_seed_ensemble_plots"
    plot_dir.mkdir(exist_ok=True)
    (out / "command.txt").write_text("python " + " ".join(sys.argv) + "\n", encoding="utf-8")

    source_root = WORKTREE_ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master"
    stage2 = load_json(source_root / "runs" / "frontend100_joint_eval_stage2_2026-04-01" / "attack_manifest_stage2.json")
    idx = resc.build_stage2_indices(stage2)
    high_idx = idx["high"]
    mixed_idx = idx["mixed"]

    raw_scores = {"id": [], "ood": [], "attack": []}
    diag_scores = {"id": [], "ood": [], "attack": []}
    audit = []
    for seed in FORMAL_SEEDS:
        raw, diag, info = load_seed_scores(seed)
        audit.append(info)
        for split in ["id", "ood", "attack"]:
            raw_scores[split].append(raw[split])
            diag_scores[split].append(diag[split])

    # shape [n_seed, n_sample]
    raw_scores = {k: np.stack(v, axis=0) for k, v in raw_scores.items()}
    diag_scores = {k: np.stack(v, axis=0) for k, v in diag_scores.items()}

    rows: List[Dict] = []
    diagnostics = []

    def add_score(label: str, score_id, score_ood, score_attack, fixed_threshold=None, fixed_source=None):
        extra = {"object_label": label, "score_label": label, "row_type": "ensemble", "n_seed": len(FORMAL_SEEDS)}
        rows.extend(evaluate_score(score_id, score_ood, score_attack, high_idx, mixed_idx, args.calibration_budget, extra, fixed_threshold, fixed_source))

    # Normalize every seed by ID-only thresholds, then aggregate across seeds.
    for raw_q in RAW_QS:
        raw_thr = np.array([np.quantile(raw_scores["id"][i], raw_q) for i in range(len(FORMAL_SEEDS))], dtype=np.float64)
        diag_thr = np.array([np.quantile(diag_scores["id"][i], 0.99) for i in range(len(FORMAL_SEEDS))], dtype=np.float64)
        for split in ["id", "ood", "attack"]:
            pass
        norm_gate = {}
        vote_gate = {}
        for split in ["id", "ood", "attack"]:
            diag_norm = diag_scores[split] / diag_thr[:, None]
            raw_norm = raw_scores[split] / raw_thr[:, None]
            gate_norm = np.maximum(diag_norm, raw_norm)
            norm_gate[split] = gate_norm
            vote_gate[split] = (gate_norm > 1.0).astype(np.float64)

        qtag = tag_num(raw_q)
        add_score(
            f"ensemble_mean_gate_q{qtag}",
            np.mean(norm_gate["id"], axis=0),
            np.mean(norm_gate["ood"], axis=0),
            np.mean(norm_gate["attack"], axis=0),
        )
        add_score(
            f"ensemble_median_gate_q{qtag}",
            np.median(norm_gate["id"], axis=0),
            np.median(norm_gate["ood"], axis=0),
            np.median(norm_gate["attack"], axis=0),
        )
        add_score(
            f"ensemble_vote2_gate_q{qtag}",
            np.sum(vote_gate["id"], axis=0),
            np.sum(vote_gate["ood"], axis=0),
            np.sum(vote_gate["attack"], axis=0),
            fixed_threshold=1.5,
            fixed_source="vote_count_at_least_2_of_3",
        )
        add_score(
            f"ensemble_vote3_gate_q{qtag}",
            np.sum(vote_gate["id"], axis=0),
            np.sum(vote_gate["ood"], axis=0),
            np.sum(vote_gate["attack"], axis=0),
            fixed_threshold=2.5,
            fixed_source="vote_count_at_least_3_of_3",
        )
        diagnostics.append({
            "raw_q": raw_q,
            "raw_thresholds": raw_thr.tolist(),
            "diag_thresholds": diag_thr.tolist(),
            "id_vote2_alarm": float(np.mean(np.sum(vote_gate["id"], axis=0) > 1.5)),
            "ood_vote2_alarm": float(np.mean(np.sum(vote_gate["ood"], axis=0)[args.calibration_budget:] > 1.5)),
            "attack_high_vote2_det": float(np.mean(np.sum(vote_gate["attack"], axis=0)[high_idx] > 1.5)),
        })

    # Branch-only aggregation checks.
    diag_thr = np.array([np.quantile(diag_scores["id"][i], 0.99) for i in range(len(FORMAL_SEEDS))], dtype=np.float64)
    diag_norm = {split: diag_scores[split] / diag_thr[:, None] for split in ["id", "ood", "attack"]}
    add_score("ensemble_mean_diag_f0p5", np.mean(diag_norm["id"], axis=0), np.mean(diag_norm["ood"], axis=0), np.mean(diag_norm["attack"], axis=0))
    add_score("ensemble_median_diag_f0p5", np.median(diag_norm["id"], axis=0), np.median(diag_norm["ood"], axis=0), np.median(diag_norm["attack"], axis=0))

    # Reference rows from existing aggregate for dA / old-best / prior gate.
    ref = pd.read_csv(WORKTREE_ROOT / "runs" / "frontend100_diagload_gate_multiseed_2026-04-08" / "diagload_gate_multiseed_aggregate.csv")
    for old, new in [
        ("dA__default_score", "dA_multiseed_reference"),
        ("old_best__log_weighted", "old_best_multiseed_reference"),
        ("gate_f0p5_raw_q0p9995", "prior_single_seed_gate_q0p9995_multiseed"),
        ("gate_f0p5_raw_q0p999", "prior_single_seed_gate_q0p999_multiseed"),
    ]:
        r = ref[(ref["object_label"] == old) & (ref["policy_name"] == "fixed_gate_s_gt_1")]
        if not r.empty:
            rr = r.iloc[0]
            rows.append({
                "object_label": new,
                "score_label": new,
                "row_type": "reference_aggregate_as_row",
                "policy_name": "fixed",
                "threshold_source": "reused_prior_multiseed_aggregate",
                "selection_feasible": True,
                "threshold": np.nan,
                "id_alarm_ratio": rr.get("id_alarm_ratio_mean", np.nan),
                "ood_alarm_ratio_full": np.nan,
                "ood_alarm_ratio_eval": rr.get("ood_alarm_ratio_eval_mean", np.nan),
                "attack_detection_all": np.nan,
                "attack_detection_high_purity": rr.get("attack_detection_high_purity_mean", np.nan),
                "attack_detection_boundary": rr.get("attack_detection_boundary_mean", np.nan),
                "roc_auc_attack_high_vs_ood_eval": rr.get("roc_auc_attack_high_vs_ood_eval_mean", np.nan),
                "n_seed": 3,
            })

    results = pd.DataFrame(rows)
    fixed = results[results["policy_name"] == "fixed"].copy()
    fixed = fixed.sort_values(["ood_alarm_ratio_eval", "attack_detection_high_purity"], ascending=[True, False])

    results.to_csv(out / "latent_seed_ensemble_results.csv", index=False)
    results.to_csv(out / "results.csv", index=False)
    fixed.to_csv(out / "latent_seed_ensemble_fixed_results.csv", index=False)
    pd.DataFrame(diagnostics).to_csv(out / "latent_seed_ensemble_diagnostics.csv", index=False)

    (out / "latent_seed_ensemble_results.md").write_text(
        "# Latent Seed Ensemble Results\n\n## Fixed\n" + md_table(fixed[["object_label", "policy_name", "threshold_source", "ood_alarm_ratio_eval", "attack_detection_high_purity", "id_alarm_ratio", "roc_auc_attack_high_vs_ood_eval"]]) +
        "\n## All policies\n" + md_table(results[["object_label", "policy_name", "ood_alarm_ratio_eval", "attack_detection_high_purity", "id_alarm_ratio", "roc_auc_attack_high_vs_ood_eval"]]),
        encoding="utf-8",
    )

    plot_fixed(fixed, plot_dir / "fixed_tradeoff_latent_seed_ensemble.png")
    plot_bar(fixed, plot_dir / "fixed_metrics_latent_seed_ensemble.png")

    # Determine best candidate that beats dA alarm/det thresholds if any.
    dA_alarm = 0.1322
    dA_det = 0.8014
    candidates = fixed[~fixed["object_label"].str.contains("reference", na=False)].copy()
    beat = candidates[(candidates["ood_alarm_ratio_eval"] <= dA_alarm) & (candidates["attack_detection_high_purity"] >= dA_det)]
    if not beat.empty:
        best = beat.sort_values(["attack_detection_high_purity", "ood_alarm_ratio_eval"], ascending=[False, True]).iloc[0]
        best_line = f"Best A-target candidate: `{best['object_label']}` with alarm={best['ood_alarm_ratio_eval']:.4f}, det={best['attack_detection_high_purity']:.4f}."
    else:
        best = candidates.sort_values(["ood_alarm_ratio_eval", "attack_detection_high_purity"], ascending=[True, False]).iloc[0]
        best_line = f"No ensemble rule beats dA alarm/det simultaneously; lowest-alarm candidate `{best['object_label']}` has alarm={best['ood_alarm_ratio_eval']:.4f}, det={best['attack_detection_high_purity']:.4f}."

    summary = [
        "# Latent Seed Ensemble Summary",
        "",
        "- This is an offline seed-stability diagnostic; no new model training and no checkpoint modification.",
        "- Seeds: `101/202/303`.",
        "- Inputs: cached `latent_swap_spike_mix_no_compact` latent arrays from the gate multiseed run.",
        "- Tested mean/median normalized gate scores and 2-of-3 / 3-of-3 vote rules.",
        "",
        "## Fixed Results",
        md_table(fixed[["object_label", "threshold_source", "ood_alarm_ratio_eval", "attack_detection_high_purity", "id_alarm_ratio", "roc_auc_attack_high_vs_ood_eval"]]),
        "",
        "## Interpretation",
        f"- {best_line}",
        "- If ensemble vote/averaging works, the main bottleneck is seed-specific latent tail geometry. If it does not, training-side tail stability must be addressed directly.",
    ]
    if beat.empty:
        summary.append("- Current outcome: use this as a decision point before adding a new tail-stability loss; do not promote ensemble unless fixed alarm/detection is both competitive with dA.")
    else:
        summary.append("- Current outcome: ensemble is a viable upper-bound/stability candidate, but deployment cost and multi-checkpoint complexity must be discussed.")
    summary_text = "\n".join(summary) + "\n"
    (out / "summary.md").write_text(summary_text, encoding="utf-8")
    (out / "latent_seed_ensemble_summary.md").write_text(summary_text, encoding="utf-8")

    cfg = {
        "stage": "frontend100_latent_seed_ensemble",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_tag": args.run_tag,
        "no_training": True,
        "seeds": FORMAL_SEEDS,
        "source_cache": str(BASE_CACHE),
        "rules": ["mean_gate", "median_gate", "vote2_gate", "vote3_gate", "mean_diag", "median_diag"],
        "threshold_stats_source": "ID benign only",
        "raw_qs": RAW_QS,
        "base_f": BASE_F,
        "audit": clean(audit),
        "outputs": {"summary": str(out / "summary.md"), "results": str(out / "latent_seed_ensemble_results.csv"), "plots": str(plot_dir)},
    }
    (out / "config.json").write_text(json.dumps(clean(cfg), indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "latent_seed_ensemble_manifest.json").write_text(json.dumps(clean(cfg), indent=2, ensure_ascii=False), encoding="utf-8")

    append_map(args.run_tag)
    update_research_log(args.run_tag, best_line)
    print(f"[done] latent seed ensemble output: {out}")


if __name__ == "__main__":
    main()
