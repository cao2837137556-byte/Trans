# Gotham Data Gate Precheck Report

Gotham passes the metadata-level precheck as a promising candidate, not as a validated benchmark.

Why it is promising:

- raw PCAP and processed CSV are advertised.
- metadata includes timestamps, attacker IPs, and attack types.
- files are organized by device identifier.
- 78 heterogeneous IoT devices create a plausible basis for ID/OOD benign splits.
- deterministic labeling from orchestration logs is reported.

What remains blocked:

- actual benign phase counts per device are unknown.
- actual CSV schema is unknown.
- actual label fields and attack windows are unknown.
- decompressed file structure is unknown because Zenodo exposes a single large zip.
- no model execution is allowed until sample/file-level Data Gate passes.
