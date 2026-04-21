from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

THIS_DIR = Path(__file__).resolve().parent
REPO_DIR = THIS_DIR.parent
WORKTREE_ROOT = REPO_DIR.parent
for p in [THIS_DIR, REPO_DIR]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import frontend100_negative_recipe_rescoring as resc
import frontend100_timescale_tokenizer_v1_3 as tv3


FAMILY_ORDER = ["MI_dir", "HH", "HH_jit", "HpHp"]
SCALE_ORDER = ["5s", "3s", "1s", "0.1s", "0.01s"]
SOURCE_RICH_CHANNEL_NAMES = [
    "logw_raw",
    "mean_slog_raw",
    "std_slog_raw",
    "cv_slog_raw",
    "cov_slog_raw",
    "pcc_slog_raw",
    "mean_rel_family",
    "std_rel_family",
    "logw_centered_family",
    "cov_rel_family",
    "pcc_centered_family",
    "mean_short_long_ratio",
    "cv_short_long_ratio",
]
ID_CALIB_POLICY = "id_budget_calibrated_target1pct"


def load_source_rich(path: Path) -> np.ndarray:
    arr = np.load(path)
    if arr.ndim != 3 or arr.shape[1:] != (20, 13):
        raise RuntimeError(f"Expected source_rich_v1 matrix [N,20,13], got {arr.shape} from {path}")
    if not np.isfinite(arr).all():
        arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
    return arr.astype(np.float32)


def flatten_source_rich(x: np.ndarray) -> np.ndarray:
    return x.reshape(len(x), -1).astype(np.float32)


def id_budget_calibrate(
    score_id_eval: np.ndarray,
    score_ood_eval: np.ndarray,
    score_attack_high: np.ndarray,
    budget: int = 5000,
    target_alarm: float = 0.01,
    seed: int = 42,
    n_candidates: int = 4000,
) -> dict:
    rng = np.random.default_rng(seed)
    n_sub = min(int(budget), len(score_id_eval))
    idx = rng.choice(len(score_id_eval), n_sub, replace=False)
    id_sub = score_id_eval[idx].astype(np.float64)
    q_levels = np.linspace(0.0, 1.0, int(n_candidates) + 1)[1:]
    candidates = np.unique(np.quantile(id_sub, q_levels))
    for thr in sorted(candidates):
        alarm = float(np.mean(score_ood_eval > thr))
        if alarm <= target_alarm:
            return {
                "threshold": float(thr),
                "calibrated_ood_alarm": alarm,
                "calibrated_det": float(np.mean(score_attack_high > thr)),
                "feasible": True,
            }

    thr_max = float(np.max(id_sub))
    alarm_max = float(np.mean(score_ood_eval > thr_max))
    return {
        "threshold": thr_max,
        "calibrated_ood_alarm": alarm_max,
        "calibrated_det": float(np.mean(score_attack_high > thr_max)),
        "feasible": alarm_max <= target_alarm,
    }


def make_combined_summary(df: pd.DataFrame, calib_policy: str) -> pd.DataFrame:
    key = ["object_label", "detector_family", "token_profile", "score_label"]
    fixed = df[df["policy_name"].eq("fixed_id_q99")].copy()
    calib = df[df["policy_name"].eq(calib_policy)].copy()
    fixed = fixed[key + ["ood_alarm_ratio_eval", "attack_detection_high_purity", "roc_auc_attack_high_vs_ood_eval"]].rename(
        columns={"ood_alarm_ratio_eval": "fixed_alarm", "attack_detection_high_purity": "fixed_det"}
    )
    calib = calib[key + ["ood_alarm_ratio_eval", "attack_detection_high_purity", "selection_feasible"]].rename(
        columns={"ood_alarm_ratio_eval": "calibrated_alarm", "attack_detection_high_purity": "calibrated_det"}
    )
    combined = fixed.merge(calib, on=key, how="left")
    order = key + [
        "fixed_alarm",
        "fixed_det",
        "calibrated_alarm",
        "calibrated_det",
        "selection_feasible",
        "roc_auc_attack_high_vs_ood_eval",
    ]
    return combined[[c for c in order if c in combined.columns]]


def split_contiguous(indices: Iterable[int], train_frac: float = 0.60, val_frac: float = 0.20) -> dict:
    idx = np.asarray(sorted(int(i) for i in indices), dtype=np.int64)
    n = len(idx)
    n_train = int(np.floor(n * train_frac))
    n_val = int(np.floor(n * val_frac))
    if n_train <= 0 or n_val <= 0 or n - n_train - n_val <= 0:
        raise RuntimeError(f"Not enough indices for contiguous split: n={n}")
    return {
        "train": idx[:n_train],
        "val": idx[n_train : n_train + n_val],
        "eval": idx[n_train + n_val :],
    }


def score_model(model: LogisticRegression, scaler: StandardScaler, x: np.ndarray) -> np.ndarray:
    return model.decision_function(scaler.transform(x)).astype(np.float64)


def add_score_rows(
    rows: List[Dict],
    object_label: str,
    detector_family: str,
    score_label: str,
    score_id_calib: np.ndarray,
    score_ood_eval: np.ndarray,
    score_attack_eval: np.ndarray,
    fixed_threshold: float,
    calib_result: dict,
    auc: float,
    seed: int,
    extra: Dict,
) -> None:
    rows.append(
        {
            "object_label": object_label,
            "detector_family": detector_family,
            "score_label": score_label,
            "seed": seed,
            "policy_name": "fixed_id_q99",
            "selection_feasible": True,
            "threshold_source": "ID calibration q99",
            "threshold": fixed_threshold,
            "id_alarm_ratio": float(np.mean(score_id_calib > fixed_threshold)),
            "ood_alarm_ratio_full": float(np.mean(score_ood_eval > fixed_threshold)),
            "ood_alarm_ratio_eval": float(np.mean(score_ood_eval > fixed_threshold)),
            "attack_detection_all": float(np.mean(score_attack_eval > fixed_threshold)),
            "attack_detection_high_purity": float(np.mean(score_attack_eval > fixed_threshold)),
            "attack_detection_boundary": float("nan"),
            "roc_auc_attack_high_vs_ood_eval": float(auc),
            **extra,
        }
    )
    thr = calib_result["threshold"]
    rows.append(
        {
            "object_label": object_label,
            "detector_family": detector_family,
            "score_label": score_label,
            "seed": seed,
            "policy_name": ID_CALIB_POLICY,
            "selection_feasible": bool(calib_result["feasible"]),
            "threshold_source": "min ID-calib q s.t. ood_alarm<=target",
            "threshold": thr,
            "id_alarm_ratio": float(np.mean(score_id_calib > thr)),
            "ood_alarm_ratio_full": float(np.mean(score_ood_eval > thr)),
            "ood_alarm_ratio_eval": float(calib_result["calibrated_ood_alarm"]),
            "attack_detection_all": float(np.mean(score_attack_eval > thr)),
            "attack_detection_high_purity": float(calib_result["calibrated_det"]),
            "attack_detection_boundary": float("nan"),
            "roc_auc_attack_high_vs_ood_eval": float(auc),
            **extra,
        }
    )


def build_row_scores(
    score_id_calib: np.ndarray,
    score_ood_eval: np.ndarray,
    score_attack_eval: np.ndarray,
    id_calib_idx: np.ndarray,
    ood_eval_idx: np.ndarray,
    attack_eval_idx: np.ndarray,
) -> pd.DataFrame:
    frames = [
        pd.DataFrame(
            {
                "source": "id",
                "split": "calibration",
                "row_index": id_calib_idx.astype(np.int64),
                "label": 0,
                "score": score_id_calib,
            }
        ),
        pd.DataFrame(
            {
                "source": "ood_benign",
                "split": "eval",
                "row_index": ood_eval_idx.astype(np.int64),
                "label": 0,
                "score": score_ood_eval,
            }
        ),
        pd.DataFrame(
            {
                "source": "attack_high",
                "split": "eval",
                "row_index": attack_eval_idx.astype(np.int64),
                "label": 1,
                "score": score_attack_eval,
            }
        ),
    ]
    return pd.concat(frames, ignore_index=True)


def build_feature_importance(coef: np.ndarray) -> pd.DataFrame:
    rows = []
    flat = coef.reshape(20, 13)
    for token_id in range(20):
        family_id = token_id // 5
        scale_id = token_id % 5
        for ch_id, ch_name in enumerate(SOURCE_RICH_CHANNEL_NAMES):
            weight = float(flat[token_id, ch_id])
            rows.append(
                {
                    "token_id": token_id,
                    "family": FAMILY_ORDER[family_id],
                    "scale": SCALE_ORDER[scale_id],
                    "channel_id": ch_id,
                    "channel": ch_name,
                    "coef": weight,
                    "abs_coef": abs(weight),
                }
            )
    return pd.DataFrame(rows).sort_values("abs_coef", ascending=False)


def load_anchor_rows() -> pd.DataFrame:
    specs = [
        (
            "v3_fix3",
            WORKTREE_ROOT / "runs" / "frontend_f2_expression_v3_tokenizer_v1_smoke_2026-04-16_fix3" / "frontend_f2_expression_v3_combined.csv",
        ),
        (
            "v5_compact_v1",
            WORKTREE_ROOT / "runs" / "frontend_f2_expression_v5_compact_tokenizer_v1_smoke_2026-04-20" / "frontend_f2_expression_v5_compact_combined.csv",
        ),
    ]
    rows = []
    for exp, path in specs:
        if not path.exists():
            continue
        df = pd.read_csv(path)
        mask = (
            df["detector_family"].astype(str).str.contains("transformer", regex=False)
            & df["token_profile"].eq("family_short_focus")
            & df["score_label"].isin(["mi_dir_mean", "mi_hphp_short_mean", "hphp_mean"])
        )
        for _, r in df[mask].iterrows():
            rows.append(
                {
                    "exp": exp,
                    "score_label": r["score_label"],
                    "auc": float(r["roc_auc_attack_high_vs_ood_eval"]),
                    "calibrated_alarm": float(r["calibrated_alarm"]),
                    "calibrated_det": float(r["calibrated_det"]),
                    "feasible": bool(r["selection_feasible"]),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    ap = argparse.ArgumentParser(description="Frontend-F2 v7 source_rich one-vs-benign diagnostic ranker.")
    ap.add_argument("--run-tag", default=f"frontend_f2_v7_source_rich_ranker_{today}")
    ap.add_argument(
        "--benign-data-dir",
        type=Path,
        default=WORKTREE_ROOT / "runs" / "frontend_f2_source_rich_crosscapture_stage1_2026-04-20" / "data",
    )
    ap.add_argument(
        "--attack-data-dir",
        type=Path,
        default=WORKTREE_ROOT / "runs" / "frontend_f2_source_rich_attack_source_2026-04-20" / "data",
    )
    ap.add_argument(
        "--stage2-manifest",
        type=Path,
        default=WORKTREE_ROOT.parents[1]
        / "KitNET-py-master"
        / "KitNET-py-master"
        / "runs"
        / "frontend100_joint_eval_stage2_2026-04-01"
        / "attack_manifest_stage2.json",
    )
    ap.add_argument("--id-train-rows", type=int, default=8000)
    ap.add_argument("--id-val-rows", type=int, default=2000)
    ap.add_argument("--id-calibration-rows", type=int, default=5000)
    ap.add_argument("--ood-train-rows", type=int, default=8000)
    ap.add_argument("--ood-val-rows", type=int, default=2000)
    ap.add_argument("--attack-train-frac", type=float, default=0.60)
    ap.add_argument("--attack-val-frac", type=float, default=0.20)
    ap.add_argument("--calibration-target", type=float, default=0.01)
    ap.add_argument("--calibration-budget", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--C", type=float, default=1.0)
    args = ap.parse_args()

    out = WORKTREE_ROOT / "runs" / args.run_tag
    out.mkdir(parents=True, exist_ok=True)
    (out / "command.txt").write_text("python " + " ".join(sys.argv) + "\n", encoding="utf-8")

    id_matrix = load_source_rich(args.benign_data_dir / "id_source_expression_source_rich_v1_matrix.npy")
    ood_matrix = load_source_rich(args.benign_data_dir / "ood_benign_source_expression_source_rich_v1_matrix.npy")
    attack_matrix = load_source_rich(args.attack_data_dir / "attack_source_expression_source_rich_v1_matrix.npy")
    id_x = flatten_source_rich(id_matrix)
    ood_x = flatten_source_rich(ood_matrix)
    attack_x = flatten_source_rich(attack_matrix)

    id_train_end = int(args.id_train_rows)
    id_val_end = id_train_end + int(args.id_val_rows)
    id_calib_end = id_val_end + int(args.id_calibration_rows)
    ood_train_end = int(args.ood_train_rows)
    ood_val_end = ood_train_end + int(args.ood_val_rows)
    if id_calib_end > len(id_x):
        raise RuntimeError(f"ID split exceeds rows: need {id_calib_end}, have {len(id_x)}")
    if ood_val_end >= len(ood_x):
        raise RuntimeError(f"OOD split leaves no eval rows: val_end={ood_val_end}, rows={len(ood_x)}")

    stage2 = json.loads(args.stage2_manifest.read_text(encoding="utf-8-sig"))
    high_idx = np.asarray(sorted(resc.build_stage2_indices(stage2)["high"]), dtype=np.int64)
    high_idx = high_idx[(high_idx >= 0) & (high_idx < len(attack_x))]
    attack_split = split_contiguous(high_idx, args.attack_train_frac, args.attack_val_frac)

    x_train = np.concatenate(
        [
            id_x[:id_train_end],
            ood_x[:ood_train_end],
            attack_x[attack_split["train"]],
        ],
        axis=0,
    )
    y_train = np.concatenate(
        [
            np.zeros(id_train_end, dtype=np.int64),
            np.zeros(ood_train_end, dtype=np.int64),
            np.ones(len(attack_split["train"]), dtype=np.int64),
        ],
        axis=0,
    )
    x_val = np.concatenate(
        [
            id_x[id_train_end:id_val_end],
            ood_x[ood_train_end:ood_val_end],
            attack_x[attack_split["val"]],
        ],
        axis=0,
    )
    y_val = np.concatenate(
        [
            np.zeros(id_val_end - id_train_end, dtype=np.int64),
            np.zeros(ood_val_end - ood_train_end, dtype=np.int64),
            np.ones(len(attack_split["val"]), dtype=np.int64),
        ],
        axis=0,
    )

    scaler = StandardScaler()
    x_train_z = scaler.fit_transform(x_train)
    model = LogisticRegression(
        C=float(args.C),
        penalty="l2",
        solver="liblinear",
        class_weight="balanced",
        max_iter=2000,
        random_state=int(args.seed),
    )
    model.fit(x_train_z, y_train)

    id_calib_idx = np.arange(id_val_end, id_calib_end, dtype=np.int64)
    ood_eval_idx = np.arange(ood_val_end, len(ood_x), dtype=np.int64)
    attack_eval_idx = attack_split["eval"]
    score_id_calib = score_model(model, scaler, id_x[id_calib_idx])
    score_ood_eval = score_model(model, scaler, ood_x[ood_eval_idx])
    score_attack_eval = score_model(model, scaler, attack_x[attack_eval_idx])
    score_val = score_model(model, scaler, x_val)

    auc = float(roc_auc_score(
        np.concatenate([np.zeros(len(score_ood_eval), dtype=np.int64), np.ones(len(score_attack_eval), dtype=np.int64)]),
        np.concatenate([score_ood_eval, score_attack_eval]),
    ))
    val_auc = float(roc_auc_score(y_val, score_val)) if len(np.unique(y_val)) == 2 else float("nan")
    fixed_threshold = float(np.quantile(score_id_calib, 0.99))
    calib_result = id_budget_calibrate(
        score_id_eval=score_id_calib,
        score_ood_eval=score_ood_eval,
        score_attack_high=score_attack_eval,
        budget=int(args.calibration_budget),
        target_alarm=float(args.calibration_target),
        seed=int(args.seed),
    )

    rows: List[Dict] = []
    object_label = "v7_source_rich_one_vs_benign_logistic"
    detector_family = "frontend_f2_v7_source_rich_diagnostic_ranker"
    score_label = "logistic_decision_function"
    extra = {
        "token_profile": "flat_source_rich_260",
        "source_mode": "source_rich_v1_frozen",
        "input_tensor": "source_rich_v1[20x13]_flat260",
        "model": "LogisticRegression_L2_balanced",
        "C": float(args.C),
        "validation_auc_threeway": val_auc,
    }
    add_score_rows(
        rows=rows,
        object_label=object_label,
        detector_family=detector_family,
        score_label=score_label,
        score_id_calib=score_id_calib,
        score_ood_eval=score_ood_eval,
        score_attack_eval=score_attack_eval,
        fixed_threshold=fixed_threshold,
        calib_result=calib_result,
        auc=auc,
        seed=int(args.seed),
        extra=extra,
    )
    df = pd.DataFrame(rows)
    combined = make_combined_summary(df, ID_CALIB_POLICY)

    row_scores = build_row_scores(
        score_id_calib=score_id_calib,
        score_ood_eval=score_ood_eval,
        score_attack_eval=score_attack_eval,
        id_calib_idx=id_calib_idx,
        ood_eval_idx=ood_eval_idx,
        attack_eval_idx=attack_eval_idx,
    )
    feature_importance = build_feature_importance(model.coef_.reshape(-1))

    df.to_csv(out / "frontend_f2_v7_source_rich_ranker_results.csv", index=False)
    df.to_csv(out / "results.csv", index=False)
    combined.to_csv(out / "frontend_f2_v7_source_rich_ranker_combined.csv", index=False)
    row_scores.to_csv(out / "frontend_f2_v7_source_rich_ranker_row_scores.csv", index=False)
    feature_importance.to_csv(out / "frontend_f2_v7_source_rich_ranker_feature_importance.csv", index=False)

    anchor_df = load_anchor_rows()
    if len(anchor_df):
        anchor_df.to_csv(out / "frontend_f2_v7_anchor_comparison.csv", index=False)

    split_info = {
        "id": {
            "train": [0, id_train_end],
            "val": [id_train_end, id_val_end],
            "calibration": [id_val_end, id_calib_end],
        },
        "ood": {
            "train": [0, ood_train_end],
            "val": [ood_train_end, ood_val_end],
            "eval": [ood_val_end, len(ood_x)],
        },
        "attack_high": {
            "total_high": int(len(high_idx)),
            "train_count": int(len(attack_split["train"])),
            "val_count": int(len(attack_split["val"])),
            "eval_count": int(len(attack_split["eval"])),
            "train_first_last": [int(attack_split["train"][0]), int(attack_split["train"][-1])],
            "val_first_last": [int(attack_split["val"][0]), int(attack_split["val"][-1])],
            "eval_first_last": [int(attack_split["eval"][0]), int(attack_split["eval"][-1])],
        },
    }
    metrics = {
        "auc_attack_high_eval_vs_ood_eval": auc,
        "val_auc": val_auc,
        "fixed_id_q99": {
            "threshold": fixed_threshold,
            "alarm": float(np.mean(score_ood_eval > fixed_threshold)),
            "det": float(np.mean(score_attack_eval > fixed_threshold)),
        },
        ID_CALIB_POLICY: calib_result,
    }
    config = {
        "stage": "frontend_f2_v7_source_rich_diagnostic_ranker",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "run_tag": args.run_tag,
        "seed": int(args.seed),
        "benign_data_dir": str(args.benign_data_dir),
        "attack_data_dir": str(args.attack_data_dir),
        "stage2_manifest": str(args.stage2_manifest),
        "model": {
            "type": "LogisticRegression",
            "penalty": "l2",
            "solver": "liblinear",
            "class_weight": "balanced",
            "C": float(args.C),
        },
        "split_info": split_info,
        "metrics": metrics,
        "outputs": {
            "results": str(out / "frontend_f2_v7_source_rich_ranker_results.csv"),
            "combined": str(out / "frontend_f2_v7_source_rich_ranker_combined.csv"),
            "row_scores": str(out / "frontend_f2_v7_source_rich_ranker_row_scores.csv"),
            "feature_importance": str(out / "frontend_f2_v7_source_rich_ranker_feature_importance.csv"),
            "summary": str(out / "summary.md"),
        },
    }
    (out / "frontend_f2_v7_source_rich_ranker_metadata.json").write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    anchor_md = tv3.md_table(anchor_df) if len(anchor_df) else "(anchor files not found)"
    combined_md = tv3.md_table(combined)
    top_features_md = tv3.md_table(feature_importance.head(20))
    target_pct = int(round(float(args.calibration_target) * 100))
    summary = "\n".join(
        [
            "# Frontend-F2 v7 Source-Rich Diagnostic Ranker",
            "",
            "- Input: frozen `source_rich_v1 [20,13]`, flattened to 260 dimensions.",
            "- Model: L2 LogisticRegression with balanced class weights.",
            "- Labels: ID benign + OOD benign = 0; stage2 high-purity attack = 1.",
            "- Attack high split: contiguous 60% train / 20% val / 20% eval by row index.",
            f"- Calibration: ID-calibration budget={args.calibration_budget}, target OOD alarm <= {args.calibration_target:.2f} ({target_pct}%).",
            "",
            "## v7 Result",
            combined_md,
            "",
            "## Anchor Comparison",
            anchor_md,
            "",
            "## Top Coefficients",
            top_features_md,
        ]
    ) + "\n"
    (out / "summary.md").write_text(summary, encoding="utf-8")

    print(f"[done] frontend-f2 v7 source-rich ranker output: {out}", flush=True)
    print(
        f"[result] auc={auc:.4f} alarm={calib_result['calibrated_ood_alarm']:.4f} "
        f"det={calib_result['calibrated_det']:.4f} feasible={calib_result['feasible']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
