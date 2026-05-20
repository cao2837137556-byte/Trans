# Protocol

This run fixes selected_source_rich_top64 and kcenter32 support. It compares adapter families only.

- Official target: 1% OOD alarm.
- Hyperparameter selection: support-validation split from the selected 32 support samples plus ID calibration and OOD validation.
- Support split for selection: 24 support-train / 8 support-validation.
- Final report: models are retrained on all 32 support samples with the selected adapter config.
- Final OOD eval and final attack eval are report-only.
- No topK search, no representation change, no routing, no promotion, no V3, no dA/Transformer training.
