# CKDE-S Lane G Pre-implementation Erratum — Kimi Narrow Review

- Reviewer: Kimi
- Date: 2026-08-26
- Erratum: `runs/mainline_docs/ckde_s_d0_lane_g_preimplementation_erratum_frozen_20260826.md`
- Erratum commit: `9921467`
- Parent FROZEN: commit `7e833ab`, SHA-256 `e2de3bd7...f29e6`
- Verdict: **ERRATUM PASS.** Codex may consume the user's existing Lane G
  **implementation** authorization (code + synthetic contract tests). Opening real
  embedding arrays and producing a Lane G verdict still requires the separate execution
  authorization.

## 1. SHA verification

- Recomputed SHA-256 of the erratum:
  `156932108d48495c4b6c7156ef2af8e3f10ca74494c75451cb0a30f5222a149d`
- Matches Codex's reported value. **PASS.**

## 2. Independent recomputation of the four pinned input identities

I recomputed SHA-256 of all four Lane G input artifacts from disk. All four match the
erratum exactly:

| Artifact | Erratum SHA-256 | My recomputation | Match |
|---|---|---|---|
| `ckda_d1_fit_select_embeddings.npz` | `b1b4f2fd...b6099` | `b1b4f2fd...b6099` | YES |
| `...npz.metadata.csv.gz` | `120ed5cc...3d8dd` | `120ed5cc...3d8dd` | YES |
| `ckda_d1_fit_select_plan.csv` | `eed3d431...9aeac` | `eed3d431...9aeac` | YES |
| `ckda_d1_probe_state.npz` | `50a9bcfc...60c38` | `50a9bcfc...60c38` | YES |

The pinned paths live under the CKDA D1 local stage directory, consistent with the
known-provenance fit/select assets already used by CKDE-R D0. The P2 identity
description (frozen 769→128→1 ReLU MLP + 768-coordinate normalizer + missingness
indicator, state keys/shapes as validated by CKDE-R) matches the established record.

## 3. The gap is real and the erratum closes exactly that gap

Verified against the parent FROZEN text:

- Parent line ~49: "The executable FROZEN version must pin the byte identities of all
  inputs before implementation" — the requirement existed, the byte identities did not.
- Parent line ~188: family-direction span requires "a literal SVD tolerance fixed in the
  FROZEN version" — placeholder, no literal.
- Parent line ~234: the removable-space test references `orthogonality_tolerance` —
  placeholder, no literal.
- Parent line ~238: "The exact SVD and orthogonality tolerances must be literals in the
  FROZEN version."

So the parent contract *demanded* these literals but never materialized them.
Implementing with locally chosen values would indeed have created post-freeze degrees of
freedom. Detecting this before any implementation, synthetic test, or real array open is
exactly the behavior the governance loop exists to produce; recorded as a process
positive.

## 4. Content review — no scientific drift

The erratum adds only:

1. **Four input identities** (verified above, §2).
2. **Three numerical conventions**, all in the numerics (not science) class:
   `SVD_RELATIVE_TOLERANCE = 1e-10`, `ORTHOGONALITY_TOLERANCE = 1e-10`,
   `GRADIENT_NORM_FLOOR = 1e-12`. The relative-to-`s_0` strict comparison
   (`s_i > tol * s_0`) is a standard float64 numerical-rank rule; making equality
   fail-closed removes boundary discretion. The 1e-12 gradient floor only guards
   normalization against degenerate vectors. None of these touch any scientific gate,
   rank rule, denominator, or threshold of the parent contract.
3. **Fail-closed semantics**: non-finite spectrum, `s_0 <= 0`, floor-equal or non-finite
   gradients, and any state-key/shape mismatch are engineering failures with no
   scientific verdict; no fallback tolerance, no eigengap rule, no in-run rank
   downgrade. The principal-angle cosine clipping to `[-1,1]` before `arccos` is a
   pure roundoff guard and explicitly cannot change any rank or gate — acceptable.
4. **Eight regression gates** that must be proven on synthetic tests before any real
   execution — including that the count-only rank gate runs before opening either NPZ
   array, and that no alternative tolerance or rank-retry path exists. These strengthen,
   not relax, the contract.

Full-text check: no scientific gate, rank, denominator, role, state transition, claim
boundary, or authorization boundary of the parent contract is modified. The
authorization language correctly leaves real-embedding execution gated on the separate
execution authorization.

## 5. Ruling

**ERRATUM PASS** at SHA-256
`156932108d48495c4b6c7156ef2af8e3f10ca74494c75451cb0a30f5222a149d`.

- Codex may now consume the user's Lane G **implementation** authorization: write the
  Lane G auditor and the eight synthetic contract tests.
- After implementation, Codex delivers an implementation report; I review it before any
  real run.
- Opening the real pinned embeddings and producing the Lane G scientific verdict remains
  blocked until the user grants the separate **execution** authorization, per the parent
  FROZEN contract.
