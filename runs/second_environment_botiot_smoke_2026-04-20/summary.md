# BoT-IoT Second Environment Smoke Summary

- Run tag: `second_environment_botiot_smoke_2026-04-20`
- Train CSV: `D:\study\paper\anomaly_detection\paper04\worktrees\data\5%\10-best features\10-best Training-Testing split\UNSW_2018_IoT_Botnet_Final_10_best_Training.csv`
- Test CSV: `D:\study\paper\anomaly_detection\paper04\worktrees\data\5%\10-best features\10-best Training-Testing split\UNSW_2018_IoT_Botnet_Final_10_best_Testing.csv`
- Label column: `attack` (`normal=0`)
- Numeric feature count used: `11`

## Split Summary
- `id_benign_train`: 370 samples, 11 features
- `ood_benign_test`: 107 samples, 11 features
- `attack_test`: 100000 samples, 11 features

## Smoke Results
- `isolation_forest` / `det_floor_50pct_min_alarm`: ood_alarm=0.000000, attack_det=0.501320, id_alarm=0.000000, auc=0.983223
- `isolation_forest` / `fixed_id_q99`: ood_alarm=0.000000, attack_det=0.743960, id_alarm=0.010811, auc=0.983223
- `isolation_forest` / `naive_calibrated_budget500_target1pct`: ood_alarm=0.018692, attack_det=0.777720, id_alarm=0.021622, auc=0.983223
- `oneclass_svm` / `det_floor_50pct_min_alarm`: ood_alarm=0.168224, attack_det=1.000000, id_alarm=0.175676, auc=1.000000
- `oneclass_svm` / `fixed_id_q99`: ood_alarm=0.037383, attack_det=1.000000, id_alarm=0.010811, auc=1.000000
- `oneclass_svm` / `naive_calibrated_budget500_target1pct`: ood_alarm=0.018692, attack_det=1.000000, id_alarm=0.000000, auc=1.000000

## Note
- This is a local smoke node for second-environment readiness, not a formal multi-seed model comparison.
