# Recommended E4 Plan

## Scope Constraint

This inventory does not start E4. It only decides whether a clean same-protocol second-environment or cross-capture validation is worth opening. No model was trained, no metric was recomputed, no threshold was changed, and the paper draft was not modified.

## Route A: If E4 Is Considered Feasible

### A1. Cleanest available option: existing paired hard-holdout as E4-lite

The only currently clean same-protocol candidate is not a new external dataset. It is the already completed v7.4 paired hard-holdout package:

- source: `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-frontend-f2\runs\frontend_f2_v7_4_paired_holdout_fairness_2026-04-22\`
- compared representations: `original100` and `source_rich`
- fixed conditions: same holdout specs, same budgets, same seeds, same threshold rules
- leakage boundary: final OOD eval is not used for threshold selection

Recommended use:

- Treat it as completed cross-holdout robustness evidence.
- Use the reverse-chronology case as the representative source_rich hard-holdout result.
- Keep `holdout_bin_2` as supplementary or appendix-leaning evidence because alarm is near-target rather than uniformly strict.
- Do not present it as independent second-environment validation.

Expected paper role:

- Section on source_rich hard-holdout robustness and auditability.
- Appendix paired holdout table.

### A2. Conditional independent second-environment route

No independent local environment currently meets the clean E4 bar. If the project still wants to open a formal independent E4 later, the minimum prerequisite is a protocol precheck before any training:

1. Confirm dataset semantics and label definitions.
2. Define ID benign, OOD benign, and high-purity attack roles.
3. Lock split sizes for ID train/validation/calibration/eval, OOD train/validation/final eval, attack train pool/validation/final eval.
4. Prove support positives are disjoint from attack validation and final attack evaluation.
5. Prove final OOD eval and attack eval are excluded from threshold selection.
6. Decide whether the representation is truly current `original100` / `source_rich` or a different tabular surrogate.
7. Only then run the frozen few-shot protocol and regenerate E2/E3-style packaging.

This conditional route should not be started from BoT-IoT or TON-IoT immediately. BoT-IoT is blocked by benign support. TON-IoT requires a new representation/loader bridge and remains scientifically risky.

## Route B: If E4 Is Not Feasible

The recommended decision from this inventory is Route B.

Why not force E4 now:

- BoT-IoT has a documented formal split-gate blocker: too few benign rows for the current ID/OOD support requirements.
- TON-IoT has local data and old score caches, but it is not aligned to the frozen original100/source_rich few-shot protocol.
- No clean standalone UNSW/CIC/IoT-23 external package was found.
- The clean cross-holdout evidence already exists as v7.4 and should not be rerun as a pretend second environment.

Recommended next step:

- Do not open a new second-environment E4 run.
- Move to E5 label-budget / label-purity sensitivity if more A-area robustness evidence is needed.
- Keep second-environment validation as an external-validity limitation and future-work item unless a clean data manifest is provided.

How to write this without overclaim:

- The current paper can say that the method is validated on the primary evaluation split with seed stability, protocol provenance, deployment-cost evidence, and paired hard-holdout analysis.
- It should not claim that independent second-environment validation has been completed.
- BoT-IoT / TON-IoT should remain limitation / feasibility-boundary evidence rather than positive support.
