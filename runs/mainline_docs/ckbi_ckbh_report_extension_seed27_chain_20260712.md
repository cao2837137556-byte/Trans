# CKBI → CKBH one-submit seed-27 chain — 2026-07-12

## Immutable boundary

- CKBE base T0 remains exactly `26` sources / `34,622` targets with manifest
  SHA-256 `b102b04347dd320f9f89a219285285866dbfa09e09bd73d0839cbe1a91bb0f67`.
- CKBI writes a separate report-only cache directory and frozen extension
  manifest.  It cannot write under the CKBE base path.
- CKBI sources are exactly air-quality-1, building-monitor-1,
  ip-camera-museum-2, and ip-camera-street-1.

## Report-only contract

| Source | Report role | Recorded targets |
| --- | --- | ---: |
| `iotsim-air-quality-1` | future attack | 24,109 |
| `iotsim-building-monitor-1` | future attack | 101,282 |
| `iotsim-ip-camera-museum-2` | sealed OOD | 54,950 |
| `iotsim-ip-camera-street-1` | sealed attack | 110,104 |

The extension is materialized from the raw packet fields used by CKBE, which
exclude the raw label column.  Its alignment CSV binds every recorded target
to a canonical event position.  Source-local anonymous IDs are regenerated
for each source.

The extension's fit/select audit checks all M1 fit and gate roles directly;
the required count is zero for all four sources.  CKBH verifies this audit
again before fitting.  Report scoring uses `torch.no_grad()`, fresh source
memory, pre-event scoring, then past-only `update_state`; it cannot update
weights, scalers, C1, thresholds, negatives, or a gate.

## Seed-27 dependency chain

```text
CKBI stage A: build four report-only caches + frozen extension manifest
    |
    +-- afterok only --> CKBH stage B: formal M1 seed 27
                              M0 / M1-Random / M1-SSL / TGN-only
```

No standalone preflight/audit/environment job is submitted.  A failure in
CKBI prevents CKBH from starting.

## support_val lineage

- Certified support sidecar: `512` rows.
- Immutable support-train partition: `385` rows.
- support-val partition: `127` rows.
- Excluded from select because temporal phase is `fit`: `58` rows.
- Legal `support_val=69` select rows.
- Strict combined-cycle leave-family removes `6`, retaining `63`; every other
  registered held family retains `69`.

## Formal outputs and stopping rule

CKBH writes attack-preservation and strict-Level-2 summaries, per-family
recall, deltas to C1, all support uses, future-label scope, extension/base
manifest hashes, source-bootstrap CI, loss curves, memory/negative audits,
wall time, and in-job RSS.  It writes `m1_single_seed_go_no_go.json` only for
seed 27 and then stops; seeds 37/47 require a later explicit decision.

`NO_GO` is emitted for stream OOD hard rate at least 99%, hydraulic worsening
by more than 2 pp against C1, overall M1-SSL recall below C1 by more than 0.5
pp, a main attack-family loss above 2 pp, any extension fit/select use,
incomplete target alignment, or nonzero review.
