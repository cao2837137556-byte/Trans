# CKDE-S Lane G missingness erratum implementation report (2026-08-27)

Status: `IMPLEMENTED_AWAITING_KIMI_DIFF_REVIEW`

This report covers only the implementation and synthetic regression-test authority granted after the frozen missingness erratum and Kimi's narrow review. No real Lane G scientific execution was performed. No real representation/probe arrays, report material, FINAL material, network resource, training path, or HPC path were opened.

## 1. Frozen inputs

- Parent CKDE-S D0 FROZEN SHA-256: `e2de3bd75ac0f4e9a1d90180bcc9db938418e44719f08bac5a89d07b29cf29e6`
- Lane G numerical erratum SHA-256: `156932108d48495c4b6c7156ef2af8e3f10ca74494c75451cb0a30f5222a149d`
- Missingness erratum SHA-256: `c7077dbae15b4792e9b66694ebc453f61f1ad990dd7e61afd89b9a576fba0976`
- CKDA D1 missingness-rule source SHA-256: `ecb429926507d2c4f8f666edc2d7e50f3e94fc2ec74bc1e26e78ca4813950aa9`
- Kimi erratum review commit: `b4152a1`

The runner verifies the frozen documents and the exact inherited missingness-rule quotation before any scientific path can proceed.

## 2. Implementation changes

### 2.1 Staged array-access contract

Lane G now has three mechanically separated stages:

1. `G0-M`: plan and metadata census only; no NPZ access.
2. `G0-A`: open only `uid` and boolean `missing` arrays to perform the deterministic availability recensus.
3. Geometry stage: open `representation` and then probe-state arrays only after all recensus gates pass.

The role audit records independent counters for `embedding_uid_missing_arrays_opened`, `representation_arrays_opened`, the legacy exact alias `embedding_arrays_opened`, and `probe_state_arrays_opened`. The legacy counter must equal the representation counter; disagreement is an engineering failure.

### 2.2 Deterministic complete-session recensus

- A complete session is represented only by its terminal frozen target.
- A terminal target with `missing=true` is unavailable; no earlier finite target may replace it.
- Availability joins are exact and exhaustive by UID. Duplicate, missing, or extra UID identities fail closed as engineering failures.
- The three scientific stop conditions are independent and literal:
  - `D_finite < 9`;
  - `rank_finite < 2`;
  - `rank_finite != rank_preopen` (the frozen pre-open rank is 4).
- Any stop condition yields `NO_IDENTIFIABLE_COMPLETE_SESSION_EMBEDDING_DENOMINATOR`, with `retry_allowed=false`.

### 2.3 Mandatory diagnostics and claim boundary

The recensus emits four scientific diagnostics with frozen schemas:

- `ckde_s_d0_embedding_availability_recensus.json`
- `ckde_s_d0_embedding_availability_by_device.csv`
- `ckde_s_d0_embedding_availability_by_attack_family.csv`
- `ckde_s_d0_embedding_availability_session_diagnostic.csv`

If G0-A stops scientifically, only these diagnostics, the role-open audit, the verdict, and `SHA256SUMS` survive atomic publication. Input-identity and count/rank scratch files are not published. Representation and probe-state arrays remain unopened.

Every downstream verdict is capped to the exact claim:

> geometry of the encodable (`missing=false`) subset of the frozen fit pool

Verdicts also carry separate device/session/record denominators, excluded device names, protected family names, and all unprotected families with literal status `UNPROTECTED_BY_REPRESENTATION_EVIDENCE`.

### 2.4 Attack-protection construction

- The full frozen 12-family attack universe is always reported.
- Only families satisfying the frozen finite-session eligibility rule contribute to the protection span.
- Each eligible family contributes exactly one robust direction, so ToN row-count dominance cannot enter the span.
- Missing-channel immunity is retained only as a reasoning note; it is not promoted to a Lane G scientific claim.

## 3. Regression verification

Commands executed locally:

```powershell
py -3.9 -m py_compile repo/ood/issue27ckde_s_d0_lane_g_geometry_audit_v1.py repo/ood/issue27ckde_s_d0_lane_g_geometry_audit_contract_tests_v1.py
py -3.9 repo/ood/issue27ckde_s_d0_lane_g_geometry_audit_contract_tests_v1.py
git diff --check
```

Result:

- Python 3.9 compilation: `PASS`
- Synthetic contract suite: `41/41 PASS`
- Whitespace/error check: `PASS`
- Historical Python-compatibility scan (`match/case`, `Path.write_text(newline=...)`): no hit
- Real embedding/probe opening: `0`
- Real Lane G verdict: not produced

Source identities at implementation completion:

- runner SHA-256: `950800abd7c1287f3ecf75f1d5be8bf2c44a61794a00d7b31bf4bf47243f7c47`
- contract-test SHA-256: `23119c1d80c659a8c5a0a6bcbec953595085aab56e368b849f09a83675657e86`

## 4. Requested Kimi implementation/diff review

Please independently verify:

1. G0-A cannot open `representation` or probe-state arrays before all recensus gates pass.
2. Terminal-target missingness cannot be substituted by any earlier finite target.
3. All three availability stop conditions independently produce the new scientific terminal state with no retry.
4. The four diagnostics and their schemas match the frozen erratum exactly, and the G0-A stop publish allowlist contains no representation-derived statistic.
5. The protection span uses one equal-weight direction per eligible family while the complete 12-family table survives unchanged.
6. The verdict claim is limited to the encodable subset and explicitly names excluded devices and unprotected families.
7. The 41-test suite contains no viewed recensus numbers as success expectations.

Only after this implementation/diff review passes should the user be asked for the second, separate real-execution authorization.
