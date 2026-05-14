# Issue07a dA-assisted Few-shot Adapter Summary

## 1. Scope
This run executed only the dA-assisted few-shot adapter branch. It did not retrain dA, did not use Transformer, did not train a new backbone, did not modify the manuscript, and did not change any existing result files.

## 2. Score alignment
- dA ID score length: 50000 / ID rows: 50000.
- dA OOD score length: 20000 / OOD rows: 20000.
- dA attack score length: 10000 / attack rows: 10000.
- Alignment status: passed.

## 3. Fixed baselines
| baseline | positive_budget | source_path | roc_auc_attack_vs_ood | final_ood_alarm | attack_detection | feasible_rate | reuse_status |
|---|---|---|---|---|---|---|---|
| fixed_baseline_da_only | -1 | D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline\runs\original100_fewshot_official_control_2026-04-22\original100_fewshot_official_control_focus.csv | 0.806365 | 0.010800 | 0.002909 | 0.000000 | exact_current_protocol_reusable |
| fixed_baseline_original100_lr | 16 | D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline\runs\fewshot_seed_stability_pack_2026-04-30\paper_facing_table.csv | 0.990672 | 0.004440 | 0.967564 | 1.000000 | exact_current_protocol_reusable |
| fixed_baseline_original100_lr | 32 | D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline\runs\fewshot_seed_stability_pack_2026-04-30\paper_facing_table.csv | 0.984615 | 0.006520 | 0.940655 | 1.000000 | exact_current_protocol_reusable |


## 4. Adapter summary
| method | input_mode | positive_budget | n_seeds | auc_mean | auc_min | auc_max | pr_auc_mean | ood_alarm_mean | ood_alarm_min | ood_alarm_max | attack_detection_mean | attack_detection_min | attack_detection_max | feasible_rate | train_time_mean | latency_ms_mean | params_mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| da_score_only_fewshot_lr | da_score_only | 16 | 5 | 0.193633 | 0.193624 | 0.193643 | 0.084461 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 1.000000 | 0.015649 | 0.000051 | 2.000000 |
| original100_plus_da_score_fewshot_lr | original100_plus_da_score | 16 | 5 | 0.990661 | 0.958012 | 0.999916 | 0.972007 | 0.004480 | 0.001400 | 0.009200 | 0.967564 | 0.914182 | 0.999273 | 1.000000 | 1.023448 | 0.001824 | 102.000000 |
| da_score_only_fewshot_lr | da_score_only | 32 | 5 | 0.193636 | 0.193631 | 0.193642 | 0.084465 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 1.000000 | 0.012578 | 0.000063 | 2.000000 |
| original100_plus_da_score_fewshot_lr | original100_plus_da_score | 32 | 5 | 0.984623 | 0.967653 | 0.999910 | 0.942002 | 0.006560 | 0.003600 | 0.009900 | 0.940655 | 0.920727 | 0.999273 | 1.000000 | 0.989483 | 0.001552 | 102.000000 |


## 5. Repair vs dA-only
| method | positive_budget | adapter_detection_mean | adapter_ood_alarm_mean | base_detection | base_ood_alarm | detection_delta_vs_da_only | ood_alarm_delta_vs_da_only | base_repair_supported |
|---|---|---|---|---|---|---|---|---|
| da_score_only_fewshot_lr | 16 | 0.000000 | 0.000000 | 0.002909 | 0.010800 | -0.002909 | -0.010800 | False |
| original100_plus_da_score_fewshot_lr | 16 | 0.967564 | 0.004480 | 0.002909 | 0.010800 | 0.964655 | -0.006320 | True |
| da_score_only_fewshot_lr | 32 | 0.000000 | 0.000000 | 0.002909 | 0.010800 | -0.002909 | -0.010800 | False |
| original100_plus_da_score_fewshot_lr | 32 | 0.940655 | 0.006560 | 0.002909 | 0.010800 | 0.937745 | -0.004240 | True |


## 6. Value over original100-only LR
| method | positive_budget | adapter_detection_mean | adapter_ood_alarm_mean | original100_lr_detection_mean | original100_lr_ood_alarm_mean | detection_delta_vs_original100_lr | ood_alarm_delta_vs_original100_lr | adds_value_over_original100_lr |
|---|---|---|---|---|---|---|---|---|
| original100_plus_da_score_fewshot_lr | 16 | 0.967564 | 0.004480 | 0.967564 | 0.004440 | 0.000000 | 0.000040 | False |
| original100_plus_da_score_fewshot_lr | 32 | 0.940655 | 0.006560 | 0.940655 | 0.006520 | -0.000000 | 0.000040 | False |


## 7. Interpretation boundary
- This is not a replacement claim against dA.
- dA remains the cold-start unsupervised detector.
- The LR adapter is a minimal deployment-stage target-alignment module.
- Transformer adapter branches are not executed here because full-ID Transformer scores are still missing.

## 8. dA score-only diagnostic

`da_score_only_fewshot_lr` did not repair the guarded low-OOD collapse. The added diagnostic files show that one-dimensional dA scores are dominated by the OOD benign score tail; sparse attack supports do not define a stable attack-oriented boundary in this scalar space. This is a negative adapter result for dA-score-only, not a split/provenance failure.
