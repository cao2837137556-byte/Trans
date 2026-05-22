# Representation-Level Ablation Protocol

## Purpose

Representation-level ablation isolates the contribution of OOD-safe source-rich representation selection. It should answer whether selected_source_rich_top64 is doing real work beyond the adapter and support selection.

## Fixed Components

- Adapter: fixed OOD guard LR.
- Support: kcenter32 confirmed attack supports.
- Threshold: ID calibration + OOD validation at 1% OOD alarm target.
- Final eval: report-only.
- OOD weight and support budget: frozen according to Enhanced LOW-GUARD+.

## Required Representation Comparisons

- original100 + kcenter32 + fixed guard LR.
- source_rich_top32 + kcenter32 + fixed guard LR.
- source_rich_top64 + kcenter32 + fixed guard LR.
- top64 no guard.
- top64 random32.

## Optional Representation Comparisons

- full_source_rich + kcenter32 + fixed guard LR, if feature alignment and runtime are safe.
- source_rich_top64 with random support sensitivity, if issue25c needs a stronger support ablation.

## Fairness Rationale

This layer intentionally changes feature input because the research claim concerns representation selection. It must not be mixed with method-level baseline fairness, where each method may receive a method-native input variant.

## Required Reporting

- Detection and OOD alarm at official 1% OOD validation target.
- Locked mean detection, locked min detection, locked OOD max, feasibility rate.
- Primary_lowood, holdout_bin_2, and chrono_late as consistency checks.
- All feature variants reported, including negative or unstable variants.

## Interpretation Boundaries

- A source_rich_top64 win supports OOD-safe attack-separating representation selection.
- It does not prove external generalization.
- It does not justify new topK search after seeing issue25c results.
