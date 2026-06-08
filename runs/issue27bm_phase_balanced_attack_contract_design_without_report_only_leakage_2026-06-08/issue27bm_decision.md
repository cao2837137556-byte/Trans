# issue27bm Decision

primary_verdict = `phase_balanced_contract_ready_for_attack_only_diagnostic_with_tail_gap_caveat`

- primary_contract: `phase_balanced_dev_v2`
- support_train_rows: `128`
- support_val_rows: `64`
- pseudo_query_dev_rows: `1024`
- forbidden_role_access: `False`
- uses_attack_eval_labels_for_support: `False`
- tail_phase_gap: `True`
- attack_go_threshold remains: `0.93`

This is a contract design/audit task. It does not run model training, does not repair heads, and does not permit OOD-gate repair.
