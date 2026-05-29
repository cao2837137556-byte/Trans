# issue27r Semantic Validity Decision

primary_verdict = `attack_benign_artifact_risk`

Stage verdicts:

- ID/OOD drift: `ood_shift_too_artificial_or_row_order_bound`
- OOD benign purity: `ood_benign_purity_supported`
- OOD deployment semantics: `ood_deployment_semantics_weak`
- attack/benign semantics: `attack_benign_artifact_risk`
- low-OOD-alert problem validity: `low_ood_alert_problem_artifact_risk`
- feature schema: `anonymous_clean115_feature_semantics_too_weak_for_main_claim`

Decision:

Issue27p model rankings should be treated as diagnostic only, not as main-paper method evidence. The current full Mirai anonymous_clean115 benchmark has useful engineering structure, but its semantic foundation is not strong enough for main claims because the split is row-order based, attack rows are a contiguous suffix, feature semantics are anonymous, and timestamp/capture/source metadata are missing.

The model line should pause. Do not promote DeepSADStyle_Lite, do not call LOW-GUARD++ failed, and do not start LOW-GUARD++ repair until a semantic split/provenance path is established.
