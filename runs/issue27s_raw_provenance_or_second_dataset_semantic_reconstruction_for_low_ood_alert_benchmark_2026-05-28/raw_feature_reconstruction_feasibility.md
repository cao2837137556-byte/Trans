# Raw Feature Reconstruction Feasibility

Stage verdict: `raw_reconstruction_blocked_missing_raw`.

Extractor code exists, but full Mirai raw input is missing. Therefore the next action is not model training; it is data acquisition or reconstruction feasibility:

1. Recover the raw pcap or packet/flow stream that generated `Mirai_dataset.csv`.
2. Verify row alignment against `Mirai_dataset.csv` and `mirai_labels.csv`.
3. Generate a sidecar with packet id, timestamp, label, source/capture/session, split role, and feature hash.
4. Run a small extractor smoke before any full feature rebuild.
5. Only then consider split-aware feature extraction (`reset_at_split_boundary`, `train_state_then_eval_online`).

Slurm is not needed for this decision issue. It is likely needed for full re-extraction if raw input is recovered.
