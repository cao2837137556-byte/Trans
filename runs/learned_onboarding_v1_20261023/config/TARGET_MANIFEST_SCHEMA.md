# Target bank producer binding

This is an input declaration format, not a target manifest or evidence that any
target assets are ready. Every `path` must identify an existing file and every
`sha256` must be its actual SHA-256. The complete target manifest is itself
SHA-256 pinned by the `evaluate` CLI before any pool is opened.
The loader also receives the complete verified source binding and its digest;
historical parent manifests and spool must match that binding.

The manifest must have schema `learned-onboarding-target-inputs-v1`, status
`SEALED`, `synthetic_only: false`, the frozen spec SHA, source binding digest,
the original seed-27 cut, source normalizer SHA, lineage and parent-parity
identities, and exactly `CIC_DEV` and `UNSW_DEV` pools. Each pool has one
ordered-UID query bundle and exactly `OLD_BANK`, `B0`, `B1`, `B2` bank bundles.
Bundles supply independently pinned `rows` (JSONL or JSONL.gz), `e3` and
`q14` (`.npy`), `feature_uids` and `q_uids` (one UID per line). Query bundles
also supply pinned scalar `scores` (`.npy`), `score_head: QUERY_TAIL_27` and
`ordered_uid_sha256`. The caller separately verifies the query scores by the
accepted head replay path. `bundle_io.write_bundle` writes this interchange
format and returns its five pinned file declarations from already verified
ordered inputs. The pinned query score file is promoted exactly to a float64
transport baseline before comparison and correction.

Every modern bank declaration has this additional shape:

```json
{
  "producer_kind": "encoded-selected-v2",
  "producer_receipt": {
    "path": "encoded/CIC_DEV/B2/receipt.json",
    "sha256": "<actual receipt SHA-256>"
  },
  "producer_receipt_sha256": "<same actual receipt SHA-256>"
}
```

The pinned `receipt.json` must be the real `encode_selected` COMPLETE producer
receipt for that policy, with `synthetic_only: false`, real RECENT features,
complete candidate census, fixed input version/readout, 768/14 dimensions,
no training/scoring, and the same source normalizer SHA. The receipt pins its
`bank.npz`, `references.jsonl.gz`, `tensor_receipts.jsonl.gz`, and
`environment.json`. The loader checks producer UID digest, tensor UID/slot
join, reference role, and bitwise equality of all declared bank rows, UID
order, E3 and q14 with those producer files.

`OLD_BANK` uses an explicitly constructed historical export receipt. Its bank
declaration has the same two receipt path/SHA fields and
`producer_kind: historical-old-bank-v1`. The receipt must have schema
`learned-onboarding-historical-bank-export-v1`, status `SEALED`,
`synthetic_only: false`, the exact pool/partition, policy `OLD_BANK`,
`source_method: parent_cache_uid_slot_replay`, the source normalizer SHA,
ordered UID hash, row count, and hashes for `bank.npz` and
`references.jsonl.gz`. It must contain exactly these pinned source assets:

```json
{
  "source_assets": {
    "parent_cache_binding": {"path": "<cache binding JSON>", "sha256": "<actual SHA-256>"},
    "parent_input_manifest": {"path": "<inputs/SHA256SUMS>", "sha256": "<actual SHA-256>"},
    "parent_feature_manifest": {"path": "<features/SHA256SUMS>", "sha256": "<actual SHA-256>"},
    "parent_normalizer_manifest": {"path": "<normalizers/SHA256SUMS>", "sha256": "<actual SHA-256>"},
    "parent_metadata": {"path": "<parent JSONL or JSONL.gz>", "sha256": "<actual SHA-256>"},
    "parent_e3": {"path": "<parent feature NPY>", "sha256": "<actual SHA-256>"},
    "parent_q14": {"path": "<parent q14 NPY>", "sha256": "<actual SHA-256>"},
    "parent_spool": {"path": "<parent spool/snapshots.sqlite>", "sha256": "<actual SHA-256>"},
    "normalizer": {"path": "<accepted RECENT normalizer NPZ>", "sha256": "<actual SHA-256>"},
    "lineage_map": {"path": "<export UID/parent slot JSONL or JSONL.gz>", "sha256": "<actual SHA-256>"}
  }
}
```

The lineage map has one ordered record per exported reference with `uid` and
the original `parent_slot`. The parent cache roles are `SOURCE_REFS` for CIC/DEV
and `UNSW_REFS` for UNSW/external archival; the role metadata and feature NPY
refer to those full parent roles, including unselected rows. The loader requires
matching parent UID, device, partition, protocol, component, capture, frame,
timestamp and label; E3 first 768 columns and exported q14 must equal the
arrays at the declared full-role slots. It calls the original
`constrained_onboarding_reference_v2.extract_old_bank_q14` on the pinned
`snapshots.sqlite` and the exported rows with `parent_slot`, and requires
bitwise equality with both the export and materialized parent q14 NPY.
The old parent cache binding and SHA256SUMS files must bind the role metadata,
role feature and RECENT normalizer hashes; its spool SHA must equal both the
pinned SQLite file and the currently verified source binding. If the old parent
assets or exact mapping are unavailable, `OLD_BANK` is input-not-ready; a
general success receipt is insufficient.
