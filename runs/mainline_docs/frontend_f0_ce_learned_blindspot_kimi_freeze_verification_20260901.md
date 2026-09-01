# Kimi Freeze Verification — CE Learned Blind-Spot Branch D0/D1 (FROZEN)

- Date: 2026-09-01
- Reviewer: Kimi (independent review role)
- FROZEN document: `runs/mainline_docs/frontend_f0_ce_learned_blindspot_branch_d0_d1_frozen_20260901.md`
- Sidecar: same name `.sha256`
- Freeze commits: `5c4aa36` (freeze) + `6fcfa0e` (EOF normalization + sidecar refresh; diff inspected — trailing blank line only)
- Draft under comparison: `b700f3d`; governing review: `4d8126a`

## Verdict

**FREEZE VERIFICATION: PASS.** All rulings from `4d8126a` (M1, Q1 literal
table, Q2 strengthening, Q3, Q5 definitions, Q7 canary cut, Q8 portability
conditions) are incorporated verbatim in substance; §17 is converted to
normative rulings; zero scientific drift anywhere else. The FROZEN document
also correctly and honestly retains the pre-computed consequence
`29 < 30 → CEL_D1_INSUFFICIENT_INDEPENDENT_ATTACK_CONTEXTS`, with explicit
text forbidding bound-lowering, cross-phase context recovery, and row
resampling. That honesty is noted with approval.

## Independent verification

1. **SHA-256**: recomputed `016d61a9d776f6ba6e0218ce1b753e3bf403fa3dab303630b2809beb6f6e5eea` — matches sidecar and handoff ✓
2. **Commit scope**: `5c4aa36` adds only document + sidecar; `6fcfa0e` touches only the same two files (EOF newline) ✓
3. **Full draft→FROZEN diff**: every change traced to a ruling; no other
   section altered ✓
4. **The critical number, recomputed independently** by the reviewer from the
   pinned ZT-2 status table + frozen plan + frozen availability container:
   - fit attack contexts pre-exclusion: **40**
   - attack-bearing cross-phase contexts: **11**
   - legal fit attack contexts post-exclusion: **29**
   - per family post-exclusion: File Download 2, Merlin C&C 3, Merlin ICMP 13,
     Mirai GRE 10, Mirai UDP 1
   All match the FROZEN literals exactly. ✓

## The strategic consequence — stated plainly

This freeze is technically sound and **pre-terminates the route's positive
path**: D0-A's mechanical re-verification will reproduce 29 legal fit attack
contexts, which is below the frozen global floor of 30, so the only lawful
outcome is `CEL_D1_INSUFFICIENT_INDEPENDENT_ATTACK_CONTEXTS`. The detector-head
protocol cannot be drafted from this route, and the CE learned blind-spot
branch cannot reach `CEL_D1_REPRESENTATION_FEASIBLE`.

Reviewer notes for the record:

1. **The floor did its job.** The integer 30 is not sacred — 29 vs 30 is
   scientifically meaningless. What is meaningful: 162 attack rows collapse to
   **29 independent contexts** (two families at 1–2). Row counts masquerading
   as independent evidence is exactly the failure this gate exists to catch.
   Holding the frozen bound after learning the count is the only disciplined
   move; Codex's refusal to lower it is correct, and the reviewer explicitly
   declines to amend his own floor now, because amending it after seeing the
   count would be outcome-conditioned rule-making.
2. **This is a usable scientific result, not just a dead end.** "On this
   corpus, the blind-spot attack subset supports at most 29 independent
   fit contexts across five families — insufficient for any honest
   attack-information or detection claim" is a rigorous, publishable negative
   boundary. It belongs in the paper's evaluation-threats narrative alongside
   the six sealed correction routes.
3. **Recommendation on D0 execution: do not execute solely to record a known
   termination.** The census, nomination, and resource audits have reuse
   value only if a future variant route opens; spending execution now buys a
   formality. (User's call; execution remains legal under the frozen chain.)
4. **What remains open and unaffected**: the incumbent system (97.37%/96.68%
   attack side, local) is untouched; ZT-2's 100% semantic coverage result
   stands; the hydraulic finite-target representation-quality problem — the
   actual central open problem — is unaffected and remains the main line;
   Data-F0b stays sealed (and note: no external corpus can change the frozen
   25,467-target universe's context denominators anyway; new data would be a
   separate corpus line under its own protocol).

## Authorization state

No implementation, census execution, nomination, training, representation,
score, report/FINAL, or HPC action is authorized by this verification. The
next legal actions, each requiring explicit user direction:

- formally close this route (with or without a record-only D0 execution);
- open a new protocol discussion on the finite-target representation-quality
  line (hydraulic class);
- or direct work to the paper line.
