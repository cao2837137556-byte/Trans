# Frontend-F0 Step-0b Causal Re-decode Attribution Audit — Preregistration Draft

- Date: 2026-08-29
- Status: **DRAFT — NOT EXECUTABLE**
- Route: Frontend-F0 / Step-0b
- Parent frozen protocol: `frontend_f0_missingness_mechanism_audit_frozen_20260828.md`
- Parent result: `NO_IDENTIFIABLE_MISSINGNESS_MECHANISM_WITHOUT_REDECODE`

## 1. Purpose and decision

The previous count-only audit proved that the committed E3 artifacts no longer retain
enough reversible information to split the generic `missing=true` state into its four
literal causes. This audit performs the minimum additional operation required to recover
that information: causally re-decode the already authorized local fit/select packet
members through each selected target cutoff.

The audit answers exactly two questions:

1. Which frozen primitive predicate caused each of the 11,640 missing terminal targets?
2. Does the resulting cause topology support a configuration-only re-encode proposal,
   require new frontend semantics, or contain multiple independent blockers?

This is an attribution audit, not a new frontend experiment. It does not train a model,
compute an embedding, open report/FINAL data, change a threshold, or claim improved
detection performance.

## 2. Frozen denominator and pinned non-packet inputs

The scientific universe is the existing fit/select terminal-target universe only:

```text
all terminal targets = 25,467
finite targets       = 13,827
missing targets      = 11,640
roles                = fit/select roles already present in the pinned plan
report/FINAL targets = 0
```

| Object | Path | Bytes | SHA-256 |
|---|---|---:|---|
| CKDA D1 FROZEN contract | `runs/mainline_docs/ckda_d1_frozen_representation_probe_preregistered_20260812.md` | — | `ecb429926507d2c4f8f666edc2d7e50f3e94fc2ec74bc1e26e78ca4813950aa9` |
| Step-0 FROZEN contract | `runs/mainline_docs/frontend_f0_missingness_mechanism_audit_frozen_20260828.md` | 7,187 | `f188afc0f9a0564a9f193b2e13637efdb660077f6ce74ba5c1d9cfc638fb1e8e` |
| Step-0 verdict | `runs/frontend_f0_missingness_mechanism_audit_20260828/frontend_f0_missingness_mechanism_verdict.json` | 642 | `a4611c854a139bb663ea64e1599beffa10d4bfbf9f82f86f433408153feee9dc` |
| unified TShark causal frontend | `repo/ood/issue27ckbu_unified_tshark_causal_frontend_v1.py` | 72,587 | `127efd212932d9330af790f17a069a84b3ee48205d68bed7e2e9f00778bb2820` |
| formal E3 embedder | `repo/ood/issue27ckda_d1_e3_embed_v1.py` | 20,364 | `360cbaa72f818e6fc423b16f3b4989333bfba002a1423085ff15b2cb1569de14` |
| local exact two-pass adapter | `repo/ood/issue27ckda_d1_e3_embed_local_twopass_v1.py` | 16,244 | `9f11d03b31e640de28f11fd7570b1495c7b9452b124b8b99b248689031b24ca2` |
| fit/select availability NPZ | `runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/ckda_d1_fit_select_embeddings.npz` | 34,314,736 | `b1b4f2fde168a69e0cf7a53aaede2ddef9bd6d92b0ce58e56a9d6fcde37b6099` |
| embedding metadata | `runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/ckda_d1_fit_select_embeddings.npz.metadata.csv.gz` | 1,122,045 | `120ed5ccc752c1210a655dbcb972e08b6263bdeb1e08093d76b3e2f9c1b3d8dd` |
| fit/select plan | `runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/ckda_d1_fit_select_plan.csv` | 3,945,736 | `eed3d431ab8d71117db7a02b5ee0022eefe7932888001e7d9bcccfd54199aeac` |
| exact target metadata | `runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/ckda_d1_fit_select_target_metadata.csv` | 9,054,589 | `d6fbba24a1997db24597a800cf952f80f739284e5ca13db5ce04497f1540c36d` |
| target-metadata audit | `runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/ckda_d1_fit_select_target_metadata.csv.audit.json` | 545 | `fec780565a8c2f706316c90d76ee5af83136522c20e688b1b6d94f439f7fc906` |
| local path-rebound source manifest | `runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/ckda_d1_local_fit_prefix_manifest.csv` | 11,262 | `afd8f700e64d799d15c2375c3a887b388423a982c7af72d1cb45b85de2ac8e01` |
| path-rebind audit | `runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/ckda_d1_local_fit_prefix_manifest.csv.audit.json` | 480 | `78bdbc0a5d3b38127ef1a06fb6bfd4af5a4be47735b9bc723ada1d2374afafe3` |

Only arrays `uid` and `missing` may be opened from the availability NPZ. Its 768D
`representation` array is forbidden. Probe states, model weights, scores, and thresholds
are forbidden.

## 3. Pre-open packet identity attachment

The exact target metadata currently names 30 `(dataset_kind, container_path,
raw_source_path)` packet members across five local containers. Before any packet body is
opened, the implementation must atomically materialize:

`frontend_f0_step0b_packet_identity_attachment.csv`

with one row per exact packet member and these fields:

```text
dataset_kind
container_path
container_bytes
container_sha256_or_published_identity
raw_source_path
member_uncompressed_bytes_if_archive
member_crc32_if_archive
source_group
role_set
target_count
maximum_target_event_position_inclusive
is_report
is_final
```

For direct PCAPs, whole-file bytes and SHA-256 are mandatory. For the Gotham archive,
the already published archive identity plus the ZIP central-directory member name,
uncompressed bytes, and CRC32 are mandatory; a fresh whole-archive SHA-256 may also be
recorded but is not required to duplicate the already established published identity.

The following pre-open assertions are conjunctive:

1. the target metadata has exactly 25,467 unique UIDs;
2. every UID joins exactly once to the plan and availability `uid` array;
3. the availability array contains exactly 13,827 finite and 11,640 missing rows;
4. every target maps to exactly one of the 30 packet members;
5. target positions are integer, non-negative, unique within a member, and no greater
   than that member's declared inclusive cutoff;
6. the role, phase, source group, member, dataset kind, and cutoff match the pinned
   target metadata without inferred or hand-written substitutions;
7. `is_report=false` and `is_final=false` for every row;
8. all local packet containers exist and match their frozen/published identities; and
9. the TShark executable path, `tshark --version` output, and its SHA-256 are recorded
   before decoding.

Failure is an engineering terminal state with no scientific verdict:

```text
STEP0B_PREOPEN_IDENTITY_OR_SCOPE_FAILURE
```

The identity attachment and its SHA-256 sidecar must be reviewed as part of the
implementation package. Runtime discovery of an additional member is forbidden.

## 4. Literal predicate semantics

The four primitive predicates and descriptive precedence are inherited without change:

```text
SESSION_TIMESTAMP_REGRESSION
NO_IP_SESSION_KEY
UNSUPPORTED_IP_PROTOCOL_NOT_TCP_UDP
NONFINITE_TARGET_TIMESTAMP
```

### 4.1 Raw IP session key

For a target event, the frozen formal embedder defines an IP session candidate only when
`ip_version in {4,6}`. The bidirectional key is:

```text
(ip_proto, sorted(((src_address, src_port), (dst_address, dst_port))))
```

where addresses, ports, and protocol are produced by the pinned
`event_from_tshark` implementation. Therefore:

```text
NO_IP_SESSION_KEY := ip_version not in {4,6}
```

This predicate is evaluated independently of protocol support. An IPv4 ICMP or GRE
target has an IP session candidate under the formal gate and separately satisfies the
unsupported-protocol predicate.

### 4.2 Protocol support

```text
UNSUPPORTED_IP_PROTOCOL_NOT_TCP_UDP := ip_proto not in {6,17}
```

The comparison uses the literal parsed `ip.proto`, not protocol inference from stream
fields. Missing or unparsable `ip.proto` becomes the pinned parser's integer default and
is reported verbatim.

### 4.3 Finite target timestamp

```text
NONFINITE_TARGET_TIMESTAMP := not isfinite(float(frame.time_epoch))
```

This predicate concerns the current selected target. Missing sentinel normalization does
not invent a finite timestamp.

### 4.4 Causal session timestamp regression

For every raw IP session candidate, packets are visited in capture order. The session is
poisoned at the first packet for which:

```text
current_timestamp < previous_timestamp_for_that_same_session
```

Equality is not a regression. The current packet is included. Once poisoned, the current
and all later selected targets in that session satisfy
`SESSION_TIMESTAMP_REGRESSION=true`; earlier targets remain valid. Packets strictly after
a target may not change that target's predicate vector.

To reproduce the local exact two-pass memory discipline, session state is retained only
through that session's last selected target. Packets after the last selected target are
irrelevant and must not recreate state.

### 4.5 Multiple predicates

All four booleans are emitted independently. They may overlap. The descriptive
`primary_reason` is the first true value in the inherited precedence above. Precedence
never deletes a secondary true predicate.

The pinned formal loop constructs and appends an IP-session event before evaluating the
current target's compound missing gate. Step-0b must preserve that ordering. In
particular, if a non-finite timestamp in an active formal IP session causes the pinned
`BoundedNetfoundPrefix.append` path to raise before a target predicate vector can be
produced, Step-0b must stop with `STEP0B_DECODE_OR_SCHEMA_FAILURE`; it may not reorder the
operations and reinterpret that runtime incompatibility as a successfully attributed
missing target. The exact-equivalence gate below therefore validates both the predicate
definitions and their reachable execution semantics.

Any fifth cause or any changed predicate definition is implementation/schema drift and
produces no scientific verdict.

## 5. Ordered execution stages

### R0 — static identity and role gate

Verify all pinned hashes, mechanically re-extract the four predicates from the pinned
formal embedder, build the packet identity attachment, and enforce every pre-open
assertion. No packet body is opened in R0.

### R1 — target-session discovery pass

For each of the 30 allowlisted members, decode only through the member's maximum selected
target position, inclusive. At target positions only, record the exact raw event fields
needed for the four predicates and construct the formal IP session candidate. This pass
does not compute any flow, token, embedding, score, or label.

The pass must cover every target exactly once and must not cross any maximum target
cutoff. Member-level discovery checkpoints are immutable and keyed by:

```text
Step-0b contract SHA
target-metadata SHA
packet-member identity
TShark identity
ordered target UID/position digest
```

### R2 — causal replay and poison-state pass

Decode each member again through the same inclusive cutoff. Retain timestamp state only
for formal IP session candidates that contain at least one selected target. Apply the
literal regression rule in capture order and emit the four predicate booleans at each
target. Release a session after its last selected target and assert that no session state
remains at member completion.

R2 is deterministic and label-free. It may reuse only an exact R1 checkpoint identity;
it may not reuse any localwin embedding checkpoint.

### R3 — exact equivalence gate

Join the reconstructed target table to the pinned availability `uid`/`missing` arrays.
Define:

```text
redecoded_missing := any(the four primitive predicates)
```

The gate is exact:

```text
UID coverage                         = 25,467 / 25,467
redecoded_missing == frozen_missing  = 25,467 / 25,467
missing count                        = 11,640
finite count                         = 13,827
```

Any mismatch, including a finite frozen row with a reconstructed predicate or a missing
frozen row with no reconstructed predicate, terminates with:

```text
REDECODE_MISSINGNESS_EQUIVALENCE_FAILURE
```

No cause topology or route verdict may be consumed after that failure.

### R4 — deterministic attribution and mechanism classification

R4 is entered only after R3 passes. It emits all four booleans, the inherited primary
reason, and exact counts by target, source, device, role, phase, member, and attack family.
All zero-count rows in the frozen device/family universes remain present.

No fitted parameter, bootstrap, threshold search, dominance threshold, or stochastic
operation is permitted. Route classification preserves the parent protocol's terminal
state vocabulary and is presence-based:

1. If every missing target is attributable to a literal existing resource/configuration
   change satisfying all seven preservation conditions in parent M3, return
   `CONFIGURATION_ONLY_REENCODE_CANDIDATE`.
2. Otherwise, if exactly one non-configuration mechanism class has non-zero primary
   count and no configuration-only cause is present, return
   `NEW_FRONTEND_REQUIRED_BY_INPUT_SEMANTICS` and carry that class in a separate
   `new_frontend_mechanism_classes` field.
3. If two or more mechanism classes are present, or configuration-only and
   non-configuration causes coexist, return `MIXED_MISSINGNESS_MECHANISMS` and carry the
   complete class set in the same field.

The four mechanism classes are:

```text
INPUT_SESSION_KEY       <- NO_IP_SESSION_KEY
PROTOCOL_COVERAGE       <- UNSUPPORTED_IP_PROTOCOL_NOT_TCP_UDP
TIMESTAMP_VALIDITY      <- NONFINITE_TARGET_TIMESTAMP
CAUSAL_TIMESTAMP_ORDER  <- SESSION_TIMESTAMP_REGRESSION
```

Because the classification uses non-zero presence rather than a post-hoc percentage,
the observed distribution cannot change the rule. Exact percentages are descriptive.

## 6. Required outputs

1. `frontend_f0_step0b_packet_identity_attachment.csv`
2. `frontend_f0_step0b_packet_identity_attachment.csv.sha256`
3. `frontend_f0_step0b_reason_by_target.csv.gz`
4. `frontend_f0_step0b_reason_by_source.csv`
5. `frontend_f0_step0b_reason_by_device.csv`
6. `frontend_f0_step0b_reason_by_role.csv`
7. `frontend_f0_step0b_reason_by_attack_family.csv`
8. `frontend_f0_step0b_member_decode_audit.csv`
9. `frontend_f0_step0b_equivalence_audit.json`
10. `frontend_f0_step0b_mechanism_verdict.json`
11. `frontend_f0_step0b_result_report.md`
12. `SHA256SUMS`

The verdict JSON must carry, not merely reference:

- all four primitive and primary-reason totals;
- the frozen, finite, missing, and equivalence denominators;
- every device and attack family excluded from any future frontend claim;
- all packet/report/FINAL/model/score/training open counters;
- TShark identity and all input hashes;
- the exact claim boundary; and
- the single terminal state.

Devices, sessions, and records are reported as separate denominators. The number of
independent sessions is computed from reversible session candidates during this audit;
record counts may not masquerade as independent support.

## 7. Terminal states and authorization consequences

Scientific terminal states:

```text
CONFIGURATION_ONLY_REENCODE_CANDIDATE
NEW_FRONTEND_REQUIRED_BY_INPUT_SEMANTICS
MIXED_MISSINGNESS_MECHANISMS
```

Engineering/no-verdict terminal states:

```text
STEP0B_PREOPEN_IDENTITY_OR_SCOPE_FAILURE
STEP0B_DECODE_OR_SCHEMA_FAILURE
REDECODE_MISSINGNESS_EQUIVALENCE_FAILURE
```

`CONFIGURATION_ONLY_REENCODE_CANDIDATE` authorizes only a new re-encode proposal draft.
`NEW_FRONTEND_REQUIRED_BY_INPUT_SEMANTICS` or a mixed state authorizes only a new
frontend requirements document. No state authorizes implementation, training,
checkpoint inference, download, report opening, FINAL opening, or performance claims.

## 8. Required contract and regression tests

Implementation review must include at least the following tests:

1. all pinned non-packet hashes are exact;
2. packet identity attachment is completed before any packet open;
3. an unallowlisted member fails before open;
4. report and FINAL roles fail before open;
5. target UIDs cover exactly 25,467 unique values;
6. target positions are unique within each member;
7. decoding is current-inclusive and stops at the exact maximum cutoff;
8. modifying a future packet cannot change an earlier target attribution;
9. IPv4 TCP has a key and supported protocol;
10. IPv6 UDP has a key and supported protocol;
11. IPv4 ICMP has a formal IP key and unsupported protocol;
12. GRE has a formal IP key and unsupported protocol;
13. a non-IP event has no IP session key;
14. non-finite timestamp is independent of key/protocol predicates, while a non-finite
    timestamp reaching the pinned active-IP append order fails closed rather than being
    reordered;
15. equal timestamps do not poison a session;
16. a decreasing timestamp poisons current and later targets only;
17. poisoning one session does not affect another;
18. post-last-target packets do not recreate released state;
19. multiple true predicates are retained while precedence is deterministic;
20. no fifth primitive cause is accepted;
21. exact 25,467-row frozen-missing equivalence is mandatory;
22. equivalence mismatch deletes/withholds the scientific verdict;
23. only `uid` and `missing` are opened from the availability NPZ;
24. representation, probe state, weights, scores, and thresholds remain unopened;
25. no label is used in R1-R3; attack-family joins occur only after equivalence;
26. member checkpoints reject contract/member/TShark/UID drift;
27. an interrupted run resumes only at a completed member boundary;
28. devices/sessions/records remain separate denominators;
29. zero-count device and family rows survive serialization;
30. Python 3.9 syntax and runtime compatibility pass before real execution;
31. every large output is streamed and atomically finalized; and
32. engineering failure produces no scientific verdict.

Tests may use synthetic fixtures. They must not encode the observed per-cause counts as
success expectations.

## 9. Resource and recovery contract

The audit is local and internet-independent. It opens only packet prefixes already used
by the authorized local CKDA D1 computation. It does not require HPC or a GPU.

To tolerate shutdown or network loss:

- progress and checkpoints are member-scoped and atomic;
- stdout records current member, pass, packets decoded, targets covered, elapsed time,
  and last completed member;
- the run is resumable only from an exact completed-member checkpoint;
- no partial member result enters an aggregate; and
- network availability cannot affect the scientific result.

Before execution, implementation must report estimated total prefix packets, local free
space, and expected temporary-output bytes. A resource shortfall is an engineering stop,
not a scientific result.

## 10. Claim boundary

The maximum claim is the exact missingness-cause topology of the pinned frozen-E3
fit/select terminal-target universe under the pinned local TShark decoding frontend.

This audit cannot claim:

- that missingness causes the hydraulic false-positive failure;
- that repairing missingness improves FPR or attack recall;
- that a new frontend is better;
- that the observed mechanism proportions generalize to report/FINAL or deployment;
- that a challenge-enriched fit/select role distribution is a wild-traffic prevalence;
  or
- any broad industrial-domain generalization.

The existing result that hydraulic error survives after excluding missing embeddings
remains unchanged.

## 11. Open review questions

1. Is the pre-open packet identity attachment sufficiently self-contained, or must the
   Gotham whole-archive SHA-256 be mandatory in addition to the published identity and
   per-member CRC32/size?
2. Do the formal IP-key and timestamp-poison semantics above exactly match the intended
   parent-contract interpretation, especially for unsupported IPv4/IPv6 protocols?
3. Is exact equivalence over both missing and finite rows sufficient to validate the
   local two-pass attribution path without recomputing embeddings?
4. Is the parent-vocabulary non-zero presence rule the correct outcome classifier, or
   should Step-0b stop at exact attribution and defer all route naming to a later
   protocol?
5. Should the identity attachment be frozen by erratum before implementation, or may it
   be an implementation artifact whose schema and construction are frozen here?
6. Are the member-scoped checkpoint and resource gates adequate for an offline Windows
   run that may be interrupted?

## 12. Authorization boundary

This DRAFT authorizes nothing. The next legal action is independent design review. After
review, a FROZEN protocol and SHA-256 sidecar require independent terminal verification.

Implementation, packet opening, causal re-decode, training, embedding generation,
checkpoint inference, network retrieval, report access, FINAL access, HPC submission,
and any performance claim remain unauthorized until their respective later gates.
