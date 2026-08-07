# Record-level Capacity Audit：单记录方法能力边界审计（2026-08-07）

执行：Kimi（三方协同）。约束已全部遵守：未写 episode 代码、未上 HPC、未训练任何模型、
未打开 FINAL（cooler-motor、seed 37/47）、未从 VIEWED 数据挑任何阈值或模型。
`a23c5fa` 的 C1-veto STATE_1 结论保持有效，本文不撤销它，只回答一个新的替代解释。

## 0. 审计问题

CKBW 记录级 veto 失败（STATE_1）有两个竞争解释：

- **假设 A（模型不够强）**：单记录里有足够信息，只是 C1 / 51D 没学出来；换一个真正强的
  benign-only 方法可能就解决了。
- **假设 B（观察尺度不够）**：单条连接本身就分不开，再强的记录级模型也只能学到重叠，
  必须加入跨记录上下文。

本文分两段：(I) 文献 + 内部证据审计；(II) 据此给出 R1/R2/R3 三选一裁决。

---

## I. 文献协议审计

核对标准（GPT 指定七项）：benign-only 训练？阈值是否用 attack/test 标签？训练/测试良性
是否同源？是否存在真正的 device/source 级 benign-OOD shift？unseen attack 划分方式？
是否用 connection-final / future 特征？是否同时要求低 benign-OOD 误报 + 高 unseen 召回？

### I.1 顶会/一区代表系统

| 系统 | 会议 | benign-only | 良性 train/test 同源 | 真正 benign-OOD shift | unseen attack 划分 | 判定粒度 | 阈值来源 | 双指标同时达标 |
|---|---|---|---|---|---|---|---|---|
| **Kitsune/KitNET** | NDSS 2018 | ✅ 仅良性在线训练 | ✅ **同源**：每条 trace 前 ~1M 包训练、剩余包测试（原文 Table III） | ❌ 无 | 同 trace 内时间切分 | 单记录（增量统计特征） | ROC 分析（用测试集标签） | 未测 |
| **Whisper** | CCS 2021 | ✅ 良性 AE 聚类 | ✅ **同源**：MAWI 骨干网背景流量，攻击回放进同一骨干 | ❌ 无（跨日期同网络） | 按攻击数据集逐个测 AUC/EER | **流窗口频域**（包长序列 DFT，非单记录） | 每数据集报 AUC/EER | 未测（无未见良性环境） |
| **HyperVision** | NDSS 2023 | ✅ 无监督图学习 | ✅ **同源**：92 个攻击数据集回放进同一 MAWI 骨干背景 | ❌ 无 | 按攻击数据集逐个测，AUC≥0.92 / F1≥0.86 | **跨流交互图**（图连通分量，非单记录） | 图损失阈值 | 未测 |
| **pVoxel** | CCS 2023 | ✅ 无监督 | ✅ 同源（对 11 个检测器的告警做后处理） | ❌ 无 | 不涉及 | **告警点云**（episode/告警级） | 密度无监督 | 减 95.55% FP，但它是告警分诊层不是检测器 |
| **NetVigil** | NSDI 2024 | ✅（GNN+对比学习，流日志图特征） | 数据中心生产 traces + 场景攻击（Yatesbury benchmark） | 部分（跨集群稳健性主张，摘要级证据） | 场景式 | **图特征**（跨流上下文） | 对比学习 | 摘要级，协议细节未全文核对 |
| **Corsini & Yang** | CNS 2023 | — | — | 直接研究 OOD 技术对 NIDS 的适用性 | — | — | — | 摘要级证据 |
| **Meta-learning zero-day web** | CCS 2023 | 跨 web 域零日检测（元学习） | 跨域 | ✅ 跨 web 域（最接近我们的设置） | 域留出 | HTTP 请求级 | 元学习 | 仅参考文献级证据，未核全文 |

证据来源（均为本次实际抓取）：Kitsune NDSS 2018 原文 PDF（ndss-symposium.org/
ndss2018_03A-3_Mirsky_paper.pdf，DOI 10.14722/ndss.2018.23204）；Whisper CCS 2021
（arXiv:2106.14707；卷目经 CCS 2021 参考文献核实 pp. 3431–3446）；HyperVision NDSS 2023
（ndss-symposium.org/ndss-paper/… 及 2023-80-paper.pdf）；pVoxel CCS 2023
（DOI 10.1145/3576915.3616631，ACM 摘要页）；NetVigil NSDI 2024
（ACM 10.5555/3691825.3691922 摘要 + microsoft/Yatesbury benchmark 仓库）；
Corsini & Yang（IEEE CNS 2023, 10288685，题录级）；meta-learning 零日 web 检测
（CCS 2023 pp. 1020–1034，参考文献级）。另注意 Whisper 常被误记为 USENIX——实为 CCS 2021，
HyperVision 实为 NDSS 2023，本审计已逐条核实。

### I.2 文献侧结论

1. **没有任何一个高水平 benign-only 系统在"留一 device/source 良性环境 + 冻结合法阈值 +
   同时报 unseen 攻击召回"的协议下被评估过。** Kitsune/Whisper/HyperVision 的良性训练和
   测试全部来自同一网络环境（同一 capture、同一骨干、同一集群）。"别人只训 benign 也能
   高泛化"与我们的开放世界任务**不可比**（GPT 的 R3 判断成立）。
2. **该领域最强的 benign-only 系统没有一个停留在单记录粒度**：Whisper 用流内包长序列的
   频域表示，HyperVision 用跨流交互图，NetVigil 用图特征 + 对比学习，pVoxel 干脆在告警
   点云上工作。顶级系统的共同选择就是**跳出单记录、吃跨记录上下文**——这本身是支持
   episode 方向的间接证据。
3. pVoxel 证明"检测器告警 → 后处理分诊"路线能减 95.55% FP，但它假设已有检测器且只处理
   告警点，不解决 unseen 攻击召回，和我们的双约束任务不同。

---

## II. 内部证据审计（我们已跑过的 benign-only / normality 方法）

| 臂 | 模型类别 | benign-only | future 攻击召回 | 良性 OOD hard rate | 出处 |
|---|---|---|---|---|---|
| M0-C1（conformal normality） | 保形秩检验 | ✅（id_calib 校准） | 86.83% | 100 / 100 / 100 / 72.4%（4 池） | ckbq_seed27_formal_result_20260721.md |
| A0 global normal conformal | 全局良性保形 | ✅ | 82.25%（overall） | 5.5 / 55.5 / 26.9 / 42.8% | 同上 |
| M1 shielded static | 静态良性护盾 | ✅ | 84.34%（overall） | 8.1 / 57.6 / 29.7 / 43.4% | 同上 |
| M3 consensus | 静态+时序共识 | 部分 | 84.35%（overall） | 8.1 / 57.6 / 29.7 / 45.7% | 同上 |
| CKBM TabM 因果源校准 | 少样本+校准 | ❌（用 support） | −0.43pp | stream 99.6% | experiment_map |
| CKBO raw AfterImage115 normality | 原始重构误差 | ✅ | −6.09pp | stream 99.7 / pred 73.0 / hyd 42.5% | experiment_map（151780） |
| CKBW M7（冻结 CKBQ+51D 双阈值） | 少样本+过程评分 | ❌ | −23.64pp（future） | **macro 0.0015** | ckbw_seed27_result_analysis |
| C1-margin veto（昨日诊断） | 记录级仲裁 | — | 7/8 族上限 < 0.90 | 良性占满分数顶端 | a23c5fa |

**关键模式**：保形（C1/A0）、静态护盾（M1）、时序（M2）、共识（M3）、原始重构
（AfterImage115）、少样本深度（TabM/CKBW）——**六个不同模型类别全部撞上同一堵墙**：
攻击召回拉高 → 良性 OOD 爆炸（C1：91.3% 召回但 OOD 100%）；OOD 压下去 → 隐蔽攻击崩
（M7：OOD 0.0015 但 Merlin 0.045）。多模型类别在同一前沿上失败，是"信息/表示层面
重叠"（假设 B）强于"单模型容量不足"（假设 A）的证据——但不是决定性的：这些模型
没有一个是"现代深度一类表示学习"（deep one-class）。

---

## III. 三选一裁决

### 裁决：**R2（有界版）** —— 存在且仅存在一个值得正式验证的强 benign-only 记录级
baseline，先预注册它，再决定 episode 主线。

理由分解：

- **R3 成分（协议不可比）已证成**：文献里不存在与我们协议可比的"benign-only 高泛化"
  结果，审稿人不能用"别人 99% AUC"反驳我们；反过来我们也不能用文献断言"任何
  记录级方法都不行"。
- **为什么不能直接 R1**：我们的内部证据覆盖多个模型类别但**没有覆盖深度一类表示学习**
  （deep one-class / 密度估计）。假设 A 的最强形式——"换一个真正强的表示，单记录信息
  就够了"——目前无法被已有证据排除。若跳过它直接 episode，审稿人一句
  "Why not a stronger benign-only detector?" 我们仍被动。
- **R2 候选的唯一指定**（避免模型动物园）：

> **Deep One-Class（DeepSVDD 类）on 冻结 51D 特征**
> - 用**现有冻结 51D 特征**，不重解码 PCAP、不动前端、不上新特征（Whisper 式频域
>   前端被明确排除：那是新前端工程，正是烧掉我们一周的东西，且其流窗口粒度已
>   半只脚踏进 episode 领地）；
> - 只在 **LEGAL benign fit** 数据上训练（id_calib 等合法拟合池，逐行核验）；
> - 不用 future attack / viewed OOD 标签选模型或阈值；VIEWED 池只做机制分析；
> - FINAL（cooler-motor、seed 37/47）完全封存；
> - 与 CKBW **完全相同的 evaluation denominator**；同时报 attack safety 与
>   benign-OOD hard rate；禁止 family 级阈值/专家；禁止未来连接统计；
> - 预注册 GO/NO_GO：**GO 标准 = 在 OOD macro ≤ CKBW 放行门槛的同时，future 攻击
>   召回不差于 C1 超过 2pp**（草案值，待 GPT/Codex 评审）；
> - 成本：纯表格训练，本地或一个小型 HPC 作业即可，不重走前端管线。

- **该实验的唯一假设（H_record-capacity）**：在严格相同开放世界协议下，更强的
  benign-only 记录级检测器是否足以同时保持 unseen 攻击召回与良性 OOD 抑制。
  - 若它同样表现为"攻击高→OOD 爆炸 / OOD 低→隐蔽攻击崩"，则假设 A 被钉死，
    R1 自动成立，episode 的必要性证据链闭环（含文献不可比 + 多模型类同墙 +
    最强记录级 baseline 失败）。
  - 若它明显解决，则暂停 episode 主线，回头研究该表示为何成功。

---

## IV. 给 GPT / Codex 的评审点

1. 候选模型是否就定 DeepSVDD 类（vs 归一化流密度估计）？二者只许选一个进预注册。
2. GO/NO_GO 草案门槛（OOD macro ≤ 30.27% 且 future 召回损失 ≤ 2pp vs C1）是否过宽/过严？
3. 训练池是否仅 id_calib=809 足够，还是需要合法扩大（须先核验 provenance）？
4. 是否需要同时报 episode 化后的口径以防"记录级赢、告警量输"？

本文档 + 本审计所用检索 CSV（`_kimi_review/capacity_audit/lit*.csv`）可供复核。
完成三方评审前，不启动新的超算任务。
