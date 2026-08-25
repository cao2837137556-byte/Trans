# CKDC D0-F Phase A — Kimi independent result review

**Date:** 2026-08-25
**Reviewed:** implementation `e51398e`, result `2ce647b`
**Result dir:** `runs/issue27ckdc_d0f_certificate_phase_a_v1_2026-08-25_local/`
**Reviewer:** Kimi

## Verdict: RESULT CONFIRMED — `CKDC_D0F_NO_CERTIFICATE` independently reproduced; Option-A candidate and CKDC fusion route accept clean closure

## 1. Independent recomputation (from committed artifacts, not from the report)

- `SHA256SUMS` readback: **7/7 PASS** (recomputed locally).
- Verdict sidecar SHA: PASS.
- Denominator: 7,069 rows reproduced from `ckdc_d0f_phase_a_certificate_rows.csv`.
- **Full formula re-derivation:** I recomputed `tail_normal`, `c1_normal`, `ckbq_normal`,
  `normality_certificate`, `candidate_hard` from raw columns for all 7,069 rows and compared
  against the implementation's own columns: **0 mismatches**.
- Conflict population reproduced exactly: 4,986 benign `P2 hard / M7 normal` rows, with
  `tail_normal` = 4,983, `ckbq_normal` = 4,983, **`c1_normal` = 0**, certificate = 0,
  changed benign = 0.
- Attack preservation reproduced: 69/69 legal attacks remain hard under the candidate.
- Clause table matches the frozen ten clauses; failures are exactly the five coverage clauses,
  which fail at the harshest possible level (zero coverage), not at a boundary.
- Boundary counters from `input_audit.json`: `final_opens=0`, `pcap_opens=0`, `report_opens=0`,
  `training_operations=0`, `fitted_parameters=0`, `phase_b_path_available=false`.

The failure is therefore structural and mechanical: the certificate is **vacuous on the entire
legal universe** (0 of 7,069 rows), not a near-miss on the 300-row gate.

## 2. A fact stronger than the report states — and its claim boundary

My recompute shows `c1_hard = true` on **all 7,069 legal select rows**, including all 4,000
`aux_normal_select` benign rows — not merely on the 4,986 conflicts. Two consequences:

1. **For the verdict: irrelevant and stronger.** Option A required C1 to stand down on some
   benign conflicts; C1 stands down on nothing in this universe. The NO_CERTIFICATE outcome is
   robust to any plausible implementation nuance.
2. **For the scientific narrative: this number must not be quoted as "C1's field false-positive
   rate is 100%".** The legal select pools were assembled as challenge-enriched subsets for
   detector stress-testing, not as representative deployment traffic. Before this figure appears
   in any paper or claim matrix cell, the provenance/selection mechanism of `aux_normal_select`
   must be stated alongside it. I ask Codex to confirm or correct this reading when closing the
   route.

## 3. Scientific meaning of the closure

The evidence topology on benign conflicts is now fully mapped:

| signal family | on 4,986 benign conflicts |
|---|---|
| process-side (M7, tail, CKBQ) | says "normal" on ≥ 4,983 (99.9%) |
| attack-side (P2, C1) | says "attack" on 4,986 (100%) |

The disagreement between evidence families is **total and systematic**. Option A required the
attack-side views to stand down as a certificate condition; they never do. This kills not just
the one formula but the whole "evidence-gated suppression" family in which suppression requires
attack-view consent — on this data there is nothing to consent to.

Per the FROZEN protocol: Phase B forbidden (correctly not launched), no revision permitted,
candidate permanently closed. CKDC fusion under this preregistered candidate closes cleanly.
This is a publishable-grade negative result with an exact mechanism.

## 4. Where this leaves the program (discussion input, not authorization)

Two live directions remain, both outside CKDC:

- **D-next (frontend retraining):** the 4,986 legal benign conflicts are legal selection data
  and could serve as hard negatives for retraining the *attack probe itself* (not a decision-time
  override). Governance is transferable: design on legal select, kill-only audit on the 51,057
  viewed attacks, one-shot untouched confirmation. This attacks the same failure at the
  representation level rather than the fusion level. Whether the zero-attack-conflict support in
  select blocks this too needs explicit argument before any preregistration.
- **Claim-boundary consolidation:** fill the missing ID-benign FPR cell under a frozen protocol,
  complete the formal CKDA D1 HPC replay when the cluster returns, and write the 2×2 matrix with
  the hydraulic failure mode and this negative result stated honestly.

Both are new routes requiring fresh preregistration. Nothing in this review authorizes either.

## 5. Standing obligations (unchanged)

FINAL sealed; CKDB closed; Phase B permanently forbidden for this candidate; CKDA D1 formal HPC
replay deferred until cluster access returns.
