# Full Mirai Raw Provenance Report

Verdict: `full_mirai_raw_assets_missing_for_claim_safe_reconstruction`.

Findings:

- Full Mirai main asset exists as `Mirai_dataset.csv` plus `mirai_labels.csv`.
- No raw pcap paired with the full 764,137-row Mirai feature matrix was found.
- Local raw pcaps exist (`3` files), but they are IoT23/public_data style assets and are not paired with the full Mirai CSV.
- `mirai3.csv` and `mirai3_ts.csv` provide a smaller timestamped 100k path, but that does not recover timestamp/capture provenance for the full 764k matrix.
- Extractor scripts exist (`24` script hits across worktrees / KitNET roots), including netStat/AfterImage/FeatureExtractor, but scripts alone do not make current clean115 traceable to raw packets.

Technical judgment:

The current full Mirai object cannot be rescued by paperwork alone. A claim-safe reconstruction requires the raw input stream or extractor-compatible packet/flow fields that generated the 764,137 rows, plus a row-level sidecar with packet id, timestamp, label, source/capture/session, split role, and feature hash.
