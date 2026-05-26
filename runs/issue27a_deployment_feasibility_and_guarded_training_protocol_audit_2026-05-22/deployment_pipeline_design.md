# Deployment Pipeline Design
## Stage 0: cold-start base detector

- input: existing dA / base IDS / prior anomaly score
- output: initial alerts and candidate incidents
- who verifies it: SOC owner + model owner
- leakage risk: base detector scores must not use final eval
- contamination risk: high false positive drift
- rollback condition: alarm explosion or known incident leakage
- how to express it in paper: Base detector supplies candidates; LOW-GUARD is not a cold-start replacement.

## Stage 1: high-purity support collection

- input: confirmed incidents, trusted rules, red-team/honeypot cases
- output: small support pool with provenance
- who verifies it: analyst or incident response lead
- leakage risk: support rows cannot overlap final attack eval
- contamination risk: mislabeled supports or biased attack family
- rollback condition: support provenance fails or support source not confirmed
- how to express it in paper: Assume small high-purity supports; do not claim labels are free.

## Stage 2: benign-OOD guard collection

- input: recent trusted normal traffic and confirmed false positives
- output: OOD benign train/validation guard pool
- who verifies it: SOC analyst + data owner
- leakage risk: OOD guard cannot include final OOD eval
- contamination risk: attack contamination inside benign guard
- rollback condition: OOD validation alarm unstable or contamination detected
- how to express it in paper: OOD guard is trusted/validated benign drift, not arbitrary production traffic.

## Stage 3: offline LOW-GUARD training

- input: frozen representation, support pool, ID/OOD benign train
- output: minimal guarded adapter instance
- who verifies it: model owner
- leakage risk: no final eval for representation/support/model choice
- contamination risk: training on unresolved alerts creates feedback
- rollback condition: provenance or contamination audit fails
- how to express it in paper: Training is offline and gated, not autonomous self-training.

## Stage 4: validation-only thresholding

- input: ID calibration + OOD validation scores
- output: threshold under 1% OOD validation alarm
- who verifies it: model owner + reviewer
- leakage risk: final OOD/attack eval cannot set threshold
- contamination risk: OOD validation labels may be noisy
- rollback condition: OOD validation exceeds budget or labels untrusted
- how to express it in paper: Threshold is validation-calibrated under low-alert budget.

## Stage 5: shadow mode

- input: frozen trained model and threshold
- output: score/alarm simulation without production alerts
- who verifies it: SOC operations
- leakage risk: shadow labels cannot be used to tune final threshold in the same evaluation
- contamination risk: operator feedback may bias later labels
- rollback condition: shadow workload exceeds budget
- how to express it in paper: Shadow mode estimates workload; it is not full deployment proof.

## Stage 6: canary deployment

- input: shadow-passed model
- output: limited-scope production alerts
- who verifies it: SOC lead + model owner
- leakage risk: canary results should be logged separately
- contamination risk: localized drift or user impact
- rollback condition: alarm rate above 1% target, analyst overload, confirmed false-positive burst
- how to express it in paper: Canary is a cautious deployment gate.

## Stage 7: rollback trigger

- input: live/near-live workload and confirmed label drift metrics
- output: rollback or freeze decision
- who verifies it: SOC incident commander
- leakage risk: rollback criteria must be pre-registered
- contamination risk: delayed labels can hide failures
- rollback condition: OOD alarm breach, support contamination, or incident miss audit
- how to express it in paper: LOW-GUARD needs rollback controls.

## Stage 8: periodic update

- input: new confirmed supports and benign guard after quarantine
- output: new offline candidate version
- who verifies it: change advisory / model governance
- leakage risk: do not self-train from predictions
- contamination risk: feedback contamination from previous model alerts
- rollback condition: update fails shadow/canary or provenance audit
- how to express it in paper: Periodic offline updates are plausible but need robustness simulation.
