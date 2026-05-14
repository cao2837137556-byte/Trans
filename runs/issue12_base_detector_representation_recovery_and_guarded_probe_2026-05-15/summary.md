# Issue12 Transformer Hidden Recovery and Fixed-Guard Probe Summary

## 1. Scope
This run recovers Transformer outputLayer mean-pooled hidden representations from an existing checkpoint and, only after score-consistency gating, runs a minimal fixed-guard LR representation probe. It does not retrain Transformer or dA, does not search guard weights, and does not modify the manuscript.

## 2. Phase A Gate
- Hidden shape: ID `(50000, 16)`, OOD `(20000, 16)`, attack `(10000, 16)`.
- Score consistency pass: `True`.
- Hidden shape gate: `True`.

## 3. Main 32-shot Results
| method | representation | guard_type | attack_detection_mean | attack_detection_min | ood_alarm_mean | ood_alarm_max | feasible_rate |
|---|---|---|---|---|---|---|---|
| original100_plus_transformer_hidden_fixed_guard_lr | original100_plus_transformer_hidden | fixed_ood_weight_2 | 0.944727 | 0.925818 | 0.003480 | 0.005800 | 1.000000 |
| transformer_hidden_fixed_guard_lr | transformer_hidden | fixed_ood_weight_2 | 0.491345 | 0.432727 | 0.014740 | 0.016800 | 0.200000 |
| transformer_hidden_plain_lr | transformer_hidden | plain | 0.489745 | 0.424727 | 0.014720 | 0.016500 | 0.200000 |


## 4. Held-out 32-shot Results
| method | representation | guard_type | attack_detection_mean | attack_detection_min | ood_alarm_mean | ood_alarm_max | feasible_rate |
|---|---|---|---|---|---|---|---|
| original100_plus_transformer_hidden_fixed_guard_lr | original100_plus_transformer_hidden | fixed_ood_weight_2 | 0.991709 | 0.984727 | 0.003980 | 0.009000 | 1.000000 |
| transformer_hidden_fixed_guard_lr | transformer_hidden | fixed_ood_weight_2 | 0.479418 | 0.432727 | 0.013940 | 0.016900 | 0.200000 |
| transformer_hidden_plain_lr | transformer_hidden | plain | 0.480145 | 0.433455 | 0.014280 | 0.016500 | 0.200000 |


## 5. Hidden vs Scalar Score Reference
| seed_group | hidden_method | scalar_reference_method | positive_budget | hidden_detection_mean | scalar_detection_mean | detection_delta_hidden_minus_scalar | hidden_ood_alarm_mean | scalar_ood_alarm_mean | ood_alarm_delta_hidden_minus_scalar | hidden_feasible_rate | scalar_feasible_rate |
|---|---|---|---|---|---|---|---|---|---|---|---|
| main_paired_42_46 | original100_plus_transformer_hidden_fixed_guard_lr | original100_plus_transformer_score_fewshot_lr | 16 | 0.972655 | 0.967564 | 0.005091 | 0.002320 | 0.004480 | -0.002160 | 1.000000 | 1.000000 |
| main_paired_42_46 | transformer_hidden_plain_lr | transformer_score_only_fewshot_lr | 16 | 0.490327 | 0.000000 | 0.490327 | 0.015100 | 0.000000 | 0.015100 | 0.000000 | 1.000000 |
| main_paired_42_46 | original100_plus_transformer_hidden_fixed_guard_lr | original100_plus_transformer_score_fewshot_lr | 32 | 0.944727 | 0.940655 | 0.004073 | 0.003480 | 0.006560 | -0.003080 | 1.000000 | 1.000000 |
| main_paired_42_46 | transformer_hidden_plain_lr | transformer_score_only_fewshot_lr | 32 | 0.489745 | 0.000000 | 0.489745 | 0.014720 | 0.000000 | 0.014720 | 0.200000 | 1.000000 |


## 6. Hidden vs Issue11 Baselines
| seed_group | positive_budget | method | baseline_method | method_detection_mean | baseline_detection_mean | detection_delta | method_ood_alarm_mean | baseline_ood_alarm_mean | ood_alarm_delta | method_ood_alarm_max | baseline_ood_alarm_max | method_feasible_rate | baseline_feasible_rate | feasible_delta |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| heldout_support_47_51 | 16 | original100_plus_transformer_hidden_fixed_guard_lr | original100_plain_lr | 0.981091 | 0.984291 | -0.003200 | 0.003280 | 0.003220 | 0.000060 | 0.008500 | 0.005300 | 1.000000 | 1.000000 | 0.000000 |
| heldout_support_47_51 | 16 | original100_plus_transformer_hidden_fixed_guard_lr | original100_fixed_guard_lr | 0.981091 | 0.984727 | -0.003636 | 0.003280 | 0.001840 | 0.001440 | 0.008500 | 0.003400 | 1.000000 | 1.000000 | 0.000000 |
| heldout_support_47_51 | 16 | original100_plus_transformer_hidden_fixed_guard_lr | original100_plus_source_rich_fixed_guard_lr | 0.981091 | 0.984000 | -0.002909 | 0.003280 | 0.006340 | -0.003060 | 0.008500 | 0.015700 | 1.000000 | 0.800000 | 0.200000 |
| heldout_support_47_51 | 16 | transformer_hidden_fixed_guard_lr | original100_plain_lr | 0.505164 | 0.984291 | -0.479127 | 0.016180 | 0.003220 | 0.012960 | 0.016500 | 0.005300 | 0.000000 | 1.000000 | -1.000000 |
| heldout_support_47_51 | 16 | transformer_hidden_fixed_guard_lr | original100_fixed_guard_lr | 0.505164 | 0.984727 | -0.479564 | 0.016180 | 0.001840 | 0.014340 | 0.016500 | 0.003400 | 0.000000 | 1.000000 | -1.000000 |
| heldout_support_47_51 | 16 | transformer_hidden_fixed_guard_lr | original100_plus_source_rich_fixed_guard_lr | 0.505164 | 0.984000 | -0.478836 | 0.016180 | 0.006340 | 0.009840 | 0.016500 | 0.015700 | 0.000000 | 0.800000 | -0.800000 |
| heldout_support_47_51 | 16 | transformer_hidden_plain_lr | original100_plain_lr | 0.502982 | 0.984291 | -0.481309 | 0.015920 | 0.003220 | 0.012700 | 0.016600 | 0.005300 | 0.000000 | 1.000000 | -1.000000 |
| heldout_support_47_51 | 16 | transformer_hidden_plain_lr | original100_fixed_guard_lr | 0.502982 | 0.984727 | -0.481745 | 0.015920 | 0.001840 | 0.014080 | 0.016600 | 0.003400 | 0.000000 | 1.000000 | -1.000000 |
| heldout_support_47_51 | 16 | transformer_hidden_plain_lr | original100_plus_source_rich_fixed_guard_lr | 0.502982 | 0.984000 | -0.481018 | 0.015920 | 0.006340 | 0.009580 | 0.016600 | 0.015700 | 0.000000 | 0.800000 | -0.800000 |
| heldout_support_47_51 | 32 | original100_plus_transformer_hidden_fixed_guard_lr | original100_plain_lr | 0.991709 | 0.993164 | -0.001455 | 0.003980 | 0.006560 | -0.002580 | 0.009000 | 0.012300 | 1.000000 | 0.800000 | 0.200000 |
| heldout_support_47_51 | 32 | original100_plus_transformer_hidden_fixed_guard_lr | original100_fixed_guard_lr | 0.991709 | 0.992291 | -0.000582 | 0.003980 | 0.004420 | -0.000440 | 0.009000 | 0.008300 | 1.000000 | 1.000000 | 0.000000 |
| heldout_support_47_51 | 32 | original100_plus_transformer_hidden_fixed_guard_lr | original100_plus_source_rich_fixed_guard_lr | 0.991709 | 0.985455 | 0.006255 | 0.003980 | 0.005480 | -0.001500 | 0.009000 | 0.008200 | 1.000000 | 1.000000 | 0.000000 |
| heldout_support_47_51 | 32 | transformer_hidden_fixed_guard_lr | original100_plain_lr | 0.479418 | 0.993164 | -0.513745 | 0.013940 | 0.006560 | 0.007380 | 0.016900 | 0.012300 | 0.200000 | 0.800000 | -0.600000 |
| heldout_support_47_51 | 32 | transformer_hidden_fixed_guard_lr | original100_fixed_guard_lr | 0.479418 | 0.992291 | -0.512873 | 0.013940 | 0.004420 | 0.009520 | 0.016900 | 0.008300 | 0.200000 | 1.000000 | -0.800000 |
| heldout_support_47_51 | 32 | transformer_hidden_fixed_guard_lr | original100_plus_source_rich_fixed_guard_lr | 0.479418 | 0.985455 | -0.506036 | 0.013940 | 0.005480 | 0.008460 | 0.016900 | 0.008200 | 0.200000 | 1.000000 | -0.800000 |
| heldout_support_47_51 | 32 | transformer_hidden_plain_lr | original100_plain_lr | 0.480145 | 0.993164 | -0.513018 | 0.014280 | 0.006560 | 0.007720 | 0.016500 | 0.012300 | 0.200000 | 0.800000 | -0.600000 |
| heldout_support_47_51 | 32 | transformer_hidden_plain_lr | original100_fixed_guard_lr | 0.480145 | 0.992291 | -0.512145 | 0.014280 | 0.004420 | 0.009860 | 0.016500 | 0.008300 | 0.200000 | 1.000000 | -0.800000 |
| heldout_support_47_51 | 32 | transformer_hidden_plain_lr | original100_plus_source_rich_fixed_guard_lr | 0.480145 | 0.985455 | -0.505309 | 0.014280 | 0.005480 | 0.008800 | 0.016500 | 0.008200 | 0.200000 | 1.000000 | -0.800000 |
| main_paired_42_46 | 16 | original100_plus_transformer_hidden_fixed_guard_lr | original100_plain_lr | 0.972655 | 0.967564 | 0.005091 | 0.002320 | 0.004440 | -0.002120 | 0.005700 | 0.009200 | 1.000000 | 1.000000 | 0.000000 |
| main_paired_42_46 | 16 | original100_plus_transformer_hidden_fixed_guard_lr | original100_fixed_guard_lr | 0.972655 | 0.964945 | 0.007709 | 0.002320 | 0.002760 | -0.000440 | 0.005700 | 0.005000 | 1.000000 | 1.000000 | 0.000000 |
| main_paired_42_46 | 16 | original100_plus_transformer_hidden_fixed_guard_lr | original100_plus_source_rich_fixed_guard_lr | 0.972655 | 0.967709 | 0.004945 | 0.002320 | 0.006320 | -0.004000 | 0.005700 | 0.009700 | 1.000000 | 1.000000 | 0.000000 |
| main_paired_42_46 | 16 | transformer_hidden_fixed_guard_lr | original100_plain_lr | 0.491491 | 0.967564 | -0.476073 | 0.015080 | 0.004440 | 0.010640 | 0.016700 | 0.009200 | 0.200000 | 1.000000 | -0.800000 |
| main_paired_42_46 | 16 | transformer_hidden_fixed_guard_lr | original100_fixed_guard_lr | 0.491491 | 0.964945 | -0.473455 | 0.015080 | 0.002760 | 0.012320 | 0.016700 | 0.005000 | 0.200000 | 1.000000 | -0.800000 |
| main_paired_42_46 | 16 | transformer_hidden_fixed_guard_lr | original100_plus_source_rich_fixed_guard_lr | 0.491491 | 0.967709 | -0.476218 | 0.015080 | 0.006320 | 0.008760 | 0.016700 | 0.009700 | 0.200000 | 1.000000 | -0.800000 |
| main_paired_42_46 | 16 | transformer_hidden_plain_lr | original100_plain_lr | 0.490327 | 0.967564 | -0.477236 | 0.015100 | 0.004440 | 0.010660 | 0.016700 | 0.009200 | 0.000000 | 1.000000 | -1.000000 |
| main_paired_42_46 | 16 | transformer_hidden_plain_lr | original100_fixed_guard_lr | 0.490327 | 0.964945 | -0.474618 | 0.015100 | 0.002760 | 0.012340 | 0.016700 | 0.005000 | 0.000000 | 1.000000 | -1.000000 |
| main_paired_42_46 | 16 | transformer_hidden_plain_lr | original100_plus_source_rich_fixed_guard_lr | 0.490327 | 0.967709 | -0.477382 | 0.015100 | 0.006320 | 0.008780 | 0.016700 | 0.009700 | 0.000000 | 1.000000 | -1.000000 |
| main_paired_42_46 | 32 | original100_plus_transformer_hidden_fixed_guard_lr | original100_plain_lr | 0.944727 | 0.940655 | 0.004073 | 0.003480 | 0.006520 | -0.003040 | 0.005800 | 0.009800 | 1.000000 | 1.000000 | 0.000000 |
| main_paired_42_46 | 32 | original100_plus_transformer_hidden_fixed_guard_lr | original100_fixed_guard_lr | 0.944727 | 0.938182 | 0.006545 | 0.003480 | 0.004300 | -0.000820 | 0.005800 | 0.005800 | 1.000000 | 1.000000 | 0.000000 |
| main_paired_42_46 | 32 | original100_plus_transformer_hidden_fixed_guard_lr | original100_plus_source_rich_fixed_guard_lr | 0.944727 | 0.970036 | -0.025309 | 0.003480 | 0.005480 | -0.002000 | 0.005800 | 0.007500 | 1.000000 | 1.000000 | 0.000000 |
| main_paired_42_46 | 32 | transformer_hidden_fixed_guard_lr | original100_plain_lr | 0.491345 | 0.940655 | -0.449309 | 0.014740 | 0.006520 | 0.008220 | 0.016800 | 0.009800 | 0.200000 | 1.000000 | -0.800000 |
| main_paired_42_46 | 32 | transformer_hidden_fixed_guard_lr | original100_fixed_guard_lr | 0.491345 | 0.938182 | -0.446836 | 0.014740 | 0.004300 | 0.010440 | 0.016800 | 0.005800 | 0.200000 | 1.000000 | -0.800000 |
| main_paired_42_46 | 32 | transformer_hidden_fixed_guard_lr | original100_plus_source_rich_fixed_guard_lr | 0.491345 | 0.970036 | -0.478691 | 0.014740 | 0.005480 | 0.009260 | 0.016800 | 0.007500 | 0.200000 | 1.000000 | -0.800000 |
| main_paired_42_46 | 32 | transformer_hidden_plain_lr | original100_plain_lr | 0.489745 | 0.940655 | -0.450909 | 0.014720 | 0.006520 | 0.008200 | 0.016500 | 0.009800 | 0.200000 | 1.000000 | -0.800000 |
| main_paired_42_46 | 32 | transformer_hidden_plain_lr | original100_fixed_guard_lr | 0.489745 | 0.938182 | -0.448436 | 0.014720 | 0.004300 | 0.010420 | 0.016500 | 0.005800 | 0.200000 | 1.000000 | -0.800000 |
| main_paired_42_46 | 32 | transformer_hidden_plain_lr | original100_plus_source_rich_fixed_guard_lr | 0.489745 | 0.970036 | -0.480291 | 0.014720 | 0.005480 | 0.009240 | 0.016500 | 0.007500 | 0.200000 | 1.000000 | -0.800000 |


## 7. Verdict
- Hidden positive by fixed criteria: `True`.
- Hidden strong gain over original100 fixed guard: `True`.
- Held-out hidden positive over original100 fixed guard: `False`.
- Held-out near original100 fixed guard: `True`.
- Recommendation: Transformer hidden fixed-guard probe is a cautious positive for representation-level integration, but held-out support seeds do not show clear superiority over original100 fixed guard. Consider a tightly scoped GDA ablation only with original100-fixed as the primary control.

## 8. Boundary
- This is not full GDA.
- This does not prove detector-agnostic adaptation.
- This does not establish dA latent usefulness.
- No manuscript edit, commit, or push was performed.
