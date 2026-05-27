# Issue27f Config Freeze Then Formal Validation Summary

## Verdict

- primary_verdict: `lowguard_plus_plus_formal_validated`
- frozen_config_id: `histgb_d2_lr005_l2p1_ood4_sup4_t0050`
- full_formal_validation_executed: `true`

## 1. Unique config freeze

Yes. The frozen config was selected using train/cal/val-side evidence only. No final OOD eval or attack eval was used in the freeze.

## 2. Frozen config

`histgb_d2_lr005_l2p1_ood4_sup4_t0050`

## 3. Formal LOW-GUARD++ result

- locked mean / min / OOD max: `1.000000` / `1.000000` / `0.000100`
- feasible_rate: `1.000000`

## 4. LOW-GUARD-LR reference

- locked mean / min / OOD max: `0.949705` / `0.882629` / `0.004500`

## 5. Does it dominate LOW-GUARD-LR?

`True`

## 6. OOD <= 1%

`True`

## 7. Seed/bin collapse

no_single_bin_catastrophic_failure: `True`

| holdout | detection_mean | detection_min | ood_max |
|---|---|---|---|
| holdout_bin_5 | 1.000000 | 1.000000 | 0.000100 |
| holdout_bin_6 | 1.000000 | 1.000000 | 0.000100 |
| holdout_bin_7 | 1.000000 | 1.000000 | 0.000100 |
| holdout_bin_8 | 1.000000 | 1.000000 | 0.000100 |


## 8. Leakage / artifact risk

No severe leakage was found. Formal config freeze and thresholding did not use final OOD eval or attack eval.

## 9. Threshold target robustness

| method | threshold_target | locked_detection_mean | locked_detection_min | locked_ood_alarm_max | feasible_rate |
|---|---|---|---|---|---|
| LOW_GUARD_PLUS_PLUS_HistGB_original100_frozen | 0.005000 | 1.000000 | 1.000000 | 0.000100 | 1.000000 |
| LOW_GUARD_PLUS_PLUS_HistGB_original100_frozen | 0.007500 | 1.000000 | 1.000000 | 0.000100 | 1.000000 |
| LOW_GUARD_PLUS_PLUS_HistGB_original100_frozen | 0.010000 | 1.000000 | 1.000000 | 0.008300 | 1.000000 |


See `threshold_target_robustness_summary.csv` for all targets. The formal target remains the frozen pre-registered 0.005 target.

## 10. Upgrade to LOW-GUARD++?

`Yes`

## 11. Paper mainline

`The mainline can become minimal instance + performance instance, with LOW-GUARD-LR as minimal and LOW-GUARD++ HistGB as performance instance.`

## 12. Issue27g

`issue27g_deployment_robustness_for_lowguard_lr_and_lowguard_plus_plus`

## 13. Slurm

Not needed.
