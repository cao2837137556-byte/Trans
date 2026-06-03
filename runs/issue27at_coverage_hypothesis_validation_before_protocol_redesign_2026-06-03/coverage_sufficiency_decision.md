# Coverage Sufficiency Decision

primary_verdict = `coverage_hypothesis_partially_supported_needs_more_attack_pool`

- Coverage-sufficient means `covered_close` or `covered_mid` under support-val-derived distance buckets.
- This subset is report-only diagnostic and cannot become a formal eval subset.
- No threshold, support, or model config is selected using attack_eval or new heldout.

## Boundary

- If coverage explains heldout collapse, the next step is a coverage-aware support gate / active labeling design.
- If coverage does not explain it, the next step is feature/task/protocol boundary redesign.
- The issue27as final OOD tail overbudget remains a separate blocker.
