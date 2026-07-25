# CKBV Checkpointed Sparse Recovery — Preregistered 2026-07-25

## Purpose

CKBV is the result-producing recovery of the cancelled CKBU seed-27 run. It
does not introduce a new scientific candidate. It preserves the registered
CKBU 51D causal frontend, target rows, role boundaries, formal model, support
rows, seed, gates, review=0 rule, metrics, and go/no-go decision.

The only changes are execution changes required after AMD job 154081 spent
about 17 hours at Gotham source coverage 1/30 without producing a new source
checkpoint:

1. commit Gotham checkpoints per ZIP PCAP member rather than per complete
   source;
2. compute the frozen 51D vector only at possible frozen target events while
   applying the same causal pruning and state update to every packet;
3. materialize each eligible ToN pilot PCAP into an atomic file checkpoint;
4. run preprocessing phases sequentially to avoid the previous shared-storage
   contention;
5. calibrate throughput on members spanning the size range and refuse the full
   dispatch unless the safety-adjusted projection fits within 75 percent of
   the post-reserve remaining allocation;
6. terminate an individual member/file when it exceeds its time bound or
   produces no progress record for 15 minutes;
7. expose actual member/file completion, decoded-packet progress, CPU, memory,
   disk I/O, failure phase, and stderr in the status command.

## Frozen scientific contract

- Seed: 27 only.
- Gotham original 1M split and target indices: unchanged.
- Gotham output: 30 sources and 325,067 target rows.
- Auxiliary output: 31 sources and 18,600 target rows.
- ToN pilot output: 12,000 legal model rows; Injection and MITM remain
  reserved with zero model rows.
- Causal schema: the same ordered 51D CKBU schema.
- Current event: feature/score before state update.
- State: source/capture-local, past-only, label-free.
- Support: all 385 legal support-train rows are used per epoch.
- support-val: gate selection only.
- Held/report sources: zero fit, normalization, calibration, gate selection,
  negative-sampling, or model-selection use.
- Review: zero.
- Formal model, hyperparameters, candidate gates, bootstrap, and go/no-go:
  unchanged from CKBU.

The sparse execution path is accepted only because its local contract test
compares selected-event feature vectors bit-for-bit with the original dense
path. It does not remove state updates, reorder packets, add fields, read raw
labels, or change target alignment.

## Recovery and isolation

The cancelled AMD 154081 run is a cache donor only. Every source cache is
reused only after source identity, target count, completion flag,
raw-label=false, SHA-256, feature names, and NPZ shape validate. Its 31/31
auxiliary caches and 1/30 Gotham source cache may therefore be copied. No
scientific result from that cancelled run is accepted.

AMD and Intel submissions have independent run roots, logs, member caches,
source caches, ToN caches, validation results, and pullback archives. Neither
job cancels the other automatically. Two hardware copies are not two
scientific seeds. Automatic Slurm requeue is disabled so a restarted allocation
cannot reuse and mix a partially written job-specific run root.

## Resource rationale

Each job requests 8 CPUs, 16 GiB, and 36 hours. The failed run used about
2.3 GiB MaxRSS, while four extraction workers each occupied a CPU. CKBV uses
up to four Gotham workers or two ToN workers, followed by the unchanged formal
model using the eight allocated CPUs. The requests are therefore bounded by
observed use rather than inflated defaults.

## Required outputs

In addition to the unchanged CKBU scientific tables and readout, CKBV must
produce:

- `ckbv_gotham_member_plan.csv/json`
- complete, validated Gotham member and source caches
- `ckbv_gotham_checkpoint_ready.json`
- `ckbv_source_reuse_audit.csv`
- `ckbv_source_aggregation_audit.csv`
- `ckbv_throughput_projection.json` when any member is materialized
- per-member and per-ToN-file runtime/progress logs
- `ckbv_result_validation.json`
- partition/job-specific pullback archive and SHA-256

An environment/contract check without scientific metrics is not a successful
job. Completion requires the unchanged attack-preservation, strict Level-2,
support-use, review, predictions, and single-seed go/no-go outputs.
