# Recommended Next Action

Start `issue14b_gda_minimal_score_recovery_for_arbitration_2026-05-15`.

Scope:

- reuse issue11 fixed configuration only;
- no hyperparameter search;
- no threshold change;
- no split/support/scaler change;
- persist row-level scores and high flags for `original100_fixed_guard_lr` 32-shot on main seeds 42-46 and held-out seeds 47-51;
- then compute issue14 arbitration policies on identical final OOD and attack eval ids.

If score recovery succeeds, rerun issue14 and report the full strategy metrics. If it fails, keep arbitration as a design discussion rather than empirical evidence.
