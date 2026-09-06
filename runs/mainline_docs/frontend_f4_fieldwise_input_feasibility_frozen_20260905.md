# Frontend-F4 fieldwise input feasibility: FROZEN

Date: 2026-09-05

Design finalization: 2026-09-06 (no F4 vectors computed).

Freeze provenance: mechanical draft-to-FROZEN transition under the user's existing implementation authorization; scientific rules and numerical constants unchanged.

Status: `FROZEN_BEFORE_FIELDWISE_INPUT_EXECUTION`

Design scope: one deterministic representation of the existing F3 L1 fields.

Training authorization: **false**.

## 1. Decision, lineage, and existing authorization

F3 stopped because a train-only whole-signature vocabulary erased unseen
combinations. F4 asks whether a fixed fieldwise mapping preserves those same
L1 strings exactly in finite float32 model inputs, including combinations not
seen in training. It adds no packet field, context, or data source.

This is a successor contract, not a revision of F3, CE, ZT, or F1. F3 remains
`F3_FULL_FIT_L1_NO_GO`. F4 is motivated by exposed F3 results and is not a
prospective replication of that discovery. Its real-data PASS is an input
engineering feasibility result, not inherited attack capability or an OOD
result.

The user's 2026-09-05 authorization covers: F3 closure, this design, and Sol
High implementation, synthetic tests, and a no-model audit after the protocol
is explicit. A further permission request is not needed for that same scope.
Before any real F4 feature vector is computed, the implementation turn must
mechanically copy this completed draft to
`frontend_f4_fieldwise_input_feasibility_frozen_20260905.md`, changing only this
title/status and adding the freeze provenance, then create its SHA sidecar.
No scientific blank, tunable default, or numerical choice is delegated to the
implementer. Any necessary scientific amendment must be identified before
execution and cannot silently rewrite an existing result.

PASS permits a future training **draft** only. Neither a GRU, a student head,
the old P2, a normalizer, a teacher score, nor a learned embedding is opened or
computed by F4. The proposed later direction is a small shared encoder and
student head with label-aware teacher constraints; it has no authorization or
numerical training contract here and is not automatically a CE deployment.

## 2. Exact input allowlist

All paths are relative to
`D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline`.
The common result prefix below is
`runs/frontend_f3_full_fit_l1_identifiability_v1_20260905/`.

| Object under common prefix | SHA-256 |
|---|---|
| `SHA256SUMS` | `a294d93bfe2fdb9c221f3589e3a8da877e9ae8679ad6102e35c8f4323165e1c1` |
| `f3b_l1_contexts.jsonl.gz` | `87383b24ff506edfb6561b3aa24776ce5c46f8c4c6d274c301f4b6c6e3337b01` |
| `f3b_target_prefix_audit.csv.gz` | `fdd9eeb75170fe30affb71b5a25b5f2dcb5e5c3ac5efecad4dc72d7fc7e5d1bd` |
| `f3b_identities.json` | `073b28f5f3617d8c2c1ff0fd919cd02116b961d35ccc7ea5de6e7581d03f2b09` |
| `f3b_verdict.json` | `6975f2a56526b7cb71982039486919c8cd963ba99799806209183d28ed3a0d11` |
| `f3b_kill_only_audit.csv` | `e6b7bf6f5288cbf288caf9a7378adf7061afccfa48cd0a1ef223e55f4b4c98c9` |
| `f3b_nested_split_census.csv` | `29f03e8408cdf1c9eadc0071dc138cc6faa0232ed1dd40f145c41ced2b6e1514` |
| `checkpoints/6c1c4e7926631066034dae98.jsonl.gz` | `f2f88316954366070b0f4f249c2f45b7d3a749c23c522f5f76ee3b6cd7071d2c` |

The last object supplies only the five already exposed kill-only prefixes.
It must contain exactly the five UIDs in `f3b_kill_only_audit.csv`, with
`scope=kill_only`, unique contexts, and matching event counts/source. Only its
`l1_signatures` are input to the field encoder; its other columns are audit
metadata. No other member checkpoint is needed for F4.

Source files may be read as text for grammar provenance, never imported as
runtime modules:

- `repo/ood/issue27frontend_f1_d1_train_v1.py`, SHA
  `6e2df7059b9bb0aba9be80adb11e7e918c3f1ddfef3ecc690b571b0f0af18634`;
- `repo/ood/issue27frontend_f3_full_fit_l1_identifiability_v1.py`, SHA
  `69fc92fb417fe8dbca646c30aaaf7f7ea40edf81ecae3c4fe36d831434e35a67`;
- `repo/ood/issue27frontend_f0_zero_training_semantics_real_v1.py`, SHA
  `ca34ff39bfe7289fee1048d74e04de53dd4d4f096228fa837104cb65388b6f60`.

The F3 package manifest may be verified against its immediate listed files;
that is byte hashing only. Runtime numeric parsing is confined to the objects
listed above. No PCAP, archive, model, original fit/select NPZ, old score,
unrelated F1 internal-validation row, select, report, or FINAL is an input.
No network access, TShark process, corpus resplit, data-dependent vocabulary,
fit mean/variance, optimizer, or learned parameter is permitted.

## 3. Denominators and role handling

- Parent F1 train universe: exactly 13,866 targets / 9,307 contexts.
- Inherited nested train: 8,660 targets / 4,984 contexts.
- Inherited nested internal validation: 5,206 targets / 4,323 contexts.
- Five exposed attacks: 5 separate kill-only contexts, excluded from training
  artifacts, feature-distribution summaries, and all positive evidence.
- Source assignments are copied and cross-checked against
  `f3b_identities.json`; the salt/source selection is not rerun or changed.
- Cross-context, duplicate UID, duplicate event-index/UID, unknown role,
  source disagreement, or changed target membership is an identity failure.

Each context contains the saved L1 event sequence. A target at zero-based index
`j` consumes exactly `signatures[:j+1]`, with `1 <= j+1 <= len(signatures) <= 256`.
Future events are never included in a target prefix. A batching PAD row is all
zeros with a separate valid-event mask; padding is never an observed event and
never included in prefix hashes or statistics. Contexts never concatenate
without offsets and independent sequence boundaries.

The input JSON already contains labels/teacher categories. Reading that
container must be disclosed; do not claim physically label-free file access.
Only its signature strings enter the pure encoding function. Labels, source,
device/family, owner, UID, context key, nested role, teacher category, and
previous decisions are used solely for joins, splits, denominator summaries,
and collision checks. They are never feature coordinates.

The category table is inherited, with its exposed status:

| Side | A protected attack contexts | A protected benign contexts | B attack contexts | B benign contexts |
|---|---:|---:|---:|---:|
| Train | 2,149 | 1,851 | 27 | 957 |
| Internal validation | 1 | 993 | 2 | 3,327 |

Category predicates are literal: `a_protected_attack` means owner A,
label 1, teacher_kind `attack_hard`; `a_protected_benign` means owner A,
label 0, teacher_kind `benign_normal`; `b_attack` and `b_benign` mean owner B,
teacher_kind `none`, with labels 1 and 0 respectively. A label-0 row with
teacher_kind `benign_hard` is `a_unprotected_benign`: retain it, but do not
silently include it in the protected-benign count or drop it from encoding.
Other owner/label/teacher combinations are identity failures. A context counts
once in each category for which it contains an eligible target; category
context counts need not be a disjoint partition.

Target conservation, including the unprotected A benign rows, is:

| Side | A protected attack | A protected benign | A unprotected benign | B attack | B benign | Total |
|---|---:|---:|---:|---:|---:|---:|
| Train | 2,179 | 4,667 | 24 | 68 | 1,722 | 8,660 |
| Internal validation | 3 | 1,478 | 2 | 3 | 3,720 | 5,206 |

This table is an identity cross-check, not a claim of adequate statistical
power. One internal-validation A attack context / three rows cannot certify
general inheritance. Future model selection must acknowledge these exposed
development roles and independently identify any untouched confirmation data.

## 4. Strict L1 grammar

Split a signature by the literal U+001F character. It must have exactly 19
components, in the source order below. No stripping, case folding, aliasing,
unknown-field omission, generic OTHER fallback, or delimiter repair is allowed.
Canonical decimal integers match ASCII `0|[1-9][0-9]*` in full;
signs, leading zeros, whitespace, floats, NaN, and infinity are invalid.

The final four components must retain their literal names in this order:
`FRAME_LEN=`, `DELTA_LOG2_US=`, `TRANSPORT_LEN=`, `TCP_FLAGS=`.
`NONE`, `ZERO`, `none`, and `encap:unknown` have distinct, case-sensitive meanings.

| Index | Component | Domain / fixed category order |
|---:|---|---|
| 0 | context tier | `H1,H2,H3,H4` |
| 1 | direction | `A_TO_B,B_TO_A,UNKNOWN` |
| 2 | link type | `encap:` followed by UInt32, or `encap:unknown` |
| 3 | EtherType | UInt16 or `NONE` |
| 4 | IP version | `NONE,4,6` |
| 5 | IP protocol | UInt8 or `NONE` |
| 6 | protocol group | `TCP,UDP,ICMP,GRE,OTHER_IP,NON_IP,KEYLESS` |
| 7 | transport ports present | `false,true` |
| 8 | field-presence mask | exact canonical mask from section 5 |
| 9 | original length bin | `<=63,64-127,128-255,256-511,512-1023,1024-1518,1519-4095,>=4096` |
| 10 | original delta bin | `0,(0,1e-6],(1e-6,1e-3],(1e-3,1e-2],(1e-2,1e-1],(1e-1,1],(1,10],(10,60],>60` |
| 11 | timestamp regression event | `false,true` |
| 12 | ICMP type | UInt8 or `NONE` |
| 13 | ICMP code | UInt8 or `NONE` |
| 14 | GRE key present | `false,true` |
| 15 | exact frame length | UInt32 |
| 16 | delta log2 microseconds | UInt8 exponent or `ZERO` |
| 17 | transport length | UInt32 or `NONE` |
| 18 | TCP flags | UInt16 or `NONE` |

UInt8/16/32 mean closed intervals `0..255`, `0..65535`, and
`0..4294967295`. These storage-width bounds are fixed here before F4 feature
computation; they are not fitted to observed ranges. An otherwise canonical
integer outside its bound is a named domain failure. Do not clip, wrap, replace
it by zero, or widen the bound in the same run. Negative values are invalid
under this grammar. The delta exponent follows frozen F3's nonnegative
`floor(log2(max(1,round(delta*1e6))))`; F4 does not recover or recompute timestamps.

Preserve every original component, including redundant length/delta bins,
presence bits, and protocol group. Do not reconstruct a finer field from a
coarser one. Validation checks the length bin against the exact frame length
using the listed boundaries. It does not infer finer delta from its log bucket.

## 5. Fixed feature map: exactly 131 float32 coordinates per event

All offsets below are zero-based and ranges are half-open. There is no learned
lookup table, fitted scaler, signature vocabulary, hash bucket, or UNK feature.

Primitive encodings:

1. `OH(c, order)` is a one-hot vector in the listed fixed order.
2. `BOOL(false)=0`, `BOOL(true)=1`.
3. `BITS_w(x)[k] = (x >> k) & 1`, `k=0..w-1` (least significant bit first).
   Optional bit encoding is `[present, BITS_w(x)]`; `NONE` is all zeros, while
   present numeric zero has `present=1`.
4. For UInt32 `x`, define `hi=x//65536`, `lo=x%65536`.
   `U32(x)=[hi/65536, lo/65536, math.log2(1+x)/32]`.
   Division is in Python binary64, then coordinates are rounded once to
   IEEE-754 float32. Both limb coordinates are exactly representable in
   float32 and independently preserve all 32 integer bits. The log coordinate
   supplies an ordered magnitude feature; it is not used to recover the integer.
5. Optional UInt32 length is `[present,U32(x)]`; `NONE` is four zeros.
6. Link type has three coordinates `[known,hi/65536,lo/65536]`, with UInt32
   limbs as above. `encap:unknown` is three zeros. No log coordinate for a link
   enumeration code.
7. Delta exponent is `[is_zero, exponent/256]`. `ZERO` maps to `[1,0]`;
   exponent `0` maps to `[0,0]`. Every valid exponent remains exact in float32.

For the field-presence mask use 21 bits in this exact order:

```text
eth.dst,eth.src,eth.type,frame.encap_type,gre.key,
icmp.code,icmp.type,icmpv6.code,icmpv6.type,
ip.dst,ip.proto,ip.src,ipv6.dst,ipv6.nxt,ipv6.src,
sctp.dstport,sctp.srcport,tcp.dstport,tcp.srcport,udp.dstport,udp.srcport
```

`none` means 21 zero bits. Otherwise the string is the nonempty lexicographically
sorted, duplicate-free subset of these names joined by `|`; its exact spelling
must be recovered by the inverse map. These are field-presence indicators, not
the IP/MAC/port values. Unknown names, duplicate names, or noncanonical order
are schema failures. TCP flags/data length were not in the inherited base mask
and must not be added to this list.

| Offsets | Component | Encoding | Width |
|---|---|---|---:|
| `[0,4)` | tier | one-hot | 4 |
| `[4,7)` | direction | one-hot | 3 |
| `[7,10)` | link type | optional UInt32 limbs | 3 |
| `[10,27)` | EtherType | optional 16 bits | 17 |
| `[27,30)` | IP version | one-hot | 3 |
| `[30,39)` | IP protocol | optional 8 bits | 9 |
| `[39,46)` | protocol group | one-hot | 7 |
| `[46,47)` | ports present | boolean | 1 |
| `[47,68)` | field-presence mask | 21 bits | 21 |
| `[68,76)` | length bin | one-hot | 8 |
| `[76,85)` | delta bin | one-hot | 9 |
| `[85,86)` | regression flag | boolean | 1 |
| `[86,95)` | ICMP type | optional 8 bits | 9 |
| `[95,104)` | ICMP code | optional 8 bits | 9 |
| `[104,105)` | GRE key present | boolean | 1 |
| `[105,108)` | frame length | UInt32 limbs + log | 3 |
| `[108,110)` | delta exponent | zero flag + fixed scalar | 2 |
| `[110,114)` | transport length | optional UInt32 limbs + log | 4 |
| `[114,131)` | TCP flags | optional 16 bits | 17 |

The inverse decoder recovers the original 19 components from the one-hots,
bits, flags, and integer limbs. It ignores the two log coordinates when
recovering integers, then checks them against re-encoding under the same
runtime. All source strings must round-trip exactly. Thus NONE/zero,
ZERO/exponent-zero, and different exact lengths cannot silently merge through
float32 rounding. No float16, bfloat16, quantization, feature dropping,
learned embedding, dimensionality reduction, or normalization is part of F4.

The use of existing L1 fields does not certify that they are free of source
shortcuts. No source/class-dependent feature choice is allowed; this audit
does not estimate performance or choose a downstream architecture.

## 6. Pure interfaces and execution order

Required pure interfaces (names may be used verbatim):

```text
parse_l1(signature: str) -> typed record with exactly the 19 declared fields
encode_event(typed_record) -> float32[131]
decode_event(float32[131]) -> canonical L1 string
encode_context(sequence_of_signatures) -> float32[n,131], 1 <= n <= 256
prefix_bytes(context_matrix, target_event_index) -> bytes
```

The typed record has these exact keys in source order:
`tier,direction,link_type,ethertype,ip_version,ip_protocol,protocol_group,
ports_present,presence_mask,length_bin,delta_bin,regression,icmp_type,
icmp_code,gre_key_present,frame_len,delta_log2_us,transport_len,tcp_flags`.
Use Python integers (not bools) for numeric values, `None` for optional
`NONE`/`encap:unknown`, a frozenset of field names for `presence_mask`, bools
for boolean fields, and strings for named categories. `link_type` is the
parsed optional integer without `encap:`; `delta_log2_us` is either the literal
string `ZERO` or an integer. `ip_version` is `None`, 4, or 6. Reject extra keys,
missing keys, or wrong types. Reconstruction restores the frozen string syntax.

`encode_event` accepts only the typed record, not a context/target metadata
dictionary. Enums, bounds, offsets, optionality, and primitives must also be
published as `f4_schema.json`. Build that schema from constants and write it
before parsing real signatures. Record its SHA in every result identity.

Execution order:

1. Verify the F4 frozen protocol SHA, implementation/test identities, and the
   fixed input hashes. Refuse an existing completed output directory.
2. Write schema and input-access intent; run the complete synthetic battery.
   No real feature computation precedes these checks.
3. Parse parent context containers with an explicit metadata/feature split.
   Verify UID/context/source/role/event-index membership against F3 audits.
4. Encode each parent context in `context_key` order, in its existing event
   order. No corpus statistics determine the encoding. Check each event's
   exact round trip, finite coordinates, width, and prefix identities.
5. Cross-check inherited split/category counts and compute parent prefix
   collision statistics using labels only in the audit layer.
6. Open the single five-row kill-only checkpoint only after the schema and
   parent computations are complete. Apply the identical encoder. It may kill
   the candidate; it never determines fields, scales, widths, or schema choices.
7. Finalize typed feature files and reports atomically. Write the verdict last
   and `SHA256SUMS` only after all terminal artifacts are complete.

The live phase/source metadata is physically accessible during this process,
but it has zero access to encoding decisions. Record actual container/label
parsing rather than fictional zero-open counters.

## 7. Mechanical gates and honest interpretation

All success gates are conjunctive:

G1. All pins, UID/context memberships, inherited splits, and target/event-index
counts are exact. No dropped/duplicated/reassigned row.

G2. Every parent and kill-only event lies in the declared grammar/domain,
encodes to 131 finite float32 coordinates, and round-trips byte-exactly to its
original signature. Success requires 100% over this scoped universe. No row
filtering or revised device denominator is allowed.

G3. The mapping creates zero new event or prefix collisions: distinct canonical
L1 strings/prefixes must never share the same feature bytes. Parent feature
prefixes must also contain zero mixed-label buckets, with the raw-L1 comparison
reported alongside. Hashes are indexes; a matching hash is confirmed with the
underlying strings/bytes before counting a collision.

G4. Each target prefix in the published artifact equals the first `j+1` rows
of the same encoded context. Appending/changing future events, permuting
unrelated contexts, or changing audit-only metadata cannot alter these bytes.

G5. The encoder makes zero vocabulary queries, learns zero numerical constants,
uses zero forbidden feature columns, and makes zero model/score/optimizer or
network/PCAP calls. Valid unseen combinations are encoded by the same pure
map; malformed values stop instead of becoming UNK.

G6. For each of the five exposed attacks, its feature prefix is finite,
round-trip exact, and not equal to any nested-train benign feature prefix.
Report individually, separately from parent counts. Absence of a collision
is not positive evidence of attack retention.

G7. The synthetic regression battery is complete and passes. Its fixtures are
constructed from the declared grammar, not copied from real problematic rows.

G8. Resource and serialization requirements in section 9 pass.

Mandatory descriptive outputs, never success thresholds: per-source/owner/
label/attack-family/context-tier coverage; scoped target and context counts;
unique signatures and unique feature vectors; number of old all-UNK targets
now represented losslessly; unchanged tiny attack-validation support. Any
comparison with F3 refers to exposed development evidence. No real observed
recovery count is hard-coded as an expected test outcome.

The old `>=1 known token` gate has no meaning in a dictionary-free map. G2/G3
replace it with a stronger information-preservation check, without relabeling
F3's failure as a pass. The replacement is declared here before new F4 vectors
exist. A finite constant vector cannot pass round-trip/injectivity checks.

## 8. Terminal states

| State | Trigger | Consequence |
|---|---|---|
| `F4_FIELDWISE_INPUT_PASS` | All gates pass | Input artifact is eligible only for a future training draft |
| `F4_FIELD_DOMAIN_UNSUPPORTED` | A canonical real integer lies outside its width or numeric-enum domain (including an IP version other than 4/6) | Stop; no widening, clipping, or alternate encoding in this run |
| `F4_FIELDWISE_INPUT_NO_GO` | A conforming implementation fails an input collision or other scientific feasibility gate | Stop; no fallback or training |
| `F4_RESOURCE_NO_GO` | A section 9 resource cap is exceeded | Stop; record measured need, no automatic cap increase |
| `F4_ENGINEERING_FAILURE` | SHA/schema/corpus identity drift, incomplete writes, implementation bug, or contract-test failure | No scientific verdict; repair engineering cause and rerun identical science if authorized |

An invalid one-hot, lossy integer conversion, missed optional flag, or wrong
offset in the implementation is an engineering failure, not a negative
scientific conclusion. A genuinely out-of-domain canonical input is a domain
stop. Unknown feature names, malformed strings, or replay identity disagreement
are schema/identity failures. Do not emit PASS or NO_GO from incomplete output.
Unlisted nonnumeric category literals are schema failures, not new aliases.
Stop at the first failed execution phase in section 6. Within a phase, validate
identity/schema before assessing scientific gates; an implementation or
integrity error takes precedence over any apparent scientific failure. Do not
continue to the kill-only phase after a parent failure. Unvisited gates are
`NOT_EVALUATED`, never false measurements or implicit passes.

Successful F4 checks do not authorize teacher-logit materialization, a model
forward pass, a random-weight model, training, select scoring, commissioning,
external download, HPC, report evaluation, or FINAL access.

## 9. Runtime, resource, and durable artifact contract

Use existing Python >=3.9 and stdlib, plus installed NumPy if useful. No new
packages are needed. Pin/report the actual interpreter and NumPy versions.
Do not import F1/F2/F3 runners, torch, sklearn, or any module with model/data
side effects. Source code provenance can be checked with byte hashes/text.

Runtime caps are fixed: 1,800 seconds wall time, 4 GiB peak working set,
2 GiB durable output, and at least 3 GiB free on the destination before launch.
Check time/memory/output at least every 100 contexts and at phase boundaries.
The time cap covers the whole runner, including preflight and tests. Memory is
OS process peak working set (on Windows, `PeakWorkingSetSize`), not Python-only
allocation tracking; unavailable resource measurements stop as engineering
failures. No subprocess is needed. Equality to a maximum cap passes; exceeding
it stops. Output size includes partial files in this attempt. The resolved
output directory must remain beneath the named worktree `runs/` directory.
Use context-wise streaming to avoid copying every target's complete prefix.
The output stays under this worktree's `runs/`; no existing dataset/cache is
deleted or relocated to satisfy a resource gate.

Logical feature bytes use C-contiguous, little-endian IEEE float32, with no
object dtype and no pickle. `prefix_sha256` hashes:

```text
b"F4_INPUT_V1\0" + struct.pack("<II", prefix_event_count, 131)
                   + prefix_matrix.astype("<f4").tobytes(order="C")
```

The real-event binary contains contexts sorted by `context_key`, with original
event order retained. `f4_context_index.csv` gives row offsets/counts into it.
The kill-only binary/index is a separate artifact and never appends to train
or internal-validation files. Offsets are row offsets, not byte offsets.
Feature arrays must contain no metadata or labels. The index is an audit join
and is never a model input.

For comparison with the saved F3 `l1_prefix_sha`, use its exact preimage:
`json.dumps(signature_list, sort_keys=True, separators=(",", ":"),
ensure_ascii=True).encode("utf-8")`. No newline is appended. The binary feature
prefix hash deliberately has a different preimage and must not be compared
to this string hash for equality; each is checked against its own reconstruction.

Required outputs in a new directory
`runs/frontend_f4_fieldwise_input_feasibility_v1_20260905/`:

1. `f4_schema.json`: version, 19 source fields, explicit offsets, enum orders,
   integer bounds, optional encodings, 131 width, float/serialization rules.
2. `f4_inputs_and_runtime.json`: exact input/schema/code/test/runtime identities,
   user authorization scope, and role-access facts.
3. `f4_parent_features.f32le` and `f4_context_index.csv`: parent context inputs;
   index columns `context_key,source_group,nested_split,event_offset,event_count`.
4. `f4_target_audit.csv.gz`: columns
   `uid,context_key,event_index,source_group,nested_split,owner,label,teacher_kind,device_family,attack_family,l1_prefix_sha256,feature_prefix_sha256,prefix_events,old_all_unk,roundtrip_exact,finite,feature_width`.
5. `f4_coverage.csv`: grouped counts by `group_kind,group_value,nested_split`,
   with `targets,contexts,encoded_targets,roundtrip_targets,old_all_unk_targets`.
   Group kinds are `source,owner,label,device_family,attack_family,context_tier`; when a
   grouping spans multiple roles, output each role separately.
   `context_tier` is component 0 of the target event's own signature (index j),
   never derived from events after that target.
6. `f4_collision_audit.csv`: `scope,collision_kind,canonical_prefix_sha256,feature_prefix_sha256,uid,label`; emit a header-only file when none.
   Event-only collisions use `uid=""`, `label=""` and are separately counted.
7. `f4_nested_split_census.csv`: independently recompute the four inherited
   category counts per side and the extra `a_unprotected_benign` category;
   columns `nested_split,category,targets,contexts`. Verify the original four
   context counts against F3; retain all five categories for target conservation.
8. `f4_kill_only_features.f32le`, `f4_kill_only_index.csv`,
   `f4_kill_only_audit.csv`: five-row audit with
   `uid,context_key,prefix_events,old_known_events,old_unk_events,roundtrip_exact,finite,feature_prefix_sha256,collides_with_nested_train_benign`.
   Kill-only index columns are `uid,context_key,event_offset,event_count`.
9. `f4_synthetic_contract_tests.json`: per-test identity and result; no fixtures
   from real target values.
10. `f4_role_open_audit.json`: actual input container counts; label metadata
    parsed for audits; feature uses of labels/UID/source/owner/role/teacher all
    zero; PCAP/network/model/score/learned-representation/optimizer counters zero.
11. `f4_verdict.json`: terminal state, all gates, denominators, resource maxima,
    collision counts, descriptive old-UNK recovery, five-row kill-only results,
    and `claim_ceiling="LOSSLESS_FIELD_INPUT_ON_EXPOSED_DEVELOPMENT_UNIVERSE"`.
    Always set `training_authorized=false` and
    `positive_attack_generalization_evidence=false`. On a scientific/resource
    stop, publish only a complete failure receipt and the actually completed
    audits; record every partial/absent artifact and unvisited gate explicitly.
    Such a manifest is a failure package, never a complete input artifact.
12. `SHA256SUMS`: all durable immediate result files except itself, sorted by
    filename. Runtime timing fields need not be byte-identical across reruns;
    schema, encoded feature bytes, and scientific tables must be deterministic
    under the same implementation/runtime.

Write through temporary files and atomic replacement. Leave failures in a
separate attempt directory or preserve numbered engineering receipts; never
overwrite a completed PASS/NO_GO directory. No partial member checkpoint is
needed for this small offline audit. An engineering rerun must reuse the same
frozen schema and inputs and document the cause.

## 10. Synthetic contract battery: 28 requirements

1. Exactly 19 components accepted; too few/many rejected.
2. Final four literal names/order enforced, including L2/L3 rejection.
3. Every declared categorical value round-trips; invalid category rejected.
4. UInt8/16/32 boundary zero/max values round-trip; max+1 stops.
5. Leading zeros, whitespace, signed numbers, fractional values, NaN/inf rejected.
6. NONE differs from numeric zero in every optional field.
7. ZERO delta differs from exponent zero; exponent max round-trips.
8. UInt32 values on both sides of 65536 and 2^24, and maximum UInt32,
   remain distinct after float32 conversion and binary serialization.
9. Length log coordinate uses the stated formula; integer recovery uses limbs.
10. TCP flags reconstruct exactly, including each individual bit and zero/NONE.
11. Presence-mask empty/subsets/all bits reconstruct; unknown, duplicate, and
    unsorted names are rejected.
12. Encapsulation unknown differs from code zero; max code round-trips.
13. Schema offsets are contiguous and sum exactly to 131; dtype is float32.
14. Lossy/corrupted coordinates, invalid one-hot, NaN/inf, and invalid optional
    masks are rejected by inverse validation.
15. A valid unseen combination of already-declared field values encodes without
    dictionary construction or UNK; distinct strings retain distinct bytes.
16. Changing a single exact frame/transport length retains that difference.
17. An event cannot become an all-zero observed row; PAD is mask-separated.
18. Exact string -> float32 bytes -> inverse -> string round trip on H1-H4
    fixtures, including ICMP, GRE, keyless, and present/absent transport fields.
19. Target prefix unaffected by appending/changing future events.
20. Context processing order and unrelated context contents cannot affect inputs.
21. Changing audit-only UID/source/label/owner/teacher/split cannot affect features;
    the pure encoder rejects extra typed-record keys.
22. Saved row offsets and prefix counts reproduce each target prefix exactly;
    index out of range and duplicate UID fail.
23. Inject a feature collision using a deliberately defective encoder; detector
    identifies it and cannot report PASS. No real data are used by this test.
24. Inject mixed labels on equal canonical prefixes; audit identifies them;
    equal inputs with the same label do not create a mixed-label collision.
25. Kill-only input is opened after parent/schema processing; it cannot enter
    parent arrays, summaries, or source selection.
26. Wrong input/protocol SHA, unlisted paths, and a completed output directory
    fail before real feature construction. A synthetic sentinel records this.
27. Test wall/memory/disk cap boundaries with injected measurements; no real
    high-resource stress is required.
28. Import/IO sentinel verifies no torch/sklearn, model, score, NPZ, PCAP,
    network, or optimizer path is invoked. Failure output has no scientific
    verdict; deterministic arrays survive a same-input repeat.

Implement meaningful assertions, including negative and boundary cases. Do not
set pass expectations to 3,173 recovered targets, 1,001 signatures, or the real
five-row failure pattern. Those observed F3 quantities are descriptive outputs.

## 11. Handoff and later decision

The implementing model is requested to use Sol High. It should read this
protocol and the F3 closure, produce the mechanical FROZEN copy/sidecar, write
the narrow encoder/runner/tests, and execute only this no-model audit under the
existing authorization. A short source review must check the pure feature
boundary, float32 injectivity, inherited roles, and kill-only ordering before
the real run.

If this passes, the next deliverable is a separate one-shot training design.
That design must decide a genuinely unified student interface and teacher
losses, preserve attacks without copying known benign errors, disclose sparse
validation support, and specify untouched confirmation. No F4 output alone
selects a classifier, justifies a claim about hydraulic, changes CE deployment,
or closes the new-device benign/attack pairing gap.


