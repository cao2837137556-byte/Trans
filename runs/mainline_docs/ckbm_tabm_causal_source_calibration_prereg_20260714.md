# CKBM preregistration: mature TabM verifier plus causal source-relative view

Date: 2026-07-14
Seed: 27 only
Status: frozen before any CKBM report score is produced

## Question

CKBL showed that the legal 207-dimensional C1 process view contains transferable
rank signal, but that one global hard threshold moves badly between sources. CKBM
asks whether a mature supervised tabular verifier, together with a strictly
past-only source-relative view, can lower C1 hard false alarms without sacrificing
attack recall.

This is a result-producing experiment. It is not another frontend observability
probe, environment job, audit-only job, or TGN repair.

## Frozen components

- C1 remains the candidate-generation anchor and is trained/calibrated exactly
  inside each legal protocol.
- The frozen 1M role split, 385 `support_train` rows, 69 legal `support_val`
  rows, CKBE 26-source manifest, CKBI report-only extension, and CKBJ C1
  report-only cache extension are not modified.
- Review is fixed to zero.
- The primary backend is the official Apache-2.0 TabM v0.0.3 implementation at
  upstream commit `a507095893d784c5702059d737ddfbd1299c41dd`.
  The upstream `tabm.py` SHA-256 is
  `fc654af6a16bac53d893a8265c79d7af4ebddcb95ad0d600cc6b6bc6b7317ade`.
- TabM is used without numerical embeddings because the frozen environment does
  not contain `rtdl_num_embeddings`. The official source is vendored unchanged;
  a local compatibility module exposes unavailable embedding class names and
  raises if an embedding is instantiated.
- CatBoost is not a CKBM candidate because it is absent from the frozen runtime
  and installation is forbidden. It must not be imitated with custom code.

## Candidates

1. `M0-C1`: unchanged C1 HistGB candidate baseline.
2. `M1-ExtraTrees-Global`: mature sklearn ExtraTrees verifier on the 207 C1
   features; non-neural strong-backend control.
3. `M2-TabM-Global`: official TabM on globally transformed 207 C1 features.
4. `M3-TabM-CSR`: preregistered primary candidate. It receives the same global
   207 features plus a causal source-relative view and a cold-start/history-count
   feature.
5. `A1-ExtraTrees-CSR`: backend/calibration ablation using the same causal view.

No candidate adds scores. Every non-C1 candidate is a logical verifier:

```text
C1 below its candidate threshold -> non-hard
C1 at/above its candidate threshold and verifier supports attack -> hard attack
C1 at/above its candidate threshold and verifier does not support attack -> suppress
```

## Mature TabM training contract

- Numerical preprocessing follows the official TabM example: a fit-only
  `QuantileTransformer(output_distribution="normal")` with deterministic tiny
  jitter.
- TabM ensemble members are trained independently: cross-entropy is evaluated
  for every member before reduction. At inference, class probabilities are
  averaged across members.
- AdamW uses the official default `lr=0.002`, `weight_decay=0.0003`.
- Fixed epochs are used; `support_val` is not used for early stopping or model
  fitting.
- Every legal support row is visited at least once per epoch. A deterministic
  coverage-first sampler repeats only within smaller attack families until all
  attack families have equal per-epoch occurrence counts; the audit records the
  actual per-row and per-family visits. Occurrence weights divide attack mass
  equally across families and benign mass equally across fit sources, without
  double-counting the repeated small-family rows. All legal benign fit rows are
  visited once per epoch.

## Causal source-relative view

For each source and each phase scope (`fit`, `select`, or `report`) a fresh
running state is created. For the current event:

1. globally transformed features are obtained with fit-only statistics;
2. source-relative residuals are computed from prior events only;
3. the current event is scored;
4. only afterwards is the label-free running state updated.

The state resets for every source and never crosses fit/select/report. Source
identity selects a state object but is never an input feature. Labels, device
family, attack family, role names, future events, and report outcomes never
update the state or the preprocessing. Report inference runs under
`torch.no_grad()` and cannot update weights, thresholds, or preprocessing.
The running state covers the frozen scored target rows; it does not pretend to
have 207-dimensional C1 features for memory-only raw events. Any repeated
source-local target event across fit/select/report is a hard contract failure.

`M2-TabM-Global` is the mechanism-disabled control for this source-relative
view. CKBM will not claim that the causal view helps unless the primary candidate
beats this control on the preregistered hard-decision endpoints while satisfying
attack preservation.

## Isolation

For each strict held family, every source belonging to that family is excluded
from:

- C1 fit and threshold calibration;
- quantile preprocessing and all source-relative fit state;
- ExtraTrees and TabM training;
- family/source balancing;
- support supervision;
- verifier threshold selection.

All current source sidecars are required to remain single-family by source.
Any report-only extension row in fit/select, any incomplete target alignment,
or any nonzero review rate is an immediate failure.

## Threshold selection

Verifier thresholds are selected only from legal `support_val` attacks and
benign select rows. The selection order is:

1. overall attack hard recall no more than 0.5 percentage point below C1;
2. each attack family with at least three support validation rows no more than
   2 percentage points below C1;
3. among eligible thresholds, minimize benign select hard rate.

The threshold search is the exact legal attack-retention frontier: every unique
`support_val` verifier score plus a below-minimum sentinel is evaluated. This
cannot read a report score and cannot miss a feasible preservation gate because
the retained attack set changes only when one of those scores is crossed.

If no verifier threshold satisfies the attack constraints, that candidate is
marked gate-failed. A fallback may be reported diagnostically but cannot be a
GO.

## Formal outputs

The single seed must report:

- overall, support-val, same-file, future, sealed, domotic, combined, per-family,
  and worst-family attack recall with delta from C1;
- stream-consumer, hydraulic-system, IP-camera, and all other held-family hard
  false-alarm metrics;
- role/source/target counts, held exclusions, report-only zero-use proof, 385
  support-row usage, family/source loss weights, preprocessing hashes, causal
  reset/update counts, cold-start fractions, loss curves, environment, commit,
  manifest hashes, wall time, and Slurm MaxRSS;
- clustered confidence intervals by source, falling back to episode only when
  more than one episode exists. Packets are never treated as independent
  bootstrap units.

## GO / NO-GO

`M3-TabM-CSR` is the preregistered decision candidate.

GO requires all of the following:

- overall attack drop versus C1 is at most 0.5 percentage point;
- no major attack-family drop exceeds 2 percentage points;
- stream-consumer hard rate is at most 0.90 and improves by at least 10
  percentage points from C1;
- hydraulic-system does not worsen by more than 2 percentage points;
- report/held isolation, complete alignment, support usage, causal ordering,
  and review=0 all pass.

Stream and hydraulic remain development canaries, not untouched final evidence.
The sealed final family is not used to select this route or any threshold. If
seed 27 is a GO signal, seeds 37/47 may be preregistered separately; otherwise
they are not run.
