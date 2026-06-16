# Unused Candidate Policy

## Decision

Unselected development attack candidates are not assigned any secondary experimental identity in issue27ce.

```text
candidate_reuse_status = pending_forbidden_until_explicit_issue
```

## Rationale

Candidate reuse can be scientifically useful, but it can also blur the boundary between:

- support candidate pool;
- support bank;
- development query;
- stress pool;
- active-labeling pool;
- final/report-only evaluation.

Because the current issue freezes protocol boundaries, not data reuse, unused candidates stay inert until a later explicit issue defines a legal role.

## Allowed Future Identities

A later issue may explicitly assign unused candidates to one of:

- `coverage_audit_pool`;
- `active_label_pool`;
- `predeclared_dev_query`;
- `tail_stress_pool`.

No such assignment is made here.

## Forbidden Until Explicit Issue

- silent training use;
- silent validation use;
- threshold selection use;
- controller tuning use;
- final-eval replacement use.

