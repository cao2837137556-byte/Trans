# Broader Attack Support Candidate Contract v1

primary_verdict: `broader_support_contract_partial_needs_targeted_multitype_materialization_and_onset_realign`

## What This Issue Did

- Read the certified 1M sidecar and split manifest in read-only mode.
- Streamed only the relevant processed CSV label rows from `GothamDataset2025.zip` to verify exact per-row attack labels.
- Did not modify extracted 115D assets, did not rerun feature extraction, and did not train models.

## Key Finding

`sidecar.first_attack_label` is too coarse for multi-attack support taxonomy. Exact CSV label audit shows the current legal support pool is broader than issue27ca suggested, but still incomplete.

- Current legal support model-ready rows: `89900`.
- Exact attack rows after excluding benign labels: `86336`.
- Support exact-label purity: `0.960356`.
- Current support attack types: `{'Ingress Tool Transfer': 214, 'TCP Scan': 46685, 'Telnet Brute Force': 39437}`.
- Benign contamination inside rows previously marked attack by alignment: `3564`.
- Missing attack types from preregistered support files: `['C&C Communication', 'File Download', 'Merlin C&C Communication', 'Merlin ICMP Flooding', 'Merlin TCP Flooding', 'Merlin UDP Flooding', 'Mirai C&C Communication', 'Mirai GRE Flooding', 'Mirai TCP Flooding', 'Mirai UDP Flooding', 'Reporting']`.

## Boundary

- This is still a data-contract issue, not a model-performance issue.
- Do not use `dev_future_attack_query` or `sealed_final_attack` rows as support.
- Current 1M query/final attack rows also need onset/label realignment before performance replay because some role rows audit as benign by exact CSV labels.
