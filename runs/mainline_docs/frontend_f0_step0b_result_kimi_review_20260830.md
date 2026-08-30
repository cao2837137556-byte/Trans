# Kimi Result Review — Frontend-F0 Step-0b Causal Re-decode Attribution

- Date: 2026-08-30
- Reviewer: Kimi (independent review role)
- Reviewed commits: `732299c` (execution preflight), `41699ed` (formal result)
- Implementation under review: `d65f705`, implementation review `727bbda` (PASS)
- Frozen protocol SHA-256: `ace6a37fa1ad84fb1660426d4e6c6876fdd3bc407577e3b0709908465b910794`
- Result document: `runs/mainline_docs/frontend_f0_step0b_result_20260830.md`
- Result bundle: `runs/frontend_f0_step0b_implementation_preopen_20260829/`

## Verdict

**RESULT REVIEW: PASS — terminal state `MIXED_MISSINGNESS_MECHANISMS` accepted.**

Every reported number was independently recomputed by the reviewer from the
per-target artifact, not copied from the result document. The equivalence gate
passed exactly, the cause topology is internally consistent at every
aggregation level, and all authorization boundaries held.

## Independent verification

### 1. Bundle integrity

- Reviewer recomputed all 11 entries of `SHA256SUMS` in the result bundle:
  **11/11 OK**, including the previously reviewed R0 identity attachment and
  its sidecar.

### 2. Equivalence gate (the decisive check)

Recomputed independently from `frontend_f0_step0b_reason_by_target.csv.gz`:

| Check | Reported | Reviewer recomputation |
|---|---:|---:|
| Rows / unique UIDs | 25,467 | 25,467 / 25,467 ✓ |
| Any-true missing | 11,640 | 11,640 ✓ |
| Per-target match vs frozen `missing` | 25,467/25,467 | 25,467/25,467 ✓ |
| Finite | 13,827 | 13,827 ✓ |

The reconstructed missingness reproduces the frozen availability artifact
**exactly, target by target**. The attribution is therefore mechanically
anchored to the same universe whose missingness was audited in Step-0.

### 3. Cause topology recomputation

Any-true predicate counts (overlapping by design, reviewer S2 semantics):

| Predicate | Reported | Recomputed |
|---|---:|---:|
| `UNSUPPORTED_IP_PROTOCOL_NOT_TCP_UDP` | 11,605 | 11,605 ✓ |
| `NO_IP_SESSION_KEY` | 9,605 | 9,605 ✓ |
| `SESSION_TIMESTAMP_REGRESSION` | 47 | 47 ✓ |
| `NONFINITE_TARGET_TIMESTAMP` | 0 | 0 ✓ |

Boolean-pattern decomposition (sums to 11,640):

| Pattern | Reported | Recomputed |
|---|---:|---:|
| no session key + unsupported protocol | 9,605 | 9,605 ✓ |
| session key present + unsupported protocol | 1,988 | 1,988 ✓ |
| timestamp regression only | 35 | 35 ✓ |
| timestamp regression + unsupported protocol | 12 | 12 ✓ |

Primary-reason distribution 9,605 / 1,988 / 47 also recomputed ✓. Mechanism
counts (`PROTOCOL_COVERAGE` 11,605, `INPUT_SESSION_KEY` 9,605,
`CAUSAL_TIMESTAMP_ORDER` 47, `TIMESTAMP_VALIDITY` 0) match the verdict JSON ✓.

### 4. Benign/attack split recomputation (labels joined post-gate, as frozen)

| Group | Targets | Missing | Rate | Reported | Recomputed |
|---|---:|---:|---:|:--:|:--:|
| Benign | 21,013 | 11,478 | 54.62% | ✓ | ✓ |
| Attack | 4,454 | 162 | 3.64% | ✓ | ✓ |

- Attack-missing families recomputed: Mirai GRE Flooding 70, Merlin ICMP
  Flooding 51, Merlin C&C Communication 32, Mirai UDP Flooding 6,
  File Download 3 (total 162) ✓.
- Attack-missing composition: 127 unsupported-protocol any-true, 47 regression
  any-true, 12 overlap → 162 unique ✓.
- **Every** missing benign target (11,478/11,478, 100%) activates the
  unsupported-protocol predicate; 9,605 of them additionally lack an IP
  session key ✓.
- 11,478 of 11,640 missing targets (**98.6%**) are benign. The missingness
  problem is overwhelmingly a benign-side blind spot; attack-side encodability
  (96.4%) is consistent with the previously audited attack-side strength.
- Devices = 8, independent sessions = 8,464 recomputed ✓.

### 5. Aggregate-artifact consistency

Reviewer cross-checked all four aggregate CSVs against the per-target file:
`reason_by_role` (9 rows), `reason_by_attack_family` (13 rows),
`reason_by_device` (8 rows), `reason_by_source` (28 rows) — every
`missing_targets` cell and every per-predicate count matches the per-target
recomputation; each table sums to 11,640 ✓.

### 6. Execution provenance

- `member_decode_audit.csv`: 30/30 members `COMPUTED_EXACT_TWOPASS` (no
  checkpoint reuse), discovery-packet count equals replay-packet count for
  every member, target counts sum to 25,467 ✓.
- Verdict boundary counters: `report_opened`, `final_opened`, `model_opened`,
  `score_opened`, `training_started` all 0; `packet_members_opened` 30 ✓.
- Verdict `contract_sha256` matches the frozen protocol SHA; `input_sha256`
  records the same 14 pinned inputs verified at implementation review ✓.
- TShark identity unchanged from the reviewed R0 audit (4.6.6, exe SHA
  `908a3b04…`) ✓.
- Commit `732299c` adds only the preflight document; commit `41699ed` adds
  only the 10 result artifacts plus the result document. No incidental files.
  Pre-existing unrelated dirty files remain untouched ✓.

## Scientific assessment

1. **This is a genuine positive diagnosis, not a performance result.** The
   claim boundary ("missingness-cause topology of the pinned frozen-E3
   fit/select terminal-target universe") is respected everywhere in the
   result document.
2. The benign blind spot is now mechanically explained: it is 100% a
   frontend-input-semantics problem (protocol coverage and session-key
   construction), with timestamp regression a negligible third mechanism
   (47 targets, attack-only). A configuration-only re-encode is empirically
   excluded, consistent with the strict M3 reading accepted at implementation
   review.
3. The two dominant mechanisms are heavily entangled (9,605 of 11,605
   unsupported-protocol targets also lack a session key): in this corpus,
   non-TCP/UDP traffic is mostly traffic for which the frozen frontend cannot
   even form a five-tuple session. A challenger frontend must therefore solve
   protocol coverage **and** keyless-event representation together; fixing
   only the protocol filter without a session semantics for those events
   would leave the 9,605-target dominant pattern unrepresented.
4. The diagnosis is mechanistically consistent with the known OOD story
   without overclaiming: over half of benign fit/select terminal targets
   never reached the encoder, so the representation's benign coverage was
   systematically biased toward TCP/UDP keyable traffic. Any causal link to
   the hydraulic false-positive pattern remains a hypothesis for the
   challenger-frontend stage, not a conclusion of this audit.
5. Encodability ≠ performance. The reviewer endorses the result document's
   point 4: any challenger frontend must pass the separately frozen
   availability and geometry instruments before any performance evaluation.

## Non-blocking observations

1. The verdict's `excluded_devices_from_frontend_claim` lists all 8 devices
   (every device has at least one missing target), and
   `excluded_attack_families_from_frontend_claim` includes the `benign`
   pseudo-family. These lists are descriptive and the claim boundary is
   intact, but their current construction dilutes the selective-exclusion
   semantics; future instruments should define exclusion lists relative to a
   stated coverage threshold rather than any-missing.
2. The 12 attack targets carrying both regression and unsupported-protocol
   predicates are counted in both any-true columns; the result document
   discloses this correctly via the pattern table.

## Route consequence (reviewer position)

- The reviewer accepts Codex's proposal: the next step is to **freeze new
  frontend requirements** grounded in this topology (declared protocol
  coverage, keyless-event session representation, causal regression handling,
  per-device/per-family encodability reporting), rather than further patching
  netFound output.
- The Frontend-F0 Stage I blocker stands independently: Pcap-Encoder has no
  pinnable official checkpoint, and NetMamba remains sealed. The requirements
  freeze should therefore be written challenger-neutral, so that any of
  {checkpoint-pinning, alternative frontend, retrained frontend} can be
  evaluated against the same frozen availability + geometry gates.
- No new execution is authorized by this review. Freezing the requirements
  document, checkpoint pinning, Data-F0b, and any re-encode each require
  their own protocol → freeze → implementation-review → execution chain.
