# Support Bank Go/No-Go

primary_verdict: `initial_support_bank_contract_ready_with_attack_taxonomy_limit_caveat`

## Checks

- Candidate pool rows: `90000` total, `89900` legal model-ready rows.
- Attack types in legal candidate pool: `{'Telnet Brute Force': 89900}`.
- File/phase region buckets: `8`; region cap pass: `True`.
- Forbidden role contamination in legal candidate pool: `0`.

## Caveats

- Current certified 1M support candidate pool contains only `Telnet Brute Force` attack labels.
- The contract can define a clean initial support bank, but it does not yet prove multi-attack taxonomy coverage.
- Larger or formal experiments need either additional legal attack-support candidate diversity or a scoped claim limited to this attack family.
- This issue does not train models and does not report detection performance.
