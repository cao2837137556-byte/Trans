# CKDD D0 — constrained attack-head retraining feasibility audit (FROZEN)

**Date:** 2026-08-25
**Status:** FROZEN preregistration; protocol immutable; execution not yet authorized
**Reviewed basis:** `ckdd_ckde_drafts_kimi_review_20260825.md` at commit `0376331`

## 1. Question and ceiling

CKDD asks whether the frozen E3 representation and P2 attack head can support exactly one
constrained retraining attempt in which the 4,986 legal benign `P2 hard / M7 normal` conflicts
are added as hard negatives while attack behavior is held inside a frozen trust region.

The ceiling is fixed before the audit:

- these hard negatives come from already-known development sources;
- success can establish a **known-pool repair** and a bounded method ablation;
- it cannot establish zero-shot robustness to the next unseen device;
- no CKDD result may be described as general unseen-device benign-OOD resolution without a
  separately preregistered untouched-device confirmation.

CKDD D0 is read-only.  It does not update a parameter, fit a threshold, open report scores,
access FINAL, decode PCAP, or create a detector result.

## 2. Immutable development evidence

The audit must pin by SHA-256 before reading:

1. CKDA D1 FROZEN contract and threshold-freeze marker;
2. `ckda_d1_fit_select_plan.csv` (25,467 rows: 18,398 fit and 7,069 select);
3. `ckda_d1_fit_select_embeddings.npz` and its audit;
4. `ckda_d1_probe_state.npz` for the frozen E3/P2 identity;
5. CKDC D0-F Phase-A row table, input audit, verdict, and `SHA256SUMS`.

The known legal composition must be reproduced, not copied from prose:

- fit attacks: 4,000 `aux_process_fit` rows plus 385 `support_train` rows;
- select attacks: 69 `support_val` rows;
- select benign: 3,000 `aux_select` plus 4,000 `aux_normal_select` rows;
- benign conflicts: exactly 4,986 rows over six source groups;
- largest conflict source: `normal_2.pcap`, 3,687/4,986 = 73.95% (rounded);
- report/FINAL opens during D0: zero.

## 3. Audit A — select-pool provenance

Before any conflict statistic enters a claim matrix, D0 must reconstruct why every select row is
in the pool.

In particular, `aux_normal_select` must be recorded as:

- a single ToN-IoT member, `normal_2.pcap`;
- role assigned by the pre-existing `TON_PILOT_FILES` mapping;
- 4,000 rows obtained by seed-27 reservoir sampling over causal, score-before-update events;
- sorted back into target-event order after sampling;
- source-disjoint from `normal_1.pcap` used as `aux_normal_fit`;
- challenge-enriched development selection evidence, not a deployment-prevalence sample.

The audit must emit the code identity, member identity, decoded-event count, reservoir budget,
seed, selected-event-position hash, role-plan hash, and zero-label-read assertion.  Therefore
`c1_hard=100%` on this pool may be used as a mechanism observation only, never as field FPR.

## 4. Audit B — source-group split feasibility

Record-wise random splitting is forbidden.  D0 must enumerate source-group-disjoint partitions
of the six conflict groups and report, for every admissible partition:

- train and validation rows;
- train and validation source-group counts;
- largest source share within each side;
- E3 embedding coverage and finite-score coverage;
- overlap of device family, capture, endpoint/session key, and original member across sides.

An admissible partition must have all of:

1. at least three training source groups and two validation source groups;
2. at least 300 hard negatives on each side;
3. no source/member/session overlap;
4. largest within-side source share at most 80%;
5. no report or FINAL row.

D0 selects no split by downstream performance.  If multiple partitions satisfy the count-only
conditions, the later training protocol must choose one by a frozen SHA-256 ordering rule before
opening any score outcome.  If none exists, verdict is `NO_IDENTIFIABLE_SOURCE_SPLIT`.

## 5. Audit C — attack-anchor adequacy

D0 must report the 4,385 legal fit attacks and 69 legal select attacks by role, family, source,
session, score margin, and E3 coverage.  It must explicitly distinguish:

- the 4,000 ToN process attacks (two mechanisms);
- the 385 support-train attacks;
- the 69 support-val attacks;
- the attack families and low-margin regions not represented by those anchors.

The audit must quantify how much of the 16-family report dictionary is absent from fit/select.
The 69/69 support-val result is an exact safety sentinel, not evidence that stealth or unseen
attack types are protected.  D0 cannot open report scores to improve this audit.

## 6. Audit D — frozen-head feasible-region diagnosis

Using frozen E3 embeddings and the frozen P2 state only, D0 may compute descriptive, read-only
diagnostics:

- P2 logit/margin distributions for fit attacks, support-val attacks, all select benign, and the
  4,986 hard negatives;
- nearest-opposite-class distances and source-stratified overlap in frozen embedding space;
- first-order per-example gradient directions at the frozen P2 state, summarized only by legal
  role/source (no optimizer step);
- conflict between aggregate hard-negative and attack-anchor gradients;
- a conservative trust-region upper bound on how many legal attacks could cross the frozen P2
  threshold under any proposed bounded update.

No learned projection, new feature, new threshold, family weight, optimizer search, or candidate
checkpoint is permitted.  This audit asks whether a safe region is identifiable; it does not
simulate training until a favorable answer appears.

Every diagnostic is emitted verbatim regardless of whether it supports or opposes CKDD.  No
scope, role, source, margin range, trust-region definition, or summary statistic may be changed
and rerun conditionally after observing a diagnostic direction.

## 7. Audit E — untouched benign exam and claim support

D0 must list every benign source/device available after removing:

- all rows used to fit E3/P2;
- all rows used in CKDA threshold selection;
- all rows already opened in CKDA/CKDC development reports;
- cooler-motor and every other FINAL identity.

If no untouched non-FINAL benign device remains, this is not an engineering failure.  The audit
must emit `NO_UNTOUCHED_BENIGN_CONFIRMATION_AVAILABLE`, and any later CKDD run is limited to the
known-pool-repair claim.  A viewed report pool may be kill-only; it cannot provide positive
generalization evidence.

## 8. Audit F — future kill-only coverage statement

Without opening score values in D0, the audit must freeze the exact identity and declared
coverage of the later kill-only attack screen:

- **all** already-viewed report attack rows, regardless of their current P2/M7 quadrant, if
  identity reproduction passes;
- the 51,057 already-viewed `P2 hard / M7 normal` report attacks as a named conflict-quadrant
  sub-denominator, never as the complete safety denominator;
- explicit whole-denominator and conflict-subset inclusion counts for `future_query`, Merlin
  C&C, and each of the 16 families;
- explicit blind spots: unseen attack types, absent devices, attacks outside the conflict
  quadrant, and the legal-select quadrant with zero conflict attacks.

If a later frozen CKDD head flips even one viewed report attack row from hard to normal at the
frozen P2 threshold, the route closes.  Passing supplies no positive evidence and permits no
iterative repair.  Distillation and the trust-region objective are design intentions, not a
substitute for this whole-report falsification screen.

## 9. Mechanical D0 verdict

Exactly one of the following is emitted:

1. `CKDD_D0_GO_ONE_SHOT_KNOWN_POOL_REPAIR` — provenance, source split, attack anchors, frozen
   identities, and read-only feasible-region gates pass.  This authorizes drafting one training
   protocol only; it does not authorize training.
2. `CKDD_D0_NO_IDENTIFIABLE_SOURCE_SPLIT` — source-disjoint validation is non-trivial only on
   paper, not in the actual concentrated data.
3. `CKDD_D0_NO_ATTACK_SAFETY_SUPPORT` — the existing anchors cannot define a defensible trust
   region.
4. `CKDD_D0_NO_FEASIBLE_HEAD_REGION` — frozen-space diagnostics show no bounded update can repair
   a meaningful hard-negative mass without crossing attack anchors.
5. `CKDD_D0_ENGINEERING_FAILURE_NO_VERDICT` — identity, join, finite-value, Python/runtime, or
   packaging contract fails.

`NO_UNTOUCHED_BENIGN_CONFIRMATION_AVAILABLE` is an obligatory claim-limitation flag and does not
upgrade any verdict.

## 10. One-shot stop-loss if D0 later passes

The later protocol may contain one P2-head training identity only: frozen E3, no encoder update,
one globally specified hard-negative objective, one attack-logit distillation/trust-region term,
one source-group split, one optimizer schedule, and no family/source exception.  Report is
kill-only, FINAL remains separately gated, and failure ends CKDD.

## 11. Required outputs and tests

D0 must emit source/provenance tables, attack coverage, admissible partition census,
frozen-space diagnostics, untouched-evidence inventory, future kill-only coverage declaration,
boundary audit, verdict, validation report, and `SHA256SUMS`.

Contract tests must cover at least: every SHA pin; exact UID joins; source/member/session leakage;
73.95% concentration reproduction; partition boundary cases; attack-family absence accounting;
whole-report attack identity coverage with the 51,057-row conflict subset reported separately;
report/FINAL score pre-open rejection; verbatim diagnostics with no conditional rerun; no
optimizer step; no fitted parameter; Python 3.9 grammar and observed runtime-API compatibility;
atomic readback; engineering failure emits no scientific verdict.

## 12. Review questions

1. Is the source-partition gate sufficiently non-trivial for six groups and one 73.95% source?
2. Should a known-pool repair with no untouched benign exam still be allowed one training attempt?
3. Is the first-order feasible-region audit informative enough without becoming covert training?
4. Are the kill-only coverage and blind-spot statements complete?
5. Should `aux_normal_select` reservoir provenance be treated as challenge-enriched selection
   evidence exactly as stated?

## 13. Authorization boundary

This FROZEN document fixes the D0 protocol but authorizes no implementation or execution.
Implementation, D0 execution, training, report opening, FINAL access, downloads, and HPC all
require their own authorization.  Any scientific-rule change requires a new named protocol and
review; this file must not be edited in place.
