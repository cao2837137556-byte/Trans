# Locked Validation Asset Report

The v7.4 paired hard-holdout assets provide multiple leave-one-attack-window-out bins. issue22 selected V2_top64 after inspecting primary_lowood, holdout_bin_2, and chrono_late_train_early_eval. Since chrono_late evaluates bins 2/3/4, `holdout_bin_3` and `holdout_bin_4` are excluded from locked proof even though they exist.

Main locked objects used here:

| holdout_name | holdout_type | train_bins | eval_bins | train_pool_count | attack_eval_count | used_in_issue22_discovery_eval | locked_validation_object | asset_status | reason |
|---|---|---|---|---|---|---|---|---|---|
| holdout_bin_5 | leave_one_attack_window_out | 2,3,4,6,7,8 | 5 | 5994 | 877 | False | True | locked_used | unused leave-one-bin eval object |
| holdout_bin_6 | leave_one_attack_window_out | 2,3,4,5,7,8 | 6 | 5870 | 1001 | False | True | locked_used | unused leave-one-bin eval object |
| holdout_bin_7 | leave_one_attack_window_out | 2,3,4,5,6,8 | 7 | 5730 | 1141 | False | True | locked_used | unused leave-one-bin eval object |
| holdout_bin_8 | leave_one_attack_window_out | 2,3,4,5,6,7 | 8 | 6445 | 426 | False | True | locked_used | unused leave-one-bin eval object |


Full candidate inventory:

| holdout_name | holdout_type | train_bins | eval_bins | train_pool_count | attack_eval_count | used_in_issue22_discovery_eval | locked_validation_object | asset_status | reason |
|---|---|---|---|---|---|---|---|---|---|
| chrono_early_train_late_eval | chronological_cross_window | 2,3,4 | 6,7,8 | 3426 | 2568 | False | False | excluded | not selected for this locked pass |
| chrono_late_train_early_eval | chronological_cross_window | 6,7,8 | 2,3,4 | 2568 | 3426 | True | False | excluded | not selected for this locked pass |
| holdout_bin_2 | leave_one_attack_window_out | 3,4,5,6,7,8 | 2 | 5523 | 1348 | True | False | excluded | used directly in issue22 top64 discovery |
| holdout_bin_3 | leave_one_attack_window_out | 2,4,5,6,7,8 | 3 | 5913 | 958 | True | False | excluded | eval bin overlaps issue22 chrono_late discovery eval bins |
| holdout_bin_4 | leave_one_attack_window_out | 2,3,5,6,7,8 | 4 | 5751 | 1120 | True | False | excluded | eval bin overlaps issue22 chrono_late discovery eval bins |
| holdout_bin_5 | leave_one_attack_window_out | 2,3,4,6,7,8 | 5 | 5994 | 877 | False | True | locked_used | unused leave-one-bin eval object |
| holdout_bin_6 | leave_one_attack_window_out | 2,3,4,5,7,8 | 6 | 5870 | 1001 | False | True | locked_used | unused leave-one-bin eval object |
| holdout_bin_7 | leave_one_attack_window_out | 2,3,4,5,6,8 | 7 | 5730 | 1141 | False | True | locked_used | unused leave-one-bin eval object |
| holdout_bin_8 | leave_one_attack_window_out | 2,3,4,5,6,7 | 8 | 6445 | 426 | False | True | locked_used | unused leave-one-bin eval object |
