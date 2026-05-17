# Issue19 LOW-GUARD+ Representation and Margin Repair Pilot Summary

## Outcome

Verdict: `strong_repair_candidate`.

Best holdout_bin_2 mean detection across reported seed groups/methods: `0.809347`.

Reached >=0.70: `True`. Reached >=0.80: `True`. Reached >=0.90: `False`.

OOD alarm at the top holdout_bin_2 row max: `0.006800`.

## Top holdout_bin_2 rows

| holdout | method | seed_group | attack_high_detection_mean | attack_high_detection_min | ood_high_alarm_mean | ood_high_alarm_max | feasible_rate |
|---|---|---|---|---|---|---|---|
| holdout_bin_2 | selected_source_rich_top32_fixed_guard_lr | main_42_46 | 0.809347 | 0.809347 | 0.006800 | 0.006800 | 1.000000 |
| holdout_bin_2 | selected_source_rich_top32_fixed_guard_lr | heldout_47_51 | 0.809347 | 0.809347 | 0.006800 | 0.006800 | 1.000000 |
| holdout_bin_2 | selected_source_rich_top16_fixed_guard_lr | heldout_47_51 | 0.617211 | 0.617211 | 0.003100 | 0.003100 | 1.000000 |
| holdout_bin_2 | selected_source_rich_top16_fixed_guard_lr | main_42_46 | 0.617211 | 0.617211 | 0.003100 | 0.003100 | 1.000000 |
| holdout_bin_2 | original100_plus_selected_source_rich_top32_margin_hardneg_w2 | heldout_47_51 | 0.403561 | 0.403561 | 0.001500 | 0.001500 | 1.000000 |
| holdout_bin_2 | original100_plus_selected_source_rich_top32_margin_hardneg_w8 | heldout_47_51 | 0.403561 | 0.403561 | 0.000700 | 0.000700 | 1.000000 |
| holdout_bin_2 | original100_plus_selected_source_rich_top32_margin_hardneg_w2 | main_42_46 | 0.403561 | 0.403561 | 0.001500 | 0.001500 | 1.000000 |
| holdout_bin_2 | original100_plus_selected_source_rich_top32_margin_hardneg_w8 | main_42_46 | 0.403561 | 0.403561 | 0.000700 | 0.000700 | 1.000000 |
| holdout_bin_2 | original100_plus_selected_source_rich_top32_margin_hardneg_w4 | main_42_46 | 0.403561 | 0.403561 | 0.001100 | 0.001100 | 1.000000 |
| holdout_bin_2 | original100_plus_selected_source_rich_top32_margin_hardneg_w4 | heldout_47_51 | 0.403561 | 0.403561 | 0.001100 | 0.001100 | 1.000000 |


## Best by holdout / seed group

| holdout | seed_group | method | attack_high_detection_mean | ood_high_alarm_mean | ood_high_alarm_max | feasible_rate |
|---|---|---|---|---|---|---|
| holdout_bin_2 | heldout_47_51 | selected_source_rich_top32_fixed_guard_lr | 0.809347 | 0.006800 | 0.006800 | 1.000000 |
| holdout_bin_2 | main_42_46 | selected_source_rich_top32_fixed_guard_lr | 0.809347 | 0.006800 | 0.006800 | 1.000000 |
| chrono_late_train_early_eval | heldout_47_51 | baseline_original100_random32_fixed_guard | 0.733800 | 0.001500 | 0.002400 | 1.000000 |
| chrono_late_train_early_eval | main_42_46 | selected_source_rich_top32_fixed_guard_lr | 0.731465 | 0.009700 | 0.009700 | 1.000000 |


## Interpretation

This is a controlled pilot, not locked validation. A positive pilot still requires a locked second validation before the paper can change the final method. A negative pilot means the minimal-linear route is insufficient for holdout_bin_2 and should not be dressed up as solved.

## Component Diagnosis

- Main positive component: selected source_rich representation. `selected_source_rich_top32_fixed_guard_lr` is the only reported method crossing the 0.80 pilot threshold on holdout_bin_2 while keeping OOD high alarm below 1%.
- Margin / hard-negative component: not the main gain source in this pilot. The hard-negative margin variants reduce OOD alarm but do not approach the selected-source_rich-only detection level.
- Fusion caveat: `original100 + selected_source_rich` is weaker than selected_source_rich-only in this pilot, so the current positive signal should be treated as representation selection evidence, not as proof that simple feature concatenation is the final LOW-GUARD+ form.
- Seed caveat: k-center support selection is deterministic in this run, so main and held-out seed groups coincide for kcenter-derived methods. This is acceptable for a repair pilot but requires locked validation with a second support/split design before paper-level claims.

## Safety

- Manuscript modified: False.
- Historical experimental numbers modified: False.
- dA / Transformer trained: False.
- MLP / prototype / full neural GDA run: False.
- OOD weight changed: False.
- Final eval used for feature/margin/threshold selection: False.
