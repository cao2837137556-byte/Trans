# Frontend-F0 ZT-2 真实语义覆盖结果（2026-08-31）

状态：`ZT_SEMANTIC_COVERAGE_PASS`。

## 1. 结论先行

冻结的零训练语义前端在 30 个已审 packet member、25,467 个 exact target cutoff 上完成了真实两遍解码：

- 全宇宙语义有限：`25,467 / 25,467 = 100%`；
- 旧前端 finite 保全：`13,827 / 13,827 = 100%`；
- 旧前端 missing 恢复：`11,640 / 11,640 = 100%`；
- 每个良性设备最低覆盖率：`100%`（门槛 80%）；
- 每个声明内攻击族最低覆盖率：`100%`（门槛 80%）；
- 30/30 member 均为 `COMPUTED_EXACT_TWOPASS`，末态 active context 合计 0；
- endpoint 首见令牌双射不变性 PASS；
- representation/model/score/training/report/FINAL 打开计数全部为 0。

因此，旧前端的结构化输入盲区已在**确定性语义覆盖层**被实证消除。该结论不是检测性能结论，也不说明 hydraulic finite 误报已经解决。

## 2. 实际上下文层级分布

| 层级 | 语义 | target 数 |
|---|---|---:|
| H1 | TCP/UDP IP endpoint+port context | 13,953 |
| H2 | 其他 IP endpoint-pair context | 1,909 |
| H3 | 非 IP link endpoint-pair context | 9,579 |
| H4 | 无键 bounded consecutive-run context | 26 |
| 合计 |  | 25,467 |

上下文事件数范围：H1 `1–256`、H2 `1–255`、H3 `1–45`、H4 `7–242`。H3/H2 的大规模实占说明新规则不是用一个统一伪会话把缺失行强行填满，而是真实启用了协议/链路语义分层。

时间回退按冻结政策因果钳位：逐 target 累计回退计数合计 26、单上下文最大 3；原始 endpoint 输出计数 0，构造期标签读取计数 0。

## 3. 旧 missing 子集

旧 missing 的 11,640 个 target 全部恢复，包括：

- 良性设备：building-monitor 825、combined-cycle 2,661、combined-cycle-tls 409、domotic-monitor 908、ToN external 6,675；
- 攻击族：File Download 3、Merlin C&C 32、Merlin ICMP 51、Mirai GRE 70、Mirai UDP 6；
- 角色切片：aux_fit 3,079、aux_normal_fit 3,157、aux_normal_select 3,518、aux_select 1,294、id_calib 49、ood_val 381、support_train 139、support_val 23。

这些数字只陈述语义可编码性；特别是攻击族小样本不能被包装成逐族检测能力证明。

## 4. 独立复核

主执行器自报之外，另行完成：

1. `SHA256SUMS` 16/16 本地独立重算 PASS；
2. 从 `zt2_semantic_status_by_target.csv.gz`、旧 availability NPZ 和冻结 metadata 重新 exact join，25,467 UID 一一对应；
3. 独立重算 old-missing=11,640、old-finite=13,827、全量 finite=25,467；
4. 独立重算全量/old-missing 的 worst-device 与 worst-family 覆盖率均为 1.0；
5. 生命周期表 30 行、target 合计 25,467、两遍完成状态 30/30、terminal active context 0；
6. 角色打开审计中 representation/model/score/training/report/FINAL 均为 0。

结果执行 wall time `928.67 s`（约 15 分 29 秒）；结束后 D 盘可用 `83,388,174,336` bytes。Windows 工作集查询未返回可用值，资源清单将其如实记为 `null`，不影响科学门。

## 5. 科学解释与下一门

本结果给出项目近期真正需要的正信号：

> 不依赖训练、不替换在役攻击通道，仅通过冻结、声明式的协议覆盖与无键上下文语义，就能把原来 45.7% 左右的前端可编码覆盖提升到 100%，同时逐 target 保持全部旧 finite 流量可编码。

它证明了 Coverage Extension 的**语义入口**可行，但还没有回答新分支是否保留攻击/正常判别信息。按 FROZEN 边界，下一合法阶段应先把该零训练语义输出接入前端测量仪器，验证表示/判别可用性；未经过新的冻结和授权，不得直接训练或声称 OOD FPR/攻击召回改善。

## 6. 工件

结果目录：`runs/frontend_f0_zero_training_semantics_real_20260831/`。

提交只纳入 `SHA256SUMS` 覆盖的 16 个终态科学工件；30 个成员级 checkpoint 保留在本地用于工程恢复，不作为论文结果工件提交。
