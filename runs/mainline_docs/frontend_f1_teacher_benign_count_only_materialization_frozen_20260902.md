# Frontend-F1 teacher-benign count-only materialization protocol

Status: **FROZEN**

Date: 2026-09-02

Scope: one local, read-only materialization of the incumbent P2 hard/normal counts for the already identified legal-fit, owner-A, true-benign denominator. This protocol does not authorize Frontend-F1 D1 training.

## 1. Question and single permitted output

Frontend-F1 D0 stopped because the old P2 verdict split for legal-fit benign owner-A rows was not available in a count-only artifact. This run may answer only:

> Among the frozen legal-fit, owner-A, true-benign rows, how many incumbent P2 scores are hard (`score >= theta_0`) and how many are normal?

The permitted scientific output is an aggregate count artifact plus a UID-only audit table containing `uid`, `hard`, and no score value or representation. Device/source/context aggregates are forbidden in this run because they are not needed to close D0.

## 2. Frozen inputs

| Input | SHA-256 |
|---|---|
| Frontend-F1 D0/D1 FROZEN contract | `98f2b73a051ee9c392631e85f4cc84d787306ed8333bfe2125f77870790c41b4` |
| D0 r1 UID/context/phase/owner conservation table | `c02937de7c5660688c60578adb2801f5a12b709745652fa8303b6c8e0d0b0ae9` |
| CKDA fit/select embedding container | `b1b4f2fde168a69e0cf7a53aaede2ddef9bd6d92b0ce58e56a9d6fcde37b6099` |
| CKDA frozen P2 probe state | `50a9bcfc18287d51bf8afda7367b57decdf3179dd41fc3aa61399d4098360c38` |
| CKDA threshold marker | `84576a5008259f4381c46eecbc3ee3bda9d06b9dc7068cd52d7c2232e884dd5b` |

The threshold identity is the marker's P2 value `theta_0 = 0.065159872174263`. Exact ties are hard because the frozen decision rule is `score >= theta_0`.

## 3. Authorized denominator

The allowlist is derived mechanically from the pinned D0 r1 conservation table:

- `legal_fit == true`;
- `owner == A`;
- `label_kind == benign`.

The frozen expected denominator is exactly `7,347` unique UIDs. Any mismatch, duplicate, missing UID, owner drift, phase drift, or label drift is an engineering failure with no scientific verdict.

## 4. Narrow array-access semantics

The NPZ is a compressed container, so byte-level decompression of the `representation.npy` member is unavoidable. The implementation must nevertheless preserve semantic isolation:

1. `uid` and `missing` may be decoded for all 25,467 rows solely to establish row identity and confirm all allowlisted rows are old-finite (`missing=false`).
2. `representation.npy` must be read sequentially as opaque row bytes. Only allowlisted row bytes may be converted into numeric arrays. Non-allowlisted row bytes must be discarded without `numpy` conversion, score computation, persistence, aggregation, or inspection.
3. Exactly 7,347 representation rows may be numerically decoded and exactly 7,347 P2 scores may be computed.
4. Select, cross-phase fit, attack, owner-B, viewed, report, and FINAL scores computed must all equal zero.
5. The probe state may be opened only to reconstruct the already frozen normalizer and P2; fitting, optimizer steps, threshold selection, checkpoint mutation, and parameter writes are forbidden.

## 5. Frozen score reconstruction

The computation must be byte-for-byte semantically identical to the accepted CKDE Stage-P reconstruction:

1. cast selected 768D representations and frozen normalizer to float64;
2. apply `(representation - normalizer_mean) / normalizer_scale`;
3. append the missing indicator (which must be false for every selected row);
4. apply frozen `p2__0.weight/bias`, ReLU, frozen `p2__3.weight/bias`;
5. apply numerically clipped sigmoid;
6. classify `score >= theta_0` as hard.

No score value may be written to disk. Only the Boolean verdict is permitted in the UID audit table.

## 6. Required outputs

- `f1_teacher_benign_counts.json`: denominator, hard, normal, threshold identity, and conservation equation `hard + normal == rows`;
- `f1_teacher_benign_uid_verdicts.csv.gz`: sorted `uid,hard` only;
- `f1_teacher_benign_input_audit.json`: pinned identities and exact-UID join checks;
- `f1_teacher_benign_boundary_audit.json`: all access and prohibition counters;
- `f1_teacher_benign_validation_report.json`;
- `SHA256SUMS`.

The result is valid only if every output file hashes cleanly and all boundary counters satisfy this protocol.

## 7. D0 re-closure

After successful materialization, Frontend-F1 D0 may be rerun into a new immutable result directory. That rerun may open only the aggregate count JSON and UID Boolean audit, never the embedding or probe-state inputs used by this materializer. It must verify:

- the count artifact SHA-256;
- exact UID equality with its own legal-fit benign owner-A denominator;
- `hard + normal == 7,347`;
- no owner-B teacher row is introduced;
- the original D0 conservation equations and synthetic resource gate still pass.

Only `F1_D0_CENSUS_PASS` is a D0 feasibility result. It authorizes drafting the numerical/training addendum; it does not authorize D1 training, score opening on select/viewed/report/FINAL, threshold changes, or a performance claim.

## 8. Fail-closed states

- implementation or identity failure: `ENGINEERING_FAILURE_NO_SCIENTIFIC_VERDICT`;
- wrong or incomplete authorized denominator: `F1_TEACHER_BENIGN_DENOMINATOR_FAILURE`;
- boundary violation: `F1_TEACHER_BENIGN_SCOPE_VIOLATION`;
- successful materialization: `F1_TEACHER_BENIGN_COUNTS_MATERIALIZED`.

## 9. Authorization boundary

User authorization dated 2026-09-02 covers this one count-only materialization and the D0 re-closure described above. It does not authorize Frontend-F1 D1 training, a real checkpoint, model selection using outcomes, select/viewed/report/FINAL access, HPC, or publication claims.
