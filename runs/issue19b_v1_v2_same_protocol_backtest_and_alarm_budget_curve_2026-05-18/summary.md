# Issue19b V1/V2 Same-Protocol Backtest Summary

## Outcome

- Preflight passed: yes.
- V1 definition: `original100 + kcenter32 + fixed guard LR`.
- V2 definition: `selected_source_rich_top32 + kcenter32 + fixed guard LR`.
- Evaluated settings: primary low-OOD, holdout_bin_2, chrono_late_train_early_eval.
- Ordinary normal-vs-attack compatibility check: not run; see `ordinary_setting_v1_v2_summary.csv`.
- V2 primary non-regression at 1% target: False.
- V2 holdout_bin_2 repair remains positive at 1% target: True.
- V2 chrono_late not-harmed criterion: True.
- Recommended locked-validation status: V2 evidence is mixed; locked validation should be mode-specific or preceded by routing analysis.

## Core 1% Target Table

| dataset | holdout | seed_group | v1_detection_mean | v1_ood_alarm_max | v2_detection_mean | v2_ood_alarm_max | delta_detection_v2_minus_v1 |
|---|---|---|---|---|---|---|---|
| harder_holdout | chrono_late_train_early_eval | heldout_47_51 | 0.679802 | 0.001800 | 0.731465 | 0.009700 | 0.051664 |
| harder_holdout | chrono_late_train_early_eval | main_42_46 | 0.679802 | 0.001800 | 0.731465 | 0.009700 | 0.051664 |
| harder_holdout | holdout_bin_2 | heldout_47_51 | 0.326409 | 0.001100 | 0.809347 | 0.006800 | 0.482938 |
| harder_holdout | holdout_bin_2 | main_42_46 | 0.326409 | 0.001100 | 0.809347 | 0.006800 | 0.482938 |
| primary_lowood | primary_lowood | heldout_47_51 | 0.929455 | 0.003600 | 0.924364 | 0.015600 | -0.005091 |
| primary_lowood | primary_lowood | main_42_46 | 0.929455 | 0.003600 | 0.924364 | 0.015600 | -0.005091 |


## Alarm-Budget Curve Finding

The curve reports all pre-registered validation OOD targets: 0.5%, 0.8%, 1.0%, 1.2%, 1.5%, and 2.0%. Feasible operating points are diagnostic only; no final threshold is changed here.

Candidate V2 targets among 1.2%/1.5% with final OOD max <= 1%:

| dataset | holdout | seed_group | ood_target_label | attack_high_detection_mean | final_ood_high_alarm_max |
|---|---|---|---|---|---|
| harder_holdout | holdout_bin_2 | heldout_47_51 | 1.2pct | 0.812315 | 0.007300 |
| harder_holdout | holdout_bin_2 | main_42_46 | 1.2pct | 0.812315 | 0.007300 |
| harder_holdout | holdout_bin_2 | heldout_47_51 | 1.5pct | 0.820475 | 0.008100 |
| harder_holdout | holdout_bin_2 | main_42_46 | 1.5pct | 0.820475 | 0.008100 |


## Interpretation Boundary

V2 is fixed as selected_source_rich_top32; this run does not re-search topK, does not add original100 fusion, and does not add margin-hardneg. Alarm-budget slack is a diagnostic indication for future locked validation, not a new official threshold.
