# Task Boundary Audit Report

boundary_verdict = `task_boundary_high_distribution_shift_no_role_leakage`

- Stage 1 used report-only roles for attribution only, not for selection.
- Dev pseudo/query being harder than report-only is treated as a possible reason for issue27bi's dev/report gap, not as permission to tune on report-only.
- Stage 2 was allowed because no forbidden role access or missing-role blocker was detected.

Boundary notes:

High distribution-shift notes:
- seed_42:medium_support_train->medium_pseudo_query_dev:dist=8.103:auc=0.904
- seed_42:medium_support_train->medium_attack_eval_report_only:dist=311.545:auc=0.907
- seed_42:heavy_support_train->heavy_pseudo_query_dev:dist=9.856:auc=1.000
- seed_42:heavy_support_train->dev_heavy_query_report_only:dist=489.103:auc=0.983
- seed_42:medium_pseudo_query_dev->medium_attack_eval_report_only:dist=509.378:auc=0.934
- seed_42:heavy_pseudo_query_dev->dev_heavy_query_report_only:dist=599.547:auc=0.887
- seed_43:medium_support_train->medium_pseudo_query_dev:dist=7.843:auc=0.971
- seed_43:medium_support_train->medium_attack_eval_report_only:dist=456.759:auc=0.922
- seed_43:heavy_support_train->heavy_pseudo_query_dev:dist=128.672:auc=1.000
- seed_43:heavy_support_train->dev_heavy_query_report_only:dist=603.580:auc=0.867
- seed_43:medium_pseudo_query_dev->medium_attack_eval_report_only:dist=304.698:auc=0.922
- seed_43:heavy_pseudo_query_dev->dev_heavy_query_report_only:dist=377.745:auc=0.979
- seed_44:medium_support_train->medium_attack_eval_report_only:dist=328.675:auc=0.924
- seed_44:heavy_support_train->heavy_pseudo_query_dev:dist=8.353:auc=1.000
- seed_44:heavy_support_train->dev_heavy_query_report_only:dist=397.403:auc=0.981
- seed_44:medium_pseudo_query_dev->medium_attack_eval_report_only:dist=451.567:auc=0.894
- seed_44:heavy_pseudo_query_dev->dev_heavy_query_report_only:dist=573.082:auc=0.882
- seed_45:medium_support_train->medium_attack_eval_report_only:dist=311.520:auc=0.917
- seed_45:heavy_support_train->heavy_pseudo_query_dev:dist=147.288:auc=1.000
- seed_45:heavy_support_train->dev_heavy_query_report_only:dist=660.746:auc=0.861
