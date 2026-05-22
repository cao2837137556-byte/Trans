# Paper Table Plan

## Table 1: Baseline Categories and Supervision Budget

Purpose:

- Make fairness explicit before showing results.

Columns:

- method category.
- method name.
- feature input.
- attack support budget.
- OOD validation usage.
- threshold rule.
- final eval isolation.

Section:

- Experimental setup.

## Table 2: Locked-Bin Strong Baseline Comparison

Purpose:

- Main strong baseline table.

Rows:

- required baselines and main method.

Columns:

- locked mean detection.
- locked min detection.
- locked OOD max.
- feasibility rate.
- ROC-AUC / PR-AUC.
- low-FPR metric.

Section:

- Main experiments.

## Table 3: Component Ablation

Purpose:

- Show source_rich top64, OOD guard, and kcenter support contributions.

Rows:

- original100.
- top32.
- top64.
- no_guard.
- random32.

Section:

- Ablation study.

## Table 4: Low-FPR / OOD-Budget Performance

Purpose:

- Align results with the low-alert problem definition.

Columns:

- TPR@FPR<=1%.
- pAUC low-FPR.
- final OOD high alarm.
- feasible flag.

Section:

- Deployment-oriented evaluation.

## Appendix Table: Method-Native Input Variants

Purpose:

- Report optional full_source_rich, LOF, RoSAS-like, and design-only variants without overloading the main table.
