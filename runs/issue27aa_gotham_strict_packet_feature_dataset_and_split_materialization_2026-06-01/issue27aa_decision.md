# issue27aa Decision

primary_verdict = gotham_strict_feature_dataset_ready_for_model_interface_smoke

Rationale:
- A full strict packet/header feature artifact and row-level sidecar were materialized outside the git worktree.
- The feature artifact excludes labels, file/source/device/path, timestamps, IP/MAC, ports, and protocol fields.
- The preregistered Gotham device-disjoint split was materialized with report-only final eval roles.
- No model training or model-result-driven split selection occurred.
