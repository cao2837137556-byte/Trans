# Arbitration Design Only

Issue14 remains scientifically well-motivated, but this pass is design-only because GDA-minimal per-sample scores are missing.

The intended comparison after score recovery is:

1. `base_only`
2. `gda_only`
3. `OR_policy`
4. `AND_policy`
5. `mode_gated_arbitration`

Primary evaluation should report high-priority alert rate and review burden separately:

- `attack_high_detection`
- `attack_review_rate`
- `attack_total_captured`
- `OOD_high_alarm`
- `OOD_review_rate`
- `OOD_total_burden`

Review samples must not be counted as confirmed detections. They preserve base-only evidence for analyst review.
