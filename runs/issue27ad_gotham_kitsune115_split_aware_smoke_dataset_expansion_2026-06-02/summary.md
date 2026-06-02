# issue27ad Summary

1. issue27ad complete: yes.
2. primary_verdict: `kitsune115_split_aware_smoke_dataset_ready_heavy_attack_deferred`.
3. ID/OOD/final OOD source rule: preregistered benign files only.
4. Attack source rule: onset-aligned malicious PCAPs only.
5. Attack files onset-aligned: `True`.
6. Attack files locally materialized: `6` of `8`.
7. hard gates pass: `True`.
8. numeric stability pass: `True`.
9. rows by strategy: `[{'strategy': 'reset_at_split_boundary', 'rows': 4800, 'columns': 115, 'finite_rate': 1.0, 'nan_count': 0, 'inf_count': 0, 'model_metric_computed': False}, {'strategy': 'train_state_then_eval_online', 'rows': 4800, 'columns': 115, 'finite_rate': 1.0, 'nan_count': 0, 'inf_count': 0, 'model_metric_computed': False}]`.
10. model experiment allowed: no.
11. issue27ae recommendation: choose either model interface shape smoke or larger 115D materialization with fast frontend/Slurm for heavy attack files.
12. commit hash: pending.
