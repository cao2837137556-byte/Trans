# Protocol

This run locks the enhanced V2_top64 configuration found in issue22/22b.

- Candidate: selected_source_rich_top64 + kcenter32 + fixed OOD guard LR.
- Official OOD target: 1%.
- Locked objects: holdout_bin_5, holdout_bin_6, holdout_bin_7, holdout_bin_8.
- The locked objects are unused leave-one-bin eval objects whose eval bins were not used to choose top64 in issue22.
- Support source: local attack train pool per locked holdout.
- Scaler fit: ID benign train + OOD benign train + selected attack supports.
- Feature selection: selected source_rich top64 is recomputed using training/support and ID/OOD calibration/validation only.
- Threshold: ID calibration + OOD validation only.
- Final OOD eval and attack eval are report-only.
- No routing, no promotion, no V3, no margin-hardneg main method, no topK search.
