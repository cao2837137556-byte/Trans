# CKCZ FROZEN 勘误 1：Gotham UID→recorded_index lineage（2026-08-10）

状态：**FROZEN ERRATUM — ENGINEERING REPAIR ONLY — SCIENTIFIC CONTRACT UNCHANGED — HPC NOT AUTHORIZED**

本勘误附属于
`ckcz_endpoint_pair_conflict_diagnostic_preregistered_20260809.md`，只补足原文 §5 已要求但未钉住
具体资产的“Gotham UID/target 映射必须复用冻结 target 输入与现有 Record 构造合同”。不修改
研究问题、数据等级、四个 scalar、frontier、门槛、分母、bootstrap、裁决或 FINAL 隔离。

## 1. 触发事实

AMD job `158015` 在 `join_predictions` fail-closed。CKCZ r1 错误地假设：

```text
int(uid.rsplit(":", 1)[1]) == recorded_index
```

但现有 CKBJ Record 合同实际为：

```text
uid = "{role}:{m1_phase}:{row_index_in_frozen_role_frame}"
recorded_index = frozen_role_frame.iloc[row_index].recorded_index
```

所以 UID 尾段只是冻结 role frame 的行号，不是 cache target key。

## 2. 唯一允许的 lineage 资产

复用 CKBY 成功 job 157930 已冻结快照：

```text
runs/issue27ckby_drocc_feature_dump_v1_2026-08-07_seed27_amd_157930/
  ckby_drocc_feature_snapshot_seed27.npz
```

- rows：287,448；
- SHA-256：`b2ef1f7d0244cc7abb8665c25364744f794190f411482e4e202e346cb850279c`；
- provenance：该快照逐行复用 CKBW 正式装配半段生成，记录表 unique UID 覆盖率 100%；
- CKCZ 只允许读取 `uid`、`source`、`role`、`m1_phase`、`recorded_index` 五个数组。

虽然同一 NPZ 还含 `x/label/device_family/attack_family/global_pool`，CKCZ 禁止读取这些数组，
不得用其训练、选 cut、筛 source、决定 state 或改变统计分母。

## 3. 精确映射合同

1. snapshot 路径不得含 FINAL marker，文件 SHA 必须逐字节一致；
2. 五个 lineage 数组长度必须均为 287,448；
3. `(uid, source, role, m1_phase)` 必须唯一；
4. CKBW 预测表中非 `aux:`、非 `ton:` 的每行，以
   `(uid, source_group, role, phase)` exact many-to-one join lineage；
5. join 后使用 lineage `recorded_index` 与 Gotham metadata 的
   `(source_group, recorded_index)` exact join；unexpected miss 必须为 0；
6. auxiliary 与 ToN 合同保持原 FROZEN 不变；
7. 禁止 source-order、时间近邻、标签、family 或字符串相似度 fallback。

## 4. 新增工程门

- 合同测试必须包含 UID suffix 与 recorded_index 不相等的正例；
- 本地真实工件必须证明 CKBW 全部非-ToN Gotham UID lineage 覆盖，且键/来源/role/phase 一致；
- installer 与 compute-node Slurm 都钉 snapshot SHA；任一不存在或漂移即工程失败；
- job 158015 及其 partial outputs 永不作为新 run 的 checkpoint 或科学证据复用。

## 5. 授权边界

本勘误只授权实现、测试、构建修复 bundle 和独立审查。原 bundle SHA
`9c3da516...` 作废且禁止重提。新的 HPC job 仍需 Kimi 对修复包 PASS，随后由用户再次明确授权。
