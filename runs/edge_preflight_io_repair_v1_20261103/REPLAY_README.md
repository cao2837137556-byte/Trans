# Edge Linux preflight replay I/O repair

This module changes numerical working-file placement, progress reporting and
completed-role checkpointing. It does not change selection, packet ordering,
capture resets, namespaces, frozen numerical Contexts, SpillMap operations,
resident-context limit (256), descriptors, model inputs or model logic.

## Integration

Import `replay_io` after importing the existing worker and its `edge_adapter`
module. Install around the original worker call, using that same module object:

```python
with replay_io.install(edge_adapter, output=output,
                       cache_root=completed_snapshot_cache,
                       scratch_root=verified_node_local_scratch,
                       deadline=absolute_monotonic_deadline,
                       guard=resource_guard,
                       heartbeat=progress_callback):
    original_worker.run_worker(args)
```

The caller verifies `scratch_root` is node-local and writable before calling.
`install` creates and owns a unique child directory and removes only that child.
Only numerical SQLite paths move there; decoder stderr and scientific outputs
remain at the original output paths. The three patched module functions restore
on normal exit and exceptions. Context closure records small stats and releases
the Contexts reference so previous capture ledgers are not retained in RAM.

`deadline` is an absolute `time.monotonic()` value. `guard()` is called without
arguments and must make its normal per-frame path cheap; the integrated runner
limits expensive RSS/disk checks to once per second. `heartbeat(stage, **extra)`
is optional. Every original packet checks the deadline; replay reports at least
every 4,096 frames or five seconds when packets are being received. Status
includes current role/frame, elapsed time, decoder-next time, append time,
SpillMap counters and SQLite/sidecar bytes. STOP is saved before timeout escapes.

## Checkpoint contract

The caller supplies an internal experiment-owned cache directory. Binding covers
raw SHA/bytes, all requested/reference frames, full execution card (including
capture boundaries), owner namespace, frozen `repo/ood/*.py` source identities,
adapter/repair source identities and Python/platform/decoder identity. This is a
conservative cache: a changed runtime or checkout path can cause a safe miss.

Each selected snapshot is immediately written with protocol 5 to preserve tuples
and exact Python value types. Size, SHA, primitive-only structure and top-level
snapshot schema gates apply before reuse; a restricted unpickler forbids global
class/function resolution. Cache and attempt symlink traversal is rejected.
These files are internal checkpoints, never downloaded pickle inputs.

A completed role marker is written only after fully exhausting the original
generator, including its final raw identity check. Partial snapshots, STOP and
INCOMPLETE records are kept as evidence but never reused. A failed role restarts
its raw prefix. A previously completed role can be reused. This is **not**
arbitrary-frame numerical-state resume.

## Local verification

`test_replay_io.py`: 10/10 tests passed. Tests cover exact nested values/types and
cache reuse; actual expired deadline and deadline expiry after the first saved
snapshot; STOP persistence; partial cache nonreuse; failure in original final
input check; tamper rejection; different frame/card binding; scope restoration;
restricted-unpickler rejection. The stand-in also verifies every constructed
SQLite path is inside the exclusively created scratch child.

`REAL_REPLAY_VALIDATION.json` records an actual no-model Windows Python 3.10 run:

- Original versus repaired snapshots at HTTP frames 1, 2, 3, 4, 8, 26, 60, 192,
  4201, 4202, 4203, 4204, 7296, 12140 matched recursively in values **and types**.
- Reading the completed-role cache matched the original values and types.
- Complete original raw prefixes replayed: NORMAL 255,220 frames (28.109 s),
  HTTP 228,978 (81.438 s), UDP 16 (1.359 s).
- Total 119.594 s within a hard 180 s cap, observed temporary peak 196,879,426
  bytes within 512 MiB. All temporary files stayed on D and were cleaned.

After adding directory traversal gates, the final module was verified again by
`REAL_ENDPOINT_FINAL_VALIDATION.json`: all 14 original/repaired/cache snapshots
still matched; module SHA is recorded in that report. The gates do not alter
numerical replay. No original frozen source or raw input was modified.

These tests establish numerical equivalence and local replay feasibility.
They do not replace the Linux runtime, node-local mount and throughput checks,
and they do not estimate model encoding throughput or authorize evaluation.
