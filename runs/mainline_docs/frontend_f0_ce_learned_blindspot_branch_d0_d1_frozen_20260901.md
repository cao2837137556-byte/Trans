# Frontend-F0 CE Learned Blind-Spot Branch D0/D1 Protocol (FROZEN)

- Date: 2026-09-01
- Status: **FROZEN; NON-EXECUTABLE; SCIENTIFIC RULES IMMUTABLE**
- Author: Codex (primary design/implementation role)
- Route: Coverage Extension (CE), learned challenger branch only
- Current authorization consumed: mechanical freeze after independent review `4d8126a`
- Independent review: `runs/mainline_docs/frontend_f0_ce_learned_blindspot_kimi_draft_review_20260901.md`

## 1. Objective

The zero-training semantic frontend has established that every frozen target can
be organized into a finite causal context.  This protocol asks the next, and
strictly narrower, question:

> Can one bounded learned encoder turn the frozen semantic contexts into a useful
> representation for the incumbent-missing branch, without changing any deployed
> decision on the incumbent-finite branch?

The experiment is a **backward-compatible coverage extension**, not a frontend
replacement and not score fusion:

```text
frozen target u
  -> frozen old_missing(u)
       false -> copy frozen netFound E3 / P2 score and verdict byte-for-byte
       true  -> one preregistered learned semantic branch
```

The learned branch may fail.  Such failure leaves the incumbent system intact.
Nothing in this protocol authorizes detector-head training, score opening,
report/FINAL access, deployment, or full replacement.

## 2. Governing evidence and immutable inputs

### 2.1 Inherited contracts

| Contract | SHA-256 |
|---|---|
| `frontend_f0_challenger_requirements_frozen_20260830.md` | `b46caf0d308531f512ffedd3a9dea8d1438c22a8d136f7c1965dff8ea3f411b0` |
| `frontend_f0_coverage_extension_protocol_frozen_20260831.md` | `0b102b7929e2a1ad2e269e35a5a225880a97d34bcc036d586b7066bcc5cddcfe` |
| `frontend_f0_controlled_zero_training_semantics_protocol_frozen_20260831.md` | `532bb52e4d03c0321f1e874cc4bd7a49fca3391943c0dd23a1968fd69ac3c0ee` |

The learned branch must consume these semantics as written.  A candidate is
ineligible if it requires changing H1-H4 context definitions, endpoint-token
rules, context bounds, timestamp-regression policy, causal cutoffs, or the
frozen `old_missing` router.

### 2.2 Positive prerequisite result

The prerequisite result is commit `6f210af`, with result report
`frontend_f0_zero_training_semantics_real_result_20260831.md` and report
SHA-256
`64266351c07bbd96db779e4bb3d215bf108658370a590f633ee00fc629f2f48a`.

The exact semantic-status artifact is:

```text
runs/frontend_f0_zero_training_semantics_real_20260831/
  zt2_semantic_status_by_target.csv.gz
SHA-256 = 73aa283477ee4b38fa71441e6d04760d24ebb2d7770ec7393855aae3813cfc5e
```

Frozen prerequisite counts:

| Universe | Rows |
|---|---:|
| all fit/select terminal targets | 25,467 |
| incumbent finite | 13,827 |
| incumbent missing | 11,640 |
| missing benign | 11,478 |
| missing attack | 162 |
| semantic finite after ZT-2 | 25,467 |

ZT-2 proved semantic coverage only.  It did not produce a learned
representation, anomaly score, detector verdict, OOD-FPR result, or attack
recall result.

## 3. Non-negotiable invariants

1. **Incumbent ownership is immutable.** Every one of the 13,827
   `old_missing=false` targets remains owned by the frozen E3/P2 branch.
2. **The incumbent is copied, not recomputed.** Score bytes, threshold identity,
   hard verdict, and provenance must match the CE contract exactly.
3. **The new branch owns only old-missing targets at integration time.** It may
   not arbitrate, override, veto, or rescore an incumbent-finite target.
4. **The router is deterministic.** It uses only the frozen old-missing
   predicate; no learned router, score router, device router, or family router
   exists.
5. **The semantic contract dominates the candidate.** A mature component is
   eligible only if it directly consumes the frozen H1-H4 causal semantics.
   The semantic layer is never changed to accommodate a checkpoint.
6. **One executed learned challenger.** There is no architecture sweep, model
   zoo, outcome-conditioned fallback, or family-specific branch.
7. **Fit-only representation learning.** Select labels and select contexts are
   unavailable to encoder fitting, early stopping, checkpoint selection, loss
   weighting, vocabulary selection, or architecture selection.
8. **No family patch.** The five missing attack families receive no separate
   model, loss weight, threshold, token rule, or stopping rule.
9. **Small-sample boundary.** The 162 missing attacks are reported exactly by
   role, family, source, and independent context.  They do not support a broad
   per-family detection claim.
10. **A representation PASS is not a detector PASS.** Detector-head work begins
    only under a later frozen protocol and fresh user authorization.

## 4. Why D0 precedes model nomination

The 25,467 target rows are not 25,467 independent training samples.  Many rows
can share one causal context, one source, or one packet member.  Treating rows as
independent would overstate training size and contaminate validation.

D0 is therefore count/identity/compatibility-only.  It must finish before any
learned representation is generated.  Its purposes are:

1. reconstruct the true independent-context denominator;
2. prove a leakage-free fit/select partition exists;
3. audit whether a mature encoder can consume the frozen semantics unchanged;
4. nominate exactly one executable challenger by a result-blind rule;
5. size CPU/GPU/RAM/disk/runtime honestly; and
6. freeze the D1 numerical and architectural addendum before training.

## 5. D0-A — exact independent-context census

### 5.1 Unit of independence

The atomic representation unit is:

```text
semantic_context_key = (member_id, causal_context_id, context_epoch)
```

Target rows sharing this key are one context.  They may never be split across
fit, internal-validation, select, or later confirmation partitions.

**Frozen cross-phase resolution (M1).** A semantic context containing any
`phase=select` row is owned in full by the evaluation side.  Every row of that
context, including any `phase=fit` row, is excluded from encoder fitting,
vocabulary/numeric-transform fitting, fit-internal validation, checkpoint
choice, and any other model-development operation.  The context definition is
not changed and no target is reassigned.  The same rule applies without
exception to attack-bearing contexts.

The census must exact-join the semantic-status artifact to the already frozen
fit/select plan by UID, with:

```text
25,467 / 25,467 joined exactly once
0 duplicate UIDs
0 unknown roles
0 target removals
0 report rows
0 FINAL rows
```

### 5.2 Mandatory denominators

Before opening labels beyond count-only post-join reporting, emit counts by:

- phase (`fit`, `select`);
- role;
- `old_missing` owner;
- member and source;
- benign device;
- exact attack family;
- H1/H2/H3/H4 tier;
- independent semantic context;
- targets per context;
- events per context; and
- number of contexts that contain more than one target.

The 162 old-missing attack rows must be mapped to their literal number of
independent contexts.  Row counts may never stand in for this denominator.

The following count-only literals were independently derived before freeze and
must be mechanically reverified by D0-A:

| Quantity | Frozen literal |
|---|---:|
| all independent semantic contexts | 18,187 |
| pre-exclusion fit rows / contexts | 18,398 / 12,908 |
| select rows / contexts | 7,069 / 5,298 |
| cross-phase contexts | 19 |
| fit rows inside cross-phase contexts | 132 |
| select rows inside cross-phase contexts | 32 |
| legal fit rows / contexts after whole-context exclusion | 18,266 / 12,889 |
| old-missing benign fit contexts after exclusion | 5,178 |
| old-missing benign select contexts | 4,157 |
| old-missing fit attack contexts before exclusion | 40 |
| attack-bearing cross-phase contexts | 11 |
| **legal old-missing fit attack contexts after exclusion** | **29** |

The post-exclusion attack-context family census is frozen as:

| Exact family | Legal fit contexts |
|---|---:|
| File Download | 2 |
| Merlin C&C Communication | 3 |
| Merlin ICMP Flooding | 13 |
| Mirai GRE Flooding | 10 |
| Mirai UDP Flooding | 1 |
| **Total** | **29** |

The 29-context literal is intentionally retained even though it is below the
frozen global lower bound of 30.  D0-A must therefore emit
`CEL_D1_INSUFFICIENT_INDEPENDENT_ATTACK_CONTEXTS` if the exact recheck
reproduces these counts.  The lower bound may not be weakened, the 11
cross-phase attack contexts may not be recovered for fitting, and target rows
may not be resampled to manufacture independence.

### 5.3 Leakage and identifiability gates

D0-A fails closed if any of the following occurs:

1. a cross-phase context is not assigned in full to the evaluation side under
   M1;
2. one semantic context is assigned to more than one model-development split;
3. any packet member is opened beyond an already legal fit/select causal prefix;
4. any row from an evaluation-owned context enters representation training,
   vocabulary/transform fitting, fit-internal validation, or checkpoint choice;
5. any report/FINAL identity enters the census; or
6. the exact UID, context, phase, and exclusion conservation laws fail.

The literal learnability bounds are:

```text
legal fit contexts after exclusion          >= 10,000
old-missing benign legal fit contexts       >=  4,000
old-missing benign select contexts          >=  4,000
legal old-missing fit attack contexts       >=     30
per-family legal fit attack contexts         report all; <3 => INSUFFICIENT
```

D0-A must reproduce the frozen actuals 12,889 / 5,178 / 4,157 / 29 before
opening any learned array.  A failed general context denominator emits
`CEL_D0_NO_IDENTIFIABLE_CONTEXT_DENOMINATOR`.  A global attack-context count
below 30 emits `CEL_D1_INSUFFICIENT_INDEPENDENT_ATTACK_CONTEXTS`.  Neither
state permits row-level resampling, a weaker split, a reduced lower bound, or
candidate execution.

## 6. D0-B — candidate compatibility and single-candidate nomination

### 6.1 Compatibility rubric

Candidate assessment is restricted to paper/documentation/repository identity
and a synthetic semantic battery.  No real embedding or detector outcome is
available.  The rubric is lexicographic:

1. consumes the frozen H1-H4 semantic event sequence without changing it;
2. causal/past-only execution at every target cutoff;
3. covers H1-H4, including ICMP/GRE and keyless H4 contexts;
4. permits raw endpoint-identifier masking and contains no irreversible raw
   endpoint embedding requirement;
5. deterministic terminal representation and explicit dimension;
6. legal license and reproducible source/checkpoint identity;
7. known pretraining lineage, or an explicit from-scratch fit-only plan;
8. Python 3.9 and target-platform compatibility;
9. bounded local/HPC resource estimate and resumable checkpoints; and
10. no family-, device-, or dataset-specific code path.

### 6.2 Nomination rule

The executed challenger is exactly one of:

1. **direct-compatible mature encoder**, if one passes all ten rubric items; or
2. **controlled semantic sequence encoder**, built only from mature library
   primitives and trained from scratch on the frozen fit semantic corpus, if no
   mature checkpoint directly consumes the contract.

The mature-component audit is compatibility-first, not popularity- or
performance-first.  It may not modify H1-H4 semantics to make a component pass.
Every assessed mature component must receive an item-by-item ten-rubric record
with evidence.  Every failure must carry literal reasons; silent shopping among
components is forbidden.

The nomination, source identity, architecture, parameter count, output width,
token dictionary, pooling rule, loss, seed set, optimizer, learning-rate rule,
epoch budget, stopping rule, and checkpoint rule must be written literally into
the D0 numerical/identity addendum before D1 execution.

There is **no engineering fallback after nomination** in this experiment.  If
the nominated candidate cannot run under its frozen identity, the state is
`CEL_D0_SINGLE_CHALLENGER_ENGINEERING_NO_GO`; the route does not activate a
second encoder.

## 7. D0-C — training-corpus and label isolation

The learned encoder may use all legal post-M1 `phase=fit` semantic contexts, including
incumbent-finite contexts, because this is a label-free representation corpus.
This does not change deployment ownership: only old-missing targets can later
use its score.

Rules:

1. all labels, exact families, device outcome columns, old scores, and hard
   verdicts are unavailable to the representation loss;
2. vocabulary and numeric transforms are fit on fit contexts only;
3. internal self-supervised validation is a deterministic hash-group split by
   full semantic context, nested entirely inside the legal post-M1 `phase=fit`
   corpus;
4. every target from one context follows its context owner;
5. all contexts containing any `phase=select` row remain evaluation-only in
   full under M1;
6. class/family balancing is forbidden during representation learning;
7. source/device labels may be joined only after representations are frozen,
   solely for leakage and geometry audits; and
8. report/FINAL remain unopened.

## 8. D0-D — resource and anti-waste gate

Before D1, perform a synthetic or count-derived resource pilot only.  It may
measure parser throughput, tensor shapes, estimated token count, peak-RSS model,
checkpoint bytes, and projected wall time.  It may not train on real contexts.

The D0 addendum must freeze:

- local CPU and optional GPU execution modes;
- maximum RAM and disk footprint;
- maximum wall time per attempt;
- heartbeat frequency;
- context/member checkpoint granularity;
- restart semantics;
- maximum number of real training attempts (one); and
- Python 3.9 syntax/runtime regression gates.

Failure to fit the available resource envelope is
`CEL_D0_RESOURCE_NO_GO`.  Reducing the model after observing a representation
result is forbidden.

## 9. Fixed non-learned semantic-summary control

D1 must include one deterministic, non-learned control built from the same
frozen semantic events.  It is not a second challenger and cannot be promoted.
Its sole purpose is to answer:

> Did the learned encoder add information beyond fixed protocol/direction/
> length/time/context summary statistics?

The exact summary fields, bucketing, aggregation, and dimension must be frozen
in the D0 addendum before any learned representation exists.  It must omit raw
endpoint identifiers and use the same causal cutoff.

A learned candidate that cannot beat this control on the preregistered
attack-information canary terminates as
`CEL_D1_NO_LEARNING_VALUE_ADDED`, even if it has 100% availability.

## 10. D1-A — learned representation materialization

D1-A requires all D0 gates and separate user authorization.

Execution order:

1. rebuild the frozen semantic corpus and verify exact ZT-2 status equivalence;
2. materialize fit-only training sequences without labels;
3. train the single frozen encoder once;
4. freeze its checkpoint before any select representation is generated;
5. generate deterministic representations for all 25,467 targets;
6. rerun generation and verify numerical determinism within a frozen tolerance;
7. emit an explicit status row for every target; and
8. stop before any detector-head training or anomaly-score computation.

Changing a future packet must leave every earlier representation invariant.
Changing raw endpoint identifiers by a within-member bijection must preserve
the context partition and, in the mandatory masked arm, must not expose the raw
identifier to the encoder.

## 11. D1-B — encoder-only scientific gates

### 11.1 Availability

Inherit the already frozen absolute requirements:

```text
full-universe finite rate >= 0.90
every benign device finite rate >= 0.80
every declared-supported exact attack family finite rate >= 0.80

old-missing finite rate >= 0.90
every benign device's old-missing finite rate >= 0.80
every exact missing attack family's finite rate >= 0.80
```

ZT-2 coverage does not automatically pass the learned encoder.  Missing,
nonfinite, or resource-failed representations remain denominator failures.

### 11.2 Collapse and effective-information checks

Before labels are joined, report:

- per-dimension variance and robust scale;
- duplicate-vector rate;
- effective rank and singular-value spectrum;
- representation norm distribution;
- within-context repeated-target trajectory; and
- constant/all-zero/nonfinite fractions.

Literal collapse thresholds must be frozen in the D0 numerical addendum before
real representations exist.  Failure is `CEL_D1_REPRESENTATION_COLLAPSE`.

### 11.3 Device and endpoint shortcut audit

After the encoder checkpoint is frozen, run all of:

1. the inherited leave-one-device-out geometry instrument;
2. a frozen-capacity shallow device classifier;
3. the mandatory raw-endpoint-masked arm;
4. a shuffled-endpoint-token negative control; and
5. a frozen shallow-header/statistical control.

The candidate may not claim semantic value merely because device identity is
easy to decode.  The device-classifier metric is balanced accuracy from a frozen-capacity
linear classifier under context-grouped splits.  Its chance reference is a
label-permutation null with at least 1,000 permutations; the 99th percentile is
reported.  The executable guard is comparative, not an absolute near-chance
test: the learned representation's device decodability may not exceed the
deterministic semantic-summary control by more than one literal margin frozen
in the D0 numerical addendum.  Every assessed device and denominator must be
reported.

The endpoint-masked arm must independently pass the attack-information canary.
If the unmasked arm passes and the masked arm fails, the candidate is
fingerprint-reliant and terminates as
`CEL_D1_DEVICE_OR_ENDPOINT_SHORTCUT_NO_GO`.

The inherited dimensionless geometry guards remain the default proposal:

```text
median projection distance <= 0.20
worst projection distance <= 0.35
median principal angle <= 20 degrees
worst principal angle <= 35 degrees
median between/within R >= 2.0
at least 80% of eligible devices have R >= 1.0
```

These constants are provisional defaults portable only if all of the following
are satisfied before execution:

1. the projection-distance, principal-angle, and R-ratio metric definitions are
   reproduced verbatim in the D0 numerical addendum;
2. the eligible-device denominator is disclosed literally;
3. at least four devices are eligible, otherwise geometry is descriptive-only
   and cannot contribute to a positive verdict; and
4. the R-ratio guards use exactly the same eligibility rule.

Failure of any portability condition prevents a positive geometry gate; it
does not permit retuning the constants.

### 11.4 Fit-only attack-information canary

Attack information is measured only after checkpoint freeze.  It uses grouped
splits by semantic context and source/member, never target-row splits.

The canary ladder is limited to:

1. nonparametric geometry; and
2. a frozen-capacity linear probe.

A small MLP or any nonlinear learned canary is not authorized.  Suspected
nonlinear signal requires a new protocol and may not be activated in-run.

The fixed semantic-summary control is evaluated with the identical splits and
capacities.  No select result chooses a probe, hyperparameter, family weight, or
threshold.

Because only 162 old-missing attack rows exist, and M1 leaves only 29 legal fit
attack contexts, outputs must include:

- fit/select targets and independent contexts by exact family;
- the pre-exclusion, cross-phase, and post-exclusion attack-context counts;
- grouped bootstrap or exact small-sample intervals where identifiable;
- `INSUFFICIENT_INDEPENDENT_ATTACK_CONTEXTS` globally below 30 and for every
  family below 3;
- no per-family tuning or positive per-family claim; and
- no macro-only concealment.

A positive representation state requires both observable attack information and
strictly greater preregistered canary value than the deterministic control.
Exact metrics and margins must be frozen before D1 arrays are opened.

### 11.5 Select is kill-only for attack safety

The 23 old-missing `support_val` attack rows are never training evidence.  After
all fit-derived representation choices are frozen, select may only kill the
candidate.  It cannot improve, retune, replace, or activate a fallback.

If their independent-context denominator is too small for a stable canary, that
fact is reported literally; it is not repaired with target-row resampling.

## 12. D1 advancement boundary

The only positive D1 terminal state is:

```text
CEL_D1_REPRESENTATION_FEASIBLE
```

It requires simultaneously:

1. exact D0 identity and context-denominator PASS;
2. single-candidate and resource PASS;
3. full-universe and old-missing availability PASS;
4. causal and deterministic representation PASS;
5. no representation collapse;
6. device/endpoint leakage and geometry PASS;
7. attack-information canary PASS on legal fit evidence;
8. learned representation beats the fixed semantic-summary control;
9. sparse select attack guard is not violated; and
10. incumbent ownership and exact-copy evidence remains intact.

This state authorizes only drafting a detector-head protocol.  It is not
`F1_FRONTEND_CHALLENGE_PASS`, `CE_DEVELOPMENT_PASS`, or a performance claim.

## 13. Literal stop states

```text
CEL_D0_IDENTITY_OR_SCOPE_FAILURE
CEL_D0_NO_IDENTIFIABLE_CONTEXT_DENOMINATOR
CEL_D0_NO_COMPATIBLE_SINGLE_CHALLENGER
CEL_D0_SINGLE_CHALLENGER_ENGINEERING_NO_GO
CEL_D0_RESOURCE_NO_GO
CEL_D1_AVAILABILITY_NO_GO
CEL_D1_CAUSALITY_OR_DETERMINISM_FAILURE
CEL_D1_REPRESENTATION_COLLAPSE
CEL_D1_DEVICE_OR_ENDPOINT_SHORTCUT_NO_GO
CEL_D1_DEVICE_GEOMETRY_NO_GO
CEL_D1_INSUFFICIENT_INDEPENDENT_ATTACK_CONTEXTS
CEL_D1_NO_ATTACK_INFORMATION
CEL_D1_NO_LEARNING_VALUE_ADDED
CEL_D1_SELECT_ATTACK_SAFETY_NO_GO
CEL_D1_REPRESENTATION_FEASIBLE
```

No stop state activates another learned encoder, full replacement, report
access, or a family patch.

## 14. Required durable outputs

### 14.1 D0

1. contract, input, runtime, and executable identities;
2. 25,467-row UID/context/phase conservation audit;
3. context census by phase/role/source/member/device/family/tier, including
   the 19 cross-phase contexts and full M1 exclusion conservation;
4. target-per-context and event-per-context distributions;
5. context-level split manifest and leakage audit;
6. mature-component compatibility rubric with one nominated outcome;
7. candidate identity and frozen architecture/training addendum;
8. deterministic semantic-summary control definition;
9. resource pilot and storage plan;
10. role-open audit proving representation/model/score/report/FINAL counters 0;
11. D0 verdict JSON; and
12. SHA256SUMS covering every terminal artifact.

### 14.2 D1

1. fit-corpus and fit-internal-validation context manifests;
2. training/checkpoint lineage and heartbeat log;
3. full 25,467-row representation status manifest;
4. deterministic replay and causal future-mutation audit;
5. availability tables by role/device/family/tier and old-missing owner;
6. collapse/effective-rank report;
7. endpoint masking and shuffled-token audits;
8. device geometry and shallow-device-classifier report;
9. shallow semantic-summary control results;
10. fit-only attack-information canary with context-level denominators;
11. sparse select attack kill-only audit;
12. incumbent ownership/exact-copy audit;
13. role-open and engineering-failure ledgers;
14. D1 verdict JSON; and
15. SHA256SUMS covering every terminal artifact.

## 15. Minimum contract tests before real execution

At minimum, tests must prove:

1. all inherited contract hashes are enforced;
2. 25,467 UIDs join exactly once;
3. a context containing any select row is excluded in full from every fitting
   mechanism;
4. cross-phase contexts remain intact and are never redefined or row-split;
5. target-row random splitting is impossible;
6. select-owned contexts cannot enter encoder fitting, vocabulary/transform
   fitting, fit-internal validation, or checkpoint choice;
7. labels/scores/verdicts are inaccessible to representation training;
8. report/FINAL are rejected before file opening;
9. raw endpoint values never enter numeric model inputs;
10. endpoint bijection preserves context partition;
11. endpoint masking and shuffled-token controls are distinct arms;
12. future-event mutation leaves earlier representations unchanged;
13. timestamp regression follows the frozen causal policy;
14. H4 is neither a global pseudo-session nor forced all-singleton;
15. one nominated candidate cannot activate a fallback;
16. resource failure emits no scientific verdict;
17. availability accounting conserves all targets including missing outputs;
18. duplicate, constant, all-zero, and nonfinite representations trigger the
    proper checks;
19. device/family tables retain zero rows;
20. attack canary grouping is by context/source, never target row;
21. the canary ladder cannot instantiate an MLP or nonlinear learned probe;
22. the deterministic control uses the same splits as the learned candidate;
23. device-classifier permutations and the comparative control guard are exact;
24. endpoint-masked attack evidence can independently kill the candidate;
25. geometry cannot pass with fewer than four eligible devices;
26. select attack evidence can only kill;
27. all 13,827 incumbent-finite targets remain challenger-inference-free;
28. incumbent score bytes and hard verdicts remain exact;
29. no stop state enables full replacement or a second candidate;
30. Python 3.9 syntax and runtime APIs pass; and
31. every durable artifact survives readback and SHA verification.

Synthetic tests prove contract behavior only, not scientific performance.

## 16. Claim matrix

| Claim | Maximum status under this protocol |
|---|---|
| frozen semantics cover prior blind spot | already established by ZT-2 |
| learned encoder produces stable representations | D1 may establish |
| representation retains fit attack information | D1 may establish narrowly |
| per-family missing-attack detection | not established |
| missing-subset benign FPR improves | not measured |
| whole-system OOD FPR improves | not measured |
| hydraulic finite-target error improves | explicitly not measured |
| incumbent finite attack capability preserved | structural exact-copy claim only |
| unseen-device detection improves | not established |
| report/FINAL performance | forbidden |

## 17. Normative independent-review rulings

1. **Q1 / denominators.** The literal lower bounds and independently observed
   census values in §5 are frozen now.  D0 may only reverify them.  The observed
   legal fit attack count 29 is below 30 and therefore predicts a fail-closed
   scientific stop; it does not authorize lowering the bound.
2. **Q2 / nomination.** The two-tier nomination rule is accepted.  Every mature
   candidate requires an itemized ten-rubric evidence record and literal failure
   reasons.  The controlled encoder identity belongs in the D0 addendum.
3. **Q3 / corpus.** Representation learning uses all legal post-M1 fit contexts,
   not only old-missing contexts.
4. **Q4 / control.** The deterministic semantic-summary arm is a non-promotable
   value-added control, not a second challenger.
5. **Q5 / leakage.** Device leakage uses context-grouped linear-classifier
   balanced accuracy, at least 1,000 label permutations, the 99th-percentile
   null reference, and a comparative margin to the deterministic control frozen
   before learned arrays.  The endpoint-masked arm must independently retain
   attack information.
6. **Q6 / attack evidence.** Global legal fit attack contexts must be at least
   30; each family below 3 is marked INSUFFICIENT and cannot support a positive
   family claim.  Row resampling is forbidden.
7. **Q7 / canary capacity.** The ladder ends at nonparametric geometry and a
   frozen linear probe.  No MLP is permitted.
8. **Q8 / geometry portability.** The inherited constants are provisional
   dimensionless defaults, executable only under the four portability
   conditions in §11.3.

## 18. Authorization boundary

This FROZEN document consumes only the user's authorization for mechanical
revision after independent review and generation of a SHA-256 sidecar.

Not authorized:

- implementation or synthetic tests;
- packet opening or re-decode;
- network retrieval or checkpoint download;
- candidate nomination execution;
- representation generation or training;
- detector-head fitting or score opening;
- CE routing execution;
- report/FINAL access;
- HPC submission; or
- deployment.

The next legal action is independent SHA/diff verification of this FROZEN
document.  Implementation, D0 execution, candidate nomination, representation
training, and any D1 action each require later explicit authorization.  Given
the frozen 29 < 30 attack-context result, no implementation may silently
reinterpret the expected `CEL_D1_INSUFFICIENT_INDEPENDENT_ATTACK_CONTEXTS`
terminal state as an engineering failure or lower the bound.
