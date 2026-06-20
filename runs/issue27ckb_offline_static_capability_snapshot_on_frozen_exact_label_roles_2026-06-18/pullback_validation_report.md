# issue27ckb Pullback Validation Report

Date: 2026-06-20

Status: `PASS_WITH_THRESHOLD_SEMANTICS_CAVEAT`

Remote jobs:

- model array: `41350`
- aggregate: `41351`

## Completeness

- Full non-smoke model jobs: `7/7`.
- Aggregate result rows: `7`.
- Aggregate role-summary rows: `72`.
- Aggregate threshold-role rows: `168`.
- Aggregate label/device rows: `1617`.
- Every job contains:
  - `result.json`;
  - `model.pkl`;
  - `frozen_config_before_stress_and_final.json`;
  - `role_access_audit.csv`;
  - role and label metric tables.

## Contract Validation

All seven jobs passed the local pullback audit:

- `smoke = false`;
- `candidate_pool_reused = false`;
- `final_used_for_selection = false`;
- the recorded frozen-config SHA256 matches the downloaded frozen-config file;
- no role-access row records forbidden access.

The remote automatic `hpc_validation_report.txt` was absent, so this report supplies the missing post-pullback validation. Model and aggregate outputs themselves were complete.

## Source Aggregate Hashes

- `aggregate_job_results.csv`: `24856e384f13d4eb108b685f0dbd6094f66a11c337eb2e66bb01904dfa51faea`
- `aggregate_role_summary.csv`: `13cd6002adf136050f226dbdf152bc5033cadad8f69ee1a7637bbf949249021b`
- `aggregate_attack_metrics_by_label_device.csv`: `e58746570a724446f4aafe272b1cb6b5151f9449dec9d903f5ecaad0092f5a06`

Downloaded source:

`D:\study\paper\anomaly_detection\paper04\supercompute_transfer\issue27ckb_offline_capability_hpc_20260618\pullback_results\issue27ckb_remote_results`

## Threshold Semantics Caveat

The run computes threshold rates with `score >= threshold`. For every model, the nominal OOD-val q99 threshold equals the maximum observed OOD-val score. Large masses of tied maximum scores therefore count as alarms:

| Model | OOD-val mass equal to threshold | OOD-val mass strictly above threshold |
|---|---:|---:|
| HistGB support64 seed42 | 24.825% | 0% |
| HistGB support64 seed43 | 6.808% | 0% |
| HistGB support64 seed44 | 17.013% | 0% |
| HistGB support256 seed42 | 43.346% | 0% |
| HistGB support256 seed43 | 7.188% | 0% |
| HistGB support256 seed44 | 17.008% | 0% |
| Logistic regression | 71.750% | 0% |

Thus `ood_guarded_q99` is not a realizable 1% deterministic operating point for these saturated/discrete score distributions. The threshold-rate tables remain useful as diagnostics, but they must not be interpreted as valid 1% calibration.

The threshold-free ROC-AUC results are not affected by this comparison-operator issue and remain the primary evidence for representation/model separability.
