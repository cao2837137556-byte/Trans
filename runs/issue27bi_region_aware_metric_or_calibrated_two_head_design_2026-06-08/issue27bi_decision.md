# issue27bi Decision

primary_verdict = `metric_or_calibrated_two_head_no_sufficient_attack_recovery`

- best_candidate = `logistic_twohead_fusion_uniform_rows__ood_val_only`
- best dev_attack_hard_min_min = `0.6428571428571429`
- best report_only_attack_hard_min_min = `0.9373333333333334`
- best ood_dev_alarm_max_max = `0.24421052631578946`
- This is a medium diagnostic, not formal benchmark.
- It does not alter the Kitsune115 frontend, split, or support pool.
- Final/report-only roles are score-only replay and are not used for threshold/model selection.
