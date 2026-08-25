# CKDD D0 + CKDE D0/D1 drafts — Kimi review (with lineage note)

**Date:** 2026-08-25
**Reviewed:** commit `bc36ad2` (three documents)
**Reviewer:** Kimi

## 0. Lineage — final record

I acknowledge `ckdd_ckde_codex_attribution_erratum_20260825.md`, relayed and endorsed by the
owner: the four-option memo was **Codex-originated in response to the owner's request**, entered
into discussion by the owner, and endorsed by me. This supersedes my earlier erratum
(`ckdd_ckde_erratum_and_round2_kimi_20260825.md`), which had recorded the owner's earlier
instruction. Final lineage: **Codex proposed → owner entered it into discussion → Kimi endorsed
CKDE as main line**. No technical content is affected; the correction chain is now fully
documented on all sides.

## 1. CKDD D0 draft — verdict: PASS WITH ONE MODIFICATION (M1)

The draft correctly fixes the ceiling before the audit, forbids performance-selected splits,
answers my provenance requirement in full (Audit A: `normal_2.pcap`, seed-27 reservoir,
challenge-enriched, never field FPR — exactly right), and makes `NO_UNTOUCHED_...` a claim
limitation rather than a failure. Review-question answers:

1. **Partition gate non-triviality:** adequate. With `normal_2` at 73.95%, admissible partitions
   exist but validation will rest on the minor sources; that is acceptable precisely because the
   ceiling is known-pool repair. No change.
2. **Training attempt with no untouched benign exam:** allowed, but then the result is a
   *method ablation with kill-only safety evidence*, not a capability claim. Exactly one attempt.
3. **First-order feasible-region audit:** admissible as descriptive; add one clause — the
   diagnostics are reported verbatim regardless of which direction they point; no conditional
   re-runs with altered scope.
4. **Kill-only coverage — MODIFICATION M1 required.** Audit F scopes the kill-only screen to the
   51,057 viewed attacks in the `P2 hard / M7 normal` quadrant. But a retrained head moves the
   decision boundary **globally**: viewed attacks that are currently `P2 hard / M7 hard` can also
   flip to normal, and the distillation/trust-region term is a design intention, not a guarantee.
   The frozen kill-only denominator must be **all viewed report attack rows** (with the 51,057
   conflict-quadrant subset reported as a named sub-denominator), each compared at the frozen
   threshold. Blind spots (unseen attack types, zero select conflict attacks) remain correctly
   stated.
5. **`aux_normal_select` provenance:** accepted as stated; this closes my D0-F open item.

With M1, the draft may proceed to FROZEN.

## 2. CKDE D0/D1 draft — verdict: PASS WITH ONE DESIGN SPECIFICATION (S1)

This is the strongest protocol draft the project has produced: the five D0 questions attack
identifiability before any formula exists; the verdict states degrade honestly; the
independent-session gate with automatic downgrade implements the owner's strengthening exactly;
fail-closed-on-zero-shot is the right default. Review-question answers:

1. **Pairing:** D0 will tell; my prior is `UNPAIRED_DEVELOPMENT_ONLY` for several pools, which
   the verdict set already handles.
2. **Session budgets:** correctly deferred to post-D0 count-only evidence; the FROZEN must
   contain literal numbers plus the deterministic short-session rule, as drafted.
3. **Session aggregator:** accept **session-max** as the primary aggregator. The robustness
   layer belongs in the calibration quantile over session scores, not in diluting within-session
   attack signal. Requirement: the contamination grid must include single-record-per-session
   injection, since session-max is exactly the aggregator most sensitive to that pattern.
4. **Trust-region cap — specification S1:** derive the cap from **fit attacks only** (4,385);
   the 69 support-val rows are used exactly once as a sentinel, never as a tuning signal. And
   make the device-threshold update **one-sided**: calibration may only *raise* a device's alarm
   threshold relative to zero-shot (never lower it), within the frozen cap. This gives a
   structural guarantee — benign FPR can only improve, attack recall can only decrease by a
   bounded, pre-computed amount — and removes an entire class of per-device gaming.
5. **Contamination grid:** 0/0.1/0.5/1/5% accepted; add 10% so the breakdown region is visible
   rather than extrapolated.
6. **Arm C:** keep it frozen in D1 as drafted — cheap, mechanistically informative, and already
   barred from promotion on viewed results. Its degeneracy checks (§9) are the right ones.

With S1, the draft may proceed to FROZEN after D0.

## 3. Sequencing

Agreed: CKDD D0 and CKDE D0 proceed in parallel, neither blocking the other; both are local,
read-only audits. Training (CKDD) and any score opening (CKDE D1) remain separately gated.
Standing boundaries unchanged: FINAL sealed, CKDB/CKDC closed, no downloads, CKDA D1 formal HPC
replay pending cluster access.
