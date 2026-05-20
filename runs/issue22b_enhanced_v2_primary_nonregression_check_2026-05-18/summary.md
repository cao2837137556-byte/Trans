# Issue22b Enhanced V2 Primary Non-Regression Summary

## Outcome

- Preflight passed: yes.
- Reused issue22 outputs: yes.
- New model training: no.
- Routing/proxy/promotion: no.
- V2_top64 primary detection: `0.947636`.
- V2_top64 primary OOD max: `0.003700`.
- V1 primary detection: `0.929455`.
- V1 primary OOD max: `0.003600`.
- V2_top32 primary detection: `0.924364`.
- V2_top32 primary OOD max: `0.015600`.
- V2_top64 - V1 detection delta: `0.018182`.
- V2_top64 - V2_top32 OOD delta: `-0.011900`.
- Global candidate status: `unified_candidate`.
- Recommended next action: `issue23_locked_validation_for_enhanced_v2_top64_2026-05-18`.

## Primary Low-OOD Core Table

| candidate | method | seed_group | roc_auc_mean | pr_auc_mean | attack_high_detection_mean | attack_high_detection_std | attack_high_detection_min | attack_high_detection_max | final_ood_high_alarm_mean | final_ood_high_alarm_max | feasible_rate | threshold_mean | feature_dim | support_size | train_time_mean | inference_time_mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| V1 | M0_V1_original100_kcenter32_fixed_guard | heldout_47_51 | 0.992537 | 0.969508 | 0.929455 | 0.000000 | 0.929455 | 0.929455 | 0.003600 | 0.003600 | 1.000000 | -2.646479 | 100 | 32 | 1.061906 | 0.019017 |
| V1 | M0_V1_original100_kcenter32_fixed_guard | main_42_46 | 0.992537 | 0.969508 | 0.929455 | 0.000000 | 0.929455 | 0.929455 | 0.003600 | 0.003600 | 1.000000 | -2.646479 | 100 | 32 | 1.028669 | 0.018374 |
| V2_top32 | M1_V2_source_rich_top32_kcenter32_fixed_guard | heldout_47_51 | 0.954677 | 0.948219 | 0.924364 | 0.000000 | 0.924364 | 0.924364 | 0.015600 | 0.015600 | 0.000000 | -3.426404 | 32 | 32 | 0.156994 | 0.006352 |
| V2_top32 | M1_V2_source_rich_top32_kcenter32_fixed_guard | main_42_46 | 0.954677 | 0.948219 | 0.924364 | 0.000000 | 0.924364 | 0.924364 | 0.015600 | 0.015600 | 0.000000 | -3.426404 | 32 | 32 | 0.169183 | 0.007539 |
| V2_top64 | M8_source_rich_top64_kcenter32_fixed_guard | heldout_47_51 | 0.982582 | 0.970602 | 0.947636 | 0.000000 | 0.947636 | 0.947636 | 0.003700 | 0.003700 | 1.000000 | -4.416415 | 64 | 32 | 0.414147 | 0.013146 |
| V2_top64 | M8_source_rich_top64_kcenter32_fixed_guard | main_42_46 | 0.982582 | 0.970602 | 0.947636 | 0.000000 | 0.947636 | 0.947636 | 0.003700 | 0.003700 | 1.000000 | -4.416415 | 64 | 32 | 0.400953 | 0.012561 |


## Interpretation

V2_top64 fixes the V2_top32 primary OOD-over-budget failure and is non-regressive on primary detection under the reused issue22 protocol. This makes V2_top64 a candidate for locked validation, not a final method.
