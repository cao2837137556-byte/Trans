# issue27ckl diagnostic interpretation

## Verdict

This is a frontend-only ablation. The detector head and data contract are fixed.

No F1 frontend candidate passes the conservative guardrail.
The useful-looking reductions are trade-offs: they either raise OOD hard false alarms or damage future/sealed attack detection.

- `F1_device_family_robust_only` vs F0: sealed OOD review delta `0.1851`, sealed OOD hard-max delta `0.0242`, sealed attack hard delta `0.0055`, future hard delta `0.0280`.
- `F1_device_family_robust_tail` vs F0: sealed OOD review delta `0.1201`, sealed OOD hard-max delta `0.0246`, sealed attack hard delta `0.0054`, future hard delta `0.0278`.
- `F1_global_robust_only` vs F0: sealed OOD review delta `-0.0418`, sealed OOD hard-max delta `0.0153`, sealed attack hard delta `-0.0063`, future hard delta `-0.1770`.
- `F1_global_robust_tail` vs F0: sealed OOD review delta `0.0844`, sealed OOD hard-max delta `0.0128`, sealed attack hard delta `-0.0012`, future hard delta `-0.0032`.

Best OOD-review-only candidate is not acceptable:
- `F1_global_robust_only` lowers sealed OOD review to `0.0315`, but future hard drops to `0.7947` and sealed OOD hard max rises to `0.0187`.

## Leave-device-family risk

Worst held-family hard alarm: `F1_device_family_robust_only` / `iotsim-stream-consumer` / `ood_stress` = `0.9997`.

## Shortcut probe

- `F0_raw115` predicts `device_family` on sealed_final_ood with balanced accuracy `0.0000`.
- `F1_device_family_robust_only` predicts `device_family` on sealed_final_ood with balanced accuracy `0.0000`.
- `F1_device_family_robust_tail` predicts `device_family` on sealed_final_ood with balanced accuracy `0.0000`.
- `F1_global_robust_only` predicts `device_family` on sealed_final_ood with balanced accuracy `0.0000`.
- `F1_global_robust_tail` predicts `device_family` on sealed_final_ood with balanced accuracy `0.0000`.
- `F0_raw115` predicts `source_family` on sealed_final_ood with balanced accuracy `0.0000`.
- `F1_device_family_robust_only` predicts `source_family` on sealed_final_ood with balanced accuracy `0.0000`.
- `F1_device_family_robust_tail` predicts `source_family` on sealed_final_ood with balanced accuracy `0.0000`.
- `F1_global_robust_only` predicts `source_family` on sealed_final_ood with balanced accuracy `0.0000`.
- `F1_global_robust_tail` predicts `source_family` on sealed_final_ood with balanced accuracy `0.0000`.

Interpretation note: sealed_final_ood probe accuracy is zero because those held families are outside the probe's fit-label support; it is not evidence of invariance. On known ood_stress families, device/source predictability remains near-perfect.
- known-family `F0_raw115` -> `device_family` balanced accuracy `0.9987`.
- known-family `F1_device_family_robust_only` -> `device_family` balanced accuracy `1.0000`.
- known-family `F1_device_family_robust_tail` -> `device_family` balanced accuracy `1.0000`.
- known-family `F1_global_robust_only` -> `device_family` balanced accuracy `0.9980`.
- known-family `F1_global_robust_tail` -> `device_family` balanced accuracy `0.9987`.
- known-family `F0_raw115` -> `source_family` balanced accuracy `0.9987`.
- known-family `F1_device_family_robust_only` -> `source_family` balanced accuracy `1.0000`.
- known-family `F1_device_family_robust_tail` -> `source_family` balanced accuracy `1.0000`.
- known-family `F1_global_robust_only` -> `source_family` balanced accuracy `0.9980`.
- known-family `F1_global_robust_tail` -> `source_family` balanced accuracy `0.9987`.

## Data-use boundary

Feature statistics, detector fit, thresholds, and shortcut probes use only legal fit/select development roles as appropriate.
No support_val, query, future, sealed_final_ood, or sealed_final_attack rows are used for fitting.
