# Prototype-Aware Gate v0

Draft only. Not applied in issue27av.

1. Compute common-scaled distances to ID, OOD, and attack prototypes.
2. If ID/OOD covered and attack not covered: suppress attack alarm or label as benign drift.
3. If attack covered and ID/OOD not covered: allow attack alarm subject to OOD-safe threshold.
4. If both benign and attack covered: conflict, route to needs_review or require a score-margin rule.
5. If none covered: unknown_uncovered, request more labels or add to OOD stress pool depending on anomaly score and operational context.

Final OOD cannot be used to tune these radii or rules.
