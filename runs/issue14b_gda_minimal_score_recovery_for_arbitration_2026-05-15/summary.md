# Issue14b GDA Score Recovery and Arbitration Summary

## 1. Purpose

This run fills the issue14 blocker by recovering row-level scores for the fixed issue11 GDA-minimal configuration: `original100_fixed_guard_lr`, 32-shot, OOD benign weight 2, seeds 42-51.

It does not train a new detector, does not search OOD weight, does not change support selection, and does not use final OOD eval or attack eval for threshold selection.

## 2. Validation

Recovered GDA seed-level metrics were compared against issue11 `method_comparison_seed_level.csv`.

- Validation status: `passed`.
- All recovered seed rows matched issue11: `True`.

See `gda_recovery_validation.csv`.

## 3. Base Scores

Both dA and Transformer current low-OOD score caches were available and used as base detectors. Base thresholds were recomputed from ID calibration + OOD validation only.

## 4. Strategy Metrics

The following table reports mean values across seeds by seed group. `needs_review` is counted as review burden, not high-priority detection.

| base_detector | strategy | seed_group | attack_high_detection_mean | attack_review_rate_mean | attack_total_captured_mean | OOD_high_alarm_mean | OOD_review_rate_mean | OOD_total_burden_mean | feasible_high_alarm_rate | feasible_total_burden_rate |
|---|---|---|---|---|---|---|---|---|---|---|
| Transformer | AND_policy | heldout_support_47_51 | 0.002618 | 0.000000 | 0.002618 | 0.000040 | 0.000000 | 0.000040 | 1.000000 | 1.000000 |
| Transformer | AND_policy | main_paired_42_46 | 0.001745 | 0.000000 | 0.001745 | 0.001340 | 0.000000 | 0.001340 | 1.000000 | 1.000000 |
| Transformer | OR_policy | heldout_support_47_51 | 0.992582 | 0.000000 | 0.992582 | 0.015280 | 0.000000 | 0.015280 | 0.000000 | 1.000000 |
| Transformer | OR_policy | main_paired_42_46 | 0.939345 | 0.000000 | 0.939345 | 0.013860 | 0.000000 | 0.013860 | 0.000000 | 1.000000 |
| Transformer | base_only | heldout_support_47_51 | 0.002909 | 0.000000 | 0.002909 | 0.010900 | 0.000000 | 0.010900 | 0.000000 | 1.000000 |
| Transformer | base_only | main_paired_42_46 | 0.002909 | 0.000000 | 0.002909 | 0.010900 | 0.000000 | 0.010900 | 0.000000 | 1.000000 |
| Transformer | gda_only | heldout_support_47_51 | 0.992291 | 0.000000 | 0.992291 | 0.004420 | 0.000000 | 0.004420 | 1.000000 | 1.000000 |
| Transformer | gda_only | main_paired_42_46 | 0.938182 | 0.000000 | 0.938182 | 0.004300 | 0.000000 | 0.004300 | 1.000000 | 1.000000 |
| Transformer | mode_gated_arbitration | heldout_support_47_51 | 0.992291 | 0.000291 | 0.992582 | 0.004420 | 0.010860 | 0.015280 | 1.000000 | 1.000000 |
| Transformer | mode_gated_arbitration | main_paired_42_46 | 0.938182 | 0.001164 | 0.939345 | 0.004300 | 0.009560 | 0.013860 | 1.000000 | 1.000000 |
| dA | AND_policy | heldout_support_47_51 | 0.002618 | 0.000000 | 0.002618 | 0.000040 | 0.000000 | 0.000040 | 1.000000 | 1.000000 |
| dA | AND_policy | main_paired_42_46 | 0.001745 | 0.000000 | 0.001745 | 0.001340 | 0.000000 | 0.001340 | 1.000000 | 1.000000 |
| dA | OR_policy | heldout_support_47_51 | 0.992582 | 0.000000 | 0.992582 | 0.015180 | 0.000000 | 0.015180 | 0.000000 | 1.000000 |
| dA | OR_policy | main_paired_42_46 | 0.939345 | 0.000000 | 0.939345 | 0.013760 | 0.000000 | 0.013760 | 0.000000 | 1.000000 |
| dA | base_only | heldout_support_47_51 | 0.002909 | 0.000000 | 0.002909 | 0.010800 | 0.000000 | 0.010800 | 0.000000 | 1.000000 |
| dA | base_only | main_paired_42_46 | 0.002909 | 0.000000 | 0.002909 | 0.010800 | 0.000000 | 0.010800 | 0.000000 | 1.000000 |
| dA | gda_only | heldout_support_47_51 | 0.992291 | 0.000000 | 0.992291 | 0.004420 | 0.000000 | 0.004420 | 1.000000 | 1.000000 |
| dA | gda_only | main_paired_42_46 | 0.938182 | 0.000000 | 0.938182 | 0.004300 | 0.000000 | 0.004300 | 1.000000 | 1.000000 |
| dA | mode_gated_arbitration | heldout_support_47_51 | 0.992291 | 0.000291 | 0.992582 | 0.004420 | 0.010760 | 0.015180 | 1.000000 | 1.000000 |
| dA | mode_gated_arbitration | main_paired_42_46 | 0.938182 | 0.001164 | 0.939345 | 0.004300 | 0.009460 | 0.013760 | 1.000000 | 1.000000 |

## 5. Interpretation

Mode-gated arbitration uses GDA-high rows as high-priority alerts and routes base-high/GDA-low rows to review. Therefore, its high-priority detection is numerically aligned with GDA-only, while its additional value is preserving base-only evidence as an explicit review queue.

## 6. Boundaries

- This is a deployment-policy experiment, not full GDA.
- Review rows are not confirmed attacks.
- `high_alert_attack_fraction` is only a label-mixture proxy, not deployment precision.
- No manuscript files were modified.
