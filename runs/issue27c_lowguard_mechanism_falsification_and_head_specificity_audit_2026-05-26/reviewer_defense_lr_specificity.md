# Reviewer Defense: LR Specificity

## Q1: Is LOW-GUARD just an LR trick?

Current evidence says LOW-GUARD-LR is the strongest feasible instance. The broader framework claim must be bounded because non-LR transfer was not stable under the locked low-alert protocol.

## Q2: Why did LR recover but threshold-only LR collapse?

Threshold-only LR moves the decision threshold high enough to suppress benign-OOD alarms, but this also suppresses attack detection. OOD-guarded LR training changes the score geometry so the same low-alert budget can retain attack detection.

## Q3: Did non-LR heads receive the OOD guard?

Yes. P2/P3 variants include OOD_train guard for non-LR heads. The issue is not that they were unguarded; it is that their score tails were less compatible with the strict low-alert threshold.

## Q4: Are DevNet and Deep SAD defeated?

No. The implemented heads are lightweight proxies. The correct claim is that these proxy heads did not produce a stronger low-alert instance under this protocol.

## Q5: Should the paper call LOW-GUARD a framework?

Only cautiously. It can be described as a guarded adaptation protocol, but current positive performance evidence should center on LOW-GUARD-LR.

## Q6: What is the next falsification?

Run `issue27d_bounded_representation_and_objective_falsification_for_lowguard_lr_specificity` before returning to deployment robustness, because direct deployment robustness would be a premature close if the mechanism is still head-specific.
