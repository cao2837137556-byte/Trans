# CKDC D0-E longest-session mechanism addendum — FROZEN

**Status:** `FROZEN`  
**Date:** 2026-08-20  
**Parent result:** `ckdc_d0_existing_evidence_implementation_and_result_20260820.md`  
**Scope:** one read-only descriptive comparison; no training, selection, PCAP, FINAL, or HPC

## 1. Why this addendum exists

The parent D0 found an apparent five-source contrast: hydraulic target ordinals 1-4 have about
5%-7% P2 hard, while ordinal 65+ is 100% hard.  The late rows in each source nevertheless come
from one long session.  The parent preregistered independence gate therefore returned
`INSUFFICIENT_EARLY_LATE_SUPPORT`.

That aggregate can arise from two distinct mechanisms:

1. **within-session transition:** a long session begins normal and becomes hard later;
2. **session-class conflict:** the one long session is already hard at its first target, while
   many unrelated one-target sessions are normal.

This addendum distinguishes only those mechanisms.  It cannot choose a model or horizon.

## 2. Immutable inputs

Use the same CKDA report score and embedding-metadata identities frozen in the parent protocol:

- `ckda_d1_report_scores.csv.gz` SHA-256
  `7ed1c0e9ebd0cbfc95669a064dcf1f57dd343fc4106611216575232432a0e6f9`;
- `ckda_d1_report_embeddings.npz.metadata.csv.gz` SHA-256
  `4d44d605bd00ac5065a2cacc9ff02ebf5384b2df6bb8f68ac6e8644a3090fb10`.

Only probe `P2` and device family `iotsim-hydraulic-system` are opened.  These rows are VIEWED
and diagnostic-only.  Every FINAL marker remains forbidden.

## 3. Metadata-only session selection

Within each of the five hydraulic source groups:

1. count targets per immutable `session_id`;
2. select the session with maximum target count;
3. break an exact count tie by ascending `session_id` string;
4. require the selected session to contain at least 65 targets.

No score, hard state, label, timestamp value, or M7 value participates in session selection.

Within the selected session, sort targets by
`(timestamp_epoch, event_position, uid)` using a stable sort and assign 1-indexed ordinal.

## 4. Fixed measurements

For each selected session report:

- target count;
- P2 hard and P2 score at ordinals 1, 2, 4, 16, 65, and last;
- first-four P2 hard rate;
- ordinal-65-and-later P2 hard rate;
- first ordinal at which P2 becomes hard;
- whether every target from that first hard ordinal onward remains hard;
- M7 hard count.

Missing requested ordinals remain explicit; no nearest-neighbor substitution is allowed.

## 5. Mechanical classification

Each source receives exactly one class:

- `SESSION_CLASS_CONFLICT` if ordinal 1 is P2 hard and ordinal-65+ hard rate is at least 0.90;
- `WITHIN_SESSION_TRANSITION` if ordinal 1 is P2 normal and ordinal-65+ hard rate is at least 0.90;
- `NO_PERSISTENT_LONG_SESSION_HARD_STATE` otherwise.

The route-level result is:

- `SESSION_CLASS_SIGNAL` if at least 3 of 5 sources are `SESSION_CLASS_CONFLICT`;
- otherwise `WITHIN_SESSION_TRANSITION_SIGNAL` if at least 3 of 5 sources are
  `WITHIN_SESSION_TRANSITION`;
- otherwise `MIXED_OR_NO_LONG_SESSION_SIGNAL`.

## 6. Consequences

- `SESSION_CLASS_SIGNAL`: the parent early/late aggregate is a composition effect, so it does not
  support the claim that E3 degrades as a session grows.  A longer horizon is not authorized.
- `WITHIN_SESSION_TRANSITION_SIGNAL`: a later separately frozen, label-free empirical retention
  audit may be drafted.  No representation arm is selected here.
- mixed/no signal: H1 remains underidentified and stops.

Every outcome preserves the parent H3 result.  No learned M7 correction is authorized.

## 7. Outputs and failure behavior

Outputs:

1. `ckdc_d0e_selected_sessions.csv`
2. `ckdc_d0e_checkpoints.csv`
3. `ckdc_d0e_verdict.json`
4. `ckdc_d0e_result_report.md`
5. `SHA256SUMS`

An identity, join, FINAL, or support failure writes only `engineering_failure.json` and no
scientific verdict.  Existing output directories are never replaced.
