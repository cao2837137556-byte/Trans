# CKBV r15 formal dependency-closure repair

## Scope

CKBV r14 jobs AMD `154875` and Intel `154876` reached
`formal_seed27_model` through validated checkpoint reuse, then failed before
model execution because the transfer payload omitted four frozen artifacts
required by `issue27ckc.validate_inputs()`.

This repair changes packaging and launch validation only. It does not change
the frozen manifests, target rows, 51D features, raw51 eligibility mask,
fit/select/report roles, labels, thresholds, candidates, seed, decision rules,
or evaluation denominators. The failed r14 jobs are not scientific evidence.

## Frozen formal dependency closure

The r15 bundle includes these exact repository-relative paths:

| Path | Repository bytes | Repository SHA-256 | Canonical UTF-8/LF SHA-256 |
| --- | ---: | --- | --- |
| `runs/issue27cf_initial_support_bank_instantiation_from_complete_exact_label_pool_2026-06-16/support_bank_sidecar.csv` | 320996 | `74d59f41e43fe58a6b82d6a2ac2174cad9dd87fa0b05792895769b8b426c92da` | `1db1e0e090398218f1d107e8468e17ac457c9e837c389722036b27b74e4962dd` |
| `runs/issue27ch_certified_attack_subset_freeze_for_protocol_replay_2026-06-17/certified_chunk_manifest.csv` | 31560 | `ea222d777ea9911264e906418749868936810a8bf8c4f185078fb190ca7ed851` | `ea222d777ea9911264e906418749868936810a8bf8c4f185078fb190ca7ed851` |
| `runs/issue27ch_certified_attack_subset_freeze_for_protocol_replay_2026-06-17/certified_attack_subset_v1.json` | 14783 | `61032d8a85e64160c48c4ad7a5724cdf202746f0d9510686d0b10acc2e60c3bf` | `940842193c5e56db679270135d3c9d9fbbf1db0b14bfa01048435bfb6fae3d0c` |
| `runs/issue27bu_unified_temporal_attack_ood_heads_certification_2026-06-10/unified_two_head_selection_audit.csv` | 3665 | `68e9c2a1aef4ebde4095f873764247b12401e1c997802d89c3c794b9965e4f4a` | `3fa394628211df286dd71d66da077201c9b6fd85367d9a7f2c9d7593d6a4f189` |

Three source files use CRLF in the Windows checkout. The bundle builder
already canonicalizes every text payload to UTF-8/LF, so the formal closure
gate deliberately binds the canonical LF hashes shown above. This is a
transport representation rule only; parsed records are unchanged.

## Permanent gates

1. The four artifacts are explicit `$payloadFiles` entries and therefore
   covered by bundle `SHA256SUMS`.
2. The Python formal program checks exact relative paths and canonical LF
   hashes in both `contract-unit` and `run-formal`.
3. The installer checks the four bundle-local files before scheduler
   validation or submission.
4. The Slurm script checks the same four files on the compute node before
   creating a run root.
5. Clean-extract testing intentionally removes one dependency and requires the
   formal contract to fail for the expected reason, then restores it and
   requires a pass.

## Reuse and recomputation

r15 may reuse only checkpoints accepted by the existing identity, schema,
coverage, and hash validators. The packaging failure does not invalidate
Gotham member/source caches, auxiliary caches, or ToN caches, so no raw PCAP
re-decoding is required. AMD and Intel remain independently writable
partition/job-isolated infrastructure copies of the same preregistered
seed-27 experiment.
