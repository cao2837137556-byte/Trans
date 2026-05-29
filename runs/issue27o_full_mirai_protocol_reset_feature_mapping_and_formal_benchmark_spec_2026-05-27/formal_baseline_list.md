# Formal Baseline List

Required rerun methods:

- LOW-GUARD++ HistGB-Conservative
- LOW-GUARD-LR minimal instance
- raw LR without guard
- threshold-only LR
- no OOD guard
- no threshold guard
- HistGB shallow
- Isolation Forest
- OC-SVM
- DevNet-style score head
- DeepSAD-style lite objective
- random support / random32
- PrototypeMargin, optional if cheap

Every method must be rerun. Old issue27b/27d collapse results are exploration and cannot be copied into the reset benchmark.
