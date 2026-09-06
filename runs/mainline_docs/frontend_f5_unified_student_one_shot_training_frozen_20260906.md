# Frontend-F5: fieldwise unified student, one-shot training FROZEN

Date: 2026-09-06

Status: `FROZEN_IMPLEMENTATION_AND_SYNTHETIC_ONLY_AUTHORIZED`

Design base checkout: `9023e39`; accepted draft commit: `6f9e0d0`.
The user authorized mechanical freezing, implementation, synthetic contract
tests and the synthetic resource pilot on 2026-09-06. Synthetic model
construction is authorized. Real teacher materialization, real student input
opens, real training and real evaluation remain NOT_AUTHORIZED. The model
used for implementation is the user's current selection; no Sol handoff is
required. This freeze changes status/provenance only, not scientific rules.

## 1. Decision and experimental question

Test one small shared sequence encoder **and its own small student head** on
the fixed F4 inputs. Both A (incumbent-finite) and B (incumbent-missing) use the
same student computation. A/B identity is used in loss accounting and audits,
never as an input, router, adapter selector, or inference-time arbitration.

The old P2 supplies label-aware continuous teacher evidence on nested-train A
only. Its classifier and normalizer are not the student's inference interface.
There is no 768D coordinate imitation, frozen-P2 compatibility arm, second
encoder, alternative head, teacher at inference, or model fallback in F5.

The question is whether this **one realization** can retain the incumbent's
correct decisions in the permitted development universe while releasing a
nontrivial proportion of B benign targets. Its candidate is evaluated in
shadow; incumbent deployment remains unchanged. No output here changes CE.

Scientific differences from F1 are declared together: invertible fieldwise
input, a jointly trained student head, continuous one-sided teacher targets,
and explicit rare-attack protection. A successful run cannot attribute its
gain to any one of these changes without a later controlled ablation.

F1 remains rejected; F2's coarse-input contradiction and F3's whole-signature
UNK failure remain valid within their scopes. F4 PASS establishes input
preservation, not attack inheritance. No existing FROZEN contract is edited.

One real optimizer trajectory, one seed, no performance-driven restart or
resplit. A completed scientific failure closes this F5 realization. Replacing
a scientific failure with a new name, weight, checkpoint, or seed is forbidden.
Failure does not prove that every unified model is impossible.

## 2. Evidence and access stages

Paths are relative to
`D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline`.

| Stage | Allowed after the applicable authorization | Must remain closed |
|---|---|---|
| D: present design | Existing protocols, code as text, saved F4 metadata/counts and hashes | Real teacher values, model construction, optimization |
| I: future implementation | Code, synthetic fixtures, synthetic models/tests/resource pilot | All real feature tensors and real models/scores |
| P: future run preflight | F4 parent inputs/metadata; narrowly selected nested-train A teacher materialization; runtime and identity checks | Numeric teacher representations for nested-validation/B/other roles; kill-only inputs |
| T: future single training | Nested-train features/labels/teacher; nested-validation features/labels for prescribed epoch checks | Select, original F1 outer-validation corpus, kill-only features, report, FINAL |
| K: fixed-checkpoint rejection test | The separately stored five exposed attack inputs, once, after checkpoint hashing | Any new training, checkpoint replacement, or threshold choice |

I requires implementation authorization. P/T/K are proposed as one bounded
future run authorization: the user need not approve individual epochs. They
do not run under present design authorization. Unvisited stages stay
`NOT_EVALUATED`. Failure in P or T cannot open K.

Metadata containers physically include owner, label, source, and teacher-kind.
Report that access honestly; only the 131 numeric F4 coordinates reach the
model. No PCAP replay, new packet fields, network download, new dataset, HPC,
old learned-student checkpoint, or raw endpoint value is needed.

### 2.1 F4 byte identities

Common prefix `P4 = runs/frontend_f4_fieldwise_input_feasibility_v1_20260905/`.

| File | SHA-256 |
|---|---|
| `runs/mainline_docs/frontend_f4_fieldwise_input_feasibility_frozen_20260905.md` | `6c5408d2437cf53aafefad6b68dd7932ffefe9309004b9a4ee673cc8f3ffc8dd` |
| `P4/SHA256SUMS` | `432c03f543e3dc9c2bdc97cc9842e53fb846e4cf62f92fb5642b2896855d4df5` |
| `P4/f4_verdict.json` | `b99396b73dff27270766f48c7280dc91c3becd4f55acda8efac7e93071692c38` |
| `P4/f4_schema.json` | `5d66120b8f1b224bdcb66ff46ae6923641d923cb1eee4554a6c8bf80179c3681` |
| `P4/f4_parent_features.f32le` | `5c4b20abcca4b192f91c6094eda370fb3c5e977c8106a69f713aa059f93b450d` |
| `P4/f4_context_index.csv` | `c62d9fb84db7edf6eaa733fcb5ac72b928f3c783db9f2549afa81a3a77700444` |
| `P4/f4_target_audit.csv.gz` | `fa4cb5efa3af5cc65cafc562c7c5e3d71aa2416910edd213ef5535f0a2da7c51` |
| `P4/f4_nested_split_census.csv` | `76da23f4ed27bea017ec3f3f36648ad730bc6e86df2246abb5435541217707da` |
| `P4/f4_coverage.csv` | `75a0b43100f178504e144a8b42e72840447b0aa55e040b55d01730c02d4f33a9` |
| `P4/f4_kill_only_features.f32le` | `e68625d0bd0ce0b0652b19a504ccc87bc467018665d469ac104466ad146876a5` |
| `P4/f4_kill_only_index.csv` | `6ca2967cc6d67e360e19608a55ca2b33e8d5f92f63dae8b82223606d9f4ea5d6` |
| `P4/f4_kill_only_audit.csv` | `f9d4585116c7b592445016a63df182911d7d249db491fa316eadfc834c00f2ca` |
| `runs/frontend_f3_full_fit_l1_identifiability_v1_20260905/f3b_identities.json` | `073b28f5f3617d8c2c1ff0fd919cd02116b961d35ccc7ea5de6e7581d03f2b09` |

Read `P4/...` as the named prefix plus filename, not a second slash or a
directory literally named P4. Verify all listed bytes before numeric access;
hashing opaque kill-only bytes is allowed in P, numeric parsing is not.

### 2.2 Teacher-only identities

Common prefix `PT = runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/`.

| File | SHA-256 |
|---|---|
| `PT/ckda_d1_fit_select_embeddings.npz` | `b1b4f2fde168a69e0cf7a53aaede2ddef9bd6d92b0ce58e56a9d6fcde37b6099` |
| `PT/ckda_d1_probe_state.npz` | `50a9bcfc18287d51bf8afda7367b57decdf3179dd41fc3aa61399d4098360c38` |
| `PT/ckda_d1_threshold_freeze_marker.json` | `84576a5008259f4381c46eecbc3ee3bda9d06b9dc7068cd52d7c2232e884dd5b` |
| `runs/mainline_docs/frontend_f2_old_function_preservation_d0_numeric_semantics_erratum_frozen_20260904.md` | `c573ef26df6bf559b5c4006d0a0aa284c760a600294f059d1a0b102c1e997e49` |
| `repo/ood/issue27ckda_d1_representation_probe_v1.py` | `f8f477ca78d8ed1fa490880d24a01f65111e3f910eaa8ab72af154d8a143de4e` |
| `repo/ood/issue27frontend_f1_d1_train_v1.py` | `6e2df7059b9bb0aba9be80adb11e7e918c3f1ddfef3ecc690b571b0f0af18634` |

The source files are provenance, not launchers to import. F2 helpers have
hard-coded 8,353-row assumptions and cannot be reused unchanged for F5's
6,870-row teacher scope. Implement a shape-parameterized pure evaluator under
the same numerical semantics and synthetic tests.

## 3. Immutable data topology and claim ceiling

Use all 13,866 F4 parent targets in 9,307 contexts, exactly as stored:

| Split | A correct attack | A correct benign | A teacher-wrong benign | B attack | B benign | Targets / contexts |
|---|---:|---:|---:|---:|---:|---:|
| Nested train | 2,179 | 4,667 | 24 | 68 | 1,722 | 8,660 / 4,984 |
| Nested development validation | 3 | 1,478 | 2 | 3 | 3,720 | 5,206 / 4,323 |

Teacher-kind values and category definitions are copied from F4 section 3.
No A wrong-attack category is present; a disagreement is an identity failure.
Context counts across target categories may overlap. Compute each eligible
context union from the table, not by summing category context counts.

All 13 nested-train sources and four nested-validation sources are copied from
the pinned F3 identity file; no hash re-sort or source reassignment. The
validation sources remain:

```text
iotsim-combined-cycle-6_0-0_to_OpenvSwitch-13_6-0
iotsim-domotic-monitor-3_0-0_to_OpenvSwitch-23_3-0
normal_1.pcap
processed/iotsim-combined-cycle-10.csv
```

The original 19 fit/select-crossing contexts remain excluded by inherited UID
membership. All original F1 outer-validation targets remain outside this
parent, except the five separately stored exposed kill-only targets. No
refitting on train+validation after checkpoint selection is permitted.

**This is exposed development evidence.** A validation attack support is one
context / three targets; B support is two contexts / three targets. Several
earlier designs have already used properties of these inputs. Passing them
cannot certify general A inheritance, B family detection, new-device
generalization, or a population risk bound. Epoch selection further makes
them development gates, never a final test.

Counts must be reported as targets, distinct semantic contexts, source groups,
and exact family/device keys. Context IDs are the sampling unit used by this
protocol; their counts are not a claim of statistical independence between
contexts from a common device or capture.

Only the nested-training part of legal A-fit supplies gradient teacher targets.
“Use all A-fit evidence” does not authorize putting validation rows into loss.

## 4. Fixed input and causal execution

Read the existing little-endian float32 `[205470,131]` parent binary with the
saved context offsets. Width, ordered fields, missing/presence bits, UInt32
limbs, and log coordinates are unchanged. No learned vocabulary, UNK, fitted
input standardizer, feature selection, clipping, or additional packet field.

For each target at index j use `h[j]` after events `0..j`, starting with a zero
hidden state for that context. Never use the last full-context state for an
earlier target. Contexts are processed separately; source/UID/context-key and
length sorting are batch logistics only. Right padding is excluded through
packed sequences with fixed length-descending/context-key tie order and
restored output order. No bidirectional computation or state carried between
contexts. Use valid events only for auxiliary losses; no successor outside
the last authorized training target's prefix. Trailing saved events, if any,
are preserved in the input artifact but not consumed for fitting.

Raw IP/MAC values, endpoint ordinal tokens, and port values are already absent.
An endpoint-masked input is therefore byte-identical by construction. Verify
that identity, but do not describe it as empirical absence of device leakage:
protocol, lengths, timing bins, and presence patterns may still identify sources.

## 5. Sole model and threshold

Construct modules in this exact order, with PyTorch 2.8.0 CPU default parameter
initialization after the seed setup in section 8:

```text
event_projection = Linear(131,64,bias=True)
event_activation = GELU(approximate="none")
encoder = GRU(64,128,num_layers=1,bias=True,batch_first=True,
              dropout=0.0,bidirectional=False)
head_hidden = Linear(128,64,bias=True)
head_activation = GELU(approximate="none")
head_output = Linear(64,1,bias=True)
semantic_head = Linear(128,27,bias=True)  # training auxiliary only
```

Student logit `q_i = head_output(GELU(head_hidden(h[j])))`.
The sole decision is `q_i >= 0` => hard; reporting score is `sigmoid(q_i)`.
Compute decisions from the raw logit, not a rounded displayed probability.
Score is not claimed to be a calibrated probability. There is no threshold
fitting, device threshold, quantile calibration, or old-P2 forward at inference.

Parameter counts: event projection 8,448; GRU 74,496; head 8,321;
inference total 91,265; auxiliary 3,483; training total 94,748. The representation
is 128D, not padded to 768D. Changing widths is a new design, not engineering.

No feature-clone arm or frozen-P2 arm is added. Joint head training addresses
the interface constraint; it does not itself guarantee retention.

## 6. Teacher materialization, before the first optimizer step

Authorize exactly the 6,870 nested-train A UIDs: 2,179 attacks, 4,667
teacher-correct benign, 24 teacher-wrong benign. Validate unique UID mapping
using the NPZ UID/missing arrays. Every selected representation has missing=false.

Stream `representation.npy` as fixed-width opaque rows; numerically decode only
the 6,870 allowlisted rows. Full matrix shape is `[25467,768]`, float32,
C-contiguous. Never instantiate the full representation matrix. B, nested
validation, and the original outer validation are not decoded numerically.
Do not unpack the whole probe container: numeric keys are limited to
`normalizer_mean`, `normalizer_scale`, `p2__0.weight`, `p2__0.bias`,
`p2__3.weight`, `p2__3.bias`; other NPZ members stay opaque.

Canonical teacher follows the F2 numeric erratum:

```text
u64 = (representation.astype(float64) - mean64) / scale64
x32 = concatenate(u64, missing=0).astype(float32)
z_old = Linear(ReLU(Linear(x32, old_layer1)), old_layer2)  # float32
p_old = torch.sigmoid(z_old)                            # float32
theta_old = 0.065159872174263
z0_old = -2.6635317063752599
old_hard = p_old.numpy().astype(float64) >= theta_old
```

Use one full 6,870-row teacher batch, UID-sorted, in inference mode and with
the recorded CPU runtime. Persist raw pre-sigmoid logits; never reconstruct
logits from rounded or saturated probabilities. Widen the float32 sigmoid
outputs to float64 before threshold comparison, matching formal
`apply_threshold`; do not round the threshold to float32. All logits must be finite;
teacher hard labels must match every frozen `teacher_kind`. Drift stops P as
`F5_TEACHER_IDENTITY_OR_NUMERICAL_FAILURE`, not an invitation to revise labels.

For correct A rows, let `s_i=2*y_i-1` and compute in float64:

```text
teacher_strength_i = clip(s_i * (float(z_old_i) - z0_old), 0.0, 6.0)
```

Store that value as float32 for training after serializing the raw value and
clipping status. Constants 0 and 6 are fixed before these scores are opened;
no quantile-derived hyperparameter or inspection-driven weight is needed.
Score/logit boundary-rounding can produce a tiny negative margin on an
old-hard row; the zero clip is intentional, and the independent true-attack
margin below still applies. Hard-class identity always uses canonical p_old.

The 24 teacher-wrong benign rows receive label supervision only; teacher
strength is null, not zero. The two wrong-benign validation rows likewise have
no protected-normal requirement. No B row is given an invented teacher target.

Persist a teacher scope/identity receipt and hashes before optimization. Old
normalizer/P2 state has no gradient and is not saved as part of the student.
No teacher constant is derived from the nested-validation scores, which are
not materialized in this experiment.

## 7. Fully specified losses and aggregation

The nonnegative Huber function is `H(v)=0.5*v*v` for `0<=v<=1`, otherwise
`v-0.5`. Use unreduced numerically stable BCE-with-logits for supervision.

For each target group g, define a context value as the mean of the relevant
target losses within a context. Then define `M_g` as the mean of those values
over contexts containing that group. Never average a long session's thousands
of rows as independent gradient votes. Groups are fixed by owner/label, not
source, device, family, teacher strength, or the five failures.

### 7.1 Balanced label loss

The four groups are A-attack, A-benign (including teacher-wrong), B-attack,
B-benign. Each has coefficient 1/4:

```text
L_label = (M_Aattack + M_Abenign + M_Battack + M_Bbenign) / 4
target loss = BCEWithLogits(q_i, y_i) / ln(2)
```

This balances task groups rather than copying their unequal prevalence. It is
a deliberate new F5 rule; it is not claimed to reproduce F1's sampling scheme.
It creates no per-family performance guarantee and may increase gradient
variance for sparse B attacks, which must be reported rather than retuned.

### 7.2 Continuous, label-aware teacher loss

Only correct A-attack and correct A-benign participate, coefficient 1/2 each:

```text
v_i = ReLU(teacher_strength_i - s_i*q_i) / 2.0
L_teacher = (M_correct_Aattack(H(v_i)) + M_correct_Abenign(H(v_i))) / 2
```

Stronger old evidence demands a stronger margin up to the fixed cap. Further
movement in the true-label direction is not penalized. Teacher wrong-benign
rows are excluded, so their errors are not distilled. This is one-sided
functional retention, not symmetric probability matching or coordinate cloning.

### 7.3 Attack safety, mean and worst observed in the batch

All true A and B training attacks participate, even if teacher strength is tiny:

```text
u_i = ReLU(1.0 - q_i)
L_attack_mean = (M_Aattack(H(u_i)) + M_Battack(H(u_i))) / 2
L_attack_batch_worst = max H(u_i) over attack targets in the current batch
L_attack = L_attack_mean + L_attack_batch_worst
```

An attack-empty batch has worst term zero. Tied maxima use `torch.amax`, sharing
the subgradient across equal maxima. This is explicitly a **batch** worst term,
not the maximum over the entire corpus. Whole-corpus worst margins and every
flip are checked after each epoch; the mean objective cannot certify them.
There is no top-k fraction, adaptive hard mining, example exception, or
five-target special weight.

### 7.4 Simple causal auxiliary objective

From h[t], predict event t+1's four attributes using fixed slices of the 27D
semantic-head output: protocol group (7), direction (3), length bin (8), delta
bin (9), in those orders from the F4 schema. Each next-attribute CE is divided
by `ln(number_of_categories)`; mean the four tasks, then mean transitions
within context, then mean eligible nested-train contexts. A length-one context
has no auxiliary term but keeps all its target losses. Use no PAD or successor
from another context/role. This head supplies only training supervision and
is removed from the student inference package.

```text
L_total = 1.0*L_label + 1.0*L_teacher + 1.0*L_attack + 0.1*L_semantic
```

ln uses binary64 natural logarithm and a float32 loss divisor. All coefficients,
margin 1, teacher cap 6, and scale 2 are proposed design constants, not measured
optima or guarantees. They are not changed after materialization or training.

### 7.5 Exact minibatch realization

Every training context appears once per epoch; no oversampling or balancing
sampler. Batch size is 32 contexts, with the last partial batch retained. Let
N=4,984 and n_g be the metadata-only count of eligible training contexts for
group g. The minibatch estimator for each context-mean component is:

```text
M_g(batch) = N / (batch_context_count * n_g)
             * sum(context_loss_g(c) for eligible c in batch)
```

Use full-training n_g, never the number of eligible examples in this batch.
Globally empty required groups fail preflight. An absent group in a particular
batch contributes zero; do not renormalize other group coefficients upward.
The same formula applies to eligible auxiliary contexts. The worst term is
the literal batch maximum and receives no n_g scaling. Gradient clipping is
applied once after the combined loss. Record the exact eligible counts.

At epoch evaluation, recompute losses at the same current checkpoint. Compute
full-split context means directly; diagnostic worst attack loss is the true
full-split maximum. Do not average in-flight losses from different weights and
label that the loss of a frozen checkpoint.

## 8. Training, runtime, and interruption rules

```text
seed = 2705
device = CPU; dtype = float32; AMP = false
threads = 4; interop_threads = 1; workers = 0
torch.use_deterministic_algorithms(True)
optimizer = AdamW(lr=0.001, betas=(0.9,0.999), eps=1e-8,
                  weight_decay=0.0001, amsgrad=False, foreach=False, fused=False)
global_gradient_clip_norm = 1.0
scheduler = none
max_epochs = 100
min_epochs_before_patience_stop = 20
patience = 12
selection_min_delta = 0.0001
```

Set `PYTHONHASHSEED=2705`, `OMP_NUM_THREADS=4`, `MKL_NUM_THREADS=4` before Python
starts; then seed Python random, NumPy, and torch with 2705 before constructing
modules. Default initialization is executed once in section 5's order. No
training initialization may be selected from synthetic or real performance.
For one-based epoch e, context order is `torch.randperm(N)` from a separate CPU
generator seeded `2705+e`, applied to lexicographically sorted context keys.
Within-batch length sorting is deterministic and undone for all joins.

Prefer the installed, previously used training runtime:
`C:/Users/28371/AppData/Local/Programs/Python/Python39/python.exe`, Python
3.9.13, NumPy 2.0.2, torch 2.8.0+cpu. This is a proposed runtime pin requiring
verification in I, not a current environment claim. Do not install or upgrade
packages automatically. F4's producer used Python 3.10/NumPy 2.2.6; its fixed
float32 byte inputs need not be regenerated to use the training runtime.
If the named runtime is unavailable, report the local mismatch before any real
run and make an explicit pre-run engineering amendment, not a model fallback.

After I, seal actual interpreter/package versions, CPU, OS build, threading,
code hashes, synthetic tests, and the model-initialization tensor hash in a
runtime receipt. Repeat initialization after reseeding in a fresh P/T process;
the initial tensor hash must match. Runtime/code changes on resume require an
engineering review; do not silently continue with altered numeric semantics.

One bounded synthetic resource pilot, no real arrays: deterministic valid F4
fixtures, 32 contexts each of length 256, supervised targets at every event,
all four groups nonempty and fixed synthetic teacher strengths. Run 2 warm-up
and 8 timed forward/backward/optimizer batches; median timed duration t.
Separately time 8 inference batches, median v. Reseed afterward; these are not
part of real training. Compute:

```text
projected_seconds = 100 * (ceil(4984/32)*t
                         + (ceil(4984/32)+ceil(4323/32))*v)
```

Three times this projection must be <=47,494.34391 seconds (the earlier local
training cap). Otherwise `F5_RESOURCE_NO_GO`, before teacher materialization.
No shrinking architecture, increasing threads/budget, or truncating contexts to
pass. It is a conservative resource screen, not an asserted runtime estimate.

Hard execution maxima: cumulative T wall time including epoch evaluation and
checkpointing 47,494.34391 seconds; P 1,800 seconds; K/final packaging 1,800
seconds; RAM peak working set 8 GiB; new output 5 GiB; initial free D: space
12 GiB. These are limits, not promises that training takes 13.2 hours. Check
resource counters each batch and phase boundary. Equality passes; excess stops.
No deleting other projects or data to satisfy a storage gate.

Heartbeat every 60 seconds with phase/epoch/batch/wall/last checkpoint. Launch
independently of chat/browser/network; any background PowerShell launcher uses
a hidden window and absolute paths. Provide a separate read-only monitor.
Checkpoint after each 25 completed optimizer batches and each epoch boundary:
model/optimizer/RNG state, order/cursor, counters, patience/selection state,
input/runtime/teacher/protocol hashes, cumulative time, and ledgers.

Persist a real-attempt-start marker before the first step. A recoverable
interruption resumes that trajectory only; no new initialization. Loss after
the last durable checkpoint may be recomputed identically (at most 24 completed
batches); elapsed attempt time is not reset. Persist elapsed-time and UTC
start/completion receipts at each batch boundary, separately from model
checkpoints. Time spent on subsequently recomputed batches is still charged.
For an unclosed batch on an unclean stop, conservatively charge the whole UTC
interval from that batch's start receipt to restart, including uncertain
offline downtime. Clock rollback or unreadable receipts stop as engineering-
incomplete; do not invent a cheaper elapsed estimate or start over automatically.

No scientific output may overwrite a finished result directory. Numeric NaN,
identity error, incomplete writes, or corrupted checkpoint is an engineering
failure with no scientific verdict. Exhausted resource budget is a resource
stop; an incomplete trajectory cannot emit a PASS from its saved best epoch.

## 9. Checkpoint eligibility and selection

At every completed epoch, evaluate the full nested train and nested validation
without gradients or teacher-score access on validation. Evaluate all targets
with their causal-prefix states. Eligibility requires all of:

1. Every input, hidden state at targets, and logit finite; no missing/omitted UID.
2. Nested-train A correct attacks: 2,179/2,179 hard; validation: 3/3 hard.
3. Nested-train B attacks: 68/68 hard; validation: 3/3 hard.
4. A old-normal benign newly hard: train 0/4,667; validation 0/1,478.
5. Frozen input/runtime/teacher/model-structure identities unchanged; model
   output has no metadata or endpoint value dependency.

Wrong-benign A rows (24 train, 2 validation) are retained and reported, with no
constraint requiring reproduction of their old hard verdicts.

Eligibility does not use B benign gain or the five exposed failures. Among
eligible checkpoints, minimize validation context-balanced supervised loss
`L_label` only (section 7.1 evaluated with validation denominators). The teacher,
auxiliary, and safety losses are not selection scalars. Validation has sparse
attacks; its four-group balance is a declared engineering selection convention,
not reliable model ranking evidence across populations.

The first eligible finite checkpoint is best. A replacement requires absolute
decrease >=0.0001; equality to that decrement qualifies; smaller differences
keep the earlier epoch. After each epoch an eligible improvement resets the
no-improvement counter, otherwise increment it from epoch 1. Stop at the first
epoch >=20 with counter>=12, or at 100, whichever first. No changing patience
after reading a curve. No eligible checkpoint => `F5_NO_ELIGIBLE_CHECKPOINT`.
Save per-epoch **individual gate counts and worst margins**, not only a single
eligible flag as in F1; this makes failures diagnosable without a second run.

Do not resume learning after the training terminal marker and selected
checkpoint hash are sealed. K cannot swap to another epoch, including a
previously eligible one. No final full-parent refit.

## 10. Final development utility and kill-only gate

Re-evaluate the selected checkpoint once to confirm section 9 identities and
counts, then measure B benign utility at the fixed q>=0 decision. The comparison
baseline is the documented old-missing hard-by-convention behavior, not learned
normality. No old B score is opened or invented.

The nested-validation B benign denominator is 3,720 targets / 3,327 contexts,
with the literal metadata-only distribution verified while drafting:

| Device-family key | Targets | Contexts | Minimum normal targets |
|---|---:|---:|---:|
| `iotsim-combined-cycle` | 333 | 282 | 34 |
| `iotsim-domotic-monitor` | 230 | 50 | 23 |
| `ton-iot-external` | 3,157 | 2,995 | 316 |

Require normal fraction >=0.10 for **every** listed key. Consequently at least
373 targets must become normal (sum of ceilings); the aggregate 10% condition
alone would require only 372 and is insufficient. Also require at least 10%
of contexts in each key to have **all of that context's B-benign target rows**
normal: minima 29,5,300 respectively. This second condition prevents a small
part of each repeated prefix being advertised as whole-context utility.
These keys are inherited coarse device families, not three independent physical
devices; preserve that wording and disclose source-group counts.

Both denominators and these numerical gates belong to F5's nested development
pool. They do not replace CE's separate 4,812/482 select gate or turn its
three-device requirement into a three-family claim. No CE PASS is emitted.
Nested-train B utility is reported by all four keys, never substituted for a
validation failure. Per-family attack results show targets/contexts/source
counts; no individual family with <3 contexts supplies positive attack evidence.

Failure here => `F5_NO_MATERIAL_BENIGN_GAIN`; K stays unopened. If it passes,
load the five saved kill-only feature prefixes, once, and apply the already
hashed student. All five must be hard. Any flip =>
`F5_KILL_ONLY_ATTACK_FAILURE`, with no retry or checkpoint replacement.
The five are exposed, selected failures from F1; five preserved decisions are
only absence of this counterexample, never five fresh confirmations.

Report hidden-state norms, exact duplicate fractions, and all per-source/
family/device metrics without selecting a new representation or fitting extra
probes. Do not make geometry, source-invariance, or calibrated-risk claims.
F0/CE geometry and attack-information instruments remain mandatory for any
later claim that requires them; F5 does not silently award their PASS statuses.

If all gates pass, emit `F5_DEVELOPMENT_CANDIDATE_PASS` with:

```text
positive_general_inheritance_evidence = false
untouched_confirmation_status = NOT_IDENTIFIED_OR_OPENED
deployment_authorized = false
ce_pass = false
ood_or_commissioning_claim = false
```

## 11. Stop states and next evidence

| First failed stage/condition | Terminal state |
|---|---|
| Resource feasibility / allowed wall or storage cap | `F5_RESOURCE_NO_GO` |
| Canonical teacher identity/numerical disagreement | `F5_TEACHER_IDENTITY_OR_NUMERICAL_FAILURE` (engineering; no scientific verdict) |
| Other implementation/hash/scope/numeric/write failure | `F5_ENGINEERING_FAILURE` (no scientific verdict) |
| Training ends with no eligible checkpoint | `F5_NO_ELIGIBLE_CHECKPOINT` |
| Final selected checkpoint violates inheritance checks despite its saved eligibility | `F5_ENGINEERING_FAILURE` (reproducibility mismatch) |
| Selected checkpoint misses B utility | `F5_NO_MATERIAL_BENIGN_GAIN` |
| Five-row rejection test has a flip | `F5_KILL_ONLY_ATTACK_FAILURE` |
| Complete chain succeeds | `F5_DEVELOPMENT_CANDIDATE_PASS` |

A resource/engineering failure does not prove a scientific negative. A
scientific negative rejects this realization and supplies no permission for
another learning attempt. Existing deployment remains the incumbent.

Before broad inheritance can be claimed, a later evaluation design must cover
the full relevant frozen attack denominators. In particular the original F1
outer-validation pool has 4,400 targets, including 2,000 A attacks; five
previous failures cannot replace those 2,000. That pool is exposed development,
not untouched confirmation, and presently lacks a fully materialized F4 input
artifact. Its later complete re-encoding/evaluation needs its own declared
scope and authorization; no partial pass here bypasses it. The 69 select
attacks and all viewed-report attacks remain separate, not training sources.

Paper-level positive evidence additionally needs a genuinely untouched,
identity-frozen confirmation universe. None is identified by F4/F5 alone.
Do not label select, earlier validation, report, or the five failures “fresh.”
The lack of such evidence is recorded before training; it limits any success
claim but does not prevent this modest development feasibility experiment.

New-device benign observation/commissioning is a subsequent system question.
It cannot rescue a failed inheritance run, use device thresholds here, or
claim industrial generalization without same-device benign/attack evidence.

## 12. Durable outputs and access accounting

Use a new `runs/frontend_f5_unified_student_v1_20260906_local/` root only after
execution is authorized, with `preflight/`, `training/`, `evaluation/` phase
subdirectories and a single immutable attempt ID.

Required artifacts:

1. `f5_identity_manifest.json`, frozen draft-successor SHA, code/test/runtime
   identities, init tensor hash, authorization receipt and boundary intent.
2. `f5_split_census.csv`, exact role/category/source/context counts, train/val
   UID lists, training eligible-context normalizers, hash of source assignment.
3. `f5_teacher_train_a.csv.gz`: UID, owner, label, source, context, teacher-kind,
   canonical logit/score/hard, raw signed margin, strength, clip/null status.
   `f5_teacher_scope.json`: numeric rows exactly 6,870; other rows zero.
4. `f5_epoch_ledger.jsonl`: all losses with denominators, all gate violations,
   per-group worst margins, selected epoch/patience state and resource totals.
5. Atomic `resume.pt`, `best.pt` only if eligible, immutable terminal training
   marker; no last-to-best substitution. Pickle loading limited to this own
   pinned checkpoint and audited tensor/primitive structures.
6. `f5_selected_predictions.csv.gz` for the exact parent universe, at fixed
   checkpoint only; its train/validation roles cannot disappear in aggregation.
7. Per-source, per-owner, exact-family and device-family confusion/utility
   tables with all target/context counts and named unsupported claims.
8. Separate `f5_kill_only_predictions.csv`, only if K reached; sealed checkpoint
   SHA predates it. No kill-only row in training files or main denominators.
9. `f5_role_open_audit.json`, `f5_verdict.json`, resource trace, meaningful test
   receipt, and sorted `SHA256SUMS` excluding itself.

Stage-specific counters distinguish opaque container bytes read, metadata rows
parsed, representation rows numerically decoded, teacher scores computed,
student scores by nested split, optimizer steps, and kill-only rows. Teacher
rows numeric=6,870, teacher validation/B/other numeric=0; select/report/FINAL,
PCAP, external network, and deployment writes=0. Byte-hashing a file is not
numeric parsing. Missing counters or absent stage outputs are not filled with
fabricated zeros. A completed result is atomically sealed; failures retain the
actual attempted stages and ledgers. Hash stored files after closing handles.

## 13. Required synthetic contracts and implementation handoff

The implementation must cover these behaviors with independent synthetic
fixtures, not expected real-data outcomes:

1. Hash/shape/dtype/offset/UID mismatch fails before teacher/model access.
2. Source-disjoint nested membership and crossing-context exclusion unchanged.
3. Teacher numeric loader decodes only its UID allowlist; mixed-container
   nonauthorized rows cannot reach NumPy arrays or P2.
4. Canonical normalizer float64 -> input/P2 float32 path, threshold equality,
   score saturation and pre-sigmoid extraction; wrong teacher-kind stops.
5. Teacher-wrong benign excluded only from distillation, never label loss;
   B has no teacher; correct A uses fixed signed clipping including endpoints.
6. Input has exactly 131 coordinates; metadata/endpoint edits do not change
   tensors; gradients or a router cannot depend on owner/source/label keys.
7. Model parameter count and construction order; same seed yields same init.
8. Packed mixed-length batches match independently evaluated target prefixes
   to abs/rel tolerance 1e-6, with identical hard decisions on test fixtures.
9. Future-event appends/changes cannot change earlier-prefix output; reset
   state between contexts. Tiny numeric differences are compared at 1e-6.
10. Four supervised-group and two teacher-group reductions, globally fixed
    n_g; missing batch groups, overlapping category contexts, final short batch.
11. Attack mean/batch-max gradients (ties included); show batch maximum is
    not misreported as corpus maximum; one failing attack invalidates eligibility.
12. Semantic head slice labels, normalization, causal t->t+1, empty transitions,
    no PAD/cross-context/future-after-cutoff target.
13. No validation/kill-only gradient path; nested-val teacher values inaccessible;
    score loss uses only prescribed validation labels during selection.
14. Exact q>=0 rule; no threshold sweep or rounded-score decision path.
15. Eligibility includes all four attack/benign protection checks on both
    splits; wrong-benign A does not accidentally become protected.
16. First eligible checkpoint, exact min-delta boundary, earlier-epoch tie,
    patience/min/max epoch stops, no best checkpoint if none eligible.
17. Per-device-family 10% target and all-benign-target-context utility rounding;
    abundant-device success cannot hide a failed smaller key.
18. Checkpoint hashing before K; failure prevents K opening; one kill flip
    cannot trigger another checkpoint, threshold, or optimizer step.
19. Interrupted vs uninterrupted synthetic trajectories have identical tensor,
    optimizer, cursor, RNG and loss-ledger state; wall counters handled separately.
20. Synthetic resource formula/cap boundaries; no real arrays in the pilot.
21. Atomic receipts, wrong/corrupt checkpoint rejection, finished directory
    refusal, failure precedence and NOT_EVALUATED unvisited stages.
22. Output denominators/per-gate counts, checkpoint-to-prediction reproducibility,
    zero forbidden access, and explicit limited-claim fields.

Add tests for a newly discovered engineering ambiguity if needed; no observed
F5 outcomes may become fixtures or justify changed numerical design. Synthetic
training validates mechanics, not scientific efficacy. Do not require a model
to learn the real answer in a “test.” The written batch objective should also
have hand-calculated fixture values checked independently of the trainer.

Implementation files proposed for the later Sol turn:
`repo/ood/issue27frontend_f5_unified_student_v1.py`,
`repo/ood/issue27frontend_f5_unified_student_contract_tests_v1.py`, and a scoped
Windows launcher/monitor. Do not import F1/F2 runners for their module state.
Reuse verified pure serialization/resource ideas with the F5 scope explicit.

## 14. Review decisions and operator references

Before FROZEN review the substantive choices together: shared new head rather
than frozen-P2 reuse; fixed clipped one-sided continuous teacher; balanced
context-level groups and batch-worst attack term; fixed zero-logit threshold;
source split with one-context A validation limitation; per-key B gain with
both target/context guards; one run and fixed resource stop. Changing any
choice after an outcome requires acknowledging a new, unauthorized experiment.

Operator definitions were checked against primary versioned documentation:
[PyTorch 2.8 GRU](https://docs.pytorch.org/docs/2.8/generated/torch.nn.GRU.html),
[BCEWithLogitsLoss](https://docs.pytorch.org/docs/2.8/generated/torch.nn.BCEWithLogitsLoss.html),
[HuberLoss](https://docs.pytorch.org/docs/2.8/generated/torch.nn.HuberLoss.html).
These document implementation semantics; none validates the proposed losses,
coefficients, acceptance thresholds, or scientific success of this experiment.

The accepted numerical design is now FROZEN. Stage I implementation and
synthetic verification are authorized; stages P/T/K remain separately gated.
The companion implementation handoff is role-based, regardless of its
historical Sol filename. No real teacher scores or training results were used
to freeze these constants.
