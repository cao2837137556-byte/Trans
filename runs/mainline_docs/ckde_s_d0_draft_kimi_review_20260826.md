# CKDE-S D0 Draft — Kimi Independent Review

- Reviewer: Kimi
- Date: 2026-08-26
- Draft under review: `runs/mainline_docs/ckde_s_d0_attack_protected_device_shift_and_paired_corpus_prereg_draft_20260826.md`
- Draft commit reviewed: `97a89d8`
- Verdict: **DRAFT PASS with one MODIFY (Q7)**. Codex may generate the FROZEN protocol and
  SHA sidecar after mechanically incorporating the Q7 modification below. All other rulings
  are accept-as-drafted.

This review rules only on the eight open questions in draft §15 and on overall structure.
It authorizes nothing: no implementation, no embedding opening, no network retrieval, no
download, no training, no score opening, no HPC, no report, no FINAL.

---

## 1. Overall structural assessment

1. Lane separation is clean. Lane G (internal geometry audit on existing fit-only
   embeddings) touches no network and no scores beyond the already-frozen fit assets;
   Lane M (metadata-only external corpus audit) touches no embeddings and no scores.
   Neither lane can contaminate the other, and each has a literal fail-closed terminal
   state. This matches the governance pattern that has kept the last five sealed routes
   (CKDB/CKDC/CKDD/CKDE-Q/CKDE-R) interpretable.
2. Lane G has standalone value even if Lane M terminates. The geometry question — does a
   stable, attack-orthogonal, low-rank device-nuisance subspace exist in the frozen E3
   representation at all — is answered by Lane G alone. A negative Lane G result with the
   corpus hunt still open is an informative negative, not wasted work, because it bounds
   what any future adapter on this representation could ever achieve.
3. The joint verdict lattice (G≠G4 → NO_GO; M2 → future work; both pass → READY for a
   separately pre-registered execution protocol) is the correct shape. In particular,
   READY authorizes only the drafting of the next protocol, not execution — this preserves
   the pattern that each capability escalation passes through its own freeze.
4. §7.3's ruling that a protection space swallowing the entire device subspace yields
   `NO_ATTACK_ORTHOGONAL_DEVICE_NUISANCE` rather than relaxing the protection is exactly
   right. The moment the protection set is adjusted to make the removable set nonempty,
   the audit becomes outcome-fitted.

## 2. Rulings on the eight open questions (draft §15)

### Q1 — Rank rule `min(4, floor((D-1)/3))` → r=4 for D=15: **ACCEPT**

r=4 spends ~29% of the 14 between-device degrees of freedom. This is conservative enough
for a screening gate, and the draft's prohibition on in-run downgrading (rank 3 would
require a new pre-registration) gives the choice real consequences, which is what makes
it a pre-registered constant rather than a tunable. The LODO stability gate in §6 is the
actual test of whether r=4 overfits; if the subspace is not leave-one-device-out stable,
the gate fails and that is a legitimate answer. I do not require rank 3. Rationale for
not tightening: at D0 we are screening for *existence* of a stable nuisance subspace,
not committing to a final adapter dimensionality; an overly small rank risks a false
negative that kills the last open route on a technicality rather than on evidence.

### Q2 — §6.1 LODO stability constants (median projected distance ≤0.20 / worst ≤0.35;
principal angles 20°/35°): **ACCEPT**

The constants are literal, pre-declared, and carry a worst-device guard rather than a
mean-only gate — the same anti-averaging discipline that correctly stopped CKDA D1's
hydraulic pool from being hidden by a macro number. For a D0 screening gate these values
are defensible: strict enough that a pass is meaningful, loose enough that the gate
measures stability rather than demanding identity. G1 failure is a legitimate, useful
answer. I note explicitly: these constants were fixed before embedding access, so no
outcome selection is being imported.

### Q3 — R_d gates (median ≥2.0, 80% of devices ≥1.0) as evidence U captures cross-device
nuisance rather than within-device temporal drift: **ACCEPT**

The causal early/late half-split construction is the right discriminator: within-device
temporal drift would show up as comparable early-vs-late dispersion, deflating R_d;
genuine cross-device structure keeps between-device dispersion dominant. Requiring a
per-value distribution report plus the 80% floor (not just the median) prevents a few
extreme devices from carrying the verdict. This is sufficient evidence for the D0 claim
"U represents cross-device nuisance"; it does not overclaim, because the claim stays at
the representation level and says nothing about downstream detection yet.

### Q4 — Frozen-head gradients as the primary attack-protection space, mean contrasts
strictly diagnostic: **ACCEPT — and recorded as superior to my own earlier formulation**

In my Round-1 endorsement I asked for "attack-direction decontamination" framed around
attack mean directions. The draft's choice is better, and I want the record to say why:
the gradient of the frozen P2 head with respect to the embedding measures the directions
the *detector actually uses*; an attack mean contrast measures where attacks happen to
sit, which is contaminated by device shift (an attack observed on few devices partly
encodes those devices' embeddings). Protecting the detector's sensitivity directions is
the direct implementation of "removing device nuisance must not remove what the
detector needs to fire on attacks." Mean contrasts retained as diagnostics is the right
secondary use. No change requested.

### Q5 — Residual-fraction gates 0.50/0.65 and the 25% removable-energy floor: **ACCEPT**

These are defensible starting literals: the residual floor (attack-gradient energy
retained after orthogonalization) protects the detector, and the removable-energy floor
ensures the procedure is non-degenerate (a removable subspace carrying <25% of device
energy would be a certificate of uselessness, echoing CKDC D0-F's zero-coverage lesson).
I have no data-grounded basis to substitute different numbers, and tightening now would
be aesthetic, not principled. Requirement: every per-device and per-family value is
reported as-is, with the gates applied mechanically — no distribution smoothing, no
post-hoc threshold discussion in the result report.

### Q6 — External minimum: 6 paired devices, of which 3 devices each cover ≥2 attack
families; hash-split reserving ≥2 fully untouched devices; single-family corpora
immediately negative: **ACCEPT**

This is the minimum design that can validate mechanism rather than identity: two attack
families on the same device let the later execution stage separate "calibration removed
device nuisance" from "calibration removed this one family's signal." The reserved
untouched devices preserve an honest confirmation set. Refusing to relax the gate for
single-family corpora is correct — relaxing after seeing a candidate would be
outcome-fitted corpus selection, the same failure class as the hydraulic-specific patch
we have refused throughout.

### Q7 — N-BaIoT failure → CICIoT2023 activation: **MODIFY — insert a blocking Kimi review
gate between candidate 1 and candidate 2**

As drafted, candidate 1's failure immediately activates candidate 2. This preserves
isolation in only one direction: it prevents opening candidate 2 after candidate 1
*passes* (motivated extra validation), but it does not prevent the reverse failure —
knowing *why* candidate 1 failed can shift how strictly candidate 2's audit criteria are
applied (motivated loosening: "candidate 1 failed on X, so let's not fail candidate 2 on
X"). The audit of candidate 2 must be designed, and its pass/fail criteria held fixed,
without knowledge of candidate 1's failure mode.

Required mechanism (to be written into the FROZEN protocol):

1. Candidate 1 (N-BaIoT) audit runs to a terminal verdict.
2. Codex writes the M1 verdict and its reason codes to a verdict file, computes its
   SHA-256, and delivers the verdict to Kimi. Candidate-2 retrieval does not begin.
3. Kimi reviews the M1 verdict for two things only: (a) that the failure reason codes
   are drawn from the pre-registered failure taxonomy, not invented post hoc; (b) that
   no candidate-2-relevant criterion was silently tightened or loosened. Kimi then issues
   an explicit proceed/terminate ruling.
4. Only after that ruling may candidate-2 (CICIoT2023) metadata retrieval begin.

If candidate 1 passes, the protocol stops as drafted — candidate 2 is never opened, and
this gate is moot. The gate costs one review round-trip only in the failure branch; that
is cheap insurance on the last open route.

### Q8 — External zero-shot challenge-relevance gate, frozen now in principle: **ACCEPT —
and required to be frozen now, at the principle level, in the FROZEN protocol**

This is the anti-cherry-picking gate, and I consider it load-bearing. If the external
corpus turns out to be one where zero-shot P2 already performs well on benign traffic
(no measurable benign-shift problem), then a successful calibration on it proves nothing
— there was no problem to solve, and promoting that result would be selecting easy
evidence. The FROZEN D0 must therefore carry, as a literal pre-declared principle:

- The later external execution protocol must define a measurable zero-shot benign-shift
  challenge criterion (e.g., a literal lower bound on zero-shot benign false-positive
  behavior or prefix-vs-fit benign score displacement, with exact form fixed in that
  protocol before any external score is opened).
- A corpus failing this challenge-relevance gate cannot be promoted as a positive
  mechanism-validation result, regardless of calibration outcome. It may at most be
  reported as a negative diagnostic ("no shift to remove").

Fixing the principle now, before any external data is seen, is what makes the gate
credible; the exact numeric form belongs to the external execution protocol and is
deliberately not fixed here.

## 3. Additional affirmations (no changes requested)

1. Lane G's no-network property and Lane M's no-scores property are both stated as hard
   boundaries with fail-closed behavior; this matches the established authorization
   discipline.
2. The prohibition on in-run rank downgrade (Q1 discussion in draft) makes the rank
   choice consequential; endorsed.
3. Reporting obligations (per-value distributions, worst-device guards, named failure
   reason codes) are consistent with the reporting discipline of the previous sealed
   routes and are sufficient for my independent recomputation later.

## 4. What this review does not authorize

- Generation of the FROZEN protocol is authorized **only** after Codex mechanically
  incorporates the Q7 blocking review gate and the Q8 principle statement. The FROZEN
  document then receives my standard SHA/diff terminal review.
- Lane G execution (embedding opening) and Lane M execution (network metadata retrieval)
  each require separate, explicit user authorization after the FROZEN protocol passes
  review. They are not bundled, and neither is authorized by this document.
- Nothing in this review touches FINAL, viewed-report data beyond its kill-only role,
  training, HPC, or score opening beyond the already-frozen fit assets.

## 5. Verdict

**DRAFT PASS with one MODIFY (Q7).** Codex may proceed to generate the CKDE-S D0 FROZEN
protocol and SHA sidecar once Q7 (blocking Kimi review gate between external candidates)
and Q8 (challenge-relevance principle, frozen now) are incorporated. All other questions
are accepted as drafted.
