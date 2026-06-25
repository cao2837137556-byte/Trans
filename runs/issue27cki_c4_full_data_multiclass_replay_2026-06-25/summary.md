# issue27cki C4 full-data multiclass replay

## Scope

This run keeps the issue27ckh C4 structure fixed and changes only data caps.
C4 is a four-class raw115 HistGradientBoosting head: ID benign / ordinary OOD / hard OOD / attack.
Sealed final attack and sealed final OOD are report-only and are not used for fit, threshold, calibration, or model selection.

## Data caps

- requested benign/OOD train caps: `1600, 5000, 20000, full`
- evaluation cap: `full legal role rows`
- attack positives remain the frozen support_train view: `385` rows

## Role inventory

| role | phase | rows |
|---|---|---:|
| id_calib | fit | 28103 |
| id_calib | select | 51497 |
| id_calib | all | 79600 |
| ood_val | fit | 11295 |
| ood_val | select | 12205 |
| ood_val | all | 23500 |
| ood_stress | fit | 149950 |
| ood_stress | select | 79950 |
| ood_stress | all | 229900 |
| support_train | fit | 385 |
| support_train | all | 385 |
| support_val | fit | 58 |
| support_val | select | 69 |
| support_val | all | 127 |
| same_file_query | fit | 57930 |
| same_file_query | select | 67749 |
| same_file_query | all | 125679 |
| future_query | fit | 149496 |
| future_query | select | 228649 |
| future_query | all | 378145 |
| sealed_final_ood | report_only | 154900 |
| sealed_final_ood | all | 154900 |
| sealed_final_attack | report_only | 110104 |
| sealed_final_attack | all | 110104 |

## Candidate summary

| candidate | train cap | ID hard | OOD-val hard | hard-OOD hard | support hard | same-file hard | future hard | sealed attack hard | sealed OOD hard | sealed OOD group max | sealed attack review | sealed OOD review |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| C4_fewshot_multiclass_raw115_cap1600 | 1600 | 0.0000 | 0.0005 | 0.0001 | 1.0000 | 0.9995 | 0.9900 | 0.9967 | 0.0071 | 0.0095 | 0.0019 | 0.0501 |
| C4_fewshot_multiclass_raw115_cap20000 | 20000 | 0.0000 | 0.0000 | 0.0003 | 0.9855 | 0.9983 | 0.9926 | 0.9922 | 0.0033 | 0.0037 | 0.0062 | 0.0370 |
| C4_fewshot_multiclass_raw115_cap5000 | 5000 | 0.0000 | 0.0000 | 0.0003 | 0.9710 | 0.9981 | 0.9422 | 0.9932 | 0.0062 | 0.0084 | 0.0050 | 0.1194 |
| C4_fewshot_multiclass_raw115_capfull | full | 0.0000 | 0.0000 | 0.0002 | 0.9710 | 0.9876 | 0.9224 | 0.9921 | 0.0071 | 0.0100 | 0.0062 | 0.0599 |

## Review burden by role

| candidate | role | rows | raw alarm | review | review count | hard alarm | hard count | threshold |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| C4_fewshot_multiclass_raw115_cap1600 | future_query | 228649 | 0.9991 | 0.0091 | 2079 | 0.9900 | 226368 | 0.0231 |
| C4_fewshot_multiclass_raw115_cap1600 | id_calib | 51497 | 0.0006 | 0.0006 | 32 | 0.0000 | 0 | 0.0231 |
| C4_fewshot_multiclass_raw115_cap1600 | ood_stress | 79950 | 0.0037 | 0.0036 | 288 | 0.0001 | 10 | 0.0231 |
| C4_fewshot_multiclass_raw115_cap1600 | ood_val | 12205 | 0.0094 | 0.0089 | 109 | 0.0005 | 6 | 0.0231 |
| C4_fewshot_multiclass_raw115_cap1600 | same_file_query | 67749 | 1.0000 | 0.0005 | 36 | 0.9995 | 67713 | 0.0231 |
| C4_fewshot_multiclass_raw115_cap1600 | sealed_final_attack | 110104 | 0.9986 | 0.0019 | 205 | 0.9967 | 109742 | 0.0231 |
| C4_fewshot_multiclass_raw115_cap1600 | sealed_final_ood | 154900 | 0.0573 | 0.0501 | 7766 | 0.0071 | 1105 | 0.0231 |
| C4_fewshot_multiclass_raw115_cap1600 | support_val | 69 | 1.0000 | 0.0000 | 0 | 1.0000 | 69 | 0.0231 |
| C4_fewshot_multiclass_raw115_cap20000 | future_query | 228649 | 0.9988 | 0.0061 | 1406 | 0.9926 | 226967 | 0.0108 |
| C4_fewshot_multiclass_raw115_cap20000 | id_calib | 51497 | 0.0011 | 0.0011 | 59 | 0.0000 | 0 | 0.0108 |
| C4_fewshot_multiclass_raw115_cap20000 | ood_stress | 79950 | 0.0057 | 0.0054 | 432 | 0.0003 | 21 | 0.0108 |
| C4_fewshot_multiclass_raw115_cap20000 | ood_val | 12205 | 0.0092 | 0.0092 | 112 | 0.0000 | 0 | 0.0108 |
| C4_fewshot_multiclass_raw115_cap20000 | same_file_query | 67749 | 1.0000 | 0.0017 | 118 | 0.9983 | 67631 | 0.0108 |
| C4_fewshot_multiclass_raw115_cap20000 | sealed_final_attack | 110104 | 0.9984 | 0.0062 | 681 | 0.9922 | 109243 | 0.0108 |
| C4_fewshot_multiclass_raw115_cap20000 | sealed_final_ood | 154900 | 0.0403 | 0.0370 | 5736 | 0.0033 | 508 | 0.0108 |
| C4_fewshot_multiclass_raw115_cap20000 | support_val | 69 | 1.0000 | 0.0145 | 1 | 0.9855 | 68 | 0.0108 |
| C4_fewshot_multiclass_raw115_cap5000 | future_query | 228649 | 0.9993 | 0.0571 | 13057 | 0.9422 | 215428 | 0.0121 |
| C4_fewshot_multiclass_raw115_cap5000 | id_calib | 51497 | 0.0046 | 0.0046 | 239 | 0.0000 | 0 | 0.0121 |
| C4_fewshot_multiclass_raw115_cap5000 | ood_stress | 79950 | 0.0086 | 0.0083 | 666 | 0.0003 | 22 | 0.0121 |
| C4_fewshot_multiclass_raw115_cap5000 | ood_val | 12205 | 0.0093 | 0.0093 | 114 | 0.0000 | 0 | 0.0121 |
| C4_fewshot_multiclass_raw115_cap5000 | same_file_query | 67749 | 1.0000 | 0.0019 | 129 | 0.9981 | 67620 | 0.0121 |
| C4_fewshot_multiclass_raw115_cap5000 | sealed_final_attack | 110104 | 0.9982 | 0.0050 | 551 | 0.9932 | 109359 | 0.0121 |
| C4_fewshot_multiclass_raw115_cap5000 | sealed_final_ood | 154900 | 0.1256 | 0.1194 | 18493 | 0.0062 | 960 | 0.0121 |
| C4_fewshot_multiclass_raw115_cap5000 | support_val | 69 | 1.0000 | 0.0290 | 2 | 0.9710 | 67 | 0.0121 |
| C4_fewshot_multiclass_raw115_capfull | future_query | 228649 | 0.9993 | 0.0768 | 17568 | 0.9224 | 210913 | 0.0119 |
| C4_fewshot_multiclass_raw115_capfull | id_calib | 51497 | 0.0009 | 0.0009 | 48 | 0.0000 | 0 | 0.0119 |
| C4_fewshot_multiclass_raw115_capfull | ood_stress | 79950 | 0.0054 | 0.0053 | 420 | 0.0002 | 14 | 0.0119 |
| C4_fewshot_multiclass_raw115_capfull | ood_val | 12205 | 0.0101 | 0.0101 | 123 | 0.0000 | 0 | 0.0119 |
| C4_fewshot_multiclass_raw115_capfull | same_file_query | 67749 | 1.0000 | 0.0124 | 840 | 0.9876 | 66906 | 0.0119 |
| C4_fewshot_multiclass_raw115_capfull | sealed_final_attack | 110104 | 0.9982 | 0.0062 | 682 | 0.9921 | 109229 | 0.0119 |
| C4_fewshot_multiclass_raw115_capfull | sealed_final_ood | 154900 | 0.0670 | 0.0599 | 9278 | 0.0071 | 1099 | 0.0119 |
| C4_fewshot_multiclass_raw115_capfull | support_val | 69 | 1.0000 | 0.0290 | 2 | 0.9710 | 67 | 0.0119 |

## Threshold-free separability

| candidate | comparison | positive rows | negative rows | AUC | AP |
|---|---|---:|---:|---:|---:|
| C4_fewshot_multiclass_raw115_cap1600 | support_vs_hard_ood | 69 | 79950 | 1.0000 | 0.9936 |
| C4_fewshot_multiclass_raw115_cap1600 | same_file_vs_hard_ood | 67749 | 79950 | 1.0000 | 1.0000 |
| C4_fewshot_multiclass_raw115_cap1600 | future_vs_hard_ood | 228649 | 79950 | 1.0000 | 1.0000 |
| C4_fewshot_multiclass_raw115_cap1600 | sealed_attack_vs_sealed_ood | 110104 | 154900 | 0.9990 | 0.9990 |
| C4_fewshot_multiclass_raw115_cap5000 | support_vs_hard_ood | 69 | 79950 | 1.0000 | 0.9880 |
| C4_fewshot_multiclass_raw115_cap5000 | same_file_vs_hard_ood | 67749 | 79950 | 1.0000 | 1.0000 |
| C4_fewshot_multiclass_raw115_cap5000 | future_vs_hard_ood | 228649 | 79950 | 0.9999 | 1.0000 |
| C4_fewshot_multiclass_raw115_cap5000 | sealed_attack_vs_sealed_ood | 110104 | 154900 | 0.9985 | 0.9986 |
| C4_fewshot_multiclass_raw115_cap20000 | support_vs_hard_ood | 69 | 79950 | 1.0000 | 0.9869 |
| C4_fewshot_multiclass_raw115_cap20000 | same_file_vs_hard_ood | 67749 | 79950 | 1.0000 | 1.0000 |
| C4_fewshot_multiclass_raw115_cap20000 | future_vs_hard_ood | 228649 | 79950 | 0.9999 | 1.0000 |
| C4_fewshot_multiclass_raw115_cap20000 | sealed_attack_vs_sealed_ood | 110104 | 154900 | 0.9990 | 0.9990 |
| C4_fewshot_multiclass_raw115_capfull | support_vs_hard_ood | 69 | 79950 | 1.0000 | 0.9895 |
| C4_fewshot_multiclass_raw115_capfull | same_file_vs_hard_ood | 67749 | 79950 | 1.0000 | 1.0000 |
| C4_fewshot_multiclass_raw115_capfull | future_vs_hard_ood | 228649 | 79950 | 0.9999 | 1.0000 |
| C4_fewshot_multiclass_raw115_capfull | sealed_attack_vs_sealed_ood | 110104 | 154900 | 0.9988 | 0.9989 |

## Training audit

| candidate | role | phase | label | rows |
|---|---|---|---:|---:|
| C4_fewshot_multiclass_raw115_cap1600 | support_train | fit | 3 | 385 |
| C4_fewshot_multiclass_raw115_cap1600 | id_calib | fit | 0 | 1600 |
| C4_fewshot_multiclass_raw115_cap1600 | ood_val | fit | 1 | 1600 |
| C4_fewshot_multiclass_raw115_cap1600 | ood_stress | fit | 2 | 1600 |
| C4_fewshot_multiclass_raw115_cap5000 | support_train | fit | 3 | 385 |
| C4_fewshot_multiclass_raw115_cap5000 | id_calib | fit | 0 | 5000 |
| C4_fewshot_multiclass_raw115_cap5000 | ood_val | fit | 1 | 5000 |
| C4_fewshot_multiclass_raw115_cap5000 | ood_stress | fit | 2 | 5000 |
| C4_fewshot_multiclass_raw115_cap20000 | support_train | fit | 3 | 385 |
| C4_fewshot_multiclass_raw115_cap20000 | id_calib | fit | 0 | 20000 |
| C4_fewshot_multiclass_raw115_cap20000 | ood_val | fit | 1 | 11295 |
| C4_fewshot_multiclass_raw115_cap20000 | ood_stress | fit | 2 | 20000 |
| C4_fewshot_multiclass_raw115_capfull | support_train | fit | 3 | 385 |
| C4_fewshot_multiclass_raw115_capfull | id_calib | fit | 0 | 28103 |
| C4_fewshot_multiclass_raw115_capfull | ood_val | fit | 1 | 11295 |
| C4_fewshot_multiclass_raw115_capfull | ood_stress | fit | 2 | 149950 |

## Interpretation guardrail

- This is still a seed42 detector-capability replay, not a final benchmark.
- If full-fit lowers sealed OOD review without hurting sealed attack, C4 is not merely a 1600-row artifact.
- If full-fit hurts attack or increases review, the next step is not more blind data; it is invariant/causal training and stronger heads.
- Sealed final roles are used only for report-only replay.

Runtime seconds: `217.9`.
