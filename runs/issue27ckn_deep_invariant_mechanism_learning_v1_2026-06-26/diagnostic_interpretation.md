# issue27ckn diagnostic interpretation

## Verdict

This run is the first deep representation test after shallow feature/reweighting failures.

No neural invariant candidate passes the conservative detection guardrail.

- `N1_mlp_erm` vs C0: sealed OOD review delta `-0.0789`, sealed OOD hard-max delta `0.0012`, sealed attack hard delta `-0.2653`, future hard delta `-0.0291`.
- `N2_dann_device_family` vs C0: sealed OOD review delta `-0.0789`, sealed OOD hard-max delta `0.0015`, sealed attack hard delta `-0.2139`, future hard delta `-0.1463`.
- `N3_dann_source_family` vs C0: sealed OOD review delta `-0.0789`, sealed OOD hard-max delta `0.0016`, sealed attack hard delta `-0.2277`, future hard delta `-0.0609`.

## Leave-device-family risk

Worst held-family hard alarm: `C0_c4_histgb` / `iotsim-stream-consumer` / `ood_stress` = `0.9977`.

## Probe interpretation

- known-family `C0_c4_histgb` -> `device_family` probe known-label balanced accuracy `0.9987` with known-label rate `1.0000`.
- known-family `N1_mlp_erm` -> `device_family` probe known-label balanced accuracy `0.9978` with known-label rate `1.0000`.
- known-family `N2_dann_device_family` -> `device_family` probe known-label balanced accuracy `0.9972` with known-label rate `1.0000`.
- known-family `N3_dann_source_family` -> `device_family` probe known-label balanced accuracy `0.9973` with known-label rate `1.0000`.
- known-family `C0_c4_histgb` -> `source_family` probe known-label balanced accuracy `0.9987` with known-label rate `1.0000`.
- known-family `N1_mlp_erm` -> `source_family` probe known-label balanced accuracy `0.9978` with known-label rate `1.0000`.
- known-family `N2_dann_device_family` -> `source_family` probe known-label balanced accuracy `0.9972` with known-label rate `1.0000`.
- known-family `N3_dann_source_family` -> `source_family` probe known-label balanced accuracy `0.9973` with known-label rate `1.0000`.
- sealed_final_ood probe rows are mostly/fully outside the probe training label vocabulary (max known-label rate `0.0000`), so all-label probe accuracy there is not treated as shortcut removal evidence.

## Data-use boundary

Training uses only support_train fit, id_calib fit, ood_val fit, and ood_stress fit.
Thresholds use only id_calib/ood_val/ood_stress select.
Representation probes are trained only on legal benign fit roles.
support_val, same_file_query, future_query, sealed_final_ood, and sealed_final_attack are report-only.
