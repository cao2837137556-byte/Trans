# CKBH formal M1 protocol — 2026-07-12

## Scope

This is the first training/evaluation step after CKBE T0.  It is not a cache
or a PASS/FAIL preflight.  The only candidates are `M0`, `M1-Random`,
`M1-SSL`, and `TGN-only`; review is fixed to `0`.

- `M0`: established strict legal C1 baseline.
- `M1-Random`: C1 candidate gate plus a frozen randomly initialized PyG TGN
  representation and a per-event verifier.
- `M1-SSL`: the same gate plus PyG TGN self-supervision and a per-event,
  family-balanced support verifier.
- `TGN-only`: ablation only.

No episode pooling, score addition, prototype bank, OpenOOD, Fishr, DANN,
GroupDRO, SupCon, or review routing is part of CKBH.

## Causal data flow

```text
legal fit raw event history ──> official PyG TGNMemory ──> pre-event memory
       │                              │                         │
       │                              ├─ IdentityMessage
       │                              ├─ LastAggregator          ├─ SSL tasks
       │                              ├─ LastNeighborLoader       │  link / response /
       │                              └─ internal TimeEncoder      │  ACK-RST / retry
       │                                                        └─ per-event verifier
       │
legal support_train (every packet, family-balanced) ────────────────────────┘

C1 reaches candidate threshold AND verifier supports attack process -> hard attack
C1 reaches candidate threshold AND verifier does not support attack process -> suppress
C1 below candidate threshold -> non-hard
```

For every target, CKBH scores the `TGNMemory` state before the current event
is passed to `update_state`.  It then updates memory.  Each source resets
memory and `LastNeighborLoader`; no memory state crosses a source boundary.
Report events are scored without labels or gradients and are updated only
past-to-future after scoring.

## Strict role rules

- SSL tasks and the verifier use only fit records.  The full legal global
  support train set is `385` rows; no support record is episode-compressed.
- `support_val` and legal benign select rows select the C1/verifier gate.
- Future and sealed roles never fit C1, standardization, TGN SSL, verifier,
  negatives, or a gate.
- For each held device family, C1 uses the existing row-level strict
  exclusion.  TGN adds a conservative source-level exclusion: any raw source
  with a target attributed to the held family is omitted from temporal fit.
- Report-side memory updates are label-free and past-only.  Stream-consumer
  and hydraulic-system remain development canaries, not untouched final data.

## Local verification completed

- Unit causal test: future mutation leaves the current representation
  unchanged; past mutation changes it; no NaN/Inf.
- Synthetic optimization smoke: SSL + verifier optimization, family usage,
  negative sampling, resets, and same-seed reproducibility pass.
- Full local dry-run records actual role and held exclusion counts.  The large
  NPZ cache is deliberately not present locally; local target-position checks
  are marked `not_verified_npz_not_pulled`, never reported as failures.

## Pre-submit coverage conflict — must be resolved before formal submission

The official CKBE T0 audit contains 26 cached sources and 34,622 targets.
It does **not** contain `processed/iotsim-ip-camera-street-1.csv`.  CKBF's
pulled role audit shows that all `sealed_final_attack` rows belong to this
missing source.  Therefore the present frozen T0 cannot yield an honest
TGN-based sealed-attack row in Table A.

The same audit also excludes `iotsim-air-quality-1`,
`iotsim-building-monitor-1`, and `iotsim-ip-camera-museum-2`.  Consequently
future/sealed report coverage is not the complete role population.  CKBH will
write requested/aligned/unmapped counts for every role, but it must not call a
T0-aligned subset a full query result.

The formal entrypoint writes `m1_required_report_source_coverage.csv` and
stops before model fitting when this coverage is incomplete.  This is an
in-process guard against wasting a formal allocation; it is not a separate
CKBF-style PASS/FAIL submission.

This conflicts with the requested formal M1 table, which explicitly requires
sealed-attack recall.  CKBH must not substitute a C1-only number or a blank
for an M1 TGN result.  The next formal submission is consequently withheld
until the owner authorizes one of these scoped choices:

1. create a label-free, report-only T0 cache extension for the missing sealed
   source and bind it to the same manifest/audit contract; or
2. narrow the claimed Table A scope and explicitly omit sealed attack.

Choice 1 is the scientifically sound option if sealed-attack recall remains a
required formal metric.  It is an additional cache scope, so it is not being
silently folded into CKBH.
