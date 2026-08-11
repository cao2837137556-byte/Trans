# CKDA D1 frozen representation probe — preregistered

Date: 2026-08-12

Status: **FROZEN**

Route: `CKDA`

D0 authority: `ckda_d0_result_20260811.md` + Kimi final review `bfbeaf9`

Freeze authority: Kimi D1 draft review `734625d`

Primary representation: `I1`

Predeclared backup/control: `E3`

> This is the formal frozen D1 information-canary preregistration. It does not
> authorize implementation, encoder training, embedding generation, report
> access, FINAL access, or HPC submission. Those actions require separate user
> authorization after the FROZEN text and SHA-256 sidecar are independently
> verified.

---

## 1. D1 question and claim boundary

D1 asks one bounded question:

> Does a strictly causal, label-blind representation of raw packet/session
> prefixes contain attack-versus-benign-OOD separation that is actionable under
> the existing frozen open-world detection gates?

D1 is not a detector promotion experiment. It may establish only one of the
five states in §12. In particular:

- D1 does not claim paper-level performance;
- D1 does not tune or evaluate the teacher-proposed loss;
- D1 does not reopen record-level model replacement, CKCZ episode veto, DROCC,
  family experts, source-specific thresholds, or a learned episode classifier;
- D1 does not touch cooler-motor or seed 37/47;
- finite probe failure is not an information-theoretic proof that no decoder
  can ever use the representation.

Only `CKDA_D1_ACTIONABLE_PROBE_SIGNAL` is aliased to `GO_D2`. That state
authorizes drafting D2 and nothing else.

---

## 2. Inherited identities and immutable denominators

### 2.1 D0 identities

The D1 implementation must pin and verify:

- D0 pullback archive SHA-256:
  `6bb7c1ec92e5954c30d8d89c5033ebd1edeec7d12a459d360543f950e72ca1bb`;
- D0 candidate audit SHA-256:
  `3522319bae1c82c1883759cc8bdcacddaf628b11092caec758d47b2e1e7a785a`;
- D0 contract SHA-256:
  `ac4e2c2093811929e0fd20b65bb0c727ef3f872f6f7586b3049cf5758fc9c8b5`;
- D0 verdict: primary `I1`, backup/control `E3`;
- original Slurm job `158210` remains `FAILED`; tail recovery is preserved as
  post-result engineering recovery, not rewritten as a successful Slurm run.

D0 measured 4,764,022 sessions and 11,705,453 I1-encodable tokens across all
legal fit-prefix rows. These numbers are compatibility evidence only. They are
not silently reused as the benign-only I1 training census in §4.2.

### 2.2 Report denominators and family dictionary

D1 inherits, without reinterpretation:

- the 244,050-row `GLOBAL_ATTACK_PRESERVATION` pool;
- role counts: support_val 69, same_file_query 2,486,
  future_query 131,391, sealed_final_attack 110,104;
- the exact 16-family report dictionary and rows from
  `ckcz_attack_family_scope_clarification_20260809.md`;
- the `rows >= 15` family gate over all 16 report families;
- future-only recall denominator 131,391;
- the four non-FINAL benign OOD report pools and FrozenCKBQ reference rates:
  hydraulic-system 45.70%, ip-camera-street 8.10%,
  predictive-maintenance 57.5889%, stream-consumer 29.70%, macro 35.2722%;
- select denominators: support_val 69, frozen auxiliary benign 3,000, and
  ToN-IoT `normal_2` benign 4,000.

The historical 12-family CKBW training strata do not replace or remap the
16-family report dictionary.

---

## 3. Data roles and non-negotiable isolation

| Role | Encoder fit | Embedding | Probe/state fit | Threshold | Report use |
|---|---:|---:|---:|---:|---|
| legal fit benign | yes | yes | benign reference/training | no | training only |
| legal fit attack | no | yes | P1/P2 attack training | no | training only |
| select attack/benign | no | yes | no | yes | selection only |
| report, non-FINAL | no | once, after freeze | no | no | one-shot verdict |
| FINAL: cooler-motor, seed 37/47 | **no** | **no** | **no** | **no** | sealed |

“Label-blind” does not make a role trainable. Select/report/FINAL cannot
contribute tokenizer statistics, bucket boundaries, normalization, masked or
next-event loss, checkpoint choice, probe fitting, or calibration.

All source/member allowlists must be resolved before opening any PCAP. A path,
member, source ID, seed, or marker matching FINAL causes fail-closed engineering
failure and produces no scientific verdict.

No source, family, mechanism, protocol, or device identity is a model input or
threshold-routing key. Such fields are permitted only in immutable manifests and
post-freeze stratified reports.

---

## 4. I1 training corpus and pre-open gate

### 4.1 Benign-only source rule

To retain `CONSTRUCTIVELY_HELD_OUT`, I1 encoder training uses only D0 manifest
members whose frozen provenance is unambiguously benign:

- `aux_fit` members whose raw path is under `raw/benign/`;
- `id_calib` members whose raw path is under `raw/benign/`;
- `ood_val` members whose raw path is under `raw/benign/`;
- `ood_stress` members whose raw path is under `raw/benign/`;
- `aux_normal_fit` direct PCAPs.

The following D0 fit-prefix roles are excluded from I1 self-supervision:

- `support_train` because they are attack prefixes;
- `aux_process_fit` because their process role is not reclassified as benign by
  filename or intuition.

This exclusion applies only to self-supervised encoder fitting. Legal fit attack
targets remain available for P1/P2 fitting after the encoder is frozen.

### 4.2 Benign-only census gate

Before I1 training, the exact benign-only allowlist in §4.1 must be censused
without reading labels or generating performance embeddings. The existing D0
minimum is reapplied to this narrower semantic corpus:

```text
benign_fit_sessions >= 500,000
AND benign_fit_tokens >= 10,000,000
```

Both conditions are mandatory. Counts, source/member rows, cutoffs, and SHA-256
must be persisted. If the gate fails, it is not repaired by admitting
support_train, aux_process_fit, select, report, or FINAL. I1 receives
`CKDA_D1_PRIMARY_PRECONDITION_FAILED` and progression follows §11.

This gate deliberately prevents the D0 all-fit-prefix token count from being
misreported as a benign-only training count.

---

## 5. Frozen session-prefix contract

### 5.1 Session identity and order

For I1, a session is:

```text
source_id + pcap_member + canonical_bidirectional_5tuple
```

The endpoint pair is ordered lexicographically by `(IP bytes, port)` and the IP
protocol number is part of the key. State resets at every source/member boundary.
There is no inactivity-timeout split.

Within a session, packets are ordered by:

1. parsed capture timestamp;
2. frozen event position within the capture as the stable equal-time tie-break.

For a target packet at cut `t`, the input is current-inclusive and contains at
most the most recent 256 packets in the same session with order `<= t`. Older
packets are truncated from the left. No complete-session length, termination,
future direction, or future burst is available.

### 5.2 I1 packet fields and fixed buckets

No data-fitted vocabulary, codebook, bucket edge, or normalization is allowed.
Each encodable packet supplies four categorical fields:

1. `direction`: canonical endpoint A→B or B→A;
2. `length_bucket`: `min(floor(max(frame_len,0) / 64), 31)`;
3. `protocol`: raw IP protocol integer in `[0,255]`;
4. causal IAT bucket within the same session:
   - `0`: first packet;
   - `1`: non-first packet with `delta_us == 0`;
   - `2 + min(floor(log2(delta_us)), 30)` for `delta_us >= 1`.

Negative length, negative IAT, missing endpoint/protocol, or parse failure is not
imputed from future context. The target remains in its denominator and uses the
unified missing state in §8.4.

---

## 6. I1 encoder, objective, and representation

### 6.1 Architecture

I1 is a small causal Transformer with one fixed identity:

| Item | Frozen value |
|---|---:|
| maximum current-inclusive prefix | 256 packets |
| hidden width | 128 |
| causal Transformer blocks | 4 |
| attention heads | 4 |
| feed-forward width | 512 |
| dropout | 0.10 |
| layer norm | pre-norm |
| position encoding | learned, positions 0–255 |
| field combination | sum of four field embeddings + position embedding |

No payload bytes, 51D features, frozen detector scores, labels, source/family
identity, endpoint identity, or report statistics enter I1.

### 6.2 Self-supervised objective

Training is next-event prediction. A BOS state predicts the first packet and
each causal prefix ending at packet `t-1` predicts packet `t`. Four cross-entropy
losses predict direction, length bucket, protocol, and IAT bucket. The encoder
loss is their unweighted arithmetic mean.

Packets are materialized once per benign fit session, not duplicated once per
downstream target. The final epoch is used mechanically; no self-supervised
validation score or downstream probe score chooses a checkpoint.

| Training item | Frozen value |
|---|---:|
| seed | 27 |
| epochs | 3 |
| optimizer | AdamW |
| learning rate | 3e-4 |
| weight decay | 1e-2 |
| global batch budget | 32,768 non-padding tokens |
| gradient clipping | global norm 1.0 |
| schedule | linear warm-up over first 5% steps, then cosine decay to 0 |
| precision | float32 reference; mixed precision forbidden in D1 |
| checkpoint choice | final optimizer step of epoch 3 only |
| early stopping | none |

### 6.3 Frozen target representation

The I1 representation for target `t` is one 132-dimensional vector:

```text
[ LayerNorm(final causal hidden state after consuming current packet)_128,
  NLL_direction(t), NLL_length(t), NLL_protocol(t), NLL_IAT(t) ]
```

The four NLL values are produced by the state immediately before consuming the
current packet. Thus they measure current-event surprise without future access.
The encoder and prediction heads are frozen before select/report embeddings are
generated.

There is no layer search, pooling search, field ablation, alternate prefix
length, or surprise-score subset in D1.

---

## 7. E3 backup/control identity

E3 is not run in parallel for model shopping. It becomes eligible only under
§11. It must reuse the exact D0-pinned official netFound code, checkpoint,
configuration, tokenizer, no-payload interface, and prefix construction.

For each current-inclusive target prefix, E3 produces the final
`base_transformer.last_hidden_state`. The single frozen E3 representation is the
attention-mask-weighted arithmetic mean over non-padding final-layer tokens,
followed by one missing-state flag. No layer, burst, token, or pooling search is
allowed. The E3 encoder remains frozen.

E3 retains D0's `NO_KNOWN_OVERLAP` caveat. Even if E3 becomes actionable, it
cannot support a `KNOWN_DISJOINT` claim.

---

## 8. Frozen three-probe canary

All probes consume only the candidate's frozen representation plus one binary
`missing_embedding` flag. The probe order is diagnostic, not a model-selection
search: G0, P1, and P2 are all reported if the candidate reaches one-shot report.

### 8.1 Shared normalization

For finite representation dimensions, mean and population standard deviation
are fitted on legal fit targets only. A zero-variance dimension is mapped to
zero after centering. The statistics are frozen before select embeddings are
opened and are shared by G0/P1/P2.

### 8.2 G0: nonparametric geometry probe

- benign reference pool: legal fit benign targets only;
- deterministic cap: the 200,000 smallest `SHA256(uid)` values; use all if
  fewer than 200,000;
- representation is standardized then L2-normalized;
- score is the arithmetic mean cosine distance to the 5 nearest benign
  references;
- the query UID itself is excluded when it is present in the reference pool;
- no attack label, family, source, or report point contributes to G0 state.

G0 has no learned gradient parameters, but its reference pool and normalization
are fitted state; it is therefore not called “zero-training.”

### 8.3 P1: fixed linear probe

- input: shared standardized representation + missing flag;
- model: one logistic linear head;
- fit rows: frozen legal fit benign and legal fit attack targets only;
- loss: binary cross-entropy with inverse binary-class-frequency weights;
- L2 coefficient: 1.0;
- solver: LBFGS, maximum 300 iterations, tolerance `1e-8`;
- no feature, C, class/family weight, solver, or epoch search.

### 8.4 P2: fixed small-MLP probe

- input and fit rows identical to P1;
- one hidden layer of width 128, ReLU, dropout 0.10, scalar logit output;
- binary-class-frequency weighting identical to P1;
- AdamW, learning rate `1e-3`, weight decay `1e-4`;
- batch size 256, 50 epochs, seed 27, gradient norm clip 1.0;
- final epoch only, no early stopping or checkpoint search.

For G0, an unencodable target has score `+infinity`. For P1/P2, its finite
representation dimensions are zero and `missing_embedding=1`. No target may be
dropped. Missing counts and hard decisions remain in every denominator.

---

## 9. Threshold selection

Each probe emits a scalar anomaly score where larger means more attack-like.
For each candidate/probe, exactly one threshold is chosen using only:

- 69 support_val attacks;
- 3,000 frozen auxiliary benign-select rows;
- 4,000 ToN-IoT `normal_2` benign-select rows.

The threshold frontier consists of exact finite observed select scores plus the
explicit no-hard and all-hard sentinels. A row is hard iff `score >= threshold`.

Selection is deterministic:

1. discard any point that does not make all 69 support_val rows hard;
2. among remaining points, minimize the total benign-select hard count over the
   fixed 7,000 rows;
3. tie-break by minimizing auxiliary 3,000 hard count;
4. then minimize ToN-IoT 4,000 hard count;
5. then choose the largest threshold;
6. then compare the canonical decimal score string, ascending.

If any select score is NaN, if a denominator drifts, or if no valid finite
frontier can be constructed, the probe is an engineering failure. Thresholds
are frozen before report labels or embeddings are opened.

There is no candidate checkpoint selection and no choice among G0/P1/P2 using
report results.

---

## 10. One-shot report metrics and action gates

### 10.1 Required metrics

Every candidate/probe must report on exact common denominators:

- support_val hard count out of 69;
- overall attack recall over 244,050 rows;
- future-only recall over 131,391 rows;
- all 16 attack-family recalls and deltas to C1 on the same rows;
- four benign OOD hard rates, macro, and deltas to FrozenCKBQ;
- target, embedded, missing, duplicate, and nonfinite counts by role/source;
- same-denominator C1, FrozenCKBQ, and M7 comparison rows;
- ROC-AUC and PR-AUC for future_query versus the four benign OOD pools;
- session detection rate, false-alert sessions per source, and time to first
  alert as diagnostics only;
- 95% source-bootstrap and session-bootstrap intervals with 2,000 replicates,
  seed 2701.

Session metrics use the frozen session key in §5. They do not change the
record-level action gate and are not used to tune a window or episode rule.

### 10.2 Actionable gate for P1/P2

A P1 or P2 probe is actionable only if all conditions hold simultaneously:

1. support_val hard recall is 69/69;
2. overall 244,050-row attack recall is no more than 0.5 percentage points below
   C1 on the same rows;
3. every one of the 16 report families has
   `probe_recall - C1_recall >= -2.0 pp`;
4. future_query recall is at least 84.83% on exactly 131,391 rows;
5. four-pool benign OOD hard-rate macro is at most 30.2722%;
6. no individual OOD pool is more than 2.0 pp worse than FrozenCKBQ;
7. every OOD pool hard rate is at most 90%;
8. review count is zero;
9. no target is removed from a denominator and all causal, scope, identity,
   finite-value, and FINAL-exclusion gates pass.

The action gate is a conjunction. Confidence intervals are mandatory evidence
but do not replace the fixed point-estimate gates in D1.

### 10.3 Strong G0 and weak-only evidence

G0 is `STRONG_GEOMETRIC_SIGNAL` only if it satisfies the same conjunction in
§10.2. It still does not by itself authorize D2.

If no full conjunction passes, a probe is weak-only evidence when its
source-bootstrap 95% lower bound for future_query-versus-four-OOD ROC-AUC is
strictly greater than 0.5. This diagnostic cannot be used to retune the encoder,
probe, threshold, or action gate.

---

## 11. Primary-to-backup progression

The order is frozen as `I1 -> E3`.

1. Run I1 preconditions, train/freeze I1, fit/freeze its probes, select all
   thresholds, then open I1 report once.
2. If I1 reaches `CKDA_D1_ACTIONABLE_PROBE_SIGNAL`, stop; E3 is not opened.
3. If I1 reaches `CKDA_D1_NO_ACTIONABLE_SIGNAL_UNDER_FROZEN_PROBES` or an I1
   engineering/precondition failure, E3 may run under the already frozen E3
   contract.
4. I1 `STRONG_GEOMETRIC_SIGNAL` or `WEAK_ONLY` does not authorize E3 model
   shopping and does not authorize D2.
5. E3 report is one-shot. No third candidate, I1 variant, layer, loss, prefix,
   family patch, or threshold is introduced after either report is seen.

The result report must state whether E3 was unopened, opened because I1 had no
actionable signal, or opened because I1 failed engineering/preconditions.

---

## 12. Final state machine

Apply the following precedence after all authorized candidate work completes:

1. `CKDA_D1_ACTIONABLE_PROBE_SIGNAL` — P1 or P2 for the currently authorized
   candidate passes the complete §10.2 conjunction and every contract gate.
   This is the only `GO_D2` alias.
2. `CKDA_D1_STRONG_GEOMETRIC_SIGNAL` — no P1/P2 is actionable, but G0 passes the
   complete §10.2 conjunction.
3. `CKDA_D1_WEAK_ONLY` — no full conjunction passes, but at least one frozen
   probe meets the §10.3 weak-only definition.
4. `CKDA_D1_NO_ACTIONABLE_SIGNAL_UNDER_FROZEN_PROBES` — all authorized G0/P1/P2
   probes complete, none passes §10.2, and none meets the weak-only definition.
5. `CKDA_D1_ENGINEERING_FAILURE` — the authorized progression cannot produce a
   valid one-shot verdict because identity, role, causal, compatibility,
   resource, runtime, validation, or packaging contracts fail.

State 4 closes only this frozen representation/probe configuration. It must not
be written as `NO_INFORMATION` or as proof that raw traffic contains no useful
signal.

---

## 13. Executable causal and engineering gates

Before any select/report result is valid, all candidates must pass:

1. future mutation invariance;
2. future-label invariance;
3. source reset isolation;
4. exact-cut/current-inclusive examples;
5. equal-time stable ordering;
6. prefix-vs-full-session trap;
7. exact join completeness and uniqueness;
8. deterministic replay;
9. FINAL allowlist/denylist fail-closed exclusion.

For floating output comparisons, the frozen tolerance is `atol=1e-6, rtol=0`.
It cannot be relaxed after failure. Same-environment duplicate runs must also
produce identical UID order and quantized (`round(x, 6)`) content SHA-256.

Because the formal runtime is Python 3.9, launch is additionally blocked unless:

- every executed custom/vendored Python file parses under Python 3.9 grammar;
- `compileall` succeeds on both login and allocated compute nodes;
- the exact environment executes a real model forward, atomic text/CSV/JSON
  write-and-readback, validator, and packager smoke path;
- static regression gates reject `match/case`, `Path.write_text(newline=...)`,
  and every previously observed incompatible API pattern;
- mixed-schema CSV tests use a deterministic union field list and survive
  atomic finalization/readback.

An engineering failure has no scientific verdict. Completed source/member
checkpoints may be reused only when their input, code, contract, and environment
hashes match exactly and the failure occurred downstream of their validated
boundary.

---

## 14. Runtime, checkpoint, and output contract

A future formal run must be result-producing, resumable, and fail-closed:

- one lineage manifest for every opened source/member and cutoff;
- checkpoints at benign census, I1 epoch, source/member embedding, probe fit,
  threshold freeze, report-open, validation, and package boundaries;
- progress means validated completed units, not CPU use or heartbeat alone;
- stage all writes in an isolated run directory and atomically promote only
  after validation;
- preserve nonzero Slurm failure state and failure markers;
- report `sacct` elapsed, TotalCPU, MaxRSS, requested memory, CPUs, disk read,
  disk write, and any VRAM evidence;
- package code/contract/environment hashes, all audit tables, metrics, bootstrap
  tables, result report, validator report, and SHA-256 manifests.

No standalone synthetic/preflight Slurm job substitutes for the real-input
result-producing run. Local and login-node tests are launch gates only.

---

## 15. Forbidden adaptations after freeze

After the FROZEN SHA exists, none of the following may change from D1 evidence:

- token fields/buckets, session key, timeout, prefix length, architecture,
  objective, layer, pooling, NLL inclusion, optimizer, epoch, or checkpoint;
- benign corpus role interpretation or minimum corpus gate;
- reference cap, distance, k, standardization, P1/P2 structure or class weights;
- fit/select/report membership, threshold frontier, tie-break, action gates, or
  state precedence;
- source/family/device/protocol-specific feature, expert, weight, threshold, or
  missing policy;
- candidate order or a third representation.

Any desired change requires a new named route and a new preregistration. It
cannot inherit the D1 one-shot report as if it were unseen.

---

## 16. Freeze-review questions for Kimi

1. Confirm the §4 correction: D0's 11,705,453 all-fit-prefix tokens are not the
   benign-only corpus count, and the 500k/10m conjunctive gate must be rerun on
   the narrower benign allowlist before I1 training.
2. Confirm exclusion of both `support_train` and `aux_process_fit` from I1
   self-supervision, while retaining legal fit attacks for P1/P2 only.
3. Confirm the single I1 identity: 256-token causal Transformer, fixed
   next-event loss, final epoch 3, and 132D hidden-plus-surprise representation.
4. Confirm the single threshold rule and the complete §10.2 conjunction,
   including the 16-family/global/future denominator separation.
5. Confirm E3 masked-mean final-layer representation and the fixed `I1 -> E3`
   progression in §11.
6. Confirm state precedence: only P1/P2 full conjunction is `GO_D2`; G0 strong
   and AUROC weak-only remain non-promoting diagnostics.

Until these questions are closed and the resulting FROZEN document plus
SHA-256 sidecar are committed, D1 execution remains unauthorized.
