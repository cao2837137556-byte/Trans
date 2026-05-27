# LOW-GUARD++ Formal Decision

## Primary Verdict

`candidate_config_not_recoverable_needs_debug`

## Formal pass conditions

- locked mean > LOW-GUARD-LR: `not_evaluated`
- locked min >= LOW-GUARD-LR: `not_evaluated`
- locked OOD max <= 0.01: `not_evaluated`
- feasible_rate >= 0.975: `not_evaluated`
- no final eval leakage: `pass`
- frozen config recoverable: `fail`
- full seeds stable: `not_evaluated`
- no single-bin catastrophic failure: `not_evaluated`

## Decision

Do not upgrade to LOW-GUARD++ yet. The candidate is promising but not formally validated because the frozen config is not uniquely recoverable.
