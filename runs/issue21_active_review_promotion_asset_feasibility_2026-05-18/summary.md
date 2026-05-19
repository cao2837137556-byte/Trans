# Issue21 Active Review Promotion Asset Feasibility Summary

## Outcome

- Preflight passed: yes.
- Promotion asset gap: none blocking for feasibility simulation.
- Final eval used for promotion evidence: no.
- V1/V2 definitions changed: no.
- issue20/20b proxy failure retained: yes.
- Best candidate summary: `R1_kcenter_confirmed_attack_validation k=4 delta=0.05`.
- Strong/moderate positive candidate exists: `False`.
- Interpretation: `current active evidence assets do not cleanly repair proxy failure`.
- Recommended next step: `weaken_routing_claim_or_recover_stronger_promotion_validation_assets`.

## Top Evidence-Gated Candidates

| evidence_strategy | k | delta_threshold | primary_selects_v1_rate | holdout_bin2_selects_v2_rate | chrono_selects_v2_rate | overall_selection_correct_rate | final_ood_alarm_max | feasible_rate | label_efficiency |
|---|---|---|---|---|---|---|---|---|---|
| R1_kcenter_confirmed_attack_validation | 4 | 0.050000 | 1.000000 | 0.000000 | 0.000000 | 0.333333 | 0.003600 | 1.000000 | 1.000000 |
| R1_kcenter_confirmed_attack_validation | 4 | 0.100000 | 1.000000 | 0.000000 | 0.000000 | 0.333333 | 0.003600 | 1.000000 | 1.000000 |
| R1_kcenter_confirmed_attack_validation | 4 | 0.200000 | 1.000000 | 0.000000 | 0.000000 | 0.333333 | 0.003600 | 1.000000 | 1.000000 |
| R0_random_confirmed_attack_validation | 8 | 0.200000 | 1.000000 | 0.000000 | 0.000000 | 0.333333 | 0.003600 | 1.000000 | 1.000000 |
| R1_kcenter_confirmed_attack_validation | 8 | 0.200000 | 1.000000 | 0.000000 | 0.000000 | 0.333333 | 0.003600 | 1.000000 | 1.000000 |
| R0_random_confirmed_attack_validation | 16 | 0.100000 | 1.000000 | 0.000000 | 0.000000 | 0.333333 | 0.003600 | 1.000000 | 1.000000 |
| R0_random_confirmed_attack_validation | 16 | 0.200000 | 1.000000 | 0.000000 | 0.000000 | 0.333333 | 0.003600 | 1.000000 | 1.000000 |
| R1_kcenter_confirmed_attack_validation | 16 | 0.100000 | 1.000000 | 0.000000 | 0.000000 | 0.333333 | 0.003600 | 1.000000 | 1.000000 |
| R1_kcenter_confirmed_attack_validation | 16 | 0.200000 | 1.000000 | 0.000000 | 0.000000 | 0.333333 | 0.003600 | 1.000000 | 1.000000 |
| R0_random_confirmed_attack_validation | 32 | 0.200000 | 1.000000 | 0.000000 | 0.000000 | 0.333333 | 0.003600 | 1.000000 | 1.000000 |
| R1_kcenter_confirmed_attack_validation | 32 | 0.100000 | 1.000000 | 0.000000 | 0.000000 | 0.333333 | 0.003600 | 1.000000 | 1.000000 |
| R1_kcenter_confirmed_attack_validation | 32 | 0.200000 | 1.000000 | 0.000000 | 0.000000 | 0.333333 | 0.003600 | 1.000000 | 1.000000 |
| R0_random_confirmed_attack_validation | 4 | 0.050000 | 0.900000 | 0.000000 | 0.000000 | 0.300000 | 0.015600 | 0.966667 | 1.000000 |
| R0_random_confirmed_attack_validation | 4 | 0.100000 | 0.900000 | 0.000000 | 0.000000 | 0.300000 | 0.015600 | 0.966667 | 1.000000 |
| R0_random_confirmed_attack_validation | 4 | 0.200000 | 0.900000 | 0.000000 | 0.000000 | 0.300000 | 0.015600 | 0.966667 | 1.000000 |


## Chosen Candidate By Setting

| setting | selected_champion | selection_correct_rate | final_attack_detection | final_ood_alarm | feasible_rate | confirmed_attack_count |
|---|---|---|---|---|---|---|
| chrono_late_train_early_eval | V1 | 0.000000 | 0.679802 | 0.001800 | 1.000000 | 4.000000 |
| holdout_bin_2 | V1 | 0.000000 | 0.326409 | 0.001100 | 1.000000 | 4.000000 |
| primary_lowood | V1 | 1.000000 | 0.929455 | 0.003600 | 1.000000 | 4.000000 |


## Research Interpretation

This run estimates whether small confirmed evidence budgets can repair the promotion-trigger gap. The key question is not whether V2 is good on final metrics, but whether V2 can be promoted using non-final evidence without mis-promoting primary_lowood. If no strategy achieves that, the routing claim should be weakened or the promotion assets must be improved before issue22.
