# Issue27d LOW-GUARD Adapter Interface And Model-Specific Objective Smoke Summary

## Verdict

- primary_verdict: `lowguard_plus_plus_candidate_found_with_model_specific_objective`
- recommended_next_action: `issue27e_formal_validation_for_lowguard_plus_plus`

## 1. Adapter interface

The LOW-GUARD adapter interface was implemented and audited with `fit`, `score`, `calibrate`, `evaluate`, and `metadata`. Stage A preflight pass: `True`.

## 2. Interface, score-direction, and leakage risks

- score_direction_fixes: `0`
- score_direction_or_objective_warnings: `2`
- final_eval_selection_violations: `0`
- support_attack_eval_overlaps: `0`

Final OOD eval and attack eval remained report-only.

## 3. Was issue27b failure possibly objective mismatch?

Yes, partially. issue27b used proxies; issue27d replaced them with model-specific-lite objectives. The bounded smoke therefore tests whether the proxy gap was material without pretending to implement full DevNet or full Deep SAD.

## 4. DevNetScore vs old DevNet-like

| head_id | old_proxy_head | old_locked_detection_mean | new_locked_detection_mean | detection_mean_delta | old_locked_detection_min | new_locked_detection_min | detection_min_delta | old_locked_ood_alarm_max | new_locked_ood_alarm_max | ood_alarm_delta | old_feasible_rate | new_feasible_rate | feasible_rate_delta | model_specific_objective_improves_transfer |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| LOW_GUARD_DevNetScore | DevNet_like_MLP | 0.947497 | 0.286255 | -0.661242 | 0.895305 | 0.122066 | -0.773239 | 0.010100 | 0.012900 | 0.002800 | 0.975000 | 0.750000 | -0.225000 | False |


## 5. DeepSADLite vs old center proxy

| head_id | old_proxy_head | old_locked_detection_mean | new_locked_detection_mean | detection_mean_delta | old_locked_detection_min | new_locked_detection_min | detection_min_delta | old_locked_ood_alarm_max | new_locked_ood_alarm_max | ood_alarm_delta | old_feasible_rate | new_feasible_rate | feasible_rate_delta | model_specific_objective_improves_transfer |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| LOW_GUARD_DeepSADLite | DeepSAD_like_center | 0.037650 | 0.026290 | -0.011360 | 0.002805 | 0.000000 | -0.002805 | 0.013400 | 0.008400 | -0.005000 | 0.250000 | 1.000000 | 0.750000 | True |


## 6. HistGB-Conservative vs old HistGB

| head_id | old_proxy_head | old_locked_detection_mean | new_locked_detection_mean | detection_mean_delta | old_locked_detection_min | new_locked_detection_min | detection_min_delta | old_locked_ood_alarm_max | new_locked_ood_alarm_max | ood_alarm_delta | old_feasible_rate | new_feasible_rate | feasible_rate_delta | model_specific_objective_improves_transfer |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| LOW_GUARD_HistGB_Conservative | HistGB_shallow | 0.755626 | 0.659751 | -0.095875 | 0.230047 | 0.040689 | -0.189358 | 0.013900 | 0.006600 | -0.007300 | 0.675000 | 1.000000 | 0.325000 | True |


## 7. PrototypeMargin vs old Prototype

| head_id | old_proxy_head | old_locked_detection_mean | new_locked_detection_mean | detection_mean_delta | old_locked_detection_min | new_locked_detection_min | detection_min_delta | old_locked_ood_alarm_max | new_locked_ood_alarm_max | ood_alarm_delta | old_feasible_rate | new_feasible_rate | feasible_rate_delta | model_specific_objective_improves_transfer |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| LOW_GUARD_PrototypeMargin | Prototype_metric_LR | 0.219025 | 0.067087 | -0.151938 | 0.042254 | 0.004995 | -0.037259 | 0.010900 | 0.015000 | 0.004100 | 0.750000 | 0.833333 | 0.083333 | True |


## 8. original100 vs top64

original100 was included as a representation-control probe. It does not change the claim boundary by itself; it tells us whether non-LR heads gain relative room when top64 is not forcing a more linear representation.

## 9. LOW-GUARD++ candidate

`Yes`. If present, candidate rows are:

| head_id | representation | locked_detection_mean | locked_detection_min | locked_ood_alarm_max | feasible_rate | candidate_type |
|---|---|---|---|---|---|---|
| LOW_GUARD_HistGB_Conservative | original100 | 0.994261 | 0.978091 | 0.005100 | 1.000000 | representation_control_lowguard_plus_plus_candidate |


## 10. Model-specific objective transfer improvement

`3` non-LR head(s) improved relative to issue27b proxy baselines by the pre-registered smoke criterion.

## 11. Can LOW-GUARD continue as multi-head protocol?

`Yes, but only with bounded model-specific objective language and formal validation.`

## 12. LOW-GUARD-LR status

LOW-GUARD-LR remains the strongest minimal reference on the frozen source_rich_top64 input unless the LOW-GUARD++ report contains a top64 dominating non-LR candidate. A representation-control candidate on original100 is important, but it is not an automatic replacement for the frozen top64 main method. In this run, top64 LR smoke mean/min/OOD max is `0.949705` / `0.882629` / `0.004500`.

## 13. Best non-LR top64 head

`LOW_GUARD_HistGB_Conservative`: `0.659751` / `0.040689` / `0.006600`, feasible_rate `1.000000`.

## 14. Issue27e formal validation

Recommendation: `issue27e_formal_validation_for_lowguard_plus_plus`.

## 15. Slurm

Not needed for this bounded smoke. The run used 3 seeds, locked bins 5/6/7/8, top64/original100, and lightweight heads.

## Top summary rows

| head_id | representation | locked_detection_mean | locked_detection_min | locked_ood_alarm_max | feasible_rate | candidate_lowguard_plus_plus | candidate_type |
|---|---|---|---|---|---|---|---|
| LOW_GUARD_HistGB_Conservative | original100 | 0.994261 | 0.978091 | 0.005100 | 1.000000 | True | representation_control_lowguard_plus_plus_candidate |
| LOW_GUARD_LR | original100 | 0.944751 | 0.835681 | 0.005300 | 1.000000 | False | not_candidate |
| LOW_GUARD_PrototypeMargin | original100 | 0.000000 | 0.000000 | 0.016600 | 0.666667 | False | not_candidate |
| LOW_GUARD_DevNetScore | original100 | 0.222063 | 0.021127 | 0.018900 | 0.333333 | False | not_candidate |
| LOW_GUARD_DeepSADLite | original100 | 0.000196 | 0.000000 | 0.017600 | 0.000000 | False | not_candidate |
| LOW_GUARD_LR | source_rich_top64 | 0.949705 | 0.882629 | 0.004500 | 1.000000 | False | not_candidate |
| LOW_GUARD_HistGB_Conservative | source_rich_top64 | 0.659751 | 0.040689 | 0.006600 | 1.000000 | False | not_candidate |
| LOW_GUARD_DeepSADLite | source_rich_top64 | 0.026290 | 0.000000 | 0.008400 | 1.000000 | False | not_candidate |
| LOW_GUARD_PrototypeMargin | source_rich_top64 | 0.067087 | 0.004995 | 0.015000 | 0.833333 | False | not_candidate |
| LOW_GUARD_DevNetScore | source_rich_top64 | 0.286255 | 0.122066 | 0.012900 | 0.750000 | False | not_candidate |
