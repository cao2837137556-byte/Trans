# Issue18 Row-Level Score Persistence and OOD Target Sensitivity Summary

## Outcome

Row-level scores were successfully saved to `row_level_scores.parquet`.

## Holdout Bin 2 Core Diagnostic Results

| holdout | support_method | seed_group | target_label | attack_high_detection_mean | attack_high_detection_min | ood_high_alarm_mean | ood_high_alarm_max | attack_margin_q50_mean | attack_margin_q75_mean |
|---|---|---|---|---|---|---|---|---|---|
| holdout_bin_2 | kcenter_32shot | heldout_47_51 | 0.5pct | 0.320475 | 0.320475 | 0.001000 | 0.001000 | -19.054650 | 3.837805 |
| holdout_bin_2 | kcenter_32shot | heldout_47_51 | 1pct | 0.326409 | 0.326409 | 0.001100 | 0.001100 | -18.509926 | 4.382530 |
| holdout_bin_2 | kcenter_32shot | heldout_47_51 | 2pct | 0.335312 | 0.335312 | 0.001600 | 0.001600 | -18.083397 | 4.809059 |
| holdout_bin_2 | kcenter_32shot | main_42_46 | 0.5pct | 0.320475 | 0.320475 | 0.001000 | 0.001000 | -19.054650 | 3.837805 |
| holdout_bin_2 | kcenter_32shot | main_42_46 | 1pct | 0.326409 | 0.326409 | 0.001100 | 0.001100 | -18.509926 | 4.382530 |
| holdout_bin_2 | kcenter_32shot | main_42_46 | 2pct | 0.335312 | 0.335312 | 0.001600 | 0.001600 | -18.083397 | 4.809059 |
| holdout_bin_2 | random_32shot_baseline | heldout_47_51 | 0.5pct | 0.212315 | 0.184718 | 0.001280 | 0.001400 | -30.238604 | -2.988307 |
| holdout_bin_2 | random_32shot_baseline | heldout_47_51 | 1pct | 0.222700 | 0.199555 | 0.001480 | 0.001800 | -29.656150 | -2.405852 |
| holdout_bin_2 | random_32shot_baseline | heldout_47_51 | 2pct | 0.227151 | 0.204006 | 0.001620 | 0.001900 | -29.385384 | -2.135087 |
| holdout_bin_2 | random_32shot_baseline | main_42_46 | 0.5pct | 0.314392 | 0.227003 | 0.001360 | 0.002700 | -16.843149 | 2.798157 |
| holdout_bin_2 | random_32shot_baseline | main_42_46 | 1pct | 0.321217 | 0.232938 | 0.001540 | 0.003000 | -16.349033 | 3.292272 |
| holdout_bin_2 | random_32shot_baseline | main_42_46 | 2pct | 0.326855 | 0.234421 | 0.001720 | 0.003200 | -16.070431 | 3.570875 |

## Diagnostic Decision

`D4_support_method_specific_partial`

K-center materially improves attack margins versus random support, but the 2% diagnostic target still leaves detection low; support acquisition is a partial repair, not a solution to the underlying representation/score bottleneck.

## Interpretation

OOD target sensitivity is diagnostic only. No target is selected as a new method setting in this run.

## Next Step

Formalize support acquisition only as a partial repair, then test representation repair.

## Safety

- Manuscript modified: False.
- Historical experimental numbers modified: False.
- dA / Transformer trained: False.
- New model family introduced: False.
- OOD weight changed: False.
- Final eval used for threshold selection: False.
