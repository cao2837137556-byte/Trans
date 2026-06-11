# Support Update Contract

## Problem

The project has two drift axes:

- benign drift: ID benign -> OOD benign, causing false alarms.
- attack drift: labelled support attack -> future/query attack, causing missed detections.

The current support set is a legal development-side simulation of analyst-labelled attack examples. It is useful for medium diagnostics, but the full online support policy is not yet complete.

## Fixed Support Mode

Use fixed support when evaluating generalization under a frozen few-shot setting.

Rules:

- support is selected only from development-side labelled attack support candidates.
- support selection cannot use final OOD, sealed attack, report-only detection scores, or report-only coverage.
- support indices, selector config, hash, and role access audit must be materialized.
- support size must be bounded and reported.

Required budgets for larger sanity:

```text
support_size: 32 / 64 / 128
support_val_size: fixed or proportional, development-side only
prototype_budget: bounded, reported per bank
```

## Active Update Mode

Use active update only as a separate online diagnostic, not as the initial formal result.

Rules:

- incoming stream samples can enter `unknown` or `review` based on pre-frozen rules.
- only analyst-confirmed attack samples may enter attack memory.
- confirmed benign drift may enter OOD stress or benign/OOD memory, never attack support.
- active selection cannot use future labels before the review decision.
- label budget and review budget must be reported.

## Region Memory Rules

Attack memory must be bounded:

- create a new region only when confirmed attack is outside existing region shell.
- merge regions if their shells overlap strongly and labels/phase evidence agree.
- retire or compress old exemplars if memory budget is exceeded.
- do not add one unlimited model head per new attack family.

## Open Items

- define exact new-region creation threshold.
- define region merge/retire policy.
- define label-noise handling.
- define mixed-stream active update replay before formal benchmark.

