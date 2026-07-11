# issue27ckav_held_ood_provenance_preflight_v1_2026-07-10

## Scope

- Audit-only: no model is trained and no held labels are used for model choice.
- A source may be semantically benign yet ineligible for a raw-PCAP frontend if its pairing is not exact.

## Counts

- held sources: 26
- target rows: 34622
- benign-provenance pass: 21
- source-label provenance pass: 21
- raw-PCAP frontend eligible: 20

## Decision

Only `raw_pcap_frontend_eligible` sources may enter the upcoming Zeek/interaction episode extractor.
Rejected sources remain processed-CSV-only until their PCAP pairing is repaired with independent evidence.
