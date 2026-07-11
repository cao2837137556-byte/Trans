# CKBD PyG-TGN data contract — 2026-07-11

## Purpose

T0 is an adapter/causality audit only.  It reuses official PyG `TGNMemory`
and proves that we can construct a portable temporal interaction stream without
inventing a custom temporal graph model.  It contains no classifier, no fitted
threshold, and no performance claim.

## Fixed event schema

```text
src_node, dst_node, timestamp,
log packet length, TCP/UDP/ICMP, destination-port bucket, SYN/ACK/RST/FIN
```

`src_node` and `dst_node` are dynamically allocated **inside one source only**.
Their numeric ids are never model message features.  TGN memory is reset at
every source boundary.

## Passed checks

Using PyG `2.8.0` and local Torch `2.8.0+cpu`:

- mutating raw truth labels leaves the target representation unchanged;
- mutating a time-later event leaves the target representation unchanged;
- mutating a time-earlier event changes the target representation;
- replaying source B after source A plus `reset_state()` equals replaying B
  alone;
- raw label is excluded from the CSV projection;
- stream-consumer and hydraulic-system are absent from every checked fit/select
  role.

The actual-source audit replayed canonical prefixes of stream-consumer-1,
hydraulic-system-1, and combined-cycle-10.  One raw recorded-order timestamp
violation exists in hydraulic-system-1; the adapter canonical-sorts before
replay, so it does not create future-state use.

## Consequence

TGN is now a valid M1 implementation candidate.  The next performance task is
not another capped local score: it is a complete-support source cache and an
HPC M1 run where all 385 support packets receive direct supervised loss, with
TGN used only for process validation.
