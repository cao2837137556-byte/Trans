# Frontend-F0 Step 0 — Frozen-E3 Missingness Mechanism Audit (DRAFT)

- Date: 2026-08-28
- Status: **DRAFT; NON-EXECUTABLE**
- Purpose: identify the exact deterministic mechanism behind the 6,424 whole-session
  missing terminal embeddings before investing in a replacement frontend.
- Scientific role: coverage/provenance diagnosis only. This is not a detector result and
  cannot authorize re-encoding, PCAP decoding, model changes, or performance claims.

## 1. Questions

1. Which literal frozen-E3 branch generated each `missing=true` terminal target?
2. Are missing causes configuration-only, input-semantic, protocol-semantic, causal-order,
   or unidentifiable from already legal artifacts?
3. How are exact causes distributed by benign device and attack family?
4. Can any cause be removed without changing packets, session identity, causal cutoff,
   token semantics, model weights, or role membership?

## 2. Pinned inputs

| Object | Path | SHA-256 |
|---|---|---|
| formal E3 embedder | `repo/ood/issue27ckda_d1_e3_embed_v1.py` | `360cbaa72f818e6fc423b16f3b4989333bfba002a1423085ff15b2cb1569de14` |
| local exact two-pass adapter | `repo/ood/issue27ckda_d1_e3_embed_local_twopass_v1.py` | `9f11d03b31e640de28f11fd7570b1495c7b9452b124b8b99b248689031b24ca2` |
| embedding metadata | `runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/ckda_d1_fit_select_embeddings.npz.metadata.csv.gz` | `120ed5ccc752c1210a655dbcb972e08b6263bdeb1e08093d76b3e2f9c1b3d8dd` |
| fit/select plan | `runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/ckda_d1_fit_select_plan.csv` | `eed3d431ab8d71117db7a02b5ee0022eefe7932888001e7d9bcccfd54199aeac` |
| CKDE-S terminal review | `runs/mainline_docs/ckde_s_d0_lane_g_r2_result_kimi_terminal_review_20260827.md` | `fddd32a9758743b0627ca64e1265b984a24fec74b3c0cab860fe2ca20939b61f` |

The availability NPZ may be named only in the FROZEN version after its identity and
permitted arrays (`uid`, `missing`) are pinned. Its 768D `representation` array and the
probe-state NPZ are forbidden in this audit.

## 3. Literal missingness predicate dictionary

The implementation has exactly four primitive missing predicates:

```text
NO_IP_SESSION_KEY
UNSUPPORTED_IP_PROTOCOL_NOT_TCP_UDP
NONFINITE_TARGET_TIMESTAMP
SESSION_TIMESTAMP_REGRESSION
```

The first three form one compound target gate and are stored under the generic reason
`UNENCODABLE`; they are not guaranteed to be mutually exclusive. The fourth is stored
as `UNENCODABLE_TIMESTAMP_REGRESSION` after the poisoned-session branch set by
`append_or_mark_unencodable`.

The audit must emit all four booleans. For a single descriptive `primary_reason` column,
the proposed frozen precedence is:

```text
SESSION_TIMESTAMP_REGRESSION
NO_IP_SESSION_KEY
UNSUPPORTED_IP_PROTOCOL_NOT_TCP_UDP
NONFINITE_TARGET_TIMESTAMP
```

The precedence changes no frozen detector behavior and cannot erase secondary true
predicates.

The following are explicitly not missing causes in the frozen implementation:

- 144-packet retained-state saturation;
- model batch/runtime failure;
- too-short flow or minimum token count;
- a missing value in an individual TShark field after sentinel normalization; or
- downstream P1/P2 scoring.

Any additional observed cause is an engineering/schema drift and produces no scientific
verdict.

## 4. Ordered audit stages

### M0 — static identity and branch audit

Verify document/code hashes and mechanically re-extract the four branch predicates. No
data array is opened. A mismatch is an engineering failure.

### M1 — reason-identifiability census

Open only plan, embedding metadata, and the pinned `uid`/`missing` arrays. Inventory all
already existing legal metadata/cache artifacts that could recover, for every target:

- IP-version/session-key availability;
- IP protocol;
- finite target timestamp; and
- per-session causal timestamp monotonicity through the target cutoff.

No PCAP, report, FINAL, label-only metric, representation vector, probe state, or model
weight may be opened.

If any missing terminal target lacks sufficient evidence to reconstruct every primitive
predicate that could apply, stop
with:

```text
NO_IDENTIFIABLE_MISSINGNESS_MECHANISM_WITHOUT_REDECODE
```

Per-device/family correlations cannot substitute for target-level attribution.

### M2 — exact deterministic attribution

M2 is entered only if M1 proves exhaustive target-level evidence. Recompute every missing
predicate and the frozen-precedence primary reason, with no fitted parameter or
stochastic operation.

Required conservation laws:

```text
sum(primary reason counts) == missing terminal sessions
finite + missing == all terminal sessions
each missing terminal has at least one true primitive predicate and exactly one primary reason
each finite terminal has no true missing predicate and no primary reason
```

### M3 — configuration-only feasibility classification

A cause is `CONFIGURATION_ONLY_REENCODE_CANDIDATE` only if changing a literal existing
resource/configuration value preserves all of:

- packet membership and order;
- session identity;
- causal target cutoff;
- protocol support and token semantics;
- checkpoint/model weights;
- fit/select roles and labels; and
- output dimensionality/meaning.

Changing protocol support, timestamp-order semantics, sessionization, tokenizer, retained
packet selection, or model code is `NEW_FRONTEND_SEMANTICS`, not a repair.

## 5. Required outputs

1. `frontend_f0_missingness_mechanism_verdict.json`
2. `frontend_f0_missingness_reason_by_target.csv.gz`
3. `frontend_f0_missingness_reason_by_device.csv`
4. `frontend_f0_missingness_reason_by_attack_family.csv`
5. `frontend_f0_missingness_identifiability_audit.json`
6. `SHA256SUMS`

All device/family rows, including zero-count rows, are retained. Devices, sessions, and
records are separate denominators.

## 6. Terminal states

```text
CONFIGURATION_ONLY_REENCODE_CANDIDATE
NEW_FRONTEND_REQUIRED_BY_INPUT_SEMANTICS
MIXED_MISSINGNESS_MECHANISMS
NO_IDENTIFIABLE_MISSINGNESS_MECHANISM_WITHOUT_REDECODE
```

The first state authorizes only a new re-encode protocol draft. The other states authorize
no execution. None of the states proves or disproves detector performance.

## 7. Claim boundary

The maximum claim is the exact frozen-E3 missingness mechanism on the pinned fit/select
terminal-session universe. This audit cannot claim that missingness causes hydraulic
false positives; existing committed diagnosis says hydraulic error survives after
excluding missing embeddings.

## 8. Authorization boundary

This draft authorizes nothing. After review and freezing, implementation, real artifact
opening, any cache read, any PCAP re-decode, and any re-encoding each require their own
explicit authorization.
