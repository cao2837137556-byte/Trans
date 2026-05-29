# DeepSADStyle_Lite Negative Controls

- label_permutation_pseudo_support detection_mean: `0.8867430250842896`.
- support_removed detection_mean: `0.886858043384216`.
- ood_benign_support detection_mean: `0.8867783889197893`.
- random_gaussian_features detection_mean: `0.009764881994657658`.

Interpretation:

The random Gaussian feature control collapses if its detection is near the OOD target, which checks that the scoring code is not label-driven.
If support removal or benign pseudo-support remains strong, the candidate is not yet proven to be few-shot support-driven; it may be a strong
normal-center detector under this split. That is a claim-boundary risk, not an automatic implementation failure.
