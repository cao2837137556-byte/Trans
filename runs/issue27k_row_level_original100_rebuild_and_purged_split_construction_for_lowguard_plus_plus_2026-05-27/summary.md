# Issue27k Row-Level Original100 Rebuild And Purged Split Construction Summary

## Verdict

- primary_verdict: `row_manifest_recovered_but_clean_split_blocked`
- issue27l_next_action: `issue27l_split_aware_original100_rebuild_with_sufficient_clean_eval_asset`

## 1. Row-level sidecar manifest

Constructed: `True`.

Total rows mapped: `80000`.

## 2. Original100 / extracted TSV alignment

Current source matrices align with extracted feature caches by row order: `True`.

Timestamp monotonic by role: `True`.

Raw pcap source paths are recorded in the sidecar, but byte-level pcap packet hashes were not matched in this issue.

## 3. Original100 reconstruction feasibility

Continuous-state baseline is reproducible from existing feature caches. Split-reset and train-state-then-eval-online are implementable, but full split-aware rebuild was not run because no clean split was selected.

## 4. Purged chronological split

Constructed: `False`.

Blocked because available chrono candidates either reuse locked/previously analyzed bins or have too few future-window attack rows.

## 5. Clean/purged LOW-GUARD++ evaluation

Completed: `False`.

No clean/purged LOW-GUARD++ score should be claimed from this issue.

## 6. Safer variants

Not evaluated on clean/purged split because no clean split and split-aware feature matrix were available.

## 7. Continuous-state carryover

Finding: `not_directly_proven_harmful_but_claim_requires_splitwise_rebuild`.

## 8. Claim status

LOW-GUARD++ cannot yet be upgraded to main-text performance instance. It remains a high-potential candidate with improved provenance.

## 9. Slurm

Not needed for this row-level manifest and feasibility run. May be needed for larger raw reconstruction or second-environment extraction.
