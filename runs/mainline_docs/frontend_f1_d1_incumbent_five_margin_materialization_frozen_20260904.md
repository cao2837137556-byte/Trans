# Frontend-F1 D1 incumbent five-margin materialization (FROZEN)

Date: 2026-09-04

Status: FROZEN before any incumbent continuous score for the five rows is
opened or computed.

## 1. Purpose

The terminal Frontend-F1 model flipped five protected A-side fit/internal-val
attacks. This one read-only materialization answers one narrow question:

> Were those same five attacks barely hard or strongly hard under the frozen
> incumbent E3 + P2?

It does not train, tune, select, reopen Frontend-F1, or evaluate any other row.

## 2. Frozen five-row allowlist

The allowlist is exactly the five rows in the committed diagnostic member
`f1_d1_terminal_flipped_attacks.csv`, SHA-256
`3adb43c349b59bc85a66024ef2533796081cca935a0f92ccd88cee008e7ca3be`:

```text
ton:ckbt_01dad899cff4388f69a7
ton:ckbt_03cee2b1ee1f725a3cc7
ton:ckbt_2430e72b8306da7ee37a
ton:ckbt_2f8a4b08f3ad6eaaeeea
ton:ckbt_31ba7d482a97ce8eb9d6
```

Order in the output is lexical UID order. Adding, removing, or replacing a UID
is an identity failure.

## 3. Frozen inputs

| input | SHA-256 |
|---|---|
| `runs/frontend_f1_d1_terminal_no_eligible_diagnostic_v1_20260904/f1_d1_terminal_flipped_attacks.csv` | `3adb43c349b59bc85a66024ef2533796081cca935a0f92ccd88cee008e7ca3be` |
| `runs/frontend_f1_d0_census_v1_20260902_local_r2/f1_d0_uid_context_phase_owner_conservation.csv.gz` | `c02937de7c5660688c60578adb2801f5a12b709745652fa8303b6c8e0d0b0ae9` |
| `runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/ckda_d1_fit_select_embeddings.npz` | `b1b4f2fde168a69e0cf7a53aaede2ddef9bd6d92b0ce58e56a9d6fcde37b6099` |
| `runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/ckda_d1_probe_state.npz` | `50a9bcfc18287d51bf8afda7367b57decdf3179dd41fc3aa61399d4098360c38` |
| `runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/ckda_d1_threshold_freeze_marker.json` | `84576a5008259f4381c46eecbc3ee3bda9d06b9dc7068cd52d7c2232e884dd5b` |

The embedding container has exactly 25,467 rows and 768 float32 coordinates.
The threshold must be the frozen P2 value `0.065159872174263`, with
`score >= threshold` hard.

## 4. Scope and row qualification

Before any representation coordinate is numerically decoded, all must hold:

1. the diagnostic allowlist contains exactly the five frozen unique UIDs;
2. the D0 census contains each UID exactly once;
3. every row is `phase=fit`, `owner=A`, `label_kind=attack`,
   `legal_fit=True`, `source_group=normal_scanning1.pcap`, and
   `attack_family=ToN-reconnaissance_scan`;
4. the container UID array is unique and contains every UID;
5. the five container rows all have `missing=false`.

Any failure is `F1_D1_FIVE_MARGIN_IDENTITY_OR_SCOPE_FAILURE` with no score
output.

## 5. Physically selective representation access

`representation.npy` inside the pinned NPZ is read sequentially as fixed-width
opaque row bytes. All 25,467 row blocks may pass through the decompressor, but
only the five allowlisted row blocks may be converted to numeric arrays or
retained. Required counters are:

```text
representation_container_rows_streamed_as_opaque_bytes = 25467
representation_rows_numeric_decoded = 5
nonallowlisted_representation_rows_numeric_decoded = 0
```

The full representation array may not be created. Existing select-score files
may not be opened. No PCAP is decoded.

## 6. Frozen computation and outputs

Apply the frozen normalizer and P2 state to the five numeric rows, with a
zero missing indicator, using the same float64 matrix computation already
audited for the Frontend-F1 teacher-benign count materialization. Persist one
CSV row per UID containing:

```text
uid, incumbent_logit, incumbent_score, threshold, score_margin,
logit_threshold, logit_margin, incumbent_hard
```

Raw margins are primary. The following descriptors are reporting aids only and
are not route gates:

- `EXACT_OR_ULP`: score equals the threshold or its immediate floating-point
  successor;
- `NEAR_0P1PP`: `0 < score_margin <= 0.001`;
- `INTERMEDIATE`: `0.001 < score_margin < 0.05`;
- `STRONG_5PP`: `score_margin >= 0.05`.

Every row must reproduce `incumbent_hard=true`; otherwise the materialization
is an identity failure. A JSON summary, boundary audit, and SHA256SUMS are
mandatory. No representation is persisted.

## 7. Claim boundary

This result can distinguish incumbent boundary proximity from terminal-student
forgetting for these five rows only. It cannot identify why every one of the 31
epochs was ineligible, cannot establish B-side attack safety, and cannot
authorize another training run.

Required zero counters:

```text
select_scores_opened = 0
nonallowlisted_numeric_rows = 0
viewed_opened = 0
report_opened = 0
final_opened = 0
pcap_opened = 0
parameters_fitted = 0
optimizer_steps = 0
training_or_resume_started = 0
```

## 8. Authorization boundary

The user's 2026-09-04 instruction authorizes this exact five-row read-only
materialization and its durable audit package. It does not authorize model
changes, threshold changes, another seed/epoch/run, select/viewed/report/FINAL,
or deployment.
