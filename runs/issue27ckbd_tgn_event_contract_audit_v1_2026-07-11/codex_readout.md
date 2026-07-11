# issue27ckbd_tgn_event_contract_audit_v1_2026-07-11

Status: **PASS**

This is a data-contract audit only; it has no classifier, threshold, or performance claim.

```json
{
  "issue": "issue27ckbd_tgn_event_contract_audit_v1_2026-07-11",
  "status": "PASS",
  "pyg_version": "2.8.0",
  "torch_version": "2.8.0+cpu",
  "raw_message_names": [
    "log_packet_length",
    "is_tcp",
    "is_udp",
    "is_icmp",
    "destination_port_bucket",
    "tcp_syn",
    "tcp_ack",
    "tcp_rst",
    "tcp_fin"
  ],
  "node_identity_policy": "dynamic source-local anonymous allocation; node id never enters raw_msg",
  "memory_policy": "reset per raw source; target read before TGNMemory.update_state",
  "max_recorded_index": 5000,
  "checks": {
    "label_mutation_invariant": true,
    "future_event_mutation_invariant": true,
    "past_event_changes_representation": true,
    "source_reset_invariant": true,
    "held_family_exclusion": true,
    "actual_sources_replayed": true,
    "raw_label_column_absent_from_projection": true
  }
}
```
