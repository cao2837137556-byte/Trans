# Issue15 Review-Budget Constrained Arbitration Summary

## 1. Outcome

Issue15 successfully read issue14b row-level scores and computed review-budget constrained arbitration metrics. No model was trained, no threshold was changed, and no manuscript file was modified.

Main analysis uses dA as the base detector; Transformer is reported as secondary in the CSV tables.

## 2. Review Queue Scale

For dA base detector:

- Main seeds 42-46 review-all queue size mean: 96.20 rows.
- Held-out seeds 47-51 review-all queue size mean: 108.00 rows.
- Main review-all OOD review rate: 0.009460.
- Held-out review-all OOD review rate: 0.010760.

## 3. Review Composition

Mean base-only/GDA-low queue composition:

- Main seeds attack fraction: 0.017316.
- Held-out seeds attack fraction: 0.003670.

This should be interpreted as a label-mixture diagnostic, not deployment precision.

## 4. Budget Results

| seed_group | review_policy | review_budget_used_mean | attack_high_detection_mean | attack_review_rate_mean | attack_total_captured_mean | OOD_high_alarm_mean | OOD_review_rate_mean | OOD_total_burden_mean | review_attack_fraction_mean | feasible_high_alarm_rate | feasible_total_burden_2pct_rate |
|---|---|---|---|---|---|---|---|---|---|---|---|
| heldout_support_47_51 | review_all | 108.000000 | 0.992291 | 0.000291 | 0.992582 | 0.004420 | 0.010760 | 0.015180 | 0.003670 | 1.000000 | 1.000000 |
| heldout_support_47_51 | review_off | 0.000000 | 0.992291 | 0.000000 | 0.992291 | 0.004420 | 0.000000 | 0.004420 | nan | 1.000000 | 1.000000 |
| heldout_support_47_51 | review_top_0.25pct | 25.000000 | 0.992291 | 0.000000 | 0.992291 | 0.004420 | 0.002500 | 0.006920 | 0.000000 | 1.000000 | 1.000000 |
| heldout_support_47_51 | review_top_0.5pct | 50.000000 | 0.992291 | 0.000145 | 0.992436 | 0.004420 | 0.004980 | 0.009400 | 0.004000 | 1.000000 | 1.000000 |
| heldout_support_47_51 | review_top_1pct | 100.000000 | 0.992291 | 0.000291 | 0.992582 | 0.004420 | 0.009960 | 0.014380 | 0.004000 | 1.000000 | 1.000000 |
| heldout_support_47_51 | review_top_2pct | 108.000000 | 0.992291 | 0.000291 | 0.992582 | 0.004420 | 0.010760 | 0.015180 | 0.003670 | 1.000000 | 1.000000 |
| main_paired_42_46 | review_all | 96.200000 | 0.938182 | 0.001164 | 0.939345 | 0.004300 | 0.009460 | 0.013760 | 0.017316 | 1.000000 | 1.000000 |
| main_paired_42_46 | review_off | 0.000000 | 0.938182 | 0.000000 | 0.938182 | 0.004300 | 0.000000 | 0.004300 | nan | 1.000000 | 1.000000 |
| main_paired_42_46 | review_top_0.25pct | 25.000000 | 0.938182 | 0.000000 | 0.938182 | 0.004300 | 0.002500 | 0.006800 | 0.000000 | 1.000000 | 1.000000 |
| main_paired_42_46 | review_top_0.5pct | 50.000000 | 0.938182 | 0.001164 | 0.939345 | 0.004300 | 0.004840 | 0.009140 | 0.032000 | 1.000000 | 1.000000 |
| main_paired_42_46 | review_top_1pct | 93.000000 | 0.938182 | 0.001164 | 0.939345 | 0.004300 | 0.009140 | 0.013440 | 0.017612 | 1.000000 | 1.000000 |
| main_paired_42_46 | review_top_2pct | 96.200000 | 0.938182 | 0.001164 | 0.939345 | 0.004300 | 0.009460 | 0.013760 | 0.017316 | 1.000000 | 1.000000 |

## 5. Interpretation

GDA-minimal remains the high-priority alerting channel. Budgeted review can preserve base-only evidence with an explicit operational burden, but review samples are not confirmed attacks.

If the paper needs a conservative framing, use: GDA-only for primary low-OOD high-priority alerts, plus optional bounded review queue as a safety-net deployment mechanism.
