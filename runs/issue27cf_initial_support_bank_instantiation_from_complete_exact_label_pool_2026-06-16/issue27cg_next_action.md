# issue27cg Next Action

Recommended next issue:

```text
issue27cg_combined_cycle_query_alignment_repair_or_replan
```

Purpose:

Repair or explicitly replan the incomplete `dev_future_attack_query_exact` role for `processed/iotsim-combined-cycle-1.csv`.

Do not train models until this is resolved.

Required checks:

- inspect alternate PCAP candidates for combined-cycle-1;
- compare CSV timestamp ranges with PCAP timestamp ranges;
- decide whether to switch PCAP candidate, narrow query windows, exclude these chunks, or rebuild a query role from different files;
- preserve sealed final attack and sealed final OOD isolation;
- do not use detection metrics or final outcomes.
