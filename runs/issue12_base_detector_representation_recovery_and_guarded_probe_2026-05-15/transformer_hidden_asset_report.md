# Transformer Hidden Asset Report

- Checkpoint: `D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\runs\frontend100_tailreg_stage1_2026-03-27\transformer_seed42\kitnet_transformer_seed42.ckpt`
- Model source: `D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master\repo\Trans.py`
- Hidden source: outputLayer Transformer encoder mean-pooled representation before output_net.
- Primary hidden policy: one pre-specified representation only; no layer search.
- Hidden extraction training performed: False.
- Score consistency tolerance: `1e-06`.
- ID hidden: `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline\runs\issue12_base_detector_representation_recovery_and_guarded_probe_2026-05-15\hidden_cache\transformer_outputlayer_meanpooled_hidden_id.npy` shape `(50000, 16)`
- OOD hidden: `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline\runs\issue12_base_detector_representation_recovery_and_guarded_probe_2026-05-15\hidden_cache\transformer_outputlayer_meanpooled_hidden_ood.npy` shape `(20000, 16)`
- Attack hidden: `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline\runs\issue12_base_detector_representation_recovery_and_guarded_probe_2026-05-15\hidden_cache\transformer_outputlayer_meanpooled_hidden_attack.npy` shape `(10000, 16)`
- Score consistency pass: `True`.
