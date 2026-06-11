# Mixed Stream Replay Design

## Why This Is Needed

Current diagnostics mostly report separated roles. Real deployment receives a mixed stream:

```text
ID benign + OOD benign + known attack + shifted attack + unknown attack + noise
```

Separated role metrics are necessary but not sufficient.

## Stream Construction

Create one or more replay streams with pre-declared proportions:

- benign-heavy stream
- attack-burst stream
- OOD-drift-heavy stream
- mixed unknown/conflict stream

Each stream must preserve within-file/time ordering where available and must not allow future packets into past-only features.

## Decision Outputs

For each packet/window:

- `hard_alarm`
- `suppress`
- `review`
- `unknown`
- `source_role`
- `decision_reason`
- `past_state_id`

## Metrics

Report:

- hard alarm rate
- false alarm rate on benign and OOD benign
- attack detection
- review rate
- unknown rate
- review precision after labels are revealed for evaluation only
- label efficiency
- time-to-detect
- cost per 1k packets

## Review Budget

Review cannot be a garbage bin.

Initial budgets:

```text
review_budget: 1% / 3% / 5%
unknown_budget: separately reported
```

If budget is exceeded, rank by frozen priority:

1. persistent high attack evidence
2. high disagreement between attack and OOD channels
3. far from all known benign/OOD/attack regions
4. source/time burst concentration

No final/report-only labels may be used to define ranking rules.

