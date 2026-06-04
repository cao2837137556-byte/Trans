# Support Bank Detection Recovery Report

primary_verdict = `support_bank_overfits_heavy_underrepresents_medium`

This is an attack-side diagnostic on the medium Gotham Kitsune115 asset. It is not a formal benchmark and does not optimize final OOD.

Support bank policy retains the medium base support train split and appends confirmed active-heavy attack labels. It does not replace medium support with heavy support.

## Best Pre-Registered Diagnostic Row

- best_bank_name: `base128_retained_plus_active64_bank192`
- best_threshold_rule: `np_orderstat_id_ood_1pct`
- best_triple_attack_min: `0.6662222222222223`
- best_support_val_detection_min: `0.71875`
- best_medium_attack_detection_min: `0.6662222222222223`
- best_dev_heavy_detection_min: `0.979`
- best_medium_delta_vs_base: `-0.323111111111111`
- best_heavy_delta_vs_base: `0.7995`

## Interpretation

- If all three attack roles are above 0.95, the support-bank mechanism is strong enough to move to OOD gate repair.
- If heavy is high but medium is low, the bank is still causing heavy-biased negative transfer.
- If medium is high but heavy is low, active labels still miss heavy regions.
- Final OOD is logged only as a diagnostic caveat.
