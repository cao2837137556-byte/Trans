# Frontend-F0 Step-0b FROZEN — Kimi Freeze Terminal Review

- Reviewer: Kimi
- Date: 2026-08-29
- FROZEN document: `runs/mainline_docs/frontend_f0_step0b_causal_redecode_attribution_preregistered_20260829.md`
- Freeze commit: `3a2d635`; binding draft review: `18d5c88`
- Verdict: **FREEZE PASS.** Step-0b is frozen and awaits the user's implementation
  authorization.

## 1. SHA verification

- Recomputed SHA-256:
  `ace6a37fa1ad84fb1660426d4e6c6876fdd3bc407577e3b0709908465b910794`
- Matches Codex's report and the `.sha256` sidecar. **PASS.**

## 2. Diff review: draft → FROZEN (every hunk inspected)

All changes are mechanical incorporations of my draft review (`18d5c88`), nothing else:

1. **S1 (Gotham identity):** attachment schema now splits `container_sha256` /
   `published_identity_if_archive`; whole-archive bytes + SHA-256 mandatory and recorded
   before any decode; published identity and per-member CRC32/size retained explicitly as
   independent provenance and decode-integrity checks; a published identity or CRC32 may
   not substitute for the local-bytes SHA-256. Pre-open assertion 8 and test 2 both
   strengthened: a missing/mismatched Gotham whole-archive SHA fails before member
   decoding **even when** published identity and CRC32/size match. Exactly as ruled.
2. **S2 (any-true presence):** R4 now defines mechanism-class presence by the union of
   any-true primitive predicates (primary or secondary); the verdict carries per-class
   `any_true_missing_target_count` plus the descriptive `primary_reason` distribution;
   the binding recoverability sentence ("a missing target is recoverable only after
   every true predicate on that target is addressed") is now in the protocol; test 19
   strengthened to require per-class any-true presence independent of primary reason.
   Exactly as ruled.
3. **Q3 scope limitation:** R3 carries an explicit paragraph stating the equivalence
   gate validates only the reconstructed OR (the frozen missing decision), that
   individual-predicate fidelity rests on frozen semantics + tests 9–20 + execution-order
   preservation + verbatim parser-default reporting, and that neither the report nor the
   verdict may cite R3 alone as per-predicate attribution proof. Exactly as ruled.
4. **Q1–Q6 converted to normative rulings** matching my review verbatim; status and
   authorization chain updated (implementation requires user authorization; the real
   re-decode requires a later separate execution authorization after implementation
   review).

No scientific rule, predicate definition, denominator, state vocabulary, or claim
boundary drifted.

## 3. Authorization state after this freeze

1. **Implementation** (Step-0b runner + 32-test battery, synthetic fixtures only) —
   awaits user implementation authorization.
2. **Implementation review** — I review the code, tests, and the R0 packet identity
   attachment (including the new Gotham whole-archive SHA-256).
3. **Real execution** (packet opening + causal re-decode) — awaits a later, separate
   user execution authorization after that review.

Training, embedding, checkpoint inference, network, report, FINAL, HPC, and performance
claims remain sealed.
