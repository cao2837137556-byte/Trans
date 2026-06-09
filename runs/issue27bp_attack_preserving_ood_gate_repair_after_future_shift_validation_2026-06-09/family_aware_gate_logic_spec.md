# Family-Aware Attack-Preserving OOD Gate

- Raw attack score stays on full Kitsune115.
- Attack-core evidence uses a selected Kitsune family subspace.
- Benign/OOD-risk evidence uses a separately selected family subspace.
- Strong attack-core alarms cannot be suppressed by the OOD gate.
- Weak attack alarms that sit inside the benign/OOD core can be suppressed.
- Attack/OOD conflicts are sent to bounded review before overflow handling.
- Final/report-only roles are replay-only and never select subspaces, thresholds, prototypes, or review budgets.
