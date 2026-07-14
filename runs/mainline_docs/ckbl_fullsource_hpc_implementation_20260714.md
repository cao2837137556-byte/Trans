# CKBL full-source result run implementation

## Purpose

Run the already-preregistered frontend-information gate with complete raw
chronology, all 385 legal attack support rows, all ten attack labels, and the
five legal benign sources. This run adds no detector architecture and does not
evaluate or tune on stream-consumer, hydraulic-system, or cooler-motor.

## Frozen scope

- selected rows: 8,671;
- attack rows: 385;
- benign rows: 8,286;
- source count: 8 (3 attack, 5 benign);
- attack-family count: 10;
- exact TGN message / current / compact / permuted / C1 dimensions:
  9 / 20 / 69 / 69 / 207;
- outer folds: 15 unseen-source pairs plus 10 unseen-family-origin folds;
- candidate-fold metric rows: 25 x 5 = 125;
- seed: 27;
- review: 0.

The complete real metadata plan passes with zero selected-fit/nonfit-target
collision. It blocks 198,173 distinct known non-selected target rows from
fit-time passive-state updates. Raw labels remain unread.

## Why existing caches are not silently substituted

CKBE's mature full-source cache is reused as the measured scale reference: the
largest museum source has 10,447,197 finite events and required about 147
seconds for the vectorized 9D materialization. But its 9D message cannot
reconstruct exact C1 207D inputs: exact source port, destination port, TCP
window/PDU, and port-dependent flow5/biflow keys are absent. The old CKAT C1
cache is prefix-based rather than full-source chronology. Substituting either
would change the registered comparison.

The result job therefore reuses CKAT's existing label-free C1 feature logic and
reads the eight relevant raw sources completely. The only frontend change is
an optional known-target state mask whose default preserves every old caller.

## Failure containment

- source start/done messages are flushed immediately;
- one JSON progress record is checkpointed after each of eight sources;
- a heartbeat is printed every five minutes;
- a nonzero exit writes `job_failure.txt`;
- no `/usr/bin/time`, optional pandas renderer, pip, Conda creation, container,
  Git operation, or environment preparation script is used;
- the job runs compile and contract checks inside the same result allocation;
- final validation uses Python standard library only;
- a validated pullback tarball and SHA-256 are produced automatically.

## Dual-partition contract

The same seed-27 infrastructure copy is submitted to `amd` and `intel` with:

- 1 node;
- 8 CPUs;
- 64 GiB RAM;
- 12-hour limit.

Every run directory, Slurm log, validation file, and pullback archive includes
partition and job id. Both jobs remain correct if both finish. They are not two
scientific seeds and must not be pooled as independent evidence.

The 64-GiB request is a safety margin for a complete 10.4M-row pandas source
with object columns. CPU and wall time are based on the prior CKBE full-source
runtime plus the local CKBL measured feature/model runtime, not copied from the
old 128-GiB/48-hour M1 request.

## Formal outputs

The result includes scope and memory-target audits, all selected rows, feature
schema/value hashes, per-source runtime/progress, 8,671 alignment records, 25
fold contracts, 125 fold metrics, ten aggregate rows, decision JSON/Markdown,
environment, source-level timing, Slurm identity/accounting, validation JSON,
and an automatically hashed pullback archive.
