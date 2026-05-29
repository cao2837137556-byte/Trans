# issue27u Decision

primary_verdict = `gotham_ready_for_full_download_with_user_confirmation`

Gotham metadata is strong enough to justify the next intake step. It has raw PCAP, processed CSV, metadata, timestamps, device-level structure, and deterministic attack labels according to the official Zenodo record.

However, Zenodo exposes the dataset as a single `23.825GB decimal / 22.189GiB` zip. Because there is no small per-file download path visible from the API, issue27v must require user confirmation before downloading. After download, the next gate must inspect file structure, label schema, benign phases, and source/capture coupling before any feature/interface or model execution.
