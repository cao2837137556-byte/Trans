# Gotham Kitsune115 Numeric Stability Report

- Strategies checked: `reset_at_split_boundary, train_state_then_eval_online`.
- Any NaN/Inf at strategy level: `false`.
- Per-feature details are in `gotham_kitsune115_numeric_stability.csv`.
- Constant features in this tiny smoke are not automatically blocking; full materialization must re-check constants at larger scale.
