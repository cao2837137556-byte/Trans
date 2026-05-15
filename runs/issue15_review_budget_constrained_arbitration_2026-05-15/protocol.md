# Issue15 Review-Budget Constrained Arbitration Protocol

This analysis reads issue14b row-level base/GDA scores and does not train or retune any model.

Review queue definition:

- `base_high = base_score >= base_threshold`
- `gda_high = gda_score >= gda_threshold`
- review queue = `base_high=true` and `gda_high=false`

High-priority alerts are controlled by GDA-minimal. Review samples are not counted as high-priority detections and are not confirmed attacks.

Budget policy:

- `review_off`: no review queue.
- `review_all`: all base-only high rows enter review.
- `review_top_0.25pct`, `review_top_0.5pct`, `review_top_1pct`, `review_top_2pct`: select top base-score review candidates using a pre-specified budget relative to final OOD eval size.

All budgets are reported; no final-eval selection of a best budget is performed.
