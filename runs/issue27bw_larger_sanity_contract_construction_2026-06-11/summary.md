# issue27bw Summary

1. issue27bw completed: yes
2. primary_verdict: `larger_sanity_contract_ready_for_materialization_not_formal_benchmark`
3. task type: larger sanity data contract construction
4. model run: no
5. 115D frontend changed: no
6. split/support materialized: no
7. all processed CSV covered by source manifest: 78 files, 35,134,281 rows
8. all-benign / mixed-attack files: 70 / 8
9. recommended larger sanity size: 3M-8M model-ready 115D rows first, hard ceiling 10M without new confirmation
10. full processed corpus size: 35,134,281 rows; do not jump directly to full/formal benchmark
11. fixed support mode defined: yes, budgets 32/64/128/256 from development-side attack support candidates only
12. active update mode defined: yes, separate diagnostic with bounded analyst-label budgets 32/64/128/256
13. sealed final OOD files: `processed/iotsim-ip-camera-museum-2.csv`, `processed/iotsim-ip-camera-street-2.csv`
14. sealed final attack files: `processed/iotsim-ip-camera-street-1.csv`
15. final seal caveat: sealed from issue27bw forward, not pristine formal final across whole project history
16. time-forward status: blocked at file-manifest level because timestamps are missing/unparsed in the file summary; larger materialization must use row order/sidecar and state logs
17. largest risk: Gotham has only 8 mixed attack CSV files, so attack final diversity is limited and formal final may require new holdout policy or external dataset
18. next recommended issue: `issue27bx_larger_sanity_materialization_dry_run_from_contract_v1`
19. commit/push: not performed by request
