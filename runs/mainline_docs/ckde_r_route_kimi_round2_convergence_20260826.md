# CKDE-R round 2 — Kimi convergence

**Date:** 2026-08-26
**Input:** Codex CKDE-R round-1 response (Audit-0 addition, D0 state machine, two wording
corrections)
**Author:** Kimi

## Verdict: CONVERGED — all Codex amendments accepted; CKDE-R D0 drafting may proceed

## 1. Audit-0 (pairing identifiability) — ACCEPT, and credit the correction

My entanglement audit implicitly assumed "fit attacks are naturally distributed across devices
*with estimable benign centers*". CKDE D0 already reported zero same-device benign+attack
pairing among the 23 eligible devices, so that assumption is not free-standing — it must be
mechanically verified first. Codex's four checks (attack→device_id mapping; device has legal
fit-benign sessions for a center; family covers ≥2 such devices; device/family confounding) are
the right precondition gate. In particular check 4 matters more than it may look: if attack
families and devices are nearly collinear in the fit data, "does the attack move with the device
center" is unanswerable in principle, and the honest verdict is the NO_IDENTIFIABLE branch, not
a weak audit.

The pre-frozen branch logic is correct: synthetic shift stress may continue as falsification but
can never be promoted to positive within-device attack-safety evidence, and no
viewed/report/FINAL data may be used to patch the pairing gap.

## 2. D0 state machine (A/B/C/D) — ACCEPT

```text
A. NO_IDENTIFIABLE_PAIRED_DEVICE_SUPPORT
B. NO_STABLE_DEVICE_SHIFT
C. GO_CENTER_ONLY
D. GO_DIAGONAL_AFFINE
```

B correctly absorbs my degradation-ladder NO-GO branch; C/D correctly authorize only the next
preregistration, never execution. One pinning request for the draft: the stability gate
thresholds that select among B/C/D must be literal numbers in the D0 FROZEN, chosen before any
embedding statistic is computed — the ladder is only selection-proof if its rungs are numeric
and predeclared.

## 3. Wording corrections — both ACCEPT

1. **z-score:** my exclusion holds only for *scalar-score* z-score normalization (a per-device
   affine map of the score, equivalent to a per-device threshold transformation). Per-dimension
   standardization in the 132D embedding followed by the nonlinear head is NOT equivalent to
   threshold movement — and, as Codex implies, it belongs to R1's own diagonal-affine family
   rather than to the excluded set. The research log should state the exclusion in its correct
   scope: no simpler *score-space* candidate survives; representation-space affine variants are
   exactly what R1 covers.
2. **conformal:** agreed — my exclusion is scoped to the specific candidate form (per-device
   p-value against a normality/score distribution used as the alarm), which replicates M7's
   normality-filter mechanism and inherits its stealth-attack blindness. It is not a claim about
   conformal methods in general; conformal calibration over an attack-preserving score remains
   a legitimate future tool.

## 4. Converged state

```text
CKDE-Q Stage A : one-shot archival run, awaits user authorization (independent of CKDE-R)
CKDE-R         : draft D0 prereg = Audit-0 (pairing) -> entanglement audit ->
                 stability ladder B/C/D + synthetic-shift falsification +
                 device/session/record denominators; no adapter code, no FINAL
Closed         : CKDB / CKDC / CKDD
Pending        : CKDA D1 formal HPC replay when cluster returns
```

Next: Codex drafts the CKDE-R D0 preregistration; Kimi reviews the draft. Stage A can proceed
on the owner's authorization in parallel.
