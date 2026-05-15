# System Role Table

| component | role | not_role |
|---|---|---|
| dA / Transformer | cold-start detector; ordinary anomaly model; low-OOD collapse diagnostic baseline; background generic anomaly monitor; optional representation provider | not fully replaced by GDA-minimal |
| GDA-minimal | deployment-stage few-shot adapter activated after low-OOD degradation evidence and high-purity attack supports are available | not active as the primary alerting model at cold start |
| fixed OOD guard | suppresses OOD benign high-score tail and improves low-alarm feasibility | not a searched global optimum; current fixed mechanism only |
| source_rich | optional representation signal and auditability asset | not a stable universal replacement for original100 |
| Transformer hidden | base-detector representation integration evidence | not currently the strongest improvement source |
| review queue | handles base-high / GDA-low conflicts, protects against unseen anomalies, and motivates issue14 arbitration | not yet experimentally validated in issue13 |
