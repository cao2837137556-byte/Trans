# Clean Eval Eligibility Rules

| rule_id | rule | candidate_assessed | status | notes |
|---|---|---|---|---|
| sufficient_final_ood_rows | final_ood_eval_count should be large enough for low-alert alarm estimates; thousands preferred. | extended_attack_10k_30k_plus_future_benign_90k_110k | pass | Satisfiable under the extended unused-segment candidate. |
| sufficient_attack_eval_rows | attack_eval_count should be large enough for stable detection estimates. | extended_attack_10k_30k_plus_future_benign_90k_110k | pass | Satisfiable under the extended unused-segment candidate. |
| clear_train_cal_val_eval_time_ranges | time/order ranges must be explicit. | extended_attack_10k_30k_plus_future_benign_90k_110k | pass | Satisfiable under the extended unused-segment candidate. |
| support_eval_disjoint | attack supports must come only from train-side attack pool. | extended_attack_10k_30k_plus_future_benign_90k_110k | pass | Satisfiable under the extended unused-segment candidate. |
| threshold_train_val_only | threshold must come from ID_calib + OOD_val only. | extended_attack_10k_30k_plus_future_benign_90k_110k | pass | Satisfiable under the extended unused-segment candidate. |
| eval_not_used_for_selection | eval asset cannot select config/support/threshold/features. | extended_attack_10k_30k_plus_future_benign_90k_110k | pass | Satisfiable under the extended unused-segment candidate. |
| no_locked_overlap | overlap with locked bins 5/6/7/8 means consistency-only. | extended_attack_10k_30k_plus_future_benign_90k_110k | pass_for_extended_candidate | Satisfiable under the extended unused-segment candidate. |
| purge_or_disjoint_available | same-capture temporal split needs purge or online-state protocol. | extended_attack_10k_30k_plus_future_benign_90k_110k | partial | Satisfiable under the extended unused-segment candidate. |
| row_timestamp_order_complete | row-level timestamp/order must be complete. | extended_attack_10k_30k_plus_future_benign_90k_110k | pass | Satisfiable under the extended unused-segment candidate. |
| bin9_not_alone | future bin9 208 rows cannot be formal validation alone. | extended_attack_10k_30k_plus_future_benign_90k_110k | pass | Satisfiable under the extended unused-segment candidate. |
| split_aware_rebuild_ready | split-aware original100 features must exist before clean evaluation. | extended_attack_10k_30k_plus_future_benign_90k_110k | fail | Blocks clean claim until fixed. |
| prior_use_audit_passed | historically used assets cannot be promoted without explicit prior-use audit. | extended_attack_10k_30k_plus_future_benign_90k_110k | fail | Blocks clean claim until fixed. |


Interpretation:
- Row counts are no longer the main blocker for the P0 extended-segment candidate.
- The blockers are claim-safety blockers: prior-use audit, same-capture benign evidence weakness, and missing split-aware feature rebuild.
- Future bin9 with 208 rows remains explicitly disallowed as a stand-alone formal validation object.
