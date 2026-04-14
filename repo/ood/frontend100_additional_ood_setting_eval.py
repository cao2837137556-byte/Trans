
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
for p in [THIS_DIR, REPO_DIR]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from paths import ARTIFACT_RUNS_DIR, TRACKED_RUNS_DIR

import KitNET as kit
import frontend100_latent_scorer_benchmark as lsb
import frontend100_negative_recipe_rescoring as resc

FORMAL_SEEDS = [101, 202, 303]
EPS = 1e-12


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
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, row in df.iterrows():
        vals = []
        for c in cols:
            v = row[c]
            if isinstance(v, float):
                vals.append(f"{v:.6f}")
            else:
                vals.append(str(v))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"


def score_stats(scores: np.ndarray) -> Dict[str, float]:
    q = np.quantile(scores, [0.5, 0.95, 0.99])
    return {
        "mean": float(np.mean(scores)),
        "std": float(np.std(scores)),
        "q50": float(q[0]),
        "q95": float(q[1]),
        "q99": float(q[2]),
        "max": float(np.max(scores)),
    }


def score_dataset(model: kit.KitNET, x: np.ndarray, label: str, progress_every: int = 2000) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    scores = np.zeros(len(x), dtype=np.float64)
    print(f"[score] {label}: n={len(x)}", flush=True)
    for i in range(len(x)):
        if i > 0 and i % progress_every == 0:
            print(f"  {label}: {i}/{len(x)}", flush=True)
        scores[i] = model.process(x[i])
    return scores


def eval_threshold(threshold: float, id_scores: np.ndarray, ood_scores: np.ndarray, attack_scores: np.ndarray, high_idx: np.ndarray) -> Dict[str, float]:
    return {
        "threshold": float(threshold),
        "id_alarm_ratio": float(np.mean(id_scores > threshold)),
        "ood_alarm_ratio": float(np.mean(ood_scores > threshold)),
        "attack_detection_high_purity": float(np.mean(attack_scores[high_idx] > threshold)),
    }


def compute_auc(ood_scores: np.ndarray, attack_scores_high: np.ndarray) -> float:
    from sklearn.metrics import roc_auc_score

    y = np.concatenate([np.zeros(len(ood_scores), dtype=np.int64), np.ones(len(attack_scores_high), dtype=np.int64)])
    s = np.concatenate([ood_scores, attack_scores_high]).astype(np.float64)
    return float(roc_auc_score(y, s))


def cholesky_diagload_scores(x: np.ndarray, mu: np.ndarray, sigma: np.ndarray, f: float):
    x = np.asarray(x, dtype=np.float64)
    mu = np.asarray(mu, dtype=np.float64).reshape(-1)
    sigma = np.asarray(sigma, dtype=np.float64)
    diag = np.clip(np.diag(sigma), EPS, None)
    sigma_reg = sigma + float(f) * np.diag(diag)
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
        raise RuntimeError(f"Cholesky failed for f={f}")
    delta = x - mu[None, :]
    y = np.linalg.solve(chol, delta.T)
    score = np.sqrt(np.clip(np.sum(y * y, axis=0), 0.0, None))
    return score, {"jitter": float(jitter_used), "diag_median": float(np.median(diag))}


def load_attack_stage2_indices(source_root: Path) -> Dict[str, np.ndarray]:
    stage2 = json.loads((source_root / "runs" / "frontend100_joint_eval_stage2_2026-04-01" / "attack_manifest_stage2.json").read_text(encoding="utf-8"))
    return resc.build_stage2_indices(stage2)


def load_csv(path: Path, nrows: int | None = None) -> np.ndarray:
    return pd.read_csv(path, header=None, nrows=nrows).to_numpy(dtype=np.float64)


def extract_candidate_ood_latent(model: kit.KitNET, x_ood: np.ndarray, batch_size: int, cache_path: Path) -> np.ndarray:
    if cache_path.exists():
        return np.load(cache_path).astype(np.float64)
    print(f"[latent] extracting new OOD latent -> {cache_path.name}", flush=True)
    h_ood, _ = lsb.extract_global_latent(model, x_ood, batch_size=batch_size, negative=False)
    np.save(cache_path, h_ood.astype(np.float32))
    return h_ood.astype(np.float64)


def plot_tradeoff(df: pd.DataFrame, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(8.8, 6.0))
    colors = {
        "dA q99": "#d62728",
        "dA q995": "#ff9896",
        "dA q997": "#c49c94",
        "Transformer q99": "#1f77b4",
        "Transformer-TailReg q99": "#9467bd",
        "Transformer ensemble rawq0.999 / idq0.995": "#2ca02c",
        "Transformer ensemble rawq0.999 / idq0.99": "#98df8a",
        "Transformer ensemble rawq0.999 / idq0.997": "#1a9850",
        "Transformer ensemble rawq0.9995 / idq0.995": "#17becf",
        "Transformer ensemble rawq0.9995 / idq0.99": "#9edae5",
        "Transformer ensemble rawq0.9995 / idq0.997": "#3182bd",
    }
    for _, r in df.iterrows():
        label = str(r["object_label"])
        ax.scatter(float(r["ood_alarm_ratio_mean"]), float(r["attack_detection_high_purity_mean"]), s=80, color=colors.get(label, "#7f7f7f"))
        ax.text(float(r["ood_alarm_ratio_mean"]) + 0.004, float(r["attack_detection_high_purity_mean"]) + 0.004, label, fontsize=8)
    ax.set_xlabel("OOD benign alarm ratio")
    ax.set_ylabel("High-purity attack detection")
    ax.set_title("Additional benign OOD setting: fixed operating points")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out, dpi=180)
    plt.close(fig)


def plot_ood_stats(per_seed: pd.DataFrame, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(9.2, 5.4))
    keep = [
        "dA q99",
        "Transformer q99",
        "Transformer-TailReg q99",
        "Transformer ensemble rawq0.999 / idq0.995",
        "Transformer ensemble rawq0.9995 / idq0.995",
    ]
    sub = per_seed[per_seed["object_label"].isin(keep)].copy()
    for label, g in sub.groupby("object_label"):
        ax.plot(g["seed"], g["ood_alarm_ratio"], marker="o", label=label)
    ax.set_xlabel("seed")
    ax.set_ylabel("OOD alarm ratio")
    ax.set_title("Additional benign OOD setting by seed")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=180)
    plt.close(fig)


def append_map(run_tag: str):
    p = TRACKED_RUNS_DIR / "master_experiment_map_v1.md"
    if not p.exists():
        return
    text = p.read_text(encoding="utf-8")
    if f"`{run_tag}`" in text:
        return
    text = text.rstrip() + f"\n- `{run_tag}`: Additional benign OOD setting evaluation (same-capture temporal split) for current Transformer ensemble candidate vs dA and family references; no retraining. Path: `runs/{run_tag}/`.\n"
    p.write_text(text, encoding="utf-8")


def update_log(run_tag: str, line: str):
    p = TRACKED_RUNS_DIR / "research_log" / "a_tier_experiment_progress_log.md"
    if not p.exists():
        return
    text = p.read_text(encoding="utf-8")
    marker = "### 5.24 Additional Benign OOD Setting Check"
    block = f"""

{marker}

Run:
- `runs/{run_tag}/`

Purpose:
- Add a second benign-OOD setting without changing training checkpoints.
- New OOD benign set: same-capture late temporal segment (`frontend100_ood_stage1_2026-03-23`), weaker than cross-capture 4-1.

Current result:
- {line}

Interpretation:
- This is a width-of-evaluation check, not a new mainline discovery run.
- If the ensemble keeps a favorable operating region on both strong cross-capture OOD and weak temporal OOD, the paper story is materially stronger.
"""
    insert = "\n## 6. Current Candidate Ranking"
    if marker in text:
        return
    text = text.replace(insert, block + "\n" + insert) if insert in text else text.rstrip() + block
    p.write_text(text, encoding="utf-8")


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    ap = argparse.ArgumentParser(description="Additional benign OOD setting evaluation for current Transformer ensemble candidate.")
    ap.add_argument("--run-tag", default=f"frontend100_additional_ood_setting_{today}")
    ap.add_argument("--source-root", type=Path, default=WORKTREE_ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master")
    ap.add_argument("--seeds", default="101,202,303")
    ap.add_argument("--batch-size", type=int, default=1024)
    ap.add_argument("--raw-q-main", type=float, default=0.999)
    ap.add_argument("--raw-q-alt", type=float, default=0.9995)
    ap.add_argument("--diag-f", type=float, default=0.5)
    ap.add_argument("--id-quantiles", default="0.99,0.995,0.997")
    ap.add_argument("--ood-max-rows", type=int, default=0)
    ap.add_argument("--attack-max-rows", type=int, default=0)
    args = ap.parse_args()

    source = args.source_root
    seeds = [int(x.strip()) for x in str(args.seeds).split(",") if x.strip()]
    id_quantiles = [float(x.strip()) for x in str(args.id_quantiles).split(",") if x.strip()]
    out = ARTIFACT_RUNS_DIR / args.run_tag
    out.mkdir(parents=True, exist_ok=True)
    plot_dir = out / "additional_ood_setting_plots"
    plot_dir.mkdir(exist_ok=True)
    cache_dir = out / "cache_latents"
    cache_dir.mkdir(exist_ok=True)
    (out / "command.txt").write_text("python " + " ".join(sys.argv) + "\n", encoding="utf-8")

    cross_id_csv = source / "runs" / "frontend100_crosscapture_stage1_2026-03-25" / "data" / "id_source_100.csv"
    weak_ood_csv = source / "runs" / "frontend100_ood_stage1_2026-03-23" / "data" / "ood_benign_source_100.csv"
    attack_csv = source / "runs" / "frontend100_joint_eval_stage1_2026-03-31" / "data" / "attack_source_100.csv"

    x_all = load_csv(cross_id_csv, nrows=13000)
    x_fit = x_all[:8000]
    x_id = x_all[8000:13000]
    x_ood = load_csv(weak_ood_csv, nrows=(args.ood_max_rows if args.ood_max_rows > 0 else None))
    x_attack = load_csv(attack_csv, nrows=(args.attack_max_rows if args.attack_max_rows > 0 else None))
    idx = load_attack_stage2_indices(source)
    high_idx = idx["high"][idx["high"] < len(x_attack)]
    if len(high_idx) == 0:
        raise RuntimeError("No valid high-purity attack indices remain after attack-max-rows truncation.")

    locked = ARTIFACT_RUNS_DIR / "frontend100_locked_candidate_multiseed_2026-04-06"
    old = source / "runs" / "frontend100_tailreg_bestcfg_stability_2026-03-28"

    per_rows: List[Dict] = []
    ensemble_main_id = []
    ensemble_main_ood = []
    ensemble_main_attack = []
    ensemble_alt_id = []
    ensemble_alt_ood = []
    ensemble_alt_attack = []

    for seed in seeds:
        print(f"[seed {seed}] start", flush=True)

        # Family references: dA / transformer / tailreg.
        for obj_label, ckpt in [
            ("dA", old / f"da_seed{seed}" / f"kitnet_da_seed{seed}.ckpt"),
            ("Transformer", old / f"transformer_seed{seed}" / f"kitnet_transformer_seed{seed}.ckpt"),
            ("Transformer-TailReg", old / f"transformer_tailreg_seed{seed}" / f"kitnet_transformer_tailreg_seed{seed}.ckpt"),
        ]:
            print(f"[seed {seed}] scoring {obj_label}", flush=True)
            model = kit.KitNET.load_checkpoint(ckpt)
            sid = score_dataset(model, x_id, f"{obj_label} seed{seed} id")
            sood = score_dataset(model, x_ood, f"{obj_label} seed{seed} weak_ood")
            satt = score_dataset(model, x_attack, f"{obj_label} seed{seed} attack")
            thr99 = float(np.quantile(sid, 0.99))
            row = eval_threshold(thr99, sid, sood, satt, high_idx)
            per_rows.append({
                "seed": seed,
                "object_label": f"{obj_label} q99",
                "threshold_source": "ID q99",
                **row,
                "roc_auc_attack_high_vs_ood_eval": compute_auc(sood, satt[high_idx]),
            })
            if obj_label == "dA":
                for q in sorted(set(id_quantiles)):
                    if abs(q - 0.99) < 1e-12:
                        continue
                    thrq = float(np.quantile(sid, q))
                    rowq = eval_threshold(thrq, sid, sood, satt, high_idx)
                    per_rows.append({
                        "seed": seed,
                        "object_label": f"dA q{str(q).replace('0.', '')}",
                        "threshold_source": f"ID q{q}",
                        **rowq,
                        "roc_auc_attack_high_vs_ood_eval": compute_auc(sood, satt[high_idx]),
                    })

        # Main candidate ensemble branch.
        print(f"[seed {seed}] loading latent candidate checkpoint", flush=True)
        ckpt = locked / f"latent_swap_spike_mix_seed{seed}" / f"kitnet_transformer_latent_contrastive_v1_seed{seed}.ckpt"
        model = kit.KitNET.load_checkpoint(ckpt)
        h_fit = np.load(ARTIFACT_RUNS_DIR / "frontend100_diagload_gate_multiseed_2026-04-08" / "cache_latents" / f"latent_swap_spike_mix_seed{seed}_h_fit.npy").astype(np.float64)
        h_id = np.load(ARTIFACT_RUNS_DIR / "frontend100_diagload_gate_multiseed_2026-04-08" / "cache_latents" / f"latent_swap_spike_mix_seed{seed}_h_id.npy").astype(np.float64)
        h_attack = np.load(ARTIFACT_RUNS_DIR / "frontend100_diagload_gate_multiseed_2026-04-08" / "cache_latents" / f"latent_swap_spike_mix_seed{seed}_h_attack.npy").astype(np.float64)
        h_ood = extract_candidate_ood_latent(model, x_ood, args.batch_size, cache_dir / f"latent_swap_spike_mix_seed{seed}_weak_ood_h.npy")
        lw = LedoitWolf().fit(h_fit)
        mu = lw.location_
        sigma = lw.covariance_
        raw_id, _ = cholesky_diagload_scores(h_id, mu, sigma, 0.0)
        raw_ood, _ = cholesky_diagload_scores(h_ood, mu, sigma, 0.0)
        raw_attack, _ = cholesky_diagload_scores(h_attack, mu, sigma, 0.0)
        diag_id, _ = cholesky_diagload_scores(h_id, mu, sigma, args.diag_f)
        diag_ood, _ = cholesky_diagload_scores(h_ood, mu, sigma, args.diag_f)
        diag_attack, _ = cholesky_diagload_scores(h_attack, mu, sigma, args.diag_f)

        diag_thr = float(np.quantile(diag_id, 0.99))
        raw_thr_main = float(np.quantile(raw_id, args.raw_q_main))
        raw_thr_alt = float(np.quantile(raw_id, args.raw_q_alt))

        ensemble_main_id.append(np.maximum(diag_id / diag_thr, raw_id / raw_thr_main))
        ensemble_main_ood.append(np.maximum(diag_ood / diag_thr, raw_ood / raw_thr_main))
        ensemble_main_attack.append(np.maximum(diag_attack / diag_thr, raw_attack / raw_thr_main))
        ensemble_alt_id.append(np.maximum(diag_id / diag_thr, raw_id / raw_thr_alt))
        ensemble_alt_ood.append(np.maximum(diag_ood / diag_thr, raw_ood / raw_thr_alt))
        ensemble_alt_attack.append(np.maximum(diag_attack / diag_thr, raw_attack / raw_thr_alt))

    # Build ensemble scores.
    score_main = {
        "id": np.mean(np.stack(ensemble_main_id, axis=0), axis=0),
        "ood": np.mean(np.stack(ensemble_main_ood, axis=0), axis=0),
        "attack": np.mean(np.stack(ensemble_main_attack, axis=0), axis=0),
    }
    score_alt = {
        "id": np.mean(np.stack(ensemble_alt_id, axis=0), axis=0),
        "ood": np.mean(np.stack(ensemble_alt_ood, axis=0), axis=0),
        "attack": np.mean(np.stack(ensemble_alt_attack, axis=0), axis=0),
    }

    for q in id_quantiles:
        thr_main = float(np.quantile(score_main["id"], q))
        per_rows.append({
            "seed": -1,
            "object_label": f"Transformer ensemble rawq0.999 / idq{str(q).replace('0.', '0.')}",
            "threshold_source": f"ensemble ID q{q}",
            **eval_threshold(thr_main, score_main["id"], score_main["ood"], score_main["attack"], high_idx),
            "roc_auc_attack_high_vs_ood_eval": compute_auc(score_main["ood"], score_main["attack"][high_idx]),
        })
        thr_alt = float(np.quantile(score_alt["id"], q))
        per_rows.append({
            "seed": -1,
            "object_label": f"Transformer ensemble rawq0.9995 / idq{str(q).replace('0.', '0.')}",
            "threshold_source": f"ensemble ID q{q}",
            **eval_threshold(thr_alt, score_alt["id"], score_alt["ood"], score_alt["attack"], high_idx),
            "roc_auc_attack_high_vs_ood_eval": compute_auc(score_alt["ood"], score_alt["attack"][high_idx]),
        })

    per_df = pd.DataFrame(per_rows)

    agg_rows = []
    for obj, g in per_df[per_df["seed"] >= 0].groupby("object_label"):
        agg_rows.append({
            "object_label": obj,
            "ood_alarm_ratio_mean": float(g["ood_alarm_ratio"].mean()),
            "ood_alarm_ratio_std": float(g["ood_alarm_ratio"].std(ddof=0)),
            "attack_detection_high_purity_mean": float(g["attack_detection_high_purity"].mean()),
            "attack_detection_high_purity_std": float(g["attack_detection_high_purity"].std(ddof=0)),
            "id_alarm_ratio_mean": float(g["id_alarm_ratio"].mean()),
            "id_alarm_ratio_std": float(g["id_alarm_ratio"].std(ddof=0)),
            "roc_auc_mean": float(g["roc_auc_attack_high_vs_ood_eval"].mean()),
            "roc_auc_std": float(g["roc_auc_attack_high_vs_ood_eval"].std(ddof=0)),
            "source_mode": "multiseed_single_model",
        })
    for obj in sorted(set(per_df.loc[per_df["seed"] == -1, "object_label"].tolist())):
        r = per_df[per_df["object_label"] == obj].iloc[0]
        agg_rows.append({
            "object_label": obj,
            "ood_alarm_ratio_mean": float(r["ood_alarm_ratio"]),
            "ood_alarm_ratio_std": 0.0,
            "attack_detection_high_purity_mean": float(r["attack_detection_high_purity"]),
            "attack_detection_high_purity_std": 0.0,
            "id_alarm_ratio_mean": float(r["id_alarm_ratio"]),
            "id_alarm_ratio_std": 0.0,
            "roc_auc_mean": float(r["roc_auc_attack_high_vs_ood_eval"]),
            "roc_auc_std": 0.0,
            "source_mode": "3seed_ensemble",
        })
    agg_df = pd.DataFrame(agg_rows).sort_values(["ood_alarm_ratio_mean", "attack_detection_high_purity_mean"], ascending=[True, False])

    per_df.to_csv(out / "additional_ood_setting_per_seed.csv", index=False)
    agg_df.to_csv(out / "additional_ood_setting_aggregate.csv", index=False)
    (out / "additional_ood_setting_results.md").write_text("# Additional OOD Setting Results\n\n## Aggregate\n" + md_table(agg_df) + "\n## Per-seed\n" + md_table(per_df), encoding="utf-8")

    plot_tradeoff(agg_df, plot_dir / "additional_ood_tradeoff.png")
    plot_ood_stats(per_df[per_df["seed"] >= 0], plot_dir / "additional_ood_by_seed.png")

    line = "Secondary weak-OOD setting added using same-capture late benign segment; evaluate ID-only operating-region points rather than a single fixed quantile."
    summary_lines = [
        "# Additional Benign OOD Setting Summary",
        "",
        "- Setting: same-capture temporal OOD (`frontend100_ood_stage1_2026-03-23`) evaluated with current crosscapture-trained checkpoints.",
        "- No retraining.",
        "- Attack evaluation remains the current stage2 high-purity attack set.",
        "",
        "## Aggregate",
        md_table(agg_df),
        "",
        "## Interpretation",
        "- This is a width-of-evaluation check: a weaker benign OOD setting than the current stronger crosscapture OOD.",
        "- Use it to show whether the current main candidate only works on one OOD split or maintains the trend on a second benign shift.",
    ]
    (out / "summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    (out / "additional_ood_setting_summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    manifest = {
        "stage": "frontend100_additional_ood_setting_eval",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_tag": args.run_tag,
        "no_training": True,
        "source_root": str(source),
        "id_source_csv": str(cross_id_csv),
        "weak_ood_csv": str(weak_ood_csv),
        "attack_csv": str(attack_csv),
        "formal_seeds": FORMAL_SEEDS,
        "eval_seeds": seeds,
        "main_candidate": {
            "diag_f": args.diag_f,
            "raw_q_main": args.raw_q_main,
            "raw_q_alt": args.raw_q_alt,
            "id_quantiles": id_quantiles,
        },
        "ood_max_rows": int(args.ood_max_rows),
        "attack_max_rows": int(args.attack_max_rows),
        "outputs": {
            "per_seed": str(out / "additional_ood_setting_per_seed.csv"),
            "aggregate": str(out / "additional_ood_setting_aggregate.csv"),
            "summary": str(out / "summary.md"),
            "plots": str(plot_dir),
        },
    }
    (out / "additional_ood_setting_manifest.json").write_text(json.dumps(clean(manifest), indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "config.json").write_text(json.dumps(clean(manifest), indent=2, ensure_ascii=False), encoding="utf-8")

    append_map(args.run_tag)
    update_log(args.run_tag, line)
    print(f"[done] additional OOD setting output: {out}", flush=True)


if __name__ == "__main__":
    main()
