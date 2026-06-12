# OOD Stress Contract

## Roles

- `ood_benign_val`: development-side OOD calibration from benign devices/files disjoint from ID train where possible.
- `ood_benign_stress`: harder development-side benign drift, still selectable for controller development.
- `sealed_final_ood`: report-only benign drift replay after all parameters are frozen.

## Assigned Files

`ood_benign_val`: `processed/iotsim-hydraulic-system-1.csv`, `processed/iotsim-hydraulic-system-10.csv`, `processed/iotsim-hydraulic-system-11.csv`, `processed/iotsim-hydraulic-system-12.csv`, `processed/iotsim-hydraulic-system-13.csv`, `processed/iotsim-hydraulic-system-14.csv`, `processed/iotsim-hydraulic-system-15.csv`, `processed/iotsim-hydraulic-system-2.csv`, `processed/iotsim-building-monitor-2.csv`, `processed/iotsim-building-monitor-3.csv`

`ood_benign_stress`: `processed/iotsim-hydraulic-system-3.csv`, `processed/iotsim-hydraulic-system-4.csv`, `processed/iotsim-hydraulic-system-5.csv`, `processed/iotsim-hydraulic-system-6.csv`, `processed/iotsim-hydraulic-system-7.csv`, `processed/iotsim-hydraulic-system-8.csv`, `processed/iotsim-hydraulic-system-9.csv`, `processed/iotsim-stream-consumer-1.csv`, `processed/iotsim-stream-consumer-2.csv`, `processed/iotsim-domotic-monitor-2.csv`, `processed/iotsim-domotic-monitor-3.csv`, `processed/iotsim-building-monitor-4.csv`, `processed/iotsim-building-monitor-5.csv`

`sealed_final_ood`: `processed/iotsim-ip-camera-museum-2.csv`, `processed/iotsim-ip-camera-street-2.csv`

## Rules

- OOD stress can guide OOD-risk and controller selection.
- Sealed final OOD cannot guide any selection.
- If final OOD is used to explain a failure, the resulting fix must be validated on a new sealed role or clearly labelled as diagnostic-only.
