# Protocol

- Fixed V1: original100 + kcenter32 + fixed guard LR.
- Fixed V2: selected_source_rich_top32 + kcenter32 + fixed guard LR.
- Fixed OOD target for champion scores: 1%.
- Routing rule: V2 active only if V2 validation OOD alarm <= 1% and V2 attack validation proxy exceeds V1 by at least 0.05; otherwise V1 active.
- Strategies: always_V1, always_V2, OR_policy, AND_policy, LOW_GUARD_Routed, oracle_best_feasible.
- No final OOD eval or attack eval is used for routing.
- This run recovers fixed V1/V2 scores from the same definitions for strategy validation; it does not introduce V3, topK search, margin hardneg, or changed thresholds.
