# Activation Rule Draft

GDA-minimal is not active as the primary alerting model during cold start. It is activated only when:

1. A base detector such as dA or Transformer is already deployed.
2. Benign OOD traffic or environment shift is observed.
3. The base detector shows low-OOD working-point degradation under the target alert budget.
4. A small set of high-purity confirmed attack samples becomes available.
5. ID benign and OOD benign calibration/validation samples are available for guarded thresholding.
6. Support provenance and threshold provenance checks pass.

After activation:

- The base detector continues running as a cold-start and generic anomaly monitor.
- GDA-minimal controls attack-oriented high-priority alerts under the low-OOD alarm constraint.
- Base-only high samples are routed to review, not suppressed.
- GDA-only high samples become GDA-driven high-priority alerts.
- Both-high samples become the strongest high-priority alerts.
- Both-low samples remain low-priority/background.

This is a proposed deployment rule, not a completed arbitration experiment.
