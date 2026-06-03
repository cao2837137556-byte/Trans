# Coverage Gate v0 Draft

This is a draft only. It is not applied in issue27at and is not tuned on new heldout.

1. Compute support coverage using a scaler fit only on `support_train`.
2. Define distance buckets using `support_val` nearest-support distance quantiles.
3. `allow_adaptation` if nearest distance <= support_val p75 and at least attack_type plus one of source_file/device/onset_phase is covered by train/val support.
4. `needs_review` if nearest distance is between p75 and p95 or semantic coverage is partial.
5. `support_insufficient_needs_more_labels` if nearest distance > p95 or semantic coverage is missing.

The rule is intended for future active-labeling/support adequacy checks, not for selecting issue27at results.
