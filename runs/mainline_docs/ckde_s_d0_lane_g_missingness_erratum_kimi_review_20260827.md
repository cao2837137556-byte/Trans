# CKDE-S Lane G Missingness Erratum — Kimi Narrow Review

- Reviewer: Kimi
- Date: 2026-08-27
- Erratum: `runs/mainline_docs/ckde_s_d0_lane_g_missingness_erratum_frozen_20260827.md`
- Erratum commit: `26b78a6`
- Binding ruling: `ckde_s_d0_lane_g_missingness_kimi_ruling_20260827.md` (`033ce19`)
- Verdict: **ERRATUM PASS.** Codex may consume the existing Lane G implementation
  authorization to modify code and tests. A second real run still requires a fresh user
  execution authorization after my implementation/diff review.

## 1. SHA verification

- Recomputed SHA-256:
  `c7077dbae15b4792e9b66694ebc453f61f1ad990dd7e61afd89b9a576fba0976`
- Matches Codex's report and the `.sha256` sidecar. **PASS.**

## 2. Ruling-implementation cross-check (033ce19 → 26b78a6)

Full text read (350 lines). Every element of the ruling is implemented mechanically:

| Ruling item | Erratum implementation | Status |
|---|---|---|
| Q1: complete = terminal + `missing=false`, no earlier-target substitution | §3 verbatim, plus "missing=true is not a zero embedding" | PASS |
| Q2/A1: staged array access | §4 G0-M → G0-A → G0-R; §4.2 forbids representation/probe reads at recensus; §5 distinct counters with `representation_arrays_opened=0` until all availability gates pass; legacy alias disagreement = engineering failure | PASS |
| A2: determinism + literal fail-closed | §4.2 pure deterministic function, no sampling/iteration dependence/rank shopping; stop conditions `D_finite<9 OR r_finite<2 OR r_finite != r_metadata` → `NO_IDENTIFIABLE_COMPLETE_SESSION_EMBEDDING_DENOMINATOR`, no retry | PASS |
| A3: mandatory no-gate diagnostics | §7 four artifacts with exact schemas: recensus JSON, per-device finite-rate CSV, full 12-family CSV (zero-finite rows survive), per-session diagnostic CSV; header states values carry no gate | PASS |
| A3(d): verbatim missingness rule + pinned source | §2 pins source doc SHA `ecb42992...50aa9` and quotes the rule | PASS (independently verified, §3 below) |
| A4: claim caps | §8 exact claim sentence; verdict JSON must carry `claim_scope`, `excluded_devices`, `protected`/`unprotected_attack_families` with literal status, device/session/record denominators | PASS |
| Q3 cond. 1: equal-family construction | §6.2 "Row prevalence may not weight the span; ToN row dominance does not enter V_raw" | PASS |
| Q3 cond. 2: unprotected families named | §6.2 names all seven, including Merlin C&C; §9 item 8 requires them in the verdict itself | PASS |
| Q3 cond. 3: structural-immunity as reasoning note only | §8 final paragraph: reasoning note only; future D1 must explicitly test frozen missing-channel behavior on a preregistered stress set | PASS |
| Q4: availability failure is scientific state | §4.2 G0-family state preserving diagnostics with representation/probe counters at 0 | PASS |

Non-drift statement (§1) correctly scopes precedence to the five named areas and leaves
rank formula, gates, weighting rules, state order, and all prohibitions unchanged.

## 3. Independent verification of the pinned missingness quotation

- Source doc SHA-256 recomputed: `ecb429926507d2c4f8f666edc2d7e50f3e94fc2ec74bc1e26e78ca4813950aa9`
  — matches the erratum's pin and the `EMBEDDING_PARENT_CONTRACT_SHA256` constant in the
  implementation.
- Quoted rule verified verbatim at lines 329–331 of
  `ckda_d1_frozen_representation_probe_preregistered_20260812.md`: "For G0, an
  unencodable target has score `+infinity`. For P1/P2, its finite representation
  dimensions are zero and `missing_embedding=1`. No target may be dropped. Missing
  counts and hard decisions remain in every denominator."

The pinned rule confirms the erratum's semantics: missingness is a designed, frozen
property of the inherited pipeline, and missing rows remain in all detector
denominators — exactly what §3 of the erratum preserves.

## 4. Regression-gate review (§9)

The 15 required gates cover every ruling element and add valuable extras: row-order
invariance (item 6), non-boolean availability rejection (item 7), 12-family readback
including zero-finite rows (item 10), verbatim quotation readback (item 12), and G0-A
stop artifacts containing no representation/probe statistic keys (item 13). The closing
clause — "No observed recensus number is encoded as a success expectation in a
regression test" — is exactly the anti-gaming discipline required now that 13/4/5 are
viewed values. Approved without modification.

## 5. Ruling

**ERRATUM PASS** at SHA-256
`c7077dbae15b4792e9b66694ebc453f61f1ad990dd7e61afd89b9a576fba0976`.

Next chain (unchanged): implementation + regression tests under the existing
implementation authorization → my implementation/diff review → **fresh user execution
authorization** for the second real Lane G run. Lane M, network, training, report,
FINAL, HPC remain sealed.
