# Non-Regression Report

Primary low-OOD non-regression criterion: V2 detection delta >= -0.01 and V2 final OOD alarm max <= 1%.

Result: False.

| dataset | holdout | seed_group | v1_detection_mean | v1_ood_alarm_max | v2_detection_mean | v2_ood_alarm_max | delta_detection_v2_minus_v1 |
|---|---|---|---|---|---|---|---|
| primary_lowood | primary_lowood | heldout_47_51 | 0.929455 | 0.003600 | 0.924364 | 0.015600 | -0.005091 |
| primary_lowood | primary_lowood | main_42_46 | 0.929455 | 0.003600 | 0.924364 | 0.015600 | -0.005091 |
