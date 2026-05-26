# Claim Update After Issue27b

## Allowed now

- LOW-GUARD can be discussed as a guarded few-shot adaptation protocol only if bounded by the evaluated lightweight heads.
- Current evidence supports LOW-GUARD-LR as the strongest feasible instance; broader protocol transfer is limited.
- Low-alert feasibility depends on support-based attack alignment and benign-OOD threshold guarding.
- The issue27b matrix did not use final eval for model selection.

## Still not allowed

- LOW-GUARD works for all semi-supervised anomaly detectors.
- LR is universally optimal.
- DevNet / DeepSAD are defeated in general.
- Temporal generalization is proven.
- Cross-dataset generalization is proven.
- Deployment robustness is proven by this issue.
- Final eval was used for model selection.

## Needs issue27c

- Any LOW-GUARD++ replacement claim needs a formal validation run.
- Deployment robustness claims need shot, support-noise, OOD-contamination, and update simulations.
