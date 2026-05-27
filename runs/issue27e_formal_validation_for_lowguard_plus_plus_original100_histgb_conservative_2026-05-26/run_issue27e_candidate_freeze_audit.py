from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs" / "issue27e_formal_validation_for_lowguard_plus_plus_original100_histgb_conservative_2026-05-26"
ISSUE27D = ROOT / "runs" / "issue27d_lowguard_adapter_interface_and_model_specific_objectives_smoke_2026-05-26"
ISSUE27C = ROOT / "runs" / "issue27c_lowguard_mechanism_falsification_and_head_specificity_audit_2026-05-26"
ISSUE25C = ROOT / "runs" / "issue25c_strong_baseline_pack_execution_for_enhanced_lowguard_top64_2026-05-18"
ISSUE23 = ROOT / "runs" / "issue23_locked_validation_for_enhanced_v2_top64_2026-05-18"

LOCKED_BINS = ["holdout_bin_5", "holdout_bin_6", "holdout_bin_7", "holdout_bin_8"]
FULL_SEEDS = list(range(42, 52))
SMOKE_SEEDS = [42, 43, 44]
PRIMARY_VERDICT = "candidate_config_not_recoverable_needs_debug"
NEXT_ACTION = "issue27f_candidate_config_freeze_and_formal_validation_for_original100_histgb_conservative"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def md_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    if max_rows is not None:
        df = df.head(max_rows).copy()
    if df.empty:
        return "_No rows._\n"
    lines = ["| " + " | ".join(df.columns) + " |", "|" + "|".join(["---"] * len(df.columns)) + "|"]
    for _, row in df.iterrows():
        vals: list[str] = []
        for value in row:
            if isinstance(value, (float, np.floating)):
                vals.append("" if np.isnan(float(value)) else f"{float(value):.6f}")
            else:
                vals.append(str(value))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"


def require_inputs() -> list[str]:
    required = [
        ISSUE27D / "summary.md",
        ISSUE27D / "stageA_interface_preflight_report.md",
        ISSUE27D / "adapter_leakage_check.csv",
        ISSUE27D / "histgb_conservative_selection_trace.csv",
        ISSUE27D / "histgb_conservative_locked_summary.csv",
        ISSUE27D / "model_specific_objective_locked_summary.csv",
        ISSUE27D / "model_specific_objective_vs_lr.csv",
        ISSUE27D / "original100_vs_top64_model_specific_comparison.csv",
        ISSUE27D / "lowguard_plus_plus_candidate_report.csv",
        ISSUE27D / "claim_update_after_issue27d.md",
        ISSUE27C / "summary.md",
        ISSUE25C / "summary.md",
        ISSUE25C / "baseline_method_comparison_by_seed.csv",
        ISSUE23 / "locked_validation_asset_report.md",
        ROOT / "runs" / "mainline_docs" / "mainline_handoff.md",
        ROOT / "runs" / "mainline_docs" / "mainline_experiment_map.md",
    ]
    return [str(path) for path in required if not path.exists()]


def empty_csv(path: Path, columns: list[str], reason: str) -> None:
    pd.DataFrame([{col: "" for col in columns} | {"not_run_reason": reason}]).to_csv(path, index=False)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    missing = require_inputs()
    write_text(OUT / "missing_input_report.md", "# Missing Input Report\n\n" + ("none" if not missing else "\n".join(f"- {x}" for x in missing)))
    if missing:
        raise RuntimeError(f"Missing required inputs: {missing}")

    trace = pd.read_csv(ISSUE27D / "histgb_conservative_selection_trace.csv")
    config_matrix = pd.read_csv(ISSUE27D / "histgb_conservative_config_matrix.csv")
    locked = pd.read_csv(ISSUE27D / "model_specific_objective_locked_summary.csv")
    plus = pd.read_csv(ISSUE27D / "lowguard_plus_plus_candidate_report.csv")
    leakage = pd.read_csv(ISSUE27D / "adapter_leakage_check.csv")

    selected = trace[(trace["representation"].eq("original100")) & (trace["selected"].astype(str).str.lower().eq("true"))].copy()
    selected = selected[selected["holdout"].isin(LOCKED_BINS) & selected["seed"].isin(SMOKE_SEEDS)]
    selected_counts = selected.groupby("config_id", as_index=False).agg(
        selected_count=("config_id", "size"),
        selected_holdouts=("holdout", lambda s: ";".join(sorted(set(map(str, s))))),
        selected_seeds=("seed", lambda s: ";".join(map(str, sorted(set(map(int, s)))))),
        validation_target_values=("validation_target", lambda s: ";".join(map(str, sorted(set(map(float, s)))))),
        mean_ood_val_alarm=("ood_val_alarm_at_selection", "mean"),
        max_ood_val_alarm=("ood_val_alarm_at_selection", "max"),
        mean_support_val_detection=("support_val_detection", "mean"),
        mean_support_val_margin=("support_val_margin_median", "mean"),
    )
    freeze = selected.merge(config_matrix[config_matrix["representation"].eq("original100")], on=["representation", "config_id"], how="left", suffixes=("", "_config"))
    freeze["candidate_recoverability"] = "not_unique" if selected_counts["config_id"].nunique() != 1 else "unique"
    freeze["formal_validation_allowed"] = selected_counts["config_id"].nunique() == 1
    freeze["freeze_blocker"] = np.where(
        freeze["formal_validation_allowed"],
        "",
        "issue27d selected two HistGB-Conservative configs across smoke bins/seeds; formal protocol requires one frozen candidate config",
    )
    freeze.to_csv(OUT / "candidate_config_freeze_table.csv", index=False)

    unique_count = int(selected_counts["config_id"].nunique())
    formal_allowed = unique_count == 1
    assert not formal_allowed, "This audit script is for the non-unique freeze case."

    issue27d_candidate = plus.copy()
    issue27d_candidate.to_csv(OUT / "formal_vs_issue27d_smoke.csv", index=False)
    lr_ref = locked[(locked["head_id"].eq("LOW_GUARD_LR")) & (locked["representation"].eq("source_rich_top64"))].copy()
    candidate_smoke = locked[(locked["head_id"].eq("LOW_GUARD_HistGB_Conservative")) & (locked["representation"].eq("original100"))].copy()
    compare_lr = pd.concat([lr_ref.assign(role="lowguard_lr_reference"), candidate_smoke.assign(role="issue27d_candidate_smoke")], ignore_index=True)
    compare_lr.to_csv(OUT / "formal_vs_lowguard_lr_reference.csv", index=False)

    not_run = "candidate_config_not_uniquely_recoverable_from_issue27d_selection_trace"
    by_seed_cols = [
        "method",
        "seed",
        "holdout",
        "attack_detection",
        "final_ood_alarm",
        "id_calib_alarm",
        "ood_val_alarm",
        "threshold",
        "feasible_under_1pct",
        "roc_auc_attack_vs_ood",
        "pr_auc_attack_vs_ood",
        "tpr_at_fpr_1pct",
        "pauc_fpr_1pct",
        "train_time",
        "inference_time",
        "param_count",
        "selected_config_id",
        "final_eval_used_for_selection",
        "representation",
        "head",
        "protocol",
        "relaxed_validation_target_used",
    ]
    empty_csv(OUT / "formal_locked_by_seed.csv", by_seed_cols, not_run)
    empty_csv(
        OUT / "formal_locked_summary.csv",
        [
            "method",
            "representation",
            "head",
            "locked_detection_mean",
            "locked_detection_min",
            "locked_ood_alarm_max",
            "feasible_rate",
            "dominates_lowguard_lr",
            "primary_verdict",
        ],
        not_run,
    )
    empty_csv(
        OUT / "threshold_target_robustness_by_seed.csv",
        ["target", "seed", "holdout", "attack_detection", "final_ood_alarm", "feasible_under_1pct"],
        not_run,
    )
    empty_csv(
        OUT / "threshold_target_robustness_summary.csv",
        ["target", "locked_detection_mean", "locked_detection_min", "locked_ood_alarm_max", "feasible_rate"],
        not_run,
    )

    leakage_table = pd.DataFrame(
        [
            {
                "audit_item": "candidate_config_recoverable",
                "status": "fail",
                "risk_level": "high",
                "evidence": f"{unique_count} selected configs recovered from issue27d smoke",
                "action": "stop formal validation; freeze one candidate config before using final eval",
            },
            {
                "audit_item": "final_eval_used_for_issue27e_selection",
                "status": "pass",
                "risk_level": "low",
                "evidence": "issue27e stopped before formal final-eval run",
                "action": "none",
            },
            {
                "audit_item": "issue27d_final_eval_leakage",
                "status": "pass" if not leakage["final_eval_used_for_selection"].astype(str).str.lower().eq("true").any() else "fail",
                "risk_level": "low",
                "evidence": "adapter_leakage_check.csv reports no final-eval selection",
                "action": "carry forward final-eval exclusion",
            },
            {
                "audit_item": "support_eval_overlap",
                "status": "pass" if not leakage["support_overlaps_attack_eval"].astype(str).str.lower().eq("true").any() else "fail",
                "risk_level": "low",
                "evidence": "adapter_leakage_check.csv reports no support/attack_eval overlap",
                "action": "none",
            },
            {
                "audit_item": "representation_leakage",
                "status": "not_evaluated",
                "risk_level": "unknown",
                "evidence": "formal run stopped before direct original100 field audit",
                "action": "include original100 feature provenance audit in issue27f",
            },
        ]
    )
    leakage_table.to_csv(OUT / "formal_leakage_audit_table.csv", index=False)

    representation_table = pd.DataFrame(
        [
            {
                "question": "why_original100_candidate",
                "current_answer": "issue27d smoke suggests conservative HistGB uses nonlinear structure retained in original100",
                "evidence_status": "smoke_only",
                "claim_allowed": "candidate for formal validation, not validated performance instance",
            },
            {
                "question": "top64_linearization",
                "current_answer": "top64 still favors LOW-GUARD-LR; no top64 non-LR dominated LR in issue27d",
                "evidence_status": "bounded_smoke",
                "claim_allowed": "representation/head interaction is plausible",
            },
            {
                "question": "dual_instance_story",
                "current_answer": "possible but blocked until one HistGB config is frozen and formally validated",
                "evidence_status": "pending_issue27f",
                "claim_allowed": "not yet",
            },
        ]
    )
    representation_table.to_csv(OUT / "representation_control_table.csv", index=False)

    write_text(
        OUT / "candidate_config_freeze_report.md",
        f"""
# Candidate Config Freeze Report

## Result

- candidate: `LOW_GUARD_HistGB_Conservative + original100`
- freeze_status: `not_recoverable_as_single_config`
- recovered_selected_config_count: `{unique_count}`
- formal_validation_allowed: `false`

## Recovered selected configs from issue27d

{md_table(selected_counts)}

## Why this blocks formal validation

The issue27d candidate was reported as an aggregate smoke result, but the original100 HistGB-Conservative selection trace does not identify one unique frozen `selected_config_id`. It selects two configs across the 12 smoke bin/seed combinations. Running full seeds with either one chosen after seeing the smoke aggregate would risk hindsight selection; running both and picking after final eval would be formal-validation leakage.

Therefore issue27e stops before full locked seed validation, as required by the Stage A rule.
""",
    )

    write_text(
        OUT / "formal_leakage_audit.md",
        f"""
# Formal Leakage Audit

## Verdict

`{PRIMARY_VERDICT}`

No issue27e final-eval leakage occurred because the formal locked validation was not run after the candidate freeze blocker was found.

## Main risk

The main risk is not final-eval leakage inside issue27e; it is candidate-freeze ambiguity inherited from issue27d. The smoke candidate is a `selection-policy / aggregate` candidate, not yet a single frozen method instance.

## Required fix

Before formal validation, issue27f must freeze one of the following without using final OOD eval or attack eval:

{md_table(selected_counts[["config_id", "selected_count", "validation_target_values", "mean_ood_val_alarm", "mean_support_val_detection"]])}

The freeze rule may use only issue27d support-validation / OOD-validation traces, simplicity, and pre-registered low-alert constraints.
""",
    )

    write_text(
        OUT / "representation_control_interpretation.md",
        """
# Representation-Control Interpretation

issue27d remains important: original100 + HistGB-Conservative looked much stronger than top64 non-LR heads, suggesting the top64 representation may expose a linear direction that helps LR while discarding nonlinear structure useful to conservative trees.

However, issue27e cannot yet elevate that observation into a formal LOW-GUARD++ claim because the candidate configuration is not uniquely frozen. The correct interpretation is:

- LOW-GUARD-LR remains the demonstrated top64 minimal instance.
- original100 + HistGB-Conservative is a serious performance-instance candidate.
- A dual-instance paper story is plausible: LOW-GUARD-LR as minimal instance, LOW-GUARD-HistGB as performance instance.
- That story requires issue27f formal validation with a single frozen config or a pre-registered two-instance sensitivity design with no post-hoc selection.

Claims remain bounded to tested representations, tested heads, and the locked low-alert protocol.
""",
    )

    decision_text = f"""
# LOW-GUARD++ Formal Decision

## Primary Verdict

`{PRIMARY_VERDICT}`

## Formal pass conditions

- locked mean > LOW-GUARD-LR: `not_evaluated`
- locked min >= LOW-GUARD-LR: `not_evaluated`
- locked OOD max <= 0.01: `not_evaluated`
- feasible_rate >= 0.975: `not_evaluated`
- no final eval leakage: `pass`
- frozen config recoverable: `fail`
- full seeds stable: `not_evaluated`
- no single-bin catastrophic failure: `not_evaluated`

## Decision

Do not upgrade to LOW-GUARD++ yet. The candidate is promising but not formally validated because the frozen config is not uniquely recoverable.
"""
    write_text(OUT / "lowguard_plus_plus_formal_decision.md", decision_text)

    claim_text = """
# Claim Update After Issue27e

## Allowed after issue27e

- issue27d identified original100 + HistGB-Conservative as a promising LOW-GUARD++ smoke candidate.
- issue27e audited the candidate-freeze gate and found that the config is not uniquely recoverable.
- LOW-GUARD-LR remains the demonstrated strongest stable instance until a single HistGB candidate is frozen and formally validated.

## Still not allowed

- LOW-GUARD++ is formally validated.
- The main method is upgraded to HistGB.
- HistGB universally dominates LR.
- LOW-GUARD works for all models.
- Cross-dataset generalization is proven.
- Temporal generalization is proven.
- Deployment robustness is proven.
- Final eval was used for model selection.
"""
    write_text(OUT / "claim_update_after_issue27e.md", claim_text)

    reviewer = """
# Reviewer Defense: LOW-GUARD++ Candidate Freeze

## Q1: Why did you not run the full formal validation?

Because the issue27d candidate was not a single frozen configuration. Two HistGB-Conservative configs were selected across the smoke bins/seeds. A formal run after choosing one post hoc would risk hindsight model selection.

## Q2: Is the LOW-GUARD++ candidate invalid?

No. It remains promising. The blocker is protocol hygiene: the candidate must be frozen before final-eval reporting.

## Q3: Did issue27e use final eval to choose a config?

No. issue27e stopped before the formal run.

## Q4: What is the correct next experiment?

Freeze a candidate config using only support-validation / OOD-validation evidence and pre-registered simplicity rules, then run full locked seeds.

## Q5: Can the paper claim LOW-GUARD++ now?

No. The allowed claim is that a strong original100 HistGB candidate was found in smoke and needs formal validation.
"""
    write_text(OUT / "reviewer_defense_lowguard_plus_plus.md", reviewer)

    next_doc = f"""
# Issue27f Next Action

## Recommendation

`{NEXT_ACTION}`

## Goal

Recover a formal candidate by freezing exactly one original100 HistGB-Conservative config before any full final-eval reporting.

## Recommended freeze rule

Use only issue27d selection trace fields:

1. OOD validation feasibility under the candidate target.
2. support validation detection / margin.
3. simplicity and lower target alarm as tie breakers.
4. no final OOD eval or attack eval.

Then run the full seeds locked validation for the frozen config.

## Not recommended

- Do not choose by issue27d final locked detection.
- Do not run both configs and pick the better final result.
- Do not change representation, add new models, or tune topK/support.
"""
    write_text(OUT / "issue27f_next_action.md", next_doc)

    summary = f"""
# Issue27e Formal LOW-GUARD++ Validation Summary

## Verdict

- primary_verdict: `{PRIMARY_VERDICT}`
- formal_locked_validation_executed: `false`
- recommended_next_action: `{NEXT_ACTION}`

## 1. Candidate config recovery

The issue27d candidate config was not uniquely recoverable. The original100 HistGB-Conservative smoke selected `{unique_count}` configs across locked bins `5/6/7/8` and seeds `42/43/44`.

{md_table(selected_counts)}

## 2. Full locked seed validation

Not executed. The Stage A rule requires stopping when a unique frozen candidate config cannot be recovered.

## 3. LOW-GUARD++ formal locked mean / min / OOD max

`NA / NA / NA` because formal validation was blocked before final-eval reporting.

## 4. Comparison with LOW-GUARD-LR

Not formally evaluated in issue27e. issue27d smoke remains the only source of the original100 HistGB candidate result, while LOW-GUARD-LR remains the demonstrated stable reference.

## 5. OOD <= 1%

Not formally evaluated in issue27e. issue27d smoke candidate had OOD max `0.005100`, but this cannot be upgraded to a formal result.

## 6. Single seed / bin collapse

Not evaluated in full seeds because the run stopped at candidate-freeze audit.

## 7. Leakage / artifact risk

No issue27e final-eval leakage occurred. The main artifact risk is candidate-freeze ambiguity. Representation leakage remains `unknown` until a full original100 provenance audit is included in issue27f.

## 8. Threshold target robustness

Not executed. Running target robustness before freezing the candidate could blur the config/target boundary.

## 9. Reproducibility of original100 + HistGB advantage

Promising but not formally validated.

## 10. Upgrade to LOW-GUARD++

No. The candidate must first be frozen and validated.

## 11. Paper mainline

Do not change the paper mainline yet. The correct current story is: LOW-GUARD-LR remains the demonstrated minimal instance; original100 + HistGB-Conservative is a serious performance-instance candidate requiring issue27f.

## 12. Slurm

Not needed for this audit. A future full locked-seed HistGB validation is likely local-feasible.
"""
    write_text(OUT / "summary.md", summary)

    command = """
git branch --show-current
git status --short
Read issue27d/27c/25c/23/mainline input files
python runs/issue27e_formal_validation_for_lowguard_plus_plus_original100_histgb_conservative_2026-05-26/run_issue27e_candidate_freeze_audit.py
git add runs/mainline_docs
git add -f runs/issue27e_formal_validation_for_lowguard_plus_plus_original100_histgb_conservative_2026-05-26
git diff --cached --check
git diff --cached --stat
git commit -m "Add issue27e formal LOW-GUARD++ validation"
git -c http.proxy=http://127.0.0.1:7897 -c https.proxy=http://127.0.0.1:7897 -c http.version=HTTP/1.1 push origin codex/exp-mainline
"""
    write_text(OUT / "command.txt", command)

    cfg = {
        "run_tag": "issue27e_formal_validation_for_lowguard_plus_plus_original100_histgb_conservative_2026-05-26",
        "candidate": "LOW_GUARD_HistGB_Conservative + original100",
        "stage_a_result": "candidate_config_not_uniquely_recoverable",
        "formal_validation_executed": False,
        "locked_bins": LOCKED_BINS,
        "intended_full_seeds": FULL_SEEDS,
        "final_eval_policy": "report_only; not reached",
        "primary_verdict": PRIMARY_VERDICT,
    }
    (OUT / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    run_spec = {
        "task_type": "formal_lowguard_plus_plus_validation_gate",
        "stage_completed": "candidate_config_freeze_audit",
        "stopped_before": "full_locked_seed_validation",
        "stop_reason": "non_unique_issue27d_selected_config",
        "selected_config_count": unique_count,
        "recommended_next_action": NEXT_ACTION,
    }
    (OUT / "run_spec.json").write_text(json.dumps(run_spec, indent=2), encoding="utf-8")
    manifest = pd.DataFrame(
        {
            "file": sorted(str(path.relative_to(OUT)) for path in OUT.iterdir() if path.is_file()),
            "role": "issue27e_output",
        }
    )
    manifest.to_csv(OUT / "manifest.csv", index=False)


if __name__ == "__main__":
    main()
