# Support Coverage Analysis

| holdout_name | support_selection_method | positive_budget | seed_group | n_seeds | mean_pairwise_support_distance | min_pairwise_support_distance | attack_train_coverage_radius | mean_nearest_support_distance_attack_train | mean_nearest_support_distance_attack_eval_diagnostic | pct_attack_eval_within_train_pool_p95_coverage_diagnostic |
|---|---|---|---|---|---|---|---|---|---|---|
| chrono_late_train_early_eval | density_aware_32shot | 32 | heldout_47_51 | 5 | 16.437239 | 7.388158 | 49.153507 | 5.058962 | 337.353452 | 0.371570 |
| chrono_late_train_early_eval | diversity_32shot | 32 | heldout_47_51 | 5 | 32.930964 | 11.664721 | 11.569871 | 7.075786 | 338.210587 | 0.375423 |
| chrono_late_train_early_eval | kcenter_32shot | 32 | heldout_47_51 | 5 | 32.853012 | 11.704074 | 11.459315 | 6.597782 | 338.094940 | 0.360771 |
| chrono_late_train_early_eval | random_32shot_baseline | 32 | heldout_47_51 | 5 | 12.479555 | 0.816441 | 49.506762 | 4.673928 | 337.483286 | 0.399124 |
| chrono_late_train_early_eval | stratified_bin_32shot | 32 | heldout_47_51 | 5 | 35.889309 | 0.783384 | 16.198151 | 6.640209 | 338.274976 | 0.385873 |
| chrono_late_train_early_eval | density_aware_32shot | 32 | main_42_46 | 5 | 16.437239 | 7.388158 | 49.153507 | 5.058962 | 337.353452 | 0.371570 |
| chrono_late_train_early_eval | diversity_32shot | 32 | main_42_46 | 5 | 32.826494 | 11.977535 | 11.732148 | 7.315679 | 338.350641 | 0.371921 |
| chrono_late_train_early_eval | kcenter_32shot | 32 | main_42_46 | 5 | 32.853012 | 11.704074 | 11.459315 | 6.597782 | 338.094940 | 0.360771 |
| chrono_late_train_early_eval | random_32shot_baseline | 32 | main_42_46 | 5 | 13.994278 | 1.187550 | 49.410298 | 4.421782 | 337.318743 | 0.396322 |
| chrono_late_train_early_eval | stratified_bin_32shot | 32 | main_42_46 | 5 | 35.889309 | 0.783384 | 16.198151 | 6.640209 | 338.274976 | 0.385873 |
| holdout_bin_2 | density_aware_32shot | 32 | heldout_47_51 | 5 | 16.602688 | 8.171710 | 115.050606 | 5.381992 | 308.106342 | 0.092730 |
| holdout_bin_2 | diversity_32shot | 32 | heldout_47_51 | 5 | 43.806063 | 14.286958 | 14.035555 | 8.064094 | 306.481246 | 0.130861 |
| holdout_bin_2 | kcenter_32shot | 32 | heldout_47_51 | 5 | 44.120945 | 13.520003 | 13.503877 | 7.580531 | 306.347577 | 0.126855 |
| holdout_bin_2 | random_32shot_baseline | 32 | heldout_47_51 | 5 | 11.931713 | 1.103152 | 115.841772 | 4.524086 | 311.634037 | 0.068398 |
| holdout_bin_2 | stratified_bin_32shot | 32 | heldout_47_51 | 5 | 45.913818 | 1.226229 | 25.005463 | 7.146006 | 309.716309 | 0.070475 |
| holdout_bin_2 | density_aware_32shot | 32 | main_42_46 | 5 | 16.602688 | 8.171710 | 115.050606 | 5.381992 | 308.106342 | 0.092730 |
| holdout_bin_2 | diversity_32shot | 32 | main_42_46 | 5 | 43.903333 | 14.029397 | 13.880235 | 7.957968 | 306.878846 | 0.110237 |
| holdout_bin_2 | kcenter_32shot | 32 | main_42_46 | 5 | 44.120945 | 13.520003 | 13.503877 | 7.580531 | 306.347577 | 0.126855 |
| holdout_bin_2 | random_32shot_baseline | 32 | main_42_46 | 5 | 13.183497 | 1.145481 | 114.706209 | 4.809332 | 311.868431 | 0.082047 |
| holdout_bin_2 | stratified_bin_32shot | 32 | main_42_46 | 5 | 45.913818 | 1.226229 | 25.005463 | 7.146006 | 309.716309 | 0.070475 |

Coverage metrics are diagnostic. Eval-nearest-support distance is reported only after support selection and is never used to choose supports.
