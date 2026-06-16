# Support Bank Protocol v1

This protocol freezes the executable boundary for the initial Gotham Kitsune115 support bank. It does not freeze empirical hyperparameters or controller thresholds.

## Scope

The protocol starts from development-side exact-label attack candidates and ends with a support bank that can later be instantiated after issue27cd materialization is complete.

No model training, metric optimization, final replay, or detection-rate interpretation is part of this issue.

## Pipeline

```text
development-side exact-label attack candidates
-> eligibility filtering
-> semantic taxonomy assignment
-> region assignment
-> coverage audit
-> global budget allocation
-> diversity selection
-> support_train / support_val split
-> initial support bank
```

## Eligibility Rules

A row is eligible only when all conditions hold:

- `source_role` is a development-side support-candidate role.
- `label` is an exact allowed attack label.
- `label` is not `Benign`, `Unknown`, empty, or inferred only from post-onset binary logic.
- PCAP pairing is available at the file level.
- CSV row timestamp and PCAP packet timestamp are aligned within the configured tolerance.
- The row is not from `dev_future_attack_query`, `same_file_time_forward_dev_query`, `sealed_final_attack`, `sealed_final_ood`, `final_ood_benign_eval`, `attack_eval`, or any report-only role.
- The row is not quarantined, retired, or marked unstable by the materialization audit.

## Frozen Invariants

- Candidate pool is not the support bank.
- The support bank is globally budgeted; it is not one unlimited pool per attack family.
- `support_train` and `support_val` are permanently disjoint.
- Final/report-only roles are never used for support selection, threshold selection, calibration, model selection, region creation, or protocol tuning.
- Unselected candidates do not silently enter training.
- Active update and candidate reuse are pending topics and must be opened by an explicit later issue.
- The current issue freezes interfaces and invariants only; empirical thresholds and budgets remain open.

## Open Parameters

The following are placeholders, not fixed values:

- `support_budget`
- `region_cap`
- `support_train_val_ratio`
- `min_per_region`
- `max_per_file`
- `max_per_phase`
- `selection_method`
- `region_distance_metric`
- `region_merge_threshold`
- `region_split_threshold`
- `controller_hard_alarm_threshold`
- `controller_suppress_threshold`
- `review_budget`

## Outputs Expected From Later Instantiation

Later issue27cf should emit:

- selected support row indices;
- `support_train` / `support_val` split manifest;
- support bank schema-compliant sidecar;
- exact source hashes;
- taxonomy and region assignment audit;
- budget and disjointness audit;
- role access audit.

