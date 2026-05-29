# Protocol Reset Rationale

issue20-27n are treated as the exploratory phase. They discovered the LOW-GUARD++ candidate, exposed feature-schema risks, found full Mirai, and clarified why original100 / clean115 / restored115 cannot be mixed.

Full Mirai can still be used as a formal within-dataset benchmark because a protocol reset makes data identity explicit: all methods are retrained from scratch under one declared split, one feature schema, and one final-eval report-only rule.

Full Mirai cannot be called a completely unseen external test because the historical `my_gold` subset is the first 200k rows of the same asset and was used in earlier exploration. The honest framing is protocol-reset within-dataset benchmarking. A second dataset remains necessary for external generalization.
