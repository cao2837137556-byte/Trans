# issue27as Bounded Calibration and Coverage Repair Report

primary_verdict = `bounded_repair_suggests_feature_or_task_boundary`

This is a medium diagnostic repair pass, not a formal benchmark. It keeps the Gotham Kitsune115 medium asset, split, frontend, old HistGB skeleton, and report-only final roles fixed.

## Candidate Selection Boundary

- Candidate selection uses only `id_calib`, `ood_val`, and `support_val`.
- `final_ood_benign_eval`, `attack_eval`, and `new_heldout_attack_eval_probe` are report-only.
- No candidate is selected by medium attack_eval or new heldout detection.

## Selected Val-Side Candidate

- selected_by_val_side_only: strategy=`reset_at_split_boundary`, support_budget=`128`, ood_weight=`2.0`, support_weight=`4.0`, threshold_rule=`support_val_guided_empirical_1pct`
- support_val_detection_min/mean: `0.96875` / `0.975`
- id_calib_alarm_max / ood_val_alarm_max: `0.005` / `0.0`
- report-only final_ood_alarm_max: `0.083`
- report-only medium attack_eval_detection_min/mean: `0.976` / `0.9891555555555556`
- report-only new heldout detection_min/mean: `0.1585` / `0.46860000000000007`

## Report-Only Feasibility Check

- best report-only final-OOD-compliant candidate: strategy=`reset_at_split_boundary`, support_budget=`128`, ood_weight=`4.0`, support_weight=`8.0`, threshold_rule=`support_val_guided_empirical_1pct`
- report-only final_ood_alarm_max: `0.007`
- report-only medium attack_eval_detection_min/mean: `0.9302222222222222` / `0.9615111111111112`
- report-only new heldout detection_min/mean: `0.15016666666666667` / `0.15883333333333333`
- This candidate is not selected by report-only performance; it is listed only to quantify whether any legal-looking configuration clears the report-only OOD budget.
