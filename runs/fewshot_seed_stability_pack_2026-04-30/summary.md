# Few-shot Seed Stability Summary

## 1. ?????

???????? seed-level ???????????? LR?????? few-shot ???????? claim?????????????? current split ? `16-shot` / `32-shot` few-shot target alignment ? seed-level ?????? paper-facing ??????? ?lucky seed / lucky split? ???

?????`2026-04-30T12:58:05+08:00`

## 2. ????

original100 official control?

- `D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/original100_fewshot_official_control_2026-04-22/results.csv`
- `D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/original100_fewshot_official_control_2026-04-22/diagnostics.json`
- `D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/original100_fewshot_official_control_2026-04-22/selected_positive_samples.csv`

source_rich v7.2 fairness validation?

- `D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-frontend-f2/runs/frontend_f2_v7_2_fairness_validation_2026-04-22/results.csv`
- `D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-frontend-f2/runs/frontend_f2_v7_2_fairness_validation_2026-04-22/config.json`

Protocol audit inheritance?

- `D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/fewshot_protocol_audit_2026-04-30/threshold_provenance.csv`
- `D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/fewshot_protocol_audit_2026-04-30/support_split_audit.csv`
- `D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/fewshot_protocol_audit_2026-04-30/support_id_provenance/selected_support_ids_full.csv`

## 3. ???????

??????? E3 / E3-b ??????

- final OOD eval ? attack eval ??? threshold selection?
- support IDs ? attack val / final attack eval disjoint?
- `original100` ? `source_rich` ???? positive budgets?positive sampling seeds ? threshold policies?
- fixed threshold = `fixed_id_calib_q99`?guarded threshold = `guarded_id_calib_and_ood_val_target1pct`?

?????

| E2 output field | Source CSV field |
|---|---|
| `auc_attack_vs_ood` | `roc_auc_attack_high_vs_ood_eval` |
| `ood_alarm` | `ood_alarm_ratio_eval` |
| `attack_detection` | `attack_detection_high_purity` |
| `feasible` | `selection_feasible` |

## 4. ?????

??????? guarded threshold policy?`guarded_id_calib_and_ood_val_target1pct`?

### original100 16-shot

- n=5, AUC mean/min/max=0.9907/0.9580/1.0000, OOD alarm mean/max=0.0044/0.0092, detection mean/min=0.9676/0.9142, feasible_rate=1.0000

### original100 32-shot

- n=5, AUC mean/min/max=0.9846/0.9676/0.9999, OOD alarm mean/max=0.0065/0.0098, detection mean/min=0.9407/0.9207, feasible_rate=1.0000

### source_rich 16-shot

- n=5, AUC mean/min/max=0.9776/0.9646/0.9924, OOD alarm mean/max=0.0056/0.0088, detection mean/min=0.9487/0.9273, feasible_rate=1.0000

### source_rich 32-shot

- n=5, AUC mean/min/max=0.9776/0.9682/0.9907, OOD alarm mean/max=0.0074/0.0109, detection mean/min=0.9587/0.9476, feasible_rate=0.8000

Appendix candidate only:

- source_rich 64-shot guarded: n=5, AUC mean/min/max=0.9837/0.9640/0.9974, OOD alarm mean/max=0.0081/0.0142, detection mean/min=0.9516/0.9207, feasible_rate=0.6000

Fixed-threshold rows are also preserved in `seed_summary.csv` and `paper_facing_table.csv`, but the paper-facing main stability claim should prioritize guarded low-OOD-alarm results.

## 5. ??????

- `paper_facing_table.csv`??????????????? compact table????? 16/32-shot guarded rows?
- `seed_summary.csv`????? appendix??? per-seed ???
- `seed_figure.png`??? appendix ??????????? guarded policy ? seed-level ?? mean line?
- `source_rich 64-shot`???? appendix candidate????????
- `source_rich` ???? universal replacement??? paper role ?? complementary hard-holdout robustness / auditability asset?
- `original100` ? official control????? target alignment ??????

## 6. ??

- ??????????????
- ??????? open-world IDS ????
- ??????????? few-shot target alignment ? seed-level ????
- ?????? E3 / E3-b ? no-leakage protocol conclusion?

## 7. Warnings

- None. All required fields were present and seed_figure.png was generated successfully.
- seed_figure.png generated successfully; it focuses on guarded policy and shows seed-level dots plus mean lines.

## 8. E2 Verdict

`fewshot_seed_stability_pack_passed`
