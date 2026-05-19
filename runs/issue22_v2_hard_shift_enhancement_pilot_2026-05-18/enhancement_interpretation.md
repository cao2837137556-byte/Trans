# Enhancement Interpretation

Best official-1% holdout_bin_2 method: `M8_source_rich_top64_kcenter32_fixed_guard`.

- Holdout_bin_2 detection: `0.974036`.
- Holdout_bin_2 OOD alarm max: `0.005700`.
- Reaches 0.85 threshold: `True`.
- Reaches 0.90 threshold: `True`.

Interpretation should be based on the method-group deltas:

- Alarm-budget operating points are diagnostic only.
- Support budget changes test whether V2 is label-budget limited.
- Feature-count sensitivity tests whether selected_source_rich_top32 is under/over-sized.
- Hard-negative sanity tests whether low-FPR weighting helps without introducing a new model class.

Any candidate must pass locked validation before becoming a new V2.
