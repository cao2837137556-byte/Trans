# issue27bt Stability Checks

- time_half: reproduces the issue27bs validation style.
- group_disjoint_source: uses source-group disjoint fit/select where each role has multiple source groups; single-source roles are marked as time-half fallback.
- no_parent_oodrisk ablations remove `ood_risk`, `past_source_ood_risk_mean_w32`, and `past_source_high_ood_risk_rate_w32`.
- Final OOD and sealed attack roles are replay-only.
