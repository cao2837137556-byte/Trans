# CKDC D0 existing-evidence diagnostic result

## Mechanical verdict

- H3: `NO_IDENTIFIABLE_LEGAL_CONFLICT_SUPPORT`
- H1: `INSUFFICIENT_EARLY_LATE_SUPPORT` (`INSUFFICIENT_EARLY_LATE_SUPPORT`)
- E3 capability: `EARLY_BURST_CONTENT_CAPPED_DURATION_VISIBLE`

## Exact facts

- legal select rows: 7069
- `P2 hard / M7 normal` benign select rows: 4986
- `P2 hard / M7 normal` attack select rows: 0
- hydraulic report rows (VIEWED, descriptive only): 3000
- hydraulic P2 hard rows: 2289
- hydraulic M7 hard rows: 0

## Interpretation boundary

This diagnosis does not train or select a model.  H3 may proceed only when its legal-support
conjunction passes.  H1 uses already-viewed report rows only to decide whether a separate,
label-free retention audit is worth preregistering.  No FINAL material was opened.
