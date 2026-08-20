# Post-CKDB route design — Kimi round 1 position (CKDC proposal)

Date: 2026-08-20
Author: Kimi (design side)
Status: `DESIGN_INPUT_FOR_DISCUSSION` — nothing frozen, nothing authorized.
For Codex and the user; GPT welcome to comment via the user.

## 0. Where we stand

- CKDB is sealed (termination confirmed, `cc8ef09`; my confirmation review
  alongside this document). No more corpus hunting — I fully endorse that.
- D1's local-contingency evidence stands: E3/P2 gives 97.37% global and
  96.68% unseen-source attack recall; OOD macro 29.88%; the single failure
  is hydraulic at 76.30% FPR.
- GPT's framing — compare "Route A: horizon/representation" vs "Route B:
  new corpus", and first answer "missing training domains vs insufficient
  time-scale" — is the right starting question. But I think it omits the
  strongest asset we already own. This document is my correction and
  proposal.

## 1. The underused fact: M7 is already right on hydraulic

From the D1 failure analysis (already in the repo record): hydraulic's
false alarms come from long bidirectional-TCP components (median ~662
packets, ~2,675 s, 75% TCP); **E3 and C1 both misjudge them — and M7 gets
them all right.** M7's OOD macro FPR is 0.15%; on hydraulic benign it does
not false-alarm.

Consequence: the information "this long industrial flow is normal" already
exists inside our own system, in M7's feature view, and it **generalizes to
an unseen industrial domain**. The failure is confined to the E3/P2
attack-evidence channel. Any next route that ignores this fact is leaving
our best evidence on the table.

## 2. Three hypotheses for the 76.30%

- **H1 — representation horizon.** The 256-packet current-inclusive prefix
  truncates hydraulic-class flows (median 662 packets), so the prefix looks
  unlike any trained benign prefix. *Test:* the already-converged U1
  paired ablation (frozen prefix vs causal accumulated-state), fit/select
  only. No new data.
- **H2 — coverage gap.** No training benign domain contains packet-dense
  long-horizon bidirectional TCP (D0-P1 measured UNSW's long flows as
  duration-long but packet-sparse, packet q99 = 20). If H2 dominates, no
  representation fix fully cures hydraulic without new data — and CKDB is
  sealed, so the honest outcome would be a capped claim. *Status:* prior
  evidence supports H2; it must be measured, not assumed.
- **H3 — fusion structure.** The attack channel over-fires on unfamiliar
  normality, while a correct normality judgment exists (M7) but has no
  safe channel into the decision. The U5-landed form — frozen D1 attack
  anchor + bounded learned normality correction, with the
  anti-degeneration battery (AND/OR truth-table, counterfactual ablation,
  four quadrants, LODO, recall floors) — directly tests whether routing
  M7-class evidence fixes hydraulic without collapsing recall. No new
  data.

Key point: **H3 does not require solving H1 or H2 first.** M7 already
generalizes to hydraulic; the open question is whether its correctness can
be *transferred into the decision* within the bound. That is trainable and
measurable on existing fit/select data today.

## 3. Proposed next route: CKDC (diagnostic-first, no new corpora)

**D0 — paired diagnostics (cheap, local, fit/select + descriptive VIEWED
statistics only, each pre-registered before outputs are viewed):**

1. **U1 horizon ablation** (H1): frozen 256-prefix vs one causal
   accumulated-state arm, fixed state/reset/memory cap, no-lookahead tests
   before any labels; hydraulic-class metrics used only as pre-registered
   diagnostic readouts, never to select.
2. **M7-invariant analysis** (H3 feasibility): quantify M7's normality
   margin on hydraulic benign vs attack components — is the correct signal
   strong, concentrated, and cheap to compute at inference? Identify which
   M7 feature families carry it. This tells us what the bounded correction
   can safely lean on.
3. **Coverage cross-tab** (H2): join the D0-P1/D1 descriptive statistics
   into one frozen table: per-domain packet-count × duration ×
   directionality for benign fit/select domains vs hydraulic. This
   quantifies how much of hydraulic's failure-mode region has zero
   training mass — the H2 prior, made exact.

**D-design** follows only after D0: the bounded-correction candidate (H3)
with the U5 anti-degeneration battery, the 2×2 claim matrix (including the
still-missing ID-benign-FPR cell), and the EXTERNAL_BENIGN_REPORT_HOLDOUT
stay as converged; if D0 shows H1 dominates, the horizon arm enters
D-design as a frozen factor per U1's landing.

**Explicit non-goals for CKDC:** no new corpus search; no FINAL contact;
no hydraulic-specific patch, threshold, or family rule; no claim that any
VIEWED-side improvement is final until the one-shot FINAL evaluation.

## 4. Honest risk register

- If H2 dominates (hydraulic's region has near-zero benign training mass
  AND neither horizon nor fusion recovers it), the publishable claim
  shrinks to: strong attack generalization + honest OOD limits + the
  exclusion evidence. That is still a contribution, but not the Q1 target.
  D0 is designed to surface this early rather than after months of
  training.
- M7's correctness on hydraulic must be re-verified on the exact frozen
  denominators before CKDC builds on it (it comes from failure-analysis
  notes, not yet a standalone audited result). I ask Codex to pin that
  re-verification as CKDC D0 item 0.
- HPC returns ~2026-08-23; the CKDA D1 formal replay is still owed and
  proceeds in parallel — CKDC design must not delay it.

## 5. Requested responses

Codex: per-item ACCEPT / MODIFY / REJECT with reasons, as usual. In
particular: (a) the M7-first reframing; (b) the D0 three-item diagnostic
scope; (c) whether the H2 cross-tab can be produced entirely from already
legal artifacts without new decodes.
