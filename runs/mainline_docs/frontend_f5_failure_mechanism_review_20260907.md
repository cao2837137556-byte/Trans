# Frontend-F5 failure mechanism review

Date: 2026-09-07. Status: `FORENSIC_REVIEW_COMPLETE_NO_NEW_RUN_AUTHORIZED`.

Post-review correction (source-only, same date): `flow_duration` is constructed
and passed through the old tokenizer/collator but is NOT supplied to the actual
E3 base-transformer call. References below to old session duration describe
preprocessing state, not a confirmed model-input gap or failure cause. Early
burst headers and burst IAT/bytes/counts remain confirmed input differences.
See `frontend_inheritance_feasibility_minimal_design_20260907.md` for the corrected
contract map and separate treatment of pretrained knowledge and coverage.

## Decision

Do not retry F5, relax its gates, change its seed/loss/epochs, or enter K.
The failure contains two distinct observed problems: persistent transfer failure
on the held source groups, and loss of previously correct rare training attacks.
There are confirmed coverage and information-contract gaps in the design.
There is no demonstrated one-line implementation repair, nor evidence that one
larger model or one weight change would solve both problems.

This review identifies structural mechanisms and narrows the causal hypotheses.
It does not claim a unique causal attribution or prove that every F4-input
classifier must fail. No new candidate or success criterion is introduced.

## Scope and immutable evidence

The user requested cause investigation after T failed. The review read existing
F5 P/T receipts, all 20 epoch ledgers, the hash-verified terminal `resume.pt`
to recover its saved batch ledger, F4 parent metadata/schema/features, and source
code as text. It did not instantiate or forward a model, calculate new teacher
scores, backpropagate, optimize, decode raw captures, or open outer validation,
kill-only, select, viewed/report or FINAL numeric data.

Reproducible forensic package:
`runs/frontend_f5_failure_forensics_20260907/` contains
`analyze_saved_evidence.py`, `analysis.json`, `evidence_identity.json`, `SHA256SUMS`.
The original F5 final manifest verified 17/17 before and after analysis. Parent
files were checked against the P identity manifest. All 3,120 batch records,
20 epoch records and saved optimizer step counters agree with the terminal.
Frozen runner/core/operator source files and the sealed scientific output were
not edited. Exploratory console reads preceded the durable package; its scope
fields describe the packaged script, not total read counts across the chat.

## 1. Confirmed training coverage gap; shortcut mechanism remains a hypothesis

F5 training contains 2,000 ToN attack targets in 1,998 contexts from
`password_normal1.pcap`, and zero ToN benign targets, across both A and B.
The file's spelling does not override the frozen attack labels.

Internal validation contains 843 old-correct A ToN benign targets in 672
contexts from `normal_1.pcap`. All 843 are false positives at epoch 20;
839 are false positives in every epoch. The other 635 old-correct A validation
benign targets, from the two IoT normal source groups, are all correct at epoch 20.

The four A/B x label objective groups do not balance the source-by-label table.
The model never receives a ToN benign training label or its teacher constraint.
Source identity itself is excluded from model input, but packet patterns can
still correlate with source and label. Thus a source-correlated shortcut is
consistent with the observations; actual reliance on a specific field or source
cue has not been established by a counterfactual model test.

Do not fix this by moving the exposed validation normal targets into F5 training
and claiming the same validation result. Any later coverage design must preserve
this failed experiment and independently declare legal development/confirmation
roles. The coverage gap alone cannot prove that generalization was impossible.

## 2. Confirmed teacher/student information mismatch

F4 losslessness is relative to its selected 19 L1 fields. It does not establish
losslessness relative to the old teacher's inputs, history, representation or
pretrained knowledge. The old E3 is the pinned netFound encoder plus P2, not F5's
new GRU and head. Source inspection confirms:

| Aspect | Old E3 input construction | F5 input |
|---|---|---|
| IP header | header length, TOS/traffic class, IP total length, IP flags, TTL/hop limit | selected protocol/length/presence fields; these old header fields are not preserved as the same fields |
| TCP header | flags, window, relative sequence/acknowledgment, urgent pointer | flags and transport length; no window, sequence/acknowledgment or urgent pointer |
| History | retained initial direction-specific bursts; session duration | current semantic-context prefix with reset state |
| Time | burst timing and duration from timestamps | binned delta and quantized log2-microsecond value within context |

See `issue27ckda_d0_resource_pilot_v1.py::netfound_flow`,
`issue27ckda_d1_e3_embed_v1.py::BoundedNetfoundPrefix`, and the F4 schema.
The actual two-pass wrapper uses the same bounded state and flow construction.
No raw endpoint values or payload are proposed for F5 by this observation.

F5 contexts reset at >256 events, >60-second idle or >300-second span under
the inherited semantics. The student starts GRU state at zero. The old bounded
session representation retains early bursts rather than resetting at those
same boundaries. Of the 843 failed ToN normal targets, 824 are in context
epochs after zero. All three failed A validation attacks are also after a reset.
However 19 ToN errors and all five final train errors occur in epoch zero;
history reset cannot be the sole explanation of all failures.

The old input generally cannot be reconstructed from F4's chosen fields/current
context. This is a confirmed information-contract gap. Whether the missing
information is necessary for the particular teacher decisions remains unproved:
no new teacher comparison or fixed-model intervention was performed. F4's zero
exact mixed-label collisions still stands; near-input difficulty is not an exact
contradiction and does not prove mathematical nonseparability.

## 3. Confirmed loss of previously learned training behavior

Five final A attack errors share one 11-event TCP context from
`processed/iotsim-ip-camera-museum-1.csv`; targets are at prefix lengths
4, 6, 7, 9 and 11. They are not old-UNK targets. All five canonical teacher
strengths are 6, so missing/weak distillation targets do not explain them.

These five targets pass at the ends of epochs 1 and 2. In epoch 3, their context
appears in batch 26, whose recorded pre-update attack worst penalty is zero.
The frozen formula makes this equivalent to q>=1 for every attack in that
batch. At epoch 3 end all five are wrong. At least one optimization update
between that measurement and epoch end destroyed the correct decisions.
The saved records do not isolate which update (including the same batch's
update), component, or gradient direction caused the change.

Context order was independently regenerated from seed 2705+epoch and the exact
sorted keys. Each context appears once per epoch; the rare one gets one of
156 batches per epoch, for 20 presentations total. Its batch worst term is
absent from the other 155 batches, so it is not a continuously enforced global
constraint. The implementation matches the frozen design on this point.

At epochs 18/19/20, the batch containing this context has preclip gradient norms
16.6679/14.9709/15.9119. The global norm-1 clip applies scale factors about
0.0600/0.0668/0.0628. In epoch 7 that batch reaches preclip norm 29,531.16.
These are gradients before clipping, not exploding applied updates, and do not
justify removing the clip. Other samples share each batch; its gradient and
worst penalty cannot be uniquely attributed to the five targets.

Context balancing gives A-attack count 2,149 but B-attack count 27. In a full
32-context batch their group estimators use 4984/(32*2149) and 4984/(32*27),
respectively. The latter is about 79.6 times larger per eligible context,
before the equal group coefficient. This is intentional balancing, not a
denominator bug; it can produce uneven optimization pressure but its causal
contribution here is not established by the ledger alone.

## 4. Concrete near-input conflict, not an exact collision

For failed train attack `support_train:fit:201`, the nearest equal-length
training benign prefix in frozen-coordinate mean-square distance is
`aux:aux_fit:iotsim-building-monitor-5_0-0_to_OpenvSwitch-28_5-0:106`.
The first three events are identical in F4 coordinates. The fourth differs
only in frame length (70 vs 80), transport length (4 vs 14), and log2-microsecond
delta bin (5 vs 6). Protocol, directions and TCP flag sequence are identical.
Both have teacher strength 6, requiring opposite logit margins for zero teacher
loss: attack q>=6, benign q<=-6.

The raw-coordinate mean-square difference is 4.778294815e-6. This number is
descriptive, not a calibrated semantic metric. The distinct inputs are in
principle separable; there is no proof of impossible inheritance. The example
does demonstrate that strong opposite teacher constraints can be presented
through very similar reduced observations. F4 round-trip success alone did not
address the stability or generalizability of learning that distinction.

## 5. Implementation audit: findings and limits

Static review found the following code aligned with the frozen specification:
metadata/source/UID joins before parent decoding; target prefix truncation;
packed-sequence sorting and inverse restoration; per-context zero state;
label loss sign and q>=0 decision; canonical teacher widening/clipping/null
semantics; fixed global context denominators; attack batch maximum; auxiliary
field slice offsets and t->t+1 alignment; separate no-grad train/validation
evaluation; eligibility and 20-epoch/12-patience stop.

This is a targeted audit, not a proof that no implementation defect exists.
No synthetic test suite or resource pilot was rerun. Stage I already covered
those mechanical behaviors. No newly found discrepancy justifies reclassifying
the frozen scientific failure as a repaired run. The stored margins also show
substantial errors (final worst train attack -5.7788, val A attack -4.2277,
val protected benign -25.5228), not merely display rounding around zero.

## Next research gate

The first task is to specify what old capability must be learnable from which
past-only inputs and legal training coverage. Do not select a new network first.
The review should address both persistent transfer failure and rare-context
retention; fixing only one does not satisfy inheritance.

Before any new run, an explicit diagnostic/design proposal should:

1. Map old teacher information/history to a deployable shared A+B interface,
   explaining each omitted item and the evidence supporting its omission.
2. Define how legal training evidence represents normal and attack behavior
   without turning exposed validation/report/FINAL into training or confirmation.
3. Provide a falsifiable way to distinguish missing information/coverage from
   optimization interference; declare any necessary extra input/model opens.
4. State a preservation mechanism and acceptance/stop gates before outcomes,
   with no promise that a soft penalty alone guarantees zero regressions.

These are prerequisites for a new proposal, not authorization to add fields,
data, replay the teacher, train a variant or replace the failed result. The
incumbent remains intact. New-device commissioning is still a subsequent
question and cannot substitute for demonstrated inheritance.
