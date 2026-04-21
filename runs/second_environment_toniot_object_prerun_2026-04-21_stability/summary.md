# TON-IoT Mainline Object Pre-Run Summary

- Run tag: `second_environment_toniot_object_prerun_2026-04-21_stability`
- Split manifest: `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline\runs\second_environment_toniot_precheck_2026-04-20\split_manifest.json`
- Split used: ID-train=8000, ID-eval=4000, OOD-eval=8000, attack-eval=12000
- Numeric feature count: `16`

## Polarity
- `dA`: chosen `neg_raw_score`, auc=0.679894, other=0.320106, delta=0.359789
- `ft_transformer_ae`: chosen `neg_raw_score`, auc=0.570755, other=0.429245, delta=0.141510
- `strongest_candidate_transformer_covreg_v2_seed101`: chosen `neg_raw_score`, auc=0.690065, other=0.309935, delta=0.380131

## Policy Results
- `dA` / `det_floor_50pct_min_alarm`: ood_alarm=0.298500, attack_det=0.501333, id_alarm=0.177000, auc=0.679894
- `dA` / `fixed_id_q99`: ood_alarm=0.007625, attack_det=0.076667, id_alarm=0.010000, auc=0.679894
- `dA` / `naive_calibrated_budget5000_target1pct`: ood_alarm=0.009125, attack_det=0.079167, id_alarm=0.014250, auc=0.679894
- `ft_transformer_ae` / `det_floor_50pct_min_alarm`: ood_alarm=0.444500, attack_det=0.502250, id_alarm=0.610000, auc=0.570755
- `ft_transformer_ae` / `fixed_id_q99`: ood_alarm=0.000000, attack_det=0.000000, id_alarm=0.005750, auc=0.570755
- `ft_transformer_ae` / `naive_calibrated_budget5000_target1pct`: ood_alarm=0.009250, attack_det=0.126000, id_alarm=0.395250, auc=0.570755
- `strongest_candidate_transformer_covreg_v2_seed101` / `det_floor_50pct_min_alarm`: ood_alarm=0.273000, attack_det=0.500000, id_alarm=0.619500, auc=0.690065
- `strongest_candidate_transformer_covreg_v2_seed101` / `fixed_id_q99`: ood_alarm=0.002125, attack_det=0.003333, id_alarm=0.001250, auc=0.690065
- `strongest_candidate_transformer_covreg_v2_seed101` / `naive_calibrated_budget5000_target1pct`: ood_alarm=0.009750, attack_det=0.027917, id_alarm=0.437750, auc=0.690065

## Note
- This node is a local prereun for object comparability and orientation consistency before formal second-environment submission.
