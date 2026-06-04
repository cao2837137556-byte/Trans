# issue27au Summary

1. issue27au completed: yes
2. primary_verdict: `active_labeling_viability_supported_but_ood_tail_blocked`
3. task type: coverage-aware active labeling viability diagnostic; not formal benchmark
4. support/threshold/model search using final roles: no
5. new heldout probe status: consumed as development-side prospective replay, no longer clean final
6. active candidate stream: first 1000 rows per heavy file, labels hidden during selection
7. dev query stream: remaining heavy rows, report-only
8. best dev-query diagnostic budget: `16`
9. best dev-query detection_min/mean: `0.991` / `0.9970000000000001`
10. best row OOD-val-safe all seeds: `True`
11. best row final-OOD-report-only-safe all seeds: `False`
12. best row final_ood_alarm_max: `0.2753333333333333`
13. formal benchmark allowed: no
14. next action: `issue27av_clean_dev_target_pool_for_coverage_active_labeling_and_ood_tail_repair`
15. commit hash: pending
