# Issue25c Strong Baseline Pack Summary

## Outcome

- Preflight passed: yes.
- Main method frozen: selected_source_rich_top64 + kcenter32 + fixed OOD guard LR.
- topK/support/adapter/threshold changed: no.
- final eval used for hyperparameter or threshold selection: no.
- Status: `strong_baseline_positive`.
- Strongest feasible locked method by mean/min detection: `M2_Enhanced_LOW_GUARD_top64_fixed_guard_LR`.
- Enhanced LOW-GUARD+ locked mean/min/OOD max: `0.949705` / `0.882629` / `0.004500`.
- Any baseline fully dominates main method under the locked low-alert criteria: `False`.
- Recommended next action: `issue26_second_environment_or_temporal_validation_for_enhanced_lowguard_top64_2026-05-18`.

## Locked Baseline Ranking

| method | baseline_category | locked_detection_mean | locked_detection_min | locked_ood_alarm_max | locked_feasible_rate_mean | delta_detection_mean_vs_main | delta_detection_min_vs_main | delta_ood_alarm_max_vs_main |
|---|---|---|---|---|---|---|---|---|
| M2_Enhanced_LOW_GUARD_top64_fixed_guard_LR | main_method | 0.949705 | 0.882629 | 0.004500 | 1.000000 | 0.000000 | 0.000000 | 0.000000 |
| M0_V1_original100_fixed_guard_LR | existing_detector_baseline | 0.944751 | 0.835681 | 0.005300 | 1.000000 | -0.004954 | -0.046948 | 0.000800 |
| M3_top64_no_guard_LR | component_ablation | 0.000000 | 0.000000 | 0.008300 | 1.000000 | -0.949705 | -0.882629 | 0.003800 |
| M4_top64_random32_fixed_guard_LR | component_ablation | 0.948943 | 0.886854 | 0.010300 | 0.975000 | -0.000762 | 0.004225 | 0.005800 |
| M8_DevNet_like_MLP_top64 | fewshot_anomaly | 0.949352 | 0.905164 | 0.010400 | 0.950000 | -0.000353 | 0.022535 | 0.005900 |
| M7_HistGB_shallow_top64 | nonlinear_tabular | 0.832218 | 0.362441 | 0.012300 | 0.925000 | -0.117487 | -0.520188 | 0.007800 |
| M6_OC_SVM_top64 | unsupervised_anomaly | 0.028613 | 0.002103 | 0.015600 | 0.750000 | -0.921093 | -0.880526 | 0.011100 |
| M9_DeepSAD_like_center_top64 | semisupervised_anomaly | 0.033757 | 0.003506 | 0.013400 | 0.250000 | -0.915949 | -0.879123 | 0.008900 |
| M1_V2_top32_fixed_guard_LR | existing_detector_baseline | 0.927405 | 0.793427 | 0.018400 | 0.000000 | -0.022300 | -0.089202 | 0.013900 |
| M5_Isolation_Forest_top64 | unsupervised_anomaly | 0.041896 | 0.000469 | 0.017900 | 0.000000 | -0.907810 | -0.882160 | 0.013400 |


## Interpretation

This is the first strong baseline execution under the issue25b three-layer fairness protocol. The conclusion is restricted to the current locked bins and consistency checks; it is not second-environment or external validation.
