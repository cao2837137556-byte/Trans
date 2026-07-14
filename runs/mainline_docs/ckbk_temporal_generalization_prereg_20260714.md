# CKBK temporal generalization preregistration

Date frozen: 2026-07-14

Parent evidence: CKBJ v2 seed 27 (`a02fbdd`) is `NO_GO`.  This experiment is
one result-producing, single-seed comparison.  It does not reopen CKBE/CKBI,
change the strict 1M cohort, or tune from report labels.

## Scientific question

The run separates two questions that CKBJ v2 could not answer fairly:

1. Does the unchanged PyG TGNMemory route work after fit, select, and report
   use the same dense, causal replay contract?
2. If recurrent memory is a poor match for the small, highly repetitive
   source-local graphs, does the maintained DyGLib GraphMixer temporal-message
   core provide a learned signal that survives strict leave-family evaluation?

Stream-consumer and hydraulic-system remain development canaries.  Seed 27 is
only a route decision; it is not final paper evidence.

## Frozen candidates

All candidates use the same C1 candidate threshold and the same legal gate
selection procedure.  `review=0`.

- `M0-C1`: unchanged strict C1 baseline.
- `TGNMemory-Repair-Random`: CKBJ TGN architecture randomly initialized and
  frozen; only its linear verifier is trained.
- `TGNMemory-Repair`: the same PyG `TGNMemory`, `IdentityMessage`,
  `LastAggregator`, `LastNeighborLoader`, internal time encoder,
  `TransformerConv`, dimensions, and verifier as CKBJ v2.  Only replay,
  self-supervised task eligibility, gate enumeration, and audit contracts are
  repaired.
- `TGNMemory-Repair-only`: verifier-only ablation without the C1 conjunction.
- `GraphMixer-Full-Anonymous`: DyGLib GraphMixer's fixed cosine time encoder,
  projection, and MLP-Mixer link encoder, plus a narrow causal anonymous-node
  adapter because the frozen cache has no legitimate stable node raw features.
- `GraphMixer-MessageOnly`: the same temporal message/time Mixer with the
  anonymous-node branch removed.
- `GraphMixer-Full-Random`: randomly initialized frozen Full-Anonymous encoder;
  only its verifier is trained.

`GraphMixer-Full-Anonymous` is not described as an untouched reproduction of
DyGLib GraphMixer.  The reused core, upstream commit, license, and the exact
adapter are reported separately.

## Node and feature contract

- Node IDs are source-local anonymous indices used only to retrieve a source's
  causal history.  They are never model inputs and have no learned embedding.
- Source ID, global ID, device/family name, raw IP/MAC, raw label, report role,
  and held-family identity are forbidden model features.
- GraphMixer uses the last `K=20` incident past messages per endpoint, their
  non-negative time gaps in seconds, and padding masks.
- The Full-Anonymous branch has exactly eight past-only statistics per endpoint:
  `log1p(incident)`, `log1p(outgoing)`, `log1p(incoming)`,
  `log1p(unique_neighbours)`, outgoing fraction, incoming fraction,
  `log1p(ms_since_last_incident)/20`, and reciprocal-neighbour fraction.
  LayerNorm is inside the model; no report-derived normalization is fitted.
- The current event is scored before it is appended to either endpoint's
  history.

## Phase state machine

Every protocol writes a hashed `source_phase_interval_manifest.csv` before
training.  Each row contains model stage, protocol/held value, source, phase,
first and last scored target, replay start/end, allowed raw-event count,
blocked role positions, reset count, and the manifest hash.

### Fit

1. Exclude every held-family source from the entire temporal fit scope.
2. Fresh reset per source.
3. Replay only label-free raw history at or before the last legal fit target.
4. Every sidecar row assigned to support-val, select, future, sealed, or report
   is mapped back to its raw event position and blocked with a per-event mask;
   blocking is not limited to scored targets.  The existing strict split has
   interleaved fit/select targets in three sources, so a single maximum-fit
   cutoff is forbidden.  Every interleaving must be represented as exact
   allowed/blocked intervals; an unmapped target or contradictory role at one
   event aborts the protocol.
5. Compute the current target representation/loss, then update with that event.

### Select

1. Encoder and verifier are frozen; gradients are disabled.
2. Fresh reset per source, replay actual past history through each select
   target while excluding every report-assigned raw event, score before update,
   then update label-free.
3. Only legal select/support-val rows choose C1 and verifier gates.  No report
   event or report label is consulted.

### Report

1. All weights, normalization, tasks, and thresholds are frozen.
2. Fresh reset per source under `torch.no_grad()`.
3. Replay every actual past event, score the current target, then update.
4. Updates are label-free and source-local.  Raw labels are read only after
   scores have been materialized for metrics.

History updates use the same maximum batch size (`200`) in every phase and are
split at every scored target.  The audit reports repeated endpoints and the
number of effective update batches; batch semantics never cross a score point.

## TGN self-supervision contract

The four already registered task definitions remain: temporal link,
reverse-response, ACK/RST completion, and retry/survival.  Outcome lookup is
limited to later events inside the legal fit interval.  It cannot cross a
blocked select/report position or a fit horizon.

Each non-link task is enabled per protocol only when all conditions hold:

- at least 64 positives and 64 negatives;
- positive prevalence is in `[0.05, 0.95]`;
- at least three sources have labeled examples;
- each class occurs in at least two sources.

The link task additionally requires at least 128 positive events and 128 legal
source-local past-seen negatives from at least three sources.  A disabled task
is recorded with its counts and reason and contributes no loss.  If link is
disabled, `TGNMemory-Repair` is invalid for that protocol rather than silently
changing its objective.  Class weighting is not used to manufacture signal
from a degenerate task.

## Supervised verifier contract

- All legal support-train rows, including all 385 rows in the global protocol,
  are used at least once in every epoch.
- Sampling is family balanced.  Per-row and per-family use counts are emitted
  with `model/protocol/held/phase/seed` keys.
- Support-val is selection-only.  Report/future/sealed rows have zero training
  use and zero gradient.

## Gate enumeration and selection

For each candidate, enumerate the no-suppression sentinel plus every distinct
decision threshold induced by legal select verifier scores.  There is no
constraint-violating fallback.

1. Retain thresholds whose overall support-val attack recall falls no more
   than `0.5 percentage point` below C1 and whose attack-family recall (family
   size at least three) falls no more than `2 percentage points` below C1.
2. Among eligible thresholds, minimize legal C1-candidate benign/OOD select
   hard rate.
3. Break ties by higher attack recall, then the less aggressive threshold.

The no-suppression sentinel makes the C1-gated candidates' feasible set
nonempty.  A missing feasible set therefore indicates an implementation or
data-contract failure and aborts that candidate.

## Representation audit before blind report

Only legal select scores are used.  Each learned and random representation
emits AUROC, AUPRC, standardized partial AUROC at FPR `<=0.01`, TPR at FPR
`0.001` and `0.01`, attack-minus-benign margin, per-family score quantiles,
feasible threshold count, and selected-threshold margin.  Confidence intervals
resample sources, or episodes when fewer than two sources exist; packets are
never treated as independent bootstrap units.

Learned candidates must exceed their matched random control by at least `0.01`
in select AUROC and AUPRC and have a strictly larger attack-minus-benign margin
before an apparent report improvement is called learned temporal evidence.

## Seed-27 decision

A candidate is `NO_GO` if any contract fails, review is nonzero, target
alignment is incomplete, overall attack recall drops more than `0.5 pp`, or a
major attack family drops more than `2 pp`.  Stream `100% -> 99%` is not a
meaningful signal.  A route-level `GO_SIGNAL` additionally requires the
learned-over-random checks, stream hard rate at most `90%` with an absolute
reduction of at least `10 pp` from C1, and hydraulic hard rate reduced by at
least `5 pp` from C1, without using either report label for selection.  Exact
canary deltas and all other held families are reported; no subset cherry-pick
rule is used.

Seeds 37/47 are not launched automatically.

## Execution and provenance

- One result-producing allocation runs independent TGN and GraphMixer child
  processes and then a failure-tolerant aggregator.  A failure in one child
  cannot erase the other's completed artifacts.
- AMD and Intel copies have partition/job-specific output and temporary paths.
  If both finish, they are infrastructure replicates of seed 27, not extra
  scientific seeds.
- The frozen 26-source CKBE manifest and four-source report-only extension are
  read-only and hash checked.  No environment, cache, or data is bundled.
- Only `scripts/00_env_issue27ckc.sh` is sourced on HPC.  No pip, Conda,
  container, wheelhouse, or old r1/r2/r3 setup script is allowed.
