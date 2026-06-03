# Old LOW-GUARD++ Protocol Fidelity Report

- primary_verdict: `old_protocol_fidelity_mixed_needs_bounded_calibration_repair`
- Scope: Gotham Kitsune115 medium diagnostic only, not formal benchmark.
- Historical protocol target: issue27f LOW-GUARD++ HistGB original100 frozen B.
- Frozen config: `histgb_d2_lr005_l2p1_ood4_sup4_t0050` with max_depth=2, learning_rate=0.05, l2=0.1, ood_weight=4, support_weight=4, max_iter=60.
- Support selector: old kcenter32 over the preregistered `attack_support` role only.
- Formal-like variant uses all 32 kcenter support rows for fit.
- Selection-trace-like variant splits support 24/8 using `seed + 27027` for support_val diagnostics.
- Because the Gotham medium asset has no separate `id_calib` or `ood_train` roles, this run uses train/val-side deterministic subsplits and records that caveat.
- Final OOD, attack_eval, and new heldout are report-only and never used for support, fit, threshold, or selection.

## Why This Is Not Formal

- Medium asset only; full_contract remains pending.
- Dataset/frontend changed from old original100 to Gotham Kitsune115.
- Internal train-side/val-side subsplits are diagnostic approximations of old roles.
- Results can indicate protocol mismatch but cannot be a paper model ranking.
