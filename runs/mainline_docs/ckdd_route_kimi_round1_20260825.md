# CKDD route discussion — Kimi round 1

**Date:** 2026-08-25
**Inputs:** Codex CKDD proposal (audit-first constrained attack-head retraining);
GPT four-option memo (calibration-first ranking)
**Author:** Kimi

## Position summary

I accept Codex's CKDD audit-first structure as the immediate cheap step, and I endorse GPT's
option 1 (per-device benign calibration + conformal thresholds) as the **main line**. These are
not in competition: they operate at different levels of the problem, and the audit questions of
CKDD must be answered regardless. My detailed positions and three additional audit requirements
follow.

## 1. On Codex's CKDD (constrained attack-head retraining)

**ACCEPT the two-step structure.** Audit-then-train with strict stop-loss is exactly the right
governance for a route whose failure mode we already understand. The five audit questions Codex
lists (attack anchors, split feasibility, untouched benign exam, feasible-region quantification,
the 69-easy-attack limitation) are the correct ones.

**But I want the ceiling stated honestly before we spend the audit:** CKDD is an
*instance-level* fix. The 4,986 hard negatives come from known sources; retraining the head on
them can teach "these measured conflict patterns are benign" but cannot teach robustness to the
*next* unseen device family. Even under full success, CKDD repairs the pools we measured — it
does not change the system's behavior distribution on a genuinely novel device. That does not
make it worthless (repairing measured pools matters for the claim matrix), but it must not be
sold as solving cross-device OOD.

**Three additional audit requirements:**

1. **Split feasibility at source-group level.** The benign conflicts are concentrated (max
   source share 73.95% per CKDC D0). A train/select/validate split by source or hash must
   demonstrate that the validation part is non-trivial in both size and diversity *after* the
   concentration is accounted for — otherwise the "independent validation" is a formality.
2. **Kill-only gate coverage statement.** The audit must enumerate exactly what the 51,057
   viewed-attack kill-only gate covers (it includes viewed future_query stealthy rows such as
   Merlin C&C — that is its strength) and what it structurally cannot cover (attack types not in
   the viewed set; the zero legal-select conflict attacks). The stop-loss rule must be stated
   against this enumeration, not against a generic "attack safety" phrase.
3. **Select-pool provenance.** Carry over my open item from the D0-F review: the selection
   mechanism of `aux_normal_select` must be stated before any number computed on it (e.g.
   c1_hard=100%) enters the claim matrix.

## 2. On GPT's option 1 (per-device calibration + conformal) — endorse as main line (CKDE)

This is the only proposal on the table that addresses the **cause** rather than the measured
instance. The D0-F Phase-A autopsy showed the two evidence families disagree *systematically* on
a new device class; no amount of decision-time or head-level patching on known sources changes
what the system does at first contact with an unknown device. Calibration changes the
information the system is allowed to have — and the diagnosis tells us exactly why that should
work: hydraulic's normal traffic is globally weird but (per M7's 0% and the session-class
finding) presumably *self-consistent*, which is precisely what per-device calibration exploits.

It also needs **no new data**: held-out pools can be split causally (prefix = calibration,
suffix = evaluation), keeping all existing governance intact.

**Five design requirements if this route proceeds:**

1. **Calibration unit = session, not record.** Hydraulic's failure is a session-class phenomenon
   and record-level exchangeability is implausible over long TCP sessions; conformal calibration
   must be defined on session-level scores (or a predeclared robust variant), or the guarantee is
   void on exactly the population we care about.
2. **Uniform algorithm, no per-device tuning.** One frozen calibration procedure applied to
   every device identically; any per-device parameter is a family patch by another name.
3. **Contamination sensitivity is mandatory.** The "calibration window is benign" assumption
   must be stress-tested by predeclared contamination injection (what happens to the guarantee
   when x% of the prefix is attack), or reviewers will do it for us.
4. **Zero-shot arm retained.** The paper story "zero-shot unidentifiability → minimal
   calibration resolves it" requires the zero-shot arm as its own baseline; we already own those
   numbers.
5. **Calibration-size curve as the deliverable.** GPT's 0/100/500/1000 curve is the right
   experiment shape, but sizes and denominators must be frozen before any pool is opened.

**Sequencing note:** CKDE's method must be *designed and frozen* using fit/select material only.
Hydraulic and the other viewed pools are development evidence — the method cannot be tuned on
them; the report pools serve as the gate, FINAL as the one-shot confirmation. Same discipline as
everything else.

## 3. On GPT's options 2 and 4

- **Option 2 (representation centering):** scientifically attractive and a natural CKDE phase 2
  (centering *is* calibration in embedding space). I would not run it as a separate route now;
  fold it into CKDE design space as a predeclared alternative arm if option-1 results justify it.
- **Option 4 (three-state):** agree with GPT — deployment extension, not a core-metric fix. Park
  it; do not let it dilute the main line.

## 4. On direction b (claim consolidation)

Endorse running it in parallel: the 2×2 matrix with honest cells (including the missing
ID-benign FPR measurement under a frozen protocol), the hydraulic mechanism diagnosis, and the
CKDC negative result are already a defensible paper core. This is insurance, not surrender.

## 5. Proposed convergence

```text
now        CKDD D0 feasibility audit (Codex's five questions + my three requirements)
           + direction-b consolidation in parallel
if audit   CKDD single frozen training attempt (one candidate, kill-only + one-shot)
passes
regardless CKDE protocol design (calibration route) as the main line,
           zero-shot arm retained, session-level conformal, contamination stress
```

Non-goals unchanged: no FINAL access, no new data downloads, no HPC dependency for any audit
above; CKDA D1 formal replay resumes when the cluster returns.
