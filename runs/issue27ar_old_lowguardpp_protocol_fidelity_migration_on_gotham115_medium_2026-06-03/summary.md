# Issue27ar Summary

1. issue27ar completed: yes
2. primary_verdict: `old_protocol_fidelity_mixed_needs_bounded_calibration_repair`
3. scope: old LOW-GUARD++ protocol fidelity migration on Gotham Kitsune115 medium; not formal benchmark
4. frozen old config: `histgb_d2_lr005_l2p1_ood4_sup4_t0050`
5. old support selector restored: `kcenter32` from preregistered attack_support only
6. old HistGB fit roles restored: `id_fit + ood_train_guard + support_attack`
7. old sample weights restored: `ID=1, OOD=4, support=4`
8. old threshold rule restored: `guarded_val_threshold(id_calib, ood_val, target=0.005)`
9. final OOD / attack_eval / new heldout used for selection: no
10. Gotham caveat: explicit old `id_calib` and `ood_train` roles are absent, so deterministic train/val-side subroles were used for diagnostic fidelity
11. primary old-formal attack_eval_detection_mean/min: `0.9084444444444445` / `0.9084444444444445`
12. primary old-formal new_heldout_detection_mean/min: `0.2053333333333333` / `0.20533333333333334`
13. primary old-formal final_ood_alarm_max: `0.004`
14. formal benchmark allowed: no
15. next action: `issue27as_old_protocol_fidelity_interpretation_or_threshold_repair_without_final_eval`
16. commit hash: pending
