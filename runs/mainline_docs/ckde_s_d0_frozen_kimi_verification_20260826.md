# CKDE-S D0 FROZEN — Kimi Freeze Terminal Review (SHA/diff verification)

- Reviewer: Kimi
- Date: 2026-08-26
- FROZEN document: `runs/mainline_docs/ckde_s_d0_attack_protected_device_shift_and_paired_corpus_preregistered_20260826.md`
- FROZEN commit reviewed: `7e833ab`
- Prior draft commit: `97a89d8`; Kimi draft review: `f32272c`
- Verdict: **FREEZE PASS — protocol is FROZEN and eligible for the two separate user
  authorizations (Lane G, Lane M).**

## 1. Hash verification (independently recomputed)

- Recomputed SHA-256 of the FROZEN document:
  `e2de3bd75ac0f4e9a1d90180bcc9db938418e44719f08bac5a89d07b29cf29e6`
- Sidecar `.sha256` content: identical.
- Codex-reported SHA-256: identical. **PASS.**

## 2. Full-text diff: draft (`97a89d8`) → FROZEN (`7e833ab`)

Every changed hunk was inspected. The diff contains exactly four classes of change and
nothing else:

1. **Status mechanics** — title DRAFT→FROZEN; status line updated to pending independent
   SHA/diff verification and separate Lane G/Lane M authorizations; §15 open questions
   converted to normative rulings; §16 authorization boundary updated. All expected.

2. **Q7 blocking review gate (my MODIFY) — fully and faithfully implemented:**
   - New M1R step: candidate-1 terminal verdict plus literal reason codes written
     atomically, hashed, sealed before any candidate-2 request.
   - New M1K step: blocking independent Kimi review; candidate 2 starts only after a
     committed, digest-matched `PROCEED_CANDIDATE_2` ruling; missing/mismatched/
     non-proceed ruling is fail-closed and leaves candidate 2 unopened.
   - Explicit non-relaxation clause: the review may verify protocol compliance and
     admissibility, but may NOT alter candidate-2 acceptance conditions in response to
     the candidate-1 failure reason; the candidate-1 reason cannot relax, reinterpret,
     or add candidate-2 criteria.
   - State machine updated: `M1_NBAIOT_FAILED_PENDING_KIMI_REVIEW` is a real blocking
     state; candidate-1 PASS is terminal and permanently blocks candidate 2; joint
     lattice gains `CKDE_S_PAUSED_FOR_INDEPENDENT_CANDIDATE_REVIEW`.
   - Contract tests extended with items 28–29 covering atomicity/hash of the sealed
     verdict and the digest-matched proceed gate.
   This matches, and in the non-relaxation clause slightly exceeds, what my review
   required. PASS.

3. **Q8 zero-shot challenge-relevance gate (my freeze-now requirement) — implemented as
   new §9.5:** the exact numeric form is correctly reserved for the later external
   execution protocol (D0 opens no external scores, so fixing numbers now would be
   unfounded), while the principle is frozen now with all five elements I required:
   frozen from metadata/count evidence before score access; deterministic hash-split of
   development vs wholly untouched devices; kill-only (may disqualify, may not select a
   transform/rank/constant/fallback/corpus); failure yields only
   `NO_ZERO_SHOT_BENIGN_SHIFT_TO_REMOVE` and never positive method evidence; a relevance
   failure does not authorize another dataset search or gate revision. Contract tests
   30–31 pin this. PASS.

4. **Normative rulings on Q1–Q6:** recorded exactly as my review ruled — rank rule
   accepted without in-run downgrade; LODO constants with worst-device guards;
   between/within gates as drafted; gradients primary, mean contrasts diagnostic only;
   residual gates 0.50/0.65 and 25% floor accepted; external six-device/three-dual-family
   minimum accepted. **No numeric threshold, gate constant, or scientific rule drifted.
   Zero drift confirmed.**

Contract test count grew 27 → 31, consistent with the two new mechanisms and nothing
else.

## 3. Ruling

**FREEZE PASS.** The CKDE-S D0 protocol is frozen at SHA-256
`e2de3bd75ac0f4e9a1d90180bcc9db938418e44719f08bac5a89d07b29cf29e6` (commit `7e833ab`).

Authorization state after this review:

- **Lane G (internal geometry audit, local, no network):** requires the user's explicit
  implementation/execution authorization. Opening the frozen fit-only E3 embeddings
  becomes permitted only under that authorization, and only within the frozen audit
  surface.
- **Lane M (external metadata retrieval, network):** requires a separate, independent
  user authorization. It is not bundled with Lane G.
- The M1K blocking review is now a live obligation on me: if N-BaIoT fails, Codex seals
  the verdict and I must issue a digest-matched `PROCEED_CANDIDATE_2` (or terminate)
  before CICIoT2023 is touched. I will verify the sealed digest against the delivered
  artifact at that time.
- Everything else — bulk download, training, adapter execution, score opening beyond
  the frozen fit assets, HPC, report, FINAL — remains sealed.
