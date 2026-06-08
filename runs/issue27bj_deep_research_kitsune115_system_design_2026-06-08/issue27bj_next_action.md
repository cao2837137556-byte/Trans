# issue27bj Next Action

Recommended task:

`issue27bj_metric_evidence_shell_controller_smoke_2026-06-08`

## One-line decision

下一步最值得做的不是继续调 threshold / shared HistGB / OOD gate，而是做一个小而硬的 `metric evidence + prototype shell + bounded controller` smoke，因为 issue27bh/issue27bi 已经说明当前 blocker 是 attack evidence 的 support-query 泛化，而不是单纯 OOD gate 误杀。

## Task Position

- medium diagnostic only;
- not formal benchmark;
- not full/larger run;
- not frontend change;
- not split change;
- not OOD-gate repair yet.

## Inputs

- `issue27af` Gotham Kitsune115 medium asset certificate;
- `issue27ba` disjoint OOD stress pool;
- `issue27bh` failure anatomy;
- `issue27bi` calibrated two-head / metric diagnostic outputs.

## Stages

### Stage 0: role and artifact audit

- Verify hashes and alignment.
- Confirm final/report-only roles are sealed.
- Confirm no support pool or split change.

### Stage 1: legal dev metric training contract

Train only on legal dev roles:

- ID fit/calib;
- OOD train/val;
- OOD stress train/val;
- medium support train/val/pseudo;
- active-heavy support train/val/pseudo.

Never use:

- final OOD;
- medium attack eval report-only;
- dev-heavy query report-only;
- attack eval report-only.

### Stage 2: lightweight embedding candidates

Candidate models:

1. linear metric projection 115D -> 16D;
2. small MLP 115D -> 16D with center/triplet objective;
3. teacher-guided metric student using two-head soft region evidence.

Do not introduce a large model.

### Stage 3: prototype shell

Build in embedding space:

- ID shell;
- OOD/stress shell;
- medium attack shell;
- heavy attack shell;
- unknown/far-all band.

### Stage 4: bounded controller

Dev-only frozen controller:

```text
low attack evidence -> no_alarm
strong attack core and not OOD dominant -> hard_alarm
weak attack and OOD dominant -> suppress
attack/OOD conflict -> bounded_review
far from all regions -> unknown_buffer
```

### Stage 5: report-only replay

After selecting rules on dev-only roles, replay report-only roles once:

- final OOD benign;
- medium attack eval;
- dev-heavy query.

Report only. Do not tune.

## Required Outputs

- `metric_training_contract.md`
- `metric_embedding_audit.csv`
- `triplet_or_pair_sampling_audit.csv`
- `prototype_shell_audit.csv`
- `controller_rule_grid_dev_only.csv`
- `controller_replay_report_only.csv`
- `support_query_gap_after_metric.csv`
- `review_budget_audit.csv`
- `role_access_audit.csv`
- `issue27bj_decision.md`

## Go / No-Go

Go to OOD-gate repair diagnostic only if:

- legal dev attack hard-min >= `0.93`;
- review rate <= `0.05`;
- no forbidden role access;
- report-only replay does not reveal catastrophic task-boundary mismatch.

No-Go if:

- legal dev attack hard-min remains < `0.80`;
- support-query gap does not shrink;
- metric embedding only improves report-only but not legal dev pseudo/query;
- review rate becomes the main mechanism.

## Primary Verdict Options

- `metric_shell_attack_recovered_ready_for_ood_gate_repair_diagnostic`
- `metric_shell_partial_attack_recovery_needs_refinement`
- `metric_shell_no_attack_recovery_task_boundary_audit_next`
- `metric_shell_blocked_by_forbidden_role_access`
- `metric_shell_blocked_by_review_cost`
