# Metadata Split Smoke Check

Status: `metadata_only_smoke_completed`

- Candidate checked: `earlier-to-later` and existing reverse `later-to-earlier` bin definitions.
- What was checked: asset-report train/eval bin definitions load, attack train/eval counts are present, and known split labels can be reconstructed at bin level.
- Smoke pass: `yes`.
- Model training: no.
- Threshold selection: no.
- Final OOD/attack eval used for selection: no.
- Can enter formal validation directly: no.

Why not formal: this smoke only confirms bin-level metadata wiring. It did not recover raw timestamp, packet order, capture/session boundaries, or purge/embargo gap metadata, so it cannot support a clean formal temporal validation claim.
