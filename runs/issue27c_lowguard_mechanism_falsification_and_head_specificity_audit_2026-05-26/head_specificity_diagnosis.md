# Head Specificity Diagnosis

The non-LR heads do not show the same clean P0-to-P2/P3 recovery pattern as LR. DevNet-like is the closest: full LOW-GUARD detection remains high, but OOD max is `0.010100`, just over the official 1% budget. HistGB responds in detection but has a weak locked minimum and OOD max `0.013900`. DeepSAD-like remains collapsed under the proxy objective.

Conclusion:
- LOW-GUARD cannot currently be claimed as head-agnostic.
- The evidence supports LOW-GUARD-LR as a stable instance.
- Non-LR failures should be described as bounded proxy-head evidence, not general defeats of DevNet, Deep SAD, or nonlinear adapters.
