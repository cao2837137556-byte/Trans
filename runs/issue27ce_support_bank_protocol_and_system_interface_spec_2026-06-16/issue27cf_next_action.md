# issue27cf Next Action

Recommended next issue:

```text
issue27cf_instantiate_exact_label_support_bank_from_issue27cd_outputs
```

## Preconditions

- issue27cd exact-label materialization must be validated or repaired.
- Missing chunks and partial timestamp-alignment chunks must be understood.
- Only exact-label, timestamp-aligned, PCAP-paired rows can be used.
- Unused candidates remain inert unless a later explicit issue assigns a legal role.

## Scope

issue27cf should instantiate support-bank indices from issue27cd outputs without training a detector.

It should produce:

- exact eligible candidate manifest;
- taxonomy and semantic attack groups;
- initial region assignment;
- support budget proposal;
- support train/val split;
- support-bank sidecar;
- role access audit;
- provenance hashes;
- invariant test report.

## Forbidden

- No model training.
- No detection metrics.
- No final/report-only access.
- No threshold/controller tuning.
- No candidate reuse beyond support-bank instantiation.

