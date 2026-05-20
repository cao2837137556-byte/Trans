# Adapter Validation Selection Report

Each non-baseline adapter selects a config per setting/seed using only:

- 24 support-train samples for fitting;
- 8 support-validation samples for attack-side proxy;
- ID calibration and OOD validation for threshold and OOD-side proxy.

No final OOD eval or final attack eval is used for selection. The support-validation proxy is small and can overfit, so selected adapters are feasibility candidates only.

Selected config snapshot:

| dataset | holdout | seed | seed_group | adapter | config_id | model_type | support_train_size | support_validation_size | support_val_detection | support_val_margin_q25 | support_val_margin_median | ood_val_alarm_at_selection | id_calib_alarm_at_selection | validation_selection_score | uses_final_eval | selected |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| locked_harder_holdout | holdout_bin_5 | 42 | main_42_46 | A1_low_fpr_weighted_lr | lr_tail_q0.975_w8.0_a1.0 | lr | 24 | 8 | 1.000000 | 12.192892 | 23.003313 | 0.000000 | 0.009800 | 1012.192892 | False | True |
| locked_harder_holdout | holdout_bin_5 | 42 | main_42_46 | A2_linear_svm_margin | sgd_hinge_alpha1e-05_a1.0 | linear_svm | 24 | 8 | 0.875000 | 13591.216739 | 18576.686466 | 0.005000 | 0.010000 | 14466.211739 | False | True |
| locked_harder_holdout | holdout_bin_5 | 43 | main_42_46 | A1_low_fpr_weighted_lr | lr_tail_q0.975_w8.0_a1.0 | lr | 24 | 8 | 1.000000 | 8.936334 | 14.182010 | 0.000500 | 0.010000 | 1008.935834 | False | True |
| locked_harder_holdout | holdout_bin_5 | 43 | main_42_46 | A2_linear_svm_margin | sgd_hinge_alpha1e-05_a1.0 | linear_svm | 24 | 8 | 0.750000 | 578.951208 | 5884.883459 | 0.006500 | 0.010000 | 1328.944708 | False | True |
| locked_harder_holdout | holdout_bin_5 | 44 | main_42_46 | A1_low_fpr_weighted_lr | lr_tail_q0.975_w8.0_a1.0 | lr | 24 | 8 | 1.000000 | 12.863100 | 18.147918 | 0.000500 | 0.010000 | 1012.862600 | False | True |
| locked_harder_holdout | holdout_bin_5 | 44 | main_42_46 | A2_linear_svm_margin | sgd_hinge_alpha1e-05_a1.0 | linear_svm | 24 | 8 | 1.000000 | 9664.117410 | 16372.358621 | 0.007500 | 0.010000 | 10664.109910 | False | True |
| locked_harder_holdout | holdout_bin_5 | 45 | main_42_46 | A1_low_fpr_weighted_lr | lr_tail_q0.975_w8.0_a1.0 | lr | 24 | 8 | 1.000000 | 9.680992 | 11.055844 | 0.000500 | 0.010000 | 1009.680492 | False | True |
| locked_harder_holdout | holdout_bin_5 | 45 | main_42_46 | A2_linear_svm_margin | sgd_hinge_alpha0.0001_a2.0 | linear_svm | 24 | 8 | 0.875000 | 498.169720 | 711.570752 | 0.002000 | 0.009800 | 1373.167720 | False | True |
| locked_harder_holdout | holdout_bin_5 | 46 | main_42_46 | A1_low_fpr_weighted_lr | lr_tail_q0.975_w8.0_a1.0 | lr | 24 | 8 | 1.000000 | 10.792141 | 13.930352 | 0.000500 | 0.010000 | 1010.791641 | False | True |
| locked_harder_holdout | holdout_bin_5 | 46 | main_42_46 | A2_linear_svm_margin | sgd_hinge_alpha1e-05_a1.0 | linear_svm | 24 | 8 | 0.875000 | 2516.883133 | 9749.703201 | 0.010000 | 0.000000 | 3391.873133 | False | True |
| locked_harder_holdout | holdout_bin_5 | 47 | heldout_47_51 | A1_low_fpr_weighted_lr | lr_tail_q0.95_w4.0_a1.0 | lr | 24 | 8 | 1.000000 | 7.256142 | 14.706541 | 0.000500 | 0.010000 | 1007.255642 | False | True |
| locked_harder_holdout | holdout_bin_5 | 47 | heldout_47_51 | A2_linear_svm_margin | sgd_hinge_alpha1e-05_a1.0 | linear_svm | 24 | 8 | 1.000000 | 11525.918784 | 15092.272300 | 0.002000 | 0.009800 | 12525.916784 | False | True |
| locked_harder_holdout | holdout_bin_5 | 48 | heldout_47_51 | A1_low_fpr_weighted_lr | lr_tail_q0.975_w4.0_a1.0 | lr | 24 | 8 | 1.000000 | 7.512138 | 16.708516 | 0.001500 | 0.010000 | 1007.510638 | False | True |
| locked_harder_holdout | holdout_bin_5 | 48 | heldout_47_51 | A2_linear_svm_margin | sgd_hinge_alpha0.0001_a2.0 | linear_svm | 24 | 8 | 0.625000 | -159.916657 | 1908.847716 | 0.001500 | 0.010000 | 465.081843 | False | True |
| locked_harder_holdout | holdout_bin_5 | 49 | heldout_47_51 | A1_low_fpr_weighted_lr | lr_tail_q0.975_w8.0_a1.0 | lr | 24 | 8 | 1.000000 | 8.869575 | 11.658969 | 0.000500 | 0.010000 | 1008.869075 | False | True |
| locked_harder_holdout | holdout_bin_5 | 49 | heldout_47_51 | A2_linear_svm_margin | sgd_hinge_alpha0.0001_a2.0 | linear_svm | 24 | 8 | 1.000000 | 1431.033632 | 2027.043276 | 0.006000 | 0.010000 | 2431.027632 | False | True |
| locked_harder_holdout | holdout_bin_5 | 50 | heldout_47_51 | A1_low_fpr_weighted_lr | lr_tail_q0.95_w4.0_a1.0 | lr | 24 | 8 | 1.000000 | 6.128698 | 12.616193 | 0.001000 | 0.009800 | 1006.127698 | False | True |
| locked_harder_holdout | holdout_bin_5 | 50 | heldout_47_51 | A2_linear_svm_margin | sgd_hinge_alpha0.0001_a1.0 | linear_svm | 24 | 8 | 0.750000 | -82.432787 | 1314.078169 | 0.010000 | 0.006200 | 667.557213 | False | True |
| locked_harder_holdout | holdout_bin_5 | 51 | heldout_47_51 | A1_low_fpr_weighted_lr | lr_tail_q0.975_w8.0_a1.0 | lr | 24 | 8 | 1.000000 | 8.651153 | 14.159572 | 0.000500 | 0.010000 | 1008.650653 | False | True |
| locked_harder_holdout | holdout_bin_5 | 51 | heldout_47_51 | A2_linear_svm_margin | sgd_hinge_alpha1e-05_a1.0 | linear_svm | 24 | 8 | 0.875000 | 887.343266 | 9282.094242 | 0.001000 | 0.009800 | 1762.342266 | False | True |
| locked_harder_holdout | holdout_bin_6 | 42 | main_42_46 | A1_low_fpr_weighted_lr | lr_tail_q0.95_w4.0_a1.0 | lr | 24 | 8 | 1.000000 | 12.142137 | 23.358761 | 0.000000 | 0.009800 | 1012.142137 | False | True |
| locked_harder_holdout | holdout_bin_6 | 42 | main_42_46 | A2_linear_svm_margin | sgd_hinge_alpha1e-05_a1.0 | linear_svm | 24 | 8 | 0.875000 | 13323.654640 | 18429.435157 | 0.010000 | 0.000200 | 14198.644640 | False | True |
| locked_harder_holdout | holdout_bin_6 | 43 | main_42_46 | A1_low_fpr_weighted_lr | lr_tail_q0.975_w8.0_a1.0 | lr | 24 | 8 | 1.000000 | 8.735676 | 14.312222 | 0.000500 | 0.010000 | 1008.735176 | False | True |
| locked_harder_holdout | holdout_bin_6 | 43 | main_42_46 | A2_linear_svm_margin | sgd_hinge_alpha0.0001_a2.0 | linear_svm | 24 | 8 | 0.875000 | 420.336582 | 1919.137394 | 0.009500 | 0.007800 | 1295.327082 | False | True |
| locked_harder_holdout | holdout_bin_6 | 44 | main_42_46 | A1_low_fpr_weighted_lr | lr_tail_q0.975_w8.0_a1.0 | lr | 24 | 8 | 1.000000 | 12.832336 | 18.406593 | 0.000500 | 0.010000 | 1012.831836 | False | True |
| locked_harder_holdout | holdout_bin_6 | 44 | main_42_46 | A2_linear_svm_margin | sgd_hinge_alpha1e-05_a1.0 | linear_svm | 24 | 8 | 1.000000 | 9328.768481 | 16194.240161 | 0.007500 | 0.010000 | 10328.760981 | False | True |
| locked_harder_holdout | holdout_bin_6 | 45 | main_42_46 | A1_low_fpr_weighted_lr | lr_tail_q0.975_w8.0_a1.0 | lr | 24 | 8 | 1.000000 | 9.638827 | 11.117623 | 0.000500 | 0.010000 | 1009.638327 | False | True |
| locked_harder_holdout | holdout_bin_6 | 45 | main_42_46 | A2_linear_svm_margin | sgd_hinge_alpha0.0001_a2.0 | linear_svm | 24 | 8 | 0.875000 | 461.268108 | 665.456890 | 0.001500 | 0.010000 | 1336.266608 | False | True |
| locked_harder_holdout | holdout_bin_6 | 46 | main_42_46 | A1_low_fpr_weighted_lr | lr_tail_q0.975_w8.0_a1.0 | lr | 24 | 8 | 1.000000 | 10.678187 | 13.839640 | 0.000500 | 0.010000 | 1010.677687 | False | True |
| locked_harder_holdout | holdout_bin_6 | 46 | main_42_46 | A2_linear_svm_margin | sgd_hinge_alpha1e-05_a1.0 | linear_svm | 24 | 8 | 0.875000 | 14759.496027 | 20001.859308 | 0.009500 | 0.010000 | 15634.486527 | False | True |
| locked_harder_holdout | holdout_bin_6 | 47 | heldout_47_51 | A1_low_fpr_weighted_lr | lr_tail_q0.95_w4.0_a1.0 | lr | 24 | 8 | 1.000000 | 7.208773 | 14.669177 | 0.000500 | 0.010000 | 1007.208273 | False | True |
| locked_harder_holdout | holdout_bin_6 | 47 | heldout_47_51 | A2_linear_svm_margin | sgd_hinge_alpha1e-05_a1.0 | linear_svm | 24 | 8 | 1.000000 | 11541.911289 | 14998.417637 | 0.002000 | 0.009800 | 12541.909289 | False | True |
| locked_harder_holdout | holdout_bin_6 | 48 | heldout_47_51 | A1_low_fpr_weighted_lr | lr_tail_q0.975_w8.0_a1.0 | lr | 24 | 8 | 1.000000 | 7.368680 | 16.708732 | 0.001000 | 0.009800 | 1007.367680 | False | True |
| locked_harder_holdout | holdout_bin_6 | 48 | heldout_47_51 | A2_linear_svm_margin | sgd_hinge_alpha0.0001_a1.0 | linear_svm | 24 | 8 | 0.500000 | -429.773416 | 792.076239 | 0.001000 | 0.009800 | 70.225584 | False | True |
| locked_harder_holdout | holdout_bin_6 | 49 | heldout_47_51 | A1_low_fpr_weighted_lr | lr_tail_q0.975_w8.0_a1.0 | lr | 24 | 8 | 1.000000 | 8.747389 | 11.711541 | 0.000500 | 0.010000 | 1008.746889 | False | True |
| locked_harder_holdout | holdout_bin_6 | 49 | heldout_47_51 | A2_linear_svm_margin | sgd_hinge_alpha1e-05_a1.0 | linear_svm | 24 | 8 | 1.000000 | 2452.651374 | 6828.843025 | 0.004500 | 0.009800 | 3452.646874 | False | True |
| locked_harder_holdout | holdout_bin_6 | 50 | heldout_47_51 | A1_low_fpr_weighted_lr | lr_tail_q0.95_w4.0_a1.0 | lr | 24 | 8 | 1.000000 | 6.128698 | 12.953916 | 0.001000 | 0.009800 | 1006.127698 | False | True |
| locked_harder_holdout | holdout_bin_6 | 50 | heldout_47_51 | A2_linear_svm_margin | sgd_hinge_alpha0.0001_a1.0 | linear_svm | 24 | 8 | 0.750000 | -82.432787 | 1314.078169 | 0.010000 | 0.006200 | 667.557213 | False | True |
| locked_harder_holdout | holdout_bin_6 | 51 | heldout_47_51 | A1_low_fpr_weighted_lr | lr_tail_q0.975_w8.0_a1.0 | lr | 24 | 8 | 1.000000 | 8.802545 | 14.154174 | 0.000500 | 0.010000 | 1008.802045 | False | True |
| locked_harder_holdout | holdout_bin_6 | 51 | heldout_47_51 | A2_linear_svm_margin | sgd_hinge_alpha0.0001_a2.0 | linear_svm | 24 | 8 | 0.875000 | 305.094247 | 1776.734262 | 0.003500 | 0.009800 | 1180.090747 | False | True |
| locked_harder_holdout | holdout_bin_7 | 42 | main_42_46 | A1_low_fpr_weighted_lr | lr_tail_q0.975_w8.0_a1.0 | lr | 24 | 8 | 1.000000 | 11.099549 | 13.954027 | 0.000000 | 0.009800 | 1011.099549 | False | True |
| locked_harder_holdout | holdout_bin_7 | 42 | main_42_46 | A2_linear_svm_margin | sgd_hinge_alpha1e-05_a1.0 | linear_svm | 24 | 8 | 0.875000 | 27055.114055 | 35052.214641 | 0.003500 | 0.009800 | 27930.110555 | False | True |
| locked_harder_holdout | holdout_bin_7 | 43 | main_42_46 | A1_low_fpr_weighted_lr | lr_tail_q0.95_w4.0_a1.0 | lr | 24 | 8 | 1.000000 | 10.069052 | 11.515190 | 0.002000 | 0.009800 | 1010.067052 | False | True |
| locked_harder_holdout | holdout_bin_7 | 43 | main_42_46 | A2_linear_svm_margin | sgd_hinge_alpha0.0001_a2.0 | linear_svm | 24 | 8 | 0.875000 | 1047.409332 | 2141.201568 | 0.001000 | 0.009800 | 1922.408332 | False | True |
| locked_harder_holdout | holdout_bin_7 | 44 | main_42_46 | A1_low_fpr_weighted_lr | lr_tail_q0.975_w8.0_a1.0 | lr | 24 | 8 | 1.000000 | 13.792223 | 19.703469 | 0.001000 | 0.009800 | 1013.791223 | False | True |
| locked_harder_holdout | holdout_bin_7 | 44 | main_42_46 | A2_linear_svm_margin | sgd_hinge_alpha1e-05_a1.0 | linear_svm | 24 | 8 | 0.875000 | 10095.989008 | 19033.829828 | 0.003500 | 0.009800 | 10970.985508 | False | True |
| locked_harder_holdout | holdout_bin_7 | 45 | main_42_46 | A1_low_fpr_weighted_lr | lr_tail_q0.95_w4.0_a1.0 | lr | 24 | 8 | 1.000000 | 12.226313 | 16.983744 | 0.001500 | 0.010000 | 1012.224813 | False | True |
| locked_harder_holdout | holdout_bin_7 | 45 | main_42_46 | A2_linear_svm_margin | sgd_hinge_alpha1e-05_a1.0 | linear_svm | 24 | 8 | 1.000000 | 8507.876480 | 19165.385758 | 0.003000 | 0.010000 | 9507.873480 | False | True |
| locked_harder_holdout | holdout_bin_7 | 46 | main_42_46 | A1_low_fpr_weighted_lr | lr_tail_q0.975_w8.0_a1.0 | lr | 24 | 8 | 1.000000 | 9.540519 | 13.216132 | 0.000000 | 0.009800 | 1009.540519 | False | True |
| locked_harder_holdout | holdout_bin_7 | 46 | main_42_46 | A2_linear_svm_margin | sgd_hinge_alpha1e-05_a1.0 | linear_svm | 24 | 8 | 0.750000 | 1938.503686 | 9837.698266 | 0.009000 | 0.009800 | 2688.494686 | False | True |
| locked_harder_holdout | holdout_bin_7 | 47 | heldout_47_51 | A1_low_fpr_weighted_lr | lr_tail_q0.975_w8.0_a1.0 | lr | 24 | 8 | 1.000000 | 11.853190 | 16.306018 | 0.001500 | 0.010000 | 1011.851690 | False | True |
| locked_harder_holdout | holdout_bin_7 | 47 | heldout_47_51 | A2_linear_svm_margin | sgd_hinge_alpha1e-05_a1.0 | linear_svm | 24 | 8 | 0.875000 | 11426.478166 | 18822.453263 | 0.001000 | 0.009800 | 12301.477166 | False | True |
| locked_harder_holdout | holdout_bin_7 | 48 | heldout_47_51 | A1_low_fpr_weighted_lr | lr_tail_q0.975_w8.0_a1.0 | lr | 24 | 8 | 1.000000 | 9.053660 | 12.870693 | 0.001500 | 0.010000 | 1009.052160 | False | True |
| locked_harder_holdout | holdout_bin_7 | 48 | heldout_47_51 | A2_linear_svm_margin | sgd_hinge_alpha1e-05_a1.0 | linear_svm | 24 | 8 | 0.875000 | 264.312048 | 8171.907507 | 0.002500 | 0.010000 | 1139.309548 | False | True |
| locked_harder_holdout | holdout_bin_7 | 49 | heldout_47_51 | A1_low_fpr_weighted_lr | lr_tail_q0.975_w8.0_a1.0 | lr | 24 | 8 | 1.000000 | 10.290153 | 11.759209 | 0.000500 | 0.010000 | 1010.289653 | False | True |
| locked_harder_holdout | holdout_bin_7 | 49 | heldout_47_51 | A2_linear_svm_margin | sgd_hinge_alpha0.0001_a1.0 | linear_svm | 24 | 8 | 1.000000 | 414.954570 | 561.791454 | 0.001500 | 0.010000 | 1414.953070 | False | True |
| locked_harder_holdout | holdout_bin_7 | 50 | heldout_47_51 | A1_low_fpr_weighted_lr | lr_tail_q0.975_w8.0_a1.0 | lr | 24 | 8 | 1.000000 | 10.281308 | 10.717506 | 0.001000 | 0.009800 | 1010.280308 | False | True |
| locked_harder_holdout | holdout_bin_7 | 50 | heldout_47_51 | A2_linear_svm_margin | sgd_hinge_alpha1e-05_a1.0 | linear_svm | 24 | 8 | 0.875000 | 6637.515226 | 16109.941495 | 0.001000 | 0.009800 | 7512.514226 | False | True |
| locked_harder_holdout | holdout_bin_7 | 51 | heldout_47_51 | A1_low_fpr_weighted_lr | lr_tail_q0.95_w4.0_a1.0 | lr | 24 | 8 | 1.000000 | 12.364187 | 16.080802 | 0.001500 | 0.010000 | 1012.362687 | False | True |
| locked_harder_holdout | holdout_bin_7 | 51 | heldout_47_51 | A2_linear_svm_margin | sgd_hinge_alpha1e-05_a1.0 | linear_svm | 24 | 8 | 0.875000 | 7889.244928 | 11069.269586 | 0.003500 | 0.009800 | 8764.241428 | False | True |
