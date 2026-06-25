# issue27ckk group-balanced / worst-group C4

## Scope

Repair experiment. Fixed detector family: raw115 C4 four-class HistGB.
Only legal fit roles are used for training. No query/select/final role is used for fit.

## Candidate matrix

| variant | future hard mean/min | future review | sealed attack hard mean/min | sealed OOD hard mean/max | sealed OOD review mean/max | ood_stress hard max |
|---|---:|---:|---:|---:|---:|---:|
| baseline_cap20000 | 0.9717/0.9016 | 0.0274 | 0.9944/0.9922 | 0.0026/0.0034 | 0.0733/0.1047 | 0.0003 |
| device_time_balanced | 0.9419/0.8983 | 0.0572 | 0.9776/0.9761 | 0.0035/0.0040 | 0.0663/0.1130 | 0.0004 |
| fit_tail_source_balanced | 0.9955/0.9911 | 0.0026 | 0.9715/0.8676 | 0.0083/0.0118 | 0.0083/0.0141 | 0.0033 |
| source_balanced | 0.9502/0.9188 | 0.0489 | 0.9946/0.9919 | 0.0029/0.0037 | 0.1099/0.1669 | 0.0003 |
| source_balanced_group_weighted | 0.9969/0.9966 | 0.0013 | 0.9965/0.9928 | 0.0181/0.0385 | 0.0110/0.0254 | 0.0047 |

## Leave-device/family stress snapshot

| variant | held field | held value | role | rows | hard | review | raw |
|---|---|---|---|---:|---:|---:|---:|
| baseline_cap20000 | device_family | iotsim-ip-camera-street | sealed_final_ood | 99950 | 0.0037 | 0.0468 | 0.0504 |
| baseline_cap20000 | device_family | iotsim-ip-camera-museum | sealed_final_ood | 54950 | 0.0026 | 0.0193 | 0.0219 |
| baseline_cap20000 | device_family | iotsim-stream-consumer | ood_stress | 79950 | 0.9977 | 0.0009 | 0.9986 |
| baseline_cap20000 | device_family | iotsim-hydraulic-system | ood_val | 12205 | 0.5083 | 0.1926 | 0.7009 |
| source_balanced_group_weighted | device_family | iotsim-ip-camera-street | sealed_final_ood | 99950 | 0.0097 | 0.0115 | 0.0212 |
| source_balanced_group_weighted | device_family | iotsim-ip-camera-museum | sealed_final_ood | 54950 | 0.0022 | 0.0062 | 0.0084 |
| source_balanced_group_weighted | device_family | iotsim-stream-consumer | ood_stress | 79950 | 0.9978 | 0.0007 | 0.9985 |
| source_balanced_group_weighted | device_family | iotsim-hydraulic-system | ood_val | 12205 | 0.7745 | 0.0017 | 0.7762 |
| fit_tail_source_balanced | device_family | iotsim-ip-camera-street | sealed_final_ood | 99950 | 0.0114 | 0.0002 | 0.0116 |
| fit_tail_source_balanced | device_family | iotsim-ip-camera-museum | sealed_final_ood | 54950 | 0.0034 | 0.0002 | 0.0035 |
| fit_tail_source_balanced | device_family | iotsim-stream-consumer | ood_stress | 79950 | 0.9978 | 0.0007 | 0.9985 |
| fit_tail_source_balanced | device_family | iotsim-hydraulic-system | ood_val | 12205 | 0.7744 | 0.0046 | 0.7790 |

## Top seed42 group burdens

| variant | role | group field | value | rows | hard | review | hard count | review count |
|---|---|---|---|---:|---:|---:|---:|---:|
| source_balanced_group_weighted | future_query | support_seen | seen | 140099 | 0.9977 | 0.0006 | 139774 | 89 |
| source_balanced | future_query | support_seen | seen | 140099 | 0.9974 | 0.0013 | 139739 | 188 |
| device_time_balanced | future_query | support_seen | seen | 140099 | 0.9963 | 0.0023 | 139583 | 324 |
| baseline_cap20000 | future_query | support_seen | seen | 140099 | 0.9960 | 0.0028 | 139540 | 386 |
| fit_tail_source_balanced | future_query | support_seen | seen | 140099 | 0.9955 | 0.0001 | 139472 | 17 |
| source_balanced_group_weighted | future_query | device_family | combined-cycle | 112729 | 0.9958 | 0.0014 | 112253 | 160 |
| fit_tail_source_balanced | future_query | device_family | combined-cycle | 112729 | 0.9934 | 0.0004 | 111983 | 49 |
| baseline_cap20000 | future_query | device_family | combined-cycle | 112729 | 0.9889 | 0.0091 | 111481 | 1024 |
| baseline_cap20000 | sealed_final_attack | device_family | ip-camera-street | 110104 | 0.9922 | 0.0062 | 109243 | 681 |
| baseline_cap20000 | sealed_final_attack | source_group | processed/iotsim-ip-camera-street-1.csv | 110104 | 0.9922 | 0.0062 | 109243 | 681 |
| source_balanced | sealed_final_attack | device_family | ip-camera-street | 110104 | 0.9919 | 0.0065 | 109212 | 713 |
| source_balanced | sealed_final_attack | source_group | processed/iotsim-ip-camera-street-1.csv | 110104 | 0.9919 | 0.0065 | 109212 | 713 |
| source_balanced_group_weighted | sealed_final_attack | source_group | processed/iotsim-ip-camera-street-1.csv | 110104 | 0.9928 | 0.0016 | 109308 | 176 |
| source_balanced_group_weighted | sealed_final_attack | device_family | ip-camera-street | 110104 | 0.9928 | 0.0016 | 109308 | 176 |
| device_time_balanced | sealed_final_attack | device_family | ip-camera-street | 110104 | 0.9761 | 0.0224 | 107470 | 2462 |
| device_time_balanced | sealed_final_attack | source_group | processed/iotsim-ip-camera-street-1.csv | 110104 | 0.9761 | 0.0224 | 107470 | 2462 |
| source_balanced | future_query | device_family | combined-cycle | 112729 | 0.9444 | 0.0535 | 106456 | 6036 |
| device_time_balanced | future_query | device_family | combined-cycle | 112729 | 0.8861 | 0.1116 | 99889 | 12584 |
| fit_tail_source_balanced | sealed_final_attack | source_group | processed/iotsim-ip-camera-street-1.csv | 110104 | 0.8676 | 0.0985 | 95522 | 10842 |
| fit_tail_source_balanced | sealed_final_attack | device_family | ip-camera-street | 110104 | 0.8676 | 0.0985 | 95522 | 10842 |
| fit_tail_source_balanced | future_query | device_family | domotic-monitor | 91812 | 0.9985 | 0.0003 | 91677 | 29 |
| fit_tail_source_balanced | future_query | source_group | processed/iotsim-domotic-monitor-1.csv | 91812 | 0.9985 | 0.0003 | 91677 | 29 |
| source_balanced_group_weighted | future_query | source_group | processed/iotsim-domotic-monitor-1.csv | 91812 | 0.9976 | 0.0015 | 91594 | 136 |
| source_balanced_group_weighted | future_query | device_family | domotic-monitor | 91812 | 0.9976 | 0.0015 | 91594 | 136 |
| baseline_cap20000 | future_query | device_family | domotic-monitor | 91812 | 0.9953 | 0.0041 | 91380 | 380 |

## Interpretation guardrail

- A good repair must reduce review without hiding uncertainty by converting review into false hard attack alarms.
- Leave-device-family collapse can only be partially addressed inside the current Gotham fit contract; if a family is absent from legal fit, training-view repair cannot create information ex nihilo.
- If group-balanced views help average review but leave-device-family still collapses, issue27ckl should add invariant/causal representation and smarter heads.

Runtime seconds: `408.3`.

Runtime note: this artifact combines the earlier full main-matrix run (`978.6s`) with the later leaveout-only supplement (`408.3s`) after fixing the BOM/group-key bug.
