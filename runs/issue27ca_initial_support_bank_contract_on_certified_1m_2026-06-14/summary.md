# issue27ca_initial_support_bank_contract_on_certified_1m_2026-06-14 Summary

1. issue27ca completed: yes
2. primary_verdict: `initial_support_bank_contract_ready_with_attack_taxonomy_limit_caveat`
3. task type: initial support bank contract and coverage audit
4. model training: no
5. formal benchmark: no
6. certified 1M asset used: yes
7. legal support candidate rows: `89900`
8. initial support budgets audited: `[32, 64, 128, 256]`
9. default budget proposal: `B=128` total, not per attack type
10. default split proposal: `support_train=96`, `support_val=32` when B=128
11. attack types in current candidate pool: `{'Telnet Brute Force': 89900}`
12. region buckets: `8`
13. forbidden final/report-only contamination: `0`
14. biggest caveat: support candidate taxonomy is currently narrow; only Telnet Brute Force appears in the 1M candidate pool.
15. next recommended issue: define attack/OOD head training contract on this support bank, or revise larger attack-support contract if broader attack taxonomy is required.
16. commit/push: not performed
