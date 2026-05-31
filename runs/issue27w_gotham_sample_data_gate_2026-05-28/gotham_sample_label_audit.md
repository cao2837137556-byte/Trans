# Gotham Sample Label Audit

- CSV label column present: `True`.
- attack labels observed: `C&C Communication, File Download, Ingress Tool Transfer, Mirai UDP Flooding, Reporting, TCP Scan, Telnet Brute Force, Unknown`.
- benign-only files are consistent with processed device files whose sampled labels are all `Benign`.
- mixed attack files contain a benign prefix plus attack labels, which is useful for semantic audit but creates row-order/time artifact risk.
- no separate `attack_type` column was observed; attack type is encoded in the `label` value.
