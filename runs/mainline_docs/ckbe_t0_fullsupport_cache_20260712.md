# CKBE T0 full-support event cache — 2026-07-12

## Verdict

`PASS`: the full-support, label-free event-cache substrate for the PyG-TGN
route is complete and contract-aligned. This closes T0 cache materialization;
it is not a trained TGN result and does not alter any IDS/OOD claim.

## HPC evidence

- Slurm array: `150067`, `ckbe_tgncache`, all 26 tasks `COMPLETED` with
  `ExitCode=0:0`; all task stderr files were empty.
- Runtime gate: provisioned Python 3.9 environment imported NumPy 2.0.1,
  Torch 2.5.1, PyG 2.6.1, fsspec, and `TGNMemory` successfully. No package
  installation, wheelhouse, Conda environment, or container was used.
- Frozen plan: 26 unique sources, 34,622 recorded target rows.
- Pullback audit: 26/26 rows passed; 26 non-empty NPZ caches, 26 cache JSON
  files, and 26 runtime JSON files exist.
- Every source satisfied source/plan identity, target-row count equality,
  complete target-position alignment, and `raw_label_column_read=false`.

The largest observed source was `iotsim-ip-camera-museum-1` with 10,447,197
finite events and an event materialization time of about 147 seconds. This
confirms that the apparently fast small-source tasks were normal startup plus
small-input runs, rather than silent early exits.

## Frozen cache contract

Each source cache is a separate anonymous event sequence:

```text
(src_local_id, dst_local_id, canonical timestamp, portable 9D raw message)
```

The message contains only log packet length, protocol indicators, destination
port bucket, and TCP SYN/ACK/RST/FIN flags. Node IDs are source-local and do
not enter the message. Source files are read fully and replayed in canonical
timestamp order with recorded-index tie-breaking.

## Boundary and next action

The cache does not train or score a model. Do not report any attack recall,
OOD false-alarm, or cross-family improvement from CKBE T0.

The next permitted step is M1: source-local temporal self-supervision followed
by direct per-packet, family-balanced attack-support supervision. Keep C1 as
the attack-candidate anchor, set `review=0`, keep held families out of both
fit and select, and report attack preservation separately from strict
leave-family evaluation.

## Reproducible evidence location

The lightweight pullback is intentionally local and excluded from Git:
`_hpc_pullback/issue27ckbe_t0_150067/`. It contains the frozen plan, 26 source
metadata pairs, T0 audit JSON/CSV, and array stdout/stderr. The large binary
event caches remain on HPC and are not published to GitHub.
