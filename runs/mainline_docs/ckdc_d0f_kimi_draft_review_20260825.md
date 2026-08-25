# CKDC D0-F draft — Kimi independent review

**Date:** 2026-08-25
**Reviewed:** `ckdc_d0f_m7_certificate_provenance_prereg_draft_20260825.md` (commit `22090b2`)
**Reviewer:** Kimi

## Verdict: DRAFT PASS — authorize FROZEN generation, with three minor notes (no re-draft needed)

Phase-A execution still requires explicit user authorization after freeze, per draft §9.

## 1. Independent verification performed

**Pinned identities — 5/5 verified locally by recomputation:**

| input | SHA-256 | result |
|---|---|---|
| CKDA D1 FROZEN contract | `ecb4299265...50aa9` | PASS |
| fit/select plan CSV | `eed3d431ab...99aeac` | PASS |
| threshold freeze marker | `84576a5008...4dd5b` | PASS |
| report scores (Phase-B only) | `7ed1c0e9eb...a0e6f9` | PASS (existence+hash only; rows not opened) |
| CKBW record predictions | `d1e905924e...dadf85` | PASS (at the absolute transfer path pinned by CKDC D0 prereg) |

**Tail-threshold direction — empirically confirmed on the committed legal-select quadrant CSV
(read-only, no audit execution):**

- benign conflicts (4,986): **99.9%** have `tail_margin_score <= τ_normal` (τn = 0.9713227);
- support attacks (69): **0%** below τn (min score 0.9849) — `tail_normal` is structurally false
  for every legal attack;
- exact-equality rows in the entire legal select set: **1** (a benign both-normal row).

Consequences:
1. The `<= τ_normal` orientation in §4 is **correct**: the CKBW score is attack-oriented, the
   normal side is the low side. My recompute settles this positively, not just by argument.
2. The `<=`/`<` boundary choice (§4 freezes equality as normal evidence; M7's hard rule uses
   `>=`) affects exactly **1 of 7,069** rows and that row is not in any conflict quadrant.
   Accepted as measure-zero; the freeze + contract test 4 make it deterministic. **Note 1.**
3. Since `tail_normal` is true for 99.9% of benign conflicts, the certificate's discriminating
   work will be done almost entirely by `c1_normal ∧ ckbq_normal`. Phase A's coverage gates are
   therefore genuinely informative — they measure exactly the open question.

## 2. Codex's three review requests

**Q1 — Option-A `<=` τ_normal semantics:** verified above. Correct orientation, frozen boundary,
fail-closed missing-value behavior (`cert=false` preserves P2). PASS.

**Q2 — 300 / 5% / 3-source / 80% gates:** consistent with the already-frozen CKDC D0 H3 benign
side discipline (rows ≥ 300, source groups ≥ 3, max share ≤ 0.80 — reproduced in D0's verdict
JSON clause names). **Note 2:** the 5% clause is mathematically subsumed by the 300-row clause
(300/4,986 = 6.02% > 5%), so it can never bind. Harmless redundancy; keep it as an explicit
sentinel, no change needed. Non-vacuity gates are correctly framed as minimums, not effectiveness
claims. PASS.

**Q3 — Phase A/B authorization and file isolation:** satisfies the two-phase freeze I required
in `ckdc_route_kimi_round2_review_20260825.md`:
- Phase A receives no Phase-B path/handle, path allowlist rejects viewed/FINAL markers before
  open, and contract tests 2/3/10/11 pin this mechanically;
- Phase B launches only on the exact hashed Phase-A marker, re-hashes all inputs independently,
  and must reproduce the 51,057 denominator (incl. 45,090 future_query) before evaluation;
- separate explicit user authorizations per phase (§9). PASS.

## 3. Additional observations (no action required)

- **Clause 6 (69/69 support attacks remain hard) is structurally guaranteed**: M7 hard ⟹ CKBQ
  hard ⟹ `ckbq_normal=false` ⟹ certificate false ⟹ `candidate_hard` preserves P2. Keeping it as
  an asserted clause is right — it converts a proof obligation into a runtime check.
- **Clause 8/9 (non-equivalence to `P2∧M7` and to `M7 normal`)**: on legal rows,
  `cert ⟹ M7_normal` holds by construction, so non-equivalence reduces to the existence of
  M7-normal rows where C1 or CKBQ fires — i.e., the clauses test exactly the added evidence. Sound.
- **Phase-B per-role/per-family counts** are correctly labeled diagnosis-only; the draft's
  closure rule (any flip → permanent close, no revision) already forbids feeding them back.
- **Note 3 (editorial):** §3 item 5 names `ckbw_record_predictions.csv.gz` without its directory.
  The FROZEN version should carry the full pinned path
  (`supercompute_transfer/ckbw_157624_extract/issue27ckbw_.../ckbw_record_predictions.csv.gz`)
  as the CKDC D0 prereg did, so the identity is self-contained.

## 4. Scientific position

This draft is the correct minimal step: it tests one pre-existing hypothesis (CKBW Option A,
written 2026-08-07, never tested) rather than searching; its Phase A is incapable of touching
viewed evidence; its Phase B can only falsify. Whatever it returns — CERTIFICATE_CANDIDATE or
NO_CERTIFICATE — the result is publishable-grade knowledge about whether frozen signal
conjunctions can separate benign conflicts from stealthy attacks.

## 5. Standing obligations (unchanged)

- CKDA D1 formal HPC replay is now past the expected cluster-return date (~2026-08-23); request
  status and scheduling. Localwin checkpoints must not be reused on HPC.
- FINAL (cooler-motor, seed 37/47) sealed; CKDB closed; this review authorizes FROZEN generation
  only — not implementation, not Phase A, not Phase B.
