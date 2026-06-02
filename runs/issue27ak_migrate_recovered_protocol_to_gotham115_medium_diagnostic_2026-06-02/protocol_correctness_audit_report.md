# Protocol Correctness Audit

- audit_pass: `True`.
- forbidden_role_access_blocked: `False`.
- support rule: recovered `kcenter32` with budget `32` from preregistered attack_support role.
- Selector scaler is fit only on attack_support features.
- Final OOD benign eval and attack eval are report-only and never used for fit/threshold/selection.
- If audit failed, diagnostic execution is not claim-usable.
