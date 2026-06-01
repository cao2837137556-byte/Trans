# Gotham Kitsune115 Packet / Label Alignment Key Spec

- Primary smoke alignment key: `pcap_member + packet_index + packet_timestamp_epoch`.
- Label source for this smoke: raw scenario path (`raw/benign` or `raw/malicious/<attack_type>`) cross-checked against processed CSV labels in the PCAP timestamp window.
- CSV cross-check fields: `frame.time` and `label`.
- Full materialization must expand this into a complete row-level alignment audit before model execution.
- If timestamp-window labels disagree with raw scenario labels, the full 115D path must block on label alignment.
