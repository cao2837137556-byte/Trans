# CKBP source-local one-sided normal calibration preregistration

Date: 2026-07-15
First seed: 27 only

## Scientific question

CKBP asks whether the current blocker is primarily cross-source score scale
rather than absence of transferable normal evidence:

> Can a normal-only model, calibrated with each report source's own label-free
> past, suppress C1 hard false alarms across unseen normal families while
> preserving future and per-family attack recall?

The report-time permission is not new. CKBJ, CKBM, and CKBO already allowed
source-local, label-free, past-only state. The methodological change is how the
history is used:

- previous TGN/TabM routes converted history into features and then used a
  symmetric attack-versus-benign decision boundary;
- CKBP uses history as the current source's calibration population and fits no
  attack-versus-benign verifier;
- only confident normal conformity can suppress a C1 candidate; cold,
  unreliable, or out-of-range adaptation fails closed to C1 hard.

CKBP is a route-selection experiment, not a claim that arbitrary OOD is
distribution-free learnable.

## Frozen inputs and boundaries

- The strict 1M role split is read-only and unchanged.
- The frozen 26-source CKBE T0 manifest and four-source report extensions are
  read-only and unchanged.
- CKBO's separate 31-source benign AfterImage extension is reused without
  changing its 11 fit / 5 select / 15 predictive-report source roles. Its
  manifest SHA-256 remains
  `d45bb5c0359555b45d19b4b5d2c62ad83ae9dfb177654a3f36c4393fd3120c4f`.
- `iotsim-stream-consumer`, `iotsim-hydraulic-system`, and
  `iotsim-cooler-motor` have zero fit, normalization, source-reference,
  threshold, and model-choice use in every protocol.
- Cooler-motor remains sealed and is not scored.
- Report extensions have zero fit/select use.
- Review is fixed to zero.

The formal protocols remain exactly:

1. global attack preservation;
2. strict `iotsim-ip-camera-street`;
3. strict `iotsim-predictive-maintenance`;
4. report-only stream-consumer development canary;
5. report-only hydraulic-system development canary.

No threshold, feature, model, update rule, or route choice uses any report
label. Report labels are opened only after every score and threshold freezes,
for metric strata and go/no-go reporting.

## Mature components and narrow custom mechanism

CKBP reuses:

- the frozen C1 CICFlow-style HistGB attack anchor;
- the audited mature Kitsune/AfterImage115 frontend;
- scikit-learn's `QuantileTransformer`;
- scikit-learn's closed-form `LedoitWolf` shrinkage covariance estimator;
- the standard finite-sample split-conformal empirical rank.

Custom code is limited to source balancing, source-disjoint calibration,
bounded causal adaptation, fail-closed fusion, and contract/output audits.
There is no new dynamic GNN, Transformer, MLP, TabM training, prototype bank,
review route, or feature construction.

## Normal-only score

For every held protocol, the normal model uses only legal benign fit rows after
held-family and permanent-canary exclusion. Attack and report use counts are
exactly zero.

1. Cap each fit source at 600 deterministically ordered rows so a large source
   cannot dominate.
2. Apply `asinh` to raw AfterImage115, then a fit-only normal-output
   `QuantileTransformer`.
3. Fit `LedoitWolf` on the transformed legal normal fit rows.
4. Use log Mahalanobis distance as nonconformity; lower is more normal.
5. Score legal source-disjoint benign-select sources with that exact frozen
   fit-only model and construct the conformal reference from those scores.
6. Separately score every fit source with a model trained without that source
   as a generalization diagnostic; those fold-model scores are not the
   deployed conformal reference.

The reference records each select source, fit source count, fit row count,
nonconformity median/MAD, model hash, and zero attack/report use.

## Source-local causal calibration

For every phase/source pair, state begins empty. Records are processed by
`event_position`, `recorded_index`, then UID.

1. Score the current record before any update.
2. During the first 64 scored records, fail closed to hard and collect a
   label-free provisional robust history.
3. Use at most the previous 256 accepted nonconformity scores.
4. Estimate the source median shift relative to the fit-source reference.
5. Bound the shift to the 10th--90th percentile range observed across legal
   source-disjoint benign-select medians.
6. Convert bounded nonconformity to an empirical conformal normal p-value.
7. If provisional/history dispersion is unreliable, emit attack score 1,
   reject all further state updates, and retain C1 hard.
8. Otherwise reject a current update when its nonconformity exceeds past
   median plus three robust MAD scales.

This does not prove that a stable unseen attack is normal. The primary limits
that unavoidable ambiguity by capping total source shift to the legal
source-disjoint benign-select range; the unbounded candidate exposes the
failure mode as a non-deployable control.

State never crosses fit/select/report phases or sources. It uses no label,
source identity feature, future event, gradient, threshold update, or model
weight update.

The original strict 1M part supplies only its frozen scored target rows to the
calibration history; it does not materialize a new full-stream AfterImage
cache. CKBP therefore reports event-position gap statistics and explicitly
labels the state scope `frozen_scored_target_rows_only`. The auxiliary
AfterImage sequences contain 600 consecutive model-ready rows. Any density
effect is an interpretation caveat, not hidden as equivalent full-history
coverage.

The empirical conformal p-value is used as a mature nonparametric calibration
score. Because the report sequence is adaptive and temporally dependent, CKBP
does **not** claim an unconditional exchangeable conformal coverage guarantee.
A formal sequential/weighted risk guarantee is deferred until R1 shows a real
scientific signal.

## Candidates and controls

1. `M0-C1`: unchanged attack anchor.
2. `M1-GlobalNormalConformal`: same normal-only model and conformal rank but no
   report source adaptation. This isolates the value of source-local history.
3. `M2-CappedSourceConformal`: preregistered primary; bounded source shift,
   robust update guard, cold/unreliable fail-closed behavior.
4. `A1-UnboundedSourceConformal`: deliberate unsafe control. It subtracts the
   entire target-source shift and is marked non-deployable. It tests whether an
   apparent OOD improvement is purchased by learning a stable attack stream as
   normal.
5. `A2-LocalRobustDeviation`: local typicality-only unsafe control, also
   non-deployable. It removes the global normal reference and exposes the risk
   of treating any stable process as benign.

The primary is fixed before report scoring. A control cannot replace it based
on report metrics.

## Attack and gate contract

- All 385 legal `support_train` rows supervise the C1 anchor once in the global
  protocol and have zero normal-calibrator fit use.
- The 69 legal `support_val` rows are gate-only.
- Gate candidates are the exact support-val attack score frontier.
- Eligibility requires overall support-val recall within 0.5 percentage point
  of C1 and every sufficiently represented attack family within 2 points.
- Among eligible thresholds, minimize hard alarms on the five legal,
  source-disjoint auxiliary benign-select sources.
- Report attacks, report normal families, and sealed data contribute zero gate
  candidates.

The final rule is:

```text
C1 below candidate threshold -> non-hard
C1 candidate + calibrated normal evidence above the selected normal gate -> suppress
C1 candidate + cold, unreliable, or insufficient normal evidence -> hard
```

Implementation stores `1 - normal_p` as the one-sided verifier attack score so
the existing exact attack-preserving frontier remains auditable.

## Seed-27 go/no-go

`M2-CappedSourceConformal` is a `GO_SIGNAL` only if all hold:

- overall attack hard recall decreases by no more than 0.5 percentage point;
- every attack family with at least 15 report rows decreases by no more than 2
  percentage points;
- stream hard false alarms are at most 90% and improve over C1 by at least 10
  points;
- hydraulic does not worsen over C1 by more than 2 points;
- both legal development held families reach at most 90% hard alarms and each
  improves by at least 5 points; their macro improves by at least 5 points;
- all 385 support rows are used by C1 and zero enter the normal model;
- every report source is score-before-update with fresh phase/source state;
- no report/permanent/sealed row enters fit, source reference, or selection;
- target alignment is complete and review is zero.

Failure stops this exact calibration route. It does not authorize family-
specific tuning, another seed, or opening cooler-motor. Seeds 37/47 and a
second dataset are allowed only after a real seed-27 signal.

## Required outputs

The result package includes:

- attack preservation and strict held-family summary tables;
- every attack-family recall and worst-family recall;
- C1, global, bounded, unbounded, and local-only candidates;
- source-out-of-fold normal-model audit;
- per-source shift/MAD reference audit;
- per-source cold start, reset, update/rejection, shift clipping, and
  event-position-gap audit;
- candidate threshold frontier;
- 385 support-row and attack-family use audits;
- fit/select/report and permanent/sealed exclusion audits;
- environment, commit, manifests, runtime, MaxRSS/accounting snapshot, and
  partition/job identity;
- one explicit `GO_SIGNAL` or `NO_GO` decision.

## Resources and execution

The previous CKBO formal run used about 4.45 GiB MaxRSS and completed in about
17 minutes. CKBP removes neural training but adds source-out-of-fold
Quantile/LedoitWolf fits. Each independent AMD/Intel copy requests 8 CPUs,
16 GiB, and 4 hours. Outputs, logs, archives, and hashes contain partition and
job ID, so correctness does not depend on cancelling the slower copy.
