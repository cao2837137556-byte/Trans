# Attack Region Lifecycle Policy

This file freezes lifecycle states and audit obligations. It does not freeze numeric split/merge thresholds.

## Region States

```text
candidate_region
-> active_region
-> merged_region
-> split_region
-> retired_region
-> quarantined_region
```

## Lifecycle Semantics

- `candidate_region`: proposed from eligible support candidates; not yet usable for routing.
- `active_region`: usable for support coverage, attack evidence, and later controller routing.
- `merged_region`: region absorbed into another region; provenance must be retained.
- `split_region`: region split because later evidence shows incompatible substructure.
- `retired_region`: no longer active for training/routing, retained for audit.
- `quarantined_region`: excluded because of label, timestamp, role, numerical, or provenance failure.

## Frozen Rules

- Region creation must use development-side eligible support candidates only.
- Region creation must not inspect sealed final attack, sealed final OOD, report-only attack query, or final OOD outcomes.
- Region split/merge/retire thresholds are open parameters and must be learned or fixed in later development-only issues.
- A region cannot be activated without a provenance hash and role access audit.

## Later Evidence Needed

issue27cf or later must report:

- per-region label mix;
- per-region file/device/source coverage;
- per-region phase coverage;
- selected support count and validation count;
- whether any region is dominated by one file or one timestamp band.

