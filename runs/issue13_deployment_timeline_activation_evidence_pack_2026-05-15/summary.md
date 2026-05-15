# Issue13 Deployment Timeline Activation Evidence Pack Summary

## 1. Purpose

This pack organizes existing evidence into a deployment timeline and activation rule. It does not train any model, rerun experiments, modify prior results, or edit the manuscript.

## 2. Timeline status

The timeline was generated successfully from existing CSV/JSON/MD assets. Key phases are:

- Phase 0: ordinary cold-start normal-vs-attack sanity.
- Phase 1: low-OOD working-point collapse before adaptation.
- Phase 2: scalar score-level adaptation attempts.
- Phase 3: few-shot minimal target-alignment adapter.
- Phase 4: guarded deployment adaptation.
- Phase 5: base-detector representation integration check.

## 3. Current stable method

Current stable method: original100 fixed guard LR 32-shot held-out seeds, detection mean 0.9923, OOD alarm mean/max 0.0044/0.0083, feasible 1.0000.

For main-paper framing, this should be called `GDA-minimal` only in the limited sense of original100 representation + fixed OOD-benign guard + few-shot LR adapter. It is not full neural GDA.

## 4. Activation rule

GDA-minimal activates after:

1. base detector deployment,
2. observed benign OOD/environment shift,
3. low-OOD working-point degradation,
4. available high-purity confirmed attack supports,
5. available ID/OOD benign calibration/validation data,
6. passed support and threshold provenance checks.

The base detector continues running after activation; it is not replaced.

## 5. Missing baselines

See `missing_baseline_report.csv`. Missing rows are not fabricated.

## 6. Next step

Recommended next step: `issue14_arbitration_matrix_experiment_2026-05-15`, comparing base-only, GDA-only, OR, AND, and mode-gated arbitration by attack detection, OOD alarm, and review volume.

## 7. Safety

- Manuscript modified: False.
- Mainline docs modified: False.
- Existing experimental numbers modified: False.
- New model training: False.
- Full GDA claim introduced: False.
