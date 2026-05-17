# Selected Representation Protocol

source_rich feature selection is performed per holdout/seed/topK using only selected attack supports, ID calibration, and OOD validation. The score combines attack-support versus OOD-validation standardized effect, attack-support versus ID-calibration effect, and a small OOD-tail safety term. A greedy redundancy pruning step skips features with absolute correlation >= 0.95 against already selected features.

Reported topK settings are top16 and top32. No attack eval or final OOD eval is used for feature selection.
