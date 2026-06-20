# issue27ckc Frozen Medium Mainline Replay Contract

This is the offline role-separated mainline replay requested by the user. It is not another raw static scorer ablation.

Architecture:

```text
Kitsune115D
-> frozen medium full-115D attack scorer
-> parent OOD-risk evidence
-> past-only temporal attack/OOD heads
-> bounded hard/suppress/review/unknown controller
```

Data:

- certified 1M benign/OOD asset;
- issue27cf frozen 512-row support bank: 385 train, 127 validation;
- issue27ch complete-only exact-label query/final attack subset;
- no reuse of the remaining attack candidate pool.

Access order:

1. Fit attack scorer on ID train, a preregistered source-disjoint OOD-val fit half, and 385 support-train rows.
2. Fit parent OOD-risk and temporal heads only on fit halves of ID-calib/OOD-val/support-val.
3. Freeze and hash all models, banks, thresholds, and controller parameters.
4. Replay OOD stress and certified dev queries read-only.
5. Replay sealed final attack/OOD report-only.

The primary variant preserves the medium weighted normal-to-attack mass ratio when moving from 128 to 385 supports and from medium to 1M ID scale. The strict weight-4 variant is retained as a frozen-weight control.
