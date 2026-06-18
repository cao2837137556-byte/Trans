# issue27ckb Offline Static Capability Role Contract

This issue is an offline diagnostic capability snapshot. It is not an online deployment simulation and not a formal benchmark.

## Fixed Role Order

1. `id_benign_train`: fit the deterministic robust transform and benign class.
2. frozen `support_train`: fit the attack class.
3. `id_benign_calib`, frozen `support_val`, and `ood_benign_val`: compute three preregistered thresholds.
4. Write and hash the frozen model/transform/threshold configuration.
5. `ood_benign_stress` and certified dev query roles: read-only stress.
6. sealed final attack/OOD: one report-only replay after freeze.

## Forbidden

- no use of the remaining 69,492 candidate pool;
- no support reselection;
- no threshold or model changes after reading stress/query/final roles;
- no controller tuning, online update, or formal benchmark claim;
- no claim that static offline performance establishes deployability.
