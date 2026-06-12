# issue27bw Decision

primary_verdict: `larger_sanity_contract_ready_for_materialization_not_formal_benchmark`

The larger sanity contract is ready for a bounded materialization dry run. It is not a formal benchmark contract.

The contract covers all 78 processed CSV files at metadata level and assigns a larger role structure with:

- ID train/calib
- OOD val/stress
- sealed final OOD
- attack support candidate pool
- dev future/query attack
- sealed final attack

The key caveat is that only 8 mixed attack CSV files exist. This is enough to stress the medium protocol at a larger sanity scale, but not enough to claim a pristine final benchmark without a stronger holdout policy.

No model was run. No 115D extraction was performed. No commit or push was performed.
