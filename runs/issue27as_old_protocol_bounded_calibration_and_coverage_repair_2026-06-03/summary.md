# issue27as Summary

1. issue27as completed: yes
2. primary_verdict: `bounded_repair_suggests_feature_or_task_boundary`
3. task type: medium bounded calibration/support-influence repair; not formal benchmark
4. frontend/split changed: no
5. model family: old LOW-GUARD++ HistGB skeleton only
6. candidate selection roles: id_calib + ood_val + support_val only
7. final OOD / attack_eval / new heldout used for selection: no
8. selected val-side candidate: `reset_at_split_boundary | support_budget=128 | ood_weight=2.0 | support_weight=4.0 | threshold_rule=support_val_guided_empirical_1pct`
9. support_val_detection_min: `0.96875`
10. report-only final_ood_alarm_max: `0.083`
11. report-only medium attack_eval_detection_min/mean: `0.976` / `0.9891555555555556`
12. report-only new heldout detection_min/mean: `0.1585` / `0.46860000000000007`
13. formal benchmark allowed: no
14. best report-only final-OOD-compliant medium attack min: `0.9302222222222222`
15. best report-only final-OOD-compliant new heldout min: `0.15016666666666667`
16. next action: `issue27at_coverage_aware_support_gap_protocol_design_or_task_boundary_decision`
17. commit hash: pending
