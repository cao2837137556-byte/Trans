# issue27bx2 Quota And Cache Repair Report

This issue repairs the materialization planning layer only. It does not train models, tune thresholds, or rerun a formal benchmark.

## Findings

- issue27bx emitted rows by role: `{"attack_support_candidate_pool": 20000, "dev_future_attack_query": 35000, "id_benign_calib": 5832, "id_benign_train": 65751, "ood_benign_stress": 35000, "ood_benign_val": 14772, "sealed_final_attack": 15000, "sealed_final_ood": 35000}`
- issue27bx file quota shortfalls: `2` files
- Shortfalls are treated as materialization planning issues, not model failures.
- Same-role fallback is required; sealed final roles must never backfill dev/train roles.

## Fallback Policy

1. Use only files already assigned to the same contract role.
2. Never borrow from `sealed_final_ood` or `sealed_final_attack`.
3. Prefer files already verified by issue27bx when possible.
4. If same-role capacity is still insufficient, lower that role quota or revise the contract explicitly.

## Cache Policy

- Cache per-file 115D outputs keyed by `(schema, state strategy, csv path, pcap path, role, warmup)`.
- Cache must include source hashes, emitted rows, sidecar rows, numeric audit, and state strategy.
- Attack PCAPs and large benign files should be cached before any 3M+ retry.
