# Full Mirai Split-Aware Rebuild Feasibility

Split-aware rebuild is blocked from the current feature CSV alone.

`reset_at_split_boundary` and `train_state_then_eval_online` require packet-level or extractor-level inputs such as packet order, addresses/ports/channels, timestamps, and the exact Kitsune frontend implementation. A 115D/116D feature matrix is already downstream of the stateful frontend and cannot prove reset/online-state behavior by itself.

Slurm is not needed for this audit. It is likely needed if we run full front-end re-extraction over the 764k-row asset or over raw pcap.
