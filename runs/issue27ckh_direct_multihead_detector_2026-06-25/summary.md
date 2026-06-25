# issue27ckh direct multihead detector

## Scope

This is the first trial of the new structure. It stops tuning the old attack-scorer plus OOD-veto pipeline and instead trains direct attack-vs-ID/OOD/hard-OOD discriminative heads. Sealed final roles are report-only.

## Candidate summary

| candidate | regime | feature | architecture | ID | OOD-val | hard-OOD | hard-OOD group max | support | same-file | future | sealed attack | sealed OOD | sealed OOD group max | sealed attack review |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| C1_fewshot_binary_raw115 | fewshot_direct | raw115 | binary_attack_vs_all_benign | 0.0002 | 0.0086 | 0.0063 | 0.0063 | 1.0000 | 0.9992 | 0.9895 | 0.9768 | 0.3055 | 0.6411 | 0.0000 |
| C2_fewshot_binary_evidence | fewshot_direct | evidence | binary_attack_vs_all_benign | 0.0001 | 0.0011 | 0.0089 | 0.0089 | 0.9710 | 0.9198 | 0.7115 | 0.8710 | 0.0069 | 0.0091 | 0.0000 |
| C3_fewshot_binary_raw_plus_evidence | fewshot_direct | raw_plus_evidence | binary_attack_vs_all_benign | 0.0001 | 0.0039 | 0.0098 | 0.0098 | 1.0000 | 0.9610 | 0.7851 | 0.9323 | 0.0758 | 0.1082 | 0.0000 |
| C4_fewshot_multiclass_raw115 | fewshot_direct | raw115 | multiclass_id_ood_hardood_attack | 0.0000 | 0.0005 | 0.0001 | 0.0001 | 1.0000 | 0.9995 | 0.9901 | 0.9967 | 0.0071 | 0.0095 | 0.0019 |
| C5_fewshot_multihead_raw_plus_evidence | fewshot_direct | raw_plus_evidence | multihead_attack_hardood_conflict | 0.0001 | 0.0039 | 0.0000 | 0.0000 | 0.9565 | 0.9031 | 0.7608 | 0.7125 | 0.0015 | 0.0020 | 0.2198 |
| U1_devlabel_binary_raw_plus_temporal_mlp | dev_label_upper | raw_plus_temporal | binary_attack_vs_all_benign | 0.0002 | 0.0101 | 0.0045 | 0.0045 | 0.9855 | 0.9960 | 0.9629 | 0.9995 | 0.0026 | 0.0031 | 0.0000 |
| U2_devlabel_multihead_raw_plus_temporal | dev_label_upper | raw_plus_temporal | multihead_attack_hardood_conflict | 0.0006 | 0.0101 | 0.0023 | 0.0023 | 0.9855 | 0.9906 | 0.9837 | 0.7830 | 0.0042 | 0.0049 | 0.2170 |

## Codex readout

The new structure is materially better than the old `attack scorer + OOD veto` pipeline.

Best first candidate:

- `C4_fewshot_multiclass_raw115`
- Training data:
  - attack: 385 `support_train` rows
  - ID benign: 1600 fit rows
  - ordinary OOD: 1600 fit rows
  - hard OOD: 1600 source-disjoint fit rows
- Sealed final roles are not used for training or threshold selection.

Key result for `C4`:

- ID: `0.0000`
- OOD-val: `0.0005`
- hard-OOD select: `0.0001`
- hard-OOD group max: `0.0001`
- support-val attack: `1.0000`
- same-file query: `0.9995`
- future query: `0.9901`
- sealed final attack: `0.9967`
- sealed final OOD: `0.0071`
- sealed final OOD group max: `0.0095`

This is the first result in this sequence that looks like a real basic detector rather than a veto patch.

Important interpretation:

- `C1` direct binary raw115 still leaves sealed OOD high (`0.3055`), so "direct binary" is not enough.
- `C2` evidence-only is OOD-safe (`sealed OOD 0.0069`) but weaker on future attack (`0.7115`).
- `C4` multiclass raw115 is the strongest seed42 deploy-style candidate: separating ID / ordinary OOD / hard OOD / attack directly is better than fitting an attack scorer and repairing with OOD-risk.
- `C5` conflict multihead is safer on OOD but sends too much attack into review (`sealed attack hard 0.7125`, review 0.2198), so it is not the first candidate to scale.
- `U1` shows a stronger label-rich/MLP upper bound is also viable, but it uses dev attack labels and is not the first deployable few-shot protocol.

Next scientific step:

> Scale `C4_fewshot_multiclass_raw115` to all issue27ckc seeds/jobs, then stress it with support coverage, worst-group OOD, and sealed transfer. Do not claim success from this single seed42 diagnostic.

If full-seed `C4` remains stable, it should replace the old issue27ckc/ckf attack-scorer-veto line as the new mainline head. If it collapses across seeds/groups, then move to the upper-bound family (`raw_plus_temporal` MLP / group-robust conflict head).

## Threshold-free separability

| candidate | comparison | AUC | AP |
|---|---|---:|---:|
| C1_fewshot_binary_raw115 | support_vs_hard_ood | 1.0000 | 0.9824 |
| C1_fewshot_binary_raw115 | same_file_vs_hard_ood | 1.0000 | 1.0000 |
| C1_fewshot_binary_raw115 | future_vs_hard_ood | 0.9993 | 0.9995 |
| C1_fewshot_binary_raw115 | sealed_attack_vs_sealed_ood | 0.9780 | 0.9823 |
| C2_fewshot_binary_evidence | support_vs_hard_ood | 0.9988 | 0.7373 |
| C2_fewshot_binary_evidence | same_file_vs_hard_ood | 0.9753 | 0.9825 |
| C2_fewshot_binary_evidence | future_vs_hard_ood | 0.8626 | 0.9344 |
| C2_fewshot_binary_evidence | sealed_attack_vs_sealed_ood | 0.9688 | 0.9741 |
| C3_fewshot_binary_raw_plus_evidence | support_vs_hard_ood | 1.0000 | 0.9904 |
| C3_fewshot_binary_raw_plus_evidence | same_file_vs_hard_ood | 0.9982 | 0.9979 |
| C3_fewshot_binary_raw_plus_evidence | future_vs_hard_ood | 0.9570 | 0.9735 |
| C3_fewshot_binary_raw_plus_evidence | sealed_attack_vs_sealed_ood | 0.9328 | 0.9640 |
| C4_fewshot_multiclass_raw115 | support_vs_hard_ood | 1.0000 | 0.9936 |
| C4_fewshot_multiclass_raw115 | same_file_vs_hard_ood | 1.0000 | 1.0000 |
| C4_fewshot_multiclass_raw115 | future_vs_hard_ood | 1.0000 | 1.0000 |
| C4_fewshot_multiclass_raw115 | sealed_attack_vs_sealed_ood | 0.9990 | 0.9992 |
| C5_fewshot_multihead_raw_plus_evidence | support_vs_hard_ood | 1.0000 | 0.9904 |
| C5_fewshot_multihead_raw_plus_evidence | same_file_vs_hard_ood | 0.9982 | 0.9979 |
| C5_fewshot_multihead_raw_plus_evidence | future_vs_hard_ood | 0.9570 | 0.9735 |
| C5_fewshot_multihead_raw_plus_evidence | sealed_attack_vs_sealed_ood | 0.9328 | 0.9640 |
| U1_devlabel_binary_raw_plus_temporal_mlp | support_vs_hard_ood | 0.9994 | 0.6324 |
| U1_devlabel_binary_raw_plus_temporal_mlp | same_file_vs_hard_ood | 0.9996 | 0.9994 |
| U1_devlabel_binary_raw_plus_temporal_mlp | future_vs_hard_ood | 0.9904 | 0.9956 |
| U1_devlabel_binary_raw_plus_temporal_mlp | sealed_attack_vs_sealed_ood | 0.9997 | 0.9994 |
| U2_devlabel_multihead_raw_plus_temporal | support_vs_hard_ood | 0.9999 | 0.9700 |
| U2_devlabel_multihead_raw_plus_temporal | same_file_vs_hard_ood | 1.0000 | 1.0000 |
| U2_devlabel_multihead_raw_plus_temporal | future_vs_hard_ood | 0.9999 | 0.9999 |
| U2_devlabel_multihead_raw_plus_temporal | sealed_attack_vs_sealed_ood | 0.9999 | 0.9999 |

## Interpretation guardrails

- A good candidate must control ID/OOD/hard-OOD and sealed-final OOD while retaining support-covered and sealed attacks.
- `dev_label_upper` candidates are not deployable few-shot systems; they only show whether stronger heads and more labels can use the existing representation.
- If a multihead candidate mainly sends attacks to review, it is not a detection fix yet; it is only safer than false high-priority alarms.

## Training audit

| candidate | role | phase | label | rows |
|---|---|---|---:|---:|
| C1_fewshot_binary_raw115 | support_train | fit | 1 | 385 |
| C1_fewshot_binary_raw115 | id_calib | fit | 0 | 1600 |
| C1_fewshot_binary_raw115 | ood_val | fit | 0 | 1600 |
| C1_fewshot_binary_raw115 | ood_stress | fit | 0 | 1600 |
| C2_fewshot_binary_evidence | support_train | fit | 1 | 385 |
| C2_fewshot_binary_evidence | id_calib | fit | 0 | 1600 |
| C2_fewshot_binary_evidence | ood_val | fit | 0 | 1600 |
| C2_fewshot_binary_evidence | ood_stress | fit | 0 | 1600 |
| C3_fewshot_binary_raw_plus_evidence | support_train | fit | 1 | 385 |
| C3_fewshot_binary_raw_plus_evidence | id_calib | fit | 0 | 1600 |
| C3_fewshot_binary_raw_plus_evidence | ood_val | fit | 0 | 1600 |
| C3_fewshot_binary_raw_plus_evidence | ood_stress | fit | 0 | 1600 |
| C4_fewshot_multiclass_raw115 | support_train | fit | 3 | 385 |
| C4_fewshot_multiclass_raw115 | id_calib | fit | 0 | 1600 |
| C4_fewshot_multiclass_raw115 | ood_val | fit | 1 | 1600 |
| C4_fewshot_multiclass_raw115 | ood_stress | fit | 2 | 1600 |
| C5_fewshot_multihead_raw_plus_evidence | support_train | fit | 1 | 385 |
| C5_fewshot_multihead_raw_plus_evidence | id_calib | fit | 0 | 1600 |
| C5_fewshot_multihead_raw_plus_evidence | ood_val | fit | 0 | 1600 |
| C5_fewshot_multihead_raw_plus_evidence | ood_stress | fit | 0 | 1600 |
| C5_fewshot_multihead_raw_plus_evidence | ood_stress | fit | 1 | 1600 |
| C5_fewshot_multihead_raw_plus_evidence | support_train | fit | 0 | 385 |
| C5_fewshot_multihead_raw_plus_evidence | id_calib | fit | 0 | 1600 |
| C5_fewshot_multihead_raw_plus_evidence | ood_val | fit | 0 | 1600 |
| U1_devlabel_binary_raw_plus_temporal_mlp | support_train | fit | 1 | 385 |
| U1_devlabel_binary_raw_plus_temporal_mlp | support_val | fit | 1 | 58 |
| U1_devlabel_binary_raw_plus_temporal_mlp | same_file_query | fit | 1 | 20000 |
| U1_devlabel_binary_raw_plus_temporal_mlp | future_query | fit | 1 | 20000 |
| U1_devlabel_binary_raw_plus_temporal_mlp | id_calib | fit | 0 | 1600 |
| U1_devlabel_binary_raw_plus_temporal_mlp | ood_val | fit | 0 | 1600 |
| U1_devlabel_binary_raw_plus_temporal_mlp | ood_stress | fit | 0 | 1600 |
| U2_devlabel_multihead_raw_plus_temporal | support_train | fit | 1 | 385 |
| U2_devlabel_multihead_raw_plus_temporal | support_val | fit | 1 | 58 |
| U2_devlabel_multihead_raw_plus_temporal | same_file_query | fit | 1 | 20000 |
| U2_devlabel_multihead_raw_plus_temporal | future_query | fit | 1 | 20000 |
| U2_devlabel_multihead_raw_plus_temporal | id_calib | fit | 0 | 1600 |
| U2_devlabel_multihead_raw_plus_temporal | ood_val | fit | 0 | 1600 |
| U2_devlabel_multihead_raw_plus_temporal | ood_stress | fit | 0 | 1600 |
| U2_devlabel_multihead_raw_plus_temporal | ood_stress | fit | 1 | 1600 |
| U2_devlabel_multihead_raw_plus_temporal | support_train | fit | 0 | 385 |
| U2_devlabel_multihead_raw_plus_temporal | id_calib | fit | 0 | 1600 |
| U2_devlabel_multihead_raw_plus_temporal | ood_val | fit | 0 | 1600 |
| U2_devlabel_multihead_raw_plus_temporal | same_file_query | fit | 0 | 20000 |
| U2_devlabel_multihead_raw_plus_temporal | future_query | fit | 0 | 20000 |

Runtime seconds: `176.7`.
