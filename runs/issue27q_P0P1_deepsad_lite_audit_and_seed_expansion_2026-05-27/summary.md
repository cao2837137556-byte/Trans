# issue27q P0P1 DeepSADStyle_Lite Audit Summary

1. issue27q_P0P1 completed: `true`.
2. primary_verdict: `deepsad_lite_result_suspicious_needs_artifact_debug`.
3. issue27p DeepSADStyle_Lite replay reproduced: `True`.
4. score direction correct: `true` (higher weighted-center distance is more anomalous).
5. threshold replay correct: `True`.
6. final eval report-only: `True`.
7. support and attack eval disjoint: `True`.
8. negative controls behaved as expected: `False`.
9. label-like / index-like / row-order artifact: `near_perfect_cols=0`.
10. seeds 42..51 stable: `True`.
11. attack/OOD stratification exposed weakness: `worst_attack_decile=8`.
12. DeepSADStyle_Lite can continue as mainline candidate: `False`.
13. can proceed to LOW-GUARD++ failure diagnosis: `False`.
14. Slurm needed: `not for P0 controls; recommended for broader follow-up`.
15. next recommendation: `issue27r_deepsad_lite_artifact_debug_and_feature_provenance`.
16. commit hash: pending.
