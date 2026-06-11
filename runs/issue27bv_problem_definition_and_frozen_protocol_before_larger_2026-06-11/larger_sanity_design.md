# Larger Sanity Design

## Purpose

The next larger sanity should test whether the medium diagnostic protocol survives broader data, stricter groups, and richer OOD/attack coverage before formal benchmark.

It is still not a full formal benchmark.

## Required Data Contract

Construct larger roles from unused Gotham files where possible:

- ID benign train/calib: multiple benign source groups, files, and devices.
- OOD benign val/stress: independent benign devices, files, time blocks, and background-load regimes.
- sealed final OOD: new benign drift groups not used for OOD stress selection.
- attack support: development-side labelled attack examples only.
- dev future/query attack: development-side attack query for protocol design.
- sealed final attack: attack files/types/groups never used for support, threshold, controller, prototype, or model selection.

## Required Splits

At minimum:

- source-group disjoint split
- file-disjoint split
- device-disjoint split where possible
- time-forward split with purge/embargo where sequence adjacency is possible

If a role has only one source group, mark it as a limitation and do not use it for formal claims.

## Larger Sanity Metrics

Report:

- dev attack min
- dev OOD max
- report-only attack min
- final OOD max
- review rate
- unknown rate if mixed stream is used
- per-device and per-file subgroup results
- support/query coverage by region and phase
- time-to-detect for attack streams if temporal replay is enabled

## Go / No-Go

Go to mixed-stream diagnostic only if:

- attack hard-min remains >= `0.93` on development-side attack roles.
- OOD hard max remains <= `1%` on development-side OOD/stress.
- report-only attack remains >= `0.90` without using report-only roles for selection.
- final OOD remains report-only and low, with caveats if not sealed anew.

No-go:

- report-only data influences any selection.
- group/file/source leakage is detected.
- OOD stress fails to cover plausible final OOD tails.
- support/query attack phase mismatch reappears.

