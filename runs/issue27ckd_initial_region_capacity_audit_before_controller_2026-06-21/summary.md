# issue27ckd Initial Region Capacity Audit

primary_verdict: `static_region_capacity_gain_but_temporal_label_stability_blocked`

- decision: `GO`
- selected variant: `V1_frozen512_two_medoid`
- baseline active-strong regions: `1`
- selected active-strong regions: `2`
- added active-strong regions: `1`
- baseline mean support-val consistency: `0.664048`
- selected mean support-val consistency: `0.716190`
- selected OOD-val nearest core+near rate: `0.765708`
- V0 reproduction pass: `True`
- support reselection: `false`
- unused candidate reuse: `false`
- temporal diagnostic status: `BLOCKED_FOR_CONTROLLER_FREEZE`
- selected active labels with temporal/query caveats: `Mirai GRE Flooding`, `Mirai UDP Flooding`.

Current candidate-pool structural ceiling:

- labels with only one eligible provenance source and therefore unable to pass the unchanged two-source strong gate: `File Download`, `Ingress Tool Transfer`, `Merlin C&C Communication`, `Mirai C&C Communication`.

Close-out:

```text
solved: Audited whether train-only multi-prototype region geometry can improve the frozen 512-row initial support bank under S3.
changed_mainline: no
active_blocker: The two-medoid candidate improves static qualification, but active-label temporal/query stability is not yet sufficient for registry freeze; single-source labels also cannot pass the current strong gate with this candidate pool.
frozen: original 512 support rows and partitions, S3 transform/distance, activation gates, and role order.
superseded: immediate controller integration as the next action before initial region capacity is resolved.
next_action: bounded_support_adequacy_and_temporal_coverage_audit_before_registry_freeze.
```
