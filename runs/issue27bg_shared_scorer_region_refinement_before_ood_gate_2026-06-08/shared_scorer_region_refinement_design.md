# Shared Scorer Region Refinement Design

This run replaces the issue27bd/issue27bf two-head raw scorer with one shared HistGB attack scorer.

- Fixed frontend: Gotham Kitsune115 115D.
- Fixed split: issue27af/issue27ba/issue27au roles.
- Positives: medium attack train + active heavy confirmed train.
- Negatives: ID train + OOD train + OOD stress train.
- Region bank: bounded HH_HpHp cluster-kcenter evidence layer, not the main classifier.
- Selection roles exclude final OOD, medium attack eval, and dev-heavy query.
- Go gate for OOD repair: attack hard min >= 0.93, OOD stress <=2%, review <=5%.
