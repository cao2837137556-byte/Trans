# Issue12 Transformer Hidden Recovery and Fixed-Guard Probe Protocol

- Phase A recovers Transformer outputLayer mean-pooled hidden representation from an existing checkpoint only.
- Phase A hard gate: row coverage, hidden shape, and scalar score consistency against issue07b score cache.
- Phase B executes only three methods: hidden-only plain LR, hidden-only fixed guard LR, and original100+hidden fixed guard LR.
- Fixed guard: OOD benign sample weight = 2; no OOD-weight or C search.
- Threshold: guarded_id_calib_and_ood_val_target1pct.
- Final OOD eval and attack eval are not used for training, scaler fitting, threshold selection, or configuration selection.
- This run is a representation probe, not full GDA.
