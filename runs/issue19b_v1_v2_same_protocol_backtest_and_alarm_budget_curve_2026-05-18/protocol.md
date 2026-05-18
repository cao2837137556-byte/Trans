# Protocol

This is a V1/V2 same-protocol backtest plus alarm-budget curve. It is not new method development and not locked validation.

- V1: original100 representation, kcenter32 support selected from the applicable attack train pool only, L2 LogisticRegression, OOD weight 2.
- V2: selected_source_rich_top32 selected by the fixed issue19 rule using only attack supports, ID calibration, and OOD validation; kcenter32 support; L2 LogisticRegression; OOD weight 2.
- Thresholds: guarded ID calibration + OOD validation thresholds at targets 0.5pct, 0.8pct, 1.0pct, 1.2pct, 1.5pct, 2.0pct.
- Official reporting target: 1.0%.
- Diagnostic targets: all non-1.0% entries. They cannot be selected as final thresholds from this run.
- Final OOD eval and attack eval are used only for final evaluation.
- Support selection does not use attack eval or final OOD eval.
- Primary low-OOD split follows issue09 stage2 high-purity attack split.
- Harder holdout split follows the issue17/18/19 repair-line local-calibration slice for comparability with issue19.
