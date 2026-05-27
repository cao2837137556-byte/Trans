# Safer Feature Variants Diagnosis

Best safer variant: `original100_rank_normalize_top3`.
Safer variant strong vs LOW-GUARD-LR: `True`.

Important boundary: "safer" here means a pre-registered risk-reduction transform, not proof of separator independence. The strongest safer variant (`original100_rank_normalize_top3`) still retains top3 separator information, so it is promising but not enough for claim upgrade.

| feature_variant | feature_count | locked_detection_mean | locked_detection_min | locked_ood_alarm_max | feasible_rate | dominates_lowguard_lr_three_axis | risk_reduced_feature_transform | retains_top3_separator_information | separator_independent |
|---|---|---|---|---|---|---|---|---|---|
| original100_all | 100 | 1.000000 | 1.000000 | 0.000100 | 1.000000 | True | False | True | False |
| original100_rank_normalize_top3 | 100 | 1.000000 | 1.000000 | 0.000100 | 1.000000 | True | True | True | False |
| original100_remove_top1 | 99 | 0.999648 | 0.985915 | 0.000000 | 1.000000 | True | False | True | False |
| original100_clip_top3_by_train_quantile | 100 | 0.998181 | 0.927230 | 0.005000 | 1.000000 | False | True | True | False |
| original100_group_aggregate_HH_features | 72 | 0.992488 | 0.838028 | 0.009400 | 1.000000 | False | True | True | False |
| original100_remove_top2 | 98 | 0.980914 | 0.847418 | 0.010500 | 0.950000 | False | False | True | False |
| original100_drop_lambda_0.01_HH_features | 93 | 0.979387 | 0.847418 | 0.009600 | 1.000000 | False | True | True | False |
| original100_remove_top3 | 97 | 0.671552 | 0.004695 | 0.006500 | 1.000000 | False | True | False | True |
| original100_drop_all_HH_radius_magnitude_top_family | 90 | 0.649367 | 0.002347 | 0.005400 | 1.000000 | False | True | False | True |


Interpretation: this stage does not select a replacement method. It identifies whether any pre-registered safer feature transform is promising enough for issue27j formal validation.
