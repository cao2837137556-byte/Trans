# issue27cke Bounded Support Adequacy Audit

primary_verdict: `attack_coverage_gain_with_ood_stress_tradeoff_requires_fresh_attack_and_benign_holdout`

- selected static variant: `E64_nested_source_time_balanced`
- selected extension rows: `64`
- baseline active-strong regions: `2`
- selected active-strong regions: `2`
- baseline mean support-val consistency: `0.716190`
- selected mean support-val consistency: `0.721190`
- baseline OOD-val nearest core+near: `0.765708`
- selected OOD-val nearest core+near: `0.765375`
- support-val net corrected rows: `1` of `127`.
- paired exact McNemar p-value: `1.000000`.
- material static gain: `False`.
- active labels passing reused historical query diagnostic: `Mirai GRE Flooding`.
- active labels with descriptive OOD-stress regression over 0.01: `Mirai GRE Flooding`.
- historical query status: `development diagnostic; not fresh validation`.
- original 512 support rows mutated: `false`.
- controller integration: `false`.
- sealed-final access: `false`.

Close-out:

```text
solved: Audited nested +64/+128 source-time-balanced extensions under frozen S3, two-medoid geometry, activation gates, and role boundaries.
changed_mainline: no
active_blocker: attack_coverage_gain_with_ood_stress_tradeoff_requires_fresh_attack_and_benign_holdout.
frozen: original 512 bank, support-val partition, S3, activation gates, and query contamination status.
superseded: treating previously inspected query roles as fresh deployment certification evidence.
next_action: reserve_or_materialize_fresh_temporal_attack_and_benign_ood_holdout_before_any_registry_freeze.
```
