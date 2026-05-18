# Routing Rule

## Inputs

- `validation_ood_alarm_v1`, `validation_ood_alarm_v2`: OOD validation high rate under each model's guarded 1% threshold.
- `attack_proxy_v1`, `attack_proxy_v2`: attack validation detection proxy under each model's guarded 1% threshold.

## Decision

1. If `validation_ood_alarm_v2 > 0.01`, select V1.
2. Else if `attack_proxy_v2 - attack_proxy_v1 >= 0.05`, select V2.
3. Else select V1.

## Constraints

The rule does not use final OOD eval, final attack eval, final OOD alarm, or final attack detection. Delta is fixed before running this issue. The proxy limitation is that attack validation is finite and may not perfectly represent future attack-side drift.
