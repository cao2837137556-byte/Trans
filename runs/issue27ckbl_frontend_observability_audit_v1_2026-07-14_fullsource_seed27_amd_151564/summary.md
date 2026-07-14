# CKBL frontend observability audit

- Verdict: `OBSERVABILITY_NO_GO`
- Formal complete protocol: `True`
- Interpretation: `engineered_upper_bound_has_signal_but_compact_process_adapter_is_insufficient`
- Selected rows: `8671`; sources: `8`; attack families: `10`
- Runtime seconds: `688.601`
- stream-consumer/hydraulic-system/cooler-motor model use: `0`
- Raw label column read by frontend: `false`
- Identity fields are split/audit metadata only and are absent from feature matrices.

## Aggregate metrics

| protocol | bundle | folds | macro_auroc | worst_fold_auroc | macro_average_precision | macro_score_margin | threshold_evaluable_folds | macro_attack_recall | worst_attack_family_recall | macro_benign_fpr |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| unseen_attack_family_origin | C1_207_upper_bound | 10 | 0.917572 | 0.709495 | 0.715596 | 0.401462 | 4 | 1 | 1 | 1 |
| unseen_attack_family_origin | CompactProcess69 | 10 | 0.88946 | 0.677649 | 0.680657 | 0.437739 | 4 | 1 | 1 | 0.298631 |
| unseen_attack_family_origin | CompactProcess69_history_permuted | 10 | 0.898865 | 0.787927 | 0.725281 | 0.485 | 4 | 1 | 1 | 0.758448 |
| unseen_attack_family_origin | Current20 | 10 | 0.778249 | 0.478698 | 0.542086 | 0.331834 | 4 | 1 | 1 | 0.960905 |
| unseen_attack_family_origin | TGN9_exact | 10 | 0.794143 | 0.456805 | 0.526424 | 0.42544 | 4 | 1 | 1 | 0.796688 |
| unseen_source_pair | C1_207_upper_bound | 15 | 0.9927 | 0.960465 | 0.986217 | 0.86172 | 15 | 1 | 1 | 0.485778 |
| unseen_source_pair | CompactProcess69 | 15 | 0.997771 | 0.976612 | 0.992447 | 0.935883 | 15 | 0.996899 | 0.555556 | 0.330969 |
| unseen_source_pair | CompactProcess69_history_permuted | 15 | 0.997876 | 0.976899 | 0.99359 | 0.94456 | 15 | 1 | 1 | 0.30661 |
| unseen_source_pair | Current20 | 15 | 0.988025 | 0.94329 | 0.965187 | 0.810894 | 15 | 1 | 1 | 0.979952 |
| unseen_source_pair | TGN9_exact | 15 | 0.997588 | 0.982362 | 0.968767 | 0.876955 | 15 | 1 | 1 | 0.494001 |

## Claim boundary

This is a fit-only representation gate, not formal report-canary performance and not final IDS evidence.
