# LR vs Framework Positioning

## Is LR the core contribution?

No. LR is the current minimal deployable instantiation. The core contribution should be framed as a low-alert guarded few-shot adaptation protocol: OOD-safe representation selection, confirmed attack support coreset, OOD benign guard, and validation-calibrated thresholding.

## Should LOW-GUARD be written as framework/protocol?

Yes. The paper should present LOW-GUARD as a protocol for adapting an IDS under benign-OOD drift and low-alert constraints. The LR head is attractive because it is transparent, cheap, stable, and easy to audit.

## If Guarded DevNet-like or Guarded HistGB becomes stronger, does the main story survive?

Yes, if the protocol framing is used. A stronger guarded adapter would become another LOW-GUARD instance. The current claim should not be that LR is universally optimal; it should be that the guarded adaptation protocol is effective and the LR instance is a strong minimal baseline.

## How to write LR as a minimal deployable instantiation?

Write it as: `LOW-GUARD-LR`, a lightweight linear adapter trained from confirmed attack supports and benign guard samples, with threshold selected only from ID calibration + OOD validation.

## How to avoid the attack "it is just Logistic Regression"?

- Emphasize the deployment problem: low-alert IDS under benign-OOD drift.
- Emphasize the protocol: support provenance, OOD guard, final eval exclusion, low-alert threshold.
- Show strong baselines: DevNet-like and random32 approach detection but exceed the 1% OOD alarm budget.
- Keep LR's role honest: simple, auditable, and not claimed as universal optimum.

## External baseline vs guarded baseline vs LOW-GUARD instance

- External baseline: method family tested under fair input/label budget rules, e.g. DevNet-like or DeepSAD-like.
- Guarded baseline: a baseline wrapped with the same ID/OOD validation threshold protocol.
- LOW-GUARD instance: a method that follows the full protocol, including support provenance, benign-OOD guard, low-alert validation threshold, and deployment update constraints.
