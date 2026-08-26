# CKDE-R D0 draft — Kimi review

**Date:** 2026-08-26
**Reviewed:** `ckde_r_d0_representation_commissioning_identifiability_prereg_draft_20260826.md`
(commits `50295ff`, `de6c726`)
**Reviewer:** Kimi

## Verdict: DRAFT PASS — may proceed to FROZEN; rulings on all seven §13 questions below, plus two recorded caveats

## Preliminary checks

- Round-2 convergence items all present: Audit-0 pre-embedding termination (no "diagnostic
  interest" continuation), 2×2 incidence cycle, global literal shrinkage, literal stability
  ladder, entanglement audit, kill-only synthetic shift, three denominator levels, A/B/C/D
  state machine with engineering-failure separation.
- The 768D/769-width correction is handled correctly: real shapes pinned, 132D assumptions
  fail-closed (contract test 2). The correction makes the stability ladder *more* likely to
  land on CENTER_ONLY or B — which is the ladder working as designed, not a defect.
- Synthetic-shift construction is deployment-faithful in a way worth crediting: attacks receive
  the **full raw** shift `v_d = mu_raw_d − mu_g` while the transform removes only the shrunken
  `λ·v_d`, leaving `(1−λ)·v_d` on the attack — exactly what a real attack on that device would
  carry after commissioning. No hidden optimism.

## Rulings on §13

**Q1 — 2×2 cycle as minimum identifiability: ACCEPT.** Two devices × two families with ≥15
independent attack sessions per cell is the minimal design in which "attack movement follows
device movement" is separable from "families just differ". Requiring a larger graph would risk
making Audit-0 unpassable for reasons unrelated to science. Caveat C1 (record, not change): with
exactly one 2×2 cycle, the bootstrap quantifies within-cell sampling noise only; the
entanglement verdict's inferential scope is the observed graph. The draft already states this
scope limit (§7 final line) — keep it verbatim in the FROZEN and in any future claim.

**Q2 — λ_center=0.50 / λ_scale=0.25 at 768D: ACCEPT.** With 64 sessions, the per-coordinate
median standard error is ~0.16·σ; shrunk to λ=0.50, the injected correction noise is RMS ≈ 0.08
of global scale — comfortably inside the 0.15 center gate, which means the gates discriminate
genuine instability rather than baseline sampling noise. Log-scale λ=0.25 is appropriately more
conservative. The ladder makes these choices self-correcting (unstable → demote → B), and
post-result modification is forbidden. Caveat C2 (record, not change): the bootstrap measures
variability around the full-sample estimate, not around the truth; it slightly underestimates
total uncertainty. Acceptable for a stability screen; the caveat should appear in the D0 output
documentation.

**Q3 — Gates 0.15/0.35 and 0.10/0.25: ACCEPT.** Literal, predeclared, with the crucial
worst-device guards that prevent equal-device averaging from hiding one unstable commissioned
device. Interpretation notes (RMS of global scale; ~10.5% multiplicative) make them reviewable
by third parties. Their achievability is unknown by design — state B is an admissible answer.

**Q4 — Entanglement ceilings 0.25/0.25: ACCEPT as justified.** In 768D, the noise floor of a
random cosine is ~1/√768 ≈ 0.036, so 0.25 is far above noise yet still a strict quarter-shift
ceiling; requiring ~0 would fail on sampling artifacts, requiring more would admit material
alignment. The verbatim reporting obligation (values plus margins, not just pass/fail) is what
makes any ceiling defensible — keep it prominent in outputs.

**Q5 — Entanglement failure stays a subreason of B: YES.** B means "no safely usable shift";
an entangled-but-stable shift is precisely that. A fifth state would add taxonomy without
changing consequences (both stop the route with named reason). Keep `ATTACK_SHIFT_ENTANGLED`
inside B.

**Q6 — Synthetic additive translation as kill-only: ACCEPT** under the converged ceiling
(falsification only, never positive within-device safety; additive-transport assumption stated
and compatibility-tested by §7). No change.

**Q7 — State A stops before embeddings: CORRECT and necessary.** Opening embeddings after an
identifiability failure is how post-hoc candidate design begins ("diagnostic interest" is the
canonical rationalization). Forfeiting descriptive stability statistics is the price of
selection-proofness, and §11 correctly requires the role/open audit to *prove* zero embedding
opens in state A.

## Verdict and next step

Draft may be frozen with no textual changes required; caveats C1/C2 should survive into output
documentation (they are already partially present). After FROZEN + sidecar and my hash/diff
review, implementation and execution each require the user's explicit authorization. CKDE-Q
Stage A remains an independent one-shot archival task awaiting the owner's authorization.
Standing boundaries unchanged: FINAL sealed; CKDB/CKDC/CKDD closed; no adapter code; CKDA D1 HPC
replay pending cluster recovery.
