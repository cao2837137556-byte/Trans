# Protocol

This run reuses issue22 fixed outputs. It does not train a new model, reselect topK, tune thresholds, or run routing/promotion.

Compared candidates:

- V1: original100 + kcenter32 + fixed guard LR.
- V2_top32: selected_source_rich_top32 + kcenter32 + fixed guard LR.
- V2_top64: selected_source_rich_top64 + kcenter32 + fixed guard LR.

Official operating point is the 1% guarded target. Other alarm-budget targets are diagnostic only and are not used to select a new threshold.
