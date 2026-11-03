# N1 fixed-terminal last-layer feasibility protocol

Date: 2026-09-08. Status: `FROZEN_DESIGN_IMPLEMENTATION_AND_REAL_EXECUTION_NOT_AUTHORIZED`.
Base: codex/exp-mainline, 4b28747b09480471e2bac1beb3a9badf27280efb.
The user authorized the next design and review. Implementation/synthetic tests
and the real parameter-fitting attempt require their subsequent authorization.
No model forward, checkpoint tensor loading, numeric feature decoding or solver
execution occurred in this design.

## 1. Question, fixed object and decision value

Can one existing `Linear(64,1)` head satisfy all predefined protected training
decisions on the **fixed terminal 64D last-layer inputs**, under the original
float32 decision rule? These inputs are GELU(head_hidden(GRU(...))), not the
128D GRU state and not old E3 representations.

Fix the terminal event projection, both GELUs, GRU, head_hidden and semantic_head
exactly. Change only the 64 head_output weights and its bias in a separate
diagnostic copy. Retain one shared A+B model and the original input/context
rules. Old E3/P2 is not a deployment head for this representation and is not
called in N1. The failed F5, original incumbent and all frozen artifacts remain
untouched. A witness cannot become an eligible F5 checkpoint or enter K.

One bounded solve is the restoration procedure; it needs no feasible starting
head and promises nothing about intermediate solver states or future updates.
This trial addresses finite-set joint decisions. ToN-normal coverage, holdout
inheritance, B utility, device commissioning and OOD remain separate questions.

## 2. Immutable target set

Membership is fully determined by pinned F4/P files and their literal `train`
selector, not by losses, margins or the five final failures. Preserve 8,660
training targets in 4,984 contexts from the original 13 training sources.

| Category | Targets | Use |
|---|---:|---|
| A1C: A attacks | 2,179 | Positive constraints |
| A0C: old-correct A benign | 4,667 | Negative constraints |
| B1N: B attacks | 68 | Positive constraints |
| A0W: old-wrong A benign | 24 | Accompanying outcome accounting |
| B0N: B benign | 1,722 | Accompanying outcome accounting |

Thus 6,914 constrained targets and 1,746 accompanying targets; no weighting,
duplication, subsampling or post-result removal. Protection equals the original
F5 rule `label == 1 or (owner == A and teacher_correct)`. Teacher correctness
comes from frozen categorical teacher_kind; teacher strengths are unnecessary.
Report baseline/candidate errors, newly wrong and newly correct UIDs for all
five categories, including the accompanying rows. Their outcomes cannot choose
the candidate or silently create a new acceptance gate after the solve.

## 3. Input identity and access

The companion `frontend_inheritance_n1_input_and_runtime_pins_20260908.json`
lists exact repository inputs and runtime file identities. Verify its own
sidecar, every required pin, manifest agreement, checkpoint receipt and terminal
state before the corresponding numeric access. Never follow unrelated members
of F4/F5 manifests into other artifacts. F5 source is reusable as an inert
model definition; historical launchers, load_parent, load_preflight,
load_checkpoint, training loops and F4 encoding/decoding routines are forbidden.

Metadata projection is explicit:

- F4 context index: its five declared columns may be read for all 9,307 rows
  to check source/split membership, contiguous offsets and 205,470 total events.
- F4 target audit: `uid,nested_split,context_key` are selector columns for all
  13,866 rows. Only train rows expose event_index, prefix_events, source_group,
  owner, label, teacher_kind, device_family, attack_family, feature_prefix_sha256,
  finite, roundtrip_exact and feature_width. Do not use other prefix statistics.
- P uid_scope: `uid,split,context` may be read for all 13,866 rows; source/owner
  are projected only for train. Its train set must equal the F4 train set.
- P/F3 JSON identities and source lists, P census and N0 summary may be parsed;
  use their training/source/identity counts, not validation outcomes.

CSV/JSON parsers can transiently materialize the full mixed metadata container.
Record that fact, selector accesses and retained payload separately. No new
validation feature, logit, score, loss or decision may be computed or used.
No old F1 mixed table or source, normal_1/normal_2, select, viewed/report, FINAL,
kill-only, PCAP, old teacher vectors/probe or teacher.csv is an N1 numeric input.

For F4 `f4_parent_features.f32le`, verify the whole 107,666,280-byte file by
opaque SHA-256 without interpreting its validation bytes. Numerically decode
only each train context's required prefix by seek/read:

```
offset_bytes = event_offset * 131 * 4
length_bytes = (max_train_target_event_index + 1) * 131 * 4
```

Use little-endian float32, require finite values and exact length, and never
load or memmap the whole parent as an array. Before numeric access, seal the
UID/context/range attachment and exact selected event count from pinned
metadata; the latter is bounded above by 205,470. This derives existing
membership; it does not make a new split. Verify each train target's existing
feature-prefix identity:
`SHA256(b"F4_INPUT_V1\0" + pack("<II", prefix_length,131) + prefix_f32le_C_bytes)`.
This is identity verification, not a repeated F4 field or collision experiment.

The terminal resume.pt is a full 1,712,912-byte checkpoint container, not a
model-only file. It includes optimizer tensors, RNG and historical validation
ledger entries. Use only a synthetic-verified restricted
`torch.load(..., map_location="cpu", weights_only=True)` with a literal
safe-global allowlist for its NumPy uint32 RNG serialization:
`numpy._core.multiarray._reconstruct`, `numpy.ndarray`, `numpy.dtype`, and
`numpy.dtypes.UInt32DType`. No custom/general pickle or automatic fallback to
weights_only=False. An incompatible serialized type stops as
`N1_NEEDS_GOVERNED_MODEL_EXPORT`; do not discover-and-allow arbitrary classes.

Full-container deserialization incidentally materializes optimizer/RNG and old
validation entries; future real-stage authorization must include this limited
container access. Do not inspect/use those incidental values. Retain only model,
identities and the final training reference: progress epoch/cursor/order/steps/
stop state, final epoch number, train_violations and train-prefixed gate_counts.
Do not instantiate/restore an optimizer or restore saved RNG. Check terminal
20 epochs/3,120 steps/no selected epoch, and final ledger epoch 20. Drop unused
deserialized content promptly and account for it honestly in the access receipt.

## 4. Canonical baseline and feature capture

Use the pinned Python 3.9.13 / NumPy 2.0.2 / torch 2.8.0+cpu runtime, CPU float32,
PYTHONHASHSEED=2705, OMP_NUM_THREADS=4, MKL_NUM_THREADS=4, torch intra-op=4 and
interop=1, deterministic algorithms enabled. Seed 2705 is construction-only;
all parameters are overwritten by the strictly loaded terminal state. No seed
candidate or initialization is trained.

Contexts are sorted lexically by context_key and batched 32, exactly 156 batches.
Each prefix ends at its last train target. Preserve the original forward's
batch-internal sort by (-length,key), packed GRU, per-context zero h0, and GELU
approximate="none". Run model.eval() under literal torch.no_grad(), matching
F5 evaluate; do not substitute inference_mode().
The unchanged forward also calculates its unused semantic output; do not inspect
that output or compute training losses/teacher terms.

Install a read-only head_output pre-hook returning None. Associate each call
with the source-defined sorted context order, and capture its full per-context
64D input. Preserve the actual full-context head invocation and logits. Extract
target rows only afterward. Store 8,660 x 64 float32 target features and a hash
of the complete 64D matrix per context, not all event matrices on disk.

This one baseline pass both reproduces the reference and supplies the LP input.
Require exact UID equality and baseline protected-violation set equality to the
saved final training ledger: five A1C failures, zero A0C/B1N failures. A mismatch
stops before solving; no alternate batching/runtime attempt is allowed.
Record all baseline decisions and model tensor identities. Form all row orders
by lexically sorted UID; persist that order and hashes before the solver.

## 5. One mathematical problem

For protected target i, let h_i be its cached 64D float32 vector, interpreted
exactly as a dyadic rational when verifying a certificate. Let x_i=[h_i,1],
y_i=+1 for attacks and -1 for protected benign, A_i=y_i*x_i^T, and theta=(w,b).
Solve a single maximum normalized margin linear program:

```
maximize gamma
subject to A theta >= gamma * ones(6914)
           -1 <= theta_j <= 1, j=1..65
           gamma unrestricted
```

For scipy.optimize.linprog use c=(0,...,0,-1), A_ub=[-A,ones], b_ub=0 and
bounds=[(-1,1)]*65+[(None,None)]. All solver coefficients are float64 promoted
from the exact cached float32 values. There is no feature normalizer, PCA,
label weighting, regularization, trust-region distance, secondary objective,
positive target margin, solver warm start or bias correction.

The box fixes scale; it does not exclude an exact-real affine separator. Any
finite separator can be positively rescaled into this box. The original rule
is attack q>=0 and benign q<0. On this finite set with free bias, a threshold
separator can be shifted upward by less than its smallest benign slack, then
rescaled, yielding a strict separator. This is an equivalence proof, not an
allowed post-solve modification of the returned candidate. In particular,
theta=0,gamma=0 is LP-feasible but does not classify benign correctly.

The LP is always feasible and has finite optimum. A solver report of infeasible
or unbounded is a numerical/engineering stop, not a scientific negative result.

## 6. Solver and finite budget

Use installed SciPy 1.13.1 and its pinned bundled HiGHS binary, method
`highs-ds`. The exact bundled semantic version is not guessed from the SciPy
version; binary hashes identify it. Set only these documented options:

```
presolve=True
time_limit=600.0
maxiter=100000
primal_feasibility_tolerance=1e-9
dual_feasibility_tolerance=1e-9
simplex_dual_edge_weight_strategy="dantzig"
```

No unsupported forwarded options, solver-method fallback, alternate tolerance,
bound, objective or repeated solve. The pinned dual-simplex implementation and
fixed row/column order are the numerical recipe. Thread settings do not claim
cross-platform bitwise solver determinism; the implementation gate must verify
repeatability on fixed small synthetic fixtures in this exact runtime. Record
the effective method/options and all solver warnings/status/iteration counts.

The separately authorized real attempt has these ceilings, including extraction,
solve, certificate work, verification and sealing:

| Resource/action | Limit |
|---|---:|
| Local worker processes | 1, no parallel candidates or jobs |
| Total wall clock | 1,800 seconds |
| Process peak memory | 8 GiB |
| Total new output including receipts | 100 MiB |
| Real LP calls | 1 |
| Baseline/candidate canonical forwards | At most 2 passes / 312 batches |
| Train target evaluations | At most 17,320 |
| Context evaluations | At most 9,968 |
| Unpadded authorized input-event occurrences | At most 410,940 |
| Padded event-projection slots | At most 2,551,808 = 2 * 4,984 * 256 |
| Exact candidate sign-check stage | 120 seconds |
| Exact dual-certificate stage | 120 seconds / one support system |
| Backward / optimizer steps / teacher forwards | 0 / 0 / 0 |

Parameter fitting still occurs despite zero optimizer steps. Solver/exact-stage
caps are included in the total, not extra time. Check time/memory at bounded
steps; reserve output capacity for stop receipts. If native code cannot obey the
wall limit, an external non-worker watchdog may terminate it at the total cap
and seal an engineering-stop receipt; it cannot restart the attempt. The exact
budget enforcement and runtime attestations must pass the implementation gate.
No real resource pilot, retry, PCAP decoding, download or HPC.

## 7. Independent positive verification

Consider only the one finite coefficient vector returned by solver status 0
(optimal) or 1 (time/iteration limit). Optimality is not needed to prove existence.
If no finite vector exists, skip candidate verification. Cast its 65 coefficients
once to float32; require finite values in [-1,1]. Never clip, renormalize, shift
the bias, round by another convention, or seek a second candidate.

Independently compute exact logits of the cast coefficients on the cached
float32 protected features, using exact dyadic/rational arithmetic. Test the
original asymmetric hard rule, not a tolerance: attacks >=0, benign <0.
Record minimum signed margin, minimum benign slack and zero-margin attack ties.
An attack at exact zero can still be a legitimate threshold witness; do not
call it rounding-dependent just because the minimum signed margin is zero.

Run the original model forward once more on the same full train contexts,
changing only head_output in a separate in-memory model state. Require all
non-head parameter hashes unchanged and every complete pre-head context-matrix
hash identical to baseline. This verifies that the fixed representation and
batching were preserved. Do not substitute a target-only GEMM for actual
full-context Linear evaluation. Require all 6,914 protected actual float32
judgments correct under q>=0, and report outcomes for all 8,660 rows.

Award the main positive witness only when both exact threshold judgments and
actual float32 judgments pass. If float32 alone fits, retain the descriptor
FLOAT32_ONLY_FIT: it earns no main positive witness, and the primary outcome
is numerical unknown unless section 8 independently verifies an exact-affine
negative certificate. If exact arithmetic alone fits, record
EXACT_AFFINE_WITNESS_FLOAT32_REPLAY_MISMATCH and numerical unknown; the verified
exact threshold witness precludes the negative-certificate branch. Neither
case permits a candidate repair or new parameter solve. A passed witness proves only this finite-set
joint decision property, not perturbation robustness, temporal retention or
causal attribution of F5's failure.

## 8. Exact negative certificate, or unknown

A near-zero optimum, small residual, solver success or time limit is not a
nonseparability certificate. When the sole candidate has not established an
exact threshold witness, and an optimal solver result supplies inequality
marginals, one bounded exact check
may attempt Gordan's alternative:

```
lambda >= 0
sum(lambda) = 1
A.T @ lambda = 0    (every equality exact)
```

SciPy minimizes -gamma, so take raw lambda_i=-ineqlin.marginals_i. Use its
strictly positive finite entries only to define support S in frozen UID order.
If support is empty or exceeds 66 entries, certificate status is unavailable.
Do not clip negatives into a certificate or threshold small positive entries.
Do not search subsets or require approximate KKT as a precondition for an exact
certificate that can be checked independently.

Build the exact 66 x |S| system C=[A_S.T;ones] and d=[0,...,0,1]. Solve once by
deterministic rational elimination: columns left-to-right, first nonzero remaining
row as pivot, fixed elimination order, and nonpivot variables set to zero.
Inconsistency or a reconstructed negative coefficient fails the certificate.
Independently verify nonnegativity, exact sum one and all 65 equalities using
the original cached dyadics, not just the transformed elimination matrix.

Use fractions.Fraction/as_integer_ratio or equivalent exact integer dyadics.
Cap each stored numerator and denominator at 16,384 bits; bound multiplication/
addition temporaries to at most 32,769 bits from capped operands, check reduced
results, and check time at each pivot/row update. These are computational stop
rules only. Rank issues, budget exhaustion or failure to reconstruct produce
UNKNOWN, never a mathematical negative result. No second support system.

A verified certificate excludes an **exact-real affine separator of these
fixed cached terminal 64D values**. By the finite-set bias argument, it also
excludes the exact asymmetric threshold solution. It does not exclude every
rounding-dependent float32 classifier, the existing trainable head_hidden,
the 128D GRU states, another encoder state or the shared-model family. If an
exact threshold witness and an exact negative certificate ever coexist, stop
as a verifier integrity failure.

## 9. Verdicts and next-decision consequences

| Verdict | Evidence | Consequence, never automatic execution |
|---|---|---|
| N1_JOINT_HEAD_WITNESS | Exact original hard-rule checks and all protected float32 checks pass; backbone identity unchanged | Design restoration/retention from this separately stored witness, with full-set guards; address coverage/holdout separately |
| N1_EXACT_AFFINE_NONSEPARABLE | Independently verified exact certificate | Close this terminal exact-affine final-layer repair; justify one preceding-layer/representation question before any new learning |
| N1_NUMERICAL_UNKNOWN | No accepted witness or exact negative certificate; includes timeout, near-zero, missing support or arithmetic/replay uncertainty | End N1; report exact limits. No automatic repeat, looser margin, new solver or new candidate |
| N1_ENGINEERING_STOP / N1_NEEDS_GOVERNED_MODEL_EXPORT | Identity, access, baseline, runtime, serialization or global resource gate fails | No scientific verdict; document the concrete blocker without a real-data retry |

Outcome precedence is explicit: integrity/access/global-resource stop first;
otherwise a jointly verified exact/float32 witness; otherwise an independently
verified exact negative certificate; otherwise numerical unknown. Exact-affine
nonseparability and FLOAT32_ONLY_FIT can coexist. Preserve both in that case,
with N1_EXACT_AFFINE_NONSEPARABLE as the primary narrow mathematical result;
do not claim that the observed float32 fit did not occur or is impossible.

No result means F5 eligible, inheritance PASS, solved ToN coverage, B utility,
new-device/OOD success, or permission to use validation, K or deployment.
Do not let N1 become an expanding series of head searches. A further study must
state what new question it answers and why the N1 evidence warrants it.

## 10. Implementation gate, artifacts and authority

The next implementation stage may build only this protocol and synthetic tests
after authorization. Required tests must cover: mixed-row access sentinels;
wrong hashes/ranges/UID joins; all five category counts; context-order/hook and
full-matrix hash preservation; safe checkpoint loader including forbidden
globals; attack-zero/benign-zero asymmetry; known separable and nonseparable
fixtures, including a tiny positive margin below solver tolerance; incorrect
solver infeasible/unbounded reports; timeout/partial candidate; float32-only
versus exact-only outcomes and certificate/outcome precedence;
exact certificate corruption/support/rank/bit/time stops; no retries; and
wall/memory/output enforcement. Test repeated fixed synthetic LPs solely for
runtime repeatability, not performance selection. No historical resource pilot
or real model/feature fixture is permitted during implementation acceptance.
The synthetic checkpoint must reproduce the source's JSON roundtrip of P
identities before T serialization, including plain version strings and the
NumPy uint32 RNG state. Do not expand the safe-global allowlist to compensate
for a synthetic fixture that serializes a different Python object type.

Seal implementation/test/runtime hashes, the exact synthetic acceptance receipt
and this scientific protocol before requesting real N1 authorization. Newly
created code identities are implementation attestations; they cannot change
the mathematical problem or outcome rules. Runtime incompatibility or a needed
scientific change returns for review; no silent package upgrades or rule edits.

Use exclusive new namespaces such as
`runs/frontend_inheritance_n1_implementation_v1_20260908/` and
`runs/frontend_inheritance_n1_fixed_terminal_head_v1_20260908/`.
The real namespace must not already exist; never restart a completed/failed
attempt or overwrite original artifacts. Output the derived train UID/range
attachment, input/code/runtime/access receipts, baseline predictions and hashes,
target64 features and full-context hashes, LP problem/status/sole candidate,
exact certificate and verification where available, all-row candidate outcomes,
resource/terminal verdict and SHA256SUMS. The candidate is a diagnostic head
artifact with NOT_DEPLOYMENT/NOT_F5_ELIGIBLE markings, not a replacement resume.pt.
No deployment checkpoint, hidden second solve or downstream launcher is produced.

Source anchors: F5 core Student :100, per-context head :131, hard rule :372,
checkpoint container :441; F5 runner train loading :264 and epoch ledger :575;
F4 prefix identity :477; N0 result and source inventory dated 2026-09-07.
The design and subsequent local reports are not claimed committed or pushed.

## 11. Design freeze and review record

The authorized design/review stage is complete. Three independent read-only
reviews covered input/runtime access, the mathematical decision procedure and
scientific scope. Final review found no remaining blocking design findings.
Corrections incorporated before freeze include literal torch.no_grad(), padded
versus unpadded work accounting, checkpoint-fixture JSON roundtrip fidelity,
and explicit exact/float32 outcome and certificate precedence. Synthetic cases
listed above are implementation requirements; none was executed in this stage.

The companion input/runtime JSON and this document each have a SHA-256 sidecar.
These sidecars seal the design and recorded pins, not a new verification of
real numeric inputs or scientific success. Next is separately authorized
implementation with synthetic acceptance, followed by separate authorization
for the single real parameter-fitting attempt. No permission to proceed to
either stage is implied by this freeze, and no N1 numeric result exists yet.
