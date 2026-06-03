# Issue27am Decision

- primary_verdict: `medium_repair_insufficient_pause_feature_state_onset_audit`
- verdict_reason: OOD<=1% held but attack detection stayed below 0.6
- Scope: medium bounded protocol repair validation only; not formal benchmark.
- Frontend: fixed Gotham Kitsune115 medium asset from issue27af.
- Split/support pool: unchanged; support selection only uses attack_support.
- Selection roles: threshold uses ID/OOD/support_val only; final_ood_benign_eval and attack_eval are report-only.

## Best Pre-Registered Diagnostic Row

- strategy: `reset_at_split_boundary`
- model: `HistGB`
- recipe: `histgb_stratified_kcenter64_np_orderstat`
- support_val_detection_worst: 0.312500
- attack_eval_detection_worst_report_only: 0.085333
- final_ood_alarm_max_report_only: 0.004667
- empirical_ood_val_feasible_all_seeds: True

## Highest Attack Diagnostic Row

- strategy: `reset_at_split_boundary`
- model: `HistGB`
- recipe: `histgb_stratified_kcenter128_supportval`
- attack_eval_detection_worst_report_only: 0.405333
- final_ood_alarm_max_report_only: 0.019000
- Interpretation: useful as an overbudget diagnostic only if final OOD exceeds 1%.
