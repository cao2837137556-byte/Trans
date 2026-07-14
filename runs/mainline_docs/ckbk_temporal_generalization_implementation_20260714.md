# CKBK implementation and pre-submission audit

Date: 2026-07-14

Status: implementation complete locally; formal HPC not submitted.

## What changed

- `issue27ckbk_temporal_generalization_formal_v1.py` implements the repaired
  TGN and GraphMixer comparison, strict metrics, representation audit, and
  failure-tolerant aggregation.
- `issue27ckbk_dyglib_graphmixer_v1.py` vendors/adapts the mature DyGLib
  GraphMixer time/message Mixer at upstream commit
  `3aacc36b94b8d2d8293d70a74fdf6d39089b4163`; the MIT license is preserved.
- `issue27ckbk_temporal_generalization_contract_tests_v1.py` checks causal
  masks, blocked future labels, reset, gate, identity, and final-holdout
  contracts without training.
- One Slurm allocation runs TGN, GraphMixer, and aggregation as independent
  child processes.  AMD and Intel submissions have isolated partition/job
  output paths.

CKBE, CKBI, CKBJ caches, the original 26-source manifest, the four-source
report extension, and the strict 1M split are read-only.

## Data flow

```text
frozen strict 1M roles + frozen CKBE/CKBI event caches + frozen C1 caches
  -> per-held C1 fit/select with complete held-family exclusion
  -> exact source/phase target mask (interleaving allowed only when mapped)
  -> stage 1: unchanged PyG TGNMemory repair + random + verifier-only
  -> stage 2: DyGLib GraphMixer Full-Anonymous + MessageOnly + Random
  -> legal select representation audit and complete attack-preserving gate
  -> frozen no-gradient blind report, review=0
  -> failure-tolerant aggregate and preregistered seed-27 decision
```

## Frozen role counts

The cohort and caps are unchanged from the contract-valid CKBJ run.  CKBK
recomputes and writes these counts before each child stage.

| Protocol | fit attack | fit benign | select attack | select benign | report |
|---|---:|---:|---:|---:|---:|
| Global preservation | 385 | 12,000 | 69 | 9,000 | 301,931 |
| Held stream-consumer | 385 | 8,000 | 69 | 6,000 | 3,000 |
| Held hydraulic-system | 385 | 10,604 | 69 | 6,000 | 3,000 |
| Held domotic-monitor | 385 | 12,000 | 69 | 9,000 | 3,000 |
| Held combined-cycle | 352 | 12,000 | 63 | 9,000 | 5,486 |
| Held ip-camera-street | 385 | 12,000 | 69 | 9,000 | 3,000 |

Support-val lineage remains `512 -> 385 train + 127 validation -> 58 temporal
fit validation rows excluded -> 69 legal select rows`.  Global support family
counts remain 15, 18, 30, 43, 60, 30, 9, 60, 60, and 60 across the ten attack
families.  Family balancing uses every legal support row at least once in each
of 30 verifier epochs and reports every row/family use count.

## Replay and feature safeguards

- Three sources have genuinely interleaved fit/select targets.  CKBK uses an
  exact per-event allowed/blocked mask; it never infers a boundary from
  `max(fit)`.
- Every sidecar row assigned to support-val/select/future/sealed/report is
  mapped to its raw event position and blocked from fit context; this is not
  limited to scored targets.  Every report-assigned event is blocked from
  select context.  Legal targets override only aggregate cross-fold stage
  labels for their current protocol, never a hard role assignment.
- Every source and phase starts fresh.  The current target is scored before
  update.  Report is no-gradient, label-free, and actual-past-only.
- GraphMixer node/source IDs index only local history dictionaries.  No ID
  embedding, source feature, device/family feature, raw IP/MAC, role, or label
  is accepted by the model.
- The new final holdout is `iotsim-cooler-motor` across five single-family
  sources.  It is hashed and explicitly not opened by CKBK seed 27.

## TGN task and negative contract

The original four task definitions remain.  Outcomes may use only later raw
events inside the legal fit mask and horizon.  Non-link tasks require at least
64 examples per class, prevalence 5--95%, at least three labeled sources, and
each class in at least two sources.  Link requires at least 128 positives and
128 source-local past-seen negatives across at least three sources.  A
degenerate task is disabled and audited; weighting cannot make it eligible.

Negatives are preregistered from the current source's already observed legal
nodes, excluding current endpoints and the maintained PyG last-neighbour set.
Ghost nodes, future identities, held sources, and report sources are invalid.

## Mature components

PyG: `TGNMemory`, `IdentityMessage`, `LastAggregator`,
`LastNeighborLoader`, TGN internal `TimeEncoder`, and the official-example
`TransformerConv` embedding.

DyGLib GraphMixer: fixed cosine `TimeEncoder`, edge/time projection, and two
official-shape MLP-Mixer blocks with the upstream default `K=20`, expansion
factors `0.5/4.0`, and dropout `0.1`.  The anonymous-node adapter is the only
paper-specific model input change and has a MessageOnly ablation.

## Local evidence

- Python compilation passed for all three Python files.
- Bash syntax checks passed for the Slurm, installer, status, and pack scripts.
- `ckbk_contract_unit.json`: `PASS`.
- `ckbk_contract_tests.json`: `PASS`, including exact interleaving masks,
  blocked-future invariance, source reset, no fallback, no ID/label argument,
  and sealed-final exclusion.
- `real_sidecar_role_block_audit.json`: `PASS` on the actual frozen 1M
  sidecars.  GLOBAL and all five held protocols have zero legal-fit overlap
  with hard-blocked roles and zero legal-select overlap with report roles.
- No environment was created and no dependency was installed.
- No HPC job was submitted.

## Resources

The prior completed CKBJ job used about 15.4 GiB MaxRSS, 1:28 wall time, and
8:28 TotalCPU.  CKBK adds one cached GraphMixer feature pass and more models,
but child stages are separate processes, so their peak memories do not add.
The request is therefore `8 CPU`, `32 GiB`, and `12 hours`, not the previous
oversized `16 CPU / 128 GiB / 48 hours` request.

## Formal outputs

Each stage writes role/held audits, the hashed phase manifest, loss curves,
support use, memory/replay audit, complete gate table, attack and strict held
metrics, per-family metrics, select AUROC/AUPRC/low-FPR diagnostics, score
distributions, and learned-versus-random bootstrap deltas.  The aggregate
writes a route decision CSV/JSON and retains partial child results if one child
fails.  Slurm adds wall time, exit codes, job/partition identity, and in-job
accounting.  Seeds 37/47 are never launched automatically.
