# CKDA D1 frozen representation probe implementation report

Status: `IMPLEMENTED_AND_LOCALLY_VALIDATED_AWAITING_KIMI_REVIEW`

Date: 2026-08-12

Contract: `ckda_d1_frozen_representation_probe_preregistered_20260812.md`

Contract SHA-256: `ecb429926507d2c4f8f666edc2d7e50f3e94fc2ec74bc1e26e78ca4813950aa9`

Authorization boundary: this report covers implementation and local validation only. It does not authorize bundle construction, upload, embedding generation, model training, FINAL access, or HPC submission.

## 1. Implemented frozen chain

The implementation is one result-producing chain with these ordered, fail-closed phases:

1. immutable dependency and Python 3.9 gates;
2. fit/select role-plan materialization without report access;
3. exact benign-only I1 census with D0-checkpoint reuse;
4. frozen `I1 -> E3` progression;
5. exact raw-target metadata join;
6. member-checkpointed E3 current-inclusive prefix embeddings;
7. shared normalization plus G0/P1/P2 fit and threshold freeze;
8. post-freeze report plan and one-shot report embeddings;
9. fixed metrics, source/session bootstrap, final state machine;
10. strict validation, allowlisted pullback packaging, and terminal marker.

The current frozen D0 manifest has a mechanically derived benign-visible packet upper bound below the 10,000,000-token I1 gate. The exact benign census is still executed and audited. If that frozen precondition fails as expected, no I1 training or embedding is started and E3 opens under the preregistered progression. This is a data-precondition result, not an engineering failure and not a hidden candidate choice.

## 2. Main implementation files

- `repo/ood/issue27ckda_d1_representation_probe_v1.py`: causal session/token contract, I1 identity, normalization, G0/P1/P2, thresholds, state machine, Python 3.9 and runtime-API gate.
- `repo/ood/issue27ckda_d1_role_plan_v1.py`: isolated fit/select and sealed-report plans.
- `repo/ood/issue27ckda_d1_benign_census_v1.py`: benign-only census and validated checkpoint reuse.
- `repo/ood/issue27ckda_d1_target_metadata_v1.py`: exact lineage join to cache/PCAP event positions.
- `repo/ood/issue27ckda_d1_e3_embed_v1.py`: one-pass member decoding, current-inclusive prefix embeddings, persistent member resume.
- `repo/ood/issue27ckda_d1_probe_runner_v1.py`: three frozen probes, select-only thresholds, one-shot report scoring.
- `repo/ood/issue27ckda_d1_metrics_v1.py`: frozen gates, coverage, family/pool metrics, 2,000-replicate bootstrap.
- `repo/ood/issue27ckda_d1_validate_and_pack_v1.py`: mandatory-artifact and lineage validation; no verdict after engineering failure.
- `scripts/issue27ckda_d1_representation_probe_formal.slurm`: complete formal chain, progress watchdog, isolated writes, and checkpoints.
- `scripts/issue27ckda_d1_install_and_submit.sh`: hash/env/test/dry-scheduler gates plus explicit user-submission authorization.
- `scripts/issue27ckda_d1_status.sh`: completed-unit and terminal status monitor.
- `scripts/issue27ckda_d1_build_bundle.ps1`: scoped, LF-normalized, hash-pinned clean-extraction builder. It intentionally reuses the already verified D0 netFound runtime and weight instead of duplicating the 665 MB payload.

## 3. Runtime-risk controls added from prior failures

- all nine executed D1 Python files parse under Python 3.9 grammar;
- the gate rejects observed runtime incompatibilities including `Path.write_text(newline=...)` and `zip(..., strict=True)`;
- static undefined-name checking is clean;
- the real E3 embedding entry point is exercised, including masked-mean and empty-mask failure;
- member timestamps must be monotone and equal timestamps use causal event position;
- heterogeneous CSV rows use deterministic union fieldnames and atomic readback;
- large CSV outputs stream directly to atomic gzip files;
- role plans, target metadata, embeddings, frontiers, thresholds, scores, metrics, and bootstrap evidence are SHA-bound by the terminal validator;
- fit/select role-plan audit is renamed before report planning so it cannot be overwritten;
- the validator requires both role-plan audits and all three threshold-frontier tables;
- Slurm is pinned to the formal Python 3.9 runtime and invokes the same contract tests on the compute node before real work;
- every E3 member has a persistent identity-checked checkpoint; a retry resumes completed members rather than restarting the full decode;
- a 20-minute no-progress gate records engineering failure and emits no scientific verdict.

## 4. Local validation evidence

### 4.1 Contract suite

`46/46 PASS`.

Covered cases include causal future-mutation invariance, session/member isolation, split-once/no-duplication, I1 forward and exact resume, E3 real-entrypoint cardinality, target metadata interface identity, G0 self-exclusion, fixed P1/P2 paths, threshold denominator/NaN gates, state precedence, streamed gzip union schema, report-marker isolation, and 2,000-replicate clustered bootstrap.

### 4.2 Python and shell gates

- Python 3.9 grammar/runtime-API gate: `PASS`, 9 files.
- `compileall`: `PASS`, 9 files.
- `pyflakes 3.2.0`: `PASS`, no undefined names or unused implementation imports.
- validator atomic-LF contract: `PASS`.
- Bash syntax for Slurm, installer, and status script: `PASS`.
- PowerShell parser for bundle builder: `PASS`.

### 4.3 Real-data lineage rehearsal

The actual local copy of the 154917 Gotham/auxiliary causal caches and the frozen CKBY snapshot was used; this was not a synthetic-only rehearsal.

- fit/select role plan: `25,467` rows (`18,398` fit + `7,069` select);
- exact target metadata join: `25,467 / 25,467` UIDs;
- cache sources audited: `55` (`24` Gotham + `31` auxiliary);
- joined rows: Gotham `3,867`, auxiliary `9,600`, ToN `12,000`;
- real decoded member identities present in the plan: `30`;
- duplicate `(container, member, target_event_position)` keys: `0`;
- missing container/member fields: `0`;
- FINAL files opened: `0`.

The sealed-report side was also exercised after a synthetic threshold marker carrying only frozen-contract identities was written:

- real CKBY + CKBW report plan: `262,050` rows;
- attack rows: `244,050`; future-query rows: `131,391`; review rows: `0`;
- report target metadata join: `262,050 / 262,050` UIDs;
- report cache split: Gotham `253,050`, auxiliary `9,000`, ToN `0`;
- cache sources audited again: `55`; FINAL files opened: `0`.

This rehearsal exposed one pre-review interface defect: the first target-metadata version called a nonexistent CKCZ `load_manifest` helper. It was corrected to the actual `validate_manifest(path, sha, allowlist, ...)` contract, then protected by a regression test and rerun successfully on all 55 cache sources. No HPC job was used to discover this defect.

## 5. Review request and remaining boundary

Kimi is requested to independently inspect the frozen-contract correspondence, the Python 3.9/runtime gates, exact role/lineage boundaries, progression logic, checkpoint/resume behavior, validator mandatory set, and the 46-test suite.

After a Kimi implementation PASS, the next separately authorized step is bundle construction and bundle review. HPC submission remains a later explicit user authorization. No claim is made that D1 has signal until the one-shot formal result passes the terminal validator.
