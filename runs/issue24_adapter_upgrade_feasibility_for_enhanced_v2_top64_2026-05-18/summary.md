# Issue24 Adapter Upgrade Feasibility Summary

## Outcome

- Preflight passed: yes.
- Representation fixed: selected_source_rich_top64.
- Support fixed: kcenter32.
- topK search: no.
- final eval used for adapter selection: no.
- Adapter status: `negative_adapter_upgrade`.
- Best adapter by locked feasible mean/min ranking: `A0_lr_baseline`.
- Best locked detection mean: `0.949705`.
- Best locked detection min: `0.882629`.
- Best locked OOD max: `0.004500`.
- LR baseline locked detection mean: `0.949705`.
- LR baseline locked detection min: `0.882629`.
- LR baseline locked OOD max: `0.004500`.
- Best - LR locked mean delta: `0.000000`.
- Best - LR locked min delta: `0.000000`.
- Recommended next action: `retain_lr_as_main_adapter_then_strong_baselines_and_external_or_temporal_validation`.

## Locked Adapter Summary

| adapter | locked_detection_mean | locked_detection_min | locked_ood_alarm_max | locked_feasible_rate_mean | locked_pauc_fpr_1pct_mean | locked_tpr_at_fpr_1pct_mean | mean_train_time | mean_inference_time | mean_parameter_count | delta_detection_mean_vs_lr | delta_detection_min_vs_lr | delta_ood_alarm_max_vs_lr |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A0_lr_baseline | 0.949705 | 0.882629 | 0.004500 | 1.000000 | 0.972888 | 0.951466 | 0.517670 | 0.020435 | 65.000000 | 0.000000 | 0.000000 | 0.000000 |
| A1_low_fpr_weighted_lr | 0.949705 | 0.882629 | 0.004400 | 1.000000 | 0.972930 | 0.951466 | 1.022861 | 0.020732 | 65.000000 | 0.000000 | 0.000000 | -0.000100 |
| A2_linear_svm_margin | 0.672538 | 0.355869 | 0.018000 | 0.775000 | 0.801359 | 0.792551 | 0.069767 | 0.016740 | 65.000000 | -0.277167 | -0.526761 | 0.013500 |


## Bin-Level Main-Seed Snapshot

| holdout | adapter | attack_high_detection_mean | final_ood_high_alarm_max | pauc_fpr_1pct_mean | selected_config |
|---|---|---|---|---|---|
| holdout_bin_5 | A0_lr_baseline | 0.968073 | 0.004500 | 0.983074 | lr_fixed_guard |
| holdout_bin_5 | A1_low_fpr_weighted_lr | 0.968073 | 0.003900 | 0.983108 | lr_tail_q0.975_w8.0_a1.0 |
| holdout_bin_5 | A2_linear_svm_margin | 0.846294 | 0.011000 | 0.872126 | sgd_hinge_alpha0.0001_a2.0;sgd_hinge_alpha1e-05_a1.0 |
| holdout_bin_6 | A0_lr_baseline | 0.970030 | 0.004500 | 0.984162 | lr_fixed_guard |
| holdout_bin_6 | A1_low_fpr_weighted_lr | 0.970030 | 0.004400 | 0.984109 | lr_tail_q0.95_w4.0_a1.0;lr_tail_q0.975_w8.0_a1.0 |
| holdout_bin_6 | A2_linear_svm_margin | 0.759640 | 0.013500 | 0.845116 | sgd_hinge_alpha0.0001_a2.0;sgd_hinge_alpha1e-05_a1.0 |
| holdout_bin_7 | A0_lr_baseline | 0.978089 | 0.004100 | 0.987329 | lr_fixed_guard |
| holdout_bin_7 | A1_low_fpr_weighted_lr | 0.978089 | 0.003600 | 0.987226 | lr_tail_q0.95_w4.0_a1.0;lr_tail_q0.975_w8.0_a1.0 |
| holdout_bin_7 | A2_linear_svm_margin | 0.724452 | 0.014500 | 0.785399 | sgd_hinge_alpha0.0001_a2.0;sgd_hinge_alpha1e-05_a1.0 |
| holdout_bin_8 | A0_lr_baseline | 0.882629 | 0.004200 | 0.936985 | lr_fixed_guard |
| holdout_bin_8 | A1_low_fpr_weighted_lr | 0.882629 | 0.003700 | 0.937297 | lr_tail_q0.975_w4.0_a1.0;lr_tail_q0.975_w8.0_a1.0 |
| holdout_bin_8 | A2_linear_svm_margin | 0.438028 | 0.005900 | 0.711728 | sgd_hinge_alpha0.0001_a1.0;sgd_hinge_alpha0.0001_a2.0;sgd_hinge_alpha1e-05_a1.0 |


## Interpretation

This is a feasibility ablation. If the best adapter is not a stable improvement over LR under the 1% OOD constraint, LR remains the main adapter and the paper should frame representation plus low-alert guard as the stronger contribution.
