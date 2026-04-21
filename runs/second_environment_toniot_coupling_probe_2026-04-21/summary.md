# TON Coupling Probe Summary

- Run tag: `second_environment_toniot_coupling_probe_2026-04-21`
- Feature views: `standard_zscore, winsor_zscore, signed_log1p_zscore`
- Split: ID-train=4000, ID-eval=2000, OOD-eval=5000, attack-eval=5000

## FT fixed_id_q99
- `signed_log1p_zscore`: ood_alarm=0.099000, attack_det=0.145200, id_alarm=0.010000, auc=0.569140
- `standard_zscore`: ood_alarm=0.000000, attack_det=0.000000, id_alarm=0.010000, auc=0.608058
- `winsor_zscore`: ood_alarm=0.000000, attack_det=0.010200, id_alarm=0.010000, auc=0.525840

## FT naive_budget5000
- `signed_log1p_zscore`: ood_alarm=0.010000, attack_det=0.005200, id_alarm=0.001500, auc=0.569140
- `standard_zscore`: ood_alarm=0.010000, attack_det=0.119000, id_alarm=0.845500, auc=0.608058
- `winsor_zscore`: ood_alarm=0.010000, attack_det=0.160600, id_alarm=0.793000, auc=0.525840
