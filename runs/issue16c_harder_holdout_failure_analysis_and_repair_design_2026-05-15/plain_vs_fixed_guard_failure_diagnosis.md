# Plain vs Fixed Guard Failure Diagnosis

## Harder-Holdout 32-Shot Core Rows

| holdout_name | method | seed_group | attack_high_detection_mean | attack_high_detection_min | ood_high_alarm_mean | ood_high_alarm_max | feasible_rate |
|---|---|---|---|---|---|---|---|
| chrono_late_train_early_eval | original100_fixed_guard_lr | heldout_47_51 | 0.733800 | 0.686807 | 0.001500 | 0.002400 | 1.000000 |
| chrono_late_train_early_eval | original100_plain_lr | heldout_47_51 | 0.734384 | 0.687099 | 0.002360 | 0.002900 | 1.000000 |
| chrono_late_train_early_eval | original100_fixed_guard_lr | main_42_46 | 0.691827 | 0.682720 | 0.001520 | 0.001700 | 1.000000 |
| chrono_late_train_early_eval | original100_plain_lr | main_42_46 | 0.691302 | 0.682428 | 0.002340 | 0.002900 | 1.000000 |
| holdout_bin_2 | original100_fixed_guard_lr | heldout_47_51 | 0.222700 | 0.199555 | 0.001480 | 0.001800 | 1.000000 |
| holdout_bin_2 | original100_plain_lr | heldout_47_51 | 0.225371 | 0.203264 | 0.001940 | 0.002300 | 1.000000 |
| holdout_bin_2 | original100_fixed_guard_lr | main_42_46 | 0.321217 | 0.232938 | 0.001540 | 0.003000 | 1.000000 |
| holdout_bin_2 | original100_plain_lr | main_42_46 | 0.323145 | 0.232938 | 0.002220 | 0.003500 | 1.000000 |

## Interpretation

- `holdout_bin_2` is weak for both plain LR and fixed-guard LR, so the failure is not primarily caused by the OOD guard.
- Fixed guard consistently lowers OOD high alarm relative to plain LR, but plain LR is already feasible under this local-calibration harder-holdout protocol.
- The guard's observed value in issue16b is alarm control, not attack-side recovery.
