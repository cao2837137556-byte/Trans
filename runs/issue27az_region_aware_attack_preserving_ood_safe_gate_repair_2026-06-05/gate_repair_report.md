# Region-Aware OOD-Safe Gate Repair Report

primary_verdict = `needs_disjoint_ood_stress_pool_final_tail_uncovered`

This is not a formal benchmark. It tests whether issue27ay region-aware heads can be guarded without killing attack recovery.

## Dev-Selected Replay Summary

- selected_active_label_budget: `64`
- selected_gate_name: `no_gate`
- selected_radius_quantile: `0.95`
- selected_margin: `0.0`
- triple_attack_hard_min: `0.96875`
- triple_attack_score_or_review_min: `0.96875`
- medium_attack_hard_min: `0.976`
- dev_heavy_hard_min: `0.9985`
- final_ood_hard_max: `0.39866666666666667`
- final_ood_review_max: `0.0`
- ood_val_hard_max: `0.0`
- ood_val_review_max: `0.0`

## Interpretation

- Hard alarm, review, and suppress rates are separated; review is not counted as detection.
- Gate selection uses only ID/OOD/support validation roles.
- Final OOD is report-only and can only diagnose whether dev OOD covered the final tail.
