# CKBY 预注册草案：DROCC 记录级能力基线（DRAFT，未冻结）

- 日期：2026-08-07
- 状态：**DRAFT**——GPT 评审意见已并入，Kimi 补充已并入；待 GPT 确认措辞 +
  Codex（8 月 10 日回归）独立终审后才转 FROZEN。冻结前不训练、不上 HPC。
- 上游依据：`record_level_capacity_audit_20260807.md`（commit 68bdeb2，裁决 R2 有界版）、
  GPT 对 68bdeb2 的评审（8 条）、CKBW FROZEN 预注册
  `ckbw_tail_margin_dual_control_preregistered_20260803.md`（数据角色逐条核对一致）。

## 1. 唯一假设

**H_record-capacity**：在严格相同的开放世界协议下，一个强 benign-only 记录级
表示学习器是否足以同时保持 unseen 攻击召回与良性 OOD 抑制。

本实验只回答这一个问题。不是论文 primary 候选，不是模型 zoo 入口。

## 2. 模型（唯一，无备选）

**DROCC（Deep Robust One-Class Classification, ICML 2020）on 冻结 51D 特征。**

- 选 DROCC 而非 DeepSVDD：DeepSVDD 有已知 hypersphere collapse 风险与架构约束；
  DROCC 专为该问题设计且在 tabular 任务上有公开验证（GPT 评审 #1，Kimi 接受）。
- 选 DROCC 而非 Normalizing Flow：本实验测的是"强一类表示学习能否挖出单记录信息"，
  不是"谁最会估计 51D 密度"（GPT 评审 #1）。
- DROCC 的对抗负样本由梯度上升**合成**，不接触任何真实攻击数据，保持 zero-positive。
- 禁止第二个模型进入本实验；禁止 family 专家；禁止新前端/重解码 PCAP。

### 2.1 架构与超参数来源规则

- 输入：冻结 51D 过程特征（与 CKBW 完全相同的特征管线产物，不重算）。
- 标准化：统计量**只从 14,013 合法 benign fit 行计算**（fit-only standardization，
  沿用 CKBW 第 3.3 节禁令）；统计量 SHA-256 入 run_spec。
- 网络结构、radius r、ascent lr/steps、λ、optimizer、batch、epochs：冻结时从
  DROCC 原论文 tabular 设置取默认值并逐条写明；**禁止用 VIEWED OOD / future attack /
  FINAL 数据选择任何超参数**。允许的超参依据只有：原论文默认值 + benign-only
  验证损失（见 2.2）。
- 随机性：仅 seed 27。seeds 37/47 继续锁定。

### 2.2 训练与 checkpoint 选择（benign-only，Kimi 补充）

- 从 14,013 benign fit 中按 source 分层切出 10% 作为 **benign 验证集**（切分规则
  冻结时写明；该子集不得再用于训练）。
- 训练早停/模型选择只依据 benign 验证集上的 DROCC 损失；**禁止用任何攻击或
  held OOD 指标选 checkpoint**。
- support_val 69 条攻击**不参与**训练、不参与阈值、不参与 checkpoint 选择；
  仅在最终一次性评估中作为安全指标报告（GPT 评审 #3：否则必须降级表述为
  "benign-only training, attack-aware calibration"，本草案选择不做这种降级，
  保持 pure zero-positive）。

## 3. 数据角色（与 CKBW FROZEN 逐条一致，已核验原文第 3.1/3.2/3.3 节）

### 3.1 Fit（14,013 benign，zero-positive）

| 类型 | 来源 | 行数 |
|---|---|---:|
| benign core `id_calib` | combined-cycle-tls-3/4/5（270/270/269） | 809 |
| benign core `ood_val` | building-monitor-2/3（1,690/914） | 2,604 |
| benign auxiliary | 冻结 auxiliary fit | 6,600 |
| benign ToN-IoT | `normal_1` | 4,000 |

0 future attack、0 viewed OOD label、0 final、0 support attack（GPT 评审 #2）。

### 3.2 Select（7,000 benign，只用于 operating point）

| 类型 | 来源 | 行数 |
|---|---|---:|
| benign select | frozen auxiliary select | 3,000 |
| benign select | ToN-IoT `normal_2` | 4,000 |

### 3.3 Report（一次性评估，与 CKBW 完全相同的分母）

future_query、sealed_final_attack、same_file_query、support_val 69、
4 个已看良性 OOD 池（hydraulic ood_val 3,000 / ip-camera-street sealed 3,000 /
predictive-maintenance aux_report 9,000 / stream-consumer ood_stress 3,000）。

### 3.4 FINAL（完全封存）

cooler-motor、seeds 37/47——本实验不触碰。

## 4. Operating point（冻结规则，GPT 评审 #3）

在打开任何 report 池之前，用 7,000 benign select 按以下规则确定并冻结：

- **主工作点 OP-1**：select 分数的 99 分位（良性误报预算 1%）；
- **副工作点 OP-0.1**：99.9 分位（预算 0.1%）。

两个点都在预注册中定死；评估时对两个点分别报告。**禁止**根据 future 攻击召回
反向调整；report 池 ROC/AUC 只作诊断输出，不得反馈进任何选择。

## 5. 双重门（GPT 评审 #4，措辞已收紧）

### Gate A — CAPACITY_SIGNAL（本实验的判据）

在冻结工作点上同时满足：

- 4 池良性 OOD macro hard rate ≤ **30.27%**（= FrozenCKBQ 35.27% − 5pp）；且
- future 攻击召回 ≥ **84.83%**（= C1 86.834% − 2pp）。

PASS 的含义仅为：**强记录级表示的信息不能被排除**，暂停 episode 主线，
转而研究 DROCC 成功的原因。Gate A PASS **不等于**论文方法 GO。

### Gate B — Mainline Scientific GO

沿用现有冻结契约（attack preservation / per-family / OOD 严格规则），不因地
Gate A 通过而放宽。本实验臂**无资格**事后晋升为论文 primary。

### Per-family 安全（GPT 评审 #5）

按冻结 family 口径逐族报告（Merlin C&C、Mirai C&C、Telnet、Ingress、TCP Scan、
UDP Scan、CoAP、Reporting 等全部族）；不得新造 family 级阈值；任何一族清零
必须在结论中显式声明。

## 6. 明确禁止

- 不重新解码 PCAP、不动前端、不加 Whisper 式频域特征；
- 不用 attack 标签训练或选阈值（pure zero-positive）；
- 不报 episode 化指标作为 primary/selection（GPT 评审 #6：保持单一假设纯净）；
- 不用 VIEWED/FINAL 选超参；不开第二个模型；不做 family 补丁；
- 不因本实验结果事后修改 CKBW 已冻结结论。

## 7. 审计输出（执行时必须产出）

run_spec.json（含全部冻结超参）、fit/select 逐行 provenance 与角色断言、
标准化统计量 SHA-256、模型权重 SHA-256、DROCC 训练曲线（benign 损失）、
两个工作点的全套 per-family / per-pool 表、与 C1 / FrozenCKBQ / CKBW M7 的
同分母对照表、结果一次性评估声明（无重复窥探）。

## 8. 结果路由

- Gate A FAIL（预期内结果）：假设 A 封死 → 记录级 capacity 解释关闭 →
  episode/context 必要性证据链闭环（文献不可比 + 六模型类同墙 + 最强记录级
  baseline 失败）→ 进入 CKBX episode 预注册。
- Gate A PASS：暂停 episode，分析 DROCC 成功机制；是否转入主线由三方另行
  预注册决定，本实验不自动晋升。

## 9. 待评审开口项

1. DROCC 具体超参数值（冻结时从原论文 tabular 设置填入）；
2. benign 验证集 10% 的确切切分规则；
3. OP-1 / OP-0.1 双工作点是否保留，还是只留 OP-1；
4. Gate A 的 30.27% / 2pp 是否最终值。
