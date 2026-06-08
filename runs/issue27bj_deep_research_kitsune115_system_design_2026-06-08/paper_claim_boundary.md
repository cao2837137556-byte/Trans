# Paper Claim Boundary

## What can be claimed now

- Gotham Kitsune115 is the current main frontend candidate.
- The project has identified a defensible low-OOD-alert benchmark direction, but formal model claims are not ready.
- Current failures are informative: attack detection is blocked mainly by support-query gap and raw attack evidence instability, not merely by threshold or OOD gate selection.
- Simple calibrated two-head / logistic fusion / LDA prototype variants did not solve the problem.

## What cannot be claimed now

- Cannot claim final model performance.
- Cannot claim external generalization.
- Cannot claim full benchmark readiness.
- Cannot claim OOD-safe attack detection.
- Cannot claim the current medium diagnostic is A-tier result evidence.
- Cannot claim report-only attack numbers as selection evidence.

## Main paper direction if future gates pass

Potential claim shape:

> Under benign OOD drift, few-shot attack support is not assumed to cover all future attacks. The method decomposes online NIDS decisions into high-recall attack evidence, OOD benign risk, bounded region memory, and selective review/unknown control, enabling low-OOD-alert detection under support-query shift.

This claim requires:

- attack hard-min >= `0.93` on legal dev diagnostic before OOD repair;
- OOD gate repair after attack evidence stabilizes;
- bounded review cost;
- full/larger materialization and formal benchmark after protocol freeze;
- final/report-only one-way evaluation.

## Innovation boundary

Not innovation:

- Kitsune / AfterImage / netStat 115D frontend;
- raw PCAP parsing;
- basic feature extraction.

Potential innovation:

- low-OOD-alert few-shot online NIDS protocol;
- support-query coverage/evidence decomposition;
- attack evidence and OOD risk decoupling;
- bounded region memory for attack support expansion;
- selective controller with review/unknown budget.

## Required negative controls

- shared scorer with OOD-as-negative hard suppression;
- bank-only prototype shell;
- calibrated two-head margin;
- metric embedding without controller;
- controller without metric embedding;
- no active-label expansion;
- fixed first32/kcenter support without region memory.

## Required discipline in writing

- Say "medium diagnostic" when using medium results.
- Say "report-only replay" when discussing final/report-only roles.
- Do not write "formal benchmark" until full/larger protocol is frozen.
- Do not imply final OOD was used for threshold selection.
- Do not imply report-only attack eval was used to choose the method.

## Current recommended claim status

`claim_status = method_direction_promising_but_main_claim_blocked`

Reason:

- The problem is meaningful and research-grade.
- The frontend/split discipline is now much cleaner than earlier Mirai runs.
- However, attack evidence is not yet strong enough to enter OOD gate repair or full benchmark.
