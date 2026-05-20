| adapter | config_id | model_type | attack_weight | ood_train_weight | tail_quantile | tail_weight | C | alpha |
|---|---|---|---|---|---|---|---|---|
| A0_lr_baseline | lr_fixed_guard | lr | 1.000000 | 2.000000 |  | 0.000000 | 1.000000 |  |
| A1_low_fpr_weighted_lr | lr_tail_q0.95_w4.0_a1.0 | lr | 1.000000 | 2.000000 | 0.950000 | 4.000000 | 1.000000 |  |
| A1_low_fpr_weighted_lr | lr_tail_q0.975_w4.0_a1.0 | lr | 1.000000 | 2.000000 | 0.975000 | 4.000000 | 1.000000 |  |
| A1_low_fpr_weighted_lr | lr_tail_q0.975_w8.0_a1.0 | lr | 1.000000 | 2.000000 | 0.975000 | 8.000000 | 1.000000 |  |
| A2_linear_svm_margin | sgd_hinge_alpha0.0001_a1.0 | linear_svm | 1.000000 | 2.000000 |  |  |  | 0.000100 |
| A2_linear_svm_margin | sgd_hinge_alpha1e-05_a1.0 | linear_svm | 1.000000 | 2.000000 |  |  |  | 0.000010 |
| A2_linear_svm_margin | sgd_hinge_alpha0.0001_a2.0 | linear_svm | 2.000000 | 2.000000 |  |  |  | 0.000100 |
