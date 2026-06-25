# issue27ckg basic capability diagnostic

## Scope

This is not a deployable repair. It asks whether the current feature/evidence space contains enough information to separate hard benign OOD from attack when the head is made stronger or given more development labels. Sealed final roles are never used for training or threshold selection.

## Main summary

| regime | feature set | model | ID | OOD-val | support | same-file | future | ood_stress | ood group max | sealed attack | sealed OOD | sealed OOD group max |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| label_rich_upper | evidence | histgb_stronger | 0.0037 | 0.0064 | 0.9855 | 0.9815 | 0.9845 | 0.0068 | 0.0068 | 0.9068 | 0.0126 | 0.0160 |
| label_rich_upper | raw115 | histgb_stronger | 0.0036 | 0.0099 | 1.0000 | 1.0000 | 1.0000 | 0.0024 | 0.0024 | 0.9567 | 0.7480 | 0.7753 |
| label_rich_upper | raw_plus_temporal | histgb_stronger | 0.0011 | 0.0101 | 1.0000 | 1.0000 | 0.9999 | 0.0035 | 0.0035 | 0.9997 | 0.0648 | 0.0917 |
| label_rich_upper | raw_plus_temporal | mlp_small | 0.0003 | 0.0101 | 1.0000 | 0.9997 | 0.9897 | 0.0016 | 0.0016 | 0.9998 | 0.0029 | 0.0034 |
| label_rich_upper | temporal | histgb_stronger | 0.0002 | 0.0048 | 1.0000 | 1.0000 | 0.9998 | 0.0100 | 0.0100 | 1.0000 | 0.0835 | 0.1257 |
| support_all_benign | evidence | histgb_shallow | 0.0001 | 0.0042 | 1.0000 | 0.9546 | 0.7730 | 0.0099 | 0.0099 | 0.9087 | 0.0091 | 0.0120 |
| support_all_benign | raw115 | histgb_shallow | 0.0003 | 0.0100 | 1.0000 | 0.9940 | 0.8685 | 0.0066 | 0.0066 | 0.9431 | 0.0327 | 0.0406 |
| support_all_benign | raw_plus_evidence | histgb_stronger | 0.0000 | 0.0048 | 1.0000 | 0.9696 | 0.7979 | 0.0099 | 0.0099 | 0.9345 | 0.0202 | 0.0261 |
| support_only | evidence | histgb_shallow | 0.0000 | 0.0001 | 0.8261 | 0.9019 | 0.4472 | 0.0007 | 0.0007 | 0.6408 | 0.0023 | 0.0026 |
| support_only | raw115 | histgb_shallow | 0.0000 | 0.0098 | 0.7681 | 0.8699 | 0.5957 | 0.0000 | 0.0000 | 0.5885 | 0.0001 | 0.0001 |
| support_only | raw_plus_evidence | histgb_stronger | 0.0000 | 0.0087 | 0.8551 | 0.8866 | 0.5204 | 0.0000 | 0.0000 | 0.6479 | 0.0000 | 0.0000 |

## Threshold-free separability

| regime | feature set | model | comparison | AUC | AP |
|---|---|---|---|---:|---:|
| support_only | raw115 | histgb_shallow | support_vs_ood_stress | 1.0000 | 0.9776 |
| support_only | raw115 | histgb_shallow | same_file_vs_ood_stress | 1.0000 | 0.9999 |
| support_only | raw115 | histgb_shallow | future_vs_ood_stress | 0.9999 | 1.0000 |
| support_only | raw115 | histgb_shallow | sealed_attack_vs_sealed_ood | 0.9992 | 0.9991 |
| support_only | evidence | histgb_shallow | support_vs_ood_stress | 0.9993 | 0.7744 |
| support_only | evidence | histgb_shallow | same_file_vs_ood_stress | 0.9995 | 0.9993 |
| support_only | evidence | histgb_shallow | future_vs_ood_stress | 0.9986 | 0.9987 |
| support_only | evidence | histgb_shallow | sealed_attack_vs_sealed_ood | 0.9977 | 0.9966 |
| support_only | raw_plus_evidence | histgb_stronger | support_vs_ood_stress | 1.0000 | 0.9909 |
| support_only | raw_plus_evidence | histgb_stronger | same_file_vs_ood_stress | 1.0000 | 1.0000 |
| support_only | raw_plus_evidence | histgb_stronger | future_vs_ood_stress | 0.9999 | 1.0000 |
| support_only | raw_plus_evidence | histgb_stronger | sealed_attack_vs_sealed_ood | 0.9997 | 0.9997 |
| support_all_benign | raw115 | histgb_shallow | support_vs_ood_stress | 0.9999 | 0.9677 |
| support_all_benign | raw115 | histgb_shallow | same_file_vs_ood_stress | 0.9997 | 0.9997 |
| support_all_benign | raw115 | histgb_shallow | future_vs_ood_stress | 0.9978 | 0.9984 |
| support_all_benign | raw115 | histgb_shallow | sealed_attack_vs_sealed_ood | 0.9867 | 0.9885 |
| support_all_benign | evidence | histgb_shallow | support_vs_ood_stress | 0.9978 | 0.6213 |
| support_all_benign | evidence | histgb_shallow | same_file_vs_ood_stress | 0.9901 | 0.9901 |
| support_all_benign | evidence | histgb_shallow | future_vs_ood_stress | 0.9445 | 0.9666 |
| support_all_benign | evidence | histgb_shallow | sealed_attack_vs_sealed_ood | 0.9751 | 0.9775 |
| support_all_benign | raw_plus_evidence | histgb_stronger | support_vs_ood_stress | 0.9999 | 0.9771 |
| support_all_benign | raw_plus_evidence | histgb_stronger | same_file_vs_ood_stress | 0.9982 | 0.9980 |
| support_all_benign | raw_plus_evidence | histgb_stronger | future_vs_ood_stress | 0.9423 | 0.9673 |
| support_all_benign | raw_plus_evidence | histgb_stronger | sealed_attack_vs_sealed_ood | 0.9370 | 0.9656 |
| label_rich_upper | raw115 | histgb_stronger | support_vs_ood_stress | 1.0000 | 0.9984 |
| label_rich_upper | raw115 | histgb_stronger | same_file_vs_ood_stress | 1.0000 | 1.0000 |
| label_rich_upper | raw115 | histgb_stronger | future_vs_ood_stress | 1.0000 | 1.0000 |
| label_rich_upper | raw115 | histgb_stronger | sealed_attack_vs_sealed_ood | 0.9632 | 0.9769 |
| label_rich_upper | evidence | histgb_stronger | support_vs_ood_stress | 0.9996 | 0.8771 |
| label_rich_upper | evidence | histgb_stronger | same_file_vs_ood_stress | 0.9997 | 0.9996 |
| label_rich_upper | evidence | histgb_stronger | future_vs_ood_stress | 0.9995 | 0.9997 |
| label_rich_upper | evidence | histgb_stronger | sealed_attack_vs_sealed_ood | 0.9938 | 0.9927 |
| label_rich_upper | temporal | histgb_stronger | support_vs_ood_stress | 1.0000 | 0.9759 |
| label_rich_upper | temporal | histgb_stronger | same_file_vs_ood_stress | 1.0000 | 1.0000 |
| label_rich_upper | temporal | histgb_stronger | future_vs_ood_stress | 1.0000 | 1.0000 |
| label_rich_upper | temporal | histgb_stronger | sealed_attack_vs_sealed_ood | 0.9976 | 0.9974 |
| label_rich_upper | raw_plus_temporal | histgb_stronger | support_vs_ood_stress | 1.0000 | 0.9953 |
| label_rich_upper | raw_plus_temporal | histgb_stronger | same_file_vs_ood_stress | 1.0000 | 1.0000 |
| label_rich_upper | raw_plus_temporal | histgb_stronger | future_vs_ood_stress | 1.0000 | 1.0000 |
| label_rich_upper | raw_plus_temporal | histgb_stronger | sealed_attack_vs_sealed_ood | 0.9998 | 0.9998 |
| label_rich_upper | raw_plus_temporal | mlp_small | support_vs_ood_stress | 1.0000 | 0.9774 |
| label_rich_upper | raw_plus_temporal | mlp_small | same_file_vs_ood_stress | 0.9999 | 0.9999 |
| label_rich_upper | raw_plus_temporal | mlp_small | future_vs_ood_stress | 0.9968 | 0.9986 |
| label_rich_upper | raw_plus_temporal | mlp_small | sealed_attack_vs_sealed_ood | 0.9999 | 0.9999 |

## Codex readout

This diagnostic changes the interpretation of the failure.

The current evidence space is not hopeless:

- `support_all_benign + raw115 + histgb_shallow` already gives ID `0.0003`, OOD-val `0.0100`, hard-OOD `0.0066`, support `1.0000`, same-file `0.9940`, future `0.8685`, sealed attack `0.9431`, sealed OOD `0.0327`.
- `support_all_benign + evidence + histgb_shallow` is more OOD-safe on sealed OOD (`0.0091`) but weaker on future attack (`0.7730`) and sealed attack (`0.9087`).
- `label_rich_upper + raw_plus_temporal + mlp_small` is near an upper-bound pass: ID `0.0003`, OOD-val `0.0101`, hard-OOD `0.0016`, sealed attack `0.9998`, sealed OOD `0.0029`.

Therefore the failure is not simply "Kitsune115D contains no separability". A better statement is:

> The current issue27ckc/ckf scoring architecture does not learn the available separability. When the problem is reframed as a direct attack-vs-ID/OOD/hard-OOD discriminative head with benign-safe thresholding, the same 115D/evidence space shows much stronger basic capability.

This does not mean the problem is solved:

- `support_all_benign` still has a future-query gap (`0.77-0.87`) and is only a seed42 diagnostic.
- `label_rich_upper` uses many dev attack labels, so it is an upper bound, not a deployable few-shot protocol.
- Raw-only upper-bound heads can still overfit sealed OOD (`raw115 + histgb_stronger` sealed OOD `0.7480`), so stronger models must be group-robust and OOD-safe, not just more expressive.

Next technical implication:

> Stop tuning the old risk/veto controller. Build the next head as a direct multi-class or multi-head discriminative detector trained with support attacks plus ID/OOD/hard-OOD negatives, then add conflict/unknown output and worst-group validation.

## Interpretation

- `support_only` tests the narrow binary question: support attacks versus hard OOD. It is not a complete detector.
- `support_all_benign` is closer to a few-shot detector: support attacks versus ID/OOD/hard-OOD negatives.
- `label_rich_upper` is an upper-bound diagnostic. If this also fails under source-disjoint hard OOD and sealed transfer, Kitsune115D/current evidence is likely insufficient.
- A scientifically useful next model must not only reduce average OOD false alarms; it must control worst-group OOD while retaining support-covered and sealed attacks.

## Training audit

| regime | feature set | model | role | phase | label | rows |
|---|---|---|---|---|---:|---:|
| support_only | raw115 | histgb_shallow | support_train | all | 1 | 385 |
| support_only | raw115 | histgb_shallow | ood_stress | fit | 0 | 1540 |
| support_only | evidence | histgb_shallow | support_train | all | 1 | 385 |
| support_only | evidence | histgb_shallow | ood_stress | fit | 0 | 1540 |
| support_only | raw_plus_evidence | histgb_stronger | support_train | all | 1 | 385 |
| support_only | raw_plus_evidence | histgb_stronger | ood_stress | fit | 0 | 1540 |
| support_all_benign | raw115 | histgb_shallow | support_train | all | 1 | 385 |
| support_all_benign | raw115 | histgb_shallow | id_calib | fit | 0 | 513 |
| support_all_benign | raw115 | histgb_shallow | ood_val | fit | 0 | 513 |
| support_all_benign | raw115 | histgb_shallow | ood_stress | fit | 0 | 513 |
| support_all_benign | evidence | histgb_shallow | support_train | all | 1 | 385 |
| support_all_benign | evidence | histgb_shallow | id_calib | fit | 0 | 513 |
| support_all_benign | evidence | histgb_shallow | ood_val | fit | 0 | 513 |
| support_all_benign | evidence | histgb_shallow | ood_stress | fit | 0 | 513 |
| support_all_benign | raw_plus_evidence | histgb_stronger | support_train | all | 1 | 385 |
| support_all_benign | raw_plus_evidence | histgb_stronger | id_calib | fit | 0 | 513 |
| support_all_benign | raw_plus_evidence | histgb_stronger | ood_val | fit | 0 | 513 |
| support_all_benign | raw_plus_evidence | histgb_stronger | ood_stress | fit | 0 | 513 |
| label_rich_upper | raw115 | histgb_stronger | support_train | fit | 1 | 385 |
| label_rich_upper | raw115 | histgb_stronger | support_val | fit | 1 | 58 |
| label_rich_upper | raw115 | histgb_stronger | same_file_query | fit | 1 | 20000 |
| label_rich_upper | raw115 | histgb_stronger | future_query | fit | 1 | 20000 |
| label_rich_upper | raw115 | histgb_stronger | id_calib | fit | 0 | 20000 |
| label_rich_upper | raw115 | histgb_stronger | ood_val | fit | 0 | 11295 |
| label_rich_upper | raw115 | histgb_stronger | ood_stress | fit | 0 | 20000 |
| label_rich_upper | evidence | histgb_stronger | support_train | fit | 1 | 385 |
| label_rich_upper | evidence | histgb_stronger | support_val | fit | 1 | 58 |
| label_rich_upper | evidence | histgb_stronger | same_file_query | fit | 1 | 20000 |
| label_rich_upper | evidence | histgb_stronger | future_query | fit | 1 | 20000 |
| label_rich_upper | evidence | histgb_stronger | id_calib | fit | 0 | 20000 |
| label_rich_upper | evidence | histgb_stronger | ood_val | fit | 0 | 11295 |
| label_rich_upper | evidence | histgb_stronger | ood_stress | fit | 0 | 20000 |
| label_rich_upper | temporal | histgb_stronger | support_train | fit | 1 | 385 |
| label_rich_upper | temporal | histgb_stronger | support_val | fit | 1 | 58 |
| label_rich_upper | temporal | histgb_stronger | same_file_query | fit | 1 | 20000 |
| label_rich_upper | temporal | histgb_stronger | future_query | fit | 1 | 20000 |
| label_rich_upper | temporal | histgb_stronger | id_calib | fit | 0 | 20000 |
| label_rich_upper | temporal | histgb_stronger | ood_val | fit | 0 | 11295 |
| label_rich_upper | temporal | histgb_stronger | ood_stress | fit | 0 | 20000 |
| label_rich_upper | raw_plus_temporal | histgb_stronger | support_train | fit | 1 | 385 |
| label_rich_upper | raw_plus_temporal | histgb_stronger | support_val | fit | 1 | 58 |
| label_rich_upper | raw_plus_temporal | histgb_stronger | same_file_query | fit | 1 | 20000 |
| label_rich_upper | raw_plus_temporal | histgb_stronger | future_query | fit | 1 | 20000 |
| label_rich_upper | raw_plus_temporal | histgb_stronger | id_calib | fit | 0 | 20000 |
| label_rich_upper | raw_plus_temporal | histgb_stronger | ood_val | fit | 0 | 11295 |
| label_rich_upper | raw_plus_temporal | histgb_stronger | ood_stress | fit | 0 | 20000 |
| label_rich_upper | raw_plus_temporal | mlp_small | support_train | fit | 1 | 385 |
| label_rich_upper | raw_plus_temporal | mlp_small | support_val | fit | 1 | 58 |
| label_rich_upper | raw_plus_temporal | mlp_small | same_file_query | fit | 1 | 20000 |
| label_rich_upper | raw_plus_temporal | mlp_small | future_query | fit | 1 | 20000 |
| label_rich_upper | raw_plus_temporal | mlp_small | id_calib | fit | 0 | 20000 |
| label_rich_upper | raw_plus_temporal | mlp_small | ood_val | fit | 0 | 11295 |
| label_rich_upper | raw_plus_temporal | mlp_small | ood_stress | fit | 0 | 20000 |

Runtime seconds: `192.3`.
