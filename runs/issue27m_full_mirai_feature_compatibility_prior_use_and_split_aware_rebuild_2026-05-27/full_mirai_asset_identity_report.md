# Full Mirai Asset Identity Report

The full Mirai asset exists as a large feature CSV plus label sidecar, not as a packet-level feature-reconstruction-ready object in the current audit.

Key finding: `Mirai_dataset.csv` has 116 columns and an index-like first column. This matches the historical `dirty116` diagnosis. Dropping col0 gives a 115D track, but the current LOW-GUARD++ candidate is frozen on the original frontend `original100`, not on clean115/restored115.

The timestamped `mirai3.csv` asset is 115D with `mirai3_ts.csv`, making it useful for future timestamp-aware split proposals. It still lacks feature names/order mapping against current `original100`.

Recursive local search found separate IoT23 raw pcaps under `public_data/raw`, but did not find a full Mirai/Botnet pcap paired with `Mirai_dataset.csv`. Therefore the current full Mirai object should be treated as a downstream feature matrix, not as a packet-level reconstruction asset.
