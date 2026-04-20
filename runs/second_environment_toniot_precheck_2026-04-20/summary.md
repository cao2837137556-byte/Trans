# TON-IoT Formal Precheck Summary

- Run tag: `second_environment_toniot_precheck_2026-04-20`
- Verdict: `polarity_checked_ready_for_formal_object_runs`
- Reason: Orientation and split manifest are fixed; baseline signal passes minimum AUC gate.
- CSV: `D:\study\paper\anomaly_detection\paper04\worktrees\data\Train_Test_Network_dataset\train_test_network.csv`
- Split: ID=30000, OOD=20000, attack=100000
- Numeric feature count: `16`

## Polarity
- `isolation_forest`: chosen `raw_decision`, auc=0.752998, other=0.247002, delta=0.505996
- `oneclass_svm`: chosen `raw_decision`, auc=0.816051, other=0.183949, delta=0.632102

## Next
- Use `split_manifest.json` as the fixed source split for formal object runs.
- Run `dA`, `current strongest candidate`, and `FT` line under the same policy family on this split.
