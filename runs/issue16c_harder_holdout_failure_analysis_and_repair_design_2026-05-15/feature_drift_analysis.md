# Feature Drift Analysis

Feature drift is measured with standardized mean difference between attack train-pool rows and attack eval rows in original100 space.

| setting | comparison | source_count | target_count | mean_abs_smd | median_abs_smd | max_abs_smd | features_abs_smd_gt_0_5 | features_abs_smd_gt_1_0 | mean_feature_auc_abs_from_0_5 | max_feature_auc_abs_from_0_5 |
|---|---|---|---|---|---|---|---|---|---|---|
| current_primary | train_pool_vs_eval | 4122 | 1375 | 0.277607 | 0.282939 | 1.267315 | 6 | 2 | 0.073166 | 0.374018 |
| holdout_bin_2 | train_pool_vs_eval | 5523 | 1348 | 0.578360 | 0.506972 | 3.736777 | 55 | 9 | 0.110184 | 0.488503 |
| chrono_late_train_early_eval | train_pool_vs_eval | 2568 | 3426 | 0.309490 | 0.309849 | 1.729343 | 9 | 3 | 0.068225 | 0.428492 |

## Interpretation

The failure is attack-side: OOD high alarm stays far below 1%, while holdout_bin_2 attack detection collapses. Large feature shifts or high single-feature separability between train and eval indicate that the random few-shot support may not cover the harder attack window.
