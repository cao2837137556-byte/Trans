# HistGB Feature Importance Diagnosis

Permutation importance was computed as report-only explanation with the frozen model. It was not used for model selection.

Top final-side permutation drops:

| holdout | seed | feature_index | feature_name_if_available | is_separator_top3 | final_auc_drop | validation_auc_drop | attack_detection_drop |
|---|---|---|---|---|---|---|---|
| holdout_bin_7 | 42 | 12 | MI_dir_weight_lambda_0.01 | False | 0.080529 | 0.007504 | 0.000000 |
| holdout_bin_6 | 42 | 12 | MI_dir_weight_lambda_0.01 | False | 0.051844 | 0.004268 | 0.000000 |
| holdout_bin_5 | 42 | 12 | MI_dir_weight_lambda_0.01 | False | 0.044864 | 0.004219 | 0.000000 |
| holdout_bin_8 | 42 | 47 | HH_magnitude_lambda_0.01 | True | 0.005047 | 0.000000 | 0.042254 |
| holdout_bin_5 | 42 | 47 | HH_magnitude_lambda_0.01 | True | 0.001605 | 0.000000 | 0.017104 |
| holdout_bin_6 | 42 | 47 | HH_magnitude_lambda_0.01 | True | 0.001305 | 0.000000 | 0.011988 |
| holdout_bin_7 | 42 | 47 | HH_magnitude_lambda_0.01 | True | 0.000726 | 0.000000 | 0.007011 |
| holdout_bin_7 | 42 | 46 | HH_radius_lambda_0.01 | True | 0.000117 | 0.000022 | 0.002629 |
| holdout_bin_8 | 42 | 12 | MI_dir_weight_lambda_0.01 | False | 0.000100 | 0.006536 | 0.000000 |
| holdout_bin_6 | 42 | 46 | HH_radius_lambda_0.01 | True | 0.000022 | 0.000000 | 0.000000 |
| holdout_bin_5 | 42 | 0 | MI_dir_weight_lambda_5 | False | 0.000000 | 0.000000 | 0.000000 |
| holdout_bin_6 | 42 | 48 | HH_covariance_lambda_0.01 | False | 0.000000 | 0.000000 | 0.000000 |
| holdout_bin_8 | 42 | 0 | MI_dir_weight_lambda_5 | False | 0.000000 | 0.000000 | 0.000000 |
| holdout_bin_5 | 42 | 1 | MI_dir_mean_lambda_5 | False | 0.000000 | 0.000000 | 0.000000 |
| holdout_bin_5 | 42 | 2 | MI_dir_std_lambda_5 | False | 0.000000 | 0.000000 | 0.000000 |
| holdout_bin_5 | 42 | 3 | MI_dir_weight_lambda_3 | False | 0.000000 | 0.000000 | 0.000000 |
| holdout_bin_5 | 42 | 4 | MI_dir_mean_lambda_3 | False | 0.000000 | 0.000000 | 0.000000 |
| holdout_bin_5 | 42 | 5 | MI_dir_std_lambda_3 | False | 0.000000 | 0.000000 | 0.000000 |
| holdout_bin_5 | 42 | 6 | MI_dir_weight_lambda_1 | False | 0.000000 | 0.000000 | 0.000000 |
| holdout_bin_5 | 42 | 7 | MI_dir_mean_lambda_1 | False | 0.000000 | 0.000000 | 0.000000 |


Top3 separator final AUC drop share: `0.047384`.

Interpretation: model reliance should be judged together with ablation. If top3-only is strong but remove-top3 also remains strong, the model has redundant traffic-stat evidence rather than a single-feature-only failure mode.
