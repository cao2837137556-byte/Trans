# Config Freeze Decision Report

## Frozen Config

- candidate family: `LOW-GUARD-HistGB-Conservative + original100`
- frozen_config_id: `histgb_d2_lr005_l2p1_ood4_sup4_t0050`
- freeze_success: `true`
- final_eval_used_for_freeze: `false`

## Why B was frozen

Both A and B were feasible under the primary 0.0075 validation-side target in all 12 issue27d traces. B is uniquely selected by the next rules: it has strictly lower OOD_val alarm/tail, higher support_val detection, and a more conservative pre-registered threshold target.

| config_id | validation_feasible_count_0075 | ood_val_alarm_mean | ood_val_alarm_max | ood_val_q99_max | support_val_detection_mean | support_val_margin_mean | validation_target |
|---|---|---|---|---|---|---|---|
| histgb_d2_lr003_l2p0_ood4_sup2_t0100 | 12 | 0.002792 | 0.006500 | 0.000874 | 0.854167 | 0.853829 | 0.010000 |
| histgb_d2_lr005_l2p1_ood4_sup4_t0050 | 12 | 0.000000 | 0.000000 | 0.000119 | 1.000000 | 0.995814 | 0.005000 |


## Rule Checklist

| rule_order | rule | config_a | config_b | winner | uses_final_eval | decision |
|---|---|---|---|---|---|---|
| 1 | validation_feasibility_count_at_primary_0075 | 12 | 12 | tie | False | both configs feasible in all 12 train/validation-side traces |
| 2 | ood_val_safety | max=0.006500,mean=0.002792 | max=0.000000,mean=0.000000 | B | False | B has zero OOD_val alarms and lower OOD tail; freeze can be made here |
| 3 | support_side_separation | det=0.854167,margin=0.853829 | det=1.000000,margin=0.995814 | B | False | B has higher support_val_detection and comparable/higher margin on all trace rows |
| 4 | target_conservativeness | 0.010000 | 0.005000 | B | False | B uses pre-registered 0.005 target; A uses 0.010 target |
| 5 | simplicity_tiebreaker | depth=2,lr=0.03,l2=0.0,support_weight=2 | depth=2,lr=0.05,l2=0.1,support_weight=4 | not_needed | False | not reached because OOD safety/support/target already identify B |
