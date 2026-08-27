# CKDE-S D0 Lane G — Kimi R1 Repair Verification (Final Implementation Approval)

- Reviewer: Kimi
- Date: 2026-08-27
- Range verified: `7c7524b` → `269e4b3`
- Verdict: **R1 VERIFIED — Lane G implementation is FULLY APPROVED.** The route is now
  ready for the user's separate real-execution authorization.

## 1. Diff scope

`git diff 7c7524b 269e4b3` touches exactly three files and nothing else:

1. Implementation: **one line** — `between_within` sort key changed from
   `["event_position", "uid"]` to `["timestamp_epoch", "uid"]`. Exactly the required fix.
2. Contract tests: `test_11` gains a `timestamp_epoch` column; new discriminating
   regression `test_11b_between_within_uses_causal_timestamp_not_session_length`.
3. Implementation report: §5 result updated to 23/23 and §8 documents the repair.

No constant, gate, state name, identity pin, or authorization boundary changed.
`terminal_session_rows` still selects the within-session terminal target by
`event_position`, which is correct and was never in scope.

## 2. The new regression genuinely discriminates

I traced `test_11b` by hand. Four sessions have timestamp order `s1,s2,s3,s4` but
terminal `event_position` values `1,4,2,3`, so the length order disagrees with the time
order. Vectors are `[0, 0, 10, 10]` in timestamp order.

- Sorting by `timestamp_epoch`: early half = {s1,s2} → median 0; late half = {s3,s4} →
  median 10; `within_early_late_norm = 10`.
- Sorting by `event_position` (the old bug): order s1,s3,s4,s2 → early = {s1,s3} →
  median 5; late = {s4,s2} → median 5; `within_early_late_norm = 0`.

The assertion `within == 10.0` passes only under the causal ordering. The regression
would have caught the original defect. Approved.

## 3. Independent re-verification

- `py -3.9 repo/ood/issue27ckde_s_d0_lane_g_geometry_audit_contract_tests_v1.py`
  → **23/23 PASS** (reproduced independently).
- `py -3.9 -m py_compile` on both files → PASS.

## 4. Ruling

Lane G implementation is **fully approved** at commit `269e4b3`. All five review
questions from the implementation report stand confirmed; the single required repair is
verified as exactly scoped.

Authorization state:

- Real Lane G execution — opening the pinned embeddings/probe-state and producing the
  G0–G4 verdict — now awaits only the **user's explicit execution authorization**.
- Lane M (external metadata retrieval) remains separately unauthorized.
- FINAL, report, training, HPC, and any score opening beyond the frozen fit assets
  remain sealed.
