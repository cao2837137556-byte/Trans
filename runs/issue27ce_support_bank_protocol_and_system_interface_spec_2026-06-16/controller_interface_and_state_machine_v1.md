# Controller Interface and State Machine v1

This file defines controller states and required inputs. It does not define final thresholds.

## Required Inputs

- `attack_score`
- `attack_region_id`
- `attack_region_distance`
- `attack_evidence_reliability`
- `ood_risk_score`
- `benign_region_id`
- `ood_region_distance`
- `ood_evidence_reliability`
- `past_attack_persistence`
- `past_ood_persistence`
- `source_consistency`
- `window_validity`

## Outputs

- `hard_alarm`
- `suppress`
- `review_conflict`
- `unknown`
- `no_alarm`

## State Machine

```text
incoming_sample
-> evidence_available | evidence_missing
-> no_alarm_candidate | attack_candidate | ood_risk_candidate | conflict_candidate | unknown_candidate
-> hard_alarm | suppress | review_conflict | unknown | no_alarm
```

## Exception Handling

- Missing attack head output: route to `unknown` or `review_conflict`, never silently hard alarm.
- Missing OOD head output: do not suppress solely from missing OOD evidence.
- Insufficient temporal history: set `window_validity=false`; controller must not use future context.
- Both attack and OOD evidence high: route to `review_conflict` unless a later issue freezes a safer override.
- Review budget exhausted: route to `unknown` with audit flag, not silent suppress.
- No matching attack region: route to `unknown` unless attack evidence is explicitly supported by a later frozen rule.

## Open Parameters

All numerical thresholds remain open and development-only:

- attack score alarm threshold;
- OOD suppress threshold;
- conflict margin threshold;
- attack-region distance shell;
- benign-region distance shell;
- review budget;
- temporal persistence horizon.

