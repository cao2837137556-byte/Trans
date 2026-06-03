# Issue27am Summary

1. issue27am completed: yes
2. primary_verdict: `medium_repair_insufficient_pause_feature_state_onset_audit`
3. scope: medium bounded protocol repair validation; not formal benchmark
4. frontend: fixed Gotham Kitsune115 115D; no frontend changes
5. split/support pool changed: no
6. support selectors tested: kcenter32, stratified_kcenter64, stratified_kcenter128
7. support_val split seeds: 42, 43, 44
8. threshold rules tested: support_val_constrained_threshold, NP/order-statistic OOD threshold
9. HistGB best support-val worst-case signal: 0.625000
10. HistGB best report-only attack worst-case signal: 0.405333
11. DeepSADMarginLite executed: True
12. online sanity executed: True
13. forbidden role access detected: False
14. best diagnostic recipe: `histgb_stratified_kcenter64_np_orderstat`
15. best diagnostic strategy: `reset_at_split_boundary`
16. best final OOD alarm max report-only: 0.004667
17. best attack detection worst report-only: 0.085333
18. highest attack recipe regardless of final OOD: `histgb_stratified_kcenter128_supportval`
19. highest attack worst report-only: 0.405333
20. highest attack final OOD max report-only: 0.019000
21. next action: `issue27an_feature_state_onset_or_protocol_repair_reassessment`
22. commit hash: pending
