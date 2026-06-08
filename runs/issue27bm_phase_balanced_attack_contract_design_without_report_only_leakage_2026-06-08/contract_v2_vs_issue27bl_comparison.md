# Contract v2 vs issue27bl Comparison

- issue27bl verdict: `attack_phase_contract_mismatch_needs_rebuild_before_more_heads`
- issue27bm primary contract: `phase_balanced_dev_v2`
- issue27bm primary verdict: `phase_balanced_contract_ready_for_attack_only_diagnostic_with_tail_gap_caveat`
- old pseudo-query q50 gap max available: `6.5275726318359375`
- new primary pseudo-query q50 gap: `0.6750279664993286`
- q50 gap improved vs old pseudo baseline: `True`

## Interpretation

- The new contract does not use `attack_eval`, `final_ood_benign_eval`, or dev-heavy query labels/features for support construction.
- It creates a development-side support/val/pseudo-query contract from the preregistered `attack_support` role plus active-label candidate rows after simulated manual confirmation.
- The contract is phase-balanced for available early/mid attack phases, but it does not cover late/tail attack phases because those are not available in the legal development-side support pool.
- Therefore it is appropriate for the next attack-only diagnostic, not for a formal benchmark or OOD-gate repair.
