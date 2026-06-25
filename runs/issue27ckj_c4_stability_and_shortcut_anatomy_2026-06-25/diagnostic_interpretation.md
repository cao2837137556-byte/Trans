# issue27ckj diagnostic interpretation

This file is the human-readable close-out for the tables in this run.

## Verdict

`C4_fewshot_multiclass_raw115_cap20000` is a real capability recovery baseline, but it is not stable enough to be promoted as a robust detector.

The diagnosis found two problems:

1. Seed42 is optimistic on review burden.
2. The detector is strongly dependent on seeing the relevant OOD/device family during training or calibration.

Therefore the next step should not be a larger C4 replay or threshold tuning. It should be a group-balanced / worst-group training-view repair, followed by invariant/causal and smarter-head tests only if the group-balanced repair is insufficient.

## Key evidence

### Seed stability is incomplete

Across seeds 42-46:

- `sealed_final_attack` hard alarm is stable enough: mean `0.9944`, min `0.9922`.
- `sealed_final_ood` hard alarm stays low: mean `0.0026`, max `0.0034`.
- But `sealed_final_ood` review is not stable: mean `0.0733`, min `0.0370`, max `0.1047`.
- `future_query` hard alarm is not fully stable: mean `0.9717`, min `0.9016`, max `0.9929`.

So the seed42 result from issue27cki is not a sufficient stability claim.

### Sealed OOD review is highly concentrated

For primary seed42, sealed OOD review count is `5736`.

It is entirely concentrated in the two sealed OOD sources:

| source | rows | review count | review rate | hard count | hard rate |
|---|---:|---:|---:|---:|---:|
| `processed/iotsim-ip-camera-street-2.csv` | 99,950 | 4,674 | 0.0468 | 366 | 0.0037 |
| `processed/iotsim-ip-camera-museum-2.csv` | 54,950 | 1,062 | 0.0193 | 142 | 0.0026 |

The `ip-camera-street-2` source contributes about `81.5%` of sealed OOD review.

This means the review burden is not a diffuse uncertainty effect; it is source/device-family concentrated.

### Device-family leave-out exposes shortcut risk

Single source-group leave-out does not collapse, because nearby same-family sources can still remain available.

Device-family leave-out is much more revealing:

| held device family | evaluated role | rows | hard alarm | review | raw alarm |
|---|---|---:|---:|---:|---:|
| `iotsim-stream-consumer` | `ood_stress` | 79,950 | 0.9977 | 0.0009 | 0.9986 |
| `iotsim-hydraulic-system` | `ood_val` | 12,205 | 0.5083 | 0.1926 | 0.7009 |

This is the strongest shortcut-risk signal in the run.

The collapse happens because these OOD families dominate their legal OOD training source. When the family is held out, the model no longer has a stable representation of that kind of benign OOD and can misclassify it as attack.

### Attack-family leave-out is a coverage diagnostic

Leave-attack-label-out should be interpreted as zero-shot attack stress, not as a normal few-shot pass/fail test.

It shows:

- `TCP Scan` remains relatively detectable.
- `UDP Scan` degrades.
- `Merlin C&C Communication` and `Mirai C&C Communication` degrade badly.

This indicates attack-family support coverage remains important. It does not invalidate the few-shot setting, but it means unseen attack families should go to unknown/review/active labeling rather than be promised as high-confidence detections.

## Decision

Do not promote C4-cap20000 as a robust final detector yet.

Proceed to:

```text
issue27ckk_group_balanced_worst_group_c4
```

The immediate repair target is:

```text
Reduce sealed/device-family OOD review and prevent leave-device-family collapse
without dropping sealed/future attack hard alarm below the C4-cap20000 baseline.
```

Only after this should we test:

```text
issue27ckl_invariant_causal_and_smarter_head_suite
```

because the current failure is already visible at the group/family coverage level.
