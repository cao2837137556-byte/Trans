# CKDE-S Lane G Missingness Implementation — Kimi Implementation/Diff Review

- Reviewer: Kimi
- Date: 2026-08-27
- Range reviewed: `269e4b3` → `c01df73`
- Governing documents: parent FROZEN (`7e833ab`), erratum 1 (`9921467`), missingness
  erratum (`26b78a6`, Kimi PASS at `b4152a1`)
- Verdict: **IMPLEMENTATION PASS.** Lane G is ready for the user's fresh execution
  authorization for the second real run.

## 1. Independent verification performed

1. Full diff of the implementation (511 lines changed) read hunk by hunk; all new
   functions traced against the missingness erratum §3–§9.
2. New-test list extracted (18 new: test_22–test_39) and the four most load-bearing
   tests read in full to confirm they genuinely discriminate (§3 below).
3. Independent re-run with the actual Python 3.9 runtime:
   `py -3.9 repo/ood/issue27ckde_s_d0_lane_g_geometry_audit_contract_tests_v1.py`
   → **41/41 PASS** (reproduced).
4. `git diff --check 269e4b3 c01df73` → PASS; `py -3.9 -m py_compile` on both files →
   PASS.
5. Confirmed the runner now pins and verifies all four governing documents (parent
   contract, both errata, CKDA D1 missingness source) and checks the missingness
   quotation verbatim at runtime.

## 2. Erratum-implementation cross-check

| Erratum requirement | Implementation | Status |
|---|---|---|
| §3 complete = terminal + `missing=false`, no substitution | missing terminal sessions filtered, never substituted; `missing_terminal_sessions_with_earlier_finite_target` computed as a reported diagnostic | PASS |
| §4.1 G0-M: no NPZ before count gate | order in `materialize`: metadata → count gate → (fail: verdict with `NOT_OPENED_G0M`, zero NPZ counters) | PASS |
| §4.2 G0-A: only `uid`/`missing` | `load_availability` checks schema via `data.files` (no array read), then reads exactly `uid` and `missing`; boolean-dtype enforcement; one-to-one exhaustive UID join | PASS |
| §4.2 three literal stop conditions | `availability_gate_status`: `stop_D_finite_lt_9`, `stop_r_finite_lt_2`, `stop_r_finite_ne_r_metadata`, independent, no retry | PASS |
| §4.3 G0-R: representation/probe only after recensus pass | `load_representations`/`load_probe_state` called only on `RECENSUS_PASS`; finite-only non-finiteness check | PASS |
| §5 distinct counters + legacy alias | `validate_role_open_audit` enforces int types, alias equality, sealed boundaries zero; called on every terminal path | PASS |
| §6.1/§6.2 eligibility + equal-family span | 12-family universe pinned; `attack_protection` iterates all 12, one robust direction per finite-eligible family; ToN row dominance cannot enter span | PASS |
| §7 four diagnostics, exact schemas | recensus JSON + by_device/by_family/session_diagnostic CSVs with the exact frozen column sets and sort orders | PASS |
| §7.5 stop-artifact whitelist | on recensus stop, pre-recensus files are unlinked; only the seven permitted artifacts remain | PASS |
| §8 claim contract | verdict carries exact `claim_scope` sentence, `excluded_devices`, protected/unprotected lists with literal status, device/session/record denominators | PASS |
| §9 fifteen regression gates | covered by test_22–test_39 plus pre-existing 23 tests | PASS |

## 3. Discriminating-power spot checks (the tests that must be able to fail)

- **test_25** drives each stop condition independently to the terminal state and
  confirms `RECENSUS_PASS` only at the exact pass point — the conditions cannot mask
  each other.
- **test_26** constructs the precise adversarial case — a session with a missing
  terminal target but an earlier finite-looking row — and asserts the terminal is still
  chosen, marked unavailable, and counted in the no-substitution diagnostic. This is the
  test that would catch any fallback-target temptation.
- **test_29** runs the full `materialize` with a mocked recensus failure and
  tripwired `load_representations`/`load_probe_state` (AssertionError if reached), then
  asserts the stop-artifact directory contains exactly the seven permitted files and no
  representation/probe statistic key appears in any output. This enforces erratum §7.5
  end-to-end, not just in spirit.
- **test_33** proves equal-family construction by doubling one family's rows and showing
  span rank and orthogonality are bit-identical — row prevalence demonstrably cannot
  enter `V_raw`.
- **test_36** source-scans the implementation for every viewed recensus number
  (13827/11640/8372/2087/4262/4123/6424) and requires their absence — the anti-gaming
  clause of erratum §9 is itself enforced by a test.

## 4. Non-blocking observations

1. The G0-M failure verdict now carries metadata-only denominators with
   `NOT_OPENED_G0M` markers — improves auditability without touching NPZ. Endorsed.
2. The gradient CSV on the G1 path reuses the availability family table so the 12-family
   denominator survives even when geometry stops early. Consistent with the full-table
   discipline.

## 5. Ruling

**IMPLEMENTATION PASS** at commit `c01df73`. The second real Lane G run is now blocked
only by the **user's fresh execution authorization**. On that run the expected flow is:
G0-M (metadata only) → G0-A (uid/missing recensus, expected 13 devices / rank 4 / 5
eligible families — armed stop conditions unchanged) → G0-R → G1–G4 geometry. Lane M,
network, training, report, FINAL, HPC remain sealed.
