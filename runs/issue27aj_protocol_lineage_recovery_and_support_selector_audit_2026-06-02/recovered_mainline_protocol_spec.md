# Recovered Mainline Protocol Spec

## Primary Verdict

`recovered_kcenter_mainline_protocol_ready_for_gotham115_migration`

## Recovered Old Mainline

The strongest historical evidence points to:

`selected_source_rich_top64 + kcenter32 + fixed OOD guard LR`

This is the old LOW-GUARD-LR / Enhanced LOW-GUARD+ mainline protocol, not the
current Gotham `fixed_first32` diagnostic placeholder.

## Support Selector

- Selector: `kcenter32`
- Budget: 32 attack support rows
- Source pool: train-side attack pool only
- Code: `issue19b.kcenter_support(train_rows, train_x_raw, budget)`
- Selector scaling: `StandardScaler().fit(train_x_raw)` inside the selector
- Distance: Euclidean farthest-first after selector-local standardization
- Initialization: closest point to the standardized attack-pool centroid
- Output: sorted selected global row indices
- Eval access: no attack eval and no final OOD eval

The executable lineage is used by issue23 and issue25c. issue25c explicitly
records `M2_Enhanced_LOW_GUARD_top64_fixed_guard_LR` as `main_method` with
`support_method=kcenter` and `support_count=32`. The `random32` rule is
recorded as a support ablation, not as the main protocol.

## Guarded Head And Threshold

- Model/head: fixed OOD guard LR / LOW-GUARD-LR minimal guarded instance
- Model scaler: `StandardScaler` fit only on the training matrix
  (`ID benign train + OOD benign train + selected local attack supports`)
- Threshold rule: ID calibration + OOD validation at the official 1% OOD
  alarm target
- Score direction: higher score means more attack/anomalous; detection uses
  `attack_score > threshold`
- Final eval: final OOD eval and final attack eval are report-only and not used
  for feature, support, threshold, hyperparameter, model, or route selection

## Evidence Files

- `runs/issue23_locked_validation_for_enhanced_v2_top64_2026-05-18/protocol.md`
- `runs/issue23_locked_validation_for_enhanced_v2_top64_2026-05-18/run_issue23_locked_validation.py`
- `runs/issue23_locked_validation_for_enhanced_v2_top64_2026-05-18/support_id_provenance.csv`
- `runs/issue25c_strong_baseline_pack_execution_for_enhanced_lowguard_top64_2026-05-18/baseline_candidate_definitions.csv`
- `runs/issue25c_strong_baseline_pack_execution_for_enhanced_lowguard_top64_2026-05-18/summary.md`
- `runs/issue25c_strong_baseline_pack_execution_for_enhanced_lowguard_top64_2026-05-18/run_issue25c_strong_baselines.py`
- `runs/mainline_docs/mainline_experiment_map.md`

## What Remains Uncertain

- The old frontend was not Gotham Kitsune115. Historical performance numbers
  cannot be migrated as Gotham results.
- Historical state strategy was based on static feature assets. Gotham must use
  the issue27af/issue27ag split-aware/state-aware Kitsune115 asset contracts.
- The selector can migrate, but old source-rich feature selection cannot be
  reused as a Gotham claim.
