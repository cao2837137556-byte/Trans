# CKDE-S D0 Lane G missingness and availability erratum (FROZEN)

**Date:** 2026-08-27
**Status:** FROZEN ERRATUM; NON-EXECUTABLE pending independent narrow review
**Parent contract:** `ckde_s_d0_attack_protected_device_shift_and_paired_corpus_preregistered_20260826.md`
**Parent SHA-256:** `e2de3bd75ac0f4e9a1d90180bcc9db938418e44719f08bac5a89d07b29cf29e6`
**Prior numerical erratum:** `ckde_s_d0_lane_g_preimplementation_erratum_frozen_20260826.md`
**Prior erratum SHA-256:** `156932108d48495c4b6c7156ef2af8e3f10ca74494c75451cb0a30f5222a149d`
**Binding ruling:** `ckde_s_d0_lane_g_missingness_kimi_ruling_20260827.md` (commit `033ce19`)

## 1. Purpose, precedence, and non-drift statement

The first authorized real Lane G run stopped fail-closed before any scientific verdict because
the inherited frozen embedding artifact contains material, deterministic missingness.  The first
run remains an **engineering failure** and cannot be reinterpreted as a scientific result.

This erratum implements Kimi's Option A ruling and amendments A1--A4.  It has precedence over the
parent contract only for:

1. the meaning of a complete causal session embedding;
2. the staged availability recensus and array-open order;
3. the availability-dependent device/family denominators;
4. the new fail-closed scientific state and mandatory missingness diagnostics; and
5. the resulting claim cap.

All other parent-contract and prior-erratum rules remain unchanged, including rank formula,
scientific constants and gates, equal-device/equal-session/equal-family weighting, state order,
FINAL/report/training/network prohibitions, and the ban on in-run rank downgrade or family/source
routing.  This erratum does not choose a new encoder, repair missing rows, or relax any gate.

## 2. Exact input identities and inherited missingness rule

The four Lane G inputs and their identities remain exactly those pinned by the prior erratum:

| Identity | Repository-relative path | SHA-256 |
|---|---|---|
| fit/select embeddings | `runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/ckda_d1_fit_select_embeddings.npz` | `b1b4f2fde168a69e0cf7a53aaede2ddef9bd6d92b0ce58e56a9d6fcde37b6099` |
| embedding metadata | `runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/ckda_d1_fit_select_embeddings.npz.metadata.csv.gz` | `120ed5ccc752c1210a655dbcb972e08b6263bdeb1e08093d76b3e2f9c1b3d8dd` |
| fit/select plan | `runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/ckda_d1_fit_select_plan.csv` | `eed3d431ab8d71117db7a02b5ee0022eefe7932888001e7d9bcccfd54199aeac` |
| frozen probe/P2 state | `runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/ckda_d1_probe_state.npz` | `50a9bcfc18287d51bf8afda7367b57decdf3179dd41fc3aa61399d4098360c38` |

The inherited missingness rule is pinned to
`ckda_d1_frozen_representation_probe_preregistered_20260812.md`, SHA-256
`ecb429926507d2c4f8f666edc2d7e50f3e94fc2ec74bc1e26e78ca4813950aa9`, and must be quoted
verbatim in the Lane G recensus output:

> For G0, an unencodable target has score `+infinity`. For P1/P2, its finite
> representation dimensions are zero and `missing_embedding=1`. No target may be
> dropped. Missing counts and hard decisions remain in every denominator.

## 3. Complete causal session embedding

For Lane G, a **complete causal session embedding** is exactly the frozen session's terminal target
whose pinned embedding row has `missing=false`.

- The terminal target remains the causal unit; no earlier target may replace it.
- `missing=true` is not a 768-dimensional zero embedding and may not enter geometric statistics.
- A session with a missing terminal target is unavailable for Lane G geometry even if another
  implementation could materialize a different representation.
- Missing rows remain in all inherited detector denominators and are not reclassified or dropped
  from the CKDA/P2 evidence.  They are excluded only from the Lane G 768D geometry hypothesis.

## 4. Mandatory two-stage denominator sequence

The runner must follow the order below.  Any different order is an engineering failure with no
scientific verdict.

### 4.1 Stage G0-M: metadata-only necessary gate

1. Verify the parent contract, both errata, and all pinned input hashes.
2. Read only the plan and metadata table; opening either NPZ is forbidden.
3. Reproduce the parent metadata-only device count and count-rank:

```text
D_metadata = number of fit-benign devices with >=64 terminal sessions
r_metadata = min(4, floor((D_metadata - 1) / 3))
```

4. Apply the unchanged parent gate `D_metadata >= 9` and `r_metadata >= 2`.

Failure here retains the parent's `NO_IDENTIFIABLE_DEVICE_SUBSPACE_BY_COUNT` state.  No NPZ array
may have been opened.

### 4.2 Stage G0-A: availability recensus

Only after G0-M passes may the runner open the embeddings NPZ and read exactly these two arrays:

```text
uid
missing
```

At this stage it is forbidden to read or materialize:

- the 768D `representation` array or any alias/copy/view of it;
- any array from the probe-state NPZ;
- any score, logit, gradient, SVD, center, projection, or downstream outcome statistic.

The recensus is a pure deterministic function of the pinned plan, metadata, `uid`, and `missing`:
no sampling, iteration-order dependence, fallback target, retry, imputation, rank shopping, or
data-dependent family merge is allowed.  Exact UID joins must be one-to-one and exhaustive over
the frozen target plan; duplicate, absent, non-boolean, or schema-drifted availability is an
engineering failure with no verdict.

For each frozen session, choose only its terminal target, then set:

```text
finite_terminal_embedding = (terminal missing == false)
```

Recompute:

```text
D_finite = number of fit-benign devices with >=64 finite terminal embeddings
r_finite = min(4, floor((D_finite - 1) / 3))
```

The following are literal, terminal, no-retry scientific stop conditions:

```text
D_finite < 9
OR r_finite < 2
OR r_finite != r_metadata
```

Any such condition yields exactly:

```text
NO_IDENTIFIABLE_COMPLETE_SESSION_EMBEDDING_DENOMINATOR
```

This is a G0-family scientific state.  It must preserve the mandatory recensus diagnostics and
must show `representation_arrays_opened=0` and `probe_state_arrays_opened=0`.  It does not
authorize a retry, alternative encoder, lower rank, earlier target, or changed family threshold.

### 4.3 Stage G0-R: representation/probe opening

Only if all G0-A gates pass may the runner:

1. read the pinned 768D representation array;
2. read the pinned probe-state arrays; and
3. continue to parent stages G2--G4 using `r_finite`, finite-eligible devices, and
   finite-eligible attack families.

The parent numerical erratum remains binding for all subsequent linear algebra.

## 5. Role-open audit counters

Every terminal or successful result must contain these distinct integer counters:

```text
embedding_uid_missing_arrays_opened
representation_arrays_opened
probe_state_arrays_opened
report_files_opened
final_files_opened
network_requests_made
training_steps_run
```

The first counter is `0` before G0-A and becomes `1` only after both `uid` and `missing` have been
read.  `representation_arrays_opened` replaces the ambiguous earlier use of
`embedding_arrays_opened`: it refers only to opening/materializing the 768D representation and
must remain `0` until every availability gate passes.  `probe_state_arrays_opened` follows the
same rule.  Legacy output may retain `embedding_arrays_opened` only as an exact alias of
`representation_arrays_opened`; disagreement is an engineering failure.

All four boundary counters for report, FINAL, network, and training must remain zero.

## 6. Availability-dependent denominators

### 6.1 Device eligibility

Only fit-benign devices with at least 64 finite terminal embeddings enter the downstream device
geometry.  Device centers, global center, LODO, drift, and all G2--G4 summaries are computed on
this finite device set with the parent's equal-device and equal-session rules.

The already observed recensus evidence is 13 eligible devices and `r_finite=4`.  These are pinned
observations, not new gates and not permission to continue if a deterministic rerun disagrees.
The two currently excluded devices must be written verbatim into every scientific verdict:

```text
normal_1.pcap
iotsim-combined-cycle-tls-1_0-0_to_OpenvSwitch-14_1-0
```

### 6.2 Attack-family eligibility and equal-family construction

An exact attack family enters `V_raw` only if it has at least 15 independent sessions with finite
terminal embeddings.  One robust median normalized-gradient direction is formed per eligible
family, and those family directions are given equal status in the span.  Row prevalence may not
weight the span; in particular, ToN row dominance does not enter `V_raw`.

The currently observed five eligible families are:

```text
ToN-reconnaissance_scan
ToN-credential_bruteforce
Mirai TCP Flooding
Merlin TCP Flooding
Merlin UDP Flooding
```

Every other exact family is `UNPROTECTED_BY_REPRESENTATION_EVIDENCE` for Lane G:

```text
File Download
Ingress Tool Transfer
Merlin C&C Communication
Merlin ICMP Flooding
Mirai C&C Communication
Mirai GRE Flooding
Mirai UDP Flooding
```

No G4 state or later narrative may imply safety, protection, or attack-preservation evidence for
an unprotected family.  The full 12-family table is mandatory even when only five families enter
the span.

## 7. Mandatory availability diagnostics (descriptive only)

The recensus must emit all artifacts below before any scientific stop or representation opening.
Their values carry **no gate** and may not select a rank, family threshold, method, retry, or
claim.  They exist only for reproducibility and claim bounding.

### 7.1 `ckde_s_d0_embedding_availability_recensus.json`

Required fields include:

- all pinned document/input hashes;
- exact missingness-rule source path, SHA-256, and verbatim quotation;
- metadata and finite device/session counts and ranks;
- terminal session counts split by `fit_benign` and `fit_attack`;
- finite and missing terminal counts for each split;
- the literal G0-A stop-condition booleans;
- eligible/excluded device lists;
- eligible/unprotected family lists;
- all role-open audit counters; and
- status `RECENSUS_PASS` or
  `NO_IDENTIFIABLE_COMPLETE_SESSION_EMBEDDING_DENOMINATOR`.

### 7.2 `ckde_s_d0_embedding_availability_by_device.csv`

One row for every fit-benign device, with exact columns:

```text
device,total_terminal_sessions,finite_terminal_sessions,missing_terminal_sessions,finite_rate,
finite_geometry_eligible
```

Rows are sorted by `device` ascending.  `finite_rate` is
`finite_terminal_sessions / total_terminal_sessions`, with no rounding in the stored value.

### 7.3 `ckde_s_d0_embedding_availability_by_attack_family.csv`

One row for each of the 12 exact attack families, including zero-finite families, with exact
columns:

```text
attack_family,total_terminal_sessions,finite_terminal_sessions,missing_terminal_sessions,
finite_rate,finite_gradient_eligible,protection_status
```

Rows are sorted by `attack_family` ascending.  `protection_status` is exactly
`PROTECTED_BY_REPRESENTATION_EVIDENCE` or `UNPROTECTED_BY_REPRESENTATION_EVIDENCE`.

### 7.4 `ckde_s_d0_embedding_availability_session_diagnostic.csv`

One row per terminal session in the frozen fit pool, derived only from plan/metadata and
availability, with exact columns:

```text
stratum,device,session_id,attack_family,terminal_uid,terminal_event_position,
records_in_frozen_session,finite_terminal_embedding
```

`stratum` is exactly `fit_benign` or `fit_attack`; benign `attack_family` is the empty string.
`records_in_frozen_session` is the count of frozen target-plan rows sharing that exact session.
Rows are sorted lexicographically by `stratum`, `device`, `session_id`, and `terminal_uid`.
This exact session-level table is the metadata-only comparison of finite versus missing session
length proxies required by A3; no summary threshold is attached.

### 7.5 Manifest and atomicity

The four artifacts above and every later Lane G artifact must be included in the final
`SHA256SUMS`.  They are written to a fresh stage directory and atomically published only after
schema and identity validation.  Engineering failure deletes any partial scientific stage and
emits no scientific verdict.  A G0-A scientific stop may atomically preserve only the recensus,
the three descriptive tables, role-open audit, verdict, and hash manifest; it may not contain
representation/probe statistics.

## 8. Claim contract

The maximum Lane G D0 claim is exactly:

> geometry of the encodable (`missing=false`) subset of the frozen fit pool

Every verdict JSON, including G4, must include:

- `claim_scope` with the exact sentence above;
- `excluded_devices` naming all fit-benign devices that fail finite eligibility;
- `protected_attack_families`;
- `unprotected_attack_families`, each carrying the literal status
  `UNPROTECTED_BY_REPRESENTATION_EVIDENCE`; and
- devices/sessions/records as separate denominators.

The observation that the missing-row detector channel is outside the 768D adapter is a reasoning
note only.  D0 does not certify that a future adapter preserves missing-channel behavior.  Any
future D1 must explicitly test the frozen missing-channel behavior on a preregistered stress set
before making such a claim.

## 9. Required regression gates before a second real run

In addition to all existing tests, implementation must prove:

1. terminal `missing=false` is the only complete-session geometry unit;
2. earlier-target substitution is absent, including a session with an earlier finite-looking row;
3. G0-M opens neither NPZ;
4. G0-A reads only `uid` and `missing`, while representation/probe counters remain zero;
5. `D_finite < 9`, `r_finite < 2`, and `r_finite != r_metadata` each independently produce the
   new scientific state without representation/probe opens or retries;
6. recensus output is invariant to input row order;
7. duplicate/missing UID and non-boolean availability fail as engineering errors;
8. both excluded devices and all seven unprotected families appear in the verdict itself;
9. equal-family construction is invariant to duplicating rows within one eligible family;
10. all 12 families, including zero-finite families, survive output and readback;
11. the session diagnostic reproduces terminal position and records-per-session exactly;
12. the CKDA D1 missingness quotation and source SHA survive output/readback verbatim;
13. any G0-A stop artifact contains no representation/probe statistic keys;
14. role-open counters distinguish availability from representation access;
15. all existing numerical, Python 3.9, identity, atomic-output, FINAL/report, and no-network gates
    continue to pass.

No observed recensus number is encoded as a success expectation in a regression test; tests may
pin identities and formulas but must not convert already observed diagnostic values into relaxed
gates.

## 10. Authorization boundary and next chain

This FROZEN erratum does **not** authorize code changes, array access, or a second real Lane G run.
The only legal next steps are:

1. independent Kimi SHA/diff narrow review of this erratum;
2. after PASS, implementation and regression tests under the already granted implementation
   authorization, with no real artifact execution beyond identity-only test fixtures;
3. independent Kimi implementation/diff review; and
4. a **fresh explicit user execution authorization** before the second real Lane G run.

Lane M, all network retrieval, training, report, FINAL, HPC, adapter execution, and additional
score opening remain sealed throughout.
