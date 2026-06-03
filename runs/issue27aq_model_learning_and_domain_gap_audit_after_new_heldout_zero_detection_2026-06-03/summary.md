# Issue27aq Summary

1. issue27aq completed: yes
2. primary_verdict: `zero_detection_due_to_ood_tail_threshold_overconservative_despite_raw_support_signal`
3. Did the audit use new heldout for fit/support/threshold/model selection: no
4. Did the audit use final OOD for fit/support/threshold/model selection: no
5. fit class balance: ID=3000, support_train=128, ratio=23.438:1, no class/sample weighting
6. support_train detection at issue27ap threshold, max over seeds: 0.000000
7. support_val detection at issue27ap threshold, max over seeds: 0.000000
8. new heldout detection at issue27ap threshold, max over seeds: 0.000000
9. OOD-vs-new heldout max feature AUC(abs): 0.996699
10. new heldout nearest support_train distance p95: 8179.160645
11. score direction/proba column: `predict_proba class_index=1 for attack class 1; higher score means more attack-like`
12. current interpretation: zero detection is not just a new heldout problem; raw support signal exists, but the OOD-tail threshold is above support and heldout scores, so learning/calibration/threshold handling must be audited before further data reshuffling.
13. issue27ar recommendation: `issue27ar_balanced_fit_and_threshold_debug_without_final_eval`
14. formal benchmark allowed: no
15. commit hash: pending
