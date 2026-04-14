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
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.neighbors import LocalOutlierFactor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

THIS_DIR = Path(__file__).resolve().parent
REPO_DIR = THIS_DIR.parent
WORKTREE_ROOT = REPO_DIR.parent
for p in [THIS_DIR, REPO_DIR]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from paths import ARTIFACT_RUNS_DIR, TRACKED_RUNS_DIR

import frontend100_negative_recipe_rescoring as resc


SEEDS = [101, 202, 303]


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


def eval_scores(
    object_label: str,
    detector_family: str,
    score_label: str,
    seed: int,
    id_scores: np.ndarray,
    ood_scores: np.ndarray,
    attack_scores: np.ndarray,
    high_idx: np.ndarray,
    mixed_idx: np.ndarray,
    budget: int,
    scan_points: int,
    extra: Dict,
) -> List[Dict]:
    rows: List[Dict] = []
    ood_eval = ood_scores[budget:]
    auc = resc.compute_auc(ood_eval_scores=ood_eval, attack_high_scores=attack_scores[high_idx])

    fixed_thr = float(np.quantile(id_scores, 0.99))
    row = resc.eval_threshold(
        threshold=fixed_thr,
        id_scores=id_scores,
        ood_scores=ood_scores,
        ood_eval_scores=ood_eval,
        attack_scores=attack_scores,
        high_idx=high_idx,
        mixed_idx=mixed_idx,
    )
    rows.append(
        {
            "row_type": "per_seed",
            "object_label": object_label,
            "detector_family": detector_family,
            "score_label": score_label,
            "seed": seed,
            "policy_name": "fixed_id_q99",
            "selection_feasible": True,
            "threshold_source": "ID benign q99",
            "roc_auc_attack_high_vs_ood_eval": float(auc),
            **row,
            **extra,
        }
    )

    calib_n = int(min(max(1, budget), len(ood_scores) - 1))
    naive_thr = float(np.quantile(ood_scores[:calib_n], 0.99))
    row = resc.eval_threshold(
        threshold=naive_thr,
        id_scores=id_scores,
        ood_scores=ood_scores,
        ood_eval_scores=ood_eval,
        attack_scores=attack_scores,
        high_idx=high_idx,
        mixed_idx=mixed_idx,
    )
    rows.append(
        {
            "row_type": "per_seed",
            "object_label": object_label,
            "detector_family": detector_family,
            "score_label": score_label,
            "seed": seed,
            "policy_name": "naive_calibrated_budget5000_target1pct",
            "selection_feasible": True,
            "threshold_source": "first 5000 OOD benign q99",
            "roc_auc_attack_high_vs_ood_eval": float(auc),
            **row,
            **extra,
        }
    )

    all_scores = np.concatenate([id_scores, ood_scores, attack_scores]).astype(np.float64)
    qs = np.linspace(0.0, 1.0, int(scan_points))
    thresholds = np.unique(np.quantile(all_scores, qs))
    scan_rows = []
    for thr in thresholds:
        er = resc.eval_threshold(
            threshold=float(thr),
            id_scores=id_scores,
            ood_scores=ood_scores,
            ood_eval_scores=ood_eval,
            attack_scores=attack_scores,
            high_idx=high_idx,
            mixed_idx=mixed_idx,
        )
        er["threshold"] = float(thr)
        scan_rows.append(er)
    scan_df = pd.DataFrame(scan_rows)
    det50 = resc.choose_detection_floor(scan_df, 0.50)
    if det50 is None:
        rows.append(
            {
                "row_type": "per_seed",
                "object_label": object_label,
                "detector_family": detector_family,
                "score_label": score_label,
                "seed": seed,
                "policy_name": "det_floor_50pct_min_alarm",
                "selection_feasible": False,
                "threshold_source": "attack high-purity scan",
                "roc_auc_attack_high_vs_ood_eval": float(auc),
                **extra,
            }
        )
    else:
        out = det50.to_dict()
        rows.append(
            {
                "row_type": "per_seed",
                "object_label": object_label,
                "detector_family": detector_family,
                "score_label": score_label,
                "seed": seed,
                "policy_name": "det_floor_50pct_min_alarm",
                "selection_feasible": True,
                "threshold_source": "min OOD eval alarm subject to high-purity detection >= 50%",
                "roc_auc_attack_high_vs_ood_eval": float(auc),
                **out,
                **extra,
            }
        )
    return rows


def aggregate(df: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        "id_alarm_ratio",
        "ood_alarm_ratio_eval",
        "attack_detection_high_purity",
        "attack_detection_boundary",
        "roc_auc_attack_high_vs_ood_eval",
    ]
    metrics = [c for c in metrics if c in df.columns]
    agg = (
        df.groupby(["object_label", "detector_family", "score_label", "policy_name"], as_index=False)[metrics]
        .agg(["mean", "std", "count"])
        .reset_index()
    )
    cols = []
    for c in agg.columns:
        if isinstance(c, tuple):
            cols.append(c[0] if c[1] == "" else f"{c[0]}_{c[1]}")
        else:
            cols.append(str(c))
    agg.columns = cols
    agg["row_type"] = "aggregate"
    meta_cols = [
        c
        for c in ["baseline_category", "training_mode", "uses_attack_labels", "source_mode"]
        if c in df.columns
    ]
    if meta_cols:
        meta = (
            df.groupby(["object_label", "detector_family", "score_label", "policy_name"], as_index=False)[meta_cols]
            .first()
        )
        agg = agg.merge(meta, on=["object_label", "detector_family", "score_label", "policy_name"], how="left")
    return agg


def fit_score_model(name: str, seed: int, x_fit: np.ndarray, x_id: np.ndarray, x_ood: np.ndarray, x_attack: np.ndarray, x_attack_mixed: np.ndarray):
    if name == "isolation_forest":
        model = make_pipeline(
            StandardScaler(),
            IsolationForest(n_estimators=300, contamination=0.01, random_state=seed, n_jobs=-1),
        )
        model.fit(x_fit)
        score_fn = lambda x: -model.decision_function(x)
        return score_fn, {"training_mode": "unsupervised_id_only", "uses_attack_labels": False}
    if name == "oneclass_svm":
        model = make_pipeline(StandardScaler(), OneClassSVM(kernel="rbf", gamma="scale", nu=0.01))
        model.fit(x_fit)
        score_fn = lambda x: -model.decision_function(x)
        return score_fn, {"training_mode": "unsupervised_id_only", "uses_attack_labels": False}
    if name == "lof_novelty":
        model = make_pipeline(
            StandardScaler(),
            LocalOutlierFactor(n_neighbors=35, contamination=0.01, novelty=True, n_jobs=-1),
        )
        model.fit(x_fit)
        score_fn = lambda x: -model.decision_function(x)
        return score_fn, {"training_mode": "unsupervised_id_only", "uses_attack_labels": False}
    if name == "random_forest_mixed_attack_upper":
        rng = np.random.default_rng(seed)
        if len(x_attack_mixed) == 0:
            raise RuntimeError("No mixed/boundary attack samples available for RandomForest upper-bound reference.")
        neg_idx = rng.choice(len(x_fit), size=len(x_fit), replace=False)
        x_train = np.vstack([x_fit[neg_idx], x_attack_mixed])
        y_train = np.concatenate([np.zeros(len(neg_idx), dtype=np.int64), np.ones(len(x_attack_mixed), dtype=np.int64)])
        model = make_pipeline(
            StandardScaler(),
            RandomForestClassifier(
                n_estimators=300,
                max_depth=None,
                min_samples_leaf=2,
                class_weight="balanced_subsample",
                random_state=seed,
                n_jobs=-1,
            ),
        )
        model.fit(x_train, y_train)
        score_fn = lambda x: model.predict_proba(x)[:, 1]
        return score_fn, {
            "training_mode": "supervised_upper_bound_mixed_attack_train_high_attack_eval",
            "uses_attack_labels": True,
            "attack_train_source": "stage2 mixed/boundary attack only; high-purity attack remains evaluation",
            "attack_train_n": int(len(x_attack_mixed)),
            "benign_train_n": int(len(neg_idx)),
        }
    raise ValueError(name)


def load_reference_rows(locked: Path, seeds: List[int]) -> pd.DataFrame:
    if not locked.exists():
        return pd.DataFrame()
    df = pd.read_csv(locked)
    keep_objects = {
        "da__default_score",
        "transformer_tailreg__default_score",
        "transformer__default_score",
        "latent_swap_spike_mix__log_weighted_z_rmse0.5_cos1.0",
    }
    keep_policies = {"fixed_id_q99", "naive_calibrated_budget5000_target1pct", "det_floor_50pct_min_alarm"}
    r = df[
        (df["row_type"].eq("per_seed"))
        & (df["object_label"].isin(keep_objects))
        & (df["policy_name"].isin(keep_policies))
        & (df["seed"].isin(seeds))
    ].copy()
    if r.empty:
        return r
    r["source_mode"] = "reused_existing_transformer_da_reference"
    r["baseline_category"] = "existing_reference"
    r["uses_attack_labels"] = False
    r["training_mode"] = "existing_reference"
    return r


def plot_tradeoff(agg: pd.DataFrame, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(10.5, 7.0))
    fixed = agg[agg["policy_name"].eq("fixed_id_q99")]
    colors = {
        "external_unsupervised": "#1f77b4",
        "supervised_upper_bound": "#d62728",
        "existing_reference": "#7f7f7f",
    }
    for _, r in fixed.iterrows():
        obj = str(r["object_label"])
        cat = str(r.get("baseline_category", "existing_reference"))
        color = colors.get(cat, "#2ca02c")
        marker = "s" if cat == "supervised_upper_bound" else ("^" if cat == "existing_reference" else "o")
        ax.errorbar(
            [r["ood_alarm_ratio_eval_mean"]],
            [r["attack_detection_high_purity_mean"]],
            xerr=[0 if pd.isna(r.get("ood_alarm_ratio_eval_std")) else r["ood_alarm_ratio_eval_std"]],
            yerr=[
                0
                if pd.isna(r.get("attack_detection_high_purity_std"))
                else r["attack_detection_high_purity_std"]
            ],
            fmt=marker,
            color=color,
            capsize=3,
        )
        ax.text(
            r["ood_alarm_ratio_eval_mean"] + 0.004,
            r["attack_detection_high_purity_mean"] + 0.006,
            obj.replace("__default_score", "").replace("__log_weighted_z_rmse0.5_cos1.0", ""),
            fontsize=8,
        )
    ax.axvline(0.1322, color="black", linestyle="--", linewidth=1, alpha=0.55, label="dA multiseed alarm mean")
    ax.axhline(0.8014, color="black", linestyle=":", linewidth=1, alpha=0.55, label="dA multiseed det mean")
    ax.set_xlabel("OOD benign alarm ratio (fixed q99, mean +/- std)")
    ax.set_ylabel("High-purity attack detection (fixed q99, mean +/- std)")
    ax.set_title("External baseline fixed-threshold comparison")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=180)
    plt.close(fig)


def plot_bar(agg: pd.DataFrame, policy: str, metric: str, out: Path, title: str) -> None:
    df = agg[agg["policy_name"].eq(policy)].copy().sort_values(metric + "_mean", ascending=False)
    if df.empty:
        return
    labels = df["object_label"].str.replace("__default_score", "", regex=False).str.replace(
        "__log_weighted_z_rmse0.5_cos1.0", "", regex=False
    )
    vals = df[metric + "_mean"].astype(float)
    errs = df[metric + "_std"].fillna(0).astype(float)
    plt.figure(figsize=(11, 5.8))
    plt.bar(np.arange(len(df)), vals, yerr=errs, capsize=3)
    plt.xticks(np.arange(len(df)), labels, rotation=35, ha="right", fontsize=8)
    plt.ylabel(metric)
    plt.title(title)
    plt.grid(axis="y", alpha=0.25)
    plt.tight_layout()
    plt.savefig(out, dpi=180)
    plt.close()


def append_map(run_tag: str) -> None:
    p = TRACKED_RUNS_DIR / "master_experiment_map_v1.md"
    if not p.exists():
        return
    text = p.read_text(encoding="utf-8")
    if f"`{run_tag}`" in text:
        return
    entry = (
        f"\n- `{run_tag}`: Minimal external baselines on original-frontend 100D stronger OOD "
        f"(`IsolationForest`, `OneClassSVM`, `LOF`, RF mixed-attack upper-bound); path: `runs/{run_tag}/`.\n"
    )
    p.write_text(text.rstrip() + entry, encoding="utf-8")


def update_research_log(run_tag: str, summary: str) -> None:
    p = TRACKED_RUNS_DIR / "research_log" / "a_tier_experiment_progress_log.md"
    if not p.exists():
        return
    text = p.read_text(encoding="utf-8")
    marker = "### 5.15 Minimal External Baselines"
    if marker in text:
        return
    insert = "\n## 6. Current Candidate Ranking"
    block = f"\n{marker}\n\nRun:\n- `runs/{run_tag}/`\n\n{summary}\n"
    if insert in text:
        text = text.replace(insert, block + "\n" + insert)
    else:
        text = text.rstrip() + block
    p.write_text(text, encoding="utf-8")


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    ap = argparse.ArgumentParser(description="Minimal external baselines for frontend100 stronger OOD.")
    ap.add_argument("--run-tag", default=f"frontend100_external_baselines_{today}")
    ap.add_argument("--source-root", type=Path, default=WORKTREE_ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master")
    ap.add_argument("--seeds", default="101,202,303")
    ap.add_argument("--calibration-budget", type=int, default=5000)
    ap.add_argument("--scan-points", type=int, default=1200)
    args = ap.parse_args()
    seeds = [int(x) for x in args.seeds.split(",") if x.strip()]
    out = ARTIFACT_RUNS_DIR / args.run_tag
    out.mkdir(parents=True, exist_ok=True)
    plot_dir = out / "external_baseline_plots"
    plot_dir.mkdir(exist_ok=True)
    (out / "command.txt").write_text("python " + " ".join(sys.argv) + "\n", encoding="utf-8")

    source = args.source_root
    data = source / "runs" / "frontend100_crosscapture_stage1_2026-03-25" / "data"
    x_all = pd.read_csv(data / "id_source_100.csv", header=None, nrows=13000).to_numpy(np.float64)
    x_fit = x_all[:8000]
    x_id = x_all[8000:13000]
    x_ood = pd.read_csv(data / "ood_benign_source_100.csv", header=None).to_numpy(np.float64)
    attack_csv = source / "runs" / "frontend100_joint_eval_stage1_2026-03-31" / "data" / "attack_source_100.csv"
    x_attack = pd.read_csv(attack_csv, header=None).to_numpy(np.float64)
    stage2 = load_json(source / "runs" / "frontend100_joint_eval_stage2_2026-04-01" / "attack_manifest_stage2.json")
    idx = resc.build_stage2_indices(stage2)
    high_idx = idx["high"]
    mixed_idx = idx["mixed"]
    x_attack_mixed = x_attack[mixed_idx]

    methods = [
        "isolation_forest",
        "oneclass_svm",
        "lof_novelty",
        "random_forest_mixed_attack_upper",
    ]
    rows: List[Dict] = []
    for method in methods:
        for seed in seeds:
            print(f"[fit] {method} seed={seed}", flush=True)
            score_fn, meta = fit_score_model(method, seed, x_fit, x_id, x_ood, x_attack, x_attack_mixed)
            sid = np.asarray(score_fn(x_id), dtype=np.float64)
            sood = np.asarray(score_fn(x_ood), dtype=np.float64)
            satt = np.asarray(score_fn(x_attack), dtype=np.float64)
            cat = "supervised_upper_bound" if meta.get("uses_attack_labels") else "external_unsupervised"
            rows.extend(
                eval_scores(
                    object_label=method,
                    detector_family=method,
                    score_label="default_score",
                    seed=seed,
                    id_scores=sid,
                    ood_scores=sood,
                    attack_scores=satt,
                    high_idx=high_idx,
                    mixed_idx=mixed_idx,
                    budget=args.calibration_budget,
                    scan_points=args.scan_points,
                    extra={
                        "source_mode": "computed_now",
                        "baseline_category": cat,
                        **meta,
                    },
                )
            )

    ref = load_reference_rows(
        ARTIFACT_RUNS_DIR / "frontend100_locked_candidate_multiseed_2026-04-06" / "multiseed_locked_candidate_results.csv",
        seeds,
    )
    if not ref.empty:
        rows.extend(ref.to_dict("records"))
    per = pd.DataFrame(rows)
    agg = aggregate(per)
    per.to_csv(out / "external_baseline_results.csv", index=False)
    per.to_csv(out / "results.csv", index=False)
    agg.to_csv(out / "external_baseline_aggregate.csv", index=False)

    results_md = "# External Baseline Results\n\n"
    results_md += "## Aggregate\n" + md_table(agg) + "\n\n"
    results_md += "## Per-seed fixed rows\n" + md_table(
        per[per["policy_name"].eq("fixed_id_q99")][
            [
                "object_label",
                "seed",
                "baseline_category",
                "training_mode",
                "ood_alarm_ratio_eval",
                "attack_detection_high_purity",
                "roc_auc_attack_high_vs_ood_eval",
                "id_alarm_ratio",
            ]
        ].sort_values(["object_label", "seed"])
    )
    (out / "external_baseline_results.md").write_text(results_md, encoding="utf-8")

    plot_tradeoff(agg, plot_dir / "fixed_tradeoff_external_baselines.png")
    plot_bar(
        agg,
        "fixed_id_q99",
        "attack_detection_high_purity",
        plot_dir / "fixed_detection_bar.png",
        "Fixed q99 high-purity attack detection",
    )
    plot_bar(
        agg,
        "fixed_id_q99",
        "ood_alarm_ratio_eval",
        plot_dir / "fixed_alarm_bar.png",
        "Fixed q99 OOD benign alarm",
    )

    fixed = agg[agg["policy_name"].eq("fixed_id_q99")].copy()
    display_cols = [
        "object_label",
        "baseline_category",
        "ood_alarm_ratio_eval_mean",
        "ood_alarm_ratio_eval_std",
        "attack_detection_high_purity_mean",
        "attack_detection_high_purity_std",
        "roc_auc_attack_high_vs_ood_eval_mean",
        "roc_auc_attack_high_vs_ood_eval_std",
    ]
    fixed_display = fixed[display_cols].sort_values("object_label")
    def rowv(obj, col):
        r = fixed[fixed.object_label.eq(obj)]
        return float("nan") if r.empty else float(r.iloc[0][col])

    summary_lines = [
        "# Minimal External Baseline Summary",
        "",
        "- Data: original-frontend 100D + stronger OOD protocol.",
        "- Unsupervised baselines train only on ID benign fit split.",
        "- RandomForest is an attack-assisted upper-bound reference: trained on ID benign plus stage2 mixed/boundary attack; high-purity attack remains evaluation.",
        "- All fixed thresholds use ID benign q99.",
        "",
        "## Fixed q99 Aggregate",
        md_table(fixed_display),
        "",
        "## Interpretation",
        f"- dA fixed reference: alarm={rowv('da__default_score','ood_alarm_ratio_eval_mean'):.4f}, det={rowv('da__default_score','attack_detection_high_purity_mean'):.4f}.",
        "- Compare unsupervised external methods against dA and current Transformer references before using them as paper baselines.",
        "- Treat RandomForest as an upper-bound / sanity check only because it uses attack labels from the same attack source, though not high-purity evaluation samples.",
    ]
    summary = "\n".join(summary_lines) + "\n"
    (out / "external_baseline_summary.md").write_text(summary, encoding="utf-8")
    (out / "summary.md").write_text(summary, encoding="utf-8")

    cfg = {
        "stage": "frontend100_external_baselines",
        "run_tag": args.run_tag,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "seeds": seeds,
        "data_protocol": "original-frontend 100D + stronger OOD",
        "id_fit_n": int(len(x_fit)),
        "id_eval_n": int(len(x_id)),
        "ood_n": int(len(x_ood)),
        "attack_n": int(len(x_attack)),
        "attack_high_n": int(len(high_idx)),
        "attack_mixed_n": int(len(mixed_idx)),
        "methods": methods,
        "rf_note": "supervised upper-bound reference trained on mixed/boundary attack only; high-purity attack remains evaluation",
        "outputs": {
            "results": str(out / "external_baseline_results.csv"),
            "aggregate": str(out / "external_baseline_aggregate.csv"),
            "summary": str(out / "summary.md"),
            "plots": str(plot_dir),
        },
    }
    (out / "external_baseline_manifest.json").write_text(json.dumps(clean(cfg), indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "config.json").write_text(json.dumps(clean(cfg), indent=2, ensure_ascii=False), encoding="utf-8")
    append_map(args.run_tag)
    update_research_log(
        args.run_tag,
        "- Added minimal external baselines for A-tier risk control: IsolationForest, OneClassSVM, LOF, and RandomForest mixed-attack upper-bound.\n"
        "- The key question is whether common non-Transformer baselines easily beat dA/Transformer under the same stronger OOD protocol.",
    )
    print(f"[done] external baselines output: {out}", flush=True)


if __name__ == "__main__":
    main()
