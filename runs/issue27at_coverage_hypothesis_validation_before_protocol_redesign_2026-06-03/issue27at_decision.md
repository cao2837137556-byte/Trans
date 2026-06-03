# Issue27at Decision

primary_verdict = `coverage_hypothesis_partially_supported_needs_more_attack_pool`

Coverage is evaluated only as a failure-explanation hypothesis. The primary support scheme is the issue27as val-side selected kcenter128 support split; old kcenter32 and file_balanced_v2 are static coverage comparisons only.

## Key Boundary

- medium coverage-sufficient detection: `0.9965100103025748`
- medium coverage-insufficient detection: `0.9525191221979217`
- new heldout coverage-sufficient fraction: `0.13463333333333333`
- new heldout coverage-sufficient detection: `0.9983963344788087`
- new heldout coverage-insufficient detection: `0.3917720921620409`

This supports the coverage/support-query gap hypothesis only partially: the covered new-heldout subset is detected, but most new-heldout rows are outside the support-val-derived covered region and some uncovered behavior remains seed-sensitive. Therefore this result is not enough to claim a method improvement or proceed to full benchmark.

Final OOD tail risk from issue27as is not solved by this analysis and remains a separate blocker.
