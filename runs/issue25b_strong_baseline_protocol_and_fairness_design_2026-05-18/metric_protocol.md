# Metric Protocol

## Primary Metrics

For every method, setting, seed, and seed group:

- ROC-AUC.
- PR-AUC.
- Attack high detection at 1% OOD validation target.
- Final OOD high alarm.
- Feasible flag: final OOD high alarm <= 1%.
- TPR@FPR<=1% or equivalent low-alert detection.
- pAUC in the low-FPR region if implemented.

## Locked Aggregates

For locked bins 5/6/7/8:

- locked mean detection.
- locked min detection.
- locked OOD max.
- feasibility rate.
- mean/std/min/max across bins and seed groups.

## Secondary Metrics

- Train time.
- Inference time.
- Model complexity or parameter count if easy.
- Hyperparameter selection provenance.
- Threshold provenance.
- Support provenance for methods using attack supports.

## Interpretation

A method is not a strong baseline winner unless it improves detection while satisfying the same final OOD <=1% constraint. A method with higher ROC-AUC but worse low-alert detection or OOD overbudget should not be presented as better under the paper's deployment problem.
