# Issue27g Suspicious Perfect Score Audit Summary

## Verdict

- primary_verdict: `lowguard_plus_plus_formal_result_passes_anomaly_audit`
- issue27f_result_under_audit: `1.000000 / 1.000000 / 0.000100`
- audit_position: `formal result reported, claim upgrade gated by anomaly audit`

## 1. Is issue27f's perfect result credible?

`Yes, within the audited locked protocol, with bounded claims.`

## 2. Final eval leakage

| audit_item | status | evidence | risk_level |
|---|---|---|---|
| final_ood_eval_used_for_config_freeze | pass | config_freeze_decision_table.freeze_uses_final_eval is false | low |
| final_ood_eval_used_for_threshold | pass | formal_locked_by_seed.threshold_uses_final_eval is false for all rows | low |
| attack_eval_used_for_config_or_threshold | pass | formal_locked_by_seed.hyperparameter_uses_final_eval is false for all rows | low |
| formal_locked_by_seed_is_report_only | pass | formal result rows mark final_eval_used_for_selection=false | low |
| issue27f_leakage_table_no_fail | pass | formal_leakage_audit_table has no fail row | low |


## 3. Split/sample overlap

Index-level attack support/eval overlap: `0`.
Locked eval-bin overlap failures: `0`.

## 4. Original100 label-like / split-like features

Flagged low-cardinality label/split-like features: `0`.
High-cardinality near-perfect separator features: `3`.

## 5. Negative controls

| control_name | attack_detection_mean | final_ood_alarm_max | statuses |
|---|---|---|---|
| label_permutation_same_positive_count | 0.003521 | 0.005500 | normal_collapse |
| ood_benign_as_positive_support | 0.002884 | 0.006900 | normal_collapse |
| positive_control_real_support | 1.000000 | 0.000100 | reference |
| random_50_feature_subset | 0.771714 | 0.005900 | caution_still_perfect;weakened_or_nonperfect |
| threshold_recompute_idcalib_oodval_only | 1.000000 | 0.000100 | pass |


## 6. Scratch recompute

Scratch recompute matches issue27f: `True`.

## 7. Score distribution

The audited score distributions show all attack scores above threshold and usually a single final-OOD tail point above threshold, yielding the reported `0.000100` OOD alarm. This is compatible with the perfect result, but not by itself sufficient; the negative controls are the stronger sanity check.

## 8. Cache/artifact reuse

| audit_item | status | evidence | risk_level |
|---|---|---|---|
| issue27f_script_contains_training_loop | pass | run_formal_validation constructs adapters and calls .fit for HistGB and LR | low |
| formal_histgb_rows_have_nonzero_train_time | pass | formal_locked_by_seed HistGB rows have positive train_time | low |
| formal_lr_reference_rows_have_nonzero_train_time | pass | LR reference rows were rerun or at least refit with positive train_time | low |
| issue27f_does_not_read_formal_summary_as_source_results | pass | script writes formal summaries after generating by-seed rows | low |
| issue27d_smoke_used_for_comparison_not_formal_result_source | pass | issue27d smoke table is used in comparison section; formal rows are generated independently | low |


## 9. Can LOW-GUARD++ remain formal validated?

`Yes as an audited locked result, but main-text upgrading should remain bounded and should add feature-provenance evidence because original100 has high-cardinality near-perfect separators.`

## 10. Need deeper audit or Slurm?

Slurm is not needed for this audit. A deeper audit is recommended if raw timestamp/packet IDs become available, because current benign split identity checks rely on feature fingerprints rather than packet-level provenance.

## 11. Issue27h

`issue27h_original100_feature_provenance_and_independent_verification_before_claim_upgrade`
