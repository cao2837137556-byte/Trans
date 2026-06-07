# Conflict-Aware Attack Shell Gate

This diagnostic keeps the raw detector score on the full Kitsune115 feature space, but lets prototype gating use a fixed feature-family subspace.

Decision idea:

```text
if raw_attack_alarm is false: no_alarm
elif pure inner attack core: hard_alarm
elif high raw score + pseudo-query-calibrated outer attack shell + benign is not overwhelmingly stronger: hard_alarm
elif weak score + benign core + outside attack shell: suppress
elif attack shell and benign core overlap: bounded review_conflict
else: bounded review_unknown or review_overflow_no_alarm
```

The selected subspace and all thresholds are selected only from dev-side roles. Report-only roles are replayed after selection.
