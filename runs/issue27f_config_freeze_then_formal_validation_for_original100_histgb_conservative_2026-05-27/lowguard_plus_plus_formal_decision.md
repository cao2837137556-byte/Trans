# LOW-GUARD++ Formal Decision

## Primary Verdict

`lowguard_plus_plus_formal_validated`

## Pass Conditions

- mean > LOW-GUARD-LR: `True`
- min >= LOW-GUARD-LR: `True`
- OOD max <= 0.01: `True`
- feasible_rate >= 0.975: `True`
- no final eval leakage: `True`
- unique frozen config: `true`
- no single-bin catastrophic failure: `True`

## Candidate Result

`1.000000` / `1.000000` / `0.000100`

## LR Reference

`0.949705` / `0.882629` / `0.004500`
