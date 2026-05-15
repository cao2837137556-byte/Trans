# Review Policy Comparison

- `review_off`: equivalent to GDA-only high-priority alerting.
- `review_all`: full mode-gated review queue from issue14b.
- `review_top_0.25pct` to `review_top_2pct`: bounded review queue using base-score ranking inside base-high/GDA-low candidates.

The review budget controls operational review burden. It does not alter the GDA guarded threshold and does not change high-priority OOD alarm.
