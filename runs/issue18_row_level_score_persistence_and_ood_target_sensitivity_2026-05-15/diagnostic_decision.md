# Diagnostic Decision

Selected diagnosis: `D4_support_method_specific_partial`.

Evidence:

- max 1% to 2% detection gain on holdout_bin_2: 0.008902
- max holdout_bin_2 2% detection mean: 0.335312
- max attack q75 margin at 1%: 5.036900
- kcenter median-margin gain over random at 1%: 10.777396

Interpretation: K-center materially improves attack margins versus random support, but the 2% diagnostic target still leaves detection low; support acquisition is a partial repair, not a solution to the underlying representation/score bottleneck.

This is a diagnostic classification, not a new method result.
