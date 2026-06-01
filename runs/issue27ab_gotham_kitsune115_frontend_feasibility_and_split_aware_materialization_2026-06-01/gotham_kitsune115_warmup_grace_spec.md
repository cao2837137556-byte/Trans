# Gotham Kitsune115 Warmup / Grace Spec

- Smoke warmup packets per state/role: `100`.
- Warmup packets update frontend state and are logged in sidecar.
- Warmup rows are marked `warmup_only=true` and `model_ready_hint=false`.
- No model training is performed in this issue.
- Full materialization must preregister whether warmup rows are excluded or retained before any model work.
