# CKDA D1 local L1 Codex review (2026-08-16)

## Verdict

**PASS for local L2 one-shot report opening.** The user explicitly authorized
Codex to perform this review and proceed without an additional Kimi review.

## Independent checks

- 48/48 CKDA D1 contract tests pass under the frozen Python 3.9 runtime.
- Fit/select plan, target metadata, and embedding artifact each contain 25,467
  unique UIDs and their UID sets are identical.
- The representation matrix is exactly 25,467 by 768.
- There are 11,640 unified-missing rows; missing rows remain in the denominator.
- Every non-missing representation is finite.
- FINAL matches in the fit/select plan are zero.
- The fit/select plan, embedding, and probe-state SHA-256 values equal the
  identities frozen in the threshold marker.
- `final_files_opened`, `report_labels_opened`, and `report_rows_opened` are all
  zero at threshold freeze.
- G0, P1, and P2 each make all 69 support_val attack rows hard under their
  independently frozen thresholds.
- Thirty member checkpoints exist and the current L1 engineering-failure
  marker is absent.

## Authorization and claim boundary

This review authorizes the local L2 report-only chain: report role plan,
metadata, E3 report embeddings, frozen scoring, metrics/bootstrap, verdict,
validation, and pullback packaging. It does not authorize FINAL access,
threshold changes, candidate/model changes, family patches, or formal paper
claims before the required HPC replay.
