# CKDE-R D0 与 CKDE-Q Stage A 实现报告（2026-08-26）

状态：`IMPLEMENTED_AND_LOCALLY_VALIDATED`

## 1. 授权与边界

项目所有者于 2026-08-26 明确“都授权”。本次只消费以下两项授权：

1. CKDE-R D0 的实现与执行；
2. CKDE-Q Stage A 的校准阈值物化存档。

本次不授权、也未实现 CKDE-Q Stage B/C；不接触 benign suffix outcome、
support-val、viewed/report、FINAL、PCAP，不下载数据，不训练模型，不提交 HPC。

## 2. 实现

新增：

- `repo/ood/issue27ckde_r_d0_representation_commissioning_identifiability_v1.py`
- `repo/ood/issue27ckde_r_d0_representation_commissioning_identifiability_contract_tests_v1.py`
- `repo/ood/issue27ckde_d1_stage_a_calibration_materialization_v1.py`
- `repo/ood/issue27ckde_d1_stage_a_calibration_materialization_contract_tests_v1.py`

### 2.1 CKDE-R D0

执行器首先完成五个冻结输入的 SHA-256 钉死，再只读 plan、session metadata 与
父 D0 census 完成 Audit-0。Audit-0 的四个机械条件、2×2 device-family cycle、
独立会话计数和具名失败原因均按 FROZEN 落地。若 Audit-0 失败，程序在打开
embedding NPZ 之前原子产生 state A，且 embedding 派生文件必须全部不存在。

当前真实输入已由合同测试确认落在 state A；因此实际合法执行路径在 I1 结束。
实现同时钉死了 768D/P2-769D、稳健中心/尺度、shrinkage、bootstrap、稳定性门、
cosine/projection 与 P2 评分等后续数学原语，但不会在 state A 后越级打开数组。
若未来输入的 Audit-0 变为 PASS，当前程序会工程性 fail-closed，不能静默宣称
I2-I4 已执行；那需要在新输入身份下另行完成后段实现审查。这一边界防止“为当前
失败分支写死结果”，也不影响本次 frozen 输入的完整 state-A 科学裁决。

### 2.2 CKDE-Q Stage A

执行器钉死 Numerical FROZEN、cap、D0 census、fit/select plan、embedding、session
metadata、P2 state 与阈值 marker。它只对 23 台合格设备的合法良性前缀行重放冻结
P2 分数，按完整会话构造 `Z/Q-S64/Q-S128/Q-S256/Q-R100/Q-R500/Q-R1000` 七臂。

校准阈值严格满足：

```text
theta_d >= theta_0
theta_d <= T_cap
cap 超限时 theta_d == theta_0
```

输出只冻结阈值清单与资源计数，不打开任何后缀结果，也不授权 Stage B。

## 3. 验证

- CKDE-R D0：24/24 合同测试 PASS；
- CKDE-Q Stage A：21/21 合同测试 PASS；
- 两个程序与两个测试文件均通过 `py_compile`；
- 四文件均通过 Python 3.9 AST grammar；
- 无 `match/case`，无 `Path.write_text(newline=...)` 历史兼容性回归；
- `git diff --check` PASS。

真实身份测试额外确认：

- CKDE-R Audit-0 会在 embedding 打开前失败关闭；
- CKDE-Q 合格设备与资源曲线分母精确为 23/20/11；
- 固定 common-11 设备清单与 D0 census 完全一致。

## 4. 执行计划

实现验证通过后，按用户既有授权依次执行：

1. CKDE-R D0，预期只产生 metadata-only state A 证据；
2. CKDE-Q Stage A，物化 23 台设备的阈值回退/校准清单；
3. 独立复算结果哈希和关键分母后再写结果报告。

Stage B/C 继续保持未授权。
