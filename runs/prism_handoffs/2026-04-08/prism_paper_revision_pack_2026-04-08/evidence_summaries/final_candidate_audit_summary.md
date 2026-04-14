# Final Candidate Audit Summary

- This package consolidates the current A-tier candidate evidence without new model training.
- 3-seed Transformer ensemble rawq0.999/idq0.995 has alarm=0.1261 and detection=0.8444; dA q99 has alarm=0.1322 and detection=0.8014; dA q995 has alarm=0.1045 and detection=0.7690.
- The claim should be framed as an ID-only operating-region result with 3x Transformer inference cost, not a single-model unconditional q99 win.

## Main Table
| object_label | ood_alarm | high_purity_detection | id_alarm | roc_auc | source | note |
|---|---|---|---|---|---|---|
| external LOF | 0.015533 | 0.000582 | 0.000000 | 0.448771 | external_baselines | minimal external baseline |
| dA fixed_id_q0p995 | 0.104489 | 0.769029 | 0.005000 | 0.809622 | dA_idq_reference | dA same-ID-alarm reference |
| Transformer ensemble mean_gate_rawq0p998/fixed_id_q0p997 | 0.119933 | 0.818804 | 0.003000 | 0.877994 | latent_seed_ensemble_idq_sweep | conservative ID q997 candidate |
| Transformer ensemble mean_gate_rawq0p9995/fixed_id_q0p995 | 0.123067 | 0.824480 | 0.005000 | 0.876983 | latent_seed_ensemble_idq_sweep | lower-alarm candidate |
| Transformer ensemble mean_gate_rawq0p999/fixed_id_q0p995 | 0.126067 | 0.844419 | 0.005000 | 0.878093 | latent_seed_ensemble_idq_sweep | current main candidate |
| dA fixed_id_q0p99 | 0.132156 | 0.801387 | 0.010000 | 0.809622 | dA_idq_reference | dA q99 reference |
| recurrent gru_ae_L4_last | 0.634149 | 0.745112 | 0.010000 | 0.638412 | recurrent_deep_baselines | deep sequence baseline |
| recurrent lstm_ae_L4_last | 0.673046 | 0.831126 | 0.010000 | 0.714129 | recurrent_deep_baselines | deep sequence baseline |


## Cost Table
| object_label | n_checkpoints | relative_forward_passes | checkpoint_bytes | torch_param_count | kitnet_subdetectors | note |
|---|---|---|---|---|---|---|
| dA single seed | 1 | 1 | 147625 | 0 | 19 | dA has numpy AE parameters; torch_param_count not applicable |
| Transformer latent single seed | 1 | 1 | 794317 | 18947 | 19 | transformer_latent_contrastive_v1 |
| Transformer latent 3-seed ensemble | 3 | 3 | 2382951 | 56841 | 57 | current main candidate uses mean of 3 seed scores |


## Score Distribution Stats
| object_label | id_q50 | id_q99 | threshold | ood_eval_q50 | ood_eval_q99 | attack_high_q50 | attack_high_q99 |
|---|---|---|---|---|---|---|---|
| Transformer ensemble rawq0.999 idq0.995 | 0.544082 | 0.994196 | 1.049294 | 0.956117 | 1.556097 | 1.192788 | 1.919345 |
| dA seed101 q99 | 0.020719 | 0.078023 | 0.078023 | 0.060384 | 2373.110110 | 0.157323 | 6.452876 |
| dA seed101 q995 | 0.020719 | 0.078023 | 0.087255 | 0.060384 | 2373.110110 | 0.157323 | 6.452876 |


## Interpretation
- Current strongest paper candidate: `Transformer 3-seed covariance ensemble, rawq=0.999, fixed_id_q0.995`.
- Recurrent AE and simple external baselines do not solve stronger OOD fixed alarms.
- The cost/complexity section must explicitly mention 3 checkpoints / 3 relative forward passes.
