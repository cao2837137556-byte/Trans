# E4 Second-Environment / Cross-Capture Feasibility Inventory

## 1. 任务边界

本轮只做 feasibility inventory，不做实验、不训练模型、不重算指标、不修改论文主稿、不 push、不建 issue。所有写入仅限：

`D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline\runs\e4_second_environment_feasibility_inventory_2026-05-08\`

执行时采用的额外约束：

- E4 不能变成 BoT-IoT / TON-IoT 的救线。
- E4 只有在能复现当前 frozen few-shot protocol 时才值得开。
- 候选必须能清楚构造 ID benign、OOD benign、high-purity attack，以及与当前主线一致的 train / validation / calibration / final-eval 角色。
- final OOD eval 与 attack eval 必须不参与 threshold selection。
- support positives 必须与 attack validation / final attack evaluation 分离。
- 如果候选只是已有主线资产或旧失败尝试，只能写成已完成证据、limitation 或 archive，不能伪装成新 external validation。

## 2. 找到的候选资产

### 2.1 当前 IoT23 primary cross-capture split

路径：

- `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline\runs\frontend_f2_crosscapture_stage1_2026-04-13\`
- `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline\runs\frontend_f2_attack_source_2026-04-13\`
- `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline\runs\original100_fewshot_official_control_2026-04-22\`

找到的资产：

- `id_source_100.npy/csv`
- `ood_benign_source_100.npy/csv`
- `attack_source_100.npy/csv`
- `id_source_structured.npz`
- `ood_benign_source_structured.npz`
- `attack_source_structured.npz`
- dA score cache: `da_full_id_scores.npy`, `da_ood_scores.npy`, `da_attack_scores.npy`

判断：

- 协议兼容性：full compatible。
- E4 价值：低，因为它已经是当前主线的 primary evaluation split，不是独立 second-environment。
- 决策：不作为新 E4。

### 2.2 frontend-f2 v7.4 paired hard-holdout

路径：

- `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-frontend-f2\runs\frontend_f2_v7_4_paired_holdout_fairness_2026-04-22\`
- `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-frontend-f2\runs\branch_handoffs\frontend_f2\paper_facing_hard_holdout_cases.md`
- `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-frontend-f2\runs\branch_handoffs\frontend_f2\source_rich_original100_boundary_table.csv`

找到的资产：

- paired holdout specs
- original100 / source_rich paired results
- same budgets, seeds, threshold rules
- final OOD eval 不参与 threshold selection

判断：

- 协议兼容性：full compatible for cross-holdout。
- E4 价值：中等，但它已经完成并已进入 source_rich hard-holdout robustness + auditability 资产。
- 决策：不重开 E4；继续作为已完成 hard-holdout evidence 使用。

### 2.3 BoT-IoT 5% local data

路径：

- `D:\study\paper\anomaly_detection\paper04\worktrees\data\5%\`
- `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline\runs\second_environment_botiot_feasibility_2026-04-20\`
- `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline\runs\second_environment_botiot_smoke_2026-04-20\`
- `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline\runs\second_environment_botiot_split_gate_2026-04-20\`

找到的资产：

- BoT-IoT CSVs
- smoke split: `id_benign_train=370`, `ood_benign_test=107`, `attack_test=100000`
- split gate verdict: `blocked_naive_budget5000_not_supported`

判断：

- 协议兼容性：not compatible。
- 主要 blocker：benign support 过少，无法支撑当前正式 ID/OOD split 与 guarded low-OOD-alarm protocol。
- 决策：不建议正式进入 E4；保留为 external-validity boundary / negative feasibility note。

### 2.4 TON-IoT Train_Test_Network_dataset

路径：

- `D:\study\paper\anomaly_detection\paper04\worktrees\data\Train_Test_Network_dataset\train_test_network.csv`
- `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline\runs\second_environment_toniot_smoke_2026-04-20\`
- `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline\runs\second_environment_toniot_threshold_sensitivity_2026-04-21\`
- `D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline\runs\second_environment_toniot_coupling_probe_2026-04-21\`

找到的资产：

- TON-IoT-like CSV
- numeric feature count: 16
- smoke split: `id_benign=30000`, `ood_benign=20000`, `attack=100000`
- old dA / FT / transformer coupling score caches

判断：

- 协议兼容性：partially compatible but weak/risky。
- 主要 blocker：它不是当前 original100/source_rich 表示，不具备当前 E3/E3-b support provenance 口径，旧 coupling probe 只能作为失败/诊断资产。
- 决策：不建议立即进入正式 E4；如未来考虑，必须先做 protocol-only precheck，而不是直接训练或扩跑。

### 2.5 其他外部数据

数据根目录：

`D:\study\paper\anomaly_detection\paper04\worktrees\data\`

本轮未找到可直接进入当前 protocol 的 clean standalone UNSW-NB15 / CIC-IDS / IoT-23 external package。BoT 文件名中包含 UNSW_2018_IoT_Botnet，但本轮按 BoT-IoT 资产处理，不视为 UNSW-NB15 formal candidate。

## 3. 协议兼容性结论

当前没有找到一个“新的、独立的、可立即按 frozen few-shot protocol 运行”的 second-environment 候选。

最干净的同协议资产是 v7.4 paired hard-holdout，但它已经完成，且科学角色是 source_rich hard-holdout robustness + auditability，不是独立 second-environment validation。

BoT-IoT 和 TON-IoT 不建议作为下一步正式 E4：

- BoT-IoT：formal split gate 已经被 benign 数量卡死。
- TON-IoT：有数据和旧缓存，但表示、split provenance、threshold provenance 与当前主线不完全对齐。

## 4. 是否建议正式进入 E4

结论：

`do_not_start_new_e4_now`

理由：

1. 新 external dataset 候选没有达到 same-protocol bar。
2. 直接跑 BoT-IoT / TON-IoT 会把 E4 变成旧 second-environment 救线，风险高于收益。
3. 已完成的 v7.4 cross-holdout 资产可以继续作为 bounded hard-holdout evidence，但不需要重跑。
4. 若需要进一步补强 A 区证据，下一步更适合转向 E5 label budget / label purity sensitivity。

## 5. 如果仍要开 E4，最小前置条件

在任何正式 E4 run 之前，必须先完成一个只读/协议型 precheck：

- 数据语义确认；
- ID benign / OOD benign / high-purity attack 角色确认；
- split sizes 确认；
- support positives 与 attack val/eval disjoint 证明；
- threshold provenance 证明；
- representation 是否等价于 current original100/source_rich 的说明；
- 决定是否能复用 E2/E3/E3-b packaging。

如果这些前置条件无法满足，则不应训练模型或生成结果。

## 6. 对论文主线的影响

本轮 inventory 不改变当前论文主线。当前主线仍为：

strict low-OOD-alarm operating region -> dA reference baseline 的 operating-point detection collapse -> few-shot target alignment -> original100 作为主控制表示 -> source_rich 作为 hard-holdout robustness 与 auditability 补充证据。

second-environment validation 仍应写作 external-validity boundary / future work，而不是当前正向主证据。

## 7. 输出文件

- `candidate_environment_table.csv`
- `protocol_compatibility_matrix.csv`
- `engineering_cost_table.csv`
- `scientific_value_table.csv`
- `risk_register.csv`
- `recommended_e4_plan.md`
- `summary.md`
