# issue27ckm diagnostic interpretation

## Verdict

This run tests environment-aware training objectives while keeping raw115 and the C4 HistGB head fixed.

No environment-aware candidate passes the conservative guardrail.

- `M1_device_family_env_balanced` vs baseline: sealed OOD review delta `0.0556`, sealed OOD hard-max delta `0.0044`, sealed attack hard delta `0.0026`, future hard delta `-0.0571`.
- `M2_source_family_env_balanced` vs baseline: sealed OOD review delta `0.0556`, sealed OOD hard-max delta `0.0044`, sealed attack hard delta `0.0026`, future hard delta `-0.0571`.
- `M3_device_family_dro` vs baseline: sealed OOD review delta `0.0194`, sealed OOD hard-max delta `0.0042`, sealed attack hard delta `0.0023`, future hard delta `-0.0601`.
- `M4_source_family_dro` vs baseline: sealed OOD review delta `0.0194`, sealed OOD hard-max delta `0.0042`, sealed attack hard delta `0.0023`, future hard delta `-0.0601`.

Interpretation: environment-aware weighting increased sealed/future attack confidence for some rows, but it did not produce a valid generalization improvement.
Compared with C4, the DRO-style variants still raise sealed OOD hard false alarms and reduce future attack hard detection by about six percentage points on average.
Device-family and source-family variants are identical here because the current role metadata maps those environments almost one-to-one in the legal fit roles.

## Leave-device-family risk

Worst held-family hard alarm: `M0_c4_baseline` / `iotsim-stream-consumer` / `ood_stress` = `0.9977`.
The invariant weighting line therefore has not solved the `iotsim-stream-consumer` collapse; the system still treats that held OOD family almost entirely as hard attack.

## Data-use boundary

Training uses only support_train fit, id_calib fit, ood_val fit, and ood_stress fit.
Thresholds use only id_calib/ood_val/ood_stress select.
support_val, same_file_query, future_query, sealed_final_ood, and sealed_final_attack are report-only.
