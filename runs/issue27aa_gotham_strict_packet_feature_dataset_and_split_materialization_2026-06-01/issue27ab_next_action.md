# issue27ab Next Action

Recommended next issue: `issue27ab_gotham_strict_packet_interface_smoke_no_model_selection_2026-06-01`.

Scope:
- Load the strict feature artifact and sidecar.
- Run only interface smoke / schema loading / split API checks.
- No benchmark training, no model comparison, no hyperparameter tuning.
- Confirm downstream code can consume `gotham_strict_packet_header_v1` without source-like fields.
- Explicitly check sparse-feature handling: `ip.tos` is fully missing and `tcp.pdu.size` is almost always missing in v1.
- If v1 is too sparse, open a flow/PCAP-derived feature construction issue instead of relaxing the source-clean policy.
