# issue27z Next Action

Recommended next task: `issue27z_gotham_pcap_csv_pairing_and_feature_source_policy_gate_2026-05-28`.

Scope:
- Strengthen PCAP/CSV pairing for the preregistered contract files using packet-count hints and safe sampled PCAP metadata reads.
- Define source identifier handling before feature/interface work: IP, MAC, ports, file identifiers, timestamp-derived fields, and protocol tokens.
- Decide whether Gotham can enter Feature / interface gate with raw PCAP extraction or processed-flow features.
- Continue to forbid model training until those gates pass.

Slurm:
- Not needed for metadata/pairing checks.
- Likely needed later for full feature extraction over all contract files.
