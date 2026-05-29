from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pandas as pd


REPO = Path(r"D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline")
OUT = REPO / "runs" / "issue27q_plan_protocol_reset_result_audit_lowguardpp_failure_and_deepsad_candidate_strategy_2026-05-27"
ISSUE27P = REPO / "runs" / "issue27p_full_mirai_anonymous_clean115_formal_benchmark_execution_2026-05-27"
MAINLINE_DOCS = REPO / "runs" / "mainline_docs"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "NA") for k in fieldnames})


def fmt(x: Any) -> str:
    try:
        return f"{float(x):.6f}"
    except Exception:
        return str(x)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    summary = (ISSUE27P / "summary.md").read_text(encoding="utf-8")
    all_results = pd.read_csv(ISSUE27P / "formal_benchmark_all_results.csv")
    ranked = pd.read_csv(ISSUE27P / "formal_benchmark_summary_table.csv")
    primary = pd.read_csv(ISSUE27P / "primary_lowguard_by_seed.csv")
    collapse = pd.read_csv(ISSUE27P / "collapse_models_summary.csv")
    registry = pd.read_csv(ISSUE27P / "method_registry.csv")
    config = json.loads((ISSUE27P / "benchmark_config.json").read_text(encoding="utf-8"))

    ds = ranked[ranked["method_name"] == "DeepSADStyle_Lite"].iloc[0].to_dict()
    lgpp = ranked[ranked["method_name"] == "LOW_GUARD_PLUSPLUS_HistGB_Conservative"].iloc[0].to_dict()
    lglr = ranked[ranked["method_name"] == "LOW_GUARD_LR_Minimal"].iloc[0].to_dict()
    ds_seed = all_results[all_results["method_name"] == "DeepSADStyle_Lite"].copy()
    lgpp_seed = primary[primary["method_name"] == "LOW_GUARD_PLUSPLUS_HistGB_Conservative"].copy()
    lglr_seed = primary[primary["method_name"] == "LOW_GUARD_LR_Minimal"].copy()

    lgpp_bad_detection = lgpp_seed.sort_values("attack_detection").iloc[0].to_dict()
    lgpp_bad_ood = lgpp_seed.sort_values("final_ood_alarm", ascending=False).iloc[0].to_dict()

    required_inputs = [
        ISSUE27P / "summary.md",
        ISSUE27P / "formal_benchmark_all_results.csv",
        ISSUE27P / "formal_benchmark_summary_table.csv",
        ISSUE27P / "formal_benchmark_ranking.md",
        ISSUE27P / "primary_lowguard_by_seed.csv",
        ISSUE27P / "primary_lowguard_summary.csv",
        ISSUE27P / "primary_lowguard_diagnosis.md",
        ISSUE27P / "collapse_models_by_seed.csv",
        ISSUE27P / "collapse_models_summary.csv",
        ISSUE27P / "formal_benchmark_anomaly_audit.md",
        ISSUE27P / "formal_benchmark_leakage_lite.csv",
        ISSUE27P / "method_registry.csv",
        ISSUE27P / "benchmark_config.json",
        ISSUE27P / "issue27q_next_action.md",
        MAINLINE_DOCS / "mainline_handoff.md",
        MAINLINE_DOCS / "mainline_experiment_map.md",
    ]
    missing = [str(p.relative_to(REPO)) for p in required_inputs if not p.exists()]
    primary_verdict = "issue27q_execution_plan_ready" if not missing else "issue27q_plan_blocked_by_missing_results"

    risk_rows = [
        {
            "risk_id": "DS01",
            "risk": "score_direction_or_scale_bug",
            "why_it_matters": "DeepSADStyle_Lite uses distance-like scores; direction or scale errors could create artificial high detection.",
            "issue27p_signal": f"DeepSAD detection_mean={fmt(ds['detection_mean'])}, OOD_max={fmt(ds['final_ood_alarm_max'])}",
            "test_plan": "Recompute scores from saved split; verify higher score means farther from guarded benign center and higher attack-side anomaly; run sign-flip control.",
            "expected_if_real": "Attack/support scores remain higher than ID/OOD and sign flip collapses detection.",
            "priority": "P0",
        },
        {
            "risk_id": "DS02",
            "risk": "seed_invariance_or_support_not_used",
            "why_it_matters": "Near-identical results across seeds can be a real robust signal or evidence that support variation has no effect.",
            "issue27p_signal": f"detection_std={fmt(ds['detection_std'])}, final_ood_std={fmt(ds['final_ood_alarm_std'])}",
            "test_plan": "Compare support row ids, support-weight vectors, score vectors, and center/scale tensors across seeds; run support removal/shuffle controls.",
            "expected_if_real": "Scores may be stable but support removal/shuffle should produce a measurable change or a documented reason support is weakly used.",
            "priority": "P0",
        },
        {
            "risk_id": "DS03",
            "risk": "row_order_or_anonymous_feature_artifact",
            "why_it_matters": "Full Mirai uses row-order split and anonymous clean115; a few columns or row-order drift may separate attack and benign.",
            "issue27p_signal": "DeepSAD dominates while IsolationForest is feasible but detects almost nothing; this contrast needs feature-level explanation.",
            "test_plan": "Feature rank/correlation audit, top-k ablation, row-index proxy test, shuffled-row negative control, and train/cal/val/final distribution plots.",
            "expected_if_real": "No index-like feature remains; top features correspond to plausible traffic statistics or result degrades after removing suspicious columns.",
            "priority": "P0",
        },
        {
            "risk_id": "DS04",
            "risk": "threshold_or_final_eval_leakage",
            "why_it_matters": "The method is feasible only if threshold is ID_calib+OOD_val only.",
            "issue27p_signal": "lite audit reports no final eval leakage, but high result still warrants replay.",
            "test_plan": "Instrument threshold construction; assert final OOD/attack arrays are not referenced before report; hash split arrays before/after.",
            "expected_if_real": "Threshold exactly matches ID_calib/OOD_val quantiles and is unchanged when final eval is replaced by dummy data.",
            "priority": "P0",
        },
        {
            "risk_id": "DS05",
            "risk": "not_exact_DeepSAD",
            "why_it_matters": "The current method is a weighted-center DeepSAD-style Lite objective, not full Deep SAD.",
            "issue27p_signal": "method_registry labels implementation as completed_model_specific_lite.",
            "test_plan": "Keep claim as DeepSAD-style Lite; optionally implement exact Deep SAD only after current lite candidate passes audit.",
            "expected_if_real": "Paper wording remains bounded; exact Deep SAD comparison is follow-up, not prerequisite for audit.",
            "priority": "P1",
        },
    ]

    write_csv(OUT / "deepsad_lite_risk_table.csv", risk_rows)
    write_text(
        OUT / "deepsad_lite_audit_plan.md",
        f"""
# DeepSADStyle_Lite Audit Plan

DeepSADStyle_Lite is the current issue27p leader under the anonymous-clean115 protocol reset, with
detection_mean `{fmt(ds['detection_mean'])}`, detection_min `{fmt(ds['detection_min'])}`,
final_OOD_alarm_max `{fmt(ds['final_ood_alarm_max'])}`, and feasible_rate `{fmt(ds['feasible_rate'])}`.

This result is promising but not yet claim-safe. The highest-priority concern is not just high performance;
it is the near seed-invariance and the fact that the implementation is a DeepSAD-style Lite weighted-center
objective, not exact Deep SAD.

P0 audit steps:

1. Recompute score direction from saved split artifacts and verify that higher scores are more anomalous.
2. Verify support rows are train-side only and disjoint from attack eval.
3. Replay threshold construction with assertions that only ID_calib and OOD_val scores are used.
4. Run label permutation, support removal, and support shuffle negative controls.
5. Audit feature dependence: top columns, top-k ablation, row-index proxy test, and distribution drift across train/val/final.
6. Expand seeds from 42-46 to 42-51 only after P0 controls pass.
7. Add attack-cluster or attack-row-block stratification so the high aggregate detection is not hiding a weak sub-family.

Claim boundary:

- If audit passes, the candidate can be called a strong `DeepSADStyle_Lite` reset-protocol candidate.
- It cannot be called exact Deep SAD without an exact objective implementation and fair rerun.
- It cannot be used for external generalization claims.
""",
    )

    hypothesis_rows = [
        {
            "hypothesis_id": "LGPP01",
            "hypothesis": "seed-specific kcenter support under-covers attack modes",
            "issue27p_evidence": f"LOW-GUARD++ seed {int(lgpp_bad_detection['seed'])} detection={fmt(lgpp_bad_detection['attack_detection'])}; random32 has high detection but OOD over-budget.",
            "diagnostic": "Compare kcenter32 support coverage vs attack_eval clusters; compute nearest-support distance by attack row block; test k=64/128 train/val only.",
            "repair_candidate": "Increase support budget or diversify support by cluster, selected only with train/validation evidence.",
            "selection_guard": "Never use final attack eval to choose support.",
            "priority": "P1",
        },
        {
            "hypothesis_id": "LGPP02",
            "hypothesis": "old HistGB config is original100-specific and mismatched to anonymous clean115",
            "issue27p_evidence": f"LOW-GUARD++ OOD_max={fmt(lgpp['final_ood_alarm_max'])}; old frozen config was designed upstream of anonymous clean115 reset.",
            "diagnostic": "Small pre-registered HistGB train/val-only grid around depth/l2/ood_weight/support_weight; compare OOD_val tail and support_val margin.",
            "repair_candidate": "Reset-protocol HistGB conservative config, not reusing original100-specific config as final.",
            "selection_guard": "No final eval during grid choice.",
            "priority": "P2",
        },
        {
            "hypothesis_id": "LGPP03",
            "hypothesis": "threshold guard suppresses attack in one seed and misses OOD tail in another",
            "issue27p_evidence": f"seed {int(lgpp_bad_detection['seed'])} threshold={fmt(lgpp_bad_detection['threshold'])} detection={fmt(lgpp_bad_detection['attack_detection'])}; seed {int(lgpp_bad_ood['seed'])} OOD={fmt(lgpp_bad_ood['final_ood_alarm'])}.",
            "diagnostic": "Threshold target curve 1.0/0.75/0.5/0.25 percent on validation only; plot attack/support/OOD score margins.",
            "repair_candidate": "Use stricter validation target only if train/val evidence supports it; report final only once.",
            "selection_guard": "Do not pick target based on final OOD or attack eval.",
            "priority": "P1",
        },
        {
            "hypothesis_id": "LGPP04",
            "hypothesis": "OOD guard weight is too weak for HistGB under anonymous clean115",
            "issue27p_evidence": "LOW-GUARD++ feasible_rate=0.8 but OOD max=0.028139; HistGB shallow and random support detect well but over-alarm.",
            "diagnostic": "Train/val-only OOD weight sensitivity with fixed support; inspect OOD_val tail and support margins.",
            "repair_candidate": "Conservative OOD weighting or monotonic/tail penalty if justified.",
            "selection_guard": "Use OOD_val and support_val only.",
            "priority": "P2",
        },
        {
            "hypothesis_id": "LGPP05",
            "hypothesis": "few anonymous columns dominate HistGB decisions",
            "issue27p_evidence": "Previous original100 path had high-risk separators; anonymous clean115 may have new unknown separators.",
            "diagnostic": "Permutation importance, split gain proxy, top-column removal, rank-normalize top columns, and label/index-like feature scan.",
            "repair_candidate": "Feature-safe HistGB variant or anonymous feature audit before main claim.",
            "selection_guard": "Feature transforms pre-registered and not chosen by final eval.",
            "priority": "P0",
        },
    ]
    write_csv(OUT / "lowguardpp_failure_hypothesis_table.csv", hypothesis_rows)
    write_text(
        OUT / "lowguardpp_failure_diagnosis_plan.md",
        f"""
# LOW-GUARD++ Failure Diagnosis Plan

issue27p does not show a uniform LOW-GUARD++ collapse; it shows instability:

- LOW-GUARD++ mean/min/OOD max = `{fmt(lgpp['detection_mean'])}` / `{fmt(lgpp['detection_min'])}` / `{fmt(lgpp['final_ood_alarm_max'])}`.
- Worst detection seed = `{int(lgpp_bad_detection['seed'])}` with detection `{fmt(lgpp_bad_detection['attack_detection'])}`.
- Worst OOD seed = `{int(lgpp_bad_ood['seed'])}` with final OOD alarm `{fmt(lgpp_bad_ood['final_ood_alarm'])}`.

Minimum diagnosis:

1. Score distribution by seed for ID_train, OOD_train, ID_calib, OOD_val, final_OOD, support, and attack_eval.
2. Attack_eval row-block or cluster stratification, especially for seed `{int(lgpp_bad_detection['seed'])}`.
3. kcenter32 support coverage audit against attack_eval clusters and nearest-support distances.
4. HistGB feature importance and top-column ablation under anonymous clean115.
5. Validation-only threshold target curve; final eval remains report-only.
6. Bounded train/val-only repair tests: support k=32/64/128, OOD weight sensitivity, and small HistGB conservative grid.

The diagnosis must not use final eval to choose a repaired configuration. A repair that only wins by final eval selection is invalid.
""",
    )

    matrix_rows = []
    heads = [
        ("LR", "logistic head", "low", "completed in issue27p but paired protocol table needs explicit grouping"),
        ("HistGB", "tree head", "low", "LOW-GUARD++ and shallow/random variants exist; needs paired matrix"),
        ("DeepSAD-style", "weighted center distance", "medium", "current leader; needs raw/support/guard/threshold decomposition"),
        ("DevNet-style", "small MLP score head", "medium", "unstable; needs interface audit and paired decomposition"),
        ("IsolationForest_or_OCSVM", "traditional anomaly detector", "medium", "support training not native; define guarded threshold and optional pseudo-support variant"),
        ("KitNET_AE_optional", "autoencoder baseline", "high", "only if implementation already available and cost acceptable"),
    ]
    variants = [
        ("raw_head", "no support, no OOD guarded training, ID-only or native threshold"),
        ("support_only", "attack support influences training/objective, no OOD training guard, ID-only threshold"),
        ("ood_train_guard_only", "OOD benign guard in training/objective, ID-only threshold"),
        ("threshold_guard_only", "no OOD training guard, ID_calib+OOD_val threshold"),
        ("full_guarded", "support + OOD guarded training + guarded threshold"),
    ]
    for head, head_desc, cost, notes in heads:
        for variant, definition in variants:
            matrix_rows.append(
                {
                    "head": head,
                    "head_description": head_desc,
                    "protocol_variant": variant,
                    "definition": definition,
                    "metrics": "detection_mean,detection_min,OOD_max,feasible_rate,protocol_gain_vs_raw",
                    "collapse_definition": "low detection_min or OOD_max > 0.01 under report-only final eval",
                    "implementation_cost": cost,
                    "notes": notes,
                }
            )
    write_csv(OUT / "paired_head_experiment_matrix.csv", matrix_rows)
    write_text(
        OUT / "lowguard_protocol_universality_matrix_plan.md",
        """
# LOW-GUARD Protocol Universality Matrix Plan

issue27p is a benchmark ranking, not a protocol-universality proof. Several methods used native objectives or lite objectives,
so the result cannot establish that LOW-GUARD is head-agnostic.

The next universality experiment must be paired. For each head, run:

1. raw head
2. support-only
3. OOD-training-guard-only
4. threshold-guard-only
5. full guarded version

Protocol gain must be computed within the same head:

- detection_mean gain
- detection_min gain
- final_OOD_alarm_max reduction
- feasible_under_1pct improvement

Collapse under the low-alert constraint means either detection_min collapses on at least one seed/subgroup or OOD max exceeds 1%.
The baseline set should include LR, HistGB, DeepSAD-style, DevNet-style, and one traditional anomaly detector. KitNET AE is optional
only if the implementation is already reliable; it is not required just to inflate baseline count.
""",
    )

    task_rows = [
        {
            "priority": "P0",
            "task_name": "deepsad_lite_sanity_controls",
            "purpose": "Check whether the current leader is real or artifact.",
            "required_inputs": "issue27p split hashes, all_results, feature matrix loader",
            "scripts_to_create_or_modify": "scripts/issue27q_audit_deepsad_lite.py",
            "expected_outputs": "score_direction_report, negative_control_by_seed, threshold_replay",
            "success_criterion": "No leakage; negative controls collapse; score direction correct.",
            "blocked_criterion": "Any final eval dependency or negative control stays strong.",
            "estimated_cost": "small to medium",
            "local_or_slurm": "local for P0; Slurm optional for seed 42-51",
            "risk": "If skipped, DeepSADStyle_Lite could be a false leader.",
        },
        {
            "priority": "P1",
            "task_name": "deepsad_lite_seed_expansion_and_stratification",
            "purpose": "Test stability beyond seeds 42-46 and identify attack subgroup weakness.",
            "required_inputs": "same split; optional row-block clusters",
            "scripts_to_create_or_modify": "extend issue27p runner for DeepSADStyle_Lite only",
            "expected_outputs": "seed42_51_by_seed, row_block_detection, OOD_score_distribution",
            "success_criterion": "Stability persists and no subgroup collapse.",
            "blocked_criterion": "Runtime/resource issue or subgroup labels unavailable.",
            "estimated_cost": "medium",
            "local_or_slurm": "local possible; Slurm recommended",
            "risk": "Strong mean may hide row-block weakness.",
        },
        {
            "priority": "P2",
            "task_name": "lowguardpp_failure_diagnosis",
            "purpose": "Find why HistGB LOW-GUARD++ has seed-44 detection collapse and seed-42 OOD violation.",
            "required_inputs": "primary_lowguard_by_seed, support row ids, feature loader",
            "scripts_to_create_or_modify": "scripts/issue27q_lowguardpp_failure_diagnosis.py",
            "expected_outputs": "support_coverage, score_distribution_by_seed, feature_importance, threshold_curve",
            "success_criterion": "At least one actionable failure mode identified without final eval tuning.",
            "blocked_criterion": "No support ids or score dumps recoverable.",
            "estimated_cost": "medium",
            "local_or_slurm": "local for diagnostics; Slurm for repair sweeps",
            "risk": "Prematurely abandoning LOW-GUARD++ would be scientifically weak.",
        },
        {
            "priority": "P3",
            "task_name": "paired_protocol_universality_matrix",
            "purpose": "Distinguish head quality from LOW-GUARD protocol gain.",
            "required_inputs": "formal split, fixed feature schema, method implementations",
            "scripts_to_create_or_modify": "scripts/issue27q_protocol_universality_matrix.py",
            "expected_outputs": "paired_head_by_seed, protocol_gain_summary, collapse_mode_table",
            "success_criterion": "Protocol gain measured within each head.",
            "blocked_criterion": "Head implementation incomplete or unfair protocol mapping.",
            "estimated_cost": "medium to high",
            "local_or_slurm": "Slurm recommended",
            "risk": "Without paired design, benchmark ranking cannot support protocol universality.",
        },
        {
            "priority": "P4",
            "task_name": "expensive_baseline_and_external_prep",
            "purpose": "Prepare exact expensive baselines and second-dataset route after internal audit.",
            "required_inputs": "Slurm config, optional KitNET AE code, second dataset metadata",
            "scripts_to_create_or_modify": "sbatch scripts and data compatibility audit",
            "expected_outputs": "exact_OCSVM_or_KITNET_plan, external_dataset_feasibility",
            "success_criterion": "Costed plan without blocking issue27q P0-P3.",
            "blocked_criterion": "No compatible external dataset or no resource allocation.",
            "estimated_cost": "high",
            "local_or_slurm": "Slurm",
            "risk": "Doing this before P0/P1 may distract from the current result audit.",
        },
    ]
    write_csv(OUT / "issue27q_task_table.csv", task_rows)
    write_text(
        OUT / "issue27q_execution_recommendation.md",
        """
# issue27q Execution Recommendation

Recommended execution order:

1. P0: DeepSADStyle_Lite sanity controls and threshold replay.
2. P1: DeepSADStyle_Lite seed expansion to 42-51 plus row-block/cluster stratification.
3. P2: LOW-GUARD++ failure diagnosis for seed-44 detection collapse and seed-42 OOD over-budget.
4. P3: paired protocol universality matrix across LR, HistGB, DeepSAD-style, DevNet-style, and one traditional anomaly detector.
5. P4: expensive baselines, optional KitNET AE, and second-dataset preparation.

Do not make a mainline method claim before P0/P1 pass. Do not abandon LOW-GUARD++ before P2 explains whether its failure is support, threshold, config, feature, or objective mismatch.
""",
    )

    write_text(
        OUT / "issue27q_plan_decision.md",
        f"""
# issue27q Plan Decision

primary_verdict = `{primary_verdict}`

secondary_verdict = `issue27p_requires_audit_before_mainline_decision`

All three required technical paths are executable:

- DeepSADStyle_Lite audit
- LOW-GUARD++ failure diagnosis
- paired LOW-GUARD protocol universality matrix

Current issue27p results are not paper-claim safe until the DeepSADStyle_Lite audit and LOW-GUARD++ failure diagnosis are completed.
""",
    )
    write_text(
        OUT / "claim_update_after_issue27q_plan.md",
        """
# Claim Update After issue27q Plan

Allowed after this planning issue:

- issue27p introduced a protocol-reset result that changes the internal mainline decision problem.
- DeepSADStyle_Lite is a serious reset-protocol candidate, but it is not claim-safe until audit passes.
- LOW-GUARD++ is not abandoned; its reset-protocol failure mode requires diagnosis.
- LOW-GUARD protocol universality is not established by issue27p and needs paired within-head experiments.

Not allowed:

- DeepSADStyle_Lite is the final main method.
- LOW-GUARD++ is permanently failed.
- anonymous clean115 proves restored115/original100 claims.
- external generalization, temporal generalization, or deployment robustness is proven.
""",
    )

    write_text(
        OUT / "summary.md",
        f"""
# issue27q Plan Summary

1. issue27q_plan completed: `true`.
2. primary_verdict: `{primary_verdict}`.
3. DeepSADStyle_Lite largest risk: near seed-invariant high performance under a lite weighted-center implementation, which could be real signal or implementation/feature/row-order artifact.
4. DeepSADStyle_Lite minimal audit: score-direction replay, threshold replay, final-eval exclusion assertions, label permutation, support removal/shuffle, and feature/row-order artifact audit.
5. LOW-GUARD++ likely failure causes: seed-specific support coverage gap, anonymous-clean115 mismatch with old HistGB config, threshold/score-margin mismatch, OOD guard weight mismatch, and possible few-column dominance.
6. LOW-GUARD++ minimal diagnosis: seed-44 attack failure and seed-42 OOD violation score distributions, support coverage, feature importance, and validation-only threshold curves.
7. LOW-GUARD protocol universality proven: `false`.
8. Paired universality matrix: raw/support-only/OOD-train-only/threshold-only/full-guarded per head for LR, HistGB, DeepSAD-style, DevNet-style, and one traditional anomaly detector.
9. Baseline collapse experiments: use DevNet-style, DeepSAD-style, HistGB, LR, and one traditional detector; KitNET AE optional only if cheap and reliable.
10. Formal issue27q order: P0 sanity controls, P1 DeepSAD seed expansion/stratification, P2 LOW-GUARD++ failure diagnosis, P3 paired protocol matrix, P4 expensive baselines/external prep.
11. Slurm: recommended for seed expansion and paired matrix; P0 sanity can run locally.
12. Commit hash: pending.
""",
    )

    write_text(
        OUT / "command.txt",
        "\n".join(
            [
                "git branch --show-current",
                "git status --short",
                "read issue27p summary/all_results/summary_table/primary/collapse/audit/method_registry/config",
                "python runs/issue27q_plan_protocol_reset_result_audit_lowguardpp_failure_and_deepsad_candidate_strategy_2026-05-27/generate_issue27q_plan.py",
            ]
        ),
    )
    write_text(
        OUT / "config.json",
        json.dumps(
            {
                "issue": "issue27q_plan_protocol_reset_result_audit_lowguardpp_failure_and_deepsad_candidate_strategy_2026-05-27",
                "mode": "plan_only_no_formal_training",
                "source_issue": "issue27p_full_mirai_anonymous_clean115_formal_benchmark_execution_2026-05-27",
                "feature_schema": config.get("feature_schema", "anonymous_clean115_all"),
                "external_generalization": False,
                "paper_modified": False,
            },
            indent=2,
            sort_keys=True,
        ),
    )
    write_text(
        OUT / "run_spec.json",
        json.dumps(
            {
                "outputs": [
                    "summary.md",
                    "deepsad_lite_audit_plan.md",
                    "deepsad_lite_risk_table.csv",
                    "lowguardpp_failure_diagnosis_plan.md",
                    "lowguardpp_failure_hypothesis_table.csv",
                    "lowguard_protocol_universality_matrix_plan.md",
                    "paired_head_experiment_matrix.csv",
                    "issue27q_execution_recommendation.md",
                    "issue27q_task_table.csv",
                    "issue27q_plan_decision.md",
                    "claim_update_after_issue27q_plan.md",
                ],
                "no_large_training": True,
                "missing_inputs": missing,
            },
            indent=2,
            sort_keys=True,
        ),
    )

    handoff = MAINLINE_DOCS / "mainline_handoff.md"
    with handoff.open("a", encoding="utf-8") as f:
        f.write(
            "\n## issue27q plan for protocol reset audit (2026-05-27)\n\n"
            f"- primary_verdict: `{primary_verdict}`\n"
            "- scope: plan-only audit package for DeepSADStyle_Lite, LOW-GUARD++ reset-protocol failure, and paired LOW-GUARD protocol universality.\n"
            "- key boundary: issue27p changes the mainline question but does not yet make DeepSADStyle_Lite claim-safe or permanently demote LOW-GUARD++.\n"
            "- next action: execute P0/P1 DeepSAD audit, then LOW-GUARD++ failure diagnosis and paired universality matrix.\n"
        )
    exp_map = MAINLINE_DOCS / "mainline_experiment_map.md"
    with exp_map.open("a", encoding="utf-8") as f:
        f.write(
            "\n| issue27q_plan | protocol reset result audit plan | "
            f"`{primary_verdict}` | Plan-only package: audit DeepSADStyle_Lite, diagnose LOW-GUARD++ failure, and design paired protocol-universality matrix. Next: P0/P1 audit before mainline decision. |\n"
        )

    manifest = []
    for path in sorted(OUT.iterdir()):
        if path.is_file():
            manifest.append({"file": path.name, "bytes": path.stat().st_size})
    write_csv(OUT / "manifest.csv", manifest)


if __name__ == "__main__":
    main()
