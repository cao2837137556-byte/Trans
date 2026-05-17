# Provenance Report

- Support provenance: `support_id_provenance.csv`; all support rows are inherited from issue17 kcenter support and remain local attack-train-pool only.
- Feature selection provenance: `selected_feature_report.csv`; selection uses supports + ID calibration + OOD validation only.
- Margin provenance: `hard_negative_report.csv`; hard negatives come from OOD validation tail only, never final OOD eval.
- Threshold provenance: `threshold_provenance.csv`; thresholds use ID calibration + OOD validation only.
- Scaler provenance: scaler fit remains ID train + OOD train + selected attack supports only.
