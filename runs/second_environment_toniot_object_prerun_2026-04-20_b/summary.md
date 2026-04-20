# TON-IoT Mainline Object Pre-Run Summary

- Run tag: `second_environment_toniot_object_prerun_2026-04-20_b`
- Split manifest: `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline\runs\second_environment_toniot_precheck_2026-04-20\split_manifest.json`
- Split used: ID-train=8000, ID-eval=4000, OOD-eval=8000, attack-eval=12000
- Numeric feature count: `16`

## Polarity
- `dA`: chosen `neg_raw_score`, auc=0.679894, other=0.320106, delta=0.359789
- `ft_transformer_ae`: chosen `neg_raw_score`, auc=0.511384, other=0.488616, delta=0.022768
- `strongest_candidate_transformer_covreg_v2_seed101`: chosen `neg_raw_score`, auc=0.668993, other=0.331007, delta=0.337986

## Policy Results
- `dA` / `det_floor_50pct_min_alarm`: ood_alarm=0.298500, attack_det=0.501333, id_alarm=0.177000, auc=0.679894
- `dA` / `fixed_id_q99`: ood_alarm=0.007625, attack_det=0.076667, id_alarm=0.010000, auc=0.679894
- `dA` / `naive_calibrated_budget5000_target1pct`: ood_alarm=0.009125, attack_det=0.079167, id_alarm=0.014250, auc=0.679894
- `ft_transformer_ae` / `det_floor_50pct_min_alarm`: ood_alarm=0.480000, attack_det=0.500833, id_alarm=0.531750, auc=0.511384
- `ft_transformer_ae` / `fixed_id_q99`: ood_alarm=0.000000, attack_det=0.000000, id_alarm=0.001000, auc=0.511384
- `ft_transformer_ae` / `naive_calibrated_budget5000_target1pct`: ood_alarm=0.010875, attack_det=0.011750, id_alarm=0.419250, auc=0.511384
- `strongest_candidate_transformer_covreg_v2_seed101` / `det_floor_50pct_min_alarm`: ood_alarm=0.333125, attack_det=0.501917, id_alarm=0.681250, auc=0.668993
- `strongest_candidate_transformer_covreg_v2_seed101` / `fixed_id_q99`: ood_alarm=0.014125, attack_det=0.000000, id_alarm=0.010000, auc=0.668993
- `strongest_candidate_transformer_covreg_v2_seed101` / `naive_calibrated_budget5000_target1pct`: ood_alarm=0.010625, attack_det=0.000000, id_alarm=0.006500, auc=0.668993

## Note
- This node is a local prereun for object comparability and orientation consistency before formal second-environment submission.
