# TON-IoT Second Environment Smoke Summary

- Run tag: `second_environment_toniot_smoke_2026-04-20`
- CSV: `D:\study\paper\anomaly_detection\paper04\worktrees\data\Train_Test_Network_dataset\train_test_network.csv`
- Label column: `label` (`normal=0`)
- Numeric feature count: `16`

## Split
- `id_benign`: 30000 samples, 16 features
- `ood_benign`: 20000 samples, 16 features
- `attack`: 100000 samples, 16 features

## Results
- `isolation_forest` / `det_floor_50pct_min_alarm`: ood_alarm=0.886150, attack_det=0.501590, id_alarm=0.310633, auc=0.247002
- `isolation_forest` / `fixed_id_q99`: ood_alarm=0.003700, attack_det=0.009740, id_alarm=0.009967, auc=0.247002
- `isolation_forest` / `naive_calibrated_budget5000_target1pct`: ood_alarm=0.003500, attack_det=0.009310, id_alarm=0.009800, auc=0.247002
- `oneclass_svm` / `det_floor_50pct_min_alarm`: ood_alarm=0.851950, attack_det=0.501520, id_alarm=0.421733, auc=0.183949
- `oneclass_svm` / `fixed_id_q99`: ood_alarm=0.496850, attack_det=0.125160, id_alarm=0.010000, auc=0.183949
- `oneclass_svm` / `naive_calibrated_budget5000_target1pct`: ood_alarm=0.007300, attack_det=0.003270, id_alarm=0.003367, auc=0.183949

## Note
- This is a local smoke node for TON-IoT fallback readiness, not a formal multi-seed comparison.
