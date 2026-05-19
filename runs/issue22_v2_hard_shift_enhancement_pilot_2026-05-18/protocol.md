# Protocol

- Fixed official OOD target: 1%.
- Diagnostic OOD targets: 0.5%, 0.8%, 1.2%, 1.5%, 2.0%.
- Support samples are selected only from the local attack train pool.
- TopK feature selection uses attack supports, ID calibration, and OOD validation only.
- Thresholds use ID calibration and OOD validation only.
- Final OOD eval and attack eval are report-only.
- No dA/Transformer training, V3, routing, promotion, MLP, prototype, or continual learning is performed.
