# TON Threshold Sensitivity Summary

- Source run: `second_environment_toniot_object_prerun_2026-04-21_stability`
- Output run: `second_environment_toniot_threshold_sensitivity_2026-04-21`
- Objects: `dA, strongest_candidate_transformer_covreg_v2_seed101, ft_transformer_ae`
- Operators audited: `>`, `>=`

## Quick Check (FT fixed_id_q99)
- `neg_raw_score` / `>`: id=0.005750, ood=0.000000, attack=0.000000, chosen=True
- `neg_raw_score` / `>=`: id=0.196500, ood=0.000000, attack=0.000000, chosen=True
- `raw_score` / `>`: id=0.010000, ood=0.005125, attack=0.008167, chosen=False
- `raw_score` / `>=`: id=0.010000, ood=0.005125, attack=0.008167, chosen=False

## FT Tie Profile
- `neg_raw_score`: eq@q99=0.190750, gt@q99=0.005750, ge@q99=0.196500, chosen=True
- `raw_score`: eq@q99=0.000000, gt@q99=0.010000, ge@q99=0.010000, chosen=False
