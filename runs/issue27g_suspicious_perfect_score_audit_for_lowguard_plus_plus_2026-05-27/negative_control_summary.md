# Negative Control Summary

Suspicious high-detection controls: `0`.
Caution controls that stayed near-perfect under random feature subset: `2`.

The decisive negative controls are label permutation and OOD-benign-as-positive-support. They should collapse if the result depends on real attack support. Random feature subset is weaker: remaining strong can mean signal is spread across many traffic features rather than leakage.

| control_name | attack_detection_mean | final_ood_alarm_max | suspicious_or_caution |
|---|---|---|---|
| label_permutation_same_positive_count | 0.003521 | 0.005500 | normal_collapse |
| ood_benign_as_positive_support | 0.002884 | 0.006900 | normal_collapse |
| positive_control_real_support | 1.000000 | 0.000100 | reference |
| random_50_feature_subset | 0.771714 | 0.005900 | caution_still_perfect;weakened_or_nonperfect |
| threshold_recompute_idcalib_oodval_only | 1.000000 | 0.000100 | pass |
