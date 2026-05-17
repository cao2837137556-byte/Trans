# Problem Definition Candidates

## Problem A: Conservative

Problem A frames the paper as a measurement/protocol paper: ordinary IDS benchmark metrics do not reliably reflect low-alert deployment under benign-OOD drift, and fixed-guard minimal adaptation is a strong baseline.

Why not choose A as the main route:

- It is safe but may look method-light.
- It risks becoming a protocol paper with a simple baseline.
- It does not fully use the current system evidence around activation and arbitration.

## Problem B: Balanced

Problem B frames the paper as a hybrid contribution:

**Low-alert intrusion detection under benign-OOD drift, with deployment-stage guarded few-shot adaptation and bounded coexistence with base detectors.**

Why choose B:

- It matches the strongest current evidence.
- It makes LOW-GUARD-minimal a system/mechanism contribution rather than an LR replacement claim.
- It can absorb negative score-fusion, unstable source_rich, and bounded review as honest system boundaries.
- It identifies clear missing evidence: harder holdout and few-shot anomaly baselines.

Recommended status: **current main route**.

## Problem C: Ambitious

Problem C frames the paper as a universal detector-agnostic adaptive IDS framework.

Why not choose C now:

- Detector-agnostic evidence is not complete.
- Transformer hidden is feasible but not a stable improvement source.
- dA latent / multi-detector representation success is missing.
- It would require second environment, adapter upgrades, and broader baselines before the claim is safe.

Problem C can remain a future direction after Problem B is defensible.
