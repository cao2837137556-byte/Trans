# Kimi Implementation Review — Frontend-F0 Step-0b Causal Re-decode Attribution

- Date: 2026-08-29
- Reviewer: Kimi (independent review role)
- Reviewed commit: `d65f705` (`feat: implement Frontend-F0 Step-0b preopen audit`)
- Frozen protocol: `runs/mainline_docs/frontend_f0_step0b_causal_redecode_attribution_preregistered_20260829.md`
  - Protocol SHA-256 (re-verified by reviewer at freeze time, commit `b32c06c`): `ace6a37fa1ad84fb1660426d4e6c6876fdd3bc407577e3b0709908465b910794`
- Implementation report under review: `runs/mainline_docs/frontend_f0_step0b_implementation_report_20260829.md`

## Verdict

**IMPLEMENTATION REVIEW: PASS**

The implementation faithfully translates the FROZEN protocol, including both
reviewer-mandated freeze modifications (S1 Gotham whole-archive SHA-256 identity,
S2 any-true mechanism classification). No scientific-semantic drift, no
boundary violation, and no observed-outcome encoding in tests were found.
Real packet execution (R1–R4) remains unauthorized until the user issues a
separate execution authorization; the runner mechanically enforces this.

## Independent verification performed by the reviewer

All checks below were re-executed independently by the reviewer on commit
`d65f705`; none rely on the implementer's claims.

### 1. Identity attachment recomputation

- Recomputed SHA-256 of
  `runs/frontend_f0_step0b_implementation_preopen_20260829/frontend_f0_step0b_packet_identity_attachment.csv`:
  `5deddd66248d036250da7b82d97437c4dfff343ed4ac25ac3fe157b8669a849c` — **matches**
  the value recorded in the R0 audit JSON and the implementation report.
- Attachment row count: **30 members**; `target_count` column sums to exactly
  **25,467** — matches the frozen fit/select denominator.
- Role-set distribution across the 30 members: `aux_fit` 11, `aux_select` 5,
  `support_train|support_val` 5, `id_calib` 3, `ood_val` 2, `aux_normal_fit` 1,
  `aux_normal_select` 1, `aux_process_fit` 2. `is_report` / `is_final` are
  `false` on all 30 rows. The `support_train|support_val` members are part of
  the frozen 25,467-target universe (which includes the 69 support_val rows);
  their presence in the attachment is scope-faithful, not leakage.

### 2. Reviewer-mandated S1 anchor: Gotham whole-archive SHA-256

- Independently recomputed SHA-256 of
  `D:\study\paper\anomaly_detection\paper04\datasets\gotham2025\raw\GothamDataset2025.zip`
  (23,824,968,355 bytes):
  `4c96a8915466baf14c8608c127bc4ef4f42aff4ba351292a2085371846175b4f` — **matches**
  the identity recorded in the R0 audit. The S1 modification (whole-archive
  SHA-256 as mandatory R0 identity, MD5 published identity kept descriptive) is
  implemented and now independently confirmed by the reviewer.

### 3. Direct PCAP source hashes

Independently recomputed SHA-256 of the four direct-read PCAPs; all match the
attachment:

- `normal_1.pcap` → `9463135bbb3ab8f6e27a459c6be117e79f72ff8e434b7e70478ed70f4f8bf3c5` ✓
- `normal_2.pcap` → `e7b2e1d7a54b34f8af190693f34cd5d09b3d8248826627bb1e8245ca47ae76ba` ✓
- `normal_scanning1.pcap` → `464f17996a5158964fc5ef4e48e6f108ea70b834bccc973e94e730371c1c51c5` ✓
- `password_normal1.pcap` → `5be996df9ae286f11f66f78708292ed8fade7d135c05514aff3e3d298fd17844` ✓

### 4. Runner code review (`repo/ood/issue27frontend_f0_step0b_causal_redecode_attribution_v1.py`, 776 lines, read in full)

- **Two-command physical separation**: `identity` performs R0 only and never
  opens packet bodies; `execute` is a separate subcommand. ✓
- **Execution token gate**: `execute` requires the literal token
  `I_UNDERSTAND_STEP0B_OPENS_FIT_SELECT_PACKET_PREFIXES`
  (`EXECUTION_TOKEN`, line 38; enforced at line 595). The frozen protocol pins
  the *requirement* of a separate user execution authorization, not a specific
  token string; the chosen literal satisfies it and cannot be bypassed
  accidentally. ✓
- **Reviewed-identity precondition**: `execute` re-verifies the R0 attachment
  SHA-256 against its sidecar, the audit JSON's contract SHA, and the live
  TShark identity before any packet member is opened
  (`verify_reviewed_identity`). The identity artifacts consumed are exactly the
  ones re-hashed in §1–§3 above. ✓
- **Four-predicate semantic equivalence with the frozen embedder** — the
  reviewer cross-read the pinned embedder
  `repo/ood/issue27ckda_d1_e3_embed_v1.py` (lines 40–116, 270–314) against the
  runner's replay:
  - Session construction `(ip_proto, sorted endpoints)` restricted to
    `ip_version ∈ {4,6}` is byte-equivalent between the two files.
  - Append-before-gate: both append the target event's own contribution to
    session state *before* evaluating target predicates. ✓
  - Regression poison on strict decrease only (`timestamp < previous`);
    equality does not poison. ✓
  - Permanent poison: once regressed, the session stays missing for all later
    targets; the runner's post-poison timestamp bookkeeping is harmless because
    the predicate `session in poisoned` is sticky, matching the embedder's
    `unencodable_sessions` stickiness. ✓
  - Tail release without reconstruction: runner releases session state at the
    session's last target and asserts full release; after the last target no
    predicate evaluation can involve that session, so the release has no
    semantic effect versus the embedder. ✓
  - Runner narrows tracking to target-bearing sessions only; per-session poison
    state at target positions is unaffected by other sessions, so this
    narrowing is semantically neutral. ✓
  - Non-finite timestamp reaching the active-IP append path raises
    fail-closed in both implementations. ✓
- **Any-true mechanism classification (reviewer S2)**: `mechanism_counts`
  increments every true predicate (union semantics); `classify_mechanisms`
  acts on the union of mechanisms with count > 0; `primary_reason` is
  descriptive only. ✓
- **Strict M3 reading**: `classify_mechanisms` can only return
  `NEW_FRONTEND_REQUIRED_BY_INPUT_SEMANTICS` (single class) or
  `MIXED_MISSINGNESS_MECHANISMS` (multiple classes);
  `CONFIGURATION_ONLY_REENCODE_CANDIDATE` is unreachable. The reviewer accepts
  this reading: none of the four predicates is repairable by a literal
  configuration change while preserving the parent-M3 invariants (protocol
  support and timestamp semantics are frontend semantics; the 144-packet
  retention cap is not a missing branch, as verified by the reviewer in the
  embedder source during the Step-0 audit). This is the conservative, faithful
  interpretation. ✓
- **Exact equivalence gate**: 25,467/25,467 UID coverage *and*
  missing=11,640 / finite=13,827 *and* per-target boolean equality against the
  frozen missingness are all mandatory; on any mismatch the verdict file is
  deleted, a failure audit is written, and `EquivalenceFailure` is raised. ✓
- **Labels joined only after R3 passes** (line 681 comment verified in source);
  `attack_family` is absent from `CAUSAL_COLUMNS`. No label leakage into
  decode. ✓
- **Member-atomic checkpoints**: checkpoint identity covers contract SHA,
  target-metadata SHA, packet-member identity, TShark identity, and the ordered
  (uid, position) list; resume only from a complete member boundary with drift
  re-hash (`REUSED_EXACT_MEMBER_BOUNDARY`). ✓
- **Cutoff discipline**: both passes raise if decoding crosses the inclusive
  member maximum and if the decoded prefix is incomplete; `packet_limit =
  cutoff + 1` is passed to TShark iteration. ✓
- **Report/FINAL guard**: members with report/final role markers fail preopen;
  verdict boundary counters (`report_opened`, `final_opened`, `model_opened`,
  `score_opened`, `training_started`) are all literal 0. ✓

### 5. Contract-test battery review (325 lines, read in full)

- 32 tests; behavioral tests genuinely discriminate the causal semantics:
  future-packet isolation (test_08), equality-no-poison (test_15),
  current-and-later-only poisoning `[False, True, True]` (test_16),
  session-local poison (test_17), tail release (test_18), non-finite fail-close
  (test_14), any-true multi-predicate counting and terminal classification
  (test_19), fifth-cause rejection (test_20), verdict withholding on
  equivalence failure with correct label-join ordering (test_22), uid/missing-
  only NPZ opening in the presence of a forbidden array (test_23), checkpoint
  identity drift axes (test_26), Python 3.9 syntax gate (test_30),
  engineering-failure-creates-no-verdict (test_32).
- No test encodes already-observed real-world outcome numbers as success
  expectations; literal-denominator tests (test_05, test_21) assert source
  constants, not results. ✓

### 6. Independent re-run of the test battery

- Reviewer re-ran: `py -3.9 repo/ood/issue27frontend_f0_step0b_causal_redecode_attribution_contract_tests_v1.py`
- Result: **32/32 PASS** on the real Python 3.9 runtime. ✓

### 7. R0 audit JSON spot-check

- `runs/frontend_f0_step0b_implementation_preopen_20260829/frontend_f0_step0b_r0_identity_audit.json`:
  30 members, 25,467 targets, 13,827 finite / 11,640 missing, all forbidden
  counters 0, 14 pinned input SHAs recorded (including the protocol SHA
  `ace6a37f…`), TShark 4.6.6 identity with executable SHA-256
  `908a3b04da69ee45be9bd54627a722741d895262b4ce0b39f6d79a03daa24087`,
  availability NPZ opened for exactly `uid` and `missing`. ✓

## Minor observations (non-blocking)

1. The execution-token literal in code differs from the phrasing used in
   earlier discussion notes; the frozen protocol pins the *requirement* of a
   separate explicit execution authorization, not a specific string, so this
   is in-contract. Recorded here only for documentation hygiene.
2. Several contract tests are static source-text assertions rather than
   behavioral tests. This is accepted because the core causal semantics are
   covered by discriminating behavioral tests and the ultimate protection is
   the empirical 25,467/25,467 exact-equivalence gate against frozen
   missingness, which no semantic drift can survive.

## Authorization state after this review

- Implementation review: **PASS** (this document).
- Still **not** authorized: real packet execution (R1–R4 causal re-decode).
  The next legal action is a separate user execution authorization for the
  `execute` command with the literal token. The execution is local,
  internet-independent, resumable at member boundaries, and opens only the 30
  reviewed fit/select packet members through their frozen target cutoffs.
- Still unauthorized, as before: training, embedding generation, checkpoint
  inference, network retrieval, report access, FINAL access, HPC submission,
  and any performance claim.
