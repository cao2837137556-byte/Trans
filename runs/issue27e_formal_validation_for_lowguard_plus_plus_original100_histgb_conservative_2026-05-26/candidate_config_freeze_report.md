# Candidate Config Freeze Report

## Result

- candidate: `LOW_GUARD_HistGB_Conservative + original100`
- freeze_status: `not_recoverable_as_single_config`
- recovered_selected_config_count: `2`
- formal_validation_allowed: `false`

## Recovered selected configs from issue27d

| config_id | selected_count | selected_holdouts | selected_seeds | validation_target_values | mean_ood_val_alarm | max_ood_val_alarm | mean_support_val_detection | mean_support_val_margin |
|---|---|---|---|---|---|---|---|---|
| histgb_d2_lr003_l2p0_ood4_sup2_t0100 | 7 | holdout_bin_5;holdout_bin_6;holdout_bin_7;holdout_bin_8 | 42;43;44 | 0.01 | 0.002357 | 0.006500 | 0.892857 | 0.998459 |
| histgb_d2_lr005_l2p1_ood4_sup4_t0050 | 5 | holdout_bin_5;holdout_bin_6;holdout_bin_7;holdout_bin_8 | 43;44 | 0.005 | 0.000000 | 0.000000 | 1.000000 | 0.995148 |


## Why this blocks formal validation

The issue27d candidate was reported as an aggregate smoke result, but the original100 HistGB-Conservative selection trace does not identify one unique frozen `selected_config_id`. It selects two configs across the 12 smoke bin/seed combinations. Running full seeds with either one chosen after seeing the smoke aggregate would risk hindsight selection; running both and picking after final eval would be formal-validation leakage.

Therefore issue27e stops before full locked seed validation, as required by the Stage A rule.
