# issue27t Next Action

Recommended next issue:

`issue27t_dual_track_full_mirai_raw_provenance_search_and_second_dataset_intake_2026-05-28`

P0 tasks:

1. Search or reacquire the raw/extractor-compatible source for the full 764,137-row Mirai matrix.
2. If found, build a minimal row-level sidecar and extractor smoke on a small range.
3. In parallel, inventory second-dataset candidates against the hard semantic requirements.
4. Select one path only after the data validity gate passes.

Do not train models in issue27t. The project is still in Data validity gate, not Feature/interface or Model execution gate.

Slurm: not needed for intake; likely needed for full raw reconstruction or large second-dataset feature extraction.
