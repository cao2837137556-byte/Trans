# CKDE D1 pre-cap freeze handoff

**Date:** 2026-08-25
**Source draft:** `ckde_d1_development_commissioning_calibration_prereg_draft_20260825.md`
**Independent review:** `ckde_d1_draft_and_d0_results_kimi_review_20260825.md` at `9ce6fca`
**Frozen output:** `ckde_d1_development_commissioning_calibration_preregistered_precap_20260825.md`
**Frozen SHA-256:** `9e7a4904dc72c0a7f81a5510e26432128478f0a17101acbece433870804697c9`

## Normative changes from the reviewed draft

1. R1 is mandatory: S64/S128/S256 are reported both on their changing eligible sets
   (23/20/11 devices) and on the immutable common 11-device subset. The expanded allowlist must
   be materialized and hashed before score access.
2. N1 is part of the claim contract: benign gates measure within-device prefix-to-suffix temporal
   stability on development devices, not universal calibration or unseen-device generalization.
3. All eight review questions are closed as normative rulings.
4. The protocol is PRE-CAP FROZEN but non-executable. No score may be opened and no implementation
   or calibration may run under this freeze alone.

## Next permissible request

Only a separately authorized cap-only materialization may read the 4,385 fit-attack scores and
emit a hashed literal `T_cap` and `cap_fit_attack`. Those values must then be inserted into a newly
named numerical D1 FROZEN document, independently hash/diff reviewed, and separately authorized
before benign-prefix or support-val score access.

No cap materialization, benign-score access, support access, report access, FINAL access, training,
download, or HPC submission occurred while producing this handoff.
