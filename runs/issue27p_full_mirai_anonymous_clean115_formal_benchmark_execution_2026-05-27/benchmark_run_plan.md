# Benchmark Run Plan

- Run fixed seeds 42-46 on the issue27o row-order split contract.
- Use only anonymous clean115 features; col0 remains excluded.
- Train/support/threshold choices use train/cal/validation side only.
- Final OOD and attack eval are report-only.
- OC-SVM uses scalable `SGDOneClassSVM`; exact RBF OC-SVM is deferred to Slurm if needed.
