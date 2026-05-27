# Available Independent Assets Diagnosis

Clean independent validation asset exists: `False`.

Current repository assets include locked bins and several non-locked consistency objects, but no row-level raw timestamp / packet-order / capture/session manifest sufficient for a clean new formal independent split.

| asset_name | asset_type | contains_original100 | contains_attack_eval | contains_timestamp | contains_packet_order | contains_capture_id | contains_bin_id | can_support_clean_independent_validation | can_support_consistency_only | leakage_risk |
|---|---|---|---|---|---|---|---|---|---|---|
| locked_holdout_bin_5 | locked_dataset_spec | True | True | False | False | False | True | already_used_locked_not_new_independent | False | low_for_current_locked_but_not_new |
| locked_holdout_bin_6 | locked_dataset_spec | True | True | False | False | False | True | already_used_locked_not_new_independent | False | low_for_current_locked_but_not_new |
| locked_holdout_bin_7 | locked_dataset_spec | True | True | False | False | False | True | already_used_locked_not_new_independent | False | low_for_current_locked_but_not_new |
| locked_holdout_bin_8 | locked_dataset_spec | True | True | False | False | False | True | already_used_locked_not_new_independent | False | low_for_current_locked_but_not_new |
| consistency_primary_lowood | consistency_dataset_spec | True | True | False | False | False | False | False | True | medium |
| consistency_chrono_late_train_early_eval | consistency_dataset_spec | True | True | False | False | False | True | False | True | medium |
| consistency_holdout_bin_2 | consistency_dataset_spec | True | True | False | False | False | True | False | True | medium |
| original100_id | npy | True | False | False | False | False | False | False | True | unknown_without_row_manifest |
| original100_ood | npy | True | False | False | False | False | False | False | True | unknown_without_row_manifest |
| original100_attack | csv | True | True | False | False | False | False | False | True | unknown_without_row_manifest |
| source_rich_id | npy | False | False | False | False | False | False | False | True | unknown_without_row_manifest |
| source_rich_ood | npy | False | False | False | False | False | False | False | True | unknown_without_row_manifest |
| source_rich_attack | npy | False | True | False | False | False | False | False | True | unknown_without_row_manifest |
| stage2_manifest | json | False | False | False | False | False | True | False | True | unknown_without_row_manifest |
| stage2_attack_manifest | json | False | False | False | False | False | True | False | True | medium_until_reconstruction_manifest_exists |
| raw_iot23_mirai_log_from_manifest | labeled | False | True | True | True | True | False | False | True | medium_until_reconstruction_manifest_exists |
| issue26b_metadata_recovery | metadata_audit | False | False | False | False | False | True | False | True | blocking_metadata_gap |
