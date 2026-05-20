# Locked Validation Success Table

Status: `moderate_locked_validation`.

Reason: V2_top64 is feasible and improves over V1 on part of the locked set, but evidence is not uniformly strong.

Official 1% locked comparison:

| dataset | holdout | method | method_group | candidate | seed_group | ood_target | ood_target_label | n_seeds | roc_auc_mean | pr_auc_mean | pauc_fpr_1pct_mean | tpr_at_fpr_1pct_mean | attack_high_detection_mean | attack_high_detection_std | attack_high_detection_min | attack_high_detection_max | final_ood_high_alarm_mean | final_ood_high_alarm_max | feasible_rate | threshold_mean | support_size | feature_dim | selected_topk | train_time_mean | inference_time_mean | provenance_clean_rate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| locked_harder_holdout | holdout_bin_5 | M0_V1_original100_kcenter32_fixed_guard | baseline | V1 | heldout_47_51 | 0.010000 | 1.0pct | 5 | 0.995596 | 0.975033 | 0.959157 | 0.982896 | 0.966933 | 0.000000 | 0.966933 | 0.966933 | 0.001900 | 0.001900 | 1.000000 | -2.416828 | 32 | 100 | 0 | 1.698652 | 0.030259 | 1.000000 |
| locked_harder_holdout | holdout_bin_5 | M0_V1_original100_kcenter32_fixed_guard | baseline | V1 | main_42_46 | 0.010000 | 1.0pct | 5 | 0.995596 | 0.975033 | 0.959157 | 0.982896 | 0.966933 | 0.000000 | 0.966933 | 0.966933 | 0.001900 | 0.001900 | 1.000000 | -2.416828 | 32 | 100 | 0 | 1.608603 | 0.037397 | 1.000000 |
| locked_harder_holdout | holdout_bin_5 | M1_V2_source_rich_top32_kcenter32_fixed_guard | reference | V2_top32 | heldout_47_51 | 0.010000 | 1.0pct | 5 | 0.971021 | 0.968446 | 0.974256 | 0.966933 | 0.968073 | 0.000000 | 0.968073 | 0.968073 | 0.016900 | 0.016900 | 0.000000 | -2.764919 | 32 | 32 | 32 | 0.264912 | 0.011249 | 1.000000 |
| locked_harder_holdout | holdout_bin_5 | M1_V2_source_rich_top32_kcenter32_fixed_guard | reference | V2_top32 | main_42_46 | 0.010000 | 1.0pct | 5 | 0.971021 | 0.968446 | 0.974256 | 0.966933 | 0.968073 | 0.000000 | 0.968073 | 0.968073 | 0.016900 | 0.016900 | 0.000000 | -2.764919 | 32 | 32 | 32 | 0.260340 | 0.011283 | 1.000000 |
| locked_harder_holdout | holdout_bin_5 | M2_enhanced_V2_source_rich_top64_kcenter32_fixed_guard | locked_candidate | V2_top64 | heldout_47_51 | 0.010000 | 1.0pct | 5 | 0.981111 | 0.972785 | 0.983074 | 0.968073 | 0.968073 | 0.000000 | 0.968073 | 0.968073 | 0.004500 | 0.004500 | 1.000000 | -4.102580 | 32 | 64 | 64 | 0.582727 | 0.019777 | 1.000000 |
| locked_harder_holdout | holdout_bin_5 | M2_enhanced_V2_source_rich_top64_kcenter32_fixed_guard | locked_candidate | V2_top64 | main_42_46 | 0.010000 | 1.0pct | 5 | 0.981111 | 0.972785 | 0.983074 | 0.968073 | 0.968073 | 0.000000 | 0.968073 | 0.968073 | 0.004500 | 0.004500 | 1.000000 | -4.102580 | 32 | 64 | 64 | 0.568065 | 0.021681 | 1.000000 |
| locked_harder_holdout | holdout_bin_6 | M0_V1_original100_kcenter32_fixed_guard | baseline | V1 | heldout_47_51 | 0.010000 | 1.0pct | 5 | 0.997589 | 0.981986 | 0.961084 | 0.993007 | 0.979021 | 0.000000 | 0.979021 | 0.979021 | 0.001900 | 0.001900 | 1.000000 | -2.366562 | 32 | 100 | 0 | 1.648261 | 0.034826 | 1.000000 |
| locked_harder_holdout | holdout_bin_6 | M0_V1_original100_kcenter32_fixed_guard | baseline | V1 | main_42_46 | 0.010000 | 1.0pct | 5 | 0.997589 | 0.981986 | 0.961084 | 0.993007 | 0.979021 | 0.000000 | 0.979021 | 0.979021 | 0.001900 | 0.001900 | 1.000000 | -2.366562 | 32 | 100 | 0 | 1.605006 | 0.031355 | 1.000000 |
| locked_harder_holdout | holdout_bin_6 | M1_V2_source_rich_top32_kcenter32_fixed_guard | reference | V2_top32 | heldout_47_51 | 0.010000 | 1.0pct | 5 | 0.970131 | 0.970692 | 0.975552 | 0.970030 | 0.970030 | 0.000000 | 0.970030 | 0.970030 | 0.018400 | 0.018400 | 0.000000 | -2.985532 | 32 | 32 | 32 | 0.253110 | 0.011317 | 1.000000 |
| locked_harder_holdout | holdout_bin_6 | M1_V2_source_rich_top32_kcenter32_fixed_guard | reference | V2_top32 | main_42_46 | 0.010000 | 1.0pct | 5 | 0.970131 | 0.970692 | 0.975552 | 0.970030 | 0.970030 | 0.000000 | 0.970030 | 0.970030 | 0.018400 | 0.018400 | 0.000000 | -2.985532 | 32 | 32 | 32 | 0.255109 | 0.010807 | 1.000000 |
| locked_harder_holdout | holdout_bin_6 | M2_enhanced_V2_source_rich_top64_kcenter32_fixed_guard | locked_candidate | V2_top64 | heldout_47_51 | 0.010000 | 1.0pct | 5 | 0.982683 | 0.975058 | 0.984162 | 0.970030 | 0.970030 | 0.000000 | 0.970030 | 0.970030 | 0.004500 | 0.004500 | 1.000000 | -4.118561 | 32 | 64 | 64 | 0.579378 | 0.020697 | 1.000000 |
| locked_harder_holdout | holdout_bin_6 | M2_enhanced_V2_source_rich_top64_kcenter32_fixed_guard | locked_candidate | V2_top64 | main_42_46 | 0.010000 | 1.0pct | 5 | 0.982683 | 0.975058 | 0.984162 | 0.970030 | 0.970030 | 0.000000 | 0.970030 | 0.970030 | 0.004500 | 0.004500 | 1.000000 | -4.118561 | 32 | 64 | 64 | 0.574279 | 0.022135 | 1.000000 |
| locked_harder_holdout | holdout_bin_7 | M0_V1_original100_kcenter32_fixed_guard | baseline | V1 | heldout_47_51 | 0.010000 | 1.0pct | 5 | 0.999586 | 0.992956 | 0.979212 | 1.000000 | 0.997371 | 0.000000 | 0.997371 | 0.997371 | 0.002000 | 0.002000 | 1.000000 | -2.312668 | 32 | 100 | 0 | 1.355553 | 0.032889 | 1.000000 |
| locked_harder_holdout | holdout_bin_7 | M0_V1_original100_kcenter32_fixed_guard | baseline | V1 | main_42_46 | 0.010000 | 1.0pct | 5 | 0.999586 | 0.992956 | 0.979212 | 1.000000 | 0.997371 | 0.000000 | 0.997371 | 0.997371 | 0.002000 | 0.002000 | 1.000000 | -2.312668 | 32 | 100 | 0 | 1.414843 | 0.033553 | 1.000000 |
| locked_harder_holdout | holdout_bin_7 | M1_V2_source_rich_top32_kcenter32_fixed_guard | reference | V2_top32 | heldout_47_51 | 0.010000 | 1.0pct | 5 | 0.978186 | 0.980287 | 0.988800 | 0.978089 | 0.978089 | 0.000000 | 0.978089 | 0.978089 | 0.016800 | 0.016800 | 0.000000 | -2.824366 | 32 | 32 | 32 | 0.220960 | 0.009989 | 1.000000 |
| locked_harder_holdout | holdout_bin_7 | M1_V2_source_rich_top32_kcenter32_fixed_guard | reference | V2_top32 | main_42_46 | 0.010000 | 1.0pct | 5 | 0.978186 | 0.980287 | 0.988800 | 0.978089 | 0.978089 | 0.000000 | 0.978089 | 0.978089 | 0.016800 | 0.016800 | 0.000000 | -2.824366 | 32 | 32 | 32 | 0.234348 | 0.010878 | 1.000000 |
| locked_harder_holdout | holdout_bin_7 | M2_enhanced_V2_source_rich_top64_kcenter32_fixed_guard | locked_candidate | V2_top64 | heldout_47_51 | 0.010000 | 1.0pct | 5 | 0.981942 | 0.980478 | 0.987329 | 0.978089 | 0.978089 | 0.000000 | 0.978089 | 0.978089 | 0.004100 | 0.004100 | 1.000000 | -4.067457 | 32 | 64 | 64 | 0.583796 | 0.020229 | 1.000000 |
| locked_harder_holdout | holdout_bin_7 | M2_enhanced_V2_source_rich_top64_kcenter32_fixed_guard | locked_candidate | V2_top64 | main_42_46 | 0.010000 | 1.0pct | 5 | 0.981942 | 0.980478 | 0.987329 | 0.978089 | 0.978089 | 0.000000 | 0.978089 | 0.978089 | 0.004100 | 0.004100 | 1.000000 | -4.067457 | 32 | 64 | 64 | 0.617722 | 0.020608 | 1.000000 |
| locked_harder_holdout | holdout_bin_8 | M0_V1_original100_kcenter32_fixed_guard | baseline | V1 | heldout_47_51 | 0.010000 | 1.0pct | 5 | 0.978820 | 0.835447 | 0.867070 | 0.866197 | 0.835681 | 0.000000 | 0.835681 | 0.835681 | 0.005300 | 0.005300 | 1.000000 | -3.022682 | 32 | 100 | 0 | 1.267003 | 0.030399 | 1.000000 |
| locked_harder_holdout | holdout_bin_8 | M0_V1_original100_kcenter32_fixed_guard | baseline | V1 | main_42_46 | 0.010000 | 1.0pct | 5 | 0.978820 | 0.835447 | 0.867070 | 0.866197 | 0.835681 | 0.000000 | 0.835681 | 0.835681 | 0.005300 | 0.005300 | 1.000000 | -3.022682 | 32 | 100 | 0 | 1.244646 | 0.030633 | 1.000000 |
| locked_harder_holdout | holdout_bin_8 | M1_V2_source_rich_top32_kcenter32_fixed_guard | reference | V2_top32 | heldout_47_51 | 0.010000 | 1.0pct | 5 | 0.882654 | 0.813923 | 0.893151 | 0.793427 | 0.793427 | 0.000000 | 0.793427 | 0.793427 | 0.015500 | 0.015500 | 0.000000 | -3.056967 | 32 | 32 | 32 | 0.220045 | 0.010880 | 1.000000 |
| locked_harder_holdout | holdout_bin_8 | M1_V2_source_rich_top32_kcenter32_fixed_guard | reference | V2_top32 | main_42_46 | 0.010000 | 1.0pct | 5 | 0.882654 | 0.813923 | 0.893151 | 0.793427 | 0.793427 | 0.000000 | 0.793427 | 0.793427 | 0.015500 | 0.015500 | 0.000000 | -3.056967 | 32 | 32 | 32 | 0.221305 | 0.009067 | 1.000000 |
| locked_harder_holdout | holdout_bin_8 | M2_enhanced_V2_source_rich_top64_kcenter32_fixed_guard | locked_candidate | V2_top64 | heldout_47_51 | 0.010000 | 1.0pct | 5 | 0.964706 | 0.910811 | 0.936985 | 0.889671 | 0.882629 | 0.000000 | 0.882629 | 0.882629 | 0.004200 | 0.004200 | 1.000000 | -4.423521 | 32 | 64 | 64 | 0.546518 | 0.019120 | 1.000000 |
| locked_harder_holdout | holdout_bin_8 | M2_enhanced_V2_source_rich_top64_kcenter32_fixed_guard | locked_candidate | V2_top64 | main_42_46 | 0.010000 | 1.0pct | 5 | 0.964706 | 0.910811 | 0.936985 | 0.889671 | 0.882629 | 0.000000 | 0.882629 | 0.882629 | 0.004200 | 0.004200 | 1.000000 | -4.423521 | 32 | 64 | 64 | 0.544969 | 0.018932 | 1.000000 |


V2_top64 vs V1:

| holdout | seed_group | attack_high_detection_mean_V1 | attack_high_detection_mean_V2_top64 | v2top64_minus_v1_detection | final_ood_high_alarm_max_V1 | final_ood_high_alarm_max_V2_top64 | v2top64_minus_v1_ood_alarm |
|---|---|---|---|---|---|---|---|
| holdout_bin_5 | heldout_47_51 | 0.966933 | 0.968073 | 0.001140 | 0.001900 | 0.004500 | 0.002600 |
| holdout_bin_5 | main_42_46 | 0.966933 | 0.968073 | 0.001140 | 0.001900 | 0.004500 | 0.002600 |
| holdout_bin_6 | heldout_47_51 | 0.979021 | 0.970030 | -0.008991 | 0.001900 | 0.004500 | 0.002600 |
| holdout_bin_6 | main_42_46 | 0.979021 | 0.970030 | -0.008991 | 0.001900 | 0.004500 | 0.002600 |
| holdout_bin_7 | heldout_47_51 | 0.997371 | 0.978089 | -0.019281 | 0.002000 | 0.004100 | 0.002100 |
| holdout_bin_7 | main_42_46 | 0.997371 | 0.978089 | -0.019281 | 0.002000 | 0.004100 | 0.002100 |
| holdout_bin_8 | heldout_47_51 | 0.835681 | 0.882629 | 0.046948 | 0.005300 | 0.004200 | -0.001100 |
| holdout_bin_8 | main_42_46 | 0.835681 | 0.882629 | 0.046948 | 0.005300 | 0.004200 | -0.001100 |


V2_top64 vs V2_top32:

| holdout | seed_group | attack_high_detection_mean_V2_top32 | attack_high_detection_mean_V2_top64 | v2top64_minus_v2top32_detection | final_ood_high_alarm_max_V2_top32 | final_ood_high_alarm_max_V2_top64 | v2top64_minus_v2top32_ood_alarm |
|---|---|---|---|---|---|---|---|
| holdout_bin_5 | heldout_47_51 | 0.968073 | 0.968073 | 0.000000 | 0.016900 | 0.004500 | -0.012400 |
| holdout_bin_5 | main_42_46 | 0.968073 | 0.968073 | 0.000000 | 0.016900 | 0.004500 | -0.012400 |
| holdout_bin_6 | heldout_47_51 | 0.970030 | 0.970030 | 0.000000 | 0.018400 | 0.004500 | -0.013900 |
| holdout_bin_6 | main_42_46 | 0.970030 | 0.970030 | 0.000000 | 0.018400 | 0.004500 | -0.013900 |
| holdout_bin_7 | heldout_47_51 | 0.978089 | 0.978089 | 0.000000 | 0.016800 | 0.004100 | -0.012700 |
| holdout_bin_7 | main_42_46 | 0.978089 | 0.978089 | 0.000000 | 0.016800 | 0.004100 | -0.012700 |
| holdout_bin_8 | heldout_47_51 | 0.793427 | 0.882629 | 0.089202 | 0.015500 | 0.004200 | -0.011300 |
| holdout_bin_8 | main_42_46 | 0.793427 | 0.882629 | 0.089202 | 0.015500 | 0.004200 | -0.011300 |
