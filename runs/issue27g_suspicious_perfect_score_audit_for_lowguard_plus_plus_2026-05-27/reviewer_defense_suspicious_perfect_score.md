# Reviewer Defense: Suspicious Perfect Score

## Q1: Was final eval used to pick the HistGB config?

No. The issue27g audit rechecked the config-freeze table and by-seed flags; final eval was report-only.

## Q2: Could attack support overlap attack eval?

Index-level support/eval overlap was zero in the audited locked bins. Feature-near-duplicate checks also did not find exact support/eval duplicates.

## Q3: Could original100 contain label-like or split-like features?

The audit screens low-cardinality near-perfect single-feature separators. Any flagged feature must be treated as a leakage risk; absent flags, the result is still bounded to this representation and requires careful wording.

The audit also found high-cardinality near-perfect separator features. These are not enough to invalidate the result by themselves because KitNET traffic-stat features can genuinely separate Mirai-like activity from benign OOD, but they should trigger a feature-provenance appendix before using the result as a major claim.

## Q4: Why trust a 1.0 result?

Only if negative controls collapse and scratch recompute matches. Issue27g therefore treats negative controls and scratch recomputation as the main gate, not the pretty aggregate score.

## Q5: Does this prove external or temporal generalization?

No. It only audits the locked within-dataset formal result for artifact/leakage concerns.
