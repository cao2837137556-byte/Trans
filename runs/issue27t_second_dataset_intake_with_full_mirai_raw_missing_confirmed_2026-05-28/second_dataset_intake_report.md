# Second Dataset Intake Report

The candidate pool was evaluated only for Data Gate suitability. No large files were downloaded and no models were trained.

Best candidate shape:

1. Gotham Dataset 2025: strongest first target because it advertises raw PCAP, CSV, metadata, labels, device/gateway context, and realistic IoT home traffic. Its main risk is size/manual download plus the need to verify benign phase/capture splits after metadata intake.
2. ToN-IoT / TON_IoT network: strong IoT/IIoT candidate with network data and local partial CSV, but the local CSV alone lacks obvious timestamp/capture columns; raw/log/security-event package must be obtained or verified.

Useful auxiliary:

- Local IoT-23 public_data can rehearse the semantic gate cheaply because raw pcap and labeled logs exist locally, but benign OOD is likely too limited for the main benchmark.

Rejected or lower-priority as immediate main benchmark:

- full Mirai anonymous_clean115: diagnostic only.
- local BoT-IoT 5% subset: too few benign rows in prior inventory.
- UNSW-IoTraffic: good benign OOD auxiliary but lacks attack labels as standalone benchmark.
