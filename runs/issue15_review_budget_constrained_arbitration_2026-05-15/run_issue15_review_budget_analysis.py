from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs" / "issue15_review_budget_constrained_arbitration_2026-05-15"
FIG_DIR = OUT / "figures"

ISSUE14B = ROOT / "runs" / "issue14b_gda_minimal_score_recovery_for_arbitration_2026-05-15"
ISSUE14 = ROOT / "runs" / "issue14_arbitration_matrix_experiment_2026-05-15"
ISSUE13 = ROOT / "runs" / "issue13_deployment_timeline_activation_evidence_pack_2026-05-15"

DA_SCORE_DIR = ROOT / "runs/original100_fewshot_official_control_2026-04-22/score_cache"
DA_OOD_SCORE = DA_SCORE_DIR / "da_ood_scores.npy"
DA_ATTACK_SCORE = DA_SCORE_DIR / "da_attack_scores.npy"

TR_SCORE_DIR = ROOT / "runs/issue07b_transformer_full_id_score_recovery_2026-05-14/score_cache"
TR_OOD_SCORE = TR_SCORE_DIR / "transformer_ood_scores.npy"
TR_ATTACK_SCORE = TR_SCORE_DIR / "transformer_attack_scores.npy"

TARGET_ALARM = 0.01
TOTAL_BURDEN_1PCT = 0.01
TOTAL_BURDEN_2PCT = 0.02
OOD_EVAL_START = 10000
BUDGET = 32
REVIEW_BUDGETS = [
    ("review_off", 0.0),
    ("review_top_0.25pct", 0.0025),
    ("review_top_0.5pct", 0.005),
    ("review_top_1pct", 0.01),
    ("review_top_2pct", 0.02),
    ("review_all", None),
]


def write_csv(path: Path, rows: List[Dict], columns: List[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if columns is None:
        columns = sorted({k for row in rows for k in row.keys()})
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


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
    return "\n".join(lines)


def seed_group(seed: int) -> str:
    return "main_paired_42_46" if seed <= 46 else "heldout_support_47_51"


def load_preflight() -> None:
    required = [
        ISSUE14B / "gda_recovery_validation.csv",
        ISSUE14B / "score_alignment_report.csv",
        ISSUE14B / "gda_minimal_row_level_scores.csv",
        ISSUE14B / "base_threshold_provenance.csv",
        ISSUE14B / "strategy_metrics_by_seed.csv",
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        (OUT / "missing_score_report.md").write_text(
            "# Missing Score Report\n\nMissing required issue14b assets:\n\n"
            + "\n".join(f"- {p}" for p in missing)
            + "\n",
            encoding="utf-8",
        )
        raise SystemExit("missing issue14b input")
    validation = pd.read_csv(ISSUE14B / "gda_recovery_validation.csv")
    align = pd.read_csv(ISSUE14B / "score_alignment_report.csv")
    if not bool(validation["passes"].all()):
        raise SystemExit("issue14b GDA recovery validation failed")
    if not bool((align["alignment_status"] == "passed").all()):
        raise SystemExit("issue14b score alignment did not pass")


def base_arrays(base_detector: str, threshold_map: Dict[str, float]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if base_detector == "dA":
        ood_scores = np.load(DA_OOD_SCORE, mmap_mode="r")[OOD_EVAL_START:]
        attack_scores_full = np.load(DA_ATTACK_SCORE, mmap_mode="r")
    elif base_detector == "Transformer":
        ood_scores = np.load(TR_OOD_SCORE, mmap_mode="r")[OOD_EVAL_START:]
        attack_scores_full = np.load(TR_ATTACK_SCORE, mmap_mode="r")
    else:
        raise ValueError(base_detector)

    # Attack eval row ids are stored in the GDA score table; use them for exact row alignment.
    gda_scores = pd.read_csv(ISSUE14B / "gda_minimal_row_level_scores.csv", usecols=["split", "row_id"]).drop_duplicates()
    attack_eval_ids = gda_scores[gda_scores["split"].eq("attack_eval")]["row_id"].sort_values().to_numpy(dtype=np.int64)
    attack_scores = np.asarray(attack_scores_full[attack_eval_ids], dtype=np.float64)
    base_threshold = threshold_map[base_detector]
    return (
        np.asarray(ood_scores, dtype=np.float64),
        attack_scores,
        np.asarray(ood_scores >= base_threshold, dtype=bool),
        np.asarray(attack_scores >= base_threshold, dtype=bool),
    )


def select_budgeted_review(
    *,
    review_candidate_score_ood: np.ndarray,
    review_candidate_score_attack: np.ndarray,
    review_candidate_ood: np.ndarray,
    review_candidate_attack: np.ndarray,
    budget_fraction: float | None,
    ood_eval_size: int,
) -> tuple[np.ndarray, np.ndarray, int]:
    if budget_fraction is None:
        return review_candidate_ood.copy(), review_candidate_attack.copy(), int(review_candidate_ood.sum())
    if budget_fraction <= 0:
        return np.zeros_like(review_candidate_ood, dtype=bool), np.zeros_like(review_candidate_attack, dtype=bool), 0

    budget_count = int(np.floor(ood_eval_size * budget_fraction))
    if budget_count <= 0:
        return np.zeros_like(review_candidate_ood, dtype=bool), np.zeros_like(review_candidate_attack, dtype=bool), 0

    scores = np.concatenate([review_candidate_score_ood[review_candidate_ood], review_candidate_score_attack[review_candidate_attack]])
    labels = np.concatenate(
        [
            np.zeros(int(review_candidate_ood.sum()), dtype=np.int8),
            np.ones(int(review_candidate_attack.sum()), dtype=np.int8),
        ]
    )
    # Stable deterministic ordering: sort by score descending, then label, then original packed index via mergesort.
    order = np.argsort(-scores, kind="mergesort")[: min(budget_count, len(scores))]
    selected_labels = labels[order]

    # Mark selected candidates in descending score order separately for OOD and attack.
    ood_selected_count = int(np.sum(selected_labels == 0))
    attack_selected_count = int(np.sum(selected_labels == 1))
    review_ood = np.zeros_like(review_candidate_ood, dtype=bool)
    review_attack = np.zeros_like(review_candidate_attack, dtype=bool)
    if ood_selected_count:
        ood_candidate_indices = np.flatnonzero(review_candidate_ood)
        ood_order = np.argsort(-review_candidate_score_ood[review_candidate_ood], kind="mergesort")[:ood_selected_count]
        review_ood[ood_candidate_indices[ood_order]] = True
    if attack_selected_count:
        attack_candidate_indices = np.flatnonzero(review_candidate_attack)
        attack_order = np.argsort(-review_candidate_score_attack[review_candidate_attack], kind="mergesort")[:attack_selected_count]
        review_attack[attack_candidate_indices[attack_order]] = True
    return review_ood, review_attack, budget_count


def metric_row(
    *,
    base_detector: str,
    seed: int,
    review_policy: str,
    review_budget_target: float | None,
    review_budget_count_target: int,
    gda_high_ood: np.ndarray,
    gda_high_attack: np.ndarray,
    review_ood: np.ndarray,
    review_attack: np.ndarray,
) -> Dict:
    high_ood = gda_high_ood
    high_attack = gda_high_attack
    high_alert_attack_count = int(high_attack.sum())
    high_alert_ood_count = int(high_ood.sum())
    review_count_attack = int(review_attack.sum())
    review_count_ood = int(review_ood.sum())
    review_total = review_count_attack + review_count_ood
    high_total = high_alert_attack_count + high_alert_ood_count
    return {
        "base_detector": base_detector,
        "seed": int(seed),
        "seed_group": seed_group(seed),
        "review_policy": review_policy,
        "review_budget_target": "all" if review_budget_target is None else float(review_budget_target),
        "review_budget_count_target": int(review_budget_count_target),
        "review_budget_used": int(review_total),
        "attack_high_detection": float(np.mean(high_attack)),
        "OOD_high_alarm": float(np.mean(high_ood)),
        "high_alert_attack_count": high_alert_attack_count,
        "high_alert_ood_count": high_alert_ood_count,
        "high_alert_attack_fraction": float(high_alert_attack_count / high_total) if high_total else np.nan,
        "attack_review_rate": float(np.mean(review_attack)),
        "OOD_review_rate": float(np.mean(review_ood)),
        "review_count_attack": review_count_attack,
        "review_count_ood": review_count_ood,
        "review_attack_fraction": float(review_count_attack / review_total) if review_total else np.nan,
        "incremental_attack_captured_by_review": float(np.mean(review_attack)),
        "incremental_ood_burden_by_review": float(np.mean(review_ood)),
        "attack_total_captured": float(np.mean(high_attack | review_attack)),
        "OOD_total_burden": float(np.mean(high_ood | review_ood)),
        "feasible_high_alarm": bool(np.mean(high_ood) <= TARGET_ALARM),
        "feasible_total_burden_1pct": bool(np.mean(high_ood | review_ood) <= TOTAL_BURDEN_1PCT),
        "feasible_total_burden_2pct": bool(np.mean(high_ood | review_ood) <= TOTAL_BURDEN_2PCT),
        "attack_captured_per_100_review": float(100.0 * review_count_attack / review_total) if review_total else np.nan,
        "ood_review_per_attack_review": float(review_count_ood / review_count_attack) if review_count_attack else np.nan,
    }


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "review_budget_used",
        "attack_high_detection",
        "OOD_high_alarm",
        "attack_review_rate",
        "OOD_review_rate",
        "attack_total_captured",
        "OOD_total_burden",
        "review_attack_fraction",
        "high_alert_attack_fraction",
        "attack_captured_per_100_review",
    ]
    return df.groupby(["base_detector", "seed_group", "review_policy", "review_budget_target"], as_index=False).agg(
        n_seeds=("seed", "nunique"),
        **{f"{c}_mean": (c, "mean") for c in cols},
        **{f"{c}_min": (c, "min") for c in cols},
        **{f"{c}_max": (c, "max") for c in cols},
        feasible_high_alarm_rate=("feasible_high_alarm", "mean"),
        feasible_total_burden_1pct_rate=("feasible_total_burden_1pct", "mean"),
        feasible_total_burden_2pct_rate=("feasible_total_burden_2pct", "mean"),
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    (OUT / "command.txt").write_text("python " + " ".join(__import__("sys").argv) + "\n", encoding="utf-8")
    load_preflight()

    threshold_df = pd.read_csv(ISSUE14B / "base_threshold_provenance.csv")
    threshold_map = {row.base_detector: float(row.threshold) for row in threshold_df.itertuples(index=False)}
    gda = pd.read_csv(ISSUE14B / "gda_minimal_row_level_scores.csv")

    rows = []
    queue_rows = []
    for base_detector in ["dA", "Transformer"]:
        base_ood_score, base_attack_score, base_high_ood, base_high_attack = base_arrays(base_detector, threshold_map)
        for seed, seed_df in gda.groupby("seed"):
            ood_seed = seed_df[seed_df["split"].eq("final_ood_eval")].sort_values("row_id")
            attack_seed = seed_df[seed_df["split"].eq("attack_eval")].sort_values("row_id")
            gda_high_ood = ood_seed["gda_high"].astype(bool).to_numpy()
            gda_high_attack = attack_seed["gda_high"].astype(bool).to_numpy()
            review_candidate_ood = base_high_ood & ~gda_high_ood
            review_candidate_attack = base_high_attack & ~gda_high_attack
            queue_rows.append(
                {
                    "base_detector": base_detector,
                    "seed": int(seed),
                    "seed_group": seed_group(int(seed)),
                    "split": "combined_final_ood_and_attack_eval",
                    "base_only_high_count": int(review_candidate_ood.sum() + review_candidate_attack.sum()),
                    "base_only_high_attack_count": int(review_candidate_attack.sum()),
                    "base_only_high_ood_count": int(review_candidate_ood.sum()),
                    "attack_fraction": float(review_candidate_attack.sum() / (review_candidate_ood.sum() + review_candidate_attack.sum()))
                    if (review_candidate_ood.sum() + review_candidate_attack.sum())
                    else np.nan,
                    "ood_fraction": float(review_candidate_ood.sum() / (review_candidate_ood.sum() + review_candidate_attack.sum()))
                    if (review_candidate_ood.sum() + review_candidate_attack.sum())
                    else np.nan,
                }
            )
            for policy_name, budget_fraction in REVIEW_BUDGETS:
                review_ood, review_attack, target_count = select_budgeted_review(
                    review_candidate_score_ood=base_ood_score,
                    review_candidate_score_attack=base_attack_score,
                    review_candidate_ood=review_candidate_ood,
                    review_candidate_attack=review_candidate_attack,
                    budget_fraction=budget_fraction,
                    ood_eval_size=len(base_ood_score),
                )
                rows.append(
                    metric_row(
                        base_detector=base_detector,
                        seed=int(seed),
                        review_policy=policy_name,
                        review_budget_target=budget_fraction,
                        review_budget_count_target=target_count,
                        gda_high_ood=gda_high_ood,
                        gda_high_attack=gda_high_attack,
                        review_ood=review_ood,
                        review_attack=review_attack,
                    )
                )

    by_seed = pd.DataFrame(rows)
    summary = summarize(by_seed)
    queue = pd.DataFrame(queue_rows)
    by_seed.to_csv(OUT / "review_budget_metrics_by_seed.csv", index=False)
    summary.to_csv(OUT / "review_budget_metrics_summary.csv", index=False)
    queue.to_csv(OUT / "review_queue_composition.csv", index=False)

    focus = summary[
        (summary["base_detector"].eq("dA"))
        & (summary["seed_group"].isin(["main_paired_42_46", "heldout_support_47_51"]))
    ][
        [
            "seed_group",
            "review_policy",
            "review_budget_used_mean",
            "attack_high_detection_mean",
            "attack_review_rate_mean",
            "attack_total_captured_mean",
            "OOD_high_alarm_mean",
            "OOD_review_rate_mean",
            "OOD_total_burden_mean",
            "review_attack_fraction_mean",
            "feasible_high_alarm_rate",
            "feasible_total_burden_2pct_rate",
        ]
    ]

    (OUT / "protocol.md").write_text(
        """# Issue15 Review-Budget Constrained Arbitration Protocol

This analysis reads issue14b row-level base/GDA scores and does not train or retune any model.

Review queue definition:

- `base_high = base_score >= base_threshold`
- `gda_high = gda_score >= gda_threshold`
- review queue = `base_high=true` and `gda_high=false`

High-priority alerts are controlled by GDA-minimal. Review samples are not counted as high-priority detections and are not confirmed attacks.

Budget policy:

- `review_off`: no review queue.
- `review_all`: all base-only high rows enter review.
- `review_top_0.25pct`, `review_top_0.5pct`, `review_top_1pct`, `review_top_2pct`: select top base-score review candidates using a pre-specified budget relative to final OOD eval size.

All budgets are reported; no final-eval selection of a best budget is performed.
""",
        encoding="utf-8",
    )

    (OUT / "review_policy_comparison.md").write_text(
        """# Review Policy Comparison

- `review_off`: equivalent to GDA-only high-priority alerting.
- `review_all`: full mode-gated review queue from issue14b.
- `review_top_0.25pct` to `review_top_2pct`: bounded review queue using base-score ranking inside base-high/GDA-low candidates.

The review budget controls operational review burden. It does not alter the GDA guarded threshold and does not change high-priority OOD alarm.
""",
        encoding="utf-8",
    )

    (OUT / "review_burden_tradeoff.md").write_text(
        """# Review Burden Tradeoff

High-priority alert burden and review burden are separate operational budgets.

- High-priority burden is controlled by GDA-minimal and remains the primary low-OOD alarm metric.
- Review burden comes from base-high/GDA-low conflicts and should be interpreted as a safety-net queue.
- Review rows are not confirmed attacks.
- `attack_total_captured` includes review rows only as captured-for-review, not as high-priority detections.
""",
        encoding="utf-8",
    )

    (OUT / "gda_only_vs_mode_gated_with_budget.md").write_text(
        """# GDA-only vs Budgeted Mode-Gated Arbitration

GDA-only corresponds to `review_off`.

Budgeted mode-gated arbitration preserves the same high-priority GDA channel and adds a bounded review queue for base-high/GDA-low conflicts. Its value should be judged by whether the added review burden is operationally acceptable and whether it preserves useful base-only attack evidence.

If review attack gain is weak, the conservative paper framing is: GDA-minimal is the main high-priority alerting channel, while review is an optional safety-net mechanism.
""",
        encoding="utf-8",
    )

    (OUT / "claim_boundary.md").write_text(
        """# Claim Boundary

Allowed:

- mode-gated arbitration can preserve base-detector evidence through a bounded review queue.
- high-priority detection remains controlled by GDA-minimal under the low-OOD alarm constraint.
- review queue size and composition quantify deployment burden.

Forbidden:

- review samples are confirmed attacks.
- review budget proves unseen-attack detection.
- arbitration completes full GDA.
- detector-agnostic adaptation is proven.
- GDA replaces the base detector.
""",
        encoding="utf-8",
    )

    risk_rows = [
        {
            "risk_name": "review_false_positive_burden",
            "severity": "medium",
            "reason": "Review queue may include mostly OOD benign rows.",
            "mitigation": "Report OOD review rate and review_attack_fraction.",
            "recommend_continue": "yes_with_caveat",
        },
        {
            "risk_name": "review_attack_gain_weak",
            "severity": "medium",
            "reason": "Base-only high rows may add little attack capture.",
            "mitigation": "Frame review as safety net rather than main detection gain.",
            "recommend_continue": "yes_with_caveat",
        },
        {
            "risk_name": "prevalence_proxy_risk",
            "severity": "medium",
            "reason": "Review composition depends on the constructed eval mix.",
            "mitigation": "Use composition as label-mixture proxy only.",
            "recommend_continue": "yes_with_caveat",
        },
        {
            "risk_name": "overclaiming_safety_net",
            "severity": "high",
            "reason": "No unseen-attack labels are present.",
            "mitigation": "Do not claim unseen attack detection.",
            "recommend_continue": "yes_with_boundary",
        },
    ]
    pd.DataFrame(risk_rows).to_csv(OUT / "risk_register.csv", index=False)

    main_queue = queue[(queue["base_detector"].eq("dA")) & (queue["seed_group"].eq("main_paired_42_46"))]
    held_queue = queue[(queue["base_detector"].eq("dA")) & (queue["seed_group"].eq("heldout_support_47_51"))]
    main_review_all = focus[(focus["seed_group"].eq("main_paired_42_46")) & (focus["review_policy"].eq("review_all"))].iloc[0]
    held_review_all = focus[(focus["seed_group"].eq("heldout_support_47_51")) & (focus["review_policy"].eq("review_all"))].iloc[0]

    (OUT / "summary.md").write_text(
        f"""# Issue15 Review-Budget Constrained Arbitration Summary

## 1. Outcome

Issue15 successfully read issue14b row-level scores and computed review-budget constrained arbitration metrics. No model was trained, no threshold was changed, and no manuscript file was modified.

Main analysis uses dA as the base detector; Transformer is reported as secondary in the CSV tables.

## 2. Review Queue Scale

For dA base detector:

- Main seeds 42-46 review-all queue size mean: {main_review_all.review_budget_used_mean:.2f} rows.
- Held-out seeds 47-51 review-all queue size mean: {held_review_all.review_budget_used_mean:.2f} rows.
- Main review-all OOD review rate: {main_review_all.OOD_review_rate_mean:.6f}.
- Held-out review-all OOD review rate: {held_review_all.OOD_review_rate_mean:.6f}.

## 3. Review Composition

Mean base-only/GDA-low queue composition:

- Main seeds attack fraction: {main_queue.attack_fraction.mean():.6f}.
- Held-out seeds attack fraction: {held_queue.attack_fraction.mean():.6f}.

This should be interpreted as a label-mixture diagnostic, not deployment precision.

## 4. Budget Results

{md_table(focus)}

## 5. Interpretation

GDA-minimal remains the high-priority alerting channel. Budgeted review can preserve base-only evidence with an explicit operational burden, but review samples are not confirmed attacks.

If the paper needs a conservative framing, use: GDA-only for primary low-OOD high-priority alerts, plus optional bounded review queue as a safety-net deployment mechanism.
""",
        encoding="utf-8",
    )

    (OUT / "recommended_next_action.md").write_text(
        """# Recommended Next Action

If using issue15 in the paper, keep it in the deployment-system discussion rather than the core method proof.

Recommended framing:

- GDA-minimal is the main high-priority alerting channel.
- Budgeted review is an optional safety-net mechanism for base-high/GDA-low conflicts.
- Review burden should be reported separately from OOD high-priority alarm.

Next experiments should prioritize harder holdout or second-environment validation over further review-queue polishing, unless the paper specifically needs a deployment operations subsection.
""",
        encoding="utf-8",
    )

    (OUT / "doc_update_patch_suggestion.md").write_text(
        """# Suggested Mainline Docs Patch

Suggested note:

- `issue15_review_budget_constrained_arbitration_2026-05-15` quantifies review queue burden for mode-gated arbitration. GDA-minimal remains the high-priority alerting channel; budgeted review is a bounded safety-net queue and should not be written as confirmed attack detection.
""",
        encoding="utf-8",
    )

    metadata = {
        "run_tag": "issue15_review_budget_constrained_arbitration_2026-05-15",
        "created_at_local": datetime.now().isoformat(timespec="seconds"),
        "input_runs": {
            "issue14b": str(ISSUE14B),
            "issue14_preflight": str(ISSUE14),
            "issue13": str(ISSUE13),
        },
        "training_executed": False,
        "threshold_changed": False,
        "manuscript_modified": False,
        "review_budget_policies": [name for name, _ in REVIEW_BUDGETS],
    }
    (OUT / "run_metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    manifest_rows = []
    for p in sorted(OUT.rglob("*")):
        if p.is_file():
            manifest_rows.append(
                {
                    "file_path": str(p),
                    "size_bytes": p.stat().st_size,
                    "role": "issue15_review_budget_analysis",
                    "ready_for_gpt": "yes",
                }
            )
    pd.DataFrame(manifest_rows).to_csv(OUT / "manifest.csv", index=False)


if __name__ == "__main__":
    main()
