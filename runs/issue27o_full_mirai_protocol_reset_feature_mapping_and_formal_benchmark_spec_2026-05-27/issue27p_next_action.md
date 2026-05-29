# issue27p Next Action

Recommended:

`issue27p_full_mirai_anonymous_clean115_formal_benchmark_execution_2026-05-27`

Scope:

- Execute the formal benchmark on `anonymous_clean115_all`.
- Rerun LOW-GUARD++ HistGB, LOW-GUARD-LR, LR variants, HistGB shallow, Isolation Forest, OC-SVM, DevNet-style, DeepSAD-style, random support, and ablations.
- Do not report restored115/common100 semantics unless mapping is recovered before execution.

Parallel optional preparation:

`issue27p_feature_mapping_recovery_for_restored115_common100`

This can upgrade the feature-study branch, but it should not block the anonymous clean115 reset benchmark.
