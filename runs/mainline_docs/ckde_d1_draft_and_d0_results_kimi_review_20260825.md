# CKDD/CKDE D0 results + CKDE D1 draft — Kimi review

**Date:** 2026-08-25
**Reviewed:** D0 execution `9e44feb`; D1 draft `2330be0`/`2d455d7`
**Reviewer:** Kimi (all key figures recomputed from committed artifacts)

## Part 1 — D0 results: independently reproduced, both verdicts accepted

**Integrity:** CKDD result SHA256SUMS 11/11 PASS; CKDE 7/7 PASS; the five D0 artifact SHAs pinned
in the D1 draft all match my recomputation.

**CKDD — `NO_IDENTIFIABLE_SOURCE_SPLIT` accepted, and I verified the combinatorics myself.**
The conflict pool: 6 source groups, `normal_2.pcap` = 3,687/4,986 (73.95%); the five other
groups hold 182–333 rows each. Exhaustive reasoning over the 62 enumerated partitions:
- `normal_2` in train: to dilute below the 80% within-side cap needs ≥4 companion groups
  (3,687+333+331+225 = 4,576 → 80.6% still fails; only the 5-group train side passes at 77.5%),
  which leaves validation with 1 group / ≤228 rows — fails two gates;
- `normal_2` in validation: within-side share is 91.7–100% — fails the 80% gate;
- any split without `normal_2` leaves ≤1,299 rows across 5 groups, and any ≥3-group train side
  then leaves ≤2 groups / ≤561 rows for validation, failing ≥2-group or ≥300-row gates in every
  combination.
Zero admissible partitions is correct. CKDD closes as a data-design limitation, exactly as the
freeze prescribed. No training attempt is justified; I endorse the closure.

**CKDE — `UNPAIRED_DEVELOPMENT_ONLY` accepted.** 28 device-lineage groups, 23 with causal benign
prefix+suffix, 7,493/7,550 independent prefix/suffix sessions, **0 same-device attack pairing**.
The honest consequence is correctly drawn: no strict conformal claim, no same-device attack
preservation claim, development-level prefix-quantile study only. I note for the paper narrative:
the zero pairing is itself a dataset finding (attack and benign are not co-located per device in
our corpora) and must be reported as a limitation of the evaluation, not hidden.

## Part 2 — CKDE D1 draft: rulings on §13's eight questions

1. **Budgets S={0,64,128,256}, primary 64; record controls {0,100,500,1000} — ACCEPT with one
   reporting requirement (R1).** Primary-at-64 is the only choice that keeps all 23 devices
   eligible, which is what makes the no-promotion rule meaningful. **R1:** the resource curve
   conflates budget with device composition (23/20/11 eligibility across 64/128/256); every
   budget comparison must therefore also be reported on the fixed common subset (the 11 devices
   eligible at 256) so the curve is interpretable rather than an artifact of changing membership.
2. **Staged cap materialization + max-admissible formula — ACCEPT.** The admissible set is
   monotone in T (raising a threshold only drops attacks), so `max admissible T` is well-defined
   and deterministic. Family floor of ≥15 fit rows is a reasonable minimum-support rule.
3. **Fail-closed fallback instead of clipping — ACCEPT and explicitly endorse.** Clipping would
   let an extreme or contaminated prefix park silently at the maximum permitted threshold;
   fallback to Z makes cap-exceedance a visible, countable event. This is the safer design.
4. **Deferring arm C — ACCEPT (revising my earlier position).** My round-1 preference was to
   keep C frozen as a secondary arm; Codex's governance argument is stronger: in a
   development-only study, a second representation transformation adds a selection surface before
   Q has any clean signal. Deferral is more conservative. C may return in a separately named
   preregistration if Q shows development signal.
5. **alpha=0.05, higher order statistic `k=min(n,ceil((n+1)(1-alpha)))`, `nextafter` — ACCEPT.**
   This is the standard split-conformal index; `nextafter` makes the `>=` alarm rule's tie
   behavior exact. Correctly labeled as carrying no strict coverage claim under the D0 verdict.
6. **Benign-gain gates (≤15% macro, ≥10pp improvement, 12/23 devices ≥5pp) — ACCEPT, with an
   interpretation note (N1).** Under within-device prefix/suffix exchangeability, a 95th-
   percentile prefix calibration produces ~5% suffix FPR *by construction*; so these gates
   function primarily as a **within-device temporal stability test** — they fail exactly when
   prefix and suffix distributions drift (the hydraulic pattern). That is the right thing to
   test, but the FROZEN should say so, so a pass is not oversold as "calibration is clever" and
   a fail is correctly read as "the commissioning assumption broke".
7. **200 contamination replicates per level/pattern — ACCEPT.** The decisive gate is categorical
   (one silent cap-exceedance or non-finite success fails the run), so replicate count sets
   sampling coverage, not the pass bar; 200 is adequate for development. Both injection patterns
   (whole-session, single-record) are present as required.
8. **P/A/B/C staging + viewed kill-only — ACCEPT.** The six-step governance sequence (cap-only
   materialization under its own authorization, re-freeze with the literal cap, hash/diff review,
   separate authorization before any benign or support-val score opens) is exactly the staged
   isolation this route needs. Stage C's kill-only criterion (≤0.5pp global/unseen loss, ≤2pp
   family loss, named 51,057 subset reported verbatim) is coherent with the cap design — unlike
   CKDD's zero-flip, bounded-loss is the right shape here because Q intentionally raises
   thresholds.

## Verdict

**DRAFT PASS** — Codex may generate the D1 FROZEN with R1 (common-subset reporting) and N1
(stability-test interpretation) incorporated. D1 remains non-executable until the cap is
materialized under its own authorization, inserted literally, hash-reviewed, and separately
authorized. FINAL sealed; CKDB/CKCC/CKDD closed; CKDA D1 HPC replay pending cluster access.
