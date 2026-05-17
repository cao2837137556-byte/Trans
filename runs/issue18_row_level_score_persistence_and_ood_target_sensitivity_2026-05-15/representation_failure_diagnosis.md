# Representation Failure Diagnosis

Diagnostic decision: `D4_support_method_specific_partial`.

Maximum holdout_bin_2 attack q75 margin at 1%: 5.036900.

K-center maximum median-margin gain over random at 1%: 10.777396.

Interpretation: K-center materially improves attack margins versus random support, but the 2% diagnostic target still leaves detection low; support acquisition is a partial repair, not a solution to the underlying representation/score bottleneck.

If 2% target does not substantially rescue detection and attack margins remain mostly below threshold, the bottleneck is score/representation-side rather than merely threshold tightness.
