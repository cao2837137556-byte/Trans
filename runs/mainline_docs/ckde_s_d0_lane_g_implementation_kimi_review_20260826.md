# CKDE-S D0 Lane G — Kimi Implementation Review

- Reviewer: Kimi
- Date: 2026-08-26
- Implementation commit reviewed: `17414b3`
- Files reviewed: `repo/ood/issue27ckde_s_d0_lane_g_geometry_audit_v1.py` (555 lines, read in
  full), `repo/ood/issue27ckde_s_d0_lane_g_geometry_audit_contract_tests_v1.py` (230 lines,
  read in full), implementation report.
- Verdict: **CONDITIONAL PASS — one required fix (R1) before real execution.** The fix is
  narrow and mechanical; after Codex delivers it with a regression test, I will verify the
  diff narrowly, and only then should the user grant the execution authorization.

## 1. What I independently did

1. Read both source files in full, line by line.
2. Cross-checked every gate and definition against the parent FROZEN contract §6–§7 and
   the erratum literals.
3. Independently re-ran the contract suite with the actual Python 3.9 runtime:
   `py -3.9 repo/ood/issue27ckde_s_d0_lane_g_geometry_audit_contract_tests_v1.py`
   → **22/22 PASS, reproduced** (0.223s).
4. Verified the role census constants sum to the frozen denominator
   (6600+4000+4000+4000+3000+809+2604+385+69 = 25,467).
5. Verified the runner itself pins the parent contract and erratum SHA-256 and refuses to
   execute on documentation drift — the contract polices itself at runtime.

## 2. Rulings on the five review questions (report §6)

**Q1 — Terminal-target operationalization of "complete causal session embedding":
CONFIRMED.** `terminal_session_rows` selects the last frozen target per
(source_group, session_id) after role filtering, one embedding per session. Because the
CKDA D1 embeddings are current-inclusive causal prefixes, the last target's embedding is
exactly the complete-session causal representation. Equal weighting per session holds;
a session cannot gain weight from having more target records. Missing terminal
representation is an engineering failure, not a zero vector. Correct.

**Q2 — Retained between-device energy formula: CONFIRMED.** Per device,
`||U_remove^T (c_d - c_g)||² / ||U^T (c_d - c_g)||²`, equal-device median, gate ≥ 0.25.
This matches contract §7.3 ("at least 25% of median between-device energy remains in
U_remove") and the report's formula. Since range(U_remove) ⊆ range(U) by construction
(U_remove = orth((I − P_Vraw) U)), the ratio is mathematically bounded by 1; the
zero-denominator fallback to 0.0 is conservative. No record-weighted alternative exists
in code. Correct.

**Q3 — Eligible major family definition: CONFIRMED.** Eligible = exact fit-attack
families with ≥ 15 independent (terminal) sessions; the `residual ≥ 0.50` conjunct
applies to *every* eligible family, the `≥ 0.65` conjunct to ≥ 80% of eligible families
(ceil), matching contract §7.2 verbatim. Ineligible families are reported in the full
family table with `eligible=False` and cannot silently enter the protection space.
The family-strata integrity check (one exact family per attack session) is present.
Correct.

**Q4 — Count-before-NPZ ordering: CONFIRMED, code- and test-verified.**
`materialize` runs `count_rank_gate` on metadata only, writes `count_rank.json`, and on
G0 failure writes the verdict with `embedding_arrays_opened=0` and returns before
`load_arrays` is reachable. `test_02` proves this by mocking `load_arrays` to raise if
called. `role_open_audit` only flips the open counters inside `load_arrays`. Correct.

**Q5 — P2 gradient is the frozen logit gradient: CONFIRMED.** The implementation computes
∂z/∂values analytically through the frozen 769→128→1 ReLU MLP:
`(active * w2) @ W1[:, :768] / scale`, with missing coordinates zeroed (correct, because
missing coordinates are clamped to 0 in the normalizer and therefore carry no gradient),
per-row normalized before aggregation. This is the **logit** gradient — not the BCE
gradient (no sigmoid factor), not a final-layer proxy. `test_12` checks agreement with
the analytic expectation; zero, floor-equal, and non-finite gradients all fail closed
(tests 13/14/14b). Correct.

## 3. Required fix — R1 (blocking)

**`between_within` does not implement the contract's *causal* early/late split.**

Contract §6.2: "Each eligible device is split causally into early and late session
halves." The purpose of W_d is to measure **within-device temporal drift**, so that the
R_d gate can distinguish genuine cross-device structure from a device simply wandering
over time.

The implementation sorts a device's terminal session rows by
`["event_position", "uid"]` before halving. For terminal rows, `event_position` is the
position of the last target *within its own session* — i.e., essentially session length,
not time. Sorting sessions by length and halving produces a "short sessions vs long
sessions" split. W_d would then measure length-correlated representation variation
(prefix-accumulation effects), which is a different quantity than temporal drift, and the
frozen R_d gate would silently answer a different question than the one we pre-registered.

This is not a nitpick: hydraulic-class devices are exactly where session length and time
are entangled, and the entire CKDE-S route exists because of a length/time-confounded
failure mode.

Required change (narrow, mechanical):

1. In `between_within`, sort `part` by `["timestamp_epoch", "uid"]` (metadata schema
   already pins `timestamp_epoch`; it is present in the required columns).
2. Add a regression test that discriminates the ordering: construct sessions whose
   *length order* disagrees with their *time order*, with a known drift direction, and
   assert the early/late halves follow `timestamp_epoch`, not `event_position`.
3. Re-run the full suite (expected 23/23) and deliver the diff.

No other change is authorized by this review item; rank, gates, state names, and all
literals stay untouched.

## 4. Non-blocking observations (no action required)

1. `test_11` (between/within synthetic) uses `event_position = session` increasing, so it
   passes under either sort key — which is why R1 slipped through the suite. The new R1
   regression test closes this hole.
2. `local_global` recomputation inside LODO (re-centered without the held-out device) is
   the faithful reading of "refit U_-d without d"; endorsed.
3. Pinning the contract/erratum SHA inside the runner itself, the refuse-to-overwrite
   output rule, and staged atomic writes with engineering-failure cleanup are all
   implemented exactly as the contract requires; recorded as process positives.

## 5. Ruling

**CONDITIONAL PASS.** Implementation is approved in all respects except R1. Codex is
authorized to apply exactly the R1 fix (sort key + discriminating regression test +
suite re-run) under the existing implementation authorization, then deliver a narrow
diff report. After I verify that diff, the implementation will be fully approved, and
the user may then grant the separate **execution** authorization for the real Lane G run.
No real embedding has been opened; nothing in this review opens one.
