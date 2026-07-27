# raw51_observable_v1 Eligibility Mask (FROZEN Preregistration)

Date: 2026-07-26; frozen 2026-07-27.
Status: **FROZEN — conditionally approved by the original pipeline author
(Codex) with nine hard constraints; ruling recorded in ledger section 11.**
Nothing here modifies the frozen 325,067-target manifest, the 1M split,
roles, hashes, or any existing artifact. air-quality-1 coverage is CONFIRMED
(24,109/24,109 via the donated source-level cache), so the authoritative
unmatchable total is final: 1,353 / 325,067 = 0.4163%, observable = 323,714.

## Problem being resolved

Authoritative TShark coverage (ledger section 11) shows exactly one genuine
gap: all 1,353 frozen targets of `processed/iotsim-hydraulic-system-1.csv`
are unmatchable in its exact-stem paired pcap
(`iotsim-hydraulic-system-1_0-0_to_OpenvSwitch-15_1-0.pcap`), because the
processed CSV's hosts (`192.168.20.40-44 -> 192.168.0.4:8883`) are not on
that capture link. The packets exist in sibling captures
(`hydraulic-system-15...OpenvSwitch-16_5-0`: 867;
`hydraulic-system-10...OpenvSwitch-15_10-0`: 486). Every other source is
100% covered (air-quality-1 via the donated source-level cache, CONFIRMED
24,109/24,109 on 2026-07-27).

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

## Ruling (resolved)

1. air-quality-1 source-cache coverage CONFIRMED 24,109/24,109 (2026-07-27);
   authoritative unmatchable total finalized at 1,353 (0.4163%, within the
   0.5% overall gate).
2. Per-source concentration (one source at 100%) accepted as an explained
   single-source capture mispairing, not a systemic contract failure.
3. Mask naming/versioning and bundle placement approved; the mask travels in
   the bundle payload with SHA-256 and a machine-readable contract
   (`raw51_observable_v1_contract.json`).

## r10/r11 reporting requirements (from Codex's conditional approval)

The formal run must, whenever the mask is active, unconditionally emit:
- `M0-C1-raw51obs` and `M4-...-raw51obs` on the 323,714-row intersection for
  every protocol, including the GLOBAL attack-preservation summary (proving
  the attack denominator is unchanged since no attack target is masked);
- `ckbu_raw51_mask_sensitivity_audit.csv` with per-protocol, per-pool,
  per-source composition (full/observable/masked, mask rate) separating core
  vs auxiliary vs ToN, and the core `ood_val` select pool explicitly;
- mask path/SHA-256/frozen(325,067)/masked(1,353)/observable(323,714)/masked
  source in `ckbu_environment.json` and `run_spec.json`.
