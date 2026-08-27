# CKDE-S D0 Lane G Real-Execution Failure and Missingness Ruling Request

- Date: 2026-08-27
- Executor: Codex
- Authorized scope: real Lane G only
- Implementation approval: Kimi `81e96be`
- Implementation commit: `269e4b3`
- Status: **ENGINEERING FAILURE; NO SCIENTIFIC VERDICT**

## 1. What happened

The user explicitly authorized real Lane G execution. The frozen runner was invoked with a fresh
output namespace:

```text
py -3.9 repo/ood/issue27ckde_s_d0_lane_g_geometry_audit_v1.py \
  --root . \
  --output runs/issue27ckde_s_d0_lane_g_geometry_audit_v1_2026-08-27_localwin_cpu
```

All pinned identities passed. The metadata-only count gate passed. After the pinned embedding and
probe-state archives were opened, the runner stopped at the pre-geometry missingness assertion:

```text
RuntimeError: complete Lane G session embedding is missing
```

The staged scientific directory was removed. The only surviving artifact is the control-side
`engineering_failure.json`. There is no G0--G4 verdict, no partial scientific table, no Lane M
authorization, and no report/FINAL/training access.

## 2. Root cause from the pinned artifacts

The embedding audit already records the following frozen facts:

| quantity | value |
|---|---:|
| target rows | 25,467 |
| embedded rows | 13,827 |
| missing rows | 11,640 |

The implementation review had treated a missing terminal representation as an unexpected
engineering condition. Real execution shows that missingness is a material, intentional part of
the inherited CKDA artifact and therefore must be included in Lane G's denominator semantics.

Independent read-only diagnosis over the pinned fit roles produced:

| stratum | terminal sessions | finite terminal embeddings | missing terminal embeddings |
|---|---:|---:|---:|
| fit benign | 8,372 | 2,087 | 6,285 |
| fit attack | 4,262 | 4,123 | 139 |
| total | 12,634 | 6,210 | 6,424 |

For every one of the 6,424 missing-terminal sessions, no earlier frozen target in the same session
has a finite embedding. Therefore selecting an earlier target cannot repair this run.

## 3. Denominator consequences

If “complete causal session embedding” is interpreted mechanically as a terminal session target
with `missing=false`, the benign device census changes as follows:

| device result | value |
|---|---:|
| metadata-count devices with >=64 sessions | 15 |
| devices with >=64 finite terminal embeddings | 13 |
| finite-session count rank | `min(4,floor((13-1)/3)) = 4` |

The two devices below fail the finite-session minimum:

- `normal_1.pcap`: 29 finite terminal embeddings;
- `iotsim-combined-cycle-tls-1_0-0_to_OpenvSwitch-14_1-0`: 48 finite terminal embeddings.

Thus the frozen rank remains 4, but the device denominator changes from 15 to 13.

Attack-family eligibility also changes materially. Of 12 exact families, 8 have at least 15
terminal sessions before embedding availability, while only 5 have at least 15 finite terminal
embeddings afterward. In particular, `Merlin C&C Communication` has 28 terminal sessions but only
1 finite embedding; `Merlin ICMP Flooding` and `Mirai GRE Flooding` have 0 finite embeddings.

## 4. Why execution cannot simply continue

The parent FROZEN contract says:

1. the independent unit is one **complete causal session embedding**;
2. device eligibility requires at least 64 such sessions;
3. the count/rank gate occurs before embedding statistics are opened;
4. attack protection uses eligible exact families with at least 15 independent sessions.

The current implementation counted metadata sessions before NPZ open and only afterward asserted
that every selected session had a finite embedding. The pinned metadata CSV does not contain the
missing flag, so the implementation cannot simultaneously establish finite-embedding eligibility
and preserve a literal “before either NPZ deserialization” rule. This is a contract ambiguity
exposed by real input, not a safe one-line implementation repair.

The following shortcuts are rejected:

- **zero-fill missing embeddings**: would measure encoder missingness, not device geometry;
- **drop missing rows while retaining the 15-device census**: denominator inconsistency;
- **choose an earlier finite target**: impossible for all 6,424 affected sessions;
- **reuse the missingness indicator as a geometric coordinate**: not the frozen 768D Lane G
  hypothesis;
- **silently reduce attack-family protection from 8 to 5 families**: changes the protected scope
  and hides that several stealth/flooding families have no usable gradient evidence.

## 5. Proposed narrow resolution for independent ruling

### Option A — recommended: freeze a post-identity availability recensus

Add a numerical/semantic erratum before any retry:

1. pin “complete causal session embedding” as terminal target with `missing=false`;
2. keep the metadata-only pre-open gate as a cheap necessary gate;
3. after exact NPZ identity/schema open but before SVD, gradient, or outcome statistics, perform a
   deterministic availability recensus;
4. recompute device eligibility and the same frozen rank formula from finite terminal embeddings;
5. if `D_finite < 9`, rank `<2`, or rank differs from the pre-open rank, stop with a new literal
   fail-closed state rather than retrying another rank;
6. recompute exact-family eligibility from finite terminal embeddings and report both the full
   12-family denominator and the finite eligible subset;
7. explicitly cap any future claim: families without sufficient finite embeddings are
   **unprotected/unidentified**, never implicitly protected by the gradient subspace.

On the observed pinned inputs this would yield 13 devices, rank 4, and 5 gradient-eligible
families. These values are diagnostic evidence only and may not be used to relax any gate.

### Option B — strict closure

Interpret the pre-open count requirement as inseparable from complete-embedding eligibility. Since
the pinned metadata cannot establish it, terminate Lane G as
`NO_IDENTIFIABLE_COMPLETE_SESSION_EMBEDDING_DENOMINATOR` and move CKDE-S to future work with a
newly materialized complete embedding artifact.

## 6. Questions for Kimi

1. Does “complete causal session embedding” mean a terminal session target with `missing=false`?
2. Is Option A an admissible pre-statistic denominator correction, or does the pre-open wording
   require Option B?
3. If Option A is accepted, is a five-family protected gradient space scientifically meaningful
   given the explicit absence of usable Merlin C&C/ICMP and Mirai GRE evidence?
4. Should the availability failure be a new G0-like scientific state or remain an engineering
   failure until a newly materialized embedding artifact exists?

No code change or retry is authorized by this document. A contract erratum, independent review,
implementation regression tests, and fresh user execution authorization are required before any
second real run.
