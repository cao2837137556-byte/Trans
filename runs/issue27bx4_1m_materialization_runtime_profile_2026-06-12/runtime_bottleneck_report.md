# Runtime Bottleneck Report

This run attempted a strict 1,000,000-row Gotham Kitsune115 larger sanity runtime profile using the issue27bw contract and the issue27bx3 500k cache as read-only acceleration.

## Completed Before Interrupt

- Completed rows: 845000 / 1000000
- Completed ratio: 0.845
- Fully completed roles before interrupt: attack_support_candidate_pool, id_benign_calib, id_benign_train, ood_benign_stress, ood_benign_val, sealed_final_attack, sealed_final_ood
- Partial role: dev_future_attack_query

## Bottleneck

The run was stopped manually after the file `processed/iotsim-building-monitor-1.csv` in role `dev_future_attack_query` stayed active for more than 70 minutes of local CPU time without completing its 80,000-row target. The process was responsive and stderr was empty, so this is recorded as a local runtime bottleneck, not a data corruption error.

The strict PCAP mapping for this file is `raw/malicious/mirai-infection/iotsim-building-monitor-1_0-0_to_OpenvSwitch-28_1-0.pcap`. The run did not switch to another role, did not borrow rows from sealed final sets, and did not downgrade the split contract to force success.

## Cleanliness Decision

The interrupted canonical files were renamed with `INCOMPLETE_INTERRUPTED_` and must not be used as model-ready assets. Completed per-file caches remain available for future cache-aware retries.

## Recommended Fix

Next step should optimize or isolate this runtime bottleneck before treating 1M as model-ready:

1. Add per-file progress/checkpoint logging during PCAP emission.
2. Add a per-file wall-time budget and partial-cache quarantine.
3. Profile `RestoredNetStat115.update` on building-monitor traffic.
4. Retry a strict 1M asset with either optimized local extraction or Slurm for high-cost attack files.
