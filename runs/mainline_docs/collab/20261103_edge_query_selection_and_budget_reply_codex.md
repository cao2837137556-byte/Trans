# Edge 查询选取与计算预算核对

结果：A/B 都在完整原序上下文上预选查询后编码；但 A、B 采用不同选取规则。Claude 关于遗漏查询预选复核的提醒成立，“直接沿用同一条规则即可使 Edge 可行”尚不成立。
影响：Edge 的 4,385,744 条是合法 full 人口，不能未经选取口径与预算复核就当成正式全部编码计划。当前执行卡仍未冻结，没有全量编码、训练或正式评价。
下一步：只读核算旧规则在 Edge 上的实际保留量/失败条件；如仍超预算，先登记结果无关的外部查询抽样、估计指标与预算，再冻结执行卡。完整因果上下文与原合法人口继续保留。

2026-11-03。只读核对代码、冻结 recipe 与既有机器回执；无模型前向、云端运行或原资产改写。

| 数据 | 原查询规则 | 已核实规模 |
|---|---|---|
| A / CIC_DEV | 每 capture × owner × canonical key 的合法有标签候选等秩最多 32 条，含首尾；另排除重复/参考重叠观测 | 固定查询 179,886：正常 100,830，攻击 79,056 |
| B / UNSW_DEV 正常 | 每设备预算 20,000；所有组件至少 1 席，其余按残余人口最大余数分配；组件内固定 SHA256(salt\|uid) 排序取样 | 原合法正常人口 983,788 → 选 75,763 → 后续 7200 秒主视图 74,444 |
| B / UNSW_DEV 攻击 | 预先登记的严格 SYN 标签下全部保留，不抽稀 | 72,553 |
| Edge 当前合法 full 人口 | 尚无正式查询预选；已封存资格人口 | 正常 1,334,562 + HTTP 152,352 + UDP 2,898,830 = 4,385,744 |

## 不能直接照搬的原因

1. B 的 20,000 预算仅作用于正常查询；照搬它不会减少 Edge 约 305 万条攻击查询。
2. B 要求组件数不超过设备预算，否则 `COMPONENTS_EXCEED_BUDGET`；A 的每组件最多 32 条也不会削减单点组件。Edge 已记录 UDP namespaces 2,898,538，绝大多数接近单点，不能承诺旧规则会把它变成几万条。namespace 与拟抽样组件的精确对应仍须在元数据人口上核算。
3. 选查询不等于删除上下文：未选包仍须按原序进入合法因果状态，只对选定端点截取快照和编码。也不等于合并相同模型输入。
4. B 冻结 recipe 明确写出：未加权样本 FPR 不是全体物理包 FPR；人口估计另用 `N_g/m_g`。外部若采用抽样，同样须区分抽中样本的精确比率与全人口估计，不能把抽样数称作全量包数。
5. 既有“可能数周”是风险提示，不是相同 Linux 运行时实测后的 ETA。必须先锁定实际编码数量，再用合格预检吞吐与资源测量给预算。

## 可复核出处

- B 冻结规则与指标语义：`runs/legacy_commissioning_unsw_evaluation_preparation_v1_20260926/evaluation_recipe.json:148–165,208–209`。
- B 实现：`repo/ood/legacy_unsw_archival_data_v1.py:13–27,102,156–177,198–227`；先全序 `context.append`，仅选中目标产生 snapshot。
- A 实现：`repo/ood/legacy_reference_sample_prepare_v1.py:30,52,227–279`；`repo/ood/legacy_reference_sample_finalize_v1.py:64,121–127`。
- A/B 连续版从冻结清单继承查询：`repo/ood/continuous_data_v3.py:36,76–91`。
- B 主视图既有复算：`runs/b_sample_fpr_readonly_audit_v1_20261101/audit.py:41–49`。
- Edge 人口与 namespace：`runs/edge_external_test1_engineering_v1_20261103/adapter/population_v1/POPULATION.json`；“数周”提示：同目录上两级 `preflight/README.md:21`。

Codex 对遗漏查询选取沿革复核负责。本回执不改变 C5、A/B 或既有封存人口，也不授权新抽样正式执行。
