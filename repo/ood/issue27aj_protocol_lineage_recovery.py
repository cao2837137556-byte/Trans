from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs" / "issue27aj_protocol_lineage_recovery_and_support_selector_audit_2026-06-02"
DOCS = ROOT / "runs" / "mainline_docs"
PRIMARY_VERDICT = "recovered_kcenter_mainline_protocol_ready_for_gotham115_migration"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def append_once(path: Path, marker: str, text: str) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker in existing:
        return
    with path.open("a", encoding="utf-8") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        f.write("\n" + text.strip() + "\n")


lineage_fields = [
    "source_file",
    "run_id",
    "issue_id",
    "date_or_stage",
    "dataset",
    "frontend",
    "support_selector",
    "support_size",
    "selector_distance_metric",
    "selector_scaler_source",
    "model_or_head",
    "threshold_rule",
    "ood_guard_rule",
    "score_direction",
    "state_strategy",
    "seed",
    "metric_summary_if_available",
    "verdict",
    "evidence_level",
    "can_migrate_to_gotham115",
    "notes",
]

lineage_rows = [
    {
        "source_file": "runs/issue25c_strong_baseline_pack_execution_for_enhanced_lowguard_top64_2026-05-18/baseline_candidate_definitions.csv",
        "run_id": "issue25c",
        "issue_id": "issue25c",
        "date_or_stage": "2026-05-18 strong baseline pack",
        "dataset": "locked_harder_holdout bins 5-8",
        "frontend": "selected_source_rich_top64 historical representation",
        "support_selector": "kcenter",
        "support_size": 32,
        "selector_distance_metric": "euclidean after selector-local StandardScaler",
        "selector_scaler_source": "attack train pool only inside issue19b.kcenter_support",
        "model_or_head": "M2_Enhanced_LOW_GUARD_top64_fixed_guard_LR",
        "threshold_rule": "ID calibration + OOD validation at official 1% OOD alarm target",
        "ood_guard_rule": "fixed OOD guard LR using ID_train, OOD_train, and kcenter32 attack supports",
        "score_direction": "higher score means more attack/anomalous; attack_scores > threshold",
        "state_strategy": "historical static feature assets; no Kitsune online state strategy",
        "seed": "42-46 main, 47-51 held-out/consistency where used",
        "metric_summary_if_available": "issue25c reports locked mean/min/OOD max 0.949705/0.882629/0.004500 for main method",
        "verdict": "main_method",
        "evidence_level": "high",
        "can_migrate_to_gotham115": "yes_selector_and_protocol_permissions_only",
        "notes": "This is the clearest old mainline record; random32 is explicitly a support ablation.",
    },
    {
        "source_file": "runs/issue25c_strong_baseline_pack_execution_for_enhanced_lowguard_top64_2026-05-18/summary.md",
        "run_id": "issue25c",
        "issue_id": "issue25c",
        "date_or_stage": "2026-05-18 strong baseline pack summary",
        "dataset": "locked_harder_holdout bins 5-8",
        "frontend": "selected_source_rich_top64",
        "support_selector": "kcenter32 confirmed attack supports",
        "support_size": 32,
        "selector_distance_metric": "euclidean after selector-local StandardScaler",
        "selector_scaler_source": "attack train pool only",
        "model_or_head": "fixed OOD guard LR",
        "threshold_rule": "ID calibration + OOD validation under 1% target",
        "ood_guard_rule": "fixed OOD guard",
        "score_direction": "higher score more attack/anomalous",
        "state_strategy": "historical static feature assets",
        "seed": "42-46 main",
        "metric_summary_if_available": "strong_baseline_positive; no baseline fully dominates main under locked criteria",
        "verdict": "main_method_frozen",
        "evidence_level": "high",
        "can_migrate_to_gotham115": "yes",
        "notes": "Summary states topK/support/adapter/threshold changed: no, final eval selection: no.",
    },
    {
        "source_file": "runs/issue25c_strong_baseline_pack_execution_for_enhanced_lowguard_top64_2026-05-18/run_issue25c_strong_baselines.py",
        "run_id": "issue25c",
        "issue_id": "issue25c",
        "date_or_stage": "2026-05-18 executable protocol",
        "dataset": "locked_harder_holdout plus consistency holdouts",
        "frontend": "source_rich_top64 for main; original100 for support kcenter input in call",
        "support_selector": "issue19b.kcenter_support",
        "support_size": 32,
        "selector_distance_metric": "euclidean after StandardScaler in kcenter_support",
        "selector_scaler_source": "x_attack_o[train_pool] only",
        "model_or_head": "guarded_lr main, plus kcenter support for adapter baselines",
        "threshold_rule": "issue19b.v72.guarded_val_threshold(id_calib, ood_val, 0.01)",
        "ood_guard_rule": "ID/OOD guarded validation threshold with fixed guard LR training",
        "score_direction": "higher score more attack/anomalous",
        "state_strategy": "historical static features",
        "seed": "42-46 plus held-out consistency seeds",
        "metric_summary_if_available": "not re-used here as new result",
        "verdict": "code_confirms_kcenter_mainline",
        "evidence_level": "high",
        "can_migrate_to_gotham115": "yes_with_gotham_attack_support_role_only",
        "notes": "Code caches kcenter once per dataset, random32 only if method support_method == random.",
    },
    {
        "source_file": "runs/issue23_locked_validation_for_enhanced_v2_top64_2026-05-18/protocol.md",
        "run_id": "issue23",
        "issue_id": "issue23",
        "date_or_stage": "2026-05-18 locked validation",
        "dataset": "locked_harder_holdout bins 5-8",
        "frontend": "selected_source_rich_top64 historical representation",
        "support_selector": "kcenter32",
        "support_size": 32,
        "selector_distance_metric": "euclidean after selector-local StandardScaler",
        "selector_scaler_source": "local attack train pool per locked holdout",
        "model_or_head": "fixed OOD guard LR",
        "threshold_rule": "ID calibration + OOD validation only",
        "ood_guard_rule": "fixed OOD guard LR",
        "score_direction": "higher score more attack/anomalous",
        "state_strategy": "historical static features",
        "seed": "42-46 main; 47-51 held-out where referenced",
        "metric_summary_if_available": "same locked candidate later reproduced in issue25c",
        "verdict": "locked_candidate",
        "evidence_level": "high",
        "can_migrate_to_gotham115": "yes_protocol_permissions_only",
        "notes": "Protocol states candidate selected_source_rich_top64 + kcenter32 + fixed OOD guard LR.",
    },
    {
        "source_file": "runs/issue23_locked_validation_for_enhanced_v2_top64_2026-05-18/support_id_provenance.csv",
        "run_id": "issue23",
        "issue_id": "issue23",
        "date_or_stage": "2026-05-18 support provenance",
        "dataset": "locked_harder_holdout bins 5-8",
        "frontend": "selected_source_rich_top64/original100 support source",
        "support_selector": "kcenter",
        "support_size": 32,
        "selector_distance_metric": "euclidean after selector-local StandardScaler",
        "selector_scaler_source": "local_locked_holdout_attack_train_pool",
        "model_or_head": "fixed_guard_lr candidates",
        "threshold_rule": "not selected from final eval",
        "ood_guard_rule": "guarded protocol",
        "score_direction": "higher score more attack/anomalous",
        "state_strategy": "historical static features",
        "seed": "42 etc.",
        "metric_summary_if_available": "support rows record no overlap with attack eval",
        "verdict": "support_audit_pass",
        "evidence_level": "high",
        "can_migrate_to_gotham115": "yes",
        "notes": "Columns show in_attack_train_pool=True, overlaps_attack_eval=False, selection_uses_attack_eval=False, selection_uses_final_ood_eval=False.",
    },
    {
        "source_file": "runs/mainline_docs/mainline_experiment_map.md",
        "run_id": "mainline_docs",
        "issue_id": "issue25c/LOW-GUARD-LR lineage",
        "date_or_stage": "mainline handoff after issue25c",
        "dataset": "historical locked protocol",
        "frontend": "old source_rich/original100 lineage",
        "support_selector": "kcenter32",
        "support_size": 32,
        "selector_distance_metric": "euclidean after StandardScaler evidence from code",
        "selector_scaler_source": "train-side attack support pool",
        "model_or_head": "LOW-GUARD-LR minimal deployable instance",
        "threshold_rule": "1% low-OOD alert target via ID calib + OOD val",
        "ood_guard_rule": "guarded few-shot adaptation protocol",
        "score_direction": "higher score more attack/anomalous",
        "state_strategy": "historical static features",
        "seed": "not uniquely specified in doc",
        "metric_summary_if_available": "docs cite issue25c mean/min/OOD max",
        "verdict": "mainline_doc_support",
        "evidence_level": "medium_high",
        "can_migrate_to_gotham115": "yes",
        "notes": "Docs support LOW-GUARD-LR lineage but executable files are stronger evidence.",
    },
    {
        "source_file": "runs/issue27ai_gotham_kitsune115_medium_protocol_diagnostic_and_collapse_probe_2026-06-02/summary.md",
        "run_id": "issue27ai",
        "issue_id": "issue27ai",
        "date_or_stage": "2026-06-02 Gotham medium diagnostic",
        "dataset": "Gotham Kitsune115 medium asset",
        "frontend": "Kitsune-style 115D",
        "support_selector": "fixed_first32",
        "support_size": 32,
        "selector_distance_metric": "none",
        "selector_scaler_source": "none",
        "model_or_head": "diagnostic matrix only",
        "threshold_rule": "diagnostic only",
        "ood_guard_rule": "diagnostic only",
        "score_direction": "adapter-specific diagnostic",
        "state_strategy": "Gotham medium fixed asset",
        "seed": "fixed minimal diagnostic",
        "metric_summary_if_available": "not used for lineage selection",
        "verdict": "diagnostic_placeholder_not_old_mainline",
        "evidence_level": "high_for_placeholder_status",
        "can_migrate_to_gotham115": "no_as_mainline_selector",
        "notes": "Current task explicitly forbids substituting fixed_first32 for old mainline.",
    },
]

candidate_fields = [
    "candidate_name",
    "support_selector",
    "support_size",
    "model_head",
    "threshold_rule",
    "ood_guard_rule",
    "evidence_files",
    "why_candidate",
    "risks",
    "migration_status",
]

candidate_rows = [
    {
        "candidate_name": "old_mainline_low_guard_lr_top64_kcenter32",
        "support_selector": "kcenter32",
        "support_size": 32,
        "model_head": "fixed OOD guard LR / LOW-GUARD-LR",
        "threshold_rule": "ID calibration + OOD validation at 1% OOD alarm target",
        "ood_guard_rule": "fixed OOD guard using ID_train/OOD_train and selected attack supports",
        "evidence_files": "issue23 protocol+run+support provenance; issue25c baseline definitions+summary+run; mainline docs",
        "why_candidate": "Repeatedly named as locked/main method, with executable kcenter selector and final-eval isolation.",
        "risks": "Old frontend was source_rich_top64/original100; only selector/protocol permissions migrate, not old claims or features.",
        "migration_status": "ready_for_gotham115_medium_diagnostic_migration",
    },
    {
        "candidate_name": "old_original100_reference_kcenter32",
        "support_selector": "kcenter32",
        "support_size": 32,
        "model_head": "fixed OOD guard LR",
        "threshold_rule": "ID calibration + OOD validation at 1%",
        "ood_guard_rule": "fixed OOD guard",
        "evidence_files": "issue19b summary/run; issue23 method_specs; issue25c baseline definitions",
        "why_candidate": "Reference lineage for V1 original100 with same support selector and guard.",
        "risks": "Reference baseline, not final enhanced mainline.",
        "migration_status": "migrate_as_reference_if_needed",
    },
    {
        "candidate_name": "old_random32_support_ablation",
        "support_selector": "random32_seeded",
        "support_size": 32,
        "model_head": "fixed OOD guard LR",
        "threshold_rule": "ID calibration + OOD validation at 1%",
        "ood_guard_rule": "fixed OOD guard",
        "evidence_files": "issue23 V2_top64_random32; issue25c M4_top64_random32_fixed_guard_LR; issue22 random_support",
        "why_candidate": "Explicit support ablation used to test whether representative kcenter support mattered.",
        "risks": "Not mainline; should not replace kcenter except as ablation.",
        "migration_status": "migrate_as_ablation_only",
    },
    {
        "candidate_name": "issue27ai_fixed_first32_medium_diagnostic",
        "support_selector": "fixed_first32",
        "support_size": 32,
        "model_head": "medium diagnostic adapters",
        "threshold_rule": "diagnostic only",
        "ood_guard_rule": "diagnostic only",
        "evidence_files": "issue27ai outputs",
        "why_candidate": "Useful clean diagnostic placeholder on Gotham Kitsune115 medium asset.",
        "risks": "Not historical mainline and not representative support selection.",
        "migration_status": "do_not_use_as_recovered_mainline",
    },
]

code_fields = [
    "selector_name",
    "source_file",
    "function_or_class",
    "inputs",
    "outputs",
    "uses_eval_data",
    "uses_final_eval",
    "deterministic",
    "seed_controlled",
    "can_reuse_for_gotham115",
    "notes",
]

code_rows = [
    {
        "selector_name": "kcenter32",
        "source_file": "runs/issue19b_v1_v2_same_protocol_backtest_and_alarm_budget_curve_2026-05-18/run_issue19b_v1_v2_backtest.py",
        "function_or_class": "kcenter_support(train_rows, train_x_raw, budget)",
        "inputs": "train_rows; train_x_raw from attack train pool; budget",
        "outputs": "sorted selected global row indices",
        "uses_eval_data": "false",
        "uses_final_eval": "false",
        "deterministic": "true",
        "seed_controlled": "not_needed",
        "can_reuse_for_gotham115": "yes_with_attack_support_only",
        "notes": "Fits StandardScaler on train_x_raw, starts closest-to-centroid, uses Euclidean farthest-first, returns sorted train_rows.",
    },
    {
        "selector_name": "random32_seeded",
        "source_file": "runs/issue22_v2_hard_shift_enhancement_pilot_2026-05-18/run_issue22_v2_enhancement.py",
        "function_or_class": "random_support(train_rows, budget, seed)",
        "inputs": "train_rows; budget; seed",
        "outputs": "sorted randomly selected row indices",
        "uses_eval_data": "false",
        "uses_final_eval": "false",
        "deterministic": "true_with_seed",
        "seed_controlled": "true",
        "can_reuse_for_gotham115": "yes_as_ablation_only",
        "notes": "Uses np.random.default_rng(seed + 2200 + budget).",
    },
    {
        "selector_name": "fixed_first32",
        "source_file": "runs/issue27ai_gotham_kitsune115_medium_protocol_diagnostic_and_collapse_probe_2026-06-02",
        "function_or_class": "diagnostic role-order first32 rule",
        "inputs": "pre-registered attack_support role sorted by asset order",
        "outputs": "first 32 support rows",
        "uses_eval_data": "false",
        "uses_final_eval": "false",
        "deterministic": "true",
        "seed_controlled": "not_needed",
        "can_reuse_for_gotham115": "diagnostic_only",
        "notes": "Clean audit placeholder; explicitly not recovered mainline.",
    },
    {
        "selector_name": "choose_positive_train_indices",
        "source_file": "repo/ood/original100_fewshot_official_control.py",
        "function_or_class": "choose_positive_train_indices(train_idx, budget, seed)",
        "inputs": "positive train indices; budget; seed",
        "outputs": "seeded support indices",
        "uses_eval_data": "false",
        "uses_final_eval": "false",
        "deterministic": "true_with_seed",
        "seed_controlled": "true",
        "can_reuse_for_gotham115": "not_as_mainline",
        "notes": "Older official control support picker, not the locked kcenter mainline.",
    },
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUT / "protocol_lineage_inventory.csv", lineage_rows, lineage_fields)
    write_csv(OUT / "recovered_protocol_candidates.csv", candidate_rows, candidate_fields)
    write_csv(OUT / "support_selector_code_map.csv", code_rows, code_fields)

    write_text(
        OUT / "recovered_mainline_protocol_spec.md",
        f"""
# Recovered Mainline Protocol Spec

## Primary Verdict

`{PRIMARY_VERDICT}`

## Recovered Old Mainline

The strongest historical evidence points to:

`selected_source_rich_top64 + kcenter32 + fixed OOD guard LR`

This is the old LOW-GUARD-LR / Enhanced LOW-GUARD+ mainline protocol, not the
current Gotham `fixed_first32` diagnostic placeholder.

## Support Selector

- Selector: `kcenter32`
- Budget: 32 attack support rows
- Source pool: train-side attack pool only
- Code: `issue19b.kcenter_support(train_rows, train_x_raw, budget)`
- Selector scaling: `StandardScaler().fit(train_x_raw)` inside the selector
- Distance: Euclidean farthest-first after selector-local standardization
- Initialization: closest point to the standardized attack-pool centroid
- Output: sorted selected global row indices
- Eval access: no attack eval and no final OOD eval

The executable lineage is used by issue23 and issue25c. issue25c explicitly
records `M2_Enhanced_LOW_GUARD_top64_fixed_guard_LR` as `main_method` with
`support_method=kcenter` and `support_count=32`. The `random32` rule is
recorded as a support ablation, not as the main protocol.

## Guarded Head And Threshold

- Model/head: fixed OOD guard LR / LOW-GUARD-LR minimal guarded instance
- Model scaler: `StandardScaler` fit only on the training matrix
  (`ID benign train + OOD benign train + selected local attack supports`)
- Threshold rule: ID calibration + OOD validation at the official 1% OOD
  alarm target
- Score direction: higher score means more attack/anomalous; detection uses
  `attack_score > threshold`
- Final eval: final OOD eval and final attack eval are report-only and not used
  for feature, support, threshold, hyperparameter, model, or route selection

## Evidence Files

- `runs/issue23_locked_validation_for_enhanced_v2_top64_2026-05-18/protocol.md`
- `runs/issue23_locked_validation_for_enhanced_v2_top64_2026-05-18/run_issue23_locked_validation.py`
- `runs/issue23_locked_validation_for_enhanced_v2_top64_2026-05-18/support_id_provenance.csv`
- `runs/issue25c_strong_baseline_pack_execution_for_enhanced_lowguard_top64_2026-05-18/baseline_candidate_definitions.csv`
- `runs/issue25c_strong_baseline_pack_execution_for_enhanced_lowguard_top64_2026-05-18/summary.md`
- `runs/issue25c_strong_baseline_pack_execution_for_enhanced_lowguard_top64_2026-05-18/run_issue25c_strong_baselines.py`
- `runs/mainline_docs/mainline_experiment_map.md`

## What Remains Uncertain

- The old frontend was not Gotham Kitsune115. Historical performance numbers
  cannot be migrated as Gotham results.
- Historical state strategy was based on static feature assets. Gotham must use
  the issue27af/issue27ag split-aware/state-aware Kitsune115 asset contracts.
- The selector can migrate, but old source-rich feature selection cannot be
  reused as a Gotham claim.
""",
    )

    write_text(
        OUT / "gotham115_migration_plan.md",
        """
# Gotham115 Migration Plan

## Purpose

Migrate the recovered old `kcenter32` support selector and guarded protocol
permissions to Gotham Kitsune115 medium diagnostics. This is not a formal
benchmark and does not import old performance claims.

## Fixed Inputs

- Dataset asset: issue27af/issue27ag Gotham Kitsune115 medium asset certificate
- Feature schema: Gotham Kitsune-style 115D
- Split: already fixed by prior Gotham contract
- Support pool: only rows with role `attack_support`
- Report-only roles: `final_ood_benign_eval` and `attack_eval`

## Selector Migration

1. Load the fixed Gotham115 medium asset through the existing immutable loader.
2. Select candidate rows only from the `attack_support` role.
3. Fit selector-local `StandardScaler` only on attack_support feature rows.
4. Run Euclidean farthest-first k-center with budget 32.
5. Output `support_indices_32`, selector configuration, role-access audit, and
   hash of selected global row IDs.
6. Verify no selected row comes from `attack_eval`, `final_ood_benign_eval`,
   `ood_benign_val`, or benign training roles.

## Forbidden Access

- Do not use `final_ood_benign_eval` for support selection, thresholding,
  model selection, feature selection, or hyperparameter selection.
- Do not use `attack_eval` for support selection, thresholding, model
  selection, feature selection, or hyperparameter selection.
- Do not re-split or re-materialize the medium asset in issue27ak.

## Next Diagnostic

The next issue should be
`issue27ak_migrate_recovered_protocol_to_gotham115_medium_diagnostic`.

It should compare the recovered kcenter32 support selector against the
diagnostic first32 placeholder only as a protocol sanity/diagnostic check, not
as a formal model ranking.
""",
    )

    write_text(
        OUT / "issue27ak_next_action.md",
        """
# Issue27ak Next Action

Recommended next task:

`issue27ak_migrate_recovered_protocol_to_gotham115_medium_diagnostic`

## Required Scope

- Reuse the fixed issue27af/issue27ag Gotham Kitsune115 medium asset.
- Do not re-split data.
- Do not change support pool membership.
- Implement recovered `kcenter32` support selection on the `attack_support`
  role only.
- Emit support selector audit files and selected support hash.
- Then run only medium diagnostic guarded-protocol checks if the selector audit
  passes.

## Boundary

This remains a medium diagnostic. It is not a formal benchmark, does not decide
the final mainline, and cannot use final OOD eval or attack eval for selection.
""",
    )

    write_text(
        OUT / "claim_update_after_issue27aj.md",
        """
# Claim Update After Issue27aj

The old LOW-GUARD lineage should not be represented by issue27ai's
`fixed_first32` diagnostic placeholder. Historical evidence supports a recovered
mainline protocol using `kcenter32` representative attack supports, a fixed OOD
guard LR head, and ID-calibration plus OOD-validation thresholding at the 1%
OOD alarm target.

This is a protocol lineage recovery finding only. It does not provide new
Gotham model performance, does not validate a paper claim, and does not make old
source-rich/original100 results equivalent to Gotham Kitsune115.
""",
    )

    write_text(
        OUT / "summary.md",
        f"""
# Issue27aj Summary

1. issue27aj completed: yes.
2. primary_verdict: `{PRIMARY_VERDICT}`.
3. Old mainline selector recovered: `kcenter32`.
4. Support size recovered: 32.
5. Selector details: selector-local StandardScaler fit on attack train pool,
   Euclidean farthest-first, centroid-nearest initialization, sorted global row
   output.
6. Old mainline head: fixed OOD guard LR / LOW-GUARD-LR.
7. Threshold rule: ID calibration + OOD validation at the official 1% OOD alarm
   target.
8. Final eval status: final OOD eval and attack eval were report-only in the
   recovered protocol.
9. issue27ai fixed_first32 status: clean diagnostic placeholder, not recovered
   mainline.
10. Migration status: selector and protocol permissions can migrate to Gotham
    Kitsune115 medium diagnostics; old performance claims and old frontend
    cannot migrate.
11. Recommended next issue: `issue27ak_migrate_recovered_protocol_to_gotham115_medium_diagnostic`.
12. New model performance produced: no.
13. Commit hash: pending.
""",
    )

    write_text(
        OUT / "issue27aj_decision.md",
        f"""
# Issue27aj Decision

primary_verdict = `{PRIMARY_VERDICT}`

The recovered old mainline protocol is sufficiently evidenced as `kcenter32`
representative support selection with support size 32, fixed OOD guard LR, and
ID-calibration plus OOD-validation thresholding. The evidence comes from both
human-readable protocol outputs and executable code in issue23/issue25c.

The current `fixed_first32` rule from issue27ai remains useful only as a clean
medium diagnostic placeholder. It must not be treated as the old mainline
support selector.
""",
    )

    config = {
        "issue": "issue27aj_protocol_lineage_recovery_and_support_selector_audit_2026-06-02",
        "primary_verdict": PRIMARY_VERDICT,
        "no_new_model_training": True,
        "no_performance_ranking": True,
        "recovered_support_selector": "kcenter32",
        "support_size": 32,
        "selector_metric": "euclidean_after_selector_local_standard_scaler",
        "selector_allowed_roles_for_gotham115": ["attack_support"],
        "selector_forbidden_roles_for_gotham115": ["final_ood_benign_eval", "attack_eval"],
    }
    write_text(OUT / "config.json", json.dumps(config, indent=2))

    run_spec = {
        "task_type": "protocol_lineage_recovery",
        "search_scope": ["runs", "runs/mainline_docs", "repo/ood", "repo"],
        "performance_outputs_generated": False,
        "formal_benchmark": False,
        "next_action": "issue27ak_migrate_recovered_protocol_to_gotham115_medium_diagnostic",
    }
    write_text(OUT / "run_spec.json", json.dumps(run_spec, indent=2))

    write_text(
        OUT / "command.txt",
        """
python repo/ood/issue27aj_protocol_lineage_recovery.py
""",
    )

    doc_section = """
## issue27aj - Protocol Lineage Recovery And Support Selector Audit

- Status: completed.
- Primary verdict: `recovered_kcenter_mainline_protocol_ready_for_gotham115_migration`.
- Key recovery: old mainline support selector is `kcenter32`, not issue27ai
  `fixed_first32`.
- Evidence: issue23 locked validation and issue25c strong baseline pack name
  the main candidate as `selected_source_rich_top64 + kcenter32 + fixed OOD
  guard LR`; executable code calls `issue19b.kcenter_support(...)` on the
  train-side attack pool only.
- Selector mechanics: selector-local `StandardScaler`, Euclidean farthest-first
  k-center, budget 32, no attack eval or final OOD eval access.
- Gotham migration: migrate selector/protocol permissions only to Gotham
  Kitsune115 medium diagnostics; do not migrate old frontend or old performance
  claims.
- Next: `issue27ak_migrate_recovered_protocol_to_gotham115_medium_diagnostic`.
"""
    append_once(DOCS / "mainline_handoff.md", "## issue27aj - Protocol Lineage Recovery And Support Selector Audit", doc_section)
    append_once(DOCS / "mainline_experiment_map.md", "## issue27aj - Protocol Lineage Recovery And Support Selector Audit", doc_section)

    manifest_rows = []
    for path in sorted(OUT.glob("*")):
        if path.is_file() and path.name != "manifest.csv":
            manifest_rows.append(
                {
                    "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    write_csv(OUT / "manifest.csv", manifest_rows, ["path", "size_bytes", "sha256"])


if __name__ == "__main__":
    main()
