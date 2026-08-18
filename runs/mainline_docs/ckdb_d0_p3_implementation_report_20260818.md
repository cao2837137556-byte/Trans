# CKDB D0-P3 implementation report — 2026-08-18

Status: `IMPLEMENTATION_COMPLETE_OFFLINE`

## Scope

Implemented the executor for the frozen CKDB D0-P3 combined large-download,
boundary-verification, and benign-census protocol. This work consumed the
user's implementation authorization only. It made zero HTTP requests, used no
portal credentials, downloaded no package body, submitted no HPC work, trained
no model, selected no threshold, and did not open FINAL.

Frozen protocol SHA-256:

```text
de864fdb54a071a4db082c79071188f1445c244cd5c05376a4ad4f191fade5a1
```

## Implemented artifacts

| artifact | SHA-256 | bytes | lines |
|---|---|---:|---:|
| `repo/ood/issue27ckdb_d0_p3_combined_large_download_and_census_v1.py` | `8ad84fefb03dd32f55bae860b996a54a6a7984632cec6100deeba7185c9b81e5` | 76,336 | 1,757 |
| `repo/ood/test_issue27ckdb_d0_p3_combined_large_download_and_census_v1.py` | `2a05e93218fa747df00da4454680de67e4c7eda5f4820131b7e58851921d0f0e` | 22,052 | 478 |
| `runs/mainline_docs/ckdb_d0_p3_execution_plan_20260818.json` | `8d5010647134096d4494006e43b30c7752fde5ed8b103582d51b792f4e6862a1` | 4,429 | 131 |

The execution plan has a matching SHA-256 sidecar. The frozen CKBU causal
TShark decoder is pinned at
`127efd212932d9330af790f17a069a84b3ee48205d68bed7e2e9f00778bb2820`.

## State-machine implementation

The executable exposes six explicit commands:

1. `validate`: offline frozen-contract and execution-plan identity check;
2. `preflight`: independently reviewed P0-A--P0-C appendix plus fresh P0-D
   storage/inode gate;
3. `transfer`: literal-authorization-gated resumable HTTPS transfer with exact
   final-host, size-cap, byte-count, checksum, archive-magic, and atomic
   promotion gates;
4. `boundary`: archive inventory before packet decoding, five-way PNNL member
   classification, CIC benign-only verification, and named scientific-stop
   verdicts with no replacement-corpus path;
5. `extract`: only the frozen benign member allowlists are materialized;
6. `census`: pinned causal decoder, member-level restartable checkpoints,
   deterministic holdout exclusion, I1 session/token gate, six-region U2
   support census, deterministic result package, and SHA-256 sidecar.

Boundary failures and engineering failures remain distinct: a boundary failure
is a valid named scientific stop, while an engineering failure removes
scientific result files and emits only `ENGINEERING_FAILURE_NO_VERDICT`.

## Verification

The required contract suite passed:

```text
Ran 33 tests in 0.447s
OK
```

Additional checks passed:

- both implementation and test modules parse under Python 3.9 grammar;
- both modules compile with the local Python runtime;
- the full CLI help/dispatch surface loads successfully;
- no known `Path.write_text(newline=...)`, `Path.read_text(newline=...)`, or
  `match/case` Python-version regression remains;
- deterministic pullback generation is byte-identical across repeated runs;
- an offline three-archive end-to-end rehearsal passed boundary inventory and
  benign-only extraction with four allowed captures and zero attack/fault
  extraction.

The first rehearsal attempt stopped in its temporary test fixture before the
executor ran because the fixture parent directory had not been created. After
fixing the fixture, the unchanged executor completed the rehearsal. This was
not an implementation or protocol failure.

## Current gate

The implementation is ready for construction of the separately hashed P0
launch appendix from authenticated portal metadata. It is **not** a download
authorization. Before any transfer, the appendix identities must be fixed, the
fresh storage gate must pass on the actual D: destination, and the user must
explicitly authorize the transfer against that exact appendix hash.
