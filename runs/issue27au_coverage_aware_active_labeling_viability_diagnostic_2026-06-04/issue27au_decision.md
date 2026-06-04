# Issue27au Decision

primary_verdict = `active_labeling_viability_supported_but_ood_tail_blocked`

- best dev-query diagnostic row: budget=`16`, threshold_rule=`np_orderstat_id_ood_1pct`
- best dev-query detection_min/mean: `0.991` / `0.9970000000000001`
- best row final_ood_alarm_max: `0.2753333333333333`
- best row OOD-val-safe all seeds: `True`
- best row final-OOD-report-only-safe all seeds: `False`

This result can only decide whether coverage-aware active labeling deserves a cleaner follow-up. It cannot be used as formal performance or mainline confirmation.
