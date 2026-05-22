# Baseline Candidate Definitions

| method | baseline_category | feature_kind | model_kind | uses_attack_supports | support_count | run_priority |
|---|---|---|---|---|---|---|
| M0_V1_original100_fixed_guard_LR | existing_detector_baseline | original100 | guarded_lr | True | 32 | required |
| M1_V2_top32_fixed_guard_LR | existing_detector_baseline | source_rich_top32 | guarded_lr | True | 32 | required |
| M2_Enhanced_LOW_GUARD_top64_fixed_guard_LR | main_method | source_rich_top64 | guarded_lr | True | 32 | required |
| M3_top64_no_guard_LR | component_ablation | source_rich_top64 | no_guard_lr | True | 32 | required |
| M4_top64_random32_fixed_guard_LR | component_ablation | source_rich_top64 | guarded_lr | True | 32 | required |
| M5_Isolation_Forest_top64 | unsupervised_anomaly | source_rich_top64_frozen_main | isolation_forest | False | 0 | required |
| M6_OC_SVM_top64 | unsupervised_anomaly | source_rich_top64_frozen_main | ocsvm_sgd | False | 0 | required |
| M7_HistGB_shallow_top64 | nonlinear_tabular | source_rich_top64 | histgb | True | 32 | required |
| M8_DevNet_like_MLP_top64 | fewshot_anomaly | source_rich_top64 | devnet_like_mlp | True | 32 | required |
| M9_DeepSAD_like_center_top64 | semisupervised_anomaly | source_rich_top64 | deepsad_like_center | True | 32 | required |
