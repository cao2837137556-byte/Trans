# Kimi Freeze Verification — Frontend-F0 Coverage Extension Protocol (FROZEN)

- Date: 2026-08-31
- Reviewer: Kimi (independent review role)
- FROZEN document: `runs/mainline_docs/frontend_f0_coverage_extension_protocol_frozen_20260831.md`
- Sidecar: `runs/mainline_docs/frontend_f0_coverage_extension_protocol_frozen_20260831.md.sha256`
- Freeze commit: `fa8ff1d`
- Governing chain: CE ruling `539b313`; draft review `d76915a`; M1
  clarification `6accfd1`; M1 narrow ruling `7f2c567`

## Verdict

**FREEZE VERIFICATION: PASS.** The CE protocol is now the normative contract
for Coverage Extension. It remains NON-EXECUTABLE: implementation, candidate
intake, and every CE stage each require their own explicit user
authorization.

## Independent verification

### 1. SHA-256 recomputation

```text
0b102b7929e2a1ad2e269e35a5a225880a97d34bcc036d586b7066bcc5cddcfe
```

Reviewer-recomputed value matches the sidecar and the freeze handoff. ✓

### 2. Commit scope

`git show --stat fa8ff1d`: exactly two files added — FROZEN document and
sidecar. No incidental changes. ✓

### 3. Full draft→FROZEN diff review

Reviewer diffed the complete draft (`e7a7075`) against the FROZEN document.
All changes are the required mechanical incorporations and nothing else:

| Change | Required by | Verified |
|---|---|---|
| Status DRAFT → FROZEN; governing review chain recorded | freeze mechanics | ✓ |
| §4.2: incumbent pinned as E3/P2, threshold `0.065159872174263`, five artifact SHAs, frontier SHA `aa36fc5f…` | M1.1 | ✓ all six identities re-verified by reviewer against disk artifacts and the threshold marker JSON (marker records `candidate_id=E3`, `select_rows=7069`, P2 threshold literal, `frontier_sha256.P2 = aa36fc5f…`) |
| New §4.3: frozen baseline filter (`E3/P2, phase=select, label_metric_only=0, old_missing=true`), 4,812 denominator (3,518+1,294), 430 fit-phase rows excluded, 5,242 withdrawn, score-pinning disclosure (`score == threshold`, `>=` rule, `H_old` a convention consequence, not learned behavior), literal gate 482, 69/69 and 23/23 hard, condition 5 subsumes condition 4 with redundant guard retained | M1.2–M1.3 + ruling §3 | ✓ verbatim in substance |
| CE-2 prerequisites: `F0_ENCODER_ONLY_PASS` + count/identity/copy artifacts, no F1 | Q6 | ✓ |
| CE-4 prerequisites: `F1_FRONTEND_CHALLENGE_PASS` + separate user authorization | Q6 | ✓ |
| CE-5 condition 8: literal 482 | M1 | ✓ |
| Q3: principle accepted, no runtime small-`H_old` branch (baseline pinned) | `d76915a` Q3 | ✓ |
| Test list: literal 482 (test 18), exact 4,812 no-fit-role denominator (19), pinning-convention test (20), CE-2/CE-4 gate tests (21–22), renumbered to 26 | M1/Q6 | ✓ |
| §13: six rulings normative + M1 chain summary | `d76915a`, `7f2c567` | ✓ all six match |
| §14: legal chain updated | freeze mechanics | ✓ |

**Zero scientific drift**: the router rule (§4.1), the challenger-branch
rules (renumbered §4.4), the full-universe measurement requirement (§5),
the missing-subset availability gates (§6), claims and boundaries (§3),
stop states (§10), anti-waste constraints (§12), and all numerical gates
outside the M1-materialized literals are byte-identical to the reviewed
draft. ✓

## Resulting state

1. The CE protocol rule layer is closed. The full legal chain for any CE
   work is now: candidate intake (Stage 0 identity under the frozen
   challenger requirements `6495a6e`) → CE-0/CE-1 → CE-2 → CE-3 → (F1 +
   separate user authorization) CE-4 → CE-5 → CE-6 one-shot protocol.
2. Frozen literals now in force: incumbent E3/P2 + six identity hashes;
   denominator 4,812; `H_old = 4,812`; material-gain gate 482; 23/23
   kill-only attack guard; condition 5 subsumption disclosed; missing-score
   pinning interpretation disclosed.
3. Still unauthorized and unchanged: challenger nomination/retrieval,
   checkpoint download, PCAP decode, representation generation, head
   training, score opening beyond the already-frozen fit/select artifacts,
   report/FINAL access, HPC submission, alarm change, deployment.
4. Open route questions for the user (each with its own authorization
   chain): which challenger enters Stage 0 (Pcap-Encoder remains blocked on
   unpinnable checkpoint; NetMamba remains sealed; a controlled zero-training
   prototype is the resource-cheapest first candidate under §12); whether
   Data-F0b is reopened.
