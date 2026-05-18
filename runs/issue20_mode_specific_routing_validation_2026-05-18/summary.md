# Issue20 Mode-Specific Routing Validation Summary

## Outcome

- Preflight passed: yes.
- Routing rule used final eval: false.
- primary_lowood selected champion: `V1`.
- holdout_bin_2 selected champion: `V1`.
- chrono_late_train_early_eval selected champion: `V1`.
- Routed OOD alarm max across settings: `0.003600`.
- Routed worst-case detection across settings: `0.326409`.
- Always-V1 worst-case detection: `0.326409`.
- Always-V2 worst-case OOD alarm max: `0.015600`.
- Routing matched expected primary/harder-shift pattern: `False`.
- Validation proxy gap present: `True`.
- Strong routing positive: `False`.

## Routed Success Table

| setting | seed_group | selected_champion | attack_high_detection_mean | OOD_high_alarm_mean | OOD_high_alarm_max | feasible_rate | review_rate_OOD_mean | comparison_winner | interpretation |
|---|---|---|---|---|---|---|---|---|---|
| chrono_late_train_early_eval | heldout_47_51 | V1 | 0.679802 | 0.001800 | 0.001800 | 1.000000 | 0.009600 | V1 | feasible routed champion |
| chrono_late_train_early_eval | main_42_46 | V1 | 0.679802 | 0.001800 | 0.001800 | 1.000000 | 0.009600 | V1 | feasible routed champion |
| holdout_bin_2 | heldout_47_51 | V1 | 0.326409 | 0.001100 | 0.001100 | 1.000000 | 0.006800 | V1 | feasible routed champion |
| holdout_bin_2 | main_42_46 | V1 | 0.326409 | 0.001100 | 0.001100 | 1.000000 | 0.006800 | V1 | feasible routed champion |
| primary_lowood | heldout_47_51 | V1 | 0.929455 | 0.003600 | 0.003600 | 1.000000 | 0.013600 | V1 | feasible routed champion |
| primary_lowood | main_42_46 | V1 | 0.929455 | 0.003600 | 0.003600 | 1.000000 | 0.013600 | V1 | feasible routed champion |


## Interpretation

The routing gate is validation-side: it uses V2 OOD validation alarm and V2-vs-V1 attack validation proxy improvement with delta fixed at 0.05. Final OOD eval and final attack eval are not used to select the champion.

This run is not a routing success under the current pre-registered proxy: the routed policy remains feasible because it degenerates to V1, but it fails to activate V2 on holdout_bin_2. This is evidence that the current attack-validation/support proxy is too weak or missing for harder-shift routing, not evidence that V2 is invalid.
