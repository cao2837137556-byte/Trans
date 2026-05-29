# Gotham Metadata Report

Official record: `https://zenodo.org/records/14502760`

Title: `A Device-Level IoT Network Traffic Dataset with Distributed Capture and Non-IID Characteristics`

DOI: `10.5281/zenodo.14502760`

Publication date: `2025-02-05`

License/access: `cc-by-4.0`, access `open`.

Metadata intake result:

- raw PCAP availability: `True`.
- labelled/processed CSV availability: `True`.
- metadata availability: `True`.
- timestamp information: `True`.
- device/source/capture information: `True`.
- attack labels: `True`.
- total downloadable data: `23.825GB decimal / 22.189GiB`.
- file granularity: `single_large_zip_no_per_file_granularity`.

Interpretation:

Gotham is a strong candidate for the low-OOD-alert benchmark because the record describes raw PCAP, processed CSV, metadata with timestamps/attacker IPs/attack types, device-level traces from 78 heterogeneous IoT devices, and deterministic labels from orchestration logs.

The metadata is strong enough to justify a user-confirmed full download or a user-confirmed method for inspecting the zip listing. It is not enough to start model experiments. The next gate must inspect the actual files and labels after download.
