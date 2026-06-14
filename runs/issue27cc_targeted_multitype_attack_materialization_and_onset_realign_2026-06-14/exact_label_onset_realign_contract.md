# Exact Label / Onset Realign Contract

This contract exists because the previous 1M asset used coarse `first_attack_label` / post-onset binary materialization for attack roles.

New hard gates:

1. Attack support/query/final materialization must filter by exact processed CSV `label` per planned row range.
2. `Benign`, empty labels, and `Unknown` are forbidden for attack support selection.
3. Same-file support/query reuse is allowed only as development-side time-forward diagnostic with an embargo.
4. Same-file time-forward query is not a clean final evaluation set.
5. Sealed final attack remains report-only and cannot be used for support selection, threshold, OOD-risk training, controller tuning, or model selection.
6. The old `post_onset_binary_from_csv_first_attack` label source is no longer sufficient for attack roles.
