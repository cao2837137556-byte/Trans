# 机制信号本地预演（探索性记录）

日期：2026-07-26
性质：**探索性诊断，不改任何协议、不进任何正式流程、不作为论文正式结果。**
用途：为论文 §5.4"为什么过程证据只能救援不能初筛"提供动机证据；为
CKBV seed-27 的按机制 AUROC 提供一个保守的本地预期。权威数字仍以 seed-27
的正式按机制读数为准。

## 问题

冻结的 51D 因果过程表示，对 scan / credential-bruteforce 机制相对良性
ToN 流量的可分性有多强？这正是 CKBV seed-27 过程头必须做的事。

## 方法

- 前端：冻结 `CausalFeatureBuilder`（bit-exact 快路径），跑本地 ToN 原始
  PCAP（CKBT 已批准的静态监督数据）。
- 攻击行时间聚焦：按 CKBT 标注的 scan/bruteforce 连接的 floor(ts) 秒集合过滤
  （scan 1794 秒、bruteforce 2028 秒）——秒级聚焦，非精确单连接隔离。
- 良性对照两种：跨文件（normal_1）与同文件背景（同一 PCAP 中非攻击秒的包）。
- 判别器：5 折交叉验证的标准化 LR，报告 ROC-AUROC；外加单维标准化均值差 d。

### 诚实局限（均为保守方向，只会低估信号）

1. 秒级聚焦使攻击行含背景污染；
2. 本地无 TShark，`tcp.stream`/时序/`tcp.analysis` 维度置零，故本预演仅用
   了 51D 的一个子空间（fan-out / syn-rst / 方向性维度为真，TCP 分析维度为
   零）——完整字段的正式过程头信息更多，分离度只会更高；
3. 良性对照来自有限文件。

## 结果

| 对比 | 5 折 LR AUROC |
|---|---|
| scan vs 跨文件良性 | **0.9771 ± 0.0038** |
| credential-bruteforce vs 跨文件良性 | **0.9997 ± 0.0003** |
| scan vs 同文件背景 | **0.5891 ± 0.0111** |
| credential-bruteforce vs 同文件背景 | **0.6856 ± 0.0095** |

顶部判别维度（跨文件）：`hist_source_rate_1s/10s/60s`（源速率，d 高达 1.57）、
`hist_log_reverse_response_ms`、包间隔类、`cur_log_frame_len`（爆破 d=1.18）。
同文件背景下唯一仍站得住的：**源速率类**（bruteforce d≈0.5–0.64）。

## 解读（进论文 §5.4）

- **机制信号真实存在且跨环境可迁移**（跨文件 0.98 / 0.9997）：51D 认得出
  扫描/爆破机制的"长相"，且跨环境保持。⇒ 未见攻击侧的救援素材是真的。
- **同环境高度混淆**（0.59 / 0.69）：机制签名与同环境正常背景重叠严重。
  ⇒ 过程证据**不能单独当检测器**，只能在 C1 已报警的候选内做二次确认。
- 二者合起来，从数据上论证了非对称决策的每个设计决定：C1 锚点先抓、
  救援只在候选内二次确认、无证据默认保留。
- 对 seed-27 的预期收窄：TCP Scan / Telnet 救回把握高（d>1，完整字段更强）；
  主要风险仍是"救援分支在同环境的四类工业 OOD 上误触发"——因为同环境本就
  难分。这与预注册的 GO 风险分析一致。

## 复现

脚本（scratchpad，非仓库正式代码）：`mechanism_signal_preview.py`，
依赖冻结的 `issue27ckbu_unified_tshark_causal_frontend_v1` 与
`issue27ckbv_checkpointed_sparse_process_frontend_v1`（FastCausalState），
输入 `datasets/external/ton_iot_raw_network/raw_pcap_pilot_v1/` 与 CKBT
manifest。种子 27。
