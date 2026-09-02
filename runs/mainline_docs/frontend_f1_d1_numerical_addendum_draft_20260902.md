# Frontend-F1 D1 numerical/training addendum (DRAFT)

- Date: 2026-09-02
- Parent FROZEN protocol SHA-256: `98f2b73a051ee9c392631e85f4cc84d787306ed8333bfe2125f77870790c41b4`
- D0 r2 state: `F1_D0_CENSUS_PASS`
- Execution target: local Windows CPU only
- HPC state: unavailable until approximately 2026-09-08; not a dependency of this run
- Authorization state: drafting only; this document does **not** authorize implementation or training

## 0. Decision summary

This addendum freezes one attempt to train the mechanically selected
`torch.nn.GRU` semantic encoder. There is no candidate fallback, hyperparameter
sweep, seed sweep, threshold change, second head, device/family patch, or
result-driven retry.

The intended deployment remains coverage extension:

```text
A / old_missing=false -> frozen incumbent E3 + frozen old P2
B / old_missing=true  -> new GRU + learned 768D adapter
                        -> frozen old normalizer + frozen old P2
```

A is used during training as a functional teacher and as a shadow inheritance
exam. A deployment bytes remain incumbent bytes regardless of the D1 result.
B is the only deployment branch whose representation may change.

This D1 does not test or claim hydraulic improvement. Hydraulic is an A-side,
finite-but-wrong problem and is unchanged by construction.

## 1. Pinned evidence

| Artifact | SHA-256 |
|---|---|
| Frontend-F1 parent FROZEN | `98f2b73a051ee9c392631e85f4cc84d787306ed8333bfe2125f77870790c41b4` |
| D0 r2 verdict | `5109826a86d5e109cc7d51c57cbecf0dcb7bbd214b0f22483904cf5b08b66ec4` |
| D0 r2 teacher coverage | `f9dc000b9fb115bf10080a67efd7bd3490762b683aa452a5daa5b95acc9e1ee9` |
| D0 r2 candidate audit | `fa79dbe289ee407926fdd07148536cabbfb2245377d12e8623d04e9b487075a7` |
| D0 r2 synthetic resource pilot | `29cb7b5607cf8b907683e81cab9d446f9b14c6e36e8d07e585cb491b6e5e7fa4` |
| D0 r2 UID/context/phase/owner table | `c02937de7c5660688c60578adb2801f5a12b709745652fa8303b6c8e0d0b0ae9` |
| teacher-benign count artifact | `922a7a4faacdbaf370adfdf72e44e88b990ba54ac07c85286be40a6e7a86063e` |
| ZT-2 semantic status | `73aa283477ee4b38fa71441e6d04760d24ebb2d7770ec7393855aae3813cfc5e` |
| H1-H4 semantic engine | `00366fdef9d644c2ac60fab68047938e6bcc4425aab68e1f6c1ae552db40affa` |
| ZT-2 real-PCAP runner | `ca34ff39bfe7289fee1048d74e04de53dd4d4f096228fa837104cb65388b6f60` |
| incumbent fit/select embedding container | `b1b4f2fde168a69e0cf7a53aaede2ddef9bd6d92b0ce58e56a9d6fcde37b6099` |
| incumbent probe state | `50a9bcfc18287d51bf8afda7367b57decdf3179dd41fc3aa61399d4098360c38` |
| incumbent threshold marker | `84576a5008259f4381c46eecbc3ee3bda9d06b9dc7068cd52d7c2232e884dd5b` |

Every identity is checked before corpus materialization. Drift yields
`F1_D1_IDENTITY_FAILURE` and zero optimizer steps.

## 2. Frozen denominators and internal split

The 19 fit/select-crossing contexts remain wholly excluded. The legal fit
denominator is `18,266` targets in `12,889` contexts.

### 2.1 Split unit and algorithm

The indivisible group is `source_group`; therefore member and semantic context
are also indivisible. Fit labels may define the two strata below because labels
are already authorized for the fit-only supervised terms. No score,
representation, select, viewed, report, or FINAL value participates.

For every legal-fit source group:

```text
stratum = "attack_present" if any legal-fit row is attack else "benign_only"
key = SHA256("frontend-f1-d1-internal-val-v1\0" || stratum || "\0" || source_group)
```

Within each stratum, sort by `(key, source_group)`. Assign the first
`max(1, ceil(N_stratum / 5))` sources to internal validation and all remaining
sources to training.

The resulting internal-validation sources are frozen literally:

```text
normal_scanning1.pcap
iotsim-combined-cycle-3_0-0_to_OpenvSwitch-13_3-0
iotsim-combined-cycle-7_0-0_to_OpenvSwitch-13_7-0
iotsim-combined-cycle-8_0-0_to_OpenvSwitch-13_8-0
iotsim-domotic-monitor-2_0-0_to_OpenvSwitch-23_2-0
```

### 2.2 Literal split census

| Split | Label | Rows | Contexts |
|---|---|---:|---:|
| train | benign | 11,613 | 7,128 |
| train | attack | 2,253 | 2,179 |
| internal-val | benign | 2,400 | 1,582 |
| internal-val | attack | 2,000 | 2,000 |

Conservation:

```text
train = 13,866 rows / 9,307 contexts
internal-val = 4,400 rows / 3,582 contexts
13,866 + 4,400 = 18,266 rows
9,307 + 3,582 = 12,889 contexts
```

Owner/label detail:

| Split | Owner | Label | Rows | Contexts |
|---|---|---|---:|---:|
| train | A | benign | 6,171 | 2,844 |
| train | A | attack | 2,182 | 2,150 |
| train | B | benign | 5,442 | 4,284 |
| train | B | attack | 71 | 29 |
| internal-val | A | benign | 1,176 | 688 |
| internal-val | A | attack | 2,000 | 2,000 |
| internal-val | B | benign | 1,224 | 894 |
| internal-val | B | attack | 0 | 0 |

The absence of B attack contexts in internal validation is disclosed and may
not be repaired by moving sources. B attack safety remains a fit diagnostic
plus the frozen 23-row select kill-only sentinel.

## 3. Frozen semantic tensor

### 3.1 Re-decode and causality

The runner reuses the pinned two-pass H1-H4 engine. Context identity, endpoint
orientation, packet ordinal, current-inclusive cutoff, 256-event cap,
300-second span cap, 60-second idle split, regression clamp, state release, and
no-tail-reentry semantics are unchanged.

No payload byte is opened. Raw IP/MAC addresses, endpoint ordinals, context
digests, member names, source names, device names, labels, families, and roles
never enter an encoder tensor.

### 3.2 Per-event canonical signature

Each event becomes one canonical UTF-8 signature containing only:

1. H1/H2/H3/H4 tier;
2. direction `A_TO_B`, `B_TO_A`, or `UNKNOWN`;
3. link/encapsulation type;
4. EtherType or `NONE`;
5. IP version or `NONE`;
6. IP protocol number or `NONE`;
7. protocol group: TCP, UDP, ICMP, GRE, OTHER_IP, NON_IP, or KEYLESS;
8. transport-port-pair-present Boolean; port values are excluded;
9. decoder field-presence mask; field values are excluded except items 4-6;
10. frame-length bin: `<=63`, `64-127`, `128-255`, `256-511`, `512-1023`,
    `1024-1518`, `1519-4095`, or `>=4096` bytes;
11. surrogate inter-event delta bin: `0`, `(0,1e-6]`, `(1e-6,1e-3]`,
    `(1e-3,1e-2]`, `(1e-2,1e-1]`, `(1e-1,1]`, `(1,10]`, `(10,60]`, or
    `>60` seconds;
12. timestamp-regression Boolean;
13. ICMP/ICMPv6 type and code or `NONE`;
14. GRE-key-present Boolean; the GRE key value is excluded.

The signature fields use ASCII names, decimal integers, literal `NONE`, and
unit-separator `0x1f`, with no locale-dependent formatting.

### 3.3 Vocabulary

The vocabulary is fit on training-source contexts only. Internal-val and
select contexts cannot create dictionary entries.

```text
0 = PAD
1 = UNK
2..4095 = observed training signatures sorted by
          (SHA256(signature_bytes), signature_bytes)
```

More than 4,094 unique training signatures is
`F1_D1_VOCABULARY_CAPACITY_NO_GO`; no hashing, truncation, frequency pruning,
or vocabulary enlargement is permitted. Unseen internal-val/select signatures
map to `UNK`.

Each target representation is the GRU state after consuming the exact causal
prefix ending at that target event. Padding is right padding and never updates
state. No context exceeds 256 events.

### 3.4 Endpoint-masked arm

Raw endpoint identifiers and endpoint ordinal tokens are absent from the
tensor by construction. The mandatory endpoint-masked arm therefore must
produce byte-identical token tensors and numerically identical representations
to the ordinary arm. Any difference is
`F1_D1_DEVICE_OR_ENDPOINT_SHORTCUT_NO_GO`; no separately trained masked model
is allowed.

## 4. Single model identity

The only model is:

```text
Embedding(num_embeddings=4096, embedding_dim=32, padding_idx=0)
GRU(input_size=32, hidden_size=128, num_layers=1,
    bias=true, batch_first=true, bidirectional=false, dropout=0.0)
Linear(in_features=128, out_features=768, bias=true)  # learned adapter
```

The inference encoder contains exactly `292,352` trainable parameters.

The self-supervised training head is:

```text
Linear(128, 32, bias=true)
dot product with the tied 4096x32 input embedding matrix
one learned 4096-vector output bias
```

The head adds `8,224` parameters; training-time total is `300,576`. It is
discarded after checkpoint selection and never enters the deployed B branch.
There is no LayerNorm, batch norm, attention, second GRU layer, residual MLP,
or alternate adapter.

The 768D output is passed through the frozen old normalizer and frozen P2.
Output width alone is not treated as compatibility evidence; compatibility is
decided only by the functional gates below.

## 5. Frozen losses

Let `z_new` be the frozen-P2 logit from the new 768D representation and
`z_old` the incumbent P2 logit, available only for A. Let

```text
theta_0 = 0.065159872174263
z_0 = log(theta_0 / (1 - theta_0))
    = -2.6635317063752599
m_attack = z_0 + 0.5
tau_teacher = 0.25 logit
```

Every term is first averaged within a semantic context, then averaged equally
over eligible contexts. No source, device, family, class, row-count, or owner
weight is used.

### 5.1 Causal semantic loss

For every adjacent event pair in a training context, predict the next event
token from the preceding GRU state using tied-softmax cross entropy. Length-1
contexts have no semantic term and remain eligible for label-aware terms.

```text
L_semantic = mean_context(mean_transition(CE(next_token)))
             / 8.317766166719343
```

### 5.2 Fit-label loss

For all legal training target rows:

```text
L_label_fit = mean_context(mean_target(BCEWithLogits(z_new, y)))
              / 0.69314718055994529
```

### 5.3 Attack-margin loss

For all true-attack training targets:

```text
L_attack_margin = mean_context(mean_attack(ReLU(m_attack - z_new))) / 0.5
```

### 5.4 Correct-teacher margin loss

Only teacher-correct A targets are eligible:

```text
A true attack, old hard:
    ReLU((z_old - 0.25) - z_new) / 0.25

A true benign, old normal:
    ReLU(z_new - (z_old + 0.25)) / 0.25
```

A true-benign old-hard rows (`28/7,347` globally) are excluded from this term
and remain in `L_label_fit`, allowing them to soften. B never receives a
teacher score or teacher embedding.

### 5.5 Total loss and weights

```text
L = L_semantic
  + 1.0 * L_label_fit
  + 1.0 * L_attack_margin
  + 1.0 * L_correct_teacher_margin
```

All four weights are literal `1.0`; their scale normalization is part of each
term above. No loss is conditionally disabled except when its mathematically
defined eligible set is empty for a batch; epoch ledgers aggregate exact
eligible denominators.

## 6. Optimizer and deterministic execution

```text
seed = 2701
dtype = float32
device = CPU
torch_num_threads = 4
torch_num_interop_threads = 1
deterministic_algorithms = true
optimizer = AdamW(lr=0.001, betas=(0.9,0.999), eps=1e-8,
                  weight_decay=1e-4, amsgrad=false)
batch = 32 semantic contexts
gradient_clip_global_norm = 1.0
learning_rate_scheduler = none
maximum_epochs = 100
minimum_epochs_before_patience_stop = 20
```

Training-context order at epoch `e` is the deterministic permutation generated
by a fresh CPU `torch.Generator` seeded with `2701 + e`. Events and targets
inside a context remain in packet-ordinal order.

No automatic mixed precision, GPU, compilation backend, data-loader worker,
random augmentation, class sampler, family sampler, or device sampler is used.

## 7. Checkpoint eligibility, selection, and early stop

After every epoch, evaluate internal validation without updating parameters.
An epoch is checkpoint-eligible only if:

1. every internal-val representation and score is finite;
2. every incumbent-hard A internal-val attack remains hard at `theta_0`;
3. no incumbent-normal A internal-val benign becomes hard;
4. the endpoint-masked arm is byte/numerically identical;
5. frozen P2, normalizer, threshold, vocabulary, and split hashes are unchanged.

For an eligible epoch, the selection scalar is the same normalized four-term
internal-validation loss from §5. The selected checkpoint is the lowest scalar;
an improvement requires an absolute decrease of at least `1e-4`. Exact or
sub-`1e-4` ties keep the earlier epoch.

After epoch 20, stop after 12 consecutive epochs without an eligible
`>=1e-4` improvement. Maximum epoch is 100. If no eligible checkpoint exists,
the scientific state is `F1_D1_NO_ELIGIBLE_CHECKPOINT`; the last epoch cannot
be substituted.

Select, viewed, report, and FINAL remain unopened during training, early stop,
and checkpoint choice.

## 8. Local resource and resume contract

This run is local-only and network-independent.

```text
training cumulative wall cap = 47,494.34391 seconds = 13.19287331 hours
corpus materialization cap = 4 hours
post-checkpoint evaluation cap = 4 hours
overall process-chain cap = 24 hours
process peak RAM cap = 8 GiB
new durable-output cap = 5 GiB
fresh free-space launch gate = 12 GiB on D:
heartbeat interval = 300 seconds
checkpoint interval = every 50 optimizer batches and every epoch boundary
maximum recompute after interruption = 49 optimizer batches
```

One real training attempt is allowed. A power/network/user interruption may
resume the same attempt only if the checkpoint contains model, optimizer,
epoch, batch cursor, vocabulary, split manifest, all RNG states, cumulative
wall time, and loss ledgers. Cumulative wall time never resets. Restarting from
zero after an optimizer step is forbidden.

Before real execution, synthetic resume and uninterrupted training must produce
byte-identical checkpoint tensors, optimizer state, batch order, and ledgers.
The experiment does not require Internet access.

## 9. Post-checkpoint representation gates

These gates are evaluated only on the one frozen checkpoint.

### 9.1 Availability

Inherit unchanged:

```text
full universe finite >= 0.90
every benign device finite >= 0.80
every exact attack family finite >= 0.80
old-missing finite >= 0.90
every benign device old-missing finite >= 0.80
every exact missing attack family finite >= 0.80
```

All 25,467 status rows and all 11,640 B rows must exist uniquely.

### 9.2 Collapse

On centered legal-fit context-terminal representations, all must hold:

- nonfinite fraction = `0`;
- exact all-zero vector fraction <= `0.001`;
- exact duplicate-vector excess fraction <= `0.10`;
- at least 32 singular values satisfy `s_i / s_1 >= 1e-3`;
- entropy effective rank `exp(-sum(p_i ln p_i)) >= 16`, where
  `p_i = s_i^2 / sum_j s_j^2`;
- median L2 norm >= `1e-3`;
- `q99(norm) / median(norm) <= 100`.

Failure is `F1_REPRESENTATION_NO_GO` and cannot activate another encoder.

### 9.3 Fixed deterministic 35D semantic control

For every target prefix, the non-learned control is the concatenation of:

- tier one-hot: 4;
- direction fractions: 3;
- IP-version fractions `{4,6,NONE}`: 3;
- protocol-group fractions: 7;
- frame-length histogram: 8 bins from §3.2;
- delta histogram: 6 bins `0`, `(0,1e-3]`, `(1e-3,1e-1]`, `(1e-1,1]`,
  `(1,60]`, and `>60` seconds;
- `log1p(event_count)/log(257)`: 1;
- `log1p(span_seconds)/log(301)`: 1;
- timestamp-regression fraction: 1;
- transport-port-present fraction: 1.

Total dimension is `35`. All fractions divide by the current causal prefix
event count. No learned parameter or endpoint identifier enters this control.

### 9.4 Device leakage

Use legal-fit benign contexts from every device with at least 20 independent
contexts. Within each device, context keys are SHA-256 sorted with salt
`frontend-f1-d1-device-audit-v1`; the first `max(4, ceil(N/5))` contexts form
diagnostic validation and the rest diagnostic training.

Fit a one-vs-rest L2 linear logistic classifier with `C=1.0`, `liblinear`,
maximum 2,000 iterations, seed 2701, after train-only z-score normalization.
Report context-equal balanced accuracy.

The 1,000-permutation null permutes diagnostic-validation device labels at the
context level while classifier predictions remain fixed. Report the 99th
percentile. The learned representation passes only if:

```text
learned device balanced accuracy <= deterministic-control accuracy + 0.05
```

The raw and endpoint-masked arms must be identical. Every eligible device and
denominator is reported.

### 9.5 Geometry instrument

The eligible legal-fit benign devices are frozen count-only as:

```text
iotsim-building-monitor
iotsim-combined-cycle
iotsim-combined-cycle-tls
iotsim-domotic-monitor
ton-iot-external
```

Each has at least 64 independent contexts. Rank is `4`. Use the inherited Lane
G definitions, equal-context weighting, timestamp-ordered early/late halves,
and leave-one-device-out construction. The literal gates remain:

```text
median projection distance <= 0.20
worst projection distance <= 0.35
median principal angle <= 20 degrees
worst principal angle <= 35 degrees
median between/within R >= 2.0
at least 80% of eligible devices have R >= 1.0
```

All five device rows are reported; macro values cannot hide a failed worst
device.

### 9.6 Fit-only attack-information canary

Fit one binary L2 logistic probe (`C=1.0`, `liblinear`, maximum 2,000
iterations, seed 2701) on frozen train representations after train-only
z-score normalization. Evaluate on the source-held-out internal-val split from
§2 with context-equal weights. The deterministic 35D control uses the identical
split and probe capacity.

The primary metric is target-level AUROC after equal context weighting. The
nonparametric nearest-centroid cosine AUROC is reported but is not a separate
pass route.

For each arm, create a 1,000-permutation null by permuting internal-val labels
at the context level against the fixed predictions. The learned representation
passes only if all hold:

```text
learned linear AUROC >= 0.80
learned linear AUROC >= control linear AUROC + 0.02
learned linear AUROC > learned-arm permutation-null p99
endpoint-masked arm independently satisfies the same three inequalities
```

Every exact family/source/context denominator is reported. Fewer than three
contexts for a family remains `INSUFFICIENT_INDEPENDENT_ATTACK_CONTEXTS` and
cannot become a per-family positive claim.

## 10. One-shot select shadow gates

Only after model, checkpoint, vocabulary, all gate definitions, and every
fit-derived artifact are hashed may select be opened once.

The frozen select attack denominator is:

```text
69 support_val attack rows / 54 independent contexts
  A: 46 rows / 39 contexts
  B: 23 rows / 15 contexts
```

All 69 new-shadow scores must be hard at `theta_0`; one flip yields
`F1_NO_ATTACK_CAPABILITY_INHERITANCE`. Exact-family and worst-source tables are
mandatory. The 23 B rows remain a small-sample kill-only sentinel, not a
positive family claim.

For B benign select:

- denominator is exactly `4,812` old-missing benign rows;
- no B benign device may have more hard rows than its incumbent fail-closed
  baseline;
- at least three B benign devices must strictly reduce hard rows;
- total hard rows must fall by at least `482`.

A deployment output remains byte-identical to the incumbent regardless of its
shadow score. A shadow benign changes are diagnostics only.

Viewed report attacks are not part of this initial select opening. They require
separate authorization and can only kill the already frozen checkpoint. FINAL
and cooler-motor remain sealed.

## 11. Literal scientific states

| Condition | State |
|---|---|
| all inherited representation, A attack, and B utility gates pass | `F1_DEVELOPMENT_INHERITANCE_AND_EXTENSION_PASS` |
| any 69-row select attack flip or required A inheritance failure | `F1_NO_ATTACK_CAPABILITY_INHERITANCE` |
| A inheritance passes but B misses device/482 gain | `F1_NO_MATERIAL_BLINDSPOT_GAIN` |
| representation gates pass but frozen P2 interface alone fails | `F1_P2_INTERFACE_NO_GO_BUT_REPRESENTATION_PASS` |
| collapse, leakage, geometry, or attack-information gate fails | `F1_REPRESENTATION_NO_GO` |
| no eligible checkpoint | `F1_D1_NO_ELIGIBLE_CHECKPOINT` |
| vocabulary exceeds 4,094 observed train signatures | `F1_D1_VOCABULARY_CAPACITY_NO_GO` |
| identity, leakage, boundary, or implementation failure | `F1_ENGINEERING_OR_PROTOCOL_FAILURE` with no scientific verdict |

No state authorizes a second encoder, a hyperparameter change, a rerun from
zero, a new head, full replacement, or hydraulic-specific repair.

## 12. Minimum implementation gates before real training

At least the parent 25 tests plus the following numerical tests must pass:

1. literal split source list and all §2 conservation counts;
2. train-only vocabulary and `UNK` behavior;
3. raw endpoint bijection leaves token tensors identical;
4. token signature boundaries for all length/delta bins;
5. target representation uses the current-inclusive exact event position;
6. future-event mutation cannot change an earlier target representation;
7. context-equal loss differs from target-row mean on an adversarial fixture;
8. the 28 old-hard benign rows are absent from teacher-hard preservation;
9. B teacher access is impossible;
10. tied semantic head parameter count and total parameter count are exact;
11. `z_0`, margins, normalizers, and all lambdas match literals;
12. no class/source/device/family weighting path exists;
13. checkpoint eligibility rejects one attack flip and one new benign hard;
14. earliest-epoch tie behavior and patience are exact;
15. interrupted/resumed synthetic run is byte-identical to uninterrupted run;
16. cumulative wall time survives resume and cannot reset;
17. endpoint-masked arm is input/representation-identical;
18. 35D deterministic control has exact dimension and no learned state;
19. collapse gates fail on constant, low-rank, duplicate, nonfinite fixtures;
20. device and attack permutations operate at context level;
21. select cannot be opened before checkpoint and fit-artifact hashes freeze;
22. 69/46/23 and 4,812/482 denominators are exact;
23. viewed/report/FINAL paths cannot enter training or checkpoint selection;
24. frozen P2/normalizer/threshold hashes are unchanged before and after;
25. engineering failure removes scientific verdict and preserves diagnostics.

## 13. Requested independent review

The reviewer should give `ACCEPT`, `MODIFY`, or `REJECT` for each:

1. Is the source-stratified, source-held-out split identifiable and free of
   target/context leakage despite the disclosed absence of B attack val?
2. Is the fixed signature/vocabulary sufficiently expressive without raw
   endpoint or port values, and is the 4,094-token no-go preferable to hashing?
3. Are the four normalized loss definitions, `0.5` attack margin,
   `0.25` teacher tolerance, and all-one lambdas a defensible one-shot choice?
4. Are checkpoint eligibility, `1e-4` improvement, epoch 20, patience 12, and
   maximum epoch 100 strict enough without creating a hidden search surface?
5. Are the collapse gates and the 35D deterministic control mechanically
   complete and dimensionally correct?
6. Are `0.05` device-leakage excess, `0.80` attack AUROC, and `0.02` learned
   improvement margins defensible before any learned representation exists?
7. Is the local resource contract consistent with the D0 synthetic pilot and
   the user's decision to wait until about 2026-09-08 for HPC?
8. Do the one-shot 69-row attack and 4,812/482 B-benign gates preserve the
   parent protocol without silently upgrading the small-sample claim?

## 14. Authorization boundary

The present user authorization covers this DRAFT only. It does not authorize:

- implementation;
- real semantic-corpus materialization for training;
- any optimizer step or checkpoint;
- select/viewed/report/FINAL opening;
- HPC submission;
- a performance or paper claim.

After independent review, only mechanical corrections may enter FROZEN. Real
implementation and real training each require explicit user authorization.
