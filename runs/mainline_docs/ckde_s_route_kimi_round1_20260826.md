# CKDE-S route (attack-protected subspace shift removal) — Kimi round 1

**Date:** 2026-08-26
**Input:** Codex proposal (image relay): freeze E3/P2; learn a global device-difference
subspace from training benign devices; determine attack-evidence directions from legal fit
attacks; per-device commissioning removes only the attack-orthogonal part of the device shift.
Owner decision 2026-08-26: paper consolidation moves to a separate future window; current effort
concentrates on system results. This document is the formal round record for the remaining
capability route.
**Author:** Kimi

## Verdict: ENDORSE as the single remaining capability candidate — with two mandatory D0 preconditions and one bounded data reconnaissance

## 1. Why this design is stronger than generic CORAL/affine alignment

1. **Attack protection is structural, not audited after the fact.** Restricting removal to the
   attack-orthogonal complement makes "do not erase attack evidence" a property of the transform,
   not a post-hoc check. This directly absorbs the CKDE-R entanglement concern.
2. **Small-sample stability is solved by geometry, not by shrinkage.** A global low-rank device
   subspace (learned from the 15 legal fit-benign devices / 11,409 records) reduces the
   per-device commissioning estimate to a handful of subspace coefficients — orders of magnitude
   more stable than 768 diagonal scales at 64 sessions.
3. **Frozen E3/P2 preserved.** All CKDA attack-side capability (97.37% / 96.68%, pending HPC
   replay) is untouched by construction.

## 2. Mandatory D0 precondition 1 — attack-direction decontamination audit

The proposal's step 3 ("determine attack evidence directions from legal fit attacks") hits the
exact gap CKDE-R Audit-0 exposed: our fit attacks come from 5 devices with **no same-device
benign centers**, so a naive direction estimate (attack mean − global benign mean) is
contaminated with those 5 devices' own domain shift. Orthogonalizing against a contaminated
direction protects the wrong thing.

Required audit (read-only, legal fit data only):

1. learn the device-difference subspace from fit-benign devices (count-only rank selection rule,
   frozen before any statistic is read);
2. estimate raw attack directions per eligible family (frozen minimum-support rule);
3. project each raw direction onto the device subspace and measure the contamination fraction;
4. the decontaminated direction (residual after projection) is admissible only if a frozen
   residual-magnitude gate passes — otherwise the route is NO-GO with reason
   `ATTACK_DIRECTION_NOT_IDENTIFIABLE`;
5. the assumption "the benign-learned device subspace also spans attack devices' shifts" must be
   stated as a named assumption with a falsification check, not adopted silently.

## 3. Mandatory D0 precondition 2 — subspace estimability census

- 15 fit-benign devices limit the identifiable subspace rank severely; rank must be chosen by a
  frozen count-only rule (e.g., bounded by a literal fraction of device count), never by outcome;
- within-device vs cross-device variance decomposition must show the subspace captures
  *between-device* variation (what commissioning needs to remove), not within-device temporal
  drift;
- frozen literals required before any embedding open: rank rule, orthogonality tolerance,
  shrinkage/regularization constants, per-device coefficient estimator, session budgets,
  three-level denominators.

## 4. Bounded data reconnaissance (paired-device corpus)

Target: same-device benign + attack pairing (the Audit-0 gap). Strict, time-boxed, predeclared:

- **N-BaIoT first** (9 real devices, per-device benign + Mirai/BASHLITE): must verify raw
  ordered PCAP availability per device (not only the 115-dim feature tables), per-device
  benign/attack member inventories, license, and overlap/pollution audit against our
  fit/select/report pools and E3 pretraining.
- **CICIoT2023 as backup only**: scenario-level captures may not recover same-physical-device
  benign→attack causality; if not recoverable, it is unusable for this purpose regardless of size.
- Hard stop-loss: if no corpus passes the frozen acceptance checks within the time box, the
  commissioning capability goes into the paper as future work. No open-ended hunting.
- Any use of a new corpus requires its own preregistered audit before any download of bulk data
  (metadata/Tier-A first), following the CKDB D0-P1 discipline.

## 5. Governance inheritance

- All transforms frozen before score access; kill-only gates on all viewed attacks; support-val
  one-time sentinel; FINAL one-shot confirmation remains the only venue for positive
  within-device attack-preservation claims.
- No per-device hyperparameters; three-level denominators; engineering failure emits no verdict.
- CKDE-Q Stage A and CKDE-R state A remain closed and unaffected; CKDB/CKDC/CKDD remain closed.
- CKDA D1 formal HPC replay remains pending cluster recovery; its result feeds the detector-side
  numbers regardless of this route's outcome.

## 6. Next step

Codex drafts the CKDE-S D0 preregistration covering §2–§4 (decontamination audit, estimability
census, N-BaIoT metadata audit protocol). Kimi reviews the draft. No implementation, no
embedding open, no download, no FINAL access is authorized by this document.
