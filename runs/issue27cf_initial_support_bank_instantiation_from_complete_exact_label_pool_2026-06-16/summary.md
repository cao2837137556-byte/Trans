# issue27cf Summary

1. issue27cf completed: `true`.
2. primary_verdict: `support_bank_instantiated_ready_for_query_alignment_repair`.
3. task type: initial pre-deployment support bank instantiation.
4. model training: forbidden and not performed.
5. detection metrics: forbidden and not computed.
6. final/report-only access: forbidden and not performed.
7. eligible support candidate rows: `69492`.
8. selected support bank rows: `512`.
9. support_train rows: `385`.
10. support_val rows: `127`.
11. exact attack labels covered: `10`.
12. semantic groups covered: `['merlin', 'mirai', 'tooling']`.
13. candidate reuse: `pending_forbidden_until_explicit_issue`.
14. dev_future_query use: `not used`.
15. sealed final use: `not used`.
16. invariant errors: `0`.

Close-out:

```text
solved: Instantiated a clean initial pre-deployment support bank from the complete exact-label support candidate pool.
changed_mainline: yes
active_blocker: dev_future_attack_query combined-cycle-1 alignment remains partial and must be repaired before model replay.
frozen: selected initial support bank rows, support_train/support_val partitions, taxonomy summaries, output hashes.
superseded: using the whole attack candidate pool as support; using old coarse attack support roles.
next_action: issue27cg_combined_cycle_query_alignment_repair_or_replan.
```
