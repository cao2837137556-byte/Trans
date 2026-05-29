# issue27u Next Action

Recommended issue:

`issue27u_gotham_metadata_intake_and_data_gate_precheck_2026-05-28`

Scope:

- no model training.
- no large raw download without user confirmation.
- download or inspect only small metadata/index/README/license files if available.
- verify Gotham has enough benign phases/environments, attack labels, timestamp/order, source/capture metadata, and report-only final eval potential.
- produce a Data Gate pass/fail decision before raw PCAP download.

Fallback:

If Gotham metadata is blocked, run ToN-IoT metadata intake. Local IoT-23 can be used only as an auxiliary Data Gate rehearsal.
