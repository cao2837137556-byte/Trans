# Strict Packet Split Materialization Report

- primary contract: `gotham_device_disjoint_v1`
- id_benign_train: 1716285 rows
- ood_benign_val: 1308423 rows
- final_ood_benign_eval: 842307 rows
- attack_support_pool: 7619570 rows
- attack_eval: 15250158 rows
- attack support/eval are file-disjoint by preregistered contract.
- final OOD and attack eval are report-only roles.
- The split is materialized as row-level sidecar metadata, not chosen from model outcomes.
