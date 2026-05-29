# Full Mirai Paired Raw Missing Confirmed

User confirmation plus issue27s local inventory establish that the current local full Mirai download consists of feature CSV + label sidecar, not the paired raw pcap/input stream for `Mirai_dataset.csv`.

Consequences:

- Do not spend further large local-search time trying to rescue full Mirai raw provenance.
- Do not use full Mirai anonymous_clean115 as the main low-OOD-alert benchmark.
- Full Mirai remains diagnostic only unless paired raw/extractor-compatible provenance is later acquired.
- The project remains in Data validity gate; model execution remains blocked.
