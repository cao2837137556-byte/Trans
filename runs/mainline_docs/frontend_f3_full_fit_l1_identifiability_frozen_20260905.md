# Frontend-F3 full-fit L1 identifiability audit — FROZEN

Status: `FROZEN_BEFORE_FULL_FIT_L1_REDECODE`

## 1. Purpose

The targeted Frontend-F3 audit selected L1 as the first endpoint-free event refinement that removed both known protected input contradictions. This audit tests whether that result survives the complete original Frontend-F1 training universe before any second training attempt.

It is a no-model, no-score, no-representation, no-training audit. PASS authorizes only preparation of a single Frontend-F2 training specification; it is not evidence of inherited ability or OOD improvement.

## 2. Frozen denominators

- original Frontend-F1 train side: 13,866 targets in 9,307 causal contexts;
- five already exposed incumbent-hard internal-validation attack flips: kill-only targets, never part of vocabulary construction, fitting, selection, or positive evidence;
- construction members: exactly the union needed by those 13,871 targets;
- all select, viewed, report, FINAL, and unrelated internal-validation targets remain unopened.

## 3. Frozen L1 signature

Use L1 exactly as frozen and selected in Frontend-F3:

- the complete incumbent H1–H4 canonical signature;
- exact `frame.len`;
- `delta_log2_us`, with `ZERO` for zero and otherwise `floor(log2(max(1, round(delta_seconds*1e6))))`;
- exact `tcp.len` or `udp.length`, otherwise `NONE`;
- normalized TCP flags bit mask, otherwise `NONE`.

No IP/MAC values, endpoint tokens, source/member/device identifiers, absolute timestamps, capture ordinals, port values/classes, TTL, labels, old scores, old representations, or payload bytes enter L1.

## 4. Causal replay and construction isolation

The deterministic H1–H4 context router and epoch semantics remain byte-identical. A construction-only attachment contains only UID, packet member identity, target ordinal, expected causal context identity, and expected event index. Labels and teacher outcomes are inaccessible until all semantic prefixes are reconstructed and target/context/event-index conservation has passed.

The existing F1 context corpus is the scaffold:

- replay is one-pass because the already materialized expected context key and event index are pinned;
- at each target, the recomputed L0 prefix SHA must equal the existing F1 prefix SHA;
- each target context contains at most 256 causal events; any count mismatch or overflow is an engineering failure;
- member inputs are checked against the pinned packet identity attachment; direct PCAPs are SHA-256 verified, archive members are verified by container size plus central-directory member size/CRC.

## 5. Fresh nested split and vocabulary

Use the already frozen source split salt `frontend-f2-d1-internal-val-v1`, stratified by whether a source contains an attack, with `max(1, ceil(n_sources/5))` sources per stratum assigned to internal validation by salted SHA-256 order.

The L1 vocabulary is built **only** from nested-train contexts. This tightens the earlier F2 implementation: nested-validation event signatures may map to `UNK=1` but may not influence vocabulary identity. `PAD=0`; known signatures receive IDs 2… in SHA-256/UTF-8 order. The vocabulary hard cap remains 4,094 signatures.

## 6. Mechanical gates

All gates are conjunctive:

1. 13,866/13,866 original-train targets and 9,307/9,307 contexts are conserved; five/five kill-only targets are reconstructed separately.
2. Recomputed L0 prefix SHA equals the pinned F1 corpus prefix SHA for every one of the 13,871 targets.
3. L1 canonical prefix identities over the 13,866 training targets contain zero mixed-label buckets.
4. L1 token prefix identities, after applying the nested-train-only vocabulary to the same 13,866 targets, contain zero mixed-label buckets.
5. Vocabulary size is at most 4,094; every target prefix has at least one non-UNK event; nested-train events have zero UNK by construction. Nested-validation UNK rates are reported globally and by source, without an outcome-fitted threshold.
6. The fresh nested split retains at least one context in each of: A protected attack and A protected benign on both sides; B benign on both sides; B attack on nested-train. B attack on nested-validation is reported but not required because the source topology is frozen.
7. Each of the five kill-only attack prefixes has at least one non-UNK event and does not equal any nested-train benign target token prefix. A collision kills the route; absence of collision supplies no positive evidence.
8. Static emission audit finds zero prohibited endpoint/source/port/absolute-time/label/score/representation fields in L1.

## 7. Outcomes

- `F3_FULL_FIT_L1_IDENTIFIABILITY_PASS`: all eight gates pass. This authorizes only drafting the one-shot continuous old-P2 function-preservation training addendum using L1.
- `F3_FULL_FIT_L1_NO_GO`: any scientific gate fails. No alternative field is tried and no training occurs.
- `F3_FULL_FIT_L1_ENGINEERING_FAILURE`: identity, parser, replay, conservation, or output integrity fails; no scientific verdict is emitted.

## 8. Stop-loss

No L1 component may be changed after this run, no L2/L3 fallback exists, and no optimizer step occurs. If PASS later leads to one permitted Frontend-F2 training and that training still violates A inheritance, the route `unified new encoder -> frozen old P2` closes permanently. The incumbent A path remains unchanged throughout.

