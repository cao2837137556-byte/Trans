# issue27bx Next Action

Recommended next task:

`issue27bx_larger_sanity_materialization_dry_run_from_contract_v1`

Boundary:

- use `larger_sanity_contract_v1.json`
- materialize a bounded 3M-8M row Kitsune115 larger sanity asset
- do not exceed 10M emitted rows without explicit confirmation
- write X/y/sidecar/split/hash/state logs
- preserve fixed_support_mode and active_update_mode as separate modes
- do not run formal benchmark
- do not use sealed final OOD or sealed final attack for selection
- include purge/embargo and past-only temporal state audit

Go/No-Go:

- if materialization violates file/role/sidecar/state logs, stop
- if sealed final roles are read during selection, stop
- if attack phase/onset cannot be represented, downgrade to data contract repair
