# Issue27j Raw Provenance And Clean Split Audit Summary

## Verdict

- primary_verdict: `clean_independent_validation_blocked_but_recoverable`
- issue27k_next_action: `issue27k_row_level_original100_rebuild_and_purged_split_construction`

## 1. Raw provenance

Raw pcap / timestamp assets found: `True`.
Row-level mapping recoverable by extraction order: `True`.

## 2. HH separator lineage

The three HH separator features were traced to legal Kitsune traffic-stat logic: HH radius/magnitude over host-host streams at lambda 0.01 / 0.1.

No explicit future-information or label/split/bin field was found. Remaining risk: continuous pre-split feature-state computation can carry temporal/capture context, so clean temporal validation should rebuild or reset state around split boundaries.

## 3. Clean independent split

Clean independent split constructable now: `False`.

Blocked because:
- no persisted full sidecar row manifest;
- unused future attack window is too small for formal validation;
- no new independent OOD/capture object is ready;
- purged validation requires split-aware reconstruction or reset.

## 4. Clean LOW-GUARD++ validation

Not run. This is a split/provenance blocker, not a method-failure result.

## 5. Claim status

LOW-GUARD++ cannot yet be upgraded to main-text performance instance. It remains a high-potential audited candidate.

## 6. Slurm

Not needed for this audit. May be needed for full raw reconstruction or second-environment extraction.
