# issue27bq Next Action

recommended_next_action = `issue27bq_ood_risk_scorer_or_task_boundary_repair_before_larger`

- If dev gate passes, run a larger sanity check before any full/formal benchmark.
- If dev OOD remains over budget, repair OOD-risk scorer or OOD stress contract before adding more attack complexity.
- If attack falls below 0.93, the gate is still attack-destructive and must not proceed.
