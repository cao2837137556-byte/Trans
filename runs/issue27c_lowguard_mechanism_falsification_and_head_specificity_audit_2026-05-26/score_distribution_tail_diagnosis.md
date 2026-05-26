# Score Distribution And Tail Diagnosis

P3 score-tail audit shows that LR has the cleanest low-alert tail under the frozen protocol. DevNet-like keeps attack margins high, but its final-OOD tail has too little safety margin and crosses 1% in at least one locked seed/bin. HistGB has unstable attack margins across bins. DeepSAD-like has weak attack separation under the center-distance proxy.

Worst P3 tail snapshot:

| head_id | max_ood_tail_rate | median_attack_margin | min_attack_minus_ood_q99 |
|---|---|---|---|
| HistGB_shallow | 0.013900 | 0.999532 | -0.817784 |
| DeepSAD_like_center | 0.013400 | -358.888966 | -723.974230 |
| DevNet_like_MLP | 0.010100 | 0.987400 | 0.892301 |
| LOW_GUARD_LR_reference | 0.004500 | 11.976977 | 10.335503 |


Score direction / objective mismatch is visible for DeepSAD-like raw and threshold-only variants, and in a small number of HistGB rows. It is not the dominant explanation for LR or DevNet-like. For the main non-LR near miss, the problem is tail calibration and low-alert safety margin.

Direction-risk rows:

| head_id | protocol_variant | score_direction_risk |
|---|---|---|
| DeepSAD_like_center | P0_raw_train_id_threshold | 34 |
| DeepSAD_like_center | P1_raw_train_oodval_threshold | 39 |
| HistGB_shallow | P0_raw_train_id_threshold | 6 |
| HistGB_shallow | P1_raw_train_oodval_threshold | 5 |
| HistGB_shallow | P2_guarded_train_id_threshold | 1 |
| HistGB_shallow | P3_full_lowguard | 1 |
