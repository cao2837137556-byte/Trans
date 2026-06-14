# issue27cd Next Action

Recommended next task:

`issue27cd_slurm_exact_label_targeted_multitype_attack_materialization`

Purpose:

- Do not train models.
- Do not run a benchmark.
- Extend the Slurm materializer so attack roles emit 115D rows only when the corresponding processed CSV row has the exact planned attack label.
- Use `targeted_exact_label_materialization_plan.csv` as the only input contract.
- Preserve sealed final as report-only.

Blockers to solve before submit:

- Review ambiguous PCAP pairing for infection/C&C/File Download/Reporting labels.
- Implement exact row-label filtering in the PCAP -> 115D materializer.
- Keep current certified 1M asset immutable; write new targeted cache/asset directory.
