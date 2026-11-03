# N3 conservative fixed-representation joint repair

Date: 2026-09-08. Status: N3_DESIGN_FROZEN_IMPLEMENTATION_AND_REAL_FIT_NOT_AUTHORIZED.
Base: codex/exp-mainline, 4b28747b09480471e2bac1beb3a9badf27280efb.
The user authorized the next complete design and review after the post-N2
strategy proposal. Implementation/synthetic acceptance and ONE real fitting
attempt each require subsequent authorization. No such execution occurs here.

## 1. New question and closed historical stages

Can one 65-parameter Linear(64,1) head on the fixed terminal representation
jointly preserve all 8,660 N1-correct training judgments, satisfy all 1,484
original development protections, and preserve all 2,567 N2 B-benign releases?
These are 12,711 disjoint, predeclared development-fitting constraints.

The question is repair of known finite observations. N1 fitted only its 6,914
protected training constraints; N2 evaluated the resulting fixed candidate and
failed development protection. N3 changes the prospective constraint population
and learning role explicitly. It is neither a repeated N1 solve nor a rerun of
N2 to choose another result. F5 remains NO_ELIGIBLE_CHECKPOINT under every N3
outcome; neither N1 nor N2 output can be amended, resumed or promoted.

N2 section 9 says, "Do not run a sequence of head searches under this roadmap."
The new proposal authorizes no execution under that roadmap. Only after this
new scope is reviewed, implemented/accepted and separately authorized may ONE
N3 conservative repair be attempted. Its constraint set, objective, numerical
recipe and terminal branches are fixed here. No result-selected expansion,
subset relaxation, additional solver, candidate or retry is allowed afterward.

Fix event_projection, event_activation, GRU, head_hidden, head_activation and
semantic_head to the sealed F5 terminal state. The object is their 64D output
to head_output, not the 128D GRU state or old netFound representation. A and B
continue to share the same GRU and their own student head; no A/B/source routing
or old P2 deployment head. P2 is not called in this study at all.

## 2. Exact population and new roles

The pinned F4/P original selectors, not UID spelling, determine membership.
Their complete 13,866 targets / 9,307 contexts remain in original train and
internal_val splits. P's census uses the producer's aggregate key val for the
latter; this naming does not change membership.

| Original split/category | Targets | N3 constrained | Role |
|---|---:|---:|---|
| train A1C | 2,179 | 2,179 | original_train_retention |
| train A0C | 4,667 | 4,667 | original_train_retention |
| train B1N | 68 | 68 | original_train_retention |
| train A0W | 24 | 24 | original_train_retention |
| train B0N | 1,722 | 1,722 | original_train_retention |
| internal_val A1C | 3 | 3 | development_protection_fit |
| internal_val A0C | 1,478 | 1,478 | development_protection_fit |
| internal_val B1N | 3 | 3 | development_protection_fit |
| internal_val B0N, N2 hard=false | 2,567 | 2,567 | development_B_release_retention_fit |
| internal_val B0N, N2 hard=true | 1,153 | 0 | exposed_report_only |
| internal_val A0W | 2 | 0 | exposed_report_only |

Constrained totals: 8,660 original train + 4,051 development = 12,711, comprising
2,253 attacks and 10,458 benign labels. All 13,866 targets remain in canonical
candidate reporting. The 1,155 residual targets are not a holdout and may share
context/prefix dependencies with fitted targets. Persist original_split,
original_category/protected, constraint_role and exposure_role independently;
the old 6,914-protected boolean must not silently become the N3 fit selector.

The outcome-informed B membership is defined ONLY by the hash-pinned N2
all_target_predictions.json: category=B0N, label=0, hard=false under the stored
actual float32 logit. Its exact file identity plus this deterministic predicate
freeze the UID membership now. Before any new feature decoding or solve,
materialize and seal the complete role/UID attachment; a new baseline may
verify this population but cannot choose a different one. Check set disjointness,
all counts, original metadata equality and strict lexical UID order.

Preserve the complete N2 development source/category/context accounting:
train 8,660/4,984 across 13 sources; development 5,206/4,323 across four sources.
Source development counts are 600/464 for
iotsim-combined-cycle-6_0-0_to_OpenvSwitch-13_6-0, 600/189 for
iotsim-domotic-monitor-3_0-0_to_OpenvSwitch-23_3-0, 4,000/3,667 for normal_1.pcap,
and 6/3 for processed/iotsim-combined-cycle-10.csv.
normal_1 A0C is 843/672, B0N is 3,157/2,995; other A0C is 635/321.
Preserve literal families: combined-cycle is not iotsim-combined-cycle.

## 3. B-retention is a sufficient, stronger rule

| B key | Original targets/contexts | Original floors targets/contexts | N2 normal targets | N2 all-B-benign-normal contexts |
|---|---|---|---:|---:|
| iotsim-combined-cycle | 333 / 282 | 34 / 29 | 333 | 282 |
| iotsim-domotic-monitor | 230 / 50 | 23 / 5 | 230 | 50 |
| ton-iot-external | 3,157 / 2,995 | 316 / 300 | 2,004 | 1,906 |
| Total | 3,720 / 3,327 | 373 / 334 | 2,567 | 2,238 |

Keeping all the 2,567 B target decisions normal preserves every member of the
2,238 previously all-B-benign-normal context set. Verify these sets explicitly
against N2, then independently recheck all three original per-key floors. A
counted context concerns all its B-benign target rows, not every event/label.
Use proper context unions, never category-count sums or a target ratio alone.

The new retention rule is stricter than the original 10% floors. An exact
negative does not imply that the weaker floors have no feasible head. No
post-failure removal of retained B rows or demand that all 3,720 B rows be normal
is allowed. N2's all-target B predictions are a new study's fixed reference;
the original floor baseline remains incumbent-missing hard-by-convention.
Do not invent per-key old F5 outcomes or run the incumbent again.

## 4. Identity chain and allowed future real access

The companion frontend_inheritance_n3_input_and_evidence_pins_20260908.json
inherits the entire N2 pin chain (N1's 17 repository/seven runtime pins and N2's
18 additions), and explicitly adds the N1 cache/reference and N2 result/code
attestations needed here. Verify design/pin/evidence sidecars, all required
input hashes, selected manifest agreement and every overlapping identity.
A manifest entry alone does not authorize following its payload.

Verify historical N1 acceptance: PASS, 36 tests, two script parser checks, nine
code and seven runtime pins. Verify N2 acceptance: PASS, 43 tests, two script
checks, nine code and the same seven runtime pins. Check every attested code
file, with exact agreement on overlaps. These are provenance checks, not new
tests or permission to execute the historical programs.

Historical N1 worker/supervisor/exact/all-category summaries must establish its
single completed witness, one LP, two train passes and no new development
numeric access, 6,914 exact protections and all 8,660 training decisions correct
in actual float32. N3 adds exact constraints for the other 1,746; N1 did not.
Historical N2 worker/supervisor/measurements must establish the complete single
check: 5,206/4,323, one pass/136 batches, all 846 protected errors unchanged,
all per-key B floors passed and no fitting. No scientific status is reclassified.

Metadata access for the future N3 real stage:

- F4 context index: all five declared columns on 9,307 rows, including contiguous
  offsets, split/source and 205,470 stored events.
- F4 target audit: uid,nested_split,context_key on all 13,866 rows; event_index,
  prefix_events,source_group,owner,label,teacher_kind,device_family,attack_family,
  feature_prefix_sha256,finite,roundtrip_exact,feature_width on BOTH authorized
  original splits. Never access l1_prefix_sha256 or old_all_unk.
- P uid_scope: uid,split,context and source,owner on all 13,866 rows. F3 source
  metadata, P identities/census, named aggregate evidence and saved N1/N2 result
  metadata may be parsed. No referenced raw source or teacher payload follows.
- N1 target64_index.json: uids, original protected_uids, shape,dtype,sha256. It
  has no labels/context, so every UID must join the train F4/P metadata. Require
  original protected_uids to equal the 6,914 old protections, not the new fit set.
- N1 candidate_predictions.json: all 8,660 saved target predictions and identity
  attachments as the historical training reference; confirm all hard labels
  correct. Its original protected flag remains historical.
- N2 all_target_predictions.json: all 5,206 saved target predictions/attachments,
  to define the B retained set, fixed-N1 baseline identity and outcome comparison.
  Saved N2 measures/ranges/state/access/runtime/identity receipts are permitted.

This explicitly permits historical stored scalar outcomes, and discloses full
CSV/JSON tokenization and incidental fields separately from accessed/retained
values. Residual labels/outcomes do not enter the LP or any normalization,
candidate-selection, threshold or retry decision. Numeric head/cache containers
must be recorded as numerical inputs, not mislabeled metadata-only reads.

Never open old F1 mixed corpora, normal_2, select/viewed/report/FINAL, kill-only,
teacher vectors/probe, teacher.csv, PCAP, or raw headers. No new field/history
construction, semantic sorting, download or source reallocation occurs.

## 5. Restricted assembly and cached training vectors

Use ONE hash/receipt-verified weights-only load of the original 1,712,912-byte
resume.pt, map_location=cpu, with only numpy._core.multiarray._reconstruct,
numpy.ndarray, numpy.dtype and numpy.dtypes.UInt32DType safe globals. Temporarily
exclude ambient globals and restore them afterward. No allowlist discovery,
weights_only=False or alternative export attempt. Incompatibility stops as
N3_NEEDS_GOVERNED_MODEL_EXPORT.

Use a new N3 projection, not the old N1/N2 loader projections. Retain model,
identities, progress epoch/cursor/order/steps/stop state and selection
best_epoch/last_epoch only. Check 21/0/[]/3120/stopped, best_epoch=None,
last_epoch=20 and the saved terminal status. Do not index any epoch_ledger
entry, inspect optimizer/RNG values, restore them or instantiate an optimizer.
Full-container incidental materialization is disclosed and discarded.

Original complete model tensor hash:
131d15e7a586a6fb105995ecb25d56f8217351c03b60495c56d6e1b723db1bcc.
Non-head state including semantic_head:
29328fc616ef5b0197d1dcc8c564d89865201eb08b540d826847e233932dbe67.
Install N1's exact 260 bytes / 65 float32-LE coefficients once, without a float64
round trip, rescale, bias repair or candidate_head.json numeric source. Head SHA:
e6ac6c418253595b46308f654d339f8dfa16be971572fa282c9588c5c43f497e.
The assembled N1 full state must equal N2's before/after identity:
386ab128a57dbcb9eb284468f39fd47697b7c82bd41c84c9cd3bc0e61f28bfd8.
Seal this before raw feature decoding and keep it unchanged.

Numerically decode N1 target64.f32le ONCE: exact 2,216,960 bytes, [8660,64],
little-endian finite float32, SHA
657a77b7e68e9b9cabbd0b944e4454e67437188331f8cd47101edbc171aef35d.
Its index is strictly UID-sorted and must exactly equal all original train UIDs;
labels and context attachments come from F4/P, not array position assumptions.
The cache supplies LP inputs; do not execute a baseline training forward or
replay N1. The future candidate train forward independently checks this cache
against actual full-context pre-head values and the recorded N1 context hashes.

## 6. Prefix decoding and sole baseline extraction

Opaque-hash the full 107,666,280-byte F4 parent. Before decoding, seal the exact
role/UID/context/range attachment for both original splits. Require 33,305 train
and 172,165 development prefix events, totaling 205,470. Decode each selected
context prefix once by seek/read: offset=event_offset*524,
length=(max selected event_index+1)*524. No full-array load/memmap. These particular
prefixes collectively cover the stored parent; this is not a claim that some
parent events remain numerically unopened in N3. Preserve split-specific reads
and causal reset semantics despite that aggregate equality.

Require exact byte length, finite float32-LE values and every original target
hash SHA256(b"F4_INPUT_V1\0" + pack("<II", prefix,131) + prefix_bytes).
This is identity verification, not another F4 fieldwise/collision experiment.
Decoded input tensors may be retained for the later candidate pass; do not
decode the development prefixes twice or export raw-event/full-history caches.

Use the inherited CPU Python 3.9.13 / NumPy 2.0.2 / torch 2.8.0+cpu / SciPy 1.13.1
runtime and all seven runtime file pins. Set PYTHONHASHSEED=2705, OMP_NUM_THREADS=4,
MKL_NUM_THREADS=4, PYTHONDONTWRITEBYTECODE=1 before Python. torch intra-op=4,
interop=1, deterministic algorithms enabled. Seed 2705 is construction-only;
all parameters come from the fixed assembly. No runtime/package substitution.

Run the fixed N1 baseline on DEVELOPMENT ONLY: lexical context order, batches
32, exactly 136 batches / 4,323 contexts / 5,206 targets. Use unchanged F5 Student,
model.eval(), literal torch.no_grad(), original (-length,key) internal sort,
packed GRU, zero h0 per context, GELU approximate=none and full-context Linear
calls. Do not substitute inference_mode or target-only GEMM. Unused semantic
outputs/GRU states are calculated but never inspected, cached or fitted.

A read-only head_output pre-hook returning None captures each complete
[context_length,64] float32 matrix in actual call order. Hash full matrices,
extract selected target rows afterward and store the UID-sorted [5206,64]
development cache (1,332,736 bytes) plus its index and per-row/full-context hashes.
N2 did NOT record such pre-head hashes; these are new N3 baseline artifacts.

Require the baseline to reproduce EVERY N2 prediction, not just counts: exact
UID/context/source/family/category/label attachments, original hard decision and
float32 logit bits obtained by re-encoding the saved JSON scalar as float32-LE.
The N2 reference SHA is
b60d90206d0daf79c6a1d0b6b7c91fd8e031208dd5ba08c2fa9fe93b0706de79.
Any mismatch stops BEFORE fitting; it cannot change the retained B set.
Seal baseline predictions, caches, hashes, role/constraint order and matrix
identity before the one solve. Combining cached train and new development
vectors never combines their forward batches or context states.

## 7. One deterministic mathematical problem

Let h_i be each of the 12,711 constrained 64D float32 vectors, interpreted as
exact dyadics for independent checks. Set x_i=[h_i,1], y_i=2*label_i-1 and
A_i=y_i*x_i. Strictly order rows by UID across all three constraint roles;
columns are the original 64 feature coordinates followed by bias then gamma.

```
maximize gamma
subject to A theta >= gamma * ones(12711)
           -1 <= theta_j <= 1, j=1..65
           gamma unrestricted
```

Use scipy.optimize.linprog c=(0,...,0,-1), A_ub=[-A,ones], b_ub=0,
bounds=[(-1,1)]*65+[(None,None)]. Float64 coefficients are exact promotions of
the cached float32 values with sign and constant 1. No normalization, PCA,
weights, regularization, trust region, warm start, secondary objective or
positive externally chosen margin. This deliberately inherits N1's recipe;
the scientific change is the fixed constraint population and new fitting roles.

The original judgment remains attack q>=0 and benign q<0. On a finite set with
free bias, any exact-real threshold separator can be shifted upward by less
than its smallest benign slack and positively rescaled into the box, yielding
strict separation. This is a mathematical equivalence, NOT permission to repair
the returned candidate. theta=0,gamma=0 is feasible but misclassifies benign.
The LP is always feasible with finite optimum; a reported infeasible/unbounded
solver status is an engineering/numerical stop, not a scientific certificate.

Use installed/pinned HiGHS through SciPy, method highs-ds, exactly:
presolve=True, time_limit=600.0, maxiter=100000,
primal_feasibility_tolerance=1e-9, dual_feasibility_tolerance=1e-9,
simplex_dual_edge_weight_strategy="dantzig".
Record all warnings, status, iteration counts, raw solution and inequality
marginals. No unsupported options, method fallback or second solve. Runtime
repeatability is checked only with fixed generated fixtures during implementation;
no cross-platform solver-bitwise guarantee is claimed.

## 8. Sole candidate, exact checks and canonical acceptance

For solver status 0 or 1, use its sole length-66 solution if present and its
first 65 coefficients are finite. Cast those 65 values ONCE to float32; require finite values in the
declared box. Do not use the optimum/gamma magnitude as the hard-rule decision.
Other non-infeasible/unbounded solver failures without a usable solution give
no candidate. A timeout candidate is eligible only for the same full independent
checks; no incomplete solver result alone is a positive witness.

Check all 12,711 exact signed-affine judgments with the candidate float32 values
as dyadic rationals, using q>=0 attacks and q<0 benign. Report every exact wrong
UID, zero-margin attack tie and minimum signed/benign margin. N1's accepted
ExactBudget/rational helper recipe may be reused without calling N1 entrypoints.
One exact-positive check: at most 120 seconds, 16,384-bit stored numerator and
denominator bounds, bounded arithmetic/time checks as in section 9.

If a finite candidate exists, install its exact float32 bits once into a separate
copy of the assembled model. Seal candidate full-state/head hashes before its
first forward. Non-head state must still match the frozen hash, and baseline
N1 model state must remain unchanged. Complete BOTH canonical candidate passes
even if a scientific sign/retention gate fails early:

1. Original train: lexical order, 156 batches, 4,984 contexts, 8,660 targets.
2. Original development: lexical order, 136 batches, 4,323 contexts, 5,206 targets.

Keep the original split-specific batch boundaries. Never batch the combined
UID/context set as one stream. The same full-context pre-hook checks every train
matrix hash against N1's recorded matrices and every train target64 row bitwise
against its cache. Check development context and target64 rows against this
N3 baseline's sealed values. No target-only linear replay or float64 substitute.
Assert candidate full state unchanged afterward; no further candidate assembly.

Extract all 13,866 finite actual float32 target logits, hard decisions and signed
margins; attach all original roles and new fit roles. A primary positive witness
requires exact PASS and actual float32 PASS on all 12,711 constraints, no missing
outputs and all identity/resource checks. Additionally verify zero training
regressions, all 1,484 development protections, preservation of the exact 2,567
N2 B target UID set and exact 2,238 context set, and all original per-key floors.
Do not infer context preservation only from aggregate counts.
Preservation means set inclusion, independently per key:
historical_retained_targets <= candidate_normal_B_targets and
historical_retained_contexts <= candidate_all_B_benign_normal_contexts.
Do not require equality of the old and candidate correct sets. Additional B
targets/contexts may become normal and must be reported as new releases.

Report all category/source/family counts, context unions, errors and margin
summaries, individual six development attacks (one A/two B contexts), normal_1
A/B and other A0C, all 1,155 report-only outcomes, all-category changes versus
saved N1 training and N2 development predictions, and raw B utility. N2 supplies
complete per-UID B baselines here; do not confuse it with the unavailable old
F5 B reference. If any protection fails, usable_joint_repair is false even when
raw B floors pass. No scientific failure permits another solve or candidate.

## 9. Exact negative certificate or unknown

When no exact threshold witness was established, an optimal solver result with
inequality marginals may support ONE exact Gordan alternative check:

```
lambda >= 0
sum(lambda) = 1
A.T @ lambda = 0  # all 65 equalities exact
```

Take raw lambda_i=-ineqlin.marginals_i. Its strictly positive finite entries
define a single support S in the original frozen UID order. Empty support or
support larger than 66 is unavailable. No clipping, epsilon support threshold,
subset search or second system. Build exact C=[A_S.T;ones], d=[0,...,0,1].
Use deterministic rational elimination: columns left-to-right, first nonzero
remaining pivot row, fixed elimination order, free variables zero. Inconsistency
or a negative reconstructed coefficient fails certification. Independently
verify nonnegativity, sum one and every equality using original cached dyadics,
not only the transformed elimination matrix.

One negative-check stage: at most 120 seconds, stored numerator/denominator
16,384 bits, multiplication/addition temporaries bounded to 32,769 bits from
capped operands, checks on each reduced result/pivot/row update. Arithmetic,
rank, support or budget failure means no certificate, not nonseparability.
An exact threshold witness and exact negative certificate together indicate a
verifier integrity stop. Skip the negative branch when exact signs pass.

A verified negative excludes an exact-real affine separator of THESE fixed
cached 64D vectors under THIS conservative constraint population. Through the
finite-set bias argument it excludes the exact asymmetric threshold solution.
It does not exclude all rounding-dependent float32 decisions, a nonlinear head,
head_hidden changes, other representations, or original weaker B floors.
Without candidate replay, training representation provenance is the sealed N1
cache/identity chain, not a new live training measurement. Exact certificate
support is a sufficient conflicting set, not guaranteed minimal or a cause.
Report its UIDs/roles/source/family; do not use it to remove constraints or fit
another candidate. Near-zero optimum or solver success alone proves nothing.

## 10. Verdict precedence and claims

Priority: integrity/access/global-resource stop; otherwise exact-and-float32
joint witness; otherwise independently verified exact negative; otherwise unknown.

| Primary status | Required evidence |
|---|---|
| N3_ENGINEERING_STOP / N3_NEEDS_GOVERNED_MODEL_EXPORT | Any input/model/cache/access/runtime/baseline/count/serialization/global-limit failure |
| N3_CONSERVATIVE_JOINT_REPAIR_WITNESS | Complete exact and canonical float32 success on all 12,711 constraints, all retention/context gates and unchanged fixed representation |
| N3_EXACT_AFFINE_NONSEPARABLE | Independently verified exact Gordan certificate for this fixed conservative problem |
| N3_NUMERICAL_UNKNOWN | No accepted joint witness or valid exact negative; includes exact-stage budget limits, missing candidate/support and numerical disagreement |

Preserve the fit descriptor independently: JOINT_EXACT_FLOAT32_FIT,
EXACT_AFFINE_WITNESS_FLOAT32_REPLAY_MISMATCH, FLOAT32_ONLY_FIT or NO_VERIFIED_FIT.
An exact negative and float32-only fit can coexist because rounding changes the
function class; retain both with the narrow negative as primary. Neither alone
awards the joint research witness. Complete exact-only success prevents an
exact negative, but still earns no main positive if canonical float32 fails.

The companion same-behavior evidence contract is binding. Every status retains
broader_inheritance=NOT_PROVED, F5_eligible=false, deployment=false,
K=NOT_AUTHORIZED, new_device=NOT_EVALUATED. A witness repairs known finite data;
it neither identifies the old failure cause nor proves generalization. Existing
model-selection exposure is not erased by changing the role column.

## 11. One bounded attempt

All verification, baseline extraction, fitting, checks and sealing belong to
one exclusive real namespace, one Windows-supervised worker and these ceilings:

| Resource/action | Ceiling |
|---|---:|
| Total wall time including final seal | 1,800 seconds |
| Peak process memory, working set and commit accounted | 8 GiB |
| All new real output, including 1 MiB terminal reserve | 100 MiB |
| Restricted checkpoint loads / old N1 head decodes | 1 / 1 |
| Train cache numerical decodes | 1 (554,240 float32 values) |
| Baseline model assemblies / new candidate installations | 1 / 1 (2 total) |
| LP calls / new candidate casts | 1 / 1 |
| Exact positive / negative check stages | 1 / 1, at most 120 seconds each |
| Canonical split passes | 3 (baseline dev, candidate train, candidate dev) |
| Batches / context evaluations | 428 / 13,630 |
| Target forward evaluations | 19,072 (5,206 + 8,660 + 5,206) |
| Raw prefix events decoded | 205,470 (33,305 train + 172,165 dev), once each |
| Model event occurrences | 377,635 (172,165 + 33,305 + 172,165) |
| Padded projection slots | 3,489,280 (13,630 * 256) |
| Baseline train forwards / old-terminal forwards | 0 / 0 |
| Teacher / optimizer / backward / threshold fits | 0 / 0 / 0 / 0 |
| Alternate candidates / retries / pilots / HPC | 0 / 0 / 0 / 0 |

Candidate branches are conditional: without a finite candidate there is no
candidate installation/forward, and counts must show that explicitly. A result
without the full expected candidate counts can never earn the positive status.
Split-specific counters must disambiguate baseline and candidate evaluations,
raw decoding versus repeated forward event occurrences, and cached64 values.

Use the accepted Windows job-object pattern: one active child process,
committed-memory limit, kill-on-supervisor-exit, external wall/output polling
and cooperative checks. Do not rely on native code returning for enforcement.
Cover startup failure, gate timeout, abnormal worker exit, corrupt/incomplete
terminal receipts and resource stops. Hash all output payloads before publishing
the final supervisor verdict; sealing is within the time/output budget.
Never overwrite or restart an existing real namespace after interruption/failure.

## 12. Implementation gate and outputs

Build new N3 controller, reader, runner and tests only after implementation
authorization. Reuse inert F5 Student/runtime/hash definitions and appropriate
pure N1 math/I/O/job helpers; do not modify accepted F5/N1/N2 sources or call
their real workers, diagnose/launch, old training/evaluation or parent loaders.
N1 math helpers may be called once within N3 accounting; N1 diagnose may not.
A new minimal checkpoint projection and two-split access accounting are required.

Required generated-fixture checks: inherited/new hash and overlap drift;
UID/cache/metadata joining, both-split payloads and forbidden-field sentinels;
original protected versus new fitting roles; outcome-informed B membership
frozen from old predictions, baseline mismatch cannot reselection; full source
and category conservation; cache and selected prefix bit/range/finite checks;
strict safe-global load and zero ledger-value access; JSON float32 logit bit
comparison; no-grad/full-context hook order and original per-split batching;
unchanged pre-head vectors and baseline/candidate parameter identity; exact
attack-zero/benign-zero rules; separable/nonseparable/tiny-positive-margin
fixtures; fixed small-fixture solver repeatability without candidate selection;
timeout partial candidate, false infeasible/unbounded reports; float32-only/
exact-only/negative precedence; certificate corruption, support/rank/bit/time
limits; B retained target/context unions and original floors; complete report-only
outcomes; no second solve/fit/retry; controller startup/abnormal-exit/output/wall/
memory/partial-result stops and provisional/final status seals.

No historical real numeric fixtures, historical test reruns or resource pilot.
Seal all N3 code/test/runtime hashes, exact test/parser receipts and protocol
sidecars before real authorization. The runtime is inherited, not reselected.

Suggested exclusive namespaces:
runs/frontend_inheritance_n3_implementation_v1_20260908/ and
runs/frontend_inheritance_n3_conservative_joint_repair_v1_20260908/.
Output identities/runtime/access receipts; original/new roles and input ranges;
cache references and new dev64/index/full-context hashes; baseline identity and
predictions; constraint UID/label/matrix identity and sole LP result; sole head
bytes with NOT_DEPLOYMENT/NOT_F5_ELIGIBLE markings; exact check/certificate;
candidate before/after hashes and all 13,866 predictions; complete retention/B/
source/family/report-only outcomes; resources and worker/supervisor terminal
receipts with SHA256SUMS. No deployment checkpoint or raw-event cache is exported.
The viewer verifies the final seal and marks earlier receipts provisional.

## 13. Evidence contract and design review

Read frontend_inheritance_n3_same_behavior_evidence_contract_20260908.md and its
sidecar with this protocol. Same-behavior, all-component fit exclusion and
dependency/exposure evidence is still missing; N3 does not solve that by reusing
development as fitting. No outside reserve is opened here.

Prepared from source, existing protocols and named historical manifests,
identity/acceptance and aggregate result metadata. No tensor, feature/head byte
decoding, model construction/forward, synthetic run or LP occurred in design.
Three parallel read-only reviews covered mathematical certification, input/
runtime identity and scientific evidence/authority. They found no blocking
issue in the final draft. All requested B-subset preservation wording is now
explicit; newly released targets/contexts are allowed. The candidate-finiteness
wording matches the inherited 65-coefficient rule and does not gate on gamma.

Static verification reconciled all 57 effective input pin names, seven named
historical manifest hashes and 39 selected manifest entries without opening
their numeric payloads. It verified 16 distinct historical code files and seven
runtime file hashes, plus the two historical implementation receipts and pin
overlaps. These are source/identity checks, not synthetic or scientific tests.

The protocol, input pin bundle and separate evidence contract each have a
SHA-256 sidecar. No N3 implementation/real namespace exists yet. Next is separate
implementation and synthetic acceptance authorization, followed by separate
authorization for the one real development-fitting attempt. All current
changes are local documents; old frozen artifacts and unrelated modifications
remain unchanged. No commit or push is claimed. N1/N2 stay permanently closed.
