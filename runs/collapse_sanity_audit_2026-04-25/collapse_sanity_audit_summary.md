# Collapse Sanity Audit Summary

Run tag: `collapse_sanity_audit_2026-04-25`

Scope:
- No new model training.
- No threshold tuning for rescue.
- Existing score caches were read where available.
- Models without retained per-sample raw score caches are marked as result-level only.

## Verdict

`collapse_likely_real_operating_point_effect`

Evidence:
- dA attack cache exactly matches stage1 `da_attack_scores.npy`: `True`.
- Attack source rows: `10000`; dA/transformer attack score lengths align to this row order where raw caches exist.
- Stage2 high-purity indices: total `6871`, train `4122`, val `1374`, eval `1375`; all in range: `True`; duplicates: `0`.
- dA official cache has AUC above 0.5 and guarded collapse with OOD-tail dominance, so it is not a score-direction bug.
- Legacy transformer/tailreg caches also show AUC above 0.5, but their ID caches are only 5000 rows and are not current official split inputs; they are auxiliary sanity evidence only.

## Raw-Score Guarded Summary

| model | protocol scope | AUC attack-vs-OOD | guarded final OOD alarm | guarded attack detection | attack median - threshold | flags |
|---|---|---:|---:|---:|---:|---|
| `dA_official_reference` | `current_official_split` | 0.806365 | 0.010800 | 0.002909 | -2275.376943 | `threshold_too_strict_not_direction_bug;OOD_tail_dominates_threshold` |
| `transformer_seed42` | `legacy_partial_id_cache` | 0.554154 | 0.014733 | 0.002909 | -590.043788 | `threshold_too_strict_not_direction_bug;OOD_tail_dominates_threshold;legacy_partial_id_cache_not_current_split` |
| `transformer_tailreg_seed42` | `legacy_partial_id_cache` | 0.454820 | 0.014733 | 0.002909 | -590.042417 | `possible_score_direction_issue;OOD_tail_dominates_threshold;legacy_partial_id_cache_not_current_split` |

Interpretation:
- `threshold_too_strict_not_direction_bug` means ranking is not reversed, but the selected low-alarm threshold sits above the attack median.
- `OOD_tail_dominates_threshold` means the OOD tail intrudes into or above the attack score mass and drives a stricter threshold.
- `legacy_partial_id_cache_not_current_split` marks old transformer caches that cannot be treated as current official split evidence.

## Operating-Point Sweep

The sweep uses ID calibration + OOD validation only for threshold selection; final OOD eval and attack eval are not used.
Target OOD alarm levels: `0.5%`, `1%`, `2%`, `5%`, `10%`.

- `dA_official_reference` detection by target alarm: 0.5% -> 0.0000, 1.0% -> 0.0029, 2.0% -> 0.0029, 5.0% -> 0.0095, 10.0% -> 0.6516
- `transformer_seed42` detection by target alarm: 0.5% -> 0.0029, 1.0% -> 0.0029, 2.0% -> 0.0029, 5.0% -> 0.0109, 10.0% -> 0.5280
- `transformer_tailreg_seed42` detection by target alarm: 0.5% -> 0.0029, 1.0% -> 0.0029, 2.0% -> 0.0029, 5.0% -> 0.0109, 10.0% -> 0.4684

## Threshold Selection Logic

- `fixed_id_calib_q99` uses ID calibration only.
- `guarded_id_calib_and_ood_val_target1pct` uses ID calibration plus OOD validation only.
- For the current dA official split: ID calibration is `[10000,15000)`, OOD validation is `[8000,10000)`, final OOD eval is `[10000,20000)`.
- Final OOD eval does not participate in threshold selection.
- Attack eval does not participate in threshold selection.

## Cache / Protocol Findings

- No evidence of dA attack cache row-order mismatch was found.
- No evidence of stage2 high-purity index out-of-range or duplicates was found.
- Transformer/tailreg legacy raw caches have only 5000 ID scores, so their raw-sweep rows are retained as auxiliary sanity evidence, not current official protocol evidence.
- Deep SVDD, FT Transformer, original100 few-shot logistic, and source_rich few-shot logistic do not retain per-sample raw score vectors in the available packages; they are result-level checks only.

## Files

- `score_cache_alignment_check.csv`
- `score_distribution_threshold_audit.csv`
- `operating_point_sweep.csv`
- `attack_index_integrity_check.json`
