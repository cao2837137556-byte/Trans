# Kimi Freeze Verification — Frontend-F0 Challenger Requirements (FROZEN)

- Date: 2026-08-30
- Reviewer: Kimi (independent review role)
- FROZEN document: `runs/mainline_docs/frontend_f0_challenger_requirements_frozen_20260830.md`
- Sidecar: `runs/mainline_docs/frontend_f0_challenger_requirements_frozen_20260830.md.sha256`
- Freeze commit: `6495a6e`
- Draft under comparison: `frontend_f0_challenger_requirements_draft_20260830.md` (`532b2b6`)
- Draft review with rulings: `e588948`

## Verdict

**FREEZE VERIFICATION: PASS.** The FROZEN document is now the normative
requirements contract for any challenger frontend. It remains NON-EXECUTABLE:
candidate intake, implementation, and every execution stage each require
their own explicit user authorization.

## Independent verification

### 1. SHA-256 recomputation

Reviewer recomputed the document SHA-256:

```text
b46caf0d308531f512ffedd3a9dea8d1438c22a8d136f7c1965dff8ea3f411b0
```

Matches the sidecar and the value declared in the freeze handoff. ✓

### 2. Commit scope

`git show --stat 6495a6e`: exactly two files added — the FROZEN document and
its sidecar. No incidental changes. ✓

### 3. Full draft→FROZEN diff review

Reviewer diffed the complete draft against the FROZEN document. The diff
contains **only** the following changes, each verified against the mandatory
strengthenings and rulings in `e588948`:

| Change | Required by | Verified |
|---|---|---|
| Title/status DRAFT → FROZEN; basis line adds `e588948` | freeze mechanics | ✓ |
| R5: mandatory raw endpoint-identifier masking arm — addresses and hardware identifiers normalized/removed, separability re-measured, arm frozen before learned-head results | S2 | ✓ verbatim in substance |
| Stage-1 gate: "every fit-benign device" → "every benign device in the frozen universe, regardless of role" | S3 | ✓ verbatim in substance |
| §8 new item 7: per-device/per-exact-family causal-context size distributions (min, quartiles, max, distinct-context count); pseudo-session and all-singleton degeneration mechanically visible | S1 | ✓ verbatim in substance |
| §9 open questions → normative rulings, six rulings recorded accurately, with the explicit note that no numerical gate, stage order, or candidate state changed beyond the S3 scope correction | `e588948` rulings | ✓ all six rulings match |
| §10 authorization boundary updated; next step is this SHA/diff terminal review | freeze mechanics | ✓ |

**Zero scientific drift**: R1–R6 capability text (outside the S2 insertion),
all numerical gates (0.90/0.80/0.80), the five-stage measurement sequence,
the twelve mandatory causality/anti-degeneracy tests, the fourteen stop
states, and the candidate blocker/seal states are byte-identical to the
reviewed draft. ✓

## Resulting state

1. The requirements contract is frozen. Any challenger — Pcap-Encoder (if its
   checkpoint ever becomes pinnable), NetMamba (if ever unsealed by a separate
   protocol), a retrained encoder, or any later candidate — is measured
   against this document and no other.
2. Still blocked and unchanged: `F0_NO_USABLE_OFFICIAL_CHECKPOINT`
   (Pcap-Encoder), NetMamba seal, all training/embedding/score/report/FINAL/
   HPC paths.
3. Next legal actions, each requiring its own authorization chain:
   - candidate intake protocol for a specific challenger (Stage 0 identity);
   - Data-F0b (CIC IoT 2022 member inventory) remains a separate sealed
     question;
   - no re-encode of the frozen universe is authorized by this freeze.
