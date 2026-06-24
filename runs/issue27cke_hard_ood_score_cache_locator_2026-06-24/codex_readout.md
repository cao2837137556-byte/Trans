# issue27cke hard-OOD 定位读数

本次不是新模型结果，而是复用 issue27ckc 的同一套冻结评分栈，定位为什么 hard benign OOD 会被系统当成攻击。

运行范围：

- medium seed42：`issue27ckc` job 1
- strict seed42：`issue27ckc` job 6
- 全量读取 `ood_stress`、`sealed_final_ood`、`future_query`、`sealed_final_attack`
- 只保存 top 诊断样本，不改变训练、阈值或 controller

## 1. 具体坏在哪一层

结论很明确：问题不是单纯的 temporal/controller 放大，而是 parent 攻击头和 OOD-risk 证据层已经错判。

medium：

| role | temporal hard | parent hard | temporal attack mean | temporal OOD-risk mean | attack distance mean | benign distance mean |
|---|---:|---:|---:|---:|---:|---:|
| ood_val | 0.0001 | 0.0011 | 0.0001 | 0.9999 | 0.5602 | 0.2522 |
| ood_stress | 0.9972 | 0.9974 | 0.9970 | 0.0030 | 0.1309 | 1.2116 |
| sealed_final_ood | 0.9972 | 0.9992 | 0.9970 | 0.0030 | 0.1326 | 1.2368 |

strict：

| role | temporal hard | parent hard | temporal attack mean | temporal OOD-risk mean | attack distance mean | benign distance mean |
|---|---:|---:|---:|---:|---:|---:|
| ood_val | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 0.5602 | 0.2522 |
| ood_stress | 0.6830 | 0.6830 | 0.6829 | 0.3171 | 0.1309 | 1.2116 |
| sealed_final_ood | 0.9966 | 0.9966 | 0.9964 | 0.0036 | 0.1326 | 1.2368 |

解释：

- `ood_val` 被识别为 OOD：风险接近 1，hard alarm 接近 0。
- hard OOD 被识别为 attack：attack score 接近 1，risk 接近 0。
- hard OOD 的 attack distance 甚至比 `ood_val` 更接近 attack support 区域。

所以问题不是“风险阈值调高一点”能解决的。风险头在 hard OOD 上方向错了。

## 2. hard OOD 不是零散噪声，而是设备/文件级集中失败

最大 hard-OOD 来源：

| role | source group | medium hard rows | strict hard rows |
|---|---|---:|---:|
| ood_stress | `processed/iotsim-stream-consumer-1.csv` | 149545 | 102374 |
| ood_stress | `processed/iotsim-stream-consumer-2.csv` | 79700 | 54645 |
| sealed_final_ood | `processed/iotsim-ip-camera-street-2.csv` | 99636 | 99552 |
| sealed_final_ood | `processed/iotsim-ip-camera-museum-2.csv` | 54834 | 54823 |

这说明 hard OOD 是结构性 OOD 域，而不是少数坏样本。

## 3. hard OOD 被吸到哪些 support 模式

对 top 诊断 hard-OOD 样本做最近 support 检查，主要靠近：

- `File Download`
- `Merlin TCP Flooding`
- `Merlin ICMP Flooding`
- 少量 `Mirai C&C Communication`

这不是说这些 benign 真的等价于攻击，而是说明当前 115D/evidence 几何把某些 benign IoTSim 设备流形放进了 attack evidence 区。

## 4. 风险头训练本身没有完全空转，但训练 OOD 不代表 hard OOD

parent OOD-risk 训练确实用了 raw-alarm 行：

| job | role | risk label | rows used |
|---:|---|---:|---:|
| 1 medium | id_calib | 1 | 3285 |
| 1 medium | ood_val | 1 | 1647 |
| 1 medium | support_val | 0 | 58 |
| 6 strict | id_calib | 1 | 3341 |
| 6 strict | ood_val | 1 | 1082 |
| 6 strict | support_val | 0 | 58 |

因此不是“风险头完全没训练”，而是训练时的 OOD-positive 只覆盖了 `ood_val` 那种 OOD，没覆盖冻结后会出现的大面积 hard benign OOD。

## 5. 当前根因判断

可以把问题收敛为三句话：

1. `ood_val` 太容易，不能代表 `ood_stress / sealed_final_ood` 的 hard OOD。
2. hard OOD 在当前 evidence 空间里更像 attack support，而不是 benign core。
3. OOD-risk 头把这种 hard OOD 判成低风险，所以 controller 没有可用证据去挡。

## 6. 下一步修复目标

先不要接 controller，也不要继续调 region。

下一步应该做一个 OOD 修复候选：

- 把 hard OOD 的一部分只作为开发期 OOD calibration，不碰 sealed_final_ood 的报告边界；
- 增加保守 OOD veto 或 hard-OOD-aware risk head；
- 固定同一套 issue27ckc replay 协议重跑；
- 成功标准不是只看 `ood_val`，而是：
  - `ood_stress` hard false alarm 大幅下降；
  - `sealed_final_ood` 仍只 report-only 检查；
  - `support_val / same_file_query / support-covered attack` 不能被明显打残；
  - `future/sealed attack` 的弱项单独记录，不能拿 OOD 修复掩盖攻击泛化问题。

最小下一步建议：做 `issue27ckf`，只验证 “hard-OOD-aware conservative veto” 是否能压住 IoTSim hard OOD，同时保住已覆盖 attack。
