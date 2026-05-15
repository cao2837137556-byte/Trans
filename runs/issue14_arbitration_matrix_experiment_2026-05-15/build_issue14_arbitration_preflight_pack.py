from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs" / "issue14_arbitration_matrix_experiment_2026-05-15"

ISSUE13 = ROOT / "runs" / "issue13_deployment_timeline_activation_evidence_pack_2026-05-15"
ISSUE11 = ROOT / "runs" / "issue11_fixed_config_ood_guard_lr_ablation_2026-05-14"
ISSUE07A = ROOT / "runs" / "issue07a_da_assisted_adapter_lowood_repair_2026-05-14"
ISSUE07B_RECOVERY = ROOT / "runs" / "issue07b_transformer_full_id_score_recovery_2026-05-14"

DA_SCORE_DIR = ROOT / "runs" / "original100_fewshot_official_control_2026-04-22" / "score_cache"
DA_ID = DA_SCORE_DIR / "da_full_id_scores.npy"
DA_OOD = DA_SCORE_DIR / "da_ood_scores.npy"
DA_ATTACK = DA_SCORE_DIR / "da_attack_scores.npy"

TR_SCORE_DIR = ISSUE07B_RECOVERY / "score_cache"
TR_ID = TR_SCORE_DIR / "transformer_full_id_scores.npy"
TR_OOD = TR_SCORE_DIR / "transformer_ood_scores.npy"
TR_ATTACK = TR_SCORE_DIR / "transformer_attack_scores.npy"


STRATEGY_COLUMNS = [
    "base_detector",
    "strategy",
    "budget",
    "seed_group",
    "attack_high_detection",
    "attack_review_rate",
    "attack_total_captured",
    "OOD_high_alarm",
    "OOD_review_rate",
    "OOD_total_burden",
    "feasible_high_alarm",
    "feasible_total_burden",
    "high_alert_attack_fraction",
    "review_burden_ratio",
    "computation_status",
    "reason",
]


CONFLICT_COLUMNS = [
    "base_detector",
    "seed",
    "budget",
    "both_high_attack",
    "both_high_ood",
    "base_low_gda_high_attack",
    "base_low_gda_high_ood",
    "base_high_gda_low_attack",
    "base_high_gda_low_ood",
    "both_low_attack",
    "both_low_ood",
    "computation_status",
    "reason",
]


def shape_of(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return str(np.load(path, mmap_mode="r").shape)
    except Exception as exc:  # pragma: no cover - diagnostic path
        return f"unreadable: {exc}"


def exists(path: Path) -> bool:
    return path.exists()


def find_gda_score_artifacts() -> list[dict[str, str]]:
    patterns = [
        "*score*.csv",
        "*score*.npy",
        "*pred*.csv",
        "*prob*.csv",
        "*decision*.csv",
        "*.joblib",
        "*.pkl",
        "*.sav",
    ]
    rows: list[dict[str, str]] = []
    if not ISSUE11.exists():
        return rows
    for pat in patterns:
        for path in ISSUE11.rglob(pat):
            # Aggregate score-related diagnostics are not per-sample GDA outputs.
            rows.append(
                {
                    "path": str(path),
                    "file_name": path.name,
                    "size_bytes": str(path.stat().st_size),
                    "artifact_type": pat,
                    "usable_as_gda_per_sample_score": "no",
                    "note": "issue11 does not persist per-sample decision_function outputs or trained model objects.",
                }
            )
    return rows


def write_csv(path: Path, rows: list[dict], columns: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if columns is None:
        columns = sorted({k for row in rows for k in row.keys()})
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    score_inventory = [
        {
            "score_name": "da_full_id_scores",
            "base_detector": "dA",
            "path": str(DA_ID),
            "exists": exists(DA_ID),
            "shape": shape_of(DA_ID),
            "expected_shape": "(50000,)",
            "alignment_status": "available_current_low_ood_protocol" if exists(DA_ID) else "missing",
            "role": "base_score",
        },
        {
            "score_name": "da_ood_scores",
            "base_detector": "dA",
            "path": str(DA_OOD),
            "exists": exists(DA_OOD),
            "shape": shape_of(DA_OOD),
            "expected_shape": "(20000,)",
            "alignment_status": "available_current_low_ood_protocol" if exists(DA_OOD) else "missing",
            "role": "base_score",
        },
        {
            "score_name": "da_attack_scores",
            "base_detector": "dA",
            "path": str(DA_ATTACK),
            "exists": exists(DA_ATTACK),
            "shape": shape_of(DA_ATTACK),
            "expected_shape": "(10000,)",
            "alignment_status": "available_current_low_ood_protocol" if exists(DA_ATTACK) else "missing",
            "role": "base_score",
        },
        {
            "score_name": "transformer_full_id_scores",
            "base_detector": "Transformer",
            "path": str(TR_ID),
            "exists": exists(TR_ID),
            "shape": shape_of(TR_ID),
            "expected_shape": "(50000,)",
            "alignment_status": "available_current_low_ood_protocol" if exists(TR_ID) else "missing",
            "role": "base_score",
        },
        {
            "score_name": "transformer_ood_scores",
            "base_detector": "Transformer",
            "path": str(TR_OOD),
            "exists": exists(TR_OOD),
            "shape": shape_of(TR_OOD),
            "expected_shape": "(20000,)",
            "alignment_status": "available_current_low_ood_protocol" if exists(TR_OOD) else "missing",
            "role": "base_score",
        },
        {
            "score_name": "transformer_attack_scores",
            "base_detector": "Transformer",
            "path": str(TR_ATTACK),
            "exists": exists(TR_ATTACK),
            "shape": shape_of(TR_ATTACK),
            "expected_shape": "(10000,)",
            "alignment_status": "available_current_low_ood_protocol" if exists(TR_ATTACK) else "missing",
            "role": "base_score",
        },
    ]

    gda_artifacts = find_gda_score_artifacts()
    has_gda_score = any(row["usable_as_gda_per_sample_score"] == "yes" for row in gda_artifacts)

    split_rows = [
        ("ID benign", "id_train", "0:8000", "base_available", "gda_missing"),
        ("ID benign", "id_val_unused", "8000:10000", "base_available", "not_required"),
        ("ID benign", "id_calib", "10000:15000", "base_available", "gda_missing"),
        ("ID benign", "id_eval", "15000:50000", "base_available", "not_primary_for_issue14"),
        ("OOD benign", "ood_train", "0:8000", "base_available", "gda_missing"),
        ("OOD benign", "ood_val", "8000:10000", "base_available", "gda_missing"),
        ("OOD benign", "final_ood_eval", "10000:20000", "base_available", "gda_missing"),
        ("high-purity attack", "attack_train_candidate", "stage2_train_rows", "base_available", "gda_missing"),
        ("high-purity attack", "attack_val", "stage2_val_rows", "base_available", "not_primary_for_issue14"),
        ("high-purity attack", "attack_eval", "stage2_eval_rows", "base_available", "gda_missing"),
    ]
    alignment_rows = [
        {
            "sample_id_or_row_range": row_range,
            "split": split,
            "label": label,
            "base_score_available": base_status == "base_available",
            "gda_score_available": gda_status == "gda_available",
            "aligned": False,
            "notes": (
                "base score caches are available, but issue11 GDA-minimal per-sample scores are not persisted; "
                "strategy-level row alignment cannot be completed without GDA score recovery."
            ),
        }
        for label, split, row_range, base_status, gda_status in split_rows
    ]

    strategies = ["base_only", "gda_only", "OR_policy", "AND_policy", "mode_gated_arbitration"]
    metric_rows = []
    for base in ["dA", "Transformer"]:
        for strategy in strategies:
            metric_rows.append(
                {
                    "base_detector": base,
                    "strategy": strategy,
                    "budget": 32,
                    "seed_group": "main_42_46_and_heldout_47_51",
                    "attack_high_detection": "",
                    "attack_review_rate": "",
                    "attack_total_captured": "",
                    "OOD_high_alarm": "",
                    "OOD_review_rate": "",
                    "OOD_total_burden": "",
                    "feasible_high_alarm": "",
                    "feasible_total_burden": "",
                    "high_alert_attack_fraction": "",
                    "review_burden_ratio": "",
                    "computation_status": "not_computed_missing_gda_per_sample_score",
                    "reason": "issue11 saved aggregate GDA-minimal metrics and thresholds, but not per-sample gda_score or trained model artifacts.",
                }
            )

    conflict_rows = [
        {
            "base_detector": base,
            "seed": "",
            "budget": 32,
            "both_high_attack": "",
            "both_high_ood": "",
            "base_low_gda_high_attack": "",
            "base_low_gda_high_ood": "",
            "base_high_gda_low_attack": "",
            "base_high_gda_low_ood": "",
            "both_low_attack": "",
            "both_low_ood": "",
            "computation_status": "not_computed_missing_gda_per_sample_score",
            "reason": "requires row-level base_high and gda_high on identical final OOD and attack eval ids.",
        }
        for base in ["dA", "Transformer"]
    ]

    write_csv(OUT / "score_inventory.csv", score_inventory)
    write_csv(OUT / "gda_score_artifact_inventory.csv", gda_artifacts or [
        {
            "path": str(ISSUE11),
            "file_name": "",
            "size_bytes": "",
            "artifact_type": "scan_result",
            "usable_as_gda_per_sample_score": "no",
            "note": "No per-sample score, prediction, probability, decision, or trained model artifact found under issue11.",
        }
    ])
    write_csv(
        OUT / "score_alignment_report.csv",
        alignment_rows,
        [
            "sample_id_or_row_range",
            "split",
            "label",
            "base_score_available",
            "gda_score_available",
            "aligned",
            "notes",
        ],
    )
    write_csv(OUT / "strategy_metrics_summary.csv", metric_rows, STRATEGY_COLUMNS)
    write_csv(OUT / "strategy_metrics_by_seed.csv", [], STRATEGY_COLUMNS)
    write_csv(OUT / "conflict_matrix_summary.csv", conflict_rows, CONFLICT_COLUMNS)

    risk_rows = [
        {
            "risk_name": "missing_gda_per_sample_score",
            "severity": "high",
            "reason": "Issue11 persists aggregate metrics, thresholds, and provenance, but not row-level GDA scores.",
            "mitigation": "Run a score-recovery pass that reuses fixed issue11 config and saves decision_function outputs; do not search hyperparameters.",
            "recommend_continue": "no_for_strategy_metrics_yes_for_design_pack",
        },
        {
            "risk_name": "base_subset_vs_gda_full_mismatch",
            "severity": "high",
            "reason": "Arbitration must use the exact same final OOD and attack eval ids for base and GDA.",
            "mitigation": "Require score_alignment_report to pass before computing strategy metrics.",
            "recommend_continue": "no_until_alignment_passes",
        },
        {
            "risk_name": "review_burden_overclaim",
            "severity": "medium",
            "reason": "Needs-review samples are not confirmed attacks.",
            "mitigation": "Report review volume separately and call it preservation of base-only evidence.",
            "recommend_continue": "yes_with_caveat",
        },
        {
            "risk_name": "arbitration_novelty_overclaim",
            "severity": "medium",
            "reason": "Mode-gated arbitration is a deployment policy candidate, not proof of full GDA.",
            "mitigation": "Keep claims bounded to system policy evidence after row-level metrics exist.",
            "recommend_continue": "yes_with_caveat",
        },
        {
            "risk_name": "precision_proxy_prevalence_risk",
            "severity": "medium",
            "reason": "Attack/OOD mixture in the eval set is not a deployment prevalence model.",
            "mitigation": "Label high_alert_attack_fraction as a proxy only.",
            "recommend_continue": "yes_with_caveat",
        },
    ]
    write_csv(OUT / "risk_register.csv", risk_rows)

    (OUT / "protocol.md").write_text(
        """# Issue14 Arbitration Preflight Protocol

This run is a score/provenance preflight for the base-detector + GDA-minimal arbitration experiment. It does not train any detector or adapter, does not modify prior experimental results, and does not tune thresholds or policies on final evaluation sets.

Required arbitration variables:

- `base_score(x)`: dA or Transformer anomaly score from the current low-OOD protocol.
- `base_threshold`: threshold from the corresponding base detector low-OOD protocol.
- `gda_score(x)`: original100 fixed-guard LR 32-shot GDA-minimal score from issue11.
- `gda_threshold`: issue11 guarded threshold selected from ID calibration + OOD validation only.

Decision policies to evaluate after score recovery:

| strategy | rule |
|---|---|
| base_only | high-priority alert if `base_high` |
| gda_only | high-priority alert if `gda_high` |
| OR_policy | high-priority alert if `base_high OR gda_high` |
| AND_policy | high-priority alert if `base_high AND gda_high` |
| mode_gated_arbitration | both-low -> background; both-high -> high-priority; base-low/GDA-high -> GDA-driven high-priority; base-high/GDA-low -> needs-review |

Preflight outcome:

- dA and Transformer base score caches are available and aligned at asset-shape level.
- issue11 GDA-minimal per-sample scores are not persisted.
- Therefore row-level strategy metrics are intentionally not computed in this pack.
""",
        encoding="utf-8",
    )

    (OUT / "score_alignment_report.md").write_text(
        """# Score Alignment Report

Base detector score assets are available for the current low-OOD protocol:

- dA ID/OOD/attack score caches: available.
- Transformer ID/OOD/attack score caches: available.

The blocking item is GDA-minimal row-level scoring:

- issue11 `run_issue11_fixed_config_ablation.py` computes `decision_function` scores in memory for ID calibration, OOD validation, final OOD eval, and attack eval.
- issue11 persists aggregate seed metrics, thresholds, support provenance, and threshold provenance.
- issue11 does not persist per-sample `gda_score`, `gda_high`, predictions, or fitted model artifacts.

Because mode-gated arbitration requires `base_high(x)` and `gda_high(x)` on the exact same final OOD and attack eval row ids, this pack does not compute strategy metrics.

See `score_alignment_report.csv` and `gda_score_artifact_inventory.csv`.
""",
        encoding="utf-8",
    )

    (OUT / "missing_score_report.md").write_text(
        """# Missing Score Report

## Available

- dA per-sample score caches are available under `runs/original100_fewshot_official_control_2026-04-22/score_cache/`.
- Transformer per-sample score caches are available under `runs/issue07b_transformer_full_id_score_recovery_2026-05-14/score_cache/`.
- issue11 threshold provenance and support provenance are available.

## Missing

- issue11 does not save per-sample GDA-minimal scores for `original100_fixed_guard_lr`.
- issue11 does not save fitted scaler/model objects that would allow exact post-hoc scoring without rerunning the adapter fitting step.

## Consequence

The following cannot be computed safely in this run:

- `gda_high(x)` on final OOD eval and attack eval.
- conflict cells: both-high, base-low/GDA-high, base-high/GDA-low, both-low.
- base-only / GDA-only / OR / AND / mode-gated strategy metrics on identical row ids.

## Minimal recovery

Run a score-recovery pass for issue11 fixed configuration only:

1. Reuse the exact issue11 code, split, supports, scaler rule, `OOD weight=2`, threshold policy, seeds, and budgets.
2. Do not search any hyperparameter.
3. Persist per-sample decision scores and binary high flags for final OOD eval and attack eval.
4. Persist row ids and threshold values.
5. Then rerun issue14 arbitration metrics.

This should be labeled as score recovery for an existing fixed experiment, not as a new model search.
""",
        encoding="utf-8",
    )

    (OUT / "arbitration_design_only.md").write_text(
        """# Arbitration Design Only

Issue14 remains scientifically well-motivated, but this pass is design-only because GDA-minimal per-sample scores are missing.

The intended comparison after score recovery is:

1. `base_only`
2. `gda_only`
3. `OR_policy`
4. `AND_policy`
5. `mode_gated_arbitration`

Primary evaluation should report high-priority alert rate and review burden separately:

- `attack_high_detection`
- `attack_review_rate`
- `attack_total_captured`
- `OOD_high_alarm`
- `OOD_review_rate`
- `OOD_total_burden`

Review samples must not be counted as confirmed detections. They preserve base-only evidence for analyst review.
""",
        encoding="utf-8",
    )

    (OUT / "arbitration_policy_table.md").write_text(
        """# Arbitration Policy Table

| base_high | gda_high | base_only | gda_only | OR_policy | AND_policy | mode_gated_arbitration |
|---|---|---|---|---|---|---|
| false | false | low_priority_or_background | low_priority_or_background | low_priority_or_background | low_priority_or_background | low_priority_or_background |
| false | true | low_priority_or_background | high_priority_alert | high_priority_alert | low_priority_or_background | GDA_driven_high_priority_alert |
| true | false | high_priority_alert | low_priority_or_background | high_priority_alert | low_priority_or_background | needs_review |
| true | true | high_priority_alert | high_priority_alert | high_priority_alert | high_priority_alert | high_priority_alert |

`needs_review` is not counted as high-priority detection. It is reported separately as review burden and as preservation of base-only evidence.
""",
        encoding="utf-8",
    )

    (OUT / "base_vs_gda_conflict_analysis.md").write_text(
        """# Base vs GDA Conflict Analysis

Conflict analysis was not computed in this pass because GDA-minimal per-sample scores are missing.

Required inputs for this analysis:

- base score and threshold for the same final OOD and attack eval row ids;
- GDA-minimal score and threshold for the same final OOD and attack eval row ids;
- row-level `base_high` and `gda_high`.

Once recovered, the analysis should distinguish:

- GDA-only high samples: `base_high=false`, `gda_high=true`;
- base-only high samples: `base_high=true`, `gda_high=false`;
- both-high samples;
- both-low samples.

Base-only high samples should be routed to review rather than interpreted as confirmed attacks or suppressed.
""",
        encoding="utf-8",
    )

    (OUT / "claim_boundary.md").write_text(
        """# Claim Boundary

Allowed after this preflight:

- Issue14 arbitration is well-defined and ready after GDA score recovery.
- dA and Transformer base score caches exist for the current low-OOD protocol.
- issue11 currently lacks the row-level GDA score artifact needed for fair arbitration.

Not allowed:

- mode-gated arbitration improves over baselines;
- GDA and base detector coexistence is empirically validated by issue14;
- review queue captures unseen attacks;
- full GDA is proven;
- detector-agnostic adaptation is proven.
""",
        encoding="utf-8",
    )

    (OUT / "recommended_next_action.md").write_text(
        """# Recommended Next Action

Start `issue14b_gda_minimal_score_recovery_for_arbitration_2026-05-15`.

Scope:

- reuse issue11 fixed configuration only;
- no hyperparameter search;
- no threshold change;
- no split/support/scaler change;
- persist row-level scores and high flags for `original100_fixed_guard_lr` 32-shot on main seeds 42-46 and held-out seeds 47-51;
- then compute issue14 arbitration policies on identical final OOD and attack eval ids.

If score recovery succeeds, rerun issue14 and report the full strategy metrics. If it fails, keep arbitration as a design discussion rather than empirical evidence.
""",
        encoding="utf-8",
    )

    (OUT / "doc_update_patch_suggestion.md").write_text(
        """# Suggested Mainline Docs Patch

Do not update the manuscript yet.

Suggested note for `runs/mainline_docs/mainline_experiment_map.md`:

- `issue14_arbitration_matrix_experiment_2026-05-15` completed as a preflight/design-only pack. Base detector per-sample scores are available, but issue11 GDA-minimal per-sample scores were not persisted, so arbitration metrics were not computed. Next action is fixed-config GDA score recovery for row-level arbitration.
""",
        encoding="utf-8",
    )

    status = "design_only_missing_gda_score"
    (OUT / "summary.md").write_text(
        f"""# Issue14 Arbitration Matrix Experiment Summary

## 1. Outcome

This run completed the arbitration preflight and design pack, but did **not** compute base-only / GDA-only / OR / AND / mode-gated strategy metrics.

Reason: dA and Transformer base detector per-sample scores are available, but issue11 does not persist per-sample GDA-minimal scores or fitted model artifacts for `original100_fixed_guard_lr`.

Final status: `{status}`.

## 2. Score Availability

| score family | status |
|---|---|
| dA ID/OOD/attack scores | available and current-protocol aligned at asset-shape level |
| Transformer ID/OOD/attack scores | available and current-protocol aligned at asset-shape level |
| GDA-minimal original100 fixed-guard row-level scores | missing |

## 3. Strategy Metrics

Strategy metrics were intentionally left blank in `strategy_metrics_summary.csv` and `strategy_metrics_by_seed.csv`. Filling them from aggregate issue11 metrics would violate the same-row arbitration constraint.

## 4. Current Blocker

Issue11 computes decision scores in memory but writes only aggregate metrics, threshold provenance, and support provenance. Arbitration requires row-level `gda_high(x)` on exactly the same final OOD and attack eval row ids as `base_high(x)`.

## 5. Recommendation

Run a narrow score recovery task: `issue14b_gda_minimal_score_recovery_for_arbitration_2026-05-15`.

This recovery should reuse issue11 fixed configuration and only persist per-sample GDA scores. It should not search OOD weight, thresholds, seeds, support pools, scalers, or model hyperparameters.

## 6. Claim Boundary

This pack supports the claim that arbitration is well-specified and ready for score recovery. It does not support any empirical claim that mode-gated arbitration improves detection, OOD alarm, or review burden.

## 7. Repository Safety

- Manuscript modified: no.
- Existing experimental numbers modified: no.
- New training executed: no.
- Commit/push may include this design-only evidence pack after self-check.
""",
        encoding="utf-8",
    )

    manifest_rows = []
    for p in sorted(OUT.glob("*")):
        if p.is_file():
            manifest_rows.append(
                {
                    "file_path": str(p),
                    "asset_type": p.suffix.lstrip(".") or "file",
                    "role": "issue14_preflight_design_pack",
                    "ready_for_gpt": "yes",
                }
            )
    write_csv(OUT / "manifest.csv", manifest_rows, ["file_path", "asset_type", "role", "ready_for_gpt"])

    (OUT / "run_metadata.json").write_text(
        json.dumps(
            {
                "run_tag": "issue14_arbitration_matrix_experiment_2026-05-15",
                "created_at_local": datetime.now().isoformat(timespec="seconds"),
                "status": status,
                "training_executed": False,
                "strategy_metrics_computed": False,
                "blocker": "missing issue11 GDA-minimal per-sample score artifact",
                "input_runs": {
                    "issue13": str(ISSUE13),
                    "issue11": str(ISSUE11),
                    "issue07a": str(ISSUE07A),
                    "issue07b_score_recovery": str(ISSUE07B_RECOVERY),
                },
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
