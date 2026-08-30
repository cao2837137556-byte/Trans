# Frontend-F0 Three-Route Comparison — Codex Draft

- Date: 2026-08-30
- Status: **DISCUSSION ONLY; NON-EXECUTABLE**
- Author role: Codex, main implementation/design lead
- Governing requirements: `frontend_f0_challenger_requirements_frozen_20260830.md`
- Governing requirements SHA-256:
  `b46caf0d308531f512ffedd3a9dea8d1438c22a8d136f7c1965dff8ea3f411b0`
- Evidence basis: Step-0b result `41699ed`, Kimi result review `85bc105`,
  Kimi freeze verification `67273e2`

## 1. Outcome first

The three proposed routes are **not three interchangeable models**:

1. **Route A — mature challenger intake** changes the frontend;
2. **Route B — Data-F0b paired corpus** changes the available development and
   evaluation evidence, but does not repair the frontend; and
3. **Route C — controlled in-domain frontend construction** changes the
   frontend and is the only route whose input semantics can be designed from
   the start to cover the complete observed protocol/event universe.

Therefore the recommended priority is:

```text
Route C0 semantic/encodability feasibility audit      PRIMARY
Route A0 mature-candidate full-universe precheck      CHEAP PARALLEL CONTROL
Route B Data-F0b bulk inventory                       DEFER UNTIL A FRONTEND PASSES STAGE 2
```

This is a priority proposal, not an authorization. It does not nominate a
model, authorize checkpoint retrieval, open embeddings, download a corpus, or
start training.

## 2. Fixed facts that the route choice must explain

Step-0b established on the frozen 25,467-target fit/select universe:

| Fact | Frozen observation |
|---|---:|
| finite targets | 13,827 |
| missing targets | 11,640 |
| missing benign targets | 11,478 / 21,013 (54.62%) |
| missing attack targets | 162 / 4,454 (3.64%) |
| unsupported non-TCP/UDP predicate | 11,605 |
| no IP session key predicate | 9,605 |
| timestamp regression predicate | 47 |
| nonfinite timestamp predicate | 0 |

Every missing benign target activated the unsupported-protocol predicate, and
9,605 missing targets activated both unsupported protocol and no session key.
The next frontend must solve both protocol coverage and bounded causal context
formation. More training rows cannot repair a frontend that still refuses to
represent those rows.

## 3. Common comparison axes

Every route is judged before performance results on:

1. direct relevance to the 11,478-target benign blind spot;
2. ability to satisfy the full-universe 0.90 / 0.80 / 0.80 availability gates;
3. reproducible lineage and immutable byte identity;
4. causal handling of keyless events and timestamp regression;
5. endpoint-identity leakage risk and the mandatory masking arm;
6. local/HPC compute, storage, and elapsed-time cost;
7. scientific claim enabled if successful;
8. cheapest decisive stop state; and
9. whether failure leaves a reusable artifact rather than another model-zoo
   attempt.

## 4. Route A — mature challenger intake

### 4.1 Candidate shape

The currently audited mature candidate is Pcap-Encoder. The existing Stage-I
audit established:

- official code and MIT license are identifiable;
- the model class is T5-base, approximately 220M parameters and 768D output;
- the official `weights.pth` link exposes no publisher-provided byte count or
  SHA-256;
- the conservative audited support matrix covers IPv4/IPv6 TCP and UDP plus
  IPv4 ICMP; and
- non-IP, ICMPv6, GRE, and other IP protocols remain outside the declared
  scope.

The existing terminal state is `F0_NO_USABLE_OFFICIAL_CHECKPOINT`. NetMamba
remains sealed and is not silently activated.

### 4.2 What Route A can solve

If an immutable official artifact can be pinned and a legal deterministic
adapter can cover the full frozen universe, Route A gives the fastest access
to a mature pretrained representation. It avoids encoder pretraining and
provides a strong external-method comparison.

### 4.3 Main risks

1. **Identity risk:** a locally fetched object can be hashed after download,
   but this proves local immutability, not publisher-intended identity.
2. **Coverage risk:** the already frozen conservative protocol matrix excludes
   GRE and non-IP/keyless events that are central to the diagnosed blind spot.
3. **Semantic-adapter risk:** widening preprocessing after seeing the missing
   mechanisms may change the pretrained model's input meaning without evidence
   that the checkpoint learned those tokens.
4. **Resource risk:** frozen inference is GPU-preferred; CPU throughput is
   unknown and the school HPC is unavailable.
5. **Lineage risk:** official pretraining names MAWI, UNSW-NB15, and an
   anonymous campus trace; complete overlap exclusion is unavailable.

### 4.4 Required evidence before checkpoint retrieval

Route A should not begin with a blind weights download. A new A0 protocol must
first answer from pinned code only:

1. Can every protocol/event class in the 25,467-target universe be mapped to a
   finite deterministic input without altering checkpoint semantics?
2. Can the 9,605 no-five-tuple targets receive bounded causal contexts without
   capture-wide pseudo-sessions or all-singleton degeneration?
3. Does the mandatory endpoint-identifier masking arm leave a nontrivial input?
4. Is any required source-code adaptation a parser/adapter only, or does it
   create new token meanings that require retraining?

If any answer is negative, Route A is retained only as a bounded literature or
control method and the checkpoint need not be fetched.

### 4.5 Cost and stop rule

| Item | Assessment |
|---|---|
| precheck | low; static/code/count-only |
| checkpoint | one official object, estimated model-scale download |
| inference | medium/high; GPU preferred |
| scientific failure risk | high on full-universe coverage |
| earliest stop | `A0_FULL_UNIVERSE_SEMANTICS_NO_GO` |

## 5. Route B — Data-F0b paired corpus inventory

### 5.1 What it is

Data-F0b would download inventory-grade CIC IoT 2022 objects to determine
whether at least eight devices have both legal benign history and attack
evidence, then freeze Data-E/Data-T identities.

### 5.2 What it can and cannot solve

It can solve a later evidence problem:

- same-device benign-prefix / attack evaluation;
- untouched-device confirmation; and
- separation of frontend effects from data effects in a later 2x2 design.

It **cannot** make the present netFound frontend encode unsupported protocols
or keyless events. Downloading more rows before a frontend exists does not
repair the 11,478 missing benign targets.

### 5.3 Main risks

1. Official metadata did not establish member-level pairing; tens of GB may be
   downloaded only to discover `N < 8`.
2. The corpus is consumer IoT and may not cover industrial high-packet-density
   long connections.
3. Storage, transfer interruption, and extraction cost are material on the
   local D drive.
4. Opening a large corpus before a candidate passes encoder-only gates creates
   evidence without a qualified system to consume it.

### 5.4 Activation condition

Route B should be activated only after one frontend reaches
`F0_ENCODER_ONLY_PASS`, or if a separately frozen paper question explicitly
requires paired-corpus evidence independent of frontend development.

### 5.5 Cost and stop rule

| Item | Assessment |
|---|---|
| metadata already done | yes; `PENDING_MEMBER_INVENTORY_AFTER_DOWNLOAD` |
| transfer/storage | high; tens of GB plus extraction headroom |
| compute | low/medium for inventory and census |
| direct blind-spot relevance | none until a frontend exists |
| earliest stop | `DATA_F0B_INSUFFICIENT_PAIRED_DEVICES` |

## 6. Route C — controlled in-domain frontend construction

### 6.1 Why it is the primary route

Route C can define the missing input semantics by construction instead of
asking a checkpoint trained under another packet grammar to extrapolate:

- protocol number is represented rather than filtered to TCP/UDP;
- five-tuple contexts are used where legal;
- no-key events receive a bounded deterministic causal hierarchy;
- timestamp regression remains representable under a frozen policy;
- missing reasons and context sizes are emitted for every target; and
- raw endpoint identifiers have a mandatory masking arm.

This directly targets the diagnosed mechanism. It is not justified merely by
being "self-developed"; it must pass the same frozen gates as every mature
candidate.

### 6.2 Proposed staged shape

Route C should not start by training a neural model. It should have three
pretraining gates:

#### C0-A — legal corpus and resource census

- enumerate fit-visible, label-blind packet/event material;
- keep report and FINAL physically unopened;
- state whether mixed unlabeled fit traffic is allowed or benign-only input is
  required by the objective;
- report sessions, events/tokens, protocol classes, devices, and source
  concentration;
- estimate local CPU/GPU memory, wall time, checkpoint size, and resume plan;
- stop if the corpus/objective pair is not scientifically identifiable.

The prior I1 result is a warning, not a reusable gate: its benign-only D1
upper bound was 2,182,190 tokens, below the then-frozen 10,000,000-token
minimum. Route C must not silently reuse the broader 11,705,453-token D0
number if its new objective requires benign-only data.

#### C0-B — zero-training semantic prototype

Implement only after a separate protocol and authorization:

- universal event tokenizer/parser;
- causal context/sessionization hierarchy;
- deterministic masks and missing-reason dictionary;
- deterministic hash/random projection or other non-learned finite output,
  used only to prove identity, causality, conservation, context-size behavior,
  and full-universe encodability.

This prototype is not a challenger result and cannot pass geometry or attack
information gates. Its purpose is to prevent spending training compute on an
input contract that still drops the same traffic.

#### C0-C — bounded model/resource pilot

Only a C0-B availability PASS permits a tiny label-blind forward/training
pilot. The pilot freezes:

- architecture family and output dimension;
- token/context budget;
- self-supervised objective;
- optimizer and maximum updates;
- checkpoint/resume semantics; and
- exact stop-loss budget.

No detector head, select metric, or report result may choose these values.

### 6.3 Main risks

1. legal label-blind corpus may be too small or too concentrated;
2. keyless context rules may encode device identity instead of behavior;
3. a small model may achieve availability but fail device geometry or attack
   information;
4. local training may be too slow without HPC;
5. method maturity and reproducibility burden are higher than Route A.

### 6.4 Reusable value even if it stops

Unlike an immediate training attempt, C0-A/B produces a protocol/event support
contract, a universal causal tokenizer, context-size audits, and a precise
resource estimate. These remain useful even if learned pretraining is later
declined.

### 6.5 Cost and stop rule

| Item | Assessment |
|---|---|
| C0-A census | low; read-only/count-only |
| C0-B prototype | medium engineering; zero training |
| C0-C pilot | bounded medium compute |
| full pretraining | high; only after all earlier gates |
| direct blind-spot relevance | highest |
| earliest stop | `C0_CORPUS_OR_INPUT_SEMANTICS_NO_GO` |

## 7. Comparative decision table

| Criterion | Route A mature intake | Route B Data-F0b | Route C controlled frontend |
|---|---|---|---|
| directly repairs missingness | uncertain | no | yes, by construction |
| full-universe semantics controllable | low/uncertain | n/a | high |
| mature pretrained weights | yes, but identity blocked | n/a | no |
| new bulk data required | no | yes | not for C0; possibly later |
| training required | no | no | yes after C0 gates |
| immediate cost | low precheck | high transfer/storage | low census, medium prototype |
| principal failure risk | unsupported event grammar | paired inventory absent | corpus/compute or learned signal weak |
| strongest successful claim | mature frontend comparison | paired-device evaluation evidence | mechanism-targeted frontend contribution |
| recommended role | cheap parallel control | deferred evidence lane | primary system lane |

## 8. Recommended sequencing

```text
Step 1: freeze and run Route C0-A corpus/resource census
        + in parallel freeze Route A0 code-only full-universe feasibility check

Step 2: if C0-A PASS, freeze C0-B zero-training semantic prototype
        if A0 PASS, separately decide whether fetch-to-pin is worth authorizing

Step 3: compare only pre-result facts
        - full-universe semantic coverage
        - lineage
        - resource feasibility
        - identity-leakage controls
        then nominate at most one challenger for learned Stage 1/2 execution

Step 4: activate Data-F0b only after F0_ENCODER_ONLY_PASS
```

The one-challenger rule remains intact: no embeddings from multiple candidates
are opened and compared to select a winner. Route A0 and C0-A/B are pre-result
feasibility gates; challenger nomination occurs before learned representation
results.

## 9. Explicitly rejected sequences

1. **Download Data-F0b first:** expensive and does not repair input semantics.
2. **Fetch weights and immediately embed:** skips full-universe feasibility and
   risks proving only another bounded protocol subset.
3. **Train a neural encoder before C0-B:** can waste compute on a tokenizer or
   context hierarchy that still drops keyless/non-TCP/UDP targets.
4. **Run Pcap-Encoder and self-trained embeddings, then choose the better:**
   prohibited model-zoo selection.
5. **Relax 0.90/0.80/0.80 after seeing candidate coverage:** prohibited.
6. **Treat encodability as detector improvement:** prohibited; geometry,
   attack-information, head-bound, and later performance gates remain.

## 10. Questions for Kimi review

1. Is the categorical distinction correct that Route B supplies evidence but
   does not itself repair the frontend?
2. Should Route A require the A0 full-universe semantics check before any
   fetch-to-pin protocol, given the already frozen conservative support matrix?
3. Is Route C0-B's zero-training semantic prototype a valid anti-waste gate, or
   would even a deterministic projection create an avoidable selection surface?
4. For C0-A, may a representation-only self-supervised objective consume the
   full label-unopened fit-visible stream, or must it remain benign-only? The
   answer must be frozen before corpus counts choose the objective.
5. Is Data-F0b correctly deferred until `F0_ENCODER_ONLY_PASS`, or is there a
   paper/evaluation reason to acquire it earlier?
6. Does the proposed A0 + C0 pre-result parallelism preserve the single-
   challenger rule if challenger nomination is frozen before any learned
   embedding exists?

## 11. Authorization boundary

This document is discussion only. It authorizes no implementation, static
candidate retrieval, network request, checkpoint download, corpus download,
PCAP decode, tokenization run, representation generation, training, score
opening, report/FINAL access, or HPC submission.

After independent review, the user chooses priority. Each accepted route then
requires its own DRAFT → review → FROZEN → terminal review → implementation
authorization → implementation review → execution authorization chain.
