# Metric Training Contract

- Input frontend: fixed Gotham Kitsune115 115D.
- Legal training/calibration roles: ID fit/calib, OOD train/val, OOD stress train/val, medium support train/val/pseudo, active-heavy support train/val/pseudo.
- Forbidden for selection: final OOD, medium attack eval report-only, dev-heavy query report-only, attack eval report-only.
- Metric candidate: NCA 115D -> 16D, bounded sample caps, prototype shells in embedding space.
- Controller selection: dev-only roles; report-only replay occurs after rule freeze.
