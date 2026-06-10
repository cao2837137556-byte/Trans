# Claim Update After issue27br

- issue27br only tests whether past-only temporal/source evidence is available and useful as an auxiliary signal.
- It cannot prove graph/causal detection, because current materialized sidecar lacks IP/port/flow interaction fields.
- It preserves final/report-only independence: final OOD and sealed attack replay do not select temporal thresholds.
