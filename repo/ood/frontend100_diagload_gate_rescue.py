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
import frontend100_score_postprocessing as spp
import frontend100_diagload_sweep_no_compact as dsw

BASE_F = [0.3, 0.4, 0.5]
RAW_Q = [0.995, 0.998, 0.999, 0.9995, 0.9998]


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


def append_map(run_tag: str) -> None:
    p = WORKTREE_ROOT / "runs" / "mainline_docs" / "mainline_experiment_map.md"
    if not p.exists(): return
    text = p.read_text(encoding="utf-8")
    if f"`{run_tag}`" in text: return
    entry = f"\n- `{run_tag}`: Offline two-threshold diagload+raw-Mahalanobis gate rescue for no-compact latent; no retraining. Path: `runs/{run_tag}/`.\n"
    p.write_text(text.rstrip() + "\n" + entry, encoding="utf-8")


def eval_pred(pred_id, pred_ood, pred_attack, high_idx, budget):
    return {
        "id_alarm_ratio": float(np.mean(pred_id)),
        "ood_alarm_ratio_full": float(np.mean(pred_ood)),
        "ood_alarm_ratio_eval": float(np.mean(pred_ood[budget:])),
        "attack_detection_all": float(np.mean(pred_attack)),
        "attack_detection_high_purity": float(np.mean(pred_attack[high_idx])),
    }


def plot_tradeoff(df: pd.DataFrame, out: Path) -> None:
    plt.figure(figsize=(9.5, 6.5))
    for _, r in df.iterrows():
        kind = str(r.get("kind", ""))
        if kind == "reference_da": color, marker, size = "#d62728", "s", 95
        elif kind == "reference_old_best": color, marker, size = "#2ca02c", "D", 85
        elif kind == "diagload_only": color, marker, size = "#1f77b4", "o", 70
        elif kind == "gate": color, marker, size = "#ff7f0e", "o", 80
        else: color, marker, size = "#7f7f7f", "x", 70
        plt.scatter(r["ood_alarm_ratio_eval"], r["attack_detection_high_purity"], color=color, marker=marker, s=size)
        if kind in ["reference_da", "reference_old_best"] or (kind == "gate" and r["ood_alarm_ratio_eval"] < 0.16 and r["attack_detection_high_purity"] > 0.8):
            plt.text(r["ood_alarm_ratio_eval"] + 0.003, r["attack_detection_high_purity"] + 0.005, str(r["label"]), fontsize=7.5)
    plt.axvline(0.1209, color="black", linestyle="--", linewidth=1, alpha=0.7, label="dA alarm")
    plt.axhline(0.7896, color="black", linestyle=":", linewidth=1, alpha=0.7, label="dA det")
    plt.xlabel("OOD benign alarm ratio (eval split)")
    plt.ylabel("High-purity attack detection")
    plt.title("Offline gate rescue: diagload base OR raw-Mahalanobis high-tail trigger")
    plt.grid(alpha=0.25); plt.legend(fontsize=8); plt.tight_layout(); plt.savefig(out, dpi=180); plt.close()


def plot_grid(df: pd.DataFrame, out: Path) -> None:
    gates = df[df["kind"].eq("gate")].copy()
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for f, g in gates.groupby("base_f"):
        g = g.sort_values("raw_q")
        axes[0].plot(g["raw_q"], g["ood_alarm_ratio_eval"], marker="o", label=f"base f={f}")
        axes[1].plot(g["raw_q"], g["attack_detection_high_purity"], marker="o", label=f"base f={f}")
    axes[0].axhline(0.1209, color="black", linestyle="--", linewidth=1); axes[0].set_title("alarm vs raw threshold quantile")
    axes[1].axhline(0.7896, color="black", linestyle="--", linewidth=1); axes[1].set_title("detection vs raw threshold quantile")
    for ax in axes:
        ax.set_xlabel("raw Mahalanobis ID quantile"); ax.grid(alpha=0.25); ax.legend(fontsize=8)
    axes[0].set_ylabel("OOD alarm"); axes[1].set_ylabel("high-purity detection")
    fig.tight_layout(); fig.savefig(out, dpi=180); plt.close(fig)


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    ap = argparse.ArgumentParser(description="Offline two-threshold gate rescue after overlap analysis.")
    ap.add_argument("--run-tag", default=f"frontend100_diagload_gate_rescue_{today}")
    ap.add_argument("--source-root", type=Path, default=WORKTREE_ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master")
    ap.add_argument("--calibration-budget", type=int, default=5000)
    args = ap.parse_args()
    out = WORKTREE_ROOT / "runs" / args.run_tag
    plot_dir = out / "diagload_gate_rescue_plots"
    out.mkdir(parents=True, exist_ok=True); plot_dir.mkdir(exist_ok=True)
    (out / "command.txt").write_text("python " + " ".join(sys.argv) + "\n", encoding="utf-8")

    # Load old-best scorer inputs.
    man = load_json(WORKTREE_ROOT / "runs" / "frontend100_negative_recipe_rescoring_2026-04-05" / "negative_recipe_rescoring_manifest.json")
    cand = {x["candidate_label"]: x for x in man["candidates"]}["latent_swap_spike_mix"]
    rd = Path(cand["run_dir"]); metrics = load_json(rd / "metrics.json")
    rmse_id = np.load(rd / "id_scores.npy").astype(float)
    rmse_ood = np.load(resc.pick_ood_score_file(rd, metrics)).astype(float)
    rmse_attack = np.load(Path(cand["attack_score_file"])).astype(float)
    cache = WORKTREE_ROOT / "runs" / "frontend100_negative_recipe_rescoring_2026-04-05" / "cache_rescored_scores"
    cos_id = np.load(cache / "latent_swap_spike_mix_latent_id_cos.npy").astype(float)
    cos_ood = np.load(cache / "latent_swap_spike_mix_latent_ood_cos.npy").astype(float)
    cos_attack = np.load(cache / "latent_swap_spike_mix_latent_attack_cos.npy").astype(float)
    versions, _ = spp.make_score_versions(rmse_id, rmse_ood, rmse_attack, cos_id, cos_ood, cos_attack)
    old_id, old_ood, old_attack = versions["log_weighted_z_rmse0.5_cos1.0"]

    # Load latent and compute Mahalanobis scores.
    lcache = WORKTREE_ROOT / "runs" / "frontend100_diagload_sweep_no_compact_2026-04-08" / "cache_latents"
    h_fit = np.load(lcache / "no_compact_latent_h_fit.npy").astype(float)
    h_id = np.load(lcache / "no_compact_latent_h_id.npy").astype(float)
    h_ood = np.load(lcache / "no_compact_latent_h_ood.npy").astype(float)
    h_attack = np.load(lcache / "no_compact_latent_h_attack.npy").astype(float)
    lw = LedoitWolf().fit(h_fit); mu = lw.location_; sigma = lw.covariance_
    maha = {}
    for f in [0.0] + BASE_F:
        sid, _ = dsw.cholesky_diagload_scores(h_id, mu, sigma, f)
        sood, _ = dsw.cholesky_diagload_scores(h_ood, mu, sigma, f)
        satt, _ = dsw.cholesky_diagload_scores(h_attack, mu, sigma, f)
        maha[float(f)] = {"id": sid, "ood": sood, "attack": satt, "thr_q99": float(np.quantile(sid, 0.99))}

    stage2 = load_json(args.source_root / "runs" / "frontend100_joint_eval_stage2_2026-04-01" / "attack_manifest_stage2.json")
    high_idx = resc.build_stage2_indices(stage2)["high"]
    budget = int(args.calibration_budget)

    rows: List[Dict] = []
    # References.
    old_thr = float(np.quantile(old_id, 0.99))
    old_pred = (old_id > old_thr, old_ood > old_thr, old_attack > old_thr)
    rows.append({"kind": "reference_old_best", "label": "old-best", "base_f": np.nan, "raw_q": np.nan, "rule": "old_best_q99", "threshold_source": "ID q99", **eval_pred(*old_pred, high_idx=high_idx, budget=budget)})
    # dA reference from known results file.
    covres = pd.read_csv(WORKTREE_ROOT / "runs" / "frontend100_covariance_regularized_v1_2026-04-07" / "covariance_regularized_v1_results.csv")
    da = covres[(covres["object_label"].eq("da__default_score")) & (covres["policy_name"].eq("fixed_id_q99"))].iloc[0]
    rows.append({"kind": "reference_da", "label": "dA", "base_f": np.nan, "raw_q": np.nan, "rule": "da_default_fixed", "threshold_source": "prior result", "id_alarm_ratio": da["id_alarm_ratio"], "ood_alarm_ratio_full": da["ood_alarm_ratio_full"], "ood_alarm_ratio_eval": da["ood_alarm_ratio_eval"], "attack_detection_all": da["attack_detection_all"], "attack_detection_high_purity": da["attack_detection_high_purity"]})

    raw = maha[0.0]
    for f in BASE_F:
        base = maha[float(f)]
        base_pred = (base["id"] > base["thr_q99"], base["ood"] > base["thr_q99"], base["attack"] > base["thr_q99"])
        rows.append({"kind": "diagload_only", "label": f"diag f={f}", "base_f": float(f), "raw_q": np.nan, "rule": f"diag_f{dsw.tag_float(f)}_q99", "threshold_source": "diag ID q99", **eval_pred(*base_pred, high_idx=high_idx, budget=budget)})
        for q in RAW_Q:
            raw_thr = float(np.quantile(raw["id"], q))
            pred_id = (base["id"] > base["thr_q99"]) | (raw["id"] > raw_thr)
            pred_ood = (base["ood"] > base["thr_q99"]) | (raw["ood"] > raw_thr)
            pred_attack = (base["attack"] > base["thr_q99"]) | (raw["attack"] > raw_thr)
            rows.append({
                "kind": "gate",
                "label": f"f={f}+raw q{q}",
                "base_f": float(f),
                "raw_q": float(q),
                "rule": f"diag_f{dsw.tag_float(f)}_q99_OR_raw_q{str(q).replace('.', 'p')}",
                "threshold_source": "both thresholds from ID benign only",
                "diag_threshold": float(base["thr_q99"]),
                "raw_threshold": raw_thr,
                **eval_pred(pred_id, pred_ood, pred_attack, high_idx=high_idx, budget=budget),
            })

    res = pd.DataFrame(rows)
    res["beats_da_fixed_alarm_and_det"] = (res["ood_alarm_ratio_eval"] <= 0.1209) & (res["attack_detection_high_purity"] >= 0.7896)
    res["beats_old_best_alarm_and_det"] = (res["ood_alarm_ratio_eval"] <= 0.1857) & (res["attack_detection_high_purity"] >= 0.8233)
    res["utility_det_minus_alarm"] = res["attack_detection_high_purity"] - res["ood_alarm_ratio_eval"]
    res.to_csv(out / "diagload_gate_rescue_results.csv", index=False)
    res.to_csv(out / "results.csv", index=False)
    (out / "diagload_gate_rescue_results.md").write_text(md_table(res), encoding="utf-8")
    (out / "results.md").write_text(md_table(res), encoding="utf-8")
    plot_tradeoff(res, plot_dir / "gate_rescue_tradeoff.png")
    plot_grid(res, plot_dir / "gate_rescue_grid.png")

    gates = res[res["kind"].eq("gate")].copy()
    best_utility = gates.sort_values("utility_det_minus_alarm", ascending=False).iloc[0]
    best_da_region = gates[(gates["ood_alarm_ratio_eval"] <= 0.130) & (gates["attack_detection_high_purity"] >= 0.7896)].sort_values(["ood_alarm_ratio_eval", "attack_detection_high_purity"], ascending=[True, False])
    best_da = best_da_region.iloc[0] if not best_da_region.empty else None
    lines = [
        "# Diagload Gate Rescue Summary",
        "",
        "## Setup",
        "- Offline decision-rule test only: no retraining and no checkpoint modification.",
        "- Base scorer: diagload Mahalanobis q99 from ID benign.",
        "- Rescue trigger: raw Mahalanobis high-tail threshold from ID benign only.",
        "- Rule: predict anomaly if `diagload_f > q99_ID(diagload_f)` OR `raw_maha > q_ID(raw_maha)`.",
        "- This is a discovery test; q selection is not yet multi-seed validated.",
        "",
        "## Key Result",
        f"- Best utility gate: `{best_utility['rule']}` alarm={float(best_utility['ood_alarm_ratio_eval']):.4f}, det={float(best_utility['attack_detection_high_purity']):.4f}, id_alarm={float(best_utility['id_alarm_ratio']):.4f}.",
    ]
    if best_da is not None:
        lines.append(f"- Best gate inside dA-level alarm region: `{best_da['rule']}` alarm={float(best_da['ood_alarm_ratio_eval']):.4f}, det={float(best_da['attack_detection_high_purity']):.4f}.")
        lines.append("- This crosses the single-seed fixed target relative to dA, but must be treated as an offline discovery and validated before claiming stability.")
    else:
        lines.append("- No gate entered the dA-level fixed region under the current thresholds.")
    lines += [
        "",
        "## Main Table",
        md_table(res.sort_values("utility_det_minus_alarm", ascending=False).head(12)),
    ]
    summary = "\n".join(lines) + "\n"
    (out / "diagload_gate_rescue_summary.md").write_text(summary, encoding="utf-8")
    (out / "summary.md").write_text(summary, encoding="utf-8")

    cfg = {"stage": "frontend100_diagload_gate_rescue", "generated_at": datetime.now().isoformat(timespec="seconds"), "run_tag": args.run_tag, "no_training": True, "no_checkpoint_modification": True, "rule": "diagload_q99 OR raw_maha_high_quantile", "base_f": BASE_F, "raw_q": RAW_Q, "statistics_source": "ID benign only", "outputs": {"results": str(out / "diagload_gate_rescue_results.csv"), "summary": str(out / "summary.md"), "plots": str(plot_dir)}}
    (out / "diagload_gate_rescue_manifest.json").write_text(json.dumps(clean(cfg), indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "config.json").write_text(json.dumps(clean(cfg), indent=2, ensure_ascii=False), encoding="utf-8")
    append_map(args.run_tag)
    print(f"[done] gate rescue output: {out}")


if __name__ == "__main__":
    main()

