# Region-Aware Attack Bank Diagnostic Report

primary_verdict = `region_aware_attack_recovery_supported_ready_for_ood_gate`

This is a bounded attack-side diagnostic on the Gotham Kitsune115 medium asset.
It does not change the 115D frontend, split, final OOD, or sealed attack eval roles.

## Best Diagnostic Row

- best_config_name: `per_region_heads_or`
- best_active_label_budget: `128`
- best_triple_attack_min: `0.96875`
- best_support_val_min: `0.96875`
- best_active_heavy_val_min: `1.0`
- best_medium_attack_min: `0.9853333333333333`
- best_dev_heavy_min: `0.9995`
- best_medium_score_or_review_min: `0.9924444444444445`
- best_dev_heavy_score_or_review_min: `0.9995`
- best_final_ood_alarm_max: `0.39866666666666667`

## Interpretation

- `single_*` rows test whether region weighting alone can stop active-heavy labels from damaging medium attack detection.
- `per_region_heads_*` rows test whether separate region heads avoid negative transfer.
- `*_score_or_review_recall` counts hard score alarms plus low-score samples that are close to an attack region; it is a review-route diagnostic, not a hard detection metric.
- Final OOD is logged as a caveat only and is not optimized in this task.
