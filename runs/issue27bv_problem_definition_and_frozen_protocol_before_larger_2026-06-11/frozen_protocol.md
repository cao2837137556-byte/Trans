# Frozen Protocol Before Larger Sanity

## Current Candidate System

The current strongest medium diagnostic system is frozen as:

```text
Gotham raw PCAP
-> Kitsune / AfterImage / netStat 115D online features
-> frozen full-115D attack scorer
-> certified parent OOD-risk channel
-> past-only temporal evidence features
-> temporal attack/OOD evidence heads
-> bounded controller
-> hard / suppress / review
```

This is a medium diagnostic protocol, not a formal benchmark result.

## Fixed Frontend

- Keep the Kitsune-style 115D frontend fixed.
- Do not replace 115D with processed CSV header fields.
- Do not add raw source-like fields such as file path, device id, label, attack type, raw absolute time, IP, MAC, or source/capture identifiers as model inputs.
- Past-only temporal features may use prior alarms, prior margins, prior distances, and prior OOD-risk summaries, but must use only past rows.

## Current Frozen Roles

- `id_fit` / `id_calib`: training and calibration side ID benign roles.
- `ood_val` / `ood_stress_val`: development-side benign drift and stress roles.
- `phase_balanced_support_train`: labelled attack support for fitting attack evidence.
- `support_val` / `dev_future_near` / `dev_future_mid` / `dev_future_far`: development-side attack validation and pseudo-query roles.
- `final_ood_report_only`: report-only benign OOD replay.
- `sealed_medium_attack_eval_report_only` / sealed heavy attack roles: report-only attack replay.

## Current Evidence Channels

- `attack scorer`: frozen full-115D supervised attack evidence.
- `parent OOD-risk`: certified medium diagnostic OOD-risk channel based on attack margins and prototype distances.
- `temporal evidence`: past-only role/source windows such as prior raw alarm rate, prior attack margin, prior OOD-risk, prior prototype-distance summaries, and prior alarm run length.
- `controller`: converts raw attack alarm and OOD-risk into `hard`, `suppress`, or `review`.

## Current Best Medium Diagnostic Numbers

From issue27bu group-disjoint replay using parent OOD-risk + temporal evidence:

- dev attack min: `1.0`
- dev OOD max: `0.0`
- report-only attack min: `0.9707207207207207`
- final OOD max: `0.0006666666666666666`

These numbers are evidence for continuing the route, not formal paper results.

## Frozen Restrictions

- No full/formal benchmark yet.
- No final OOD or sealed attack use for fit, selection, support construction, prototype construction, threshold selection, or controller tuning.
- No support/query reshuffling from report-only data.
- No claim that temporal evidence is true causality.
- No unbounded head growth; attack/OOD should remain two main evidence heads plus controller.

