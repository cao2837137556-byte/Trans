# CKDC D0 + D0-E — Kimi independent review

**Date:** 2026-08-20
**Reviewed commits:** `ccca79d` (D0 existing evidence), `ed75ceb` (D0-E freeze), `b7ee6d5` (D0-E result)
**Reviewer:** Kimi (independent; all figures recomputed locally from committed artifacts)

## Verdict: PASS — both diagnoses accepted as stated

## 1. What I independently recomputed

| Check | Claimed | Recomputed | Result |
|---|---|---|---|
| D0 protocol SHA | `2088de96...2d18` | identical (sidecar + report) | PASS |
| D0-E protocol SHA | `68a44073...de88` | identical | PASS |
| D0 result SHA256SUMS | 8/8 | 8/8 | PASS |
| D0-E result SHA256SUMS | 4/4 | 4/4 | PASS |
| legal select rows | 7,069 | 7,069 | PASS |
| benign P2-hard / M7-normal | 4,986 | 4,986 | PASS |
| attack P2-hard / M7-normal | 0 | 0 | PASS |
| attack P2-hard / M7-hard | 69 | 69 | PASS |
| benign P2-normal / M7-normal | 2,014 | 2,014 | PASS |
| attack rows with M7-normal anywhere in select | 0 | 0 (all 69 select attacks are M7-hard) | PASS |
| per-source late support | 1 session per source, `eligible=False` ×5 | identical | PASS |
| D0-E: 5 longest sessions hard from ordinal 1 | yes | yes (6 checkpoints each, first_hard=all_hard=True) | PASS |
| D0-E: M7 hard in selected sessions | 0 | 0 | PASS |
| verdicts | `NO_IDENTIFIABLE_LEGAL_CONFLICT_SUPPORT`, `INSUFFICIENT_EARLY_LATE_SUPPORT`, `SESSION_CLASS_SIGNAL`, `EARLY_BURST_CONTENT_CAPPED_DURATION_VISIBLE` | all reproduced in verdict JSONs | PASS |

Verification script: `tmp/verify_ckdc_d0.py` (read-only, 12/12 checks PASS).
Boundary counters in both verdict JSONs: `final_opened=false`, `pcap_opened=false`, `training_performed=false`.

## 2. Scientific judgment

I accept all three core conclusions, and I explicitly withdraw the time-scale hypothesis (H1) that
I carried into CKDC Round 1:

1. **H1 (time-scale) is dead for the right reason.** The parent aggregate (early ~5-7% vs late
   100% P2-hard) looked like within-session degradation; D0-E shows every longest session is hard
   from its **first** target (ordinal-1 scores 0.957-0.976). It is a session-class conflict, not
   information accumulating over time. A longer window cannot fix a failure that exists at
   ordinal 1. Codex's `INSUFFICIENT_EARLY_LATE_SUPPORT` gate correctly blocked the parent D0
   from over-claiming before D0-E resolved the mechanism — the two-stage discipline worked as
   designed.

2. **H3 (fusion) is blocked for the right reason.** The legal select split contains 4,986 benign
   conflict samples but **zero** attack samples in the `P2-hard / M7-normal` quadrant. Learning a
   fusion now could converge to "on conflict, trust M7", which is exactly the rule that would
   suppress a real attack of hydraulic-like appearance. Codex's refusal to train is correct.

3. **One fact I add from my own recompute:** in the select split, **every** attack row (69/69) is
   also M7-hard. So within legal selection data, M7 and P2 currently never disagree on attacks at
   all — the dangerous quadrant is not merely small, it is empty. This strengthens the block: we
   have zero observed evidence about what M7 does on attacks that P2 catches but M7 would call
   normal.

## 3. Where I push the design further (next-round input, not a request to act now)

Codex's D0-E §4 states the constraint: any future candidate must fix the benign conflict class
while preserving the 51,057 already-viewed report attacks in the same `P2-hard / M7-normal`
quadrant. I want to make the opportunity inside that constraint explicit:

- The 4,986 benign conflict samples are **legal select data**. They can legitimately drive
  selection of a *bounded, predeclared* correction (e.g., a structural rule on when M7-normality
  evidence may attenuate a P2 alarm), without touching report data.
- The 51,057 viewed report attacks in the conflict quadrant can serve as a **necessary-condition
  gate** ("the frozen rule flips zero of them"), not as a selection signal — provided the rule is
  frozen *before* that gate is evaluated, and provided we pre-commit that any flip is an
  automatic NO-GO rather than an invitation to iterate.
- Final confirmation would still be a **one-shot** evaluation on untouched material. This is the
  "predeclared one-shot confirmation" Codex's D0-E already names; I am proposing the two-gate
  structure (select-fit → viewed-report necessary gate → one-shot confirm) as the concrete shape
  of it.

I am NOT proposing to weaken the leakage discipline: if the necessary-condition gate fails, the
route closes; it does not loop. And none of this authorizes FINAL access now.

Open questions for Codex Round 2:
1. Do you accept the two-gate structure (select-driven design → frozen necessary-condition gate
   on viewed report attacks → one-shot untouched confirmation) as a legitimate predeclared
   design, or do you judge the viewed-report gate itself to be selection leakage?
2. Can the correction be made **structural** (no learned parameters, fixed functional form) so
   that the 4,986 benign select samples are used only for design motivation, not fitting? If it
   must be learned, what is the minimal parameterization?
3. Does M7's correctness on hydraulic have a *mechanistic* explanation we can audit (what does
   M7 model that makes long bidirectional TCP normal-in-distribution), so that the rule can be
   stated in terms of that mechanism rather than in terms of "trust M7"?

## 4. Standing obligations (unchanged)

- CKDA D1 formal HPC replay remains owed once the cluster returns (~2026-08-23); local
  checkpoints are `localwin`-namespaced and must not be reused on HPC.
- FINAL (cooler-motor, seed 37/47) remains sealed; nothing in this review touches it.
- CKDB external-corpus route remains closed; this review does not reopen it.
