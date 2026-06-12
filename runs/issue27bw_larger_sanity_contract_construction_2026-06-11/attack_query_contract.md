# Attack Query Contract

## Roles

- `attack_support_candidate_pool`: development-side labelled attack support.
- `dev_future_attack_query`: development-side future/query attack used for mechanism design.
- `sealed_final_attack`: report-only replay after config freeze.

## Assigned Files

`attack_support_candidate_pool`: `processed/iotsim-air-quality-1.csv`, `processed/iotsim-city-power-1.csv`

`dev_future_attack_query`: `processed/iotsim-ip-camera-museum-1.csv`, `processed/iotsim-building-monitor-1.csv`, `processed/iotsim-domotic-monitor-1.csv`, `processed/iotsim-combined-cycle-1.csv`, `processed/iotsim-combined-cycle-10.csv`

`sealed_final_attack`: `processed/iotsim-ip-camera-street-1.csv`

## Known Limitation

Gotham has only 8 mixed attack CSV files. The sealed final attack role is therefore useful for larger sanity, but it is not enough by itself for a formal A-tier final benchmark. Formal claims need either a new holdout policy at row/phase/source level, additional untouched Gotham raw materialization, or a second dataset.

## Phase/Onset Rule

Attack support, support_val, dev query, and final attack must be phase-balanced during materialization. Use early/mid/late/tail buckets where enough rows exist; if a bucket is missing, write the failure reason instead of silently dropping it.
