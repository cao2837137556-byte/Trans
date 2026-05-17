# Issue17 Support Diversity Selection Summary

## Outcome

Preflight provenance passed. The experiment used local harder-holdout attack train pools only and did not use attack eval or final OOD eval for support selection.

## Core Results

| holdout_name | support_selection_method | seed_group | attack_high_detection_mean | attack_high_detection_min | ood_high_alarm_mean | ood_high_alarm_max | feasible_rate | support_diversity_mean |
|---|---|---|---|---|---|---|---|---|
| chrono_late_train_early_eval | density_aware_32shot | heldout_47_51 | 0.678342 | 0.678342 | 0.001300 | 0.001300 | 1.000000 | 16.437239 |
| chrono_late_train_early_eval | diversity_32shot | heldout_47_51 | 0.682370 | 0.677466 | 0.001740 | 0.001900 | 1.000000 | 32.930964 |
| chrono_late_train_early_eval | kcenter_32shot | heldout_47_51 | 0.679802 | 0.679802 | 0.001800 | 0.001800 | 1.000000 | 32.853012 |
| chrono_late_train_early_eval | random_32shot_baseline | heldout_47_51 | 0.733800 | 0.686807 | 0.001500 | 0.002400 | 1.000000 | 12.479555 |
| chrono_late_train_early_eval | stratified_bin_32shot | heldout_47_51 | 0.687974 | 0.687974 | 0.002200 | 0.002200 | 1.000000 | 35.889309 |
| chrono_late_train_early_eval | density_aware_32shot | main_42_46 | 0.678342 | 0.678342 | 0.001300 | 0.001300 | 1.000000 | 16.437239 |
| chrono_late_train_early_eval | diversity_32shot | main_42_46 | 0.686340 | 0.677758 | 0.001860 | 0.002100 | 1.000000 | 32.826494 |
| chrono_late_train_early_eval | kcenter_32shot | main_42_46 | 0.679802 | 0.679802 | 0.001800 | 0.001800 | 1.000000 | 32.853012 |
| chrono_late_train_early_eval | random_32shot_baseline | main_42_46 | 0.691827 | 0.682720 | 0.001520 | 0.001700 | 1.000000 | 13.994278 |
| chrono_late_train_early_eval | stratified_bin_32shot | main_42_46 | 0.687974 | 0.687974 | 0.002200 | 0.002200 | 1.000000 | 35.889309 |
| holdout_bin_2 | density_aware_32shot | heldout_47_51 | 0.225519 | 0.225519 | 0.001300 | 0.001300 | 1.000000 | 16.602688 |
| holdout_bin_2 | diversity_32shot | heldout_47_51 | 0.295401 | 0.240356 | 0.001320 | 0.001700 | 1.000000 | 43.806063 |
| holdout_bin_2 | kcenter_32shot | heldout_47_51 | 0.326409 | 0.326409 | 0.001100 | 0.001100 | 1.000000 | 44.120945 |
| holdout_bin_2 | random_32shot_baseline | heldout_47_51 | 0.222700 | 0.199555 | 0.001480 | 0.001800 | 1.000000 | 11.931713 |
| holdout_bin_2 | stratified_bin_32shot | heldout_47_51 | 0.260386 | 0.260386 | 0.001400 | 0.001400 | 1.000000 | 45.913818 |
| holdout_bin_2 | density_aware_32shot | main_42_46 | 0.225519 | 0.225519 | 0.001300 | 0.001300 | 1.000000 | 16.602688 |
| holdout_bin_2 | diversity_32shot | main_42_46 | 0.312018 | 0.241098 | 0.001000 | 0.001700 | 1.000000 | 43.903333 |
| holdout_bin_2 | kcenter_32shot | main_42_46 | 0.326409 | 0.326409 | 0.001100 | 0.001100 | 1.000000 | 44.120945 |
| holdout_bin_2 | random_32shot_baseline | main_42_46 | 0.321217 | 0.232938 | 0.001540 | 0.003000 | 1.000000 | 13.183497 |
| holdout_bin_2 | stratified_bin_32shot | main_42_46 | 0.260386 | 0.260386 | 0.001400 | 0.001400 | 1.000000 | 45.913818 |

## Random vs Diverse Delta

| holdout_name | support_selection_method | positive_budget | seed_group | delta_detection_vs_random | delta_ood_alarm_mean_vs_random | delta_ood_alarm_max_vs_random | delta_feasible_rate_vs_random | delta_support_diversity_vs_random | delta_train_coverage_radius_vs_random | delta_eval_nearest_distance_vs_random_diagnostic |
|---|---|---|---|---|---|---|---|---|---|---|
| chrono_late_train_early_eval | density_aware_32shot | 32 | heldout_47_51 | -0.055458 | -0.000200 | -0.001100 | 0.000000 | 3.957683 | -0.353255 | -0.129834 |
| chrono_late_train_early_eval | diversity_32shot | 32 | heldout_47_51 | -0.051430 | 0.000240 | -0.000500 | 0.000000 | 20.451409 | -37.936891 | 0.727301 |
| chrono_late_train_early_eval | kcenter_32shot | 32 | heldout_47_51 | -0.053999 | 0.000300 | -0.000600 | 0.000000 | 20.373457 | -38.047447 | 0.611653 |
| chrono_late_train_early_eval | stratified_bin_32shot | 32 | heldout_47_51 | -0.045826 | 0.000700 | -0.000200 | 0.000000 | 23.409754 | -33.308611 | 0.791690 |
| chrono_late_train_early_eval | density_aware_32shot | 32 | main_42_46 | -0.013485 | -0.000220 | -0.000400 | 0.000000 | 2.442961 | -0.256791 | 0.034709 |
| chrono_late_train_early_eval | diversity_32shot | 32 | main_42_46 | -0.005487 | 0.000340 | 0.000400 | 0.000000 | 18.832216 | -37.678150 | 1.031898 |
| chrono_late_train_early_eval | kcenter_32shot | 32 | main_42_46 | -0.012026 | 0.000280 | 0.000100 | 0.000000 | 18.858734 | -37.950983 | 0.776196 |
| chrono_late_train_early_eval | stratified_bin_32shot | 32 | main_42_46 | -0.003853 | 0.000680 | 0.000500 | 0.000000 | 21.895031 | -33.212148 | 0.956233 |
| holdout_bin_2 | density_aware_32shot | 32 | heldout_47_51 | 0.002819 | -0.000180 | -0.000500 | 0.000000 | 4.670975 | -0.791167 | -3.527695 |
| holdout_bin_2 | diversity_32shot | 32 | heldout_47_51 | 0.072700 | -0.000160 | -0.000100 | 0.000000 | 31.874350 | -101.806217 | -5.152791 |
| holdout_bin_2 | kcenter_32shot | 32 | heldout_47_51 | 0.103709 | -0.000380 | -0.000700 | 0.000000 | 32.189232 | -102.337896 | -5.286459 |
| holdout_bin_2 | stratified_bin_32shot | 32 | heldout_47_51 | 0.037685 | -0.000080 | -0.000400 | 0.000000 | 33.982105 | -90.836310 | -1.917727 |
| holdout_bin_2 | density_aware_32shot | 32 | main_42_46 | -0.095697 | -0.000240 | -0.001700 | 0.000000 | 3.419191 | 0.344397 | -3.762089 |
| holdout_bin_2 | diversity_32shot | 32 | main_42_46 | -0.009199 | -0.000540 | -0.001300 | 0.000000 | 30.719835 | -100.825974 | -4.989585 |
| holdout_bin_2 | kcenter_32shot | 32 | main_42_46 | 0.005193 | -0.000440 | -0.001900 | 0.000000 | 30.937448 | -101.202332 | -5.520854 |
| holdout_bin_2 | stratified_bin_32shot | 32 | main_42_46 | -0.060831 | -0.000140 | -0.001600 | 0.000000 | 32.730321 | -89.700746 | -2.152122 |

## Verdict

`moderate_or_mixed_support_signal`

Best holdout_bin_2 method by average delta: `kcenter_32shot`, mean_delta_detection_vs_random=0.054451, min_delta=0.005193, max_delta=0.103709, min_abs_detection=0.326409.

This is not a strong positive: the best method improves held-out seed behavior but does not deliver high absolute detection on `holdout_bin_2`, and the main seed group improvement is small.

## Interpretation

Support diversity is meaningful only if it improves holdout_bin_2 detection while keeping OOD high alarm <= 1%. This run does not change the LOW-GUARD-minimal model family, OOD weight, threshold protocol, or manuscript.

## Safety

- Manuscript modified: False.
- Historical experimental numbers modified: False.
- dA / Transformer trained: False.
- OOD weight search: False.
- Eval data used for support selection: False.
