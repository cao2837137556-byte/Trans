# Best Available Clean Split Report

A large labeled full-Mirai split candidate was identified and should be prioritized before returning to the 80k-cache future-bin path.

| candidate_name | source_asset | total_rows | benign_rows | attack_rows | proposed_id_train | proposed_id_calib | proposed_ood_val | proposed_final_ood_eval | proposed_attack_support_pool | proposed_attack_eval | timestamp_or_order_basis | feature_compatibility | can_prioritize_over_80k_future_bin | clean_split_ready_now | blocked_reason | recommended_priority |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| full_mirai_labeled_restored115_chrono_split | full_mirai_labeled_feature_csv | 764137 | 121621 | 642516 | benign rows 0-60000 | benign rows 60000-80000 | benign rows 80000-100000 | benign rows 100000-121620 | early attack rows after benign prefix | later attack rows with purge gap | row_order_only; explicit timestamp not found in full csv | restored115_candidate; current frozen original100 config needs mapping/subset audit | True | False | Needs feature-compatibility audit and prior-use audit before LOW-GUARD++ original100 evaluation. | P0 |


Gate status:
- row counts and labels are sufficient;
- packet order is available by row index;
- explicit timestamps are available for the 100k official subset but not for the full 764k CSV;
- feature compatibility is not resolved because the full Mirai feature files appear restored115-style, while the frozen LOW-GUARD++ instance is original100 + HistGB;
- no frozen LOW-GUARD++ evaluation was run in issue27l.
