# Purged Split Design Report

Purged or clean chronological split constructed: `False`.

| split_name | train_time_range | calib_time_range | ood_val_time_range | purge_gap | final_eval_time_range | attack_support_source | attack_eval_source | id_train_count | ood_train_count | id_calib_count | ood_val_count | final_ood_eval_count | attack_support_count | attack_eval_count | can_construct | blocked_reason | leakage_risk | evidence_level |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| chronological_forward_existing_bins_2_4_to_6_8 | attack bins 2-4 | ID 8000-12999; OOD 8000-9999 | OOD 8000-9999 | bin 5 | attack bins 6-8 | attack bins 2-4 | attack bins 6-8 | 8000 | 8000 | 5000 | 2000 | 10000 | 32 | 2568 | False | Constructable as a purged chrono object but eval bins 6/7/8 already overlap locked evidence; not clean independent. | medium_repeated_locked_bin_analysis | consistency_only_not_formal_clean |
| future_window_bin9_eval | attack bins 2-8 excluding eval | ID/OOD locked calibration | OOD 8000-9999 | none_or_bin8_gap_required | attack bin 9 | attack bins 2-8 | attack bin 9 | 8000 | 8000 | 5000 | 2000 | 10000 | 32 | 208 | False | Bin 9 has only 208 packet rows, below the prior min_eval_rows=300 gate and too small for stable formal validation. | medium_small_eval_and_adjacent_state | diagnostic_only_if_run_later |
| capture_disjoint_attack_eval | current attack capture train | current ID/OOD calibration | current OOD validation | capture-disjoint | new attack capture/session | current or new train capture | new unused capture/session | 8000 | 8000 | 5000 | 2000 | needs_new_ood_or_prespecified_current | 32 | unknown | False | No unused attack capture/session with original100 assets is currently available. | low_if_constructed | blocked |
| purged_split_with_splitwise_feature_reset | to be selected after sidecar hash verification | disjoint validation side | disjoint OOD validation side | packet/time embargo around split | future window after gap | pre-eval train window | post-gap eval window | 50000 | depends_on_design | depends_on_design | depends_on_design | depends_on_design | 32 | needs_more_future_rows | False | Need split-aware feature rebuild and enough post-gap attack/OOD rows before formal evaluation. | low_after_rebuild | issue27l_candidate |


Conclusion:
- A row-level manifest now exists.
- Existing bins can be mapped to timestamps.
- Formal clean validation is still blocked because the usable post-locked future window is too small, and candidate chrono splits reuse previously analyzed locked bins.
