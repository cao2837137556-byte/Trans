# Frontend-F0 Step-0b implementation report

Date: 2026-08-29

Branch: `codex/exp-mainline`

Implementation base: `b32c06cc37dd1d4728b88c0ac23b1fde95b52b7d`

Frozen protocol: `runs/mainline_docs/frontend_f0_step0b_causal_redecode_attribution_preregistered_20260829.md`

Frozen protocol SHA-256: `ace6a37fa1ad84fb1660426d4e6c6876fdd3bc407577e3b0709908465b910794`

## 1. Authorization consumed

The user authorized only the implementation-review stage after Kimi's freeze verification.
This report covers:

1. the Step-0b runner;
2. the 32 synthetic contract tests; and
3. the R0 pre-open packet-identity attachment.

No real PCAP packet body was opened. R1-R4 causal re-decode, scientific attribution,
training, model/probe/score access, report access, and FINAL access remain sealed pending
independent implementation review and a separate user execution authorization.

## 2. Implemented files

| File | Bytes | SHA-256 |
|---|---:|---|
| `repo/ood/issue27frontend_f0_step0b_causal_redecode_attribution_v1.py` | 38,130 | `4eef64d9a8de605495bd5e3fa98b9a0982f7a18870520506e3011e87636b1b27` |
| `repo/ood/issue27frontend_f0_step0b_causal_redecode_attribution_contract_tests_v1.py` | 12,798 | `ad87040cc27b101bba08e6666de16c4ed2b3f73ea53eecd1eab51351f5623195` |

The runner has two mechanically separate commands:

- `identity`: R0 only; verifies pins and writes identities without packet-body decode;
- `execute`: R1-R4 only; requires both the reviewed R0 artifacts and the exact separate
  execution token `STEP0B_REAL_PACKET_EXECUTION_AUTHORIZED`.

## 3. Scientific-contract implementation

The implementation provides:

- exact joins over the pinned 25,467-UID fit/select universe;
- two-pass, current-inclusive, capture-order replay through each exact target cutoff;
- the four independent primitive predicates and inherited descriptive precedence;
- current-packet inclusion, equal-timestamp behavior, causal poisoning, session-local state,
  last-target release, and no post-tail state recreation;
- any-true mechanism presence rather than primary-reason selection;
- exact 25,467/25,467 frozen-missingness equivalence before labels are re-opened;
- member-boundary checkpoints whose identity covers contract, target metadata, packet member,
  TShark, and ordered UID/position tuples;
- reversible, capture-scoped session candidates for independent-session denominators;
- zero-count device/family rows and explicit excluded device/family claim fields; and
- atomic large-output finalization with engineering-failure/no-verdict behavior.

Parent-M3 semantics are fail-closed: none of the four observed primitive mechanisms can be
called configuration-only merely because it concerns timestamps. Changing timestamp-order or
timestamp-validity semantics is explicitly `NEW_FRONTEND_SEMANTICS`; a singleton mechanism is
therefore `NEW_FRONTEND_REQUIRED_BY_INPUT_SEMANTICS`, while coexistence is
`MIXED_MISSINGNESS_MECHANISMS`.

## 4. Thirty-member identity scope

The pinned target metadata is the normative 30-member fit/select universe. The separately
pinned local path-rebound manifest contains 27 fit-prefix lineage rows by design. The
implementation therefore:

- requires exactly 30 target-metadata member groups;
- requires and verifies the exact 27-row fit-prefix manifest;
- independently checks its cutoff wherever a target member also occurs in that fit-only
  manifest; and
- uses the exact maximum selected position in pinned target metadata as the declared cutoff for
  select-only members, without inventing a fit-manifest row or hand-written substitution.

This preserves both pinned inputs and avoids the invalid inference that a fit-only manifest must
contain all select-only packet members.

## 5. R0 pre-open identity result

Directory: `runs/frontend_f0_step0b_implementation_preopen_20260829`

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `frontend_f0_step0b_packet_identity_attachment.csv` | 11,399 | `5deddd66248d036250da7b82d97437c4dfff343ed4ac25ac3fe157b8669a849c` |
| `frontend_f0_step0b_packet_identity_attachment.csv.sha256` | 116 | `d72349e7537c0f9ac1929c638a2f47b200afbb429866db4c764a503daaa7897e` |
| `frontend_f0_step0b_r0_identity_audit.json` | 3,709 | `41b524918af9fd07d65460bc2e7c86367b1ba1bc6c1522bc0a9683adc2c68e11` |

R0 assertions:

- 30/30 exact packet members across five containers;
- 25,467 targets; 13,827 frozen finite and 11,640 frozen missing;
- whole-file SHA-256 for every direct PCAP and the Gotham archive;
- Gotham published MD5 plus allowlisted ZIP member name, uncompressed bytes, and CRC32;
- TShark executable SHA-256 `908a3b04da69ee45be9bd54627a722741d895262b4ce0b39f6d79a03daa24087`;
- TShark version `4.6.6`; and
- `packet_bodies_opened=0`, with report, FINAL, model, score, and training counters all zero.

Only the availability arrays `uid` and `missing` were opened; `representation` remained sealed.

## 6. Verification

The exact contract suite passed under Python 3.9:

```text
32/32 PASS
status=PASS
```

Additional checks passed:

- Python 3.9 AST parse and runtime import/compile;
- R0 attachment row count = 30;
- attachment digest = sidecar digest = audit JSON digest; and
- all R0 forbidden-open counters = 0.

No observed scientific count is encoded as a required success result in the synthetic tests.

## 7. Review request and remaining gate

Requested independent review:

1. frozen-semantics fidelity of the two-pass replay and four predicates;
2. the 30-target-member versus 27-fit-lineage-row handling;
3. parent-M3 route classification;
4. reversible session-denominator identity;
5. all 32 Python 3.9 contract tests; and
6. the R0 identity attachment and its zero-open audit.

Passing this review does not itself authorize real causal re-decode. R1-R4 execution remains a
separate user authorization gate.
