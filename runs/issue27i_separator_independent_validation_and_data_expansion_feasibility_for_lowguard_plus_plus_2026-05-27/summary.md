# Issue27i Separator Independent Validation And Data Expansion Feasibility Summary

## Verdict

- primary_verdict: `lowguard_plus_plus_promising_needs_clean_independent_validation`
- issue27j_next_action: `issue27j_raw_provenance_recovery_and_clean_independent_split_construction`

## 1. Clean independent validation asset

Exists now: `False`.

Missing: raw timestamp, packet order, capture/session id, window start/end, row-level support/eval manifests, and clean unused split construction.

## 2. Separator stability outside locked bins

Separator stability on available non-locked consistency assets: `False`.

## 3. Frozen LOW-GUARD++ non-locked report

| asset_name | dataset | evidence_level | clean_independent | detection_mean | detection_min | ood_alarm_max | feasible_rate | pauc_mean | tpr_at_fpr_1pct_mean |
|---|---|---|---|---|---|---|---|---|---|
| chrono_late_train_early_eval | harder_holdout | consistency_only | False | 0.603211 | 0.603036 | 0.000000 | 1.000000 | 0.801511 | 0.603211 |
| holdout_bin_2 | harder_holdout | consistency_only | False | 1.000000 | 1.000000 | 0.002000 | 1.000000 | 0.996220 | 1.000000 |
| primary_lowood | primary_lowood | consistency_only | False | 1.000000 | 1.000000 | 0.005000 | 1.000000 | 0.998552 | 1.000000 |


Evidence level is consistency-only, not formal independent validation.

## 4. Safer feature variants

Safer variant strong vs LOW-GUARD-LR: `True`.
Best safer variant: `original100_rank_normalize_top3`.

| feature_variant | locked_detection_mean | locked_detection_min | locked_ood_alarm_max | dominates_lowguard_lr_three_axis | risk_reduced_feature_transform | retains_top3_separator_information | separator_independent |
|---|---|---|---|---|---|---|---|
| original100_all | 1.000000 | 1.000000 | 0.000100 | True | False | True | False |
| original100_rank_normalize_top3 | 1.000000 | 1.000000 | 0.000100 | True | True | True | False |
| original100_remove_top1 | 0.999648 | 0.985915 | 0.000000 | True | False | True | False |
| original100_clip_top3_by_train_quantile | 0.998181 | 0.927230 | 0.005000 | False | True | True | False |
| original100_group_aggregate_HH_features | 0.992488 | 0.838028 | 0.009400 | False | True | True | False |
| original100_remove_top2 | 0.980914 | 0.847418 | 0.010500 | False | False | True | False |
| original100_drop_lambda_0.01_HH_features | 0.979387 | 0.847418 | 0.009600 | False | True | True | False |
| original100_remove_top3 | 0.671552 | 0.004695 | 0.006500 | False | True | False | True |
| original100_drop_all_HH_radius_magnitude_top_family | 0.649367 | 0.002347 | 0.005400 | False | True | False | True |


Boundary: the best safer variant still retains transformed top3 separator information. This supports continuing LOW-GUARD++, but it does not establish separator-independent generalization.

## 5. Interpretation of top3 separator

The separator is more likely a real but currently over-sharp traffic-stat signal than an explicit label/split artifact. It is still not cleanly generalizable until raw provenance and independent validation are obtained.

## 6. Continue LOW-GUARD++?

Yes. Do not abandon or permanently demote it. But do not upgrade it to main-text performance instance yet.

## 7. Need raw provenance / second environment / temporal expansion?

Yes. The preferred next step is raw provenance and clean independent split construction; second environment remains valuable if compatible features can be reconstructed.

## 8. Slurm

Not needed for this feasibility run. May be needed for full raw feature reconstruction or large second-environment extraction.
