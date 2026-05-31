# Gotham Sample Temporal And Source Report

- `frame.time` parsed successfully in all selected CSVs.
- Selected CSVs were mostly internally time-ordered at the scanned level.
- Device/capture can be inferred from processed filenames and matching raw PCAP names.
- Protocol can be inferred from `frame.protocols`; names provide only partial hints.
- The sample supports device/protocol split design, but does not yet justify a temporal-deployment claim.
