# Frontend-F3 full-fit L1 audit: result closure

Date: 2026-09-05

Closure finalized: 2026-09-06; package pins and 19 synthetic tests rechecked.

Status: `F3_FULL_FIT_L1_NO_GO_CONFIRMED`

Execution code: `5699f2a` (final resource-profile pin update)

Scope: closure of an existing run; no replay, score computation, or training.

## Outcome and its precise scope

The frozen full-fit L1 audit produced `F3_FULL_FIT_L1_NO_GO`. The two failed
gates are `vocabulary_capacity_and_non_unk` and
`kill_only_not_structurally_blocked`. Both fail because some prefixes consist
entirely of UNK after a whole-event-signature vocabulary is applied. The
vocabulary has 1,001 entries, below its 4,094-entry limit. Capacity, canonical
label contradictions, and token-label contradictions are not the blockers.

This run is closed. Its inputs, output package, gates, and verdict are retained
unchanged. Further work on a different field encoding requires a new contract;
it is not a retry of this run or promotion of L2/L3.

The raw verdict's `next_authorized_by_pass` field contains
`close_unified_encoder_frozen_p2_route` even though this was a NO_GO without
training. That policy string is broader than the parent protocol: section 7
requires stopping this audit, while section 8 makes permanent closure of the
general interface conditional on a later permitted training failure. The
authoritative interpretation is therefore **this vocabulary realization stops;
no training is authorized by this result**. Neither all unified frontends nor
all frozen-P2 interfaces have been disproved. This clarification corrects the
scope of the policy string without editing or replacing the archived verdict.

## Independent verification

Verification read the existing result files and saved member checkpoints only.
It independently rebuilt each target's L0 prefix from the pinned F1 corpus,
rebuilt L1 and vocabulary prefix hashes from checkpoints, and compared them
with the published target audit.

| Check | Result |
|---|---:|
| Package members / matching SHA-256 | 12 / 12 |
| Saved member checkpoints / matching SHA-256 | 20 / 20 |
| Parent train targets / contexts | 13,866 / 9,307 |
| Exposed internal-validation kill-only targets | 5 |
| L0 prefix mismatches over all 13,871 targets | 0 |
| Context/event-index mismatches | 0 |
| Recomputed L1 prefix, token-prefix, known-event count mismatches | 0 / 0 / 0 |
| Canonical mixed-label buckets / token mixed-label buckets | 0 / 0 |
| Vocabulary size / frozen maximum | 1,001 / 4,094 |
| Full-fit synthetic tests | 7 / 7 PASS |
| Shared field/replay synthetic tests | 12 / 12 PASS |

No real TShark replay or model computation was run during closure. The original
result's boundary counters remain zero for model, score, learned representation,
optimizer, select, report, FINAL, and payload bytes. The five previously exposed
attack targets remain a named kill-only exception, not new validation evidence.

## Where the dictionary loses information

| Nested split | Targets | Contexts | Entirely UNK target prefixes | Prefix-event occurrences | UNK occurrences |
|---|---:|---:|---:|---:|---:|
| Train | 8,660 | 4,984 | 0 | 47,536 | 0 |
| Internal validation | 5,206 | 4,323 | 3,173 | 195,361 | 150,035 |

All 3,173 entirely UNK internal-validation targets are benign `normal_1.pcap`
targets: 16 A targets and 3,157 B targets. Two of the five exposed attack
prefixes are entirely UNK (2/2 and 3/3 events). None of those five token prefixes
collides with a nested-train benign prefix; the known-event requirement is what
kills that gate.

Prefix-event occurrences repeat events when several targets share a prefix.
Their UNK ratio must not be reported as a fraction of independent packets,
sessions, or the full 25,467-target universe. An all-UNK sequence may still
retain sequence length; the demonstrated loss is of its event-field detail,
not a theorem that every such sequence is indistinguishable from every other.

The L1 strings themselves contain the additional frame length, delta bucket,
transport length, and TCP flags. The encoder currently uses the complete string
as a categorical key, so an unseen combination loses all those distinctions.
This supports testing a fixed, fieldwise encoding of the same fields. Zero
exact collisions alone is only a necessary input condition, not a proof of
attack semantics, generalization, or freedom from capture shortcuts.

## Validation support remains limited

| Nested split | A protected attack contexts | A protected benign contexts | B attack contexts | B benign contexts |
|---|---:|---:|---:|---:|
| Train | 2,149 | 1,851 | 27 | 957 |
| Internal validation | 1 | 993 | 2 | 3,327 |

The internal-validation A attack context supplies three target rows. It passes
the parent's mechanical nonempty gate, but is insufficient to establish broad
attack inheritance. Source assignments must not be shuffled after seeing this
table. These internal-validation diagnostics are now exposed development
evidence. The five older failures remain kill-only. Any future positive
generalization claim needs a separately declared, untouched confirmation set.

Protected-benign counts exclude A rows labeled benign but marked `benign_hard`
by the teacher: 24 train rows and 2 internal-validation rows. These rows remain
in the parent corpus and all input-conservation checks; they are not deleted.

## Engineering history and replay limits

The final invocation reused 18 exact member checkpoints and freshly computed
two members. It was not 20 fresh decodes in that invocation. The zero packet
counts on reused entries describe the final invocation, not the original cost
of producing those checkpoints.

Two engineering failures are retained in the result package: an empty TShark
cell represented as the string `None`, and a TShark allocation failure. The
subsequent resource profile disabled reassembly/sequence analysis and used
TShark's 100,000-packet session reset, with absolute frame ordinals restored.
The 28-target resource canary reproduced the original prefix payload byte for
byte; all 13,871 final L0 prefixes were also independently reproduced. L1
resource-profile equivalence outside that canary is not claimed to have been
compared against an unbounded original TShark run.

Direct PCAP identities were checked by SHA-256. This replay checked the Gotham
container size and member central-directory size/CRC against pinned metadata;
it did not rehash the entire 23.8 GB archive or independently read every member
through its end. The earlier R0 identity remains provenance, not a fresh full
archive checksum for this invocation.

## Durable identities and next work

- Parent protocol SHA-256:
  `f8eb764839c6514b385851d5e693ecb14ae485c3fc4dfd51cc86aa309bc3be2f`.
- Original package: `runs/frontend_f3_full_fit_l1_identifiability_v1_20260905`.
- Original `SHA256SUMS` SHA-256:
  `a294d93bfe2fdb9c221f3589e3a8da877e9ae8679ad6102e35c8f4323165e1c1`.
- Original verdict SHA-256:
  `6975f2a56526b7cb71982039486919c8cd963ba99799806209183d28ed3a0d11`.
- Closure receipt: `frontend_f3_full_fit_l1_closure_receipt_20260905.json`.
- Byte-preserving archive manifest (original 13 immediate files plus 40 member
  checkpoint files): `frontend_f3_full_fit_l1_archive_manifest_20260906.sha256`.
  This new manifest lives outside the original result directory. The compact
  original outputs and semantic checkpoints are archived unchanged; Git's
  scoped `-text` rule prevents checkout newline conversion of pinned bytes.

The user authorized this closure and a new fieldwise-input feasibility
protocol, with Sol High implementation/tests/no-model audit after the design
is explicit. Training is not authorized. The new draft is
`frontend_f4_fieldwise_input_feasibility_draft_20260905.md`; it preserves the
L1 fields and inherited source split and makes no learned-model selection.
