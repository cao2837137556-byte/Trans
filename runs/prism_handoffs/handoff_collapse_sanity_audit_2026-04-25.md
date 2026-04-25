# Prism Handoff: Collapse Sanity Audit

Date: 2026-04-25

Purpose:
- Compress the `collapse_sanity_audit_2026-04-25` run into paper-facing language.
- This is a sanity audit, not a new experiment line.
- No new model was trained, no threshold was tuned to rescue a result, and no second-environment run was reopened.

Primary audit package:
- `runs/collapse_sanity_audit_2026-04-25/collapse_sanity_audit_summary.md`
- `runs/collapse_sanity_audit_2026-04-25/score_cache_alignment_check.csv`
- `runs/collapse_sanity_audit_2026-04-25/score_distribution_threshold_audit.csv`
- `runs/collapse_sanity_audit_2026-04-25/operating_point_sweep.csv`
- `runs/collapse_sanity_audit_2026-04-25/attack_index_integrity_check.json`

## 1. Audit Purpose

This audit checks whether the near-zero detection of unsupervised / modern models under the guarded low-OOD-alarm operating point is a genuine score-threshold trade-off, rather than a code or protocol artifact.

The checked failure modes were:
- score cache length mismatch;
- attack score cache row-order mismatch;
- stage2 high-purity attack index out-of-range or duplication;
- reversed score direction;
- threshold selection using final OOD eval;
- threshold selection using attack eval;
- legacy result reuse outside its valid split boundary.

## 2. Bugs Ruled Out

For the current dA official reference used in the few-shot paper package:
- `da_full_id_scores.npy` length matches the 50,000-row ID matrix.
- `da_ood_scores.npy` length matches the 20,000-row OOD benign matrix.
- `da_attack_scores.npy` length matches the 10,000-row `attack_source_100.csv`.
- The dA attack cache exactly matches stage1 `da_attack_scores.npy`, so the attack score row order is consistent with the current attack source.
- Stage2 high-purity attack indices are all within the attack matrix range.
- Stage2 high-purity attack indices have no duplicates.
- The threshold logic keeps final OOD eval and attack eval out of threshold selection.

Stage2 high-purity split integrity:
- total high-purity count: `6871`
- train count: `4122`
- validation count: `1374`
- eval count: `1375`
- first / last high-purity row id: `2921 / 9791`
- all in attack matrix range: `true`
- duplicate count: `0`

## 3. dA Sweep Interpretation

The current dA official reference does not look like a simple score-direction bug:
- ROC AUC attack-vs-OOD eval is `0.806365`, clearly above 0.5.
- Under guarded low-OOD-alarm selection, final OOD alarm is `0.010800`.
- Under the same guarded point, high-purity attack detection is only `0.002909`.
- The attack median is far below the selected threshold, while the OOD tail dominates the threshold.

Operating-point sweep for dA:

| target OOD alarm | attack detection |
|---:|---:|
| 0.5% | 0.0000 |
| 1.0% | 0.0029 |
| 2.0% | 0.0029 |
| 5.0% | 0.0095 |
| 10.0% | 0.6516 |

Paper-facing interpretation:
- The dA score still contains ranking information.
- The collapse appears when the operating point is forced into a strict low-OOD-alarm region.
- Detection recovers only after the allowed OOD alarm is relaxed substantially.
- This supports an operating-point collapse interpretation, not an invalid-cache or reversed-score interpretation.

## 4. Legacy Transformer / TailReg Boundary

The legacy transformer and transformer-tailreg raw-score checks should be used only as auxiliary sanity evidence.

Reason:
- Their attack and OOD score caches are available.
- Their raw-score AUC and sweep behavior show the same broad threshold-tail pattern.
- However, their ID score caches have only 5,000 rows and are not the current 50,000-row official split used by the few-shot paper package.

Therefore:
- It is acceptable to mention them as legacy auxiliary evidence that similar low-alarm collapse patterns were observed.
- They should not be used as the main current-split proof.
- The main current-split sanity claim should be anchored on the dA official reference.

## 5. Paper-Facing Paragraph

To ensure that the observed low-alarm detection collapse was not an implementation artifact, we performed a collapse sanity audit on the score caches and thresholding protocol. For the dA official reference, the ID, OOD, and attack score cache lengths match their corresponding input matrices, the attack cache matches the stage1 attack score order, and all stage2 high-purity attack indices fall within the attack matrix without duplication. The guarded threshold uses only ID calibration and OOD validation; final OOD eval and attack eval are not used for threshold selection. The dA score direction is also not reversed: attack-vs-OOD AUC remains 0.806, but the guarded 1% low-OOD-alarm threshold lies above almost all held-out high-purity attack scores, yielding only 0.0029 detection. A threshold sweep shows that detection remains near zero at 0.5%-5% target OOD alarm and recovers to 0.6516 only when the target alarm is relaxed to 10%. We therefore treat this as a real operating-point effect caused by OOD-tail-dominated thresholding, not as a cache, index, score-direction, or threshold-leakage bug.

## 6. Conservative Writing Boundary

Use this wording:
- "The sanity audit supports interpreting dA collapse as an operating-point effect under strict low-OOD-alarm constraints."
- "The audit did not find cache alignment, attack index, score-direction, or threshold-leakage evidence that would invalidate the dA reference."
- "Legacy transformer/tailreg caches show compatible behavior but are only auxiliary because their ID cache is not the current official split."

Avoid this wording:
- "All modern unsupervised baselines are fully audited at raw-score level."
- "The audit proves every historical transformer result is current-split clean."
- "The collapse is a universal law rather than a protocol-specific low-alarm effect."
- "Few-shot target alignment completely solves open-world anomaly detection."

## 7. Verdict

`collapse_likely_real_operating_point_effect`

