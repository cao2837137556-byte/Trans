# Issue22 V2 Hard-Shift Enhancement Pilot Summary

## Outcome

- Preflight passed: yes.
- Routing/promotion attempted: no.
- V1/V2 historical definitions modified: no.
- Final eval used for topK/support/target selection: no.
- Strong enhancement threshold 0.85 reached: `True`.
- Very strong threshold 0.90 reached: `True`.
- Best holdout_bin_2 official-1% method: `M8_source_rich_top64_kcenter32_fixed_guard`.
- Best holdout_bin_2 detection mean: `0.974036`.
- Best holdout_bin_2 OOD alarm max: `0.005700`.
- Best-method chrono_late detection mean: `0.950088`.
- Best-method chrono_late OOD alarm max: `0.008900`.
- Best-method primary_lowood OOD alarm max: `0.003700`.

## Holdout Bin 2 Official 1% Ranking

| method | method_group | attack_high_detection_mean | attack_high_detection_min | attack_high_detection_max | final_ood_high_alarm_max | feasible_rate | feature_dim | support_size |
|---|---|---|---|---|---|---|---|---|
| M8_source_rich_top64_kcenter32_fixed_guard | feature_count | 0.974036 | 0.974036 | 0.974036 | 0.005700 | 1.000000 | 64 | 32 |
| M4_source_rich_top32_kcenter128_fixed_guard | support_budget | 0.858309 | 0.858309 | 0.858309 | 0.001700 | 1.000000 | 32 | 128 |
| M7_source_rich_top48_kcenter32_fixed_guard | feature_count | 0.854599 | 0.854599 | 0.854599 | 0.004300 | 1.000000 | 48 | 32 |
| M1_V2_source_rich_top32_kcenter32_fixed_guard | v2_baseline | 0.809347 | 0.809347 | 0.809347 | 0.006800 | 1.000000 | 32 | 32 |
| M9_source_rich_top32_kcenter32_hardneg_w4 | low_fpr_adapter_sanity | 0.806380 | 0.806380 | 0.806380 | 0.005400 | 1.000000 | 32 | 32 |
| M3_source_rich_top32_kcenter64_fixed_guard | support_budget | 0.766320 | 0.766320 | 0.766320 | 0.000400 | 1.000000 | 32 | 64 |
| M5_source_rich_top16_kcenter32_fixed_guard | feature_count | 0.617211 | 0.617211 | 0.617211 | 0.003100 | 1.000000 | 16 | 32 |
| M0_V1_original100_kcenter32_fixed_guard | baseline | 0.326409 | 0.326409 | 0.326409 | 0.001100 | 1.000000 | 100 | 32 |
| M4b_source_rich_top32_random64_fixed_guard | support_budget_random_baseline | 0.846662 | 0.678042 | 0.968101 | 0.010400 | 0.900000 | 32 | 64 |


## Interpretation

This is a pilot, not locked validation. The result should be used to decide whether an enhanced V2 candidate deserves locked validation. If the best method only improves by relaxing diagnostic targets or worsens primary_lowood safety, it cannot be promoted as a final method.
