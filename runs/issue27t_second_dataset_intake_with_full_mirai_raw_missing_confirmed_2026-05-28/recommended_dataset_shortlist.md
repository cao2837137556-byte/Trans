# Recommended Dataset Shortlist

## 1. Gotham Dataset 2025

Why it fits:

- raw PCAP plus CSV/metadata/labels are reported.
- IoT smart-home style setting with multiple devices and gateway context.
- Better chance to build ID benign / OOD benign / attack support / attack eval without row-order fiction.
- Metadata should allow row-order/source/capture artifact audit.

Largest risks:

- 23.8GB download needs user confirmation.
- Need to inspect metadata before trusting benign phases or attack labels.
- Need to define feature extraction path after intake.

## 2. ToN-IoT / TON_IoT network

Why it fits:

- IoT/IIoT network dataset family with labels and network traffic records.
- Local flow CSV already exists, so path familiarity is high.
- Raw/log/security event package may support timestamp-aware split if acquired.

Largest risks:

- Local CSV alone is not enough for Data Gate.
- Access/download may require manual steps.
- Must verify benign multi-phase/capture/source metadata before model execution.

## Auxiliary: local IoT-23

Useful for a quick Data Gate rehearsal because raw pcap and labeled logs exist locally. It should not yet be treated as the main benchmark because benign OOD depth looks weak.
