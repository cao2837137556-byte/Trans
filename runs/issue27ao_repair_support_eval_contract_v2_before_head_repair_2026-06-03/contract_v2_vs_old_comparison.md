# Contract V2 vs Old Comparison

- best_contract_by_support_val_p95: `file_balanced_v2`
- old support_val_union max group p95: 7.677603
- old support_val_union max group max: 884839.687500
- v2 support_val_to_eval p95: 5.716684
- v2 support_val_to_eval max: 11.582300
- v2 support_train_to_eval p95: 3.697550
- v2 support_train_to_eval max: 6.327081

Important caveat: this consumes the previous medium attack_eval rows for diagnostic contract design. Any later detection retest on this v2 contract remains medium diagnostic only and cannot be treated as formal evaluation.
