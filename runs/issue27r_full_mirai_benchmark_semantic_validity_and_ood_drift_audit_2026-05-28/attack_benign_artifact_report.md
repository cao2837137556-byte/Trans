# Attack/Benign Artifact Report

Verdict: `attack_benign_artifact_risk`.

Key diagnostic values:

- best attack-vs-benign diagnostic AUC: `0.999972`
- rank-normalized attack-vs-benign diagnostic AUC: `0.991249`
- drop-top10-separator-features attack-vs-benign diagnostic AUC: `0.407798`
- attack label vs row-order correlation: `0.633630`

Interpretation:

The attack/benign separation is strong, but the dataset identity is semantically risky: every benign row precedes every attack row, and no timestamp/capture/source metadata is available to show whether the separation is attack behavior rather than source/capture/row-segment construction. The anonymous feature space also prevents mapping the strongest columns to known Kitsune statistics. This blocks main-paper attack semantics until raw provenance, interleaved construction, capture/session metadata, or a second validated dataset is available.
