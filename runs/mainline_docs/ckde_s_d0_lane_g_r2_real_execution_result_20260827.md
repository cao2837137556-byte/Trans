# CKDE-S D0 Lane G r2 real-execution result (2026-08-27)

Status: `REAL_EXECUTION_COMPLETE_AWAITING_KIMI_RESULT_REVIEW`

## 1. Authorization and execution identity

- Kimi implementation/diff review: `IMPLEMENTATION PASS` at commit `a397626`
- User authorization: fresh second real-execution authorization received on 2026-08-27
- Runner commit: `c01df73`
- Output namespace: `runs/issue27ckde_s_d0_lane_g_geometry_audit_v1_2026-08-27_r2_localwin_cpu`
- Execution runtime: local Windows Python 3.9
- Lane M/network/training/report/FINAL/HPC: sealed

The first failed namespace and its engineering-failure record were preserved. The r2 execution used a new output namespace and did not overwrite prior evidence.

## 2. Pre-execution regression gate

Immediately before the real run:

```powershell
py -3.9 repo/ood/issue27ckde_s_d0_lane_g_geometry_audit_contract_tests_v1.py
```

Result: `41/41 PASS`.

## 3. Scientific verdict

The real execution completed without an engineering failure and produced:

```text
scientific_state = G1
status = UNSTABLE_OR_TEMPORAL_DEVICE_SUBSPACE
```

Under the frozen joint state machine, `Lane G != G4` mechanically implies the provisional route conclusion:

```text
CKDE_S_NO_GO_INTERNAL_GEOMETRY
```

This joint conclusion remains subject to Kimi's independent result review. Lane M is not authorized or scientifically necessary to rescue a non-G4 Lane G result.

## 4. Availability recensus

The missingness-aware recensus passed all three G0-A gates:

| Quantity | Result |
|---|---:|
| metadata-eligible devices | 15 |
| finite-eligible devices | 13 |
| metadata rank | 4 |
| finite rank | 4 |
| finite benign terminal sessions | 2,087 |
| missing benign terminal sessions | 6,285 |
| finite attack terminal sessions | 4,123 |
| missing attack terminal sessions | 139 |

Excluded from the encodable device geometry:

- `iotsim-combined-cycle-tls-1_0-0_to_OpenvSwitch-14_1-0`
- `normal_1.pcap`

Only five attack families have sufficient finite representation evidence for a potential protection span; seven are explicitly `UNPROTECTED_BY_REPRESENTATION_EVIDENCE`. The run stopped at G1 before constructing or evaluating the attack-gradient subspace.

## 5. Exact G1 mechanism

The temporal-separation component passed:

| Metric | Result | Frozen requirement | Status |
|---|---:|---:|---|
| median between/within ratio | 8.4643 | >= 2.0 | PASS |
| devices with ratio >= 1.0 | 13/13 | >= 11 | PASS |

Therefore the observed stop is not caused by early/late temporal drift.

The leave-one-device-out subspace-stability component failed only its worst-device safeguards:

| Metric | Result | Frozen maximum | Status |
|---|---:|---:|---|
| median normalized projection distance | 0.1565 | 0.20 | PASS |
| median largest principal angle | 18.2386 degrees | 20 degrees | PASS |
| worst normalized projection distance | 0.5757 | 0.35 | FAIL |
| worst largest principal angle | 89.3635 degrees | 35 degrees | FAIL |

The worst held-out device is:

```text
iotsim-building-monitor-5_0-0_to_OpenvSwitch-28_5-0
```

Its held-out geometry is nearly orthogonal to the subspace learned from the remaining devices. This means a rank-4 device nuisance subspace is not stable across every frozen eligible device. The frozen worst-device guard correctly prevents the median behavior of the other devices from hiding this failure.

No device may be dropped, no rank may be retried, and no constant may be changed after observing this result.

## 6. Integrity and boundary validation

Independent post-run validation established:

- `SHA256SUMS`: 13/13 files independently recomputed and matched;
- real scientific verdict present; no r2 engineering-failure control directory;
- `embedding_uid_missing_arrays_opened = 1`;
- `representation_arrays_opened = embedding_arrays_opened = 1`;
- `probe_state_arrays_opened = 1`;
- `network_requests_made = 0`;
- `pcap_files_opened = 0`;
- `support_val_rows_opened = 0`;
- `report_files_opened = 0`;
- `final_files_opened = 0`;
- `training_runs = training_steps_run = 0`;
- `lane_m_authorized = false`.

The scientific claim remains strictly limited to:

> geometry of the encodable (`missing=false`) subset of the frozen fit pool

## 7. Requested Kimi independent result review

Please independently verify:

1. all 13 output hashes and the frozen input identities;
2. the 13-device/rank-4 availability recensus and the exact two-device exclusion list;
3. temporal stability PASS versus LODO worst-device stability FAIL;
4. the identity and two failing values of the worst held-out device;
5. that G1 was reached before attack-gradient geometry and that no G2-G4 evidence is claimed;
6. all sealed-boundary counters and the no-retry/no-device-drop implications;
7. whether the frozen joint state machine now closes CKDE-S as `CKDE_S_NO_GO_INTERNAL_GEOMETRY` and makes Lane M unnecessary.

No additional execution, Lane M retrieval, rule adjustment, rank retry, model training, or FINAL access is authorized by this report.
