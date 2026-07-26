# raw51_observable_v1 Eligibility Mask

Generated: 2026-07-27, under the conditional approval recorded in ledger
section 11 and `raw51_observable_v1_mask_prereg_draft_20260726.md`.

- File: `raw51_observable_v1_mask.csv` (LF, header `source_group,recorded_index`)
- SHA-256: `b16017d2755feaedbe6d3ad76fd7d1e2444cf66a14a70f6bca35f270734ad2df`
- Rows: exactly 1,353, all from `processed/iotsim-hydraulic-system-1.csv`,
  recorded_index range 50..3868.

## Provenance (mask generated from alignment results only)

1. Authoritative TShark coverage review of r9 (`154695`) member checkpoints:
   hydraulic-system-1 matched 0/1,353; all 29 other sources 100% covered
   (air-quality-1 via the donated source cache, 24,109/24,109).
2. Index list taken from the frozen
   `canonical_source_target_index.csv` (source filter only); cross-checked
   equal to the local full audit's `non_exact_member_unique` set for the
   same source.
3. No label, model score, or experiment outcome was read during generation.

## Generation-time gates (all enforced, all passed)

- mask count == 1,353; no duplicates;
- single source == hydraulic-system-1;
- roles of every masked row == `ood_val` (stages `fit`);
- support_train / support_val / attack / sealed / future / report role hits == 0.

## Semantics

The frozen 325,067-target manifest is unchanged. This mask lists targets
that currently have no legal same-observation-unit raw-51D input (their
packets exist in sibling capture links). All raw-51D consumers operate on
the 323,714-row complement; every compared system uses the identical
intersection; C1 is reported on both denominators.
