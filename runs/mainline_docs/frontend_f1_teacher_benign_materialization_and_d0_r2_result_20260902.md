# Frontend-F1 teacher-benign materialization and D0 r2 result

Date: 2026-09-02

Execution: local Windows CPU, Python 3.9.13

Authorization: count-only teacher-benign materialization plus Frontend-F1 D0 re-closure; no D1 training

## Outcome first

Frontend-F1 D0 is now closed with:

```text
status = F1_D0_CENSUS_PASS
reason = ALL_D0_GATES_PASS
```

The previously missing evidence was materialized exactly once. Among the `7,347` legal-fit, owner-A, true-benign rows:

- incumbent P2 hard: `28`;
- incumbent P2 normal: `7,319`;
- conservation: `28 + 7,319 = 7,347`;
- old-hard rate on this fit-only denominator: `0.3811%`.

This is a feasibility/census result, not a detection-performance result and not a claim about select, OOD, report, or FINAL behavior.

## Frozen protocol and implementation

Protocol:

- `runs/mainline_docs/frontend_f1_teacher_benign_count_only_materialization_frozen_20260902.md`
- SHA-256: `019c6e8864d0029c224de94b93d96edd8f3a6bf4f8c2bc92a1f52c59d028526b`

Implementation:

- `repo/ood/issue27frontend_f1_teacher_benign_count_only_v1.py`
- `repo/ood/issue27frontend_f1_teacher_benign_count_only_contract_tests_v1.py`

Python 3.9 compilation passed. Contract tests passed `12/12`.

## Isolation mechanism

The compressed NPZ representation member was streamed row by row. All `25,467` container rows necessarily passed through the decompressor as opaque bytes, but only the `7,347` exact allowlisted rows were converted to numeric arrays. Non-allowlisted numeric representation rows decoded: `0`.

The materializer then reconstructed the frozen P2 exactly and persisted only `uid,hard`; it persisted no score or representation value.

Boundary audit:

- authorized fit-benign scores computed: `7,347`;
- select/cross-phase-fit/attack/owner-B/viewed/report/FINAL scores computed: all `0`;
- score values persisted: `0`;
- representations persisted: `0`;
- fitted parameters / optimizer steps / threshold selections: all `0`;
- PCAP opened / training started: `0`.

## Independent verification

The result package at `runs/frontend_f1_teacher_benign_count_only_v1_20260902_local/` was verified independently from its durable outputs:

- SHA256SUMS: `5/5` members recomputed PASS;
- UID rows: `7,347`, unique `7,347`;
- Boolean hard count independently recounted: `28`;
- Boolean normal count independently recounted: `7,319`;
- aggregate JSON and UID table agree exactly.

## D0 r2 re-closure

The D0 runner was extended only to consume and validate the authorized count-only artifact. It verifies all member hashes, exact UID-set equality, the two-column `uid,hard` schema, threshold identity, denominator conservation, and the absence of persisted score values.

Updated D0 tests passed `22/22`. The new result package is:

```text
runs/frontend_f1_d0_census_v1_20260902_local_r2/
```

Independent verification:

- SHA256SUMS: `12/12` members recomputed PASS;
- teacher coverage complete: `true`;
- original four conservation equations unchanged and PASS;
- synthetic resource gate: PASS;
- selected candidate by frozen non-performance ordering: `torch.nn.GRU`;
- synthetic wall-time cap for this machine snapshot: `13.193 h`;
- training started: `0`;
- real representation / score / probe / checkpoint / PCAP / viewed / report / FINAL opened by D0 r2: all `0`.

## Scientific interpretation

This result removes the D0 evidence gap. It shows that the frozen old P2 supplies a usable label-aware teacher partition on legal-fit owner-A benign rows: most are already normal, while `28` old-hard benign rows can be exempted from hard-preservation and allowed to soften under the frozen Frontend-F1 loss semantics.

It does **not** show that the unified encoder improves OOD FPR, hydraulic behavior, or attack recall. Those questions require a separately frozen numerical/training addendum and a separately authorized D1 run.

## Authorization state

Completed authorization:

- teacher-benign count-only materialization;
- Frontend-F1 D0 re-closure.

Still not authorized:

- Frontend-F1 D1 training or real checkpoint production;
- any select/viewed/report/FINAL score opening;
- threshold or P2 changes;
- HPC execution;
- performance or paper claim.

The next legal action is to draft and freeze the Frontend-F1 D1 numerical/training addendum. No training should begin until that addendum fixes the loss weights, validation/early-stop rule, checkpoint identity, resource stop rule, and all zero-regression gates.
