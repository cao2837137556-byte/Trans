# issue27p Full Mirai Anonymous Clean115 Formal Benchmark Execution

1. issue27p completed: `true`.
2. primary_verdict: `baseline_dominates_needs_method_rethink`.
3. preflight: `pass`.
4. anonymous_clean115 materialized/read: `true`; clean115 rows=764137, cols=115.
5. formal split fixed and hashed: `true`.
6. LOW-GUARD++: detection_mean=0.731811, detection_min=0.096397, OOD_max=0.028139, feasible_rate=0.800.
7. LOW-GUARD-LR: detection_mean=0.705204, detection_min=0.071734, OOD_max=0.010756, feasible_rate=0.600.
8. current strongest method by ranking: `DeepSADStyle_Lite`.
9. baseline fully dominates LOW-GUARD++: `DeepSADStyle_Lite`.
10. collapse models were rerun under reset protocol; see collapse_models_summary.csv.
11. obvious leakage/artifact flags: `none_detected`.
12. all formal local baseline methods completed: `True`.
13. missing methods / Slurm: exact full RBF OC-SVM is deferred; local reset benchmark used scalable OC-SVM and recommends Slurm for seed/resource expansion.
14. current mainline decision: `baseline_dominates_needs_method_rethink`.
15. issue27q recommendation: `issue27q_protocol_reset_result_audit_and_seed_expansion_2026-05-27`.
16. commit hash: pending.
