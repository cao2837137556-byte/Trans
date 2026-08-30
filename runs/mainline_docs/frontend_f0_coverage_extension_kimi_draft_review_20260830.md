# Kimi Draft Review — Frontend-F0 Coverage Extension Protocol

- Date: 2026-08-30
- Reviewer: Kimi (independent review role)
- Reviewed draft: `runs/mainline_docs/frontend_f0_coverage_extension_protocol_draft_20260830.md`
- Reviewed commit: `e7a7075` (verified single-file commit: only the draft added)
- Governing ruling: `539b313` (CE route ruling, C1–C4 + F1)
- Inherited requirements: `6495a6e` (SHA `b46caf0d…`)

## Verdict

**DRAFT ACCEPTED — freeze authorized after one mandatory pre-freeze
clarification (M1) is incorporated.** The draft faithfully implements C1–C4
and F1 from the route ruling, and its §8 fusion/distinction argument is
correct. One definitional gap in CE-5 must be closed before FROZEN: the
incumbent baseline verdict identity behind `H_old` is currently unpinned.

## Ruling-condition compliance check

| Condition | Draft location | Status |
|---|---|---|
| C1 measurement full-universe, integration narrowed | §5 (full-universe exam; challenger behavior on 13,827 incumbent-finite rows diagnostic only) | ✓ |
| C2 pre-frozen insufficiency stop states | §10.2 single-state whitelist with four required proofs | ✓ |
| C3 attack-side claim downgrade | §3.3 six-level evidence hierarchy; no small-denominator family claims | ✓ |
| C4 frozen deterministic router | §4.1 frozen predicate router with forbidden-input list; no learned routing | ✓ |
| F1 role split 139/23, per-family 60/10, 43/8, 27/5, 6/0, 3/0 | §2 tables | ✓ (reviewer recomputed; exact match) |
| Claim boundary (hydraulic finite-target FPR not solved by CE) | §3.2 verbatim | ✓ |
| Benign role split 3,157/3,079/3,518/1,294/381/49 = 11,478 | §2 table | ✓ exact match |

## M1 — Mandatory pre-freeze clarification: pin the incumbent baseline
verdict identity behind `H_old` and CE-5 conditions 6–8

Reviewer inspected the incumbent scoring code
(`issue27ckda_d1_probe_runner_v1.py::score_frozen`,
`issue27ckda_d1_metrics_v1.py`). The incumbent's missing-row verdict
semantics are **probe-dependent**:

- **G0 (geometry probe):** missing rows are scored `+inf` ("declared
  missing" — `isposinf(score) & missing==1`), i.e. fail-closed hard alarm
  on every missing row. Under a G0 baseline, every old-missing benign-select
  row is incumbent-hard and `H_old` equals the full missing benign-select
  count.
- **P1/P2 (learned probes):** features use `append_missing(normalized,
  missing)`; missing rows receive a finite learned score, so their hard
  verdict is learned, not automatic. Under a P2 baseline, `H_old` is whatever
  the frozen artifact contains.

CE-5 conditions 6–8 ("no benign device has more hard rows than baseline",
"≥3 devices with strict reduction", "reduction ≥ max(300, ceil(0.10·H_old))")
and condition 5 ("every incumbent-hard select attack remains hard") all
presuppose one pinned incumbent verdict identity. Left unpinned, the single
most important number in the development gate would be *discovered after
scores are opened* — exactly the failure pattern this protocol exists to
prevent.

**Required before FROZEN:**

1. Name the exact pinned probe/verdict artifact (probe id, score artifact
   identity, threshold identity) whose hard column defines the incumbent
   baseline for CE-5 conditions 5–8.
2. Compute `H_old` **count-only from the already-frozen fit/select verdict
   artifact** (no new score opening is needed — the artifact is legal and
   frozen) and write the literal integer, its denominator definition
   (old-missing benign-select rows = 5,242 by the §2 role split), and the
   artifact SHA into the FROZEN protocol. `max(300, ceil(0.10·H_old))` then
   becomes a literal constant at freeze time.
3. State explicitly how condition 5 interacts with fail-closed baselines:
   if the pinned baseline makes missing rows hard by construction, then the
   23 select missing attacks are incumbent-hard and condition 5 subsumes
   condition 4; the protocol should say so rather than leave the overlap
   implicit.

## Rulings on §13 questions

**Q1 (`23/23` kill-only guard): ACCEPT.** Strict, non-promotional, and
confined to the only three families with nonzero select denominators; the two
zero-denominator families (Mirai UDP, File Download) remain visible through
the mandatory family tables (test 15) rather than being silently dropped.
Given C3's downgrade this is a safety guard, not evidence of detection
capability. Correctly scoped.

**Q2 (conditions 6–8 mechanical, no identity leak): ACCEPT, conditional on
M1.** Device identity is used only for audit aggregation — consistent with
the standing audit-join discipline and forbidden as a routing/model feature
by §4.1. All three conditions are count-based and mechanical once the
baseline verdict is pinned.

**Q3 (`H_old < 300` automatic `CE_NO_MATERIAL_BENIGN_GAIN`): ACCEPT the
floor's logic, MODIFY the mechanics.** The principle "no material problem →
no material-gain claim" is right. But: (a) the value must be pinned at freeze
time per M1, not discovered at runtime; (b) if the pinned `H_old < 300`, the
correct outcome is a freeze-time discussion of a distinct no-material-problem
terminal state — not a runtime surprise. Note the likely case under a
fail-closed baseline is `H_old = 5,242`, requiring a ≥525 reduction; under a
learned-probe baseline the number must be computed per M1.2.

**Q4 (target-level preservation as the one-shot noninferiority rule):
ACCEPT.** Target-level preservation of every incumbent-hard attack is
strictly stronger than any global recall tolerance and cannot hide changed
families. This matches the project's equivalence-gate culture (Step-0b's
25,467/25,467 is the same shape of guarantee).

**Q5 (§10.2 whitelist narrow enough for C2): ACCEPT.** A single literal
state, reachable only after coverage + safety + real gain + exact incumbent
protection, with a later one-shot protocol proving the residual error mass
sits on incumbent-finite targets. Failed challengers cannot trigger it. No
widening needed.

**Q6 (F1_FRONTEND_CHALLENGE_PASS before CE-2?): CE-2 may run after
`F0_ENCODER_ONLY_PASS`; F1 is required only before CE-4.** CE-2 is
count/identity/copy-only and opens no challenger scores or representations;
its incumbent-equivalence half is challenger-independent. Serializing head
training before a cheap router audit would waste the resource discipline in
§12. The draft's own staging already implies this; state it explicitly in
§7 (CE-2 prerequisites: F0_ENCODER_ONLY_PASS + count-only artifacts; CE-4
prerequisites: F1_FRONTEND_CHALLENGE_PASS + separate user authorization).

## Additional findings (no change required)

1. §4.2's incumbent copy gate (13,827/13,827 ownership, score byte strings,
   hard verdicts; 0 duplicates) is the correct invariance construction — same
   shape as the Step-0b equivalence gate.
2. §8's fusion distinction is correct and important: routing assigns ownership
   before any score is examined; comparing routed output to baseline is an
   evaluation gate, and a challenger that loses an old-hard attack is
   rejected rather than repaired. This is what keeps CE from becoming CKDC
   under another name.
3. §12 anti-waste constraints (mature-component first, zero-training
   prototype first, no paired-corpus download before `F0_ENCODER_ONLY_PASS`,
   at most one learned challenger, no family-specific patches, no gate
   relaxation) are exactly the resource discipline this project needs.
4. §9 test list covers the material mechanics, including the exact 23-row
   denominator (test 14), zero-denominator family visibility (test 15), the
   ≥3-device rule (test 17), and the `max(300, …)` boundary (test 18).

## Mechanics before freeze

1. Incorporate M1.1–M1.3 verbatim (probe identity, literal `H_old` + artifact
   SHA + denominator definition, condition 4/5 overlap statement).
2. State the CE-2/CE-4 prerequisite mapping per Q6 explicitly in §7.
3. Update §13 from questions to these rulings.
4. Generate FROZEN + SHA-256 sidecar for reviewer SHA/diff verification.

This review authorizes mechanical revision toward FROZEN only. No
implementation, retrieval, decode, training, or execution is authorized.
