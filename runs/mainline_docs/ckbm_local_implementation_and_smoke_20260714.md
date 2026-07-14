# CKBM local implementation and smoke audit

Date: 2026-07-14
Formal seed: 27 only
HPC status: not submitted

## Outcome

CKBM is locally implemented and ready for a single result-producing formal
seed, subject to user confirmation.  It keeps C1 only as the high-recall
candidate anchor and replaces the simple verifier with the official TabM
v0.0.3 implementation.  A mature sklearn ExtraTrees backend and global-only
TabM are frozen controls.  The paper-specific change is limited to a causal,
source-relative view that addresses CKBL's measured cross-source calibration
failure.

This local result is an execution/contract result, not evidence that OOD
generalization improved.  Only the formal HPC report can answer that question.

## Data flow

```text
frozen strict 1M roles and C1 cache
  -> per-protocol C1 fit/calibration with held-family exclusion
  -> causal 207D C1 target features
  -> QuantileTransformer fit on legal fit rows only
  -> two verifier views
       global: 207D
       CSR: global 207D + prior-only source residual 207D + history count 1D
  -> mature backend candidates
       ExtraTrees global / official TabM global / official TabM CSR / ExtraTrees CSR
  -> exact support_val attack-retention frontier plus legal benign select
  -> logical decision: C1 candidate AND verifier support
  -> report-only source-local scoring, fresh phase/source state, no gradients
  -> attack preservation + strict held-family OOD hard-rate tables, review=0
```

The CSR running state consumes only frozen scored target rows because memory-only
raw events do not have the 207D C1 view.  This boundary is explicit in every
causal audit row.  The state is label-free and current-event-before-update; a
duplicate source-local target event across fit/select/report is rejected.

## Frozen role counts

These counts are inherited from the already completed CKBJ frozen collector and
caps.  CKBM calls the same collector and adds stricter duplicate-event checks;
the formal validator rechecks every count before packaging.

| protocol | fit attack | fit benign | select attack | select benign | report |
|---|---:|---:|---:|---:|---:|
| global attack preservation | 385 | 12,000 | 69 | 9,000 | 301,931 |
| stream-consumer held | 385 | 8,000 | 69 | 6,000 | 3,000 |
| hydraulic-system held | 385 | 10,604 | 69 | 6,000 | 3,000 |
| domotic-monitor held | 385 | 12,000 | 69 | 9,000 | 3,000 |
| combined-cycle held | 352 | 12,000 | 63 | 9,000 | 5,486 |
| ip-camera-street held | 385 | 12,000 | 69 | 9,000 | 3,000 |

The combined-cycle strict protocol removes 33 support-train and 6 support-val
rows.  The stream protocol removes its 4,000 fit and 3,000 select OOD-stress
rows; hydraulic removes 1,396 fit and 3,000 select OOD-val rows.  Source-level
fit exclusion remains active for all held protocols.  CKBI/CKBJ report-only
extension sources are required to have zero fit/select use.

## Full support distribution and formal use

The immutable global `support_train` distribution is:

| attack family | rows |
|---|---:|
| File Download | 15 |
| Ingress Tool Transfer | 18 |
| Merlin C&C Communication | 30 |
| Merlin ICMP Flooding | 43 |
| Merlin TCP Flooding | 60 |
| Merlin UDP Flooding | 30 |
| Mirai C&C Communication | 9 |
| Mirai GRE Flooding | 60 |
| Mirai TCP Flooding | 60 |
| Mirai UDP Flooding | 60 |
| **total** | **385** |

The coverage-first sampler includes every legal fit row once, then repeats only
within smaller attack families until each family has 60 occurrences per epoch
in the global protocol.  Occurrence weights allocate equal attack mass per
family and equal benign mass per fit source.  TabM uses 48 fixed epochs, so each
global attack family has 2,880 sampled occurrences; the per-row CSV records the
actual count.  ExtraTrees receives the same one-epoch sampled cohort.  There is
no episode pooling.

CKBM has no self-supervised task or negative sampler.  Its negative-sampling
count is exactly zero by design: it is the supervised strong-backend/calibration
experiment motivated by CKBL, not another repair of the failed TGN SSL route.

## Mature components

- Official Yandex Research TabM v0.0.3, Apache-2.0, upstream commit
  `a507095893d784c5702059d737ddfbd1299c41dd`; `tabm.py` is vendored unchanged
  with LF SHA-256
  `fc654af6a16bac53d893a8265c79d7af4ebddcb95ad0d600cc6b6bc6b7317ade`.
- Official TabM ensemble loss and probability-averaging rules, AdamW defaults,
  and fit-only quantile preprocessing are preserved.
- sklearn `ExtraTreesClassifier` is the non-neural mature-backend control.
- CatBoost was not imitated because it is absent from the frozen runtime and
  dependency installation is forbidden.

## Local evidence

Two independent real-data fit-only runs used 8,344 legal fit rows, 7 sources,
58 bounded support attacks, and no report or development-canary rows.  Both
runs produced exactly the same artifacts except wall time:

- loss CSV SHA-256:
  `799d3911cd21e788b3724d63e457b9b3d9692d8fd09f560ad421297539d69ea0`;
- model SHA-256:
  `9dc15af187d7e4c7a3288f7b4996504def8ccfb1238a0df93b95121e8a8cea53`;
- score-array SHA-256:
  `a7ccf532aebb5b86b7271ffc4ef53ff40f153156bcf15831cbc5bbb57b499d2f`;
- quantile SHA-256:
  `9373f7cc613b469c9a8fd91b8bc73451594fd06bb5f106602e87d714ea67db2e`;
- first/last loss: `0.5627379514 -> 0.2759007011`;
- all 8,344 unique rows covered; 8,361 sampled occurrences after balancing;
- three bounded attack families each had 25 occurrences per epoch;
- seven fresh source resets, 8,344 score-before-update records, 14 cold starts;
- finite scores, no label read for state, no phase crossing, no NaN.

Contract-unit tests also verify official TabM shape/loss, future-mutation
invariance, label-flip invariance, source resets, exact support-val threshold
frontier, and duplicate target-event rejection.  Python compilation, Bash
syntax, embedded validator-Python compilation, dry-run, and `git diff --check`
all pass.

## Formal job and outputs

One launcher submits independent AMD and Intel copies.  Both use 8 CPUs, 32 GiB
RAM, and a 12-hour limit.  Every output, log, failure marker, validation JSON,
and pullback archive contains both partition and job ID, so simultaneous
completion is safe.  Both jobs only read the shared frozen caches.

The formal result writes attack-preservation, strict Level-2, per-family,
selection, loss, support-use, role-use, held-exclusion, feature, preprocessing,
causal-state, model, environment, manifest, Slurm, resource, GO/NO-GO, and
Markdown readout artifacts.  The in-job validator is standard-library-only and
packages a partition/job-specific pullback archive.  No `/usr/bin/time`, pip,
Conda, container, or old environment script is used.

Measured predecessors peaked at about 19 GiB or less; 32 GiB leaves practical
headroom without repeating the earlier 128 GiB over-request.  Expected wall
time is approximately 3--8 hours; the 12-hour limit covers the six protocols
and two TabM fits per protocol without claiming that unused time is memory or
CPU allocation.
