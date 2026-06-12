# issue27bx2 Decision

primary_verdict: `quota_cache_repair_ready_for_500k_materialization_retry`

The previous issue27bx partial result is attributable to quota planning and local PCAP materialization cost. The next retry should use capacity-aware quotas and per-file cache keys before any larger replay.

This decision does not validate model performance and does not authorize formal benchmark.
