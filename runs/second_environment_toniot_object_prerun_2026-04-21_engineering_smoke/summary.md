# TON-IoT Mainline Object Pre-Run Summary

- Run tag: `second_environment_toniot_object_prerun_2026-04-21_engineering_smoke`
- Split manifest: `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline\runs\second_environment_toniot_precheck_2026-04-20\split_manifest.json`
- Split used: ID-train=4000, ID-eval=2000, OOD-eval=5000, attack-eval=5000
- Numeric feature count: `16`

## Polarity
- `dA`: chosen `neg_raw_score`, auc=0.715330, other=0.284670, delta=0.430660
- `ft_transformer_ae`: chosen `neg_raw_score`, auc=0.623945, other=0.376055, delta=0.247890
- `strongest_candidate_transformer_covreg_v2_seed101`: chosen `neg_raw_score`, auc=0.663070, other=0.336930, delta=0.326140

## Policy Results
- `dA` / `det_floor_50pct_min_alarm`: ood_alarm=0.268800, attack_det=0.501400, id_alarm=0.869000, auc=0.715330
- `dA` / `fixed_id_q99`: ood_alarm=0.000000, attack_det=0.000600, id_alarm=0.010000, auc=0.715330
- `dA` / `naive_calibrated_budget5000_target1pct`: ood_alarm=0.010000, attack_det=0.189200, id_alarm=0.819500, auc=0.715330
- `ft_transformer_ae` / `det_floor_50pct_min_alarm`: ood_alarm=0.319400, attack_det=0.501200, id_alarm=0.919000, auc=0.623945
- `ft_transformer_ae` / `fixed_id_q99`: ood_alarm=0.000000, attack_det=0.000000, id_alarm=0.000500, auc=0.623945
- `ft_transformer_ae` / `naive_calibrated_budget5000_target1pct`: ood_alarm=0.010000, attack_det=0.153200, id_alarm=0.835000, auc=0.623945
- `strongest_candidate_transformer_covreg_v2_seed101` / `det_floor_50pct_min_alarm`: ood_alarm=0.353600, attack_det=0.500200, id_alarm=0.096500, auc=0.663070
- `strongest_candidate_transformer_covreg_v2_seed101` / `fixed_id_q99`: ood_alarm=0.018000, attack_det=0.019200, id_alarm=0.010000, auc=0.663070
- `strongest_candidate_transformer_covreg_v2_seed101` / `naive_calibrated_budget5000_target1pct`: ood_alarm=0.010000, attack_det=0.009000, id_alarm=0.008500, auc=0.663070

## Note
- This node is a local prereun for object comparability and orientation consistency before formal second-environment submission.
