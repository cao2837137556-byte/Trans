# New Data Acquisition Contract

Use this contract only if the local archive has no eligible fresh pair.

## Preferred Route

Run a new reproducible Gotham capture rather than selecting more rows from an already used capture.

Minimum target scope:

- target attacks: Mirai GRE Flooding, Mirai UDP Flooding, and Mirai TCP Flooding;
- at least two independent attack sessions per target label;
- exact packet-level labels with raw PCAP and timestamp-aligned CSV metadata;
- matched benign traffic from the same declared device/environment era;
- at least two benign sessions and a target of at least 100,000 benign packets for stable low-FPR estimation;
- at least 10,000 exact-labelled attack packets per target label, subject to session-level reporting rather than treating packets as independent;
- new run IDs, seeds, timestamps, and hashes recorded before feature extraction.

## Freeze Rule

Before opening any region result, freeze:

- B0 and the single selected repair candidate;
- Kitsune115 state strategy;
- S3 transform, prototype rule, shell rule, and activation gates;
- attack and benign source manifests;
- packet/session bootstrap reporting plan;
- a one-pass decision rule with no return to support selection.

A second public environment is an alternative only if raw PCAP, exact labels, timestamps, and compatible online feature extraction are available. It must not be treated as interchangeable with Gotham without a separate semantic audit.
