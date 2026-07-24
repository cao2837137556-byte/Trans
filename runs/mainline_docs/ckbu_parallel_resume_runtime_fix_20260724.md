# CKBU Parallel Resume Runtime Fix — 2026-07-24

## Scope

This is an execution-only repair of the registered CKBU seed-27 experiment.
It does not change the frozen split, target rows, labels, feature schema,
frontend state transitions, model, seed, support use, gates, or report roles.

## Observed bottleneck

AMD job 153973 remained live but processed Gotham sources serially.  After
about 4.5 hours it had completed only one of 30 source caches.  Accounting
showed approximately one active CPU despite an eight-CPU allocation.  The
second source alone contains about 2.09 GiB of PCAP; the 30 planned sources
contain about 23.34 GiB, including individual 8.31 GiB and 5.62 GiB sources.
The original 24-hour serial launcher was therefore unlikely to finish.

## Repair

- Reuse a predecessor cache only after source identity, target count,
  completion flag, raw-label flag, SHA-256, NPZ shape, and 51D schema pass.
- Copy reused caches into the new partition/job-specific run root.
- Schedule unfinished Gotham sources largest-first with four workers.
- Schedule auxiliary sources with two workers.
- Run the unchanged ToN pilot materialization concurrently with both groups.
- Give every source an isolated stdout/stderr file and fail the stage if any
  source or final cache validation fails.
- Aggregate only after all source caches validate.
- Run the unchanged CKBU formal program and result validator afterward.

## Resource rationale

The repaired job requests 8 CPUs, 16 GiB, and 36 hours.  At most seven
materialization workers are active (4 Gotham + 2 auxiliary + 1 ToN), so the
CPU request is used rather than reserved idle.  The predecessor used under
0.5 GiB during its single-source frontend stage; 16 GiB also preserves margin
for the later model stage without repeating the older 32/128 GiB defaults.
The 36-hour wall limit protects the largest individual source and formal model
stage while remaining below the partition maximum.

## Frozen scientific boundary

- Original 1M and CKBE/CKBI manifests remain unchanged.
- C1, 51D unified causal frontend, TabM process head, seed 27, 385 support rows,
  69 gate-only support-val rows, review=0, and all go/no-go criteria remain
  unchanged.
- No report/held source enters fit, normalization, thresholding, negative
  sampling, or model selection.
- AMD and Intel runs have separate run roots, logs, caches, result archives,
  and job identity files; both may finish without overwriting each other.
