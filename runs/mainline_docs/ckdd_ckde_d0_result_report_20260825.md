# CKDD / CKDE D0 Result Report (2026-08-25)

Status: `D0_RESULTS_COMPLETE`

## 1. Executive result

The two frozen D0 audits return different but mechanically clear outcomes:

- **CKDD:** `CKDD_D0_NO_IDENTIFIABLE_SOURCE_SPLIT` — do not start the one-shot
  constrained attack-head retraining experiment.
- **CKDE:** `CKDE_D0_UNPAIRED_DEVELOPMENT_ONLY` — a benign-prefix calibration
  study is identifiable on existing devices, but only as a development-level
  experiment without strict session-conformal or same-device attack-preservation
  claims.

Neither result is a model-performance result. No new detector was trained and no
report or FINAL score was opened.

## 2. CKDD result: source-disjoint retraining is not identifiable

The frozen hard-negative pool contains 4,986 benign-conflict rows from six source
groups. Its largest group (`normal_2.pcap`) contributes 3,687 rows (73.947%). All
62 non-trivial source partitions were enumerated. Zero satisfy the frozen joint
requirements:

- at least three training source groups;
- at least two validation source groups;
- at least 300 rows on each side;
- no source overlap;
- no side dominated above the frozen 80% limit.

Therefore the verdict is:

```text
CKDD_D0_NO_IDENTIFIABLE_SOURCE_SPLIT
```

This closes the **defensible one-shot known-pool repair experiment under the frozen
split contract**. It does not prove that attack-head retraining is universally
impossible; it proves that this data cannot support a non-trivial source-disjoint
validation of that claim. Starting training anyway would turn a known-pool repair
into an unidentifiable instance-level patch, so it is rejected before optimization.

The future kill-only gate remains a declaration only: all viewed attack rows would
have to be checked if a separately identifiable retraining design ever existed.
No viewed report scores were opened in D0.

## 3. CKDE result: commissioning calibration is development-identifiable

Count-only causal census results:

| Item | Result |
|---|---:|
| Device-lineage groups | 28 |
| Devices with causal benign prefix and suffix | 23 |
| Eligible independent prefix sessions | 7,493 |
| Eligible independent suffix sessions | 7,550 |
| Devices with same-device attack pairing | 0 |

The 23 eligible devices provide enough independent benign sessions to justify
drafting a **uniform, one-sided prefix-quantile calibration study**. However, zero
devices provide the paired same-device attack evidence needed to measure how that
calibration preserves attack recall on the commissioned device.

Accordingly:

- `d1_executable = false` under the current D0-only freeze;
- strict session-conformal coverage claims are not authorized;
- same-device attack-preservation positive claims are not authorized;
- record counts may never substitute for independent session counts;
- a post-D0 protocol may be drafted only as a development study with explicit
  zero-shot control, fixed calibration budgets, one-sided threshold updates, and
  contamination stress tests.

## 4. Decision and next step

1. **CKDD stops at D0.** No training implementation or one-shot training run is
   authorized or scientifically justified.
2. **CKDE remains the main live route**, but the next action is protocol design,
   not immediate calibration. The protocol must freeze literal per-device session
   budgets, the global update rule, attack-derived cap, pollution grid, zero-shot
   arm, and development-only claim boundary before any score is opened.
3. The CKDA D1 formal HPC replay remains a separate paper-grade confirmation task
   when the cluster becomes available; local evidence must not be promoted as HPC
   evidence.

## 5. Claim boundary

The positive result is an **identifiability result about available benign
commissioning information**, not proof that OOD false positives have already
improved. The negative CKDD result is a data-design limitation, not a performance
failure. No FINAL, downloads, new training data, or family-specific patch was used.
