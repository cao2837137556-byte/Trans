# CKDA D1 local contingency L0 precompute result

Date: 2026-08-14
Implementation commits: `8ed6d7f`, `b27f734`, `0b45df3`
Scientific contract SHA-256: `ecb429926507d2c4f8f666edc2d7e50f3e94fc2ec74bc1e26e78ca4813950aa9`

## Verdict

`CKDA_D1_LOCAL_L0_PRECOMPUTE_PASS`

This verdict authorizes no performance claim. It records that the local contingency path has completed all label-free/pre-embedding work and stopped before E3 fit/select embedding pending independent review.

At the stop point:

- `performance_embeddings_generated = 0`
- `i1_training_started = false`
- `i1_embeddings_generated = 0`
- `raw_label_columns_read = 0`
- `final_files_opened = 0`
- `report_opened = 0`
- `embeddings_started = 0`

Current phase: `precompute_complete_embedding_pending_kimi_review`.

## 1. Contract and implementation gates

- Frozen CKDA D1 contract hash: PASS.
- Frozen snapshot/predictions/model hashes: PASS.
- Python 3.9.13 and TShark 4.6.6: PASS.
- Frozen CKDA D1 contract tests: 46/46 PASS.
- Local Python 3.9 grammar gate: PASS.
- PowerShell runner/status parser gates: PASS.
- Local runner is resumable and isolates checkpoints under `localwin`.

## 2. Formal-manifest local path rebinding

The formal D0 fit-prefix manifest remains pinned at SHA-256 `9184cd018efcc6547832bf04ce6d3046c687b8e48cac73234482d9fb3ba89689`.

The generated local derivative:

- rows: 27
- container path cells changed: 27
- non-path cells changed: 0
- lineage-source cells changed: 0
- local derivative SHA-256: `afd8f700e64d799d15c2375c3a887b388423a982c7af72d1cb45b85de2ac8e01`
- status: `CKDA_D1_LOCAL_MANIFEST_PATH_REBIND_PASS`

Thus only storage locations were rebound; source IDs, PCAP members, inclusive cutoffs, roles, dataset kinds, and original lineage identities were unchanged.

## 3. Real-input E3 equivalence gate

Preflight exposed a formal frontend defect: CKBU's 24 requested TShark fields and D0 netFound's 27 requested fields are not supersets. The repaired ordered union contains 39 fields. This is a pre-result engineering repair and is independent of labels, families, and performance.

The frozen one-pass embedder and the local memory-bounded two-pass embedder were run on the same 32 real target prefixes:

- member: `raw/benign/iotsim-building-monitor-2_0-0_to_OpenvSwitch-28_2-0.pcap`
- maximum event position: 149
- batch size: 16
- representation width: 768
- frozen checkpoint SHA-256: `f19c06bac8197a0cae88c19bb69d38c1d974b91f4525aec91fadea9f40875161`
- local checkpoint SHA-256: `f19c06bac8197a0cae88c19bb69d38c1d974b91f4525aec91fadea9f40875161`
- maximum absolute representation delta: `0.0`
- frozen/local round-6 representation SHA-256: `bdbaa2814e38bb1340ffa5abe403ba8d32e980fb0565065e327f5c9982bc0a09`
- verdict: `CKDA_D1_LOCAL_TWOPASS_REAL_EQUIVALENCE_PASS`

All checkpoint metadata arrays were also exact. This gate supports local fit/select execution but does not remove the later HPC confirmation requirement.

## 4. Exact benign-only I1 census

All 20 allowed benign members were re-decoded locally; no D0 census checkpoint was reused.

| Measure | Exact value | Frozen minimum | Result |
|---|---:|---:|---|
| benign fit sessions | 8,735 | 500,000 | FAIL |
| benign fit tokens | 697,387 | 10,000,000 | FAIL |
| visible packet upper bound | 2,182,190 | — | informational |

Additional identities:

- excluded members: 7
- member-manifest SHA-256: `2ecf10f6512d7fab4121633c6c51520f9c8510cf57417e1a54c79a449f20e5e8`
- status: `CKDA_D1_PRIMARY_PRECONDITION_FAILED`

The exact result is even farther below the I1 minimum than the earlier packet upper bound. Per the frozen state machine, I1 did not train and E3 opened cleanly:

`CKDA_D1_FROZEN_PROGRESSION_PASS`, selected candidate `E3`.

This is the preregistered fallback, not post-result candidate selection.

## 5. Fit/select target plan

- plan rows: 25,467
- fit rows: 18,398
- select rows: 7,069
- plan SHA-256: `eed3d431ab8d71117db7a02b5ee0022eefe7932888001e7d9bcccfd54199aeac`
- target metadata SHA-256: `d6fbba24a1997db24597a800cf952f80f739284e5ca13db5ce04497f1540c36d`
- Gotham rows: 3,867
- auxiliary rows: 9,600
- ToN rows: 12,000
- unique UIDs: 25,467
- FINAL files opened: 0
- threshold marker: `NOT_OPENED`

## 6. Preserved engineering failures

Two launch-time engineering failures are retained with null scientific verdicts:

1. A local path-rebound manifest was incorrectly checked against the formal HPC byte hash. The repair now pins the formal manifest and independently audits a path-only derivative.
2. Windows PowerShell 5.1 treated a Transformers `FutureWarning` on stderr as fatal despite a non-failing Python path. The repair uses native process exit code as the success criterion and preserves stdout/stderr separately.

Neither failure started a performance embedding, opened report, or touched FINAL.

## 7. Requested independent review and next action

Kimi is asked to review the companion addendum and decide whether:

1. the fixed 39-field union is the minimal correct frontend repair;
2. the two-pass state filter is semantically exact;
3. the byte-identical real gate is sufficient for local fit/select authorization;
4. report isolation remains intact.

On PASS, rerun the same local launcher with the reviewed-embedding gate. It will reuse L0 artifacts, generate 25,467 E3 fit/select embeddings, fit G0/P1/P2, freeze thresholds, and stop again before report.
