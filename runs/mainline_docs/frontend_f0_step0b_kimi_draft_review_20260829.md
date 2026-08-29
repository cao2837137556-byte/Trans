# Frontend-F0 Step-0b Causal Re-decode Attribution — Kimi Draft Review

- Reviewer: Kimi
- Date: 2026-08-29
- Draft: `runs/mainline_docs/frontend_f0_step0b_causal_redecode_attribution_prereg_draft_20260829.md` (commit `ec13e2a`)
- Verdict: **DRAFT PASS with two MODIFY (S1, S2).** Codex may freeze after mechanical
  incorporation. No packet opening, implementation, or execution authorized.

## 1. Prior verification feeding this review

The draft's predicate semantics rest on the pinned formal embedder, which I already
read directly during Round 3 (`96172df`): the missing branch is the four-predicate
compound gate, IP session candidates are constructed for ALL IPv4/IPv6 protocols
(including ICMP/GRE) and appended BEFORE the target gate is evaluated. The draft's
§4.1–§4.5, including the append-before-gate ordering and the fail-closed rule if the
append path raises on a non-finite timestamp, match the source exactly. The
tail-reentry discipline (§4.4: state released after the last selected target, never
recreated) correctly inherits the CKDA D1 local-adapter repair we already verified.

## 2. Rulings on the six open questions (§11)

### Q1 — Gotham identity: **MODIFY (S1). Whole-archive SHA-256 becomes mandatory.**

As drafted, Gotham members are pinned by published archive identity + central-directory
member name + uncompressed bytes + CRC32. CRC32 is a 32-bit corruption check, not an
identity pin; and "published archive identity" is provenance, not a pin of the local
bytes. Computing one whole-archive SHA-256 of the local Gotham archive at pre-open is
cheap (one pass, one time) and upgrades the exact local artifact to a cryptographic
identity — the same standard we applied to every other container in this project.
Ruling: whole-archive SHA-256 of the Gotham archive is **mandatory** at R0 (recorded
before any decode), alongside the published identity and per-member CRC32/size, which
remain as decode-integrity checks. Direct PCAPs already require whole-file SHA-256;
archives must not be held to a weaker standard.

### Q2 — IP-key and poison semantics vs parent intent: **CONFIRMED**, with one
classification-relevant observation that feeds S2

Semantics match the verified source: ICMP/GRE targets DO receive formal IP session
candidates and CAN be timestamp-poisoned; predicate booleans are independent and may
overlap; equality is not regression; poisoning affects current and later targets only.
The observation: because the missing gate is an OR over four predicates and predicates
overlap, **which predicate is "binding" for a given target is not determined by the
primary-reason precedence**. See S2.

### Q3 — Exact 25,467/25,467 missing-equivalence sufficiency: **ACCEPT, with the
validation-scope clarification recorded in the FROZEN protocol**

Exact row-level equality of `redecoded_missing == frozen_missing` on all 25,467 rows
completely validates the reconstruction of the OR-of-predicates (the missing decision)
without recomputing embeddings — embeddings are irrelevant to attribution. However, the
equivalence gate cannot validate the individual predicate booleans: a missing row whose
true cause is protocol would still match if reconstruction wrongly asserted regression
(the OR is true either way). Individual-predicate fidelity therefore rests on the frozen
literal semantics (§4.1–§4.5), contract tests 9–20, and the verbatim reporting of parser
defaults. The FROZEN text must state this scope explicitly so nobody later cites the
equivalence gate as validating per-predicate attribution. With that clarification, the
gate is sufficient.

### Q4 — Route naming vs attribution-only: **keep route naming, but MODIFY (S2) the
presence rule from primary-reason counts to any-true-predicate unions**

Deferring route naming would only add a round-trip, and a frozen presence-based rule
imports no outcome selection. But the drafted rule — "exactly one non-configuration
mechanism class has non-zero **primary** count" — has a real defect. Worked example:
Merlin ICMP Flooding targets are unsupported-protocol by design; if any of their
sessions also suffered a timestamp regression before the target cutoff, the inherited
precedence assigns primary reason = REGRESSION, and PROTOCOL_COVERAGE would show **zero
primary count** — the classifier could conclude the sole blocker is causal timestamp
order, when in truth repairing timestamps alone recovers nothing for those targets.
The missing gate being an OR means a target is recoverable **only if every true
predicate is addressed**.

S2 therefore requires: in R4, a mechanism class is **present** iff its predicate is
true for at least one missing target — computed as the union over ALL four booleans
(primary or secondary), not from primary-reason counts. `primary_reason` remains as a
frozen descriptive column. Classification rules 1–3 are otherwise unchanged, and the
verdict JSON must carry both the per-class any-true counts and the primary-reason
distribution. This stays deterministic, threshold-free, and presence-based.

### Q5 — Identity attachment as implementation artifact: **ACCEPT as drafted**

The 30 members' byte identities are facts not yet fully observable, so an erratum-freeze
is impossible without first reading archive central directories. Freezing the schema and
the nine conjunctive pre-open assertions here, materializing the attachment in R0 with
fail-closed behavior on any assertion failure, and delivering it with the implementation
package for my review before the user authorizes execution is the correct chain. The
fail-closed assertions (not a mid-run human gate) are the enforcement mechanism.

### Q6 — Member-scoped checkpoints and resource gates: **ACCEPT**

The member-atomic checkpoint discipline mirrors the already-proven CKDA D1 local
two-pass pattern: resume only at completed-member boundaries, no partial member enters
an aggregate, resource shortfall is an engineering stop. Adequate for an interruptible
offline Windows run.

## 3. Additional affirmations (no change requested)

1. Test battery (32 items) covers the causal-ordering adversarial cases that matter —
   including "modifying a future packet cannot change an earlier target" (item 8),
   post-last-target state recreation (18), and the append-ordering fail-closed case (14).
   The clause forbidding observed per-cause counts as test expectations is present.
2. The claim boundary (§10) correctly refuses to link missingness to hydraulic FPR and
   refuses wild-prevalence generalization from a challenge-enriched role distribution.
3. Session denominators are computed from reversible session candidates during the
   audit — records cannot masquerade as independent support.

## 4. Next chain

S1/S2 incorporated → FROZEN + SHA sidecar → my SHA/diff terminal review →
implementation + 32-test battery under a user implementation authorization → my
implementation review (including the R0 identity attachment) → user execution
authorization for the re-decode run. Nothing else is authorized.
