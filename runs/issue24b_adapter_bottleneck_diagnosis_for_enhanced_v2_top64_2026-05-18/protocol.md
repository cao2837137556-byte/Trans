# Protocol

This run is diagnosis only. It reconstructs row-level scores for fixed existing methods on locked bins using representative seed 42:

- V1 original100 LR from issue23 configuration.
- V2_top64 LR from issue23/24 configuration.
- A1 weighted LR and A2 SVM using issue24 selected configs.

No new adapter candidate is introduced, no topK/support/representation is changed, and final eval is used only to analyze already-reported errors.
