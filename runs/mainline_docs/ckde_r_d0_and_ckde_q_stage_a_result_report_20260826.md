# CKDE-R D0 与 CKDE-Q Stage A 结果报告（2026-08-26）

状态：`RESULT_COMPLETE`

## 1. 结论先行

两项获授权的本地任务均正常完成，无工程失败、无越界访问。

1. **CKDE-R D0：state A**
   `A_NO_IDENTIFIABLE_PAIRED_DEVICE_SUPPORT`。当前合法数据不具备识别
   “设备良性偏移与同族攻击偏移是否纠缠”的配对结构；程序在打开任何
   embedding 数组前终止，CKDE-R 不得进入表征适配 D1。
2. **CKDE-Q Stage A：全部精确回退到 zero-shot**
   23/23 个 Q-S64 主设备均为 `CAP_EXCEEDED_ZERO_SHOT`，0 台完成阈值上调；
   所有具备预算的 123 个校准臂也全部回退，accepted delta 全为 0。

两者合在一起给出清晰答案：现有证据既不足以安全识别表征级设备偏移，也不给
标量阈值校准留下任何安全移动空间。良性观察期作为系统接口仍合理，但当前两种
具体消费方式均未产生可部署增益。

## 2. CKDE-R D0 结果

输出：

`runs/issue27ckde_r_d0_representation_commissioning_identifiability_v1_2026-08-26_local`

### 2.1 Audit-0

| 项目 | 实测 |
|---|---:|
| fit attack 记录 | 4,385 |
| attack devices | 5 |
| device-family incidence rows | 18 |
| attack families | 12 |
| eligible device-family cells | 0 |
| 2×2 cycles | 0 |
| 每个 attack device 的 prior fit-benign sessions | 0 |

具名原因码：

- `ATTACK_DEVICE_UNMAPPED`
- `NO_SAME_DEVICE_FIT_BENIGN_CENTER`
- `INSUFFICIENT_ATTACK_SESSIONS_PER_CELL`
- `NO_TWO_BY_TWO_DEVICE_FAMILY_CYCLE`

这不是“embedding 没信息”，而是**当前数据无法合法提出该问题**：攻击设备没有
同设备、攻击前的可估计良性中心，device 与 family 结构也不足以构成最小 2×2 环。

### 2.2 Fail-closed 证明

- `embedding_arrays_opened = 0`
- `probe_state_arrays_opened = 0`
- support-val/report/FINAL/PCAP/training 全为 0
- 八个 embedding 派生输出全部不存在
- validation status = `PASS`

因此 state A 是 metadata-only 科学裁决，不是运行失败。

## 3. CKDE-Q Stage A 结果

输出：

`runs/issue27ckde_d1_stage_a_calibration_materialization_v1_2026-08-26_local`

### 3.1 分母

| 项目 | 实测 |
|---|---:|
| eligible devices | 23 |
| benign prefix records scored | 9,822 |
| independent prefix sessions | 7,493 |
| embedding width | 768 |
| threshold manifest rows | 161 = 23×7 |
| S64/S128/S256 eligible devices | 23 / 20 / 11 |

### 3.2 各臂状态

| 臂 | cap 超限回退 | 预算不足回退 | zero-shot 基线 |
|---|---:|---:|---:|
| Z | 0 | 0 | 23 |
| Q-S64 | 23 | 0 | 0 |
| Q-S128 | 20 | 3 | 0 |
| Q-S256 | 11 | 12 | 0 |
| Q-R100 | 23 | 0 | 0 |
| Q-R500 | 23 | 0 | 0 |
| Q-R1000 | 23 | 0 | 0 |
| **合计** | **123** | **15** | **23** |

所有 123 个实际计算校准阈值的臂均有：

```text
q_raw = nextafter(T_cap, +inf)
      = 0.06515988319416892
requested_delta = 1.1019905918341344e-08 > cap
accepted_delta = 0
threshold = theta_0 = 0.065159872174263
```

这里的一个 ULP 超限不是随意的数值惩罚。大量良性前缀分数恰好等于 `T_cap`；
在冻结的 `score >= threshold` 报警语义下，只有把阈值严格抬到该分数之上才能消除
这些并列误报，而这会同时越过由 fit attack 冻结的安全上限。因此回退是安全与
误报目标在同一分数点相撞的结构性证据。

### 3.3 隔离边界

- benign suffix score rows opened = 0
- fit attack/support-val/report/FINAL/PCAP/training 全为 0
- `stage_b_authorized = false`
- validation 六项合取全部 PASS

由于所有校准臂最终阈值与 Z 臂逐字相同，打开 Stage B 不可能产生方法间差异；
本报告不请求 Stage B 授权。

## 4. 独立验证

- 实现前合同测试：CKDE-R 24/24、CKDE-Q 21/21，合计 45/45 PASS；
- 执行后 `SHA256SUMS`：CKDE-R 6/6、CKDE-Q 7/7 独立复算 PASS；
- CKDE-R verdict、role-open audit 与缺失派生输出交叉核对一致；
- CKDE-Q 161 行清单、23/20/11 资源分母、123/15/23 状态计数独立重算一致；
- Python 3.9 grammar、`py_compile`、历史 `match/case` 与
  `Path.write_text(newline=...)` 回归扫描均 PASS。

## 5. 科学边界与下一步

本结果不支持以下表述：

- 不支持“表征级校准无效”——CKDE-R 是不可识别，不是效果失败；
- 不支持“良性观察期无用”——失败的是当前阈值级/可识别表征级消费方式；
- 不支持任何 report/FINAL、设备内攻击保持或广义跨设备声明。

可以支持的结论是：

> 在当前冻结证据下，标量阈值级 commissioning 没有安全移动空间；
> 表征级 commissioning 又缺少可识别的同设备良性—攻击配对图。
> 后续若继续保留良性观察期，必须引入不依赖当前缺失配对的全新可证伪机制，
> 或把它明确降为部署扩展而非当前论文的正面主结果。

CKDE-Q Stage B/C 维持未授权；FINAL、HPC、训练、下载均未触碰。
