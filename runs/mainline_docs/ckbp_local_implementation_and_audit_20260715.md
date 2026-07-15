# CKBP local implementation and audit

Date: 2026-07-15

## Status

CKBP is implemented locally and is ready for one seed-27 result-producing
dual-partition job after bundle validation. No HPC job has been submitted by
this implementation work, and no performance conclusion exists yet.

The implemented question is narrower than another backend comparison:

- freeze C1 as the high-recall attack anchor;
- fit a normal-only QuantileTransformer + LedoitWolf score on legal benign fit
  sources;
- use leave-one-fit-source-out normal predictions only as a diagnostic;
- build the deployed empirical reference from legal source-disjoint
  benign-select sources scored by the exact frozen fit-only model;
- use report source history as a bounded, label-free, past-only calibration
  population;
- suppress only when one-sided normal evidence is confident;
- fail closed to C1 hard during cold start, unreliable state, or out-of-range
  source shift.

The primary is fixed as `M2-CappedSourceConformal`. Global calibration,
unbounded target adaptation, and local-typicality-only variants are controls.
The latter two are explicitly non-deployable.

## Local contract evidence

`contract-unit` passes and covers:

- finite 115D QuantileTransformer + LedoitWolf fitting;
- four-fold source-out-of-fold normal scoring;
- empirical conformal rank;
- bounded source shift restoring a moderate synthetic normal offset;
- bounded shift retaining a far synthetic attack as hard;
- unbounded adaptation incorrectly normalizing that stable far attack;
- score-before-update;
- source reset;
- future-value changes leaving every earlier score unchanged;
- provisional burn-in that stays hard and cannot grow after an unreliable
  cohort;
- an audited hard bound on the deployable source shift;
- exact attack-preserving gate-frontier selection;
- mixed-output-directory rejection.

The synthetic bounded candidate's post-burn-in mean attack score is about
`0.4975` for the moderate normal offset and `0.9975` for the far attack. The
unbounded control lowers the same far attack to about `0.4975`, which validates
that the unsafe control actually exposes the intended poisoning/adaptation
risk rather than duplicating the primary.

All four shell entry points pass syntax checking. The Python module compiles
under the local Python runtime and all frozen dependency hashes match.

## Real 1M read-only scope audit

The first local scope attempt stopped correctly because the default T0 path is
the HPC path and the local checkout does not contain the frozen proxy files at
that location. It produced no model or metric.

The audit was rerun against the pulled-back CKBE T0 audit directory and passed:

- status: `CKBO_REAL_1M_SCOPE_PASS` (the reused frozen-scope function name);
- support_train fit: `385`;
- legal support_val select: `69`;
- original benign fit after the frozen C1/T0 intersection: `3,413`;
- original benign select: `0`;
- permanent stream/hydraulic/cooler fit-select use after masking: `0`;
- report-extension fit/select retention: `0`;
- missing feature zero fill: `0`;
- raw rows rematerialized: `0`;
- CKBO auxiliary overlap with the strict 1M sources: `0`;
- legal development held families: IP-camera-street and
  predictive-maintenance;
- C1 target manifest SHA-256:
  `74a1699e29b7b1e227f4532ff81f1546a9ba239f2d2d323d390efa5b07437158`.

The local pullback intentionally lacks the 26 large T0 NPZ files and the
report-only T0/C1 extensions, so it cannot run the actual formal metrics. The
formal job rechecks all NPZ targets and extensions before fitting; the local
proxy is accepted only for the membership audit.

## History-density disclosure

CKBP does not repeat CKBJ's hidden sparse-fit/dense-report TGN state mismatch.
It states its scope explicitly:

- strict 1M sources calibrate only over frozen scored target rows, ordered by
  event position;
- CKBO auxiliary sources contain 600 consecutive model-ready AfterImage rows;
- the algorithm uses a fixed previous-record count, not elapsed-event time;
- per-source first/last event position, median gap, maximum gap, cold-start
  rows, updates, and rejections are emitted;
- no full-stream deployment-equivalence claim is made from this R1 result.

If the target-density discrepancy explains a positive result, the gap audit
will expose it and the route will not be promoted without a harmonized replay.

## Formal resource request

Each independent partition copy requests:

- 8 CPU;
- 16 GiB RAM;
- 4 hours;
- no GPU.

CKBO measured about 4.45 GiB MaxRSS and roughly 17 minutes. CKBP removes TabM
training but adds repeated 115D source-out-of-fold closed-form fits. The 16 GiB
request is a measured-margin request rather than a repeat of the old 32/64/128
GiB allocations.

## Formal outputs

The job writes and validates:

- attack preservation, strict Level-2, and every attack-family metric;
- C1/global/bounded/unbounded/local-only candidate results;
- exact gate frontier;
- normal-only model and source-out-of-fold audits;
- per-source reference and causal state audits;
- 385 support-row and family-use audits;
- role, target, report-extension, permanent-canary, and sealed-final audits;
- environment, dependency, manifest, commit, job, wall-time, and resource
  identity;
- one `GO_SIGNAL` or `NO_GO` decision;
- one partition/job-specific pullback archive and SHA-256.

AMD and Intel use different log paths, run roots, archive names, and job-ID
files. If both complete, neither can overwrite the other and both remain
independently valid.
