# CKBL frontend observability audit

- Verdict: `TRUNCATED_LOCAL_NO_SIGNAL`
- Formal complete protocol: `False`
- Interpretation: `engineered_upper_bound_has_signal_but_compact_process_adapter_is_insufficient`
- Selected rows: `8344`; sources: `7`; attack families: `3`
- Runtime seconds: `206.756`
- stream-consumer/hydraulic-system/cooler-motor model use: `0`
- Raw label column read by frontend: `false`
- Identity fields are split/audit metadata only and are absent from feature matrices.

## Aggregate metrics

| protocol | bundle | folds | macro_auroc | worst_fold_auroc | macro_average_precision | macro_score_margin | threshold_evaluable_folds | macro_attack_recall | worst_attack_family_recall | macro_benign_fpr |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| unseen_attack_family_origin | C1_207_upper_bound | 3 | 0.836669 | 0.576674 | 0.679594 | 0.539968 | 0 | NA | NA | NA |
| unseen_attack_family_origin | CompactProcess69 | 3 | 0.627905 | 0.576951 | 0.211314 | 0.0855011 | 0 | NA | NA | NA |
| unseen_attack_family_origin | CompactProcess69_history_permuted | 3 | 0.627905 | 0.576951 | 0.211314 | 0.0855011 | 0 | NA | NA | NA |
| unseen_attack_family_origin | Current20 | 3 | 0.597564 | 0.52 | 0.213515 | 0.0854396 | 0 | NA | NA | NA |
| unseen_attack_family_origin | TGN9_exact | 3 | 0.596191 | 0.52 | 0.0610971 | 0.012374 | 0 | NA | NA | NA |
| unseen_source_pair | C1_207_upper_bound | 10 | 0.773697 | 0.571816 | 0.542908 | 0.408009 | 0 | NA | NA | NA |
| unseen_source_pair | CompactProcess69 | 10 | 0.624416 | 0.611024 | 0.208929 | 0.0644073 | 0 | NA | NA | NA |
| unseen_source_pair | CompactProcess69_history_permuted | 10 | 0.624416 | 0.611024 | 0.208929 | 0.0644073 | 0 | NA | NA | NA |
| unseen_source_pair | Current20 | 10 | 0.568634 | 0.470897 | 0.163929 | 0.0596729 | 0 | NA | NA | NA |
| unseen_source_pair | TGN9_exact | 10 | 0.567801 | 0.475405 | 0.127784 | 0.0127027 | 0 | NA | NA | NA |

## Claim boundary

This is a fit-only representation gate, not formal report-canary performance and not final IDS evidence.
