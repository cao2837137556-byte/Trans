# Issue27g Next Action

## Recommendation

`issue27g_deployment_robustness_for_lowguard_lr_and_lowguard_plus_plus`

## Reason

issue27f primary verdict is `lowguard_plus_plus_formal_validated`.

If LOW-GUARD++ is formal validated, the next useful step is deployment robustness for both LOW-GUARD-LR and LOW-GUARD++: support-count, support-noise, OOD contamination, label-delay if metadata permits, and shadow-mode workload. If it is not validated, diagnose the specific instability rather than expanding the model zoo.

## Slurm

Not required for similar HistGB/LR robustness experiments unless the matrix expands substantially.
