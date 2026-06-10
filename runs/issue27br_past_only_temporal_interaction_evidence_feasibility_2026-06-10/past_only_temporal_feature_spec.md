# Past-Only Temporal Feature Spec

- Scope: diagnostic/controller feasibility only; no 115D frontend changes.
- Ordering key: `packet_timestamp_epoch`, then `recorded_index`, then materialized row position.
- Grouping: role-level and source-group-level (`csv_member`/`pcap_member`) past windows.
- Windows: 8, 32, 128 previous rows.
- Every rolling feature uses `shift(1)` before the rolling computation, so the current row and future rows are never included.
- Available interaction evidence is limited to source/file/state metadata; no IP/port/flow graph fields are present in the current sidecar.
- Report-only roles are replayed only after dev-side temporal thresholds are selected.
