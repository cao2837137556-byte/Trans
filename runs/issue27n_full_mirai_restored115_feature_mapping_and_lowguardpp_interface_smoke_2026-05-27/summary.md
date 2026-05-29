# issue27n Full Mirai restored115 Mapping and Interface Smoke Gate

## Verdict

- primary_verdict = `restored115_feature_mapping_blocked`
- clean115 construction: yes, by dropping dirty116 col0.
- interface smoke: not run.

## Answers

1. clean115 was successfully defined but not materialized as a large duplicate cache.
2. dirty116 col0 should be removed: it is a strict row index and label-correlated only through row order.
3. clean115 cannot yet be safely mapped to restored115 because feature names/order are missing.
4. mapping confidence = `low`.
5. common100 and extra15 are only tentative; `common100_mapping_blocked.md` records why they were not materialized.
6. prior-use/my_gold overlap is severe: sampled features and labels indicate my_gold is the full Mirai prefix, and strict exclusion removes all benign rows.
7. A split proposal was written, but clean-claim evidence is blocked.
8. split evidence_level = `consistency_only_due_to_historical_my_gold_benign_overlap` for relaxed split; strict split is `blocked`.
9. LOW-GUARD interface smoke was not executed.
10. restored115 + HistGB-Conservative remains a candidate, but potential cannot be judged until mapping and split gates pass.
11. restored115_common100 vs restored115_all was not evaluated.
12. It cannot enter formal clean validation yet.
13. Minimal blockers: feature mapping/order and prior-use isolation.
14. issue27o should recover restored115 mapping and audit the timestamped official 100k overlap.
15. Slurm: not needed for this audit; may be needed for full re-extraction or large smoke later.
