# issue27ckd Validation Report

Status: `PASS`

- V0 exactly reproduced issue27ck S3 registry: `True`.
- All prototypes were selected from support-train only.
- Support-val and OOD-val selected the candidate variant.
- OOD-stress and certified dev query were read only after selection.
- No support reselection, candidate reuse, model training, controller tuning, or sealed-final access occurred.
- Read-only temporal/query diagnostic status: `BLOCKED_FOR_CONTROLLER_FREEZE`.
- Temporal/query caveat labels: `Mirai GRE Flooding`, `Mirai UDP Flooding`.
- Deterministic rerun verification: `PASS`; qualification, registry, selection,
  OOD-stress, certified-query, query-confusion, and result hashes matched.
