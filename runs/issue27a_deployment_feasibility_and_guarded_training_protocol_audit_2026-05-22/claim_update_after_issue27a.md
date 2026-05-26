# Claim Update After Issue27a

## Allowed

- LOW-GUARD is better framed as a guarded few-shot adaptation protocol rather than a standalone LR detector.
- The minimal LR head is a deployable instantiation of the protocol.
- The deployment setting assumes a small number of high-purity attack supports and trusted benign-OOD guard samples.
- Fully autonomous online self-training is outside the current scope.
- Deployment claims require support-noise, label-budget, OOD-contamination, label-delay, and update-simulation experiments.

## Not Allowed

- LOW-GUARD is fully deployable in all SOCs.
- 32 attack supports are always available.
- OOD benign labels are always clean.
- The method supports autonomous self-training.
- Temporal generalization is proven.
- Cross-dataset generalization is proven.
- LR is universally optimal.

## Recommended Wording

Use `LOW-GUARD-LR` for the current minimal instance and `LOW-GUARD protocol` for the broader contribution. Keep deployment claims conditional on trusted support/guard provenance and offline gated updates.
