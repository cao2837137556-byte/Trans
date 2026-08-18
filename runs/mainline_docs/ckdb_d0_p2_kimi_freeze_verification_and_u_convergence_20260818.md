# CKDB D0-P2 freeze verification + U1-U6 convergence — Kimi

Date: 2026-08-18
Reviewer: Kimi
Targets:
- `ckdb_d0_p2_second_industrial_corpus_amendment_preregistered_20260818.md`
  (FROZEN, Codex commit `e36468b`)
- `ckdb_route_codex_design_input_round3_response_20260818.md` (same commit)

## Part 1 — D0-P2 freeze verification: PASS

SHA-256 recomputed from file bytes:
`16926b7eb860322dc380a45c98bcb9d116d78dabcee32e8743d0639fef41c4b6` —
matches the sidecar exactly.

I diffed FROZEN against the reviewed draft. Every change is the mechanical
incorporation of review `14e281a`; no other drift:

1. **Q3 ruled state**: `PENDING_ARCHIVE_INVENTORY` is explicitly "metadata
   pending, not proof of inseparability and not an immediate NO-GO"
   (§6), is named in verdict state 3 (§9), and is propagated by new
   contract test 23 into the later contract.
2. **Q3 consequence frozen**: the combined large-download/census
   preregistration must contain post-download, pre-use boundary
   verification per sector; failure or ambiguity is fail-closed
   `NO_IDENTIFIABLE_SECOND_INDUSTRIAL_CORPUS`, the archive is isolated, no
   replacement corpus is searched, and the text explicitly accepts the risk
   of one scientifically unusable download. Exactly as ruled.
3. **Q4 rationale on record**: system-fault scenarios are "abnormal physical
   states: neither baseline operation nor cyber-attack"; contamination
   rationale present; future role requires its own preregistration.
4. **N1**: OSTI/DataCite publication/capture dates are the frozen timeline
   anchor for Audit 2.
5. **N2**: protocol families descriptive; PNNL-gas and CIC sharing Modbus
   neither merges nor proves separation; independence rests only on the
   §5 four-condition evidence.
6. **N3**: PNNL registration is a manual user action; registration or
   approval never constitutes download authorization.
7. Header status, authority chain (`14e281a` cited), and the no-retrieval
   boundary (including HEAD requests) are correct.

The FROZEN protocol stands. D0-P2 metadata implementation may proceed once
the user authorizes execution; implementation must pass the 23 contract
tests and my implementation review before any retrieval.

## Part 2 — U1-U6 convergence: CONFIRMED, all six landed

Codex ruled `MODIFY_AND_ACCEPT` on U1–U5 and `ACCEPT_WITH_OPERATIONAL_BOUNDARY`
on U6. I checked each modification is a strengthening, not a weakening:

- **U1**: two arms only (frozen 256-prefix; one causal accumulated-state
  arm with fixed state/reset/memory cap and no-lookahead tests *before* any
  embedding or label is opened); cannot multiply into four promotable
  candidates; horizon selection only by a rule frozen before outputs are
  viewed; VIEWED hydraulic results can never select the horizon. This is
  precisely the claim-bounding ablation I proposed. CONVERGED.
- **U2**: corpus-global descriptors, full distribution table,
  `COVERAGE_GAP_NAMED` caps claims and activates the U1 analysis; not an
  automatic route kill unless a numerical minimum-mass gate is separately
  frozen before object bodies open. CONVERGED, with one scheduling note:
  the decision whether such a minimum-mass gate exists must be taken at the
  large-download protocol stage, before bodies — I will hold that gate
  question there.
- **U3**: `EXTERNAL_BENIGN_REPORT_HOLDOUT` is a better name than my
  "quasi-FINAL" (it cannot be mistaken for the one-shot FINAL and cannot
  support attack-recall claims); deterministic pre-body selection,
  exclusion from pretraining/fitting/thresholding/selection/early stopping;
  industrial side is a mechanical two-option choice frozen from metadata
  counts before bodies are viewed. CONVERGED (my own lean was the
  use-all-plus-claim-limitation option; the mechanical choice preserves
  both honestly).
- **U4**: fine groups are optimization strata only — metadata-derived,
  label-free, frozen min-size/pooling/weighting rules; coarse clusters
  remain the only units for LODO, bootstrap, CIs, domain counts, and
  claims; the added requirement to report worst-group domination by a tiny
  or correlated fine group is a genuinely good diagnostic I had not
  demanded. CONVERGED.
- **U5**: Codex read my proposal as a hard normality veto and rejected
  that; I note for the record that I did not propose a hard veto — my U5
  was "attack evidence anchored on the D1 scorer, CKDB learns normality
  evidence and the combination rule family." The landed invariant
  (immutable D1 attack anchor + bounded learned correction, no silent
  from-scratch classifier) **is** that proposal with one sharpening:
  "bounded". Given the AND-collapse precedent (97.37% → 76.45%), the bound
  is the right hardening, and the `DEGENERATE_FUSION` classification for an
  AND-equivalent arm is exactly the anti-hype guard this project needs.
  CONVERGED on the landed text.
- **U6**: credentials never enter Git/logs/bundles/screenshots; Codex owes
  a storage/transfer/cleanup plan with minimum free-space gates before any
  large-download authorization request. CONVERGED; the user has been briefed
  on the two registrations already.

## Part 3 — the 2×2 claim framework: endorsed, with one addition

The four-cell framework (ID-benign FPR / ID-attack recall / cross-device
benign FPR / cross-device attack recall) with strictly defined denominators
is the right claim matrix, and the correction of the two over-optimistic
cell assignments is factually right: 97.37% is overall-pool attack recall,
96.68% is future-query, and neither fills its naive cell. The only strictly
measured cell today is cross-device benign FPR, and it fails.

Proposal: freeze this matrix, with its exact denominator definitions, in
the D-design preregistration as the paper's claim contract — and add the
currently missing **ID-benign FPR** measurement as a required D-design
output, since that cell is `unknown` today and a Q1 claim cannot leave it
blank. Targets stay labeled "project strong targets", never community
thresholds.

## What this document authorizes

- D0-P2 status: FROZEN VERIFIED. Codex may implement the D0-P2 metadata
  executor and its 23 contract tests, then present them for my
  implementation review. Execution itself still requires the user's
  explicit authorization.

This document does **not** authorize: any PNNL retrieval (including HEAD),
registration automation, download, HPC, training, embedding, threshold
work, or FINAL contact.
