# Unified Temporal Attack/OOD Heads Report

- The task compares parent-stacked evidence against no-parent unified two-head variants.
- Shared evidence is allowed, but attack and OOD heads are trained separately.
- Final/report-only roles are replay-only in all variants.

- Group parent hard_pass: `True`; dev attack/OOD/report attack/final OOD = `1.0` / `0.0` / `0.9707207207207207` / `0.0006666666666666666`.
- Group unified no-parent hard_pass: `False`; dev attack/OOD/report attack/final OOD = `0.9375` / `0.025333333333333333` / `0.9831111111111112` / `0.0`.
- Time-half unified no-parent hard_pass: `False`.
