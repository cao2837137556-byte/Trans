# Frontend-F0 Coverage Extension Protocol (DRAFT)

- Date: 2026-08-30
- Status: **DRAFT; ROUTE-LEVEL; NON-EXECUTABLE**
- Author: Codex (primary implementation/design role)
- Review basis: Kimi CE ruling `539b313`
- Inherited requirements: `frontend_f0_challenger_requirements_frozen_20260830.md`
- Inherited requirements SHA-256:
  `b46caf0d308531f512ffedd3a9dea8d1438c22a8d136f7c1965dff8ea3f411b0`
- Step-0b result: `41699ed`; independent review: `85bc105`
- Scope: deterministic Coverage Extension (CE) integration only

## 1. Question and decision boundary

This protocol asks one bounded systems question:

> Can one qualified challenger frontend extend representation and detection to
> targets for which the frozen incumbent frontend emits `missing=true`, while
> leaving every incumbent-finite target's deployed score and hard verdict
> exactly unchanged?

CE is a **routing architecture**, not score fusion and not full frontend
replacement. It has two mutually exclusive owners:

```text
frozen raw target
  -> frozen incumbent missing predicate
       false -> incumbent owner: copy frozen incumbent score/verdict
       true  -> challenger owner: challenger representation/head/verdict
```

This draft does not nominate a challenger, authorize a parser, retrieve a
checkpoint, train a model, or open a performance partition. A mature component
remains preferred when it satisfies the frozen requirements. A controlled
frontend may be considered only through the already proposed zero-training
semantic and bounded-resource gates; there is no open-ended architecture
search.

## 2. Exact frozen universe

The routing and measurement universes are fixed by Step-0b:

| Universe | Rows |
|---|---:|
| all fit/select terminal targets | 25,467 |
| incumbent finite (`old_missing=false`) | 13,827 |
| incumbent missing (`old_missing=true`) | 11,640 |
| missing benign | 11,478 |
| missing attack | 162 |

The 162 missing attacks have the following frozen development-role structure:

| Exact family | fit (`support_train`) | select (`support_val`) |
|---|---:|---:|
| Mirai GRE Flooding | 60 | 10 |
| Merlin ICMP Flooding | 43 | 8 |
| Merlin C&C Communication | 27 | 5 |
| Mirai UDP Flooding | 6 | 0 |
| File Download | 3 | 0 |
| **Total** | **139** | **23** |

Missing benign rows have the frozen role split:

| Role | Rows |
|---|---:|
| `aux_normal_fit` | 3,157 |
| `aux_fit` | 3,079 |
| `aux_normal_select` | 3,518 |
| `aux_select` | 1,294 |
| `ood_val` | 381 |
| `id_calib` | 49 |
| **Total** | **11,478** |

All counts are identities, not adjustable budgets. A later implementation
must reconstruct them before opening challenger representations or scores.
Any mismatch is an engineering identity failure and emits no scientific
verdict.

## 3. Claims this route may and may not make

### 3.1 Maximum positive claim before one-shot confirmation

A development PASS may establish only:

1. the challenger covers the incumbent's missing input-semantics blind spot;
2. the deployed incumbent branch is target-exact on incumbent-finite rows;
3. the missing branch provides a preregistered benign development gain without
   losing any observed old-hard attack in legal development evidence; and
4. CE is eligible for a separately frozen one-shot confirmation protocol.

### 3.2 Mandatory claim boundary

**CE success proves blind-spot coverage on the missing subset only. It does
not prove that the hydraulic-class finite-target false-positive problem is
solved.**

Hydraulic-class finite-target error belongs to the separate representation-
quality line. It must be reported separately whenever later performance is
opened. A macro average may not use a missing-subset gain to conceal a
finite-subset failure.

### 3.3 Attack-side downgrade

The route does not promise per-family missing-subset attack detection. The
attack-side evidence hierarchy is:

1. exact incumbent score/verdict invariance on all 13,827 incumbent-finite
   targets;
2. missing-subset attack encodability on all 162 rows, reported by family;
3. development safety on the 23 select rows as a kill-only guard;
4. fit rows reported descriptively and never treated as confirmation;
5. any later viewed/report attack evidence used only to kill a frozen CE
   candidate, never to improve, retune, or replace it; and
6. no positive family-level detection claim where the literal denominator is
   too small.

## 4. Deterministic ownership rule

### 4.1 Frozen router

For each frozen target UID `u`:

```text
owner(u) = INCUMBENT  iff frozen_old_missing(u) == false
owner(u) = CHALLENGER iff frozen_old_missing(u) == true
```

`frozen_old_missing` is the incumbent frontend's already-frozen deterministic
OR of the four Step-0b predicates. The router may not inspect:

- incumbent or challenger anomaly scores;
- model confidence, logits, thresholds, or embeddings;
- label, family, source, device, member path, or role;
- any future packet; or
- any report/FINAL artifact.

There is no learned router, family router, device router, score arbitration,
OR/AND fusion, or post-hoc fallback selection.

### 4.2 Incumbent branch is copied, not recomputed

For every `owner=INCUMBENT` row, the CE materializer must copy the pinned
incumbent score byte string, hard verdict, threshold identity, and provenance
identity. It must not recompute them with a new runtime or pass the row through
the challenger.

The exact gate is:

```text
13,827 / 13,827 UID ownership matches
13,827 / 13,827 score byte strings match
13,827 / 13,827 hard verdicts match
0 duplicate UIDs
0 missing copied rows
```

Failure is terminal `CE_INCUMBENT_INVARIANCE_FAILURE`; it is an engineering or
identity failure, not evidence that CE or full replacement is scientifically
bad.

### 4.3 Challenger branch

For every `owner=CHALLENGER` row, only the single preregistered challenger may
provide representation, score, and hard verdict. A missing challenger output
is not silently removed. Before promotion it remains a missing failure; any
later deployed fail-closed behavior must be frozen in the candidate-specific
CE execution protocol before scores are opened.

The old score may be retained as a comparison column, but it cannot arbitrate
the challenger verdict for that same target.

## 5. Measurement remains full-universe

CE narrows integration scope only. It does not narrow the frozen challenger
exam.

Before CE integration, the challenger must pass the inherited full-universe
sequence on all 25,467 targets:

1. Stage 0 identity and feasibility;
2. Stage 1 count-only availability with absolute gates
   `overall >= 0.90`, every benign device `>= 0.80`, and every exact attack
   family `>= 0.80`;
3. Stage 2 geometry, attack-information, and shallow-header-control gates; and
4. Stage 3 frozen P2 head-bound measurement, if separately authorized.

The challenger must still report its behavior on the 13,827 incumbent-finite
targets. Those values are diagnostic and may reveal representation drift, but
they never replace the incumbent branch under CE.

## 6. CE-specific missing-subset availability gate

After the full-universe availability PASS, a CE-specific count-only audit is
run on the 11,640 routing targets. It opens no representation values or
scores.

It requires simultaneously:

```text
missing-subset overall challenger finite rate >= 0.90
each benign device's old-missing challenger finite rate >= 0.80
each exact missing attack family's challenger finite rate >= 0.80
11,640 / 11,640 status rows present exactly once
all challenger-missing reasons use the preregistered literal dictionary
```

The 162 attack rows are an encodability denominator only at this stage. Exact
per-family numerators and denominators are mandatory; small counts cannot be
hidden by the total.

Failure is terminal
`CE_CHALLENGER_FAILS_AVAILABILITY_ON_MISSING_SUBSET`.

## 7. Stage sequence

### CE-0 — identities and prerequisite verdicts

Before CE code or score access, pin:

- the frozen target manifest and Step-0b missing artifact;
- the incumbent score/verdict artifact and threshold identities;
- the challenger requirements contract and result verdicts;
- the single nominated challenger identity;
- the exact fit/select/report/FINAL allowlists;
- all executable and environment hashes; and
- the CE router source hash and literal status dictionary.

A challenger is ineligible unless its inherited frontend verdict permits the
required stage. No failed mature candidate may silently activate a second
learned challenger. A controlled candidate must have passed its separately
frozen zero-training semantics and resource gates before learned execution.

### CE-1 — full-universe challenger exam

Run the inherited challenger requirements unchanged. CE is not evaluated if
the candidate fails availability, causality, geometry, attack-information, or
header-control gates.

### CE-2 — router and incumbent-equivalence audit

This stage is count/identity/copy-only:

1. reconstruct all 25,467 frozen UIDs;
2. assign exactly 13,827 incumbent and 11,640 challenger owners;
3. prove the incumbent branch exact gate in §4.2;
4. prove no label or score enters the router; and
5. emit an ownership manifest before challenger decisions are opened.

### CE-3 — missing-subset availability

Apply §6. Representation arrays remain unopened until all count-only gates
pass.

### CE-4 — shadow development decisions

Only after CE-0 through CE-3 PASS and separate user authorization may the
frozen challenger head emit scores on legal fit/select rows. The CE result is
shadow-only: it cannot alter the formal alarm stream.

The development split remains role-based:

- fit rows fit the already-frozen challenger/head contract;
- select rows apply the preregistered threshold and CE gates;
- fit attack rows are descriptive, never confirmation evidence; and
- no report or FINAL row is opened.

### CE-5 — development promotion gate

The CE candidate may reach `CE_DEVELOPMENT_PASS` only if all of the following
hold simultaneously:

1. incumbent invariance in §4.2 passes exactly;
2. full-universe inherited frontend/head gates pass;
3. missing-subset availability in §6 passes;
4. all 23 missing `support_val` attacks are hard under the frozen challenger
   head (`23/23`), used strictly as a kill-only safety guard;
5. every incumbent-hard select attack remains hard under the routed CE output;
6. no benign device on the old-missing select subset has more hard rows under
   CE than under the incumbent baseline;
7. at least three benign devices have a strict hard-count reduction;
8. total old-missing benign-select hard-count reduction is at least
   `max(300, ceil(0.10 * H_old))`, where `H_old` is the frozen incumbent hard
   count on exactly the eligible old-missing benign-select rows;
9. zero review rows, denominator removals, duplicate UIDs, or nonfinite scores;
   and
10. report, viewed attack, and FINAL counters remain zero.

Conditions 6–8 define **development utility**, not a paper claim. Their
numbers are proposed now, before opening the corresponding CE scores, so that
`CE_NO_MATERIAL_BENIGN_GAIN` is mechanical rather than narrative.

If `H_old < 300`, condition 8 remains `>=300` and therefore cannot pass. This
is intentional: a branch with fewer than 300 incumbent hard benign rows has no
material development problem to solve under this protocol.

### CE-6 — separately frozen one-shot confirmation

`CE_DEVELOPMENT_PASS` authorizes only drafting a one-shot confirmation
protocol. That later protocol must pin, before any report score is opened:

- same-denominator incumbent and routed CE metrics;
- target-level preservation of every incumbent-hard attack;
- overall and unseen-device attack recall;
- exact-family attack rows with literal small-sample warnings;
- missing and finite benign metrics separately;
- every individual OOD pool and macro;
- ID-benign FPR;
- source/session bootstrap intervals;
- the finite hydraulic pool as a mandatory separate row; and
- a one-shot report/FINAL access ledger.

No performance threshold or final promotion state is inferred by this draft;
those values must be frozen in CE-6 before report access.

## 8. Why the development safety rule is not fusion

The router assigns each target exactly one scoring owner before either score is
examined. Comparing the routed result with the incumbent baseline is an
evaluation gate, not a runtime OR/AND rule. If the challenger loses an old-hard
attack, the candidate is rejected; the final system is not repaired by
reintroducing the incumbent verdict on that target.

This distinction prevents CE from becoming CKDC under another name.

## 9. Required tests before real CE execution

At minimum, the implementation suite must prove:

1. all 25,467 UIDs receive exactly one owner;
2. flipping a score cannot change ownership;
3. changing a label/family/source/device/role cannot change ownership;
4. a future packet cannot change an earlier ownership decision;
5. all 13,827 finite rows copy incumbent score bytes exactly;
6. all 13,827 finite rows copy incumbent hard verdicts exactly;
7. no incumbent-finite row reaches challenger inference;
8. all 11,640 incumbent-missing rows reach challenger status accounting;
9. a challenger-missing row cannot disappear from output;
10. a duplicate or missing UID fails before any scientific verdict;
11. count-only CE-3 cannot load representation arrays;
12. CE-4 cannot open report/viewed/FINAL roles;
13. fit rows cannot be counted as select safety evidence;
14. the 23-row attack safety denominator is exact and immutable;
15. family tables contain all five missing attack families including zero
    select denominators for UDP Flooding and File Download;
16. a per-device benign regression blocks CE even if macro benign improves;
17. fewer than three improved benign devices blocks material-gain status;
18. the `max(300, ceil(0.10 * H_old))` boundary is exact;
19. viewed/report attack outcomes can only kill an already frozen candidate;
20. a CE failure cannot activate full replacement unless its literal state is
    whitelisted in §10.2;
21. Python 3.9 syntax and runtime API compatibility pass; and
22. every durable output survives readback and SHA verification.

Synthetic tests demonstrate contract behavior only, not performance.

## 10. Literal states and route consequences

### 10.1 CE terminal states

```text
CE_IDENTITY_OR_SCOPE_FAILURE
CE_INCUMBENT_INVARIANCE_FAILURE
CE_INHERITED_CHALLENGER_NO_GO
CE_CHALLENGER_FAILS_AVAILABILITY_ON_MISSING_SUBSET
CE_MISSING_SUBSET_SAFETY_NO_GO
CE_NO_MATERIAL_BENIGN_GAIN
CE_DEVELOPMENT_PASS
CE_ONE_SHOT_CONFIRMATION_NO_GO
CE_EXTENSION_SCOPE_INSUFFICIENT_AFTER_SAFE_GAIN
CE_SYSTEM_PROMOTION_CANDIDATE
```

`CE_SYSTEM_PROMOTION_CANDIDATE` is not a production deployment authorization.
Deployment, service integration, and online monitoring require a separate
engineering contract.

### 10.2 Full-replacement discussion whitelist

Full replacement remains closed after ordinary candidate, availability,
identity, safety, or material-gain failure. Those failures show that the
challenger or CE evidence is inadequate; they do not show that replacing the
working incumbent is justified.

Only the literal state
`CE_EXTENSION_SCOPE_INSUFFICIENT_AFTER_SAFE_GAIN` may open a full-replacement
**discussion**. It requires a later one-shot protocol to establish all of:

1. challenger coverage and missing-subset safety passed;
2. CE produced a real missing-subset benign gain;
3. incumbent-finite behavior remained exactly protected; and
4. the frozen whole-system OOD target still failed specifically because the
   remaining error mass is on incumbent-finite targets.

The state authorizes no full-replacement implementation or execution.

## 11. Durable outputs

Any CE execution must produce:

1. immutable input, incumbent, challenger, runtime, and contract identities;
2. full-universe target/status manifest;
3. deterministic ownership manifest;
4. incumbent exact-copy audit;
5. challenger full-universe availability tables;
6. CE missing-subset availability tables by role/device/family;
7. challenger missing-reason tables including zero rows;
8. causal-context size distributions required by the frozen requirements;
9. fit/select shadow score and hard-decision tables, if authorized;
10. attack safety table with fit and select evidence explicitly separated;
11. benign material-gain table by device and role;
12. full boundary/open ledger;
13. literal verdict JSON; and
14. `SHA256SUMS` over every result artifact.

## 12. Resource and anti-waste constraints

1. Mature-component feasibility is checked before learned self-development.
2. A controlled candidate begins with a zero-training semantics prototype;
   no neural training is allowed merely to prove parser/session coverage.
3. No large paired-corpus download is activated before a frontend reaches the
   inherited `F0_ENCODER_ONLY_PASS` state.
4. At most one learned challenger proceeds to representation/head results.
5. Every learned stage has a separately frozen compute, checkpoint/resume, and
   wall-time budget.
6. No family-specific parser, threshold, head, or fallback is permitted.
7. A failed gate cannot be repaired by adding a second candidate or relaxing
   the 0.90/0.80/0.80 requirements.

## 13. Questions for independent review

1. Is `23/23` an appropriate kill-only development guard given C3/F1, while
   remaining explicitly non-promotional and non-family-level?
2. Are conditions 6–8 in CE-5 sufficient to make material benign gain
   mechanical without converting device identity into a routing or model
   feature?
3. Should `H_old < 300` be a legitimate automatic
   `CE_NO_MATERIAL_BENIGN_GAIN`, or should the absolute gate scale down when
   the incumbent missing-subset hard count is already small?
4. Is target-level preservation of every incumbent-hard attack the correct
   later one-shot noninferiority rule, rather than allowing a global recall
   tolerance that could hide changed families?
5. Is the full-replacement whitelist in §10.2 narrow enough to satisfy C2
   without turning every failed challenger into permission to replace the
   incumbent?
6. Must a challenger earn `F1_FRONTEND_CHALLENGE_PASS` before CE-2, or may
   CE-2's router/equivalence audit occur after `F0_ENCODER_ONLY_PASS` because
   it opens no challenger scores?

## 14. Authorization boundary

This document is a draft only. It authorizes no implementation, candidate
retrieval, network access, checkpoint download, corpus download, PCAP decode,
tokenization, representation generation, head training, score opening,
report/FINAL access, HPC submission, alarm change, or deployment.

After independent review, every accepted execution layer still requires:

```text
DRAFT review
-> FROZEN + SHA sidecar
-> independent freeze verification
-> user implementation authorization
-> implementation review
-> user stage-specific execution authorization
```
