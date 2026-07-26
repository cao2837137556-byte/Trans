# Controlled Strong-Baseline Comparison (DRAFT Preregistration)

Date: 2026-07-26
Status: **DRAFT — not yet binding.** This becomes a formal preregistration
only after the CKBV seed-27 result is recorded and the user approves the
final baseline list. Nothing here authorizes any HPC submission now; it
exists so the comparison can enter the same submission window as seeds
37/47 without a serial design delay.

## Purpose

The primary reviewer risk on record is that the evidence-layered controller
is compressed to "LR plus heuristic arbitration." The defense is a
controlled comparison against mature published methods under the identical
frozen protocol, showing that (a) single-surface methods reproduce the
enumerated infeasibility and (b) the asymmetric evidence composition is not
replaceable by standard few-shot anomaly detection, drift rejection, or
cost-sensitive tuning.

## Candidate baselines (official implementations only, vendored offline)

1. Transcendent (Barbero et al., IEEE S&P 2022) — conformal evaluator
   (cred/conf p-values) as a reject-option layer over the frozen C1 score.
   Closest published relative of the fail-closed principle.
2. CADE (Yang et al., USENIX Security 2021) — contrastive autoencoder drift
   detector on the mature 115D frontend; its OOD score plays the same role
   as the normality-suppression branch.
3. DeepSAD (Ruff et al., ICLR 2020) — semi-supervised anomaly detection
   using the 385 support attacks plus legal benign fit rows.
4. DevNet (Pang et al., KDD 2019) — deviation network under the same
   few-labeled-anomaly budget.
5. Cost-sensitive LR and gradient-boosted trees — the "simple fix" a
   reviewer will demand; class-weight sweep selected on legal select only.
6. Kitsune/AfterImage RMSE — the unsupervised anchor already in the
   lineage, reported at the same operating points.

Vendoring follows the TabM/MiniRocket precedent: pinned upstream commit,
license and provenance files, no network access on the cluster, bundle
dependency-closure checks unchanged.

## Frozen shared protocol (identical for every baseline)

- Same fit/select/report role assignments; held/report/sealed sources enter
  nothing (no fit, preprocessing, threshold, calibration, model selection).
- Same support budget: exactly the 385 support-train and 127/69-lineage
  support-val rows; no baseline may consume more labeled attack rows.
- Thresholds selected only on legal select data at matched alert budgets;
  no report-derived tuning of any kind; review=0.
- Seeds 27/37/47 with the same aggregation rule as the main system (the
  aggregation rule must be fixed before seeds 37/47 run anywhere).
- Each baseline uses its natural published input representation, recorded
  explicitly (C1-score space for Transcendent; 115D for CADE; the frozen
  feature spaces for DeepSAD/DevNet/cost-sensitive), so no baseline is
  handicapped by a representation it was not designed for.

## Metrics (identical report set)

- Per-source attack recall at fixed alert budgets 0.1%, 0.5%, 1%, 5%.
- Hard false-alarm rate on each of the four held benign-OOD families,
  with the at-least-5pp / at-most-90% framing used by the main gates.
- Per-family attack recall including the future-query slice.
- Cluster bootstrap confidence intervals (resampled by source and
  time-block, never by row) and cross-seed mean and standard deviation.

## Explicitly out of scope

No new evidence branches, no threshold changes to the main system, no
report-family tuning, no per-family experts. A baseline failing to run
under the frozen protocol is recorded as such, not silently dropped.

## Open items before this draft can be preregistered

1. CKBV seed-27 outcome and its diagnostic readout (per-mechanism
   separation, rescue-branch OOD trigger rate) may adjust which ablations
   accompany the baselines.
2. User approval of the final baseline list and of the seed-aggregation
   rule.
3. Vendor-closure builds and local contract tests for each pinned upstream
   implementation.
