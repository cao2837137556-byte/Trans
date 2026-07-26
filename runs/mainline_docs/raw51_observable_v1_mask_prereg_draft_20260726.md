# raw51_observable_v1 Eligibility Mask (DRAFT Preregistration)

Date: 2026-07-26
Status: **DRAFT — pending ruling by the original pipeline author (Codex) and
the user.** Nothing here modifies the frozen 325,067-target manifest, the
1M split, roles, hashes, or any existing artifact.

## Problem being resolved

Authoritative TShark coverage (ledger section 11) shows exactly one genuine
gap: all 1,353 frozen targets of `processed/iotsim-hydraulic-system-1.csv`
are unmatchable in its exact-stem paired pcap
(`iotsim-hydraulic-system-1_0-0_to_OpenvSwitch-15_1-0.pcap`), because the
processed CSV's hosts (`192.168.20.40-44 -> 192.168.0.4:8883`) are not on
that capture link. The packets exist in sibling captures
(`hydraulic-system-15...OpenvSwitch-16_5-0`: 867;
`hydraulic-system-10...OpenvSwitch-15_10-0`: 486). Every other source is
100% covered (air-quality-1 via the donated source-level cache, pending
final confirmation).

## Role safety (decisive)

All 1,353 rows are `roles=ood_val`, `stages=fit`:

- support_train (385) and support_val (69): **untouched**;
- report / sealed / held-family evaluation denominators: **untouched**;
- impact is confined to development-phase benign-OOD validation
  (8,682 -> 7,329 rows).

## Proposed rule

1. Define a versioned derived artifact `raw51_observable_v1`: the frozen
   target manifest MINUS exactly the 1,353 enumerated
   (source_group=hydraulic-system-1, recorded_index) pairs, with the
   exclusion list and its sha256 recorded alongside.
2. Every raw-51D consumer (process head fit/threshold/eval) operates on
   this mask. Every compared system in any raw-51D experiment uses the
   identical intersection.
3. Reports state both denominators: the original frozen counts and the
   raw51-observable counts.
4. The frozen manifest file itself is never edited; the mask is a separate
   versioned file.
5. The aggregation coverage gate accepts a source iff its targets-minus-mask
   are fully covered; the pre-materialization validator reports mask hits
   up front.

## Why not re-pair (option A) now

Matching the 1,353 rows in sibling captures would put one source's causal
state across multiple capture links, forcing a new observation-unit
contract (time-merge vs per-member reset, dedup rules) for the entire
frontend — disproportionate for 1,353 development-only rows. This option
remains open as a future versioned contract if hydraulic-1 coverage is ever
needed.

## Open questions for the ruling

1. Confirm air-quality-1 source-cache coverage (24,109 rows) so the overall
   unmatchable total is finalized at 1,353 (0.4163%, within the 0.5%
   overall gate).
2. Accept the per-source concentration (one source at 100%) as explained
   mispairing rather than a systemic contract failure.
3. Approve the mask naming/versioning and its placement in the bundle.
