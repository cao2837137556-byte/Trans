# Clean Independent Split Blocked

No formal clean independent split was constructed in issue27j.

Blocking reasons:
- Raw pcap and TSV timestamp assets exist, and row-level mapping is recoverable by extraction order.
- However, the current paper matrices do not have a persisted sidecar row manifest with packet hash / packet_order / timestamp / capture_id.
- The only obvious unused future attack window is bin 9, which has too few packet rows for a stable formal validation object.
- The current OOD final object is not a new independent OOD environment.
- A purged split should rebuild/reset Kitsune state around split boundaries before it is used as formal evidence.
