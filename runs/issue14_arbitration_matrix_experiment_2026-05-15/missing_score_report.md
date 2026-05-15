# Missing Score Report

## Available

- dA per-sample score caches are available under `runs/original100_fewshot_official_control_2026-04-22/score_cache/`.
- Transformer per-sample score caches are available under `runs/issue07b_transformer_full_id_score_recovery_2026-05-14/score_cache/`.
- issue11 threshold provenance and support provenance are available.

## Missing

- issue11 does not save per-sample GDA-minimal scores for `original100_fixed_guard_lr`.
- issue11 does not save fitted scaler/model objects that would allow exact post-hoc scoring without rerunning the adapter fitting step.

## Consequence

The following cannot be computed safely in this run:

- `gda_high(x)` on final OOD eval and attack eval.
- conflict cells: both-high, base-low/GDA-high, base-high/GDA-low, both-low.
- base-only / GDA-only / OR / AND / mode-gated strategy metrics on identical row ids.

## Minimal recovery

Run a score-recovery pass for issue11 fixed configuration only:

1. Reuse the exact issue11 code, split, supports, scaler rule, `OOD weight=2`, threshold policy, seeds, and budgets.
2. Do not search any hyperparameter.
3. Persist per-sample decision scores and binary high flags for final OOD eval and attack eval.
4. Persist row ids and threshold values.
5. Then rerun issue14 arbitration metrics.

This should be labeled as score recovery for an existing fixed experiment, not as a new model search.
