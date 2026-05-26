# Reviewer Defense: Protocol Transfer

## Q1: Is this just Logistic Regression?

issue27b tests that question directly by wrapping LR, DevNet-like MLP, HistGB, DeepSAD-like center, Prototype/metric LR, and optional RFF Logistic in the same P0/P1/P2/P3 guarded protocol matrix. The answer is bounded: the protocol framing is useful, but the LR instance remains the reference unless a head dominates it under the low-alert constraint.

## Q2: Did you use final eval to pick heads?

No. Config selection uses support validation and OOD validation only. Final OOD eval and attack eval are report-only.

## Q3: Why not use a bigger neural adapter?

The task is low-alert few-shot deployment adaptation. Large neural sweeps would reopen model-search risk and weaken the claim boundary. This issue uses only pre-registered lightweight heads.

## Q4: What counts as LOW-GUARD++?

A non-LR full LOW-GUARD head must exceed LOW-GUARD-LR mean detection, match or exceed its minimum detection, keep OOD max <= 1%, and preserve feasibility rate. Result: `nonlinear_detection_gain_not_low_alert_feasible`.

## Q5: Why are high-detection but OOD-over-budget models not enough?

The paper problem is low-alert IDS under benign-OOD drift. A head that raises detection while exceeding 1% OOD alarm is not a deployable low-alert instance.

## Q6: Does this prove temporal or external generalization?

No. issue27b reuses the locked within-dataset bins; temporal and external generalization remain separate evidence gaps.

## Q7: What should happen next?

`issue27c_deployment_robustness_simulation_for_lowguard_lr`. If no LOW-GUARD++ candidate dominates, prioritize deployment robustness simulation rather than expanding the adapter space.
