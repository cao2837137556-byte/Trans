# CKBY 预注册：DROCC 记录级能力基线（FROZEN）

- 日期：2026-08-07
- 状态：**FROZEN**。自本文件 SHA-256 侧车生成之时起，除笔误外不得修改；
  任何变更必须新开预注册。冻结授权：用户明确指令（2026-08-07 15:37，
  "codex 不在……不用等他拍板"）+ GPT round-8 评审已并入 + Kimi 执行。
  Codex 回归后按 commit 记录审查，不构成解冻条件。
- 草案来源：`ckby_drocc_record_capacity_baseline_prereg_draft_20260807.md`
  （commit 7473a0e 起，736c7a2 并入 round-8 修订）。本文件与草案的差异仅为：
  填入 §2.1 冻结超参数、写明哈希兜底规则、状态转 FROZEN。
- 上游依据：`record_level_capacity_audit_20260807.md`（commit 68bdeb2，
  裁决 R2 有界版）、GPT 对 68bdeb2 的评审（8 条）、CKBW FROZEN 预注册
  `ckbw_tail_margin_dual_control_preregistered_20260803.md`（数据角色逐条核对一致）。

## 1. 唯一假设

**H_record-capacity**：在严格相同的开放世界协议下，一个强 benign-only 记录级
表示学习器是否足以同时保持 unseen 攻击召回与良性 OOD 抑制。

本实验只回答这一个问题。不是论文 primary 候选，不是模型 zoo 入口。

## 2. 模型（唯一，无备选）

**DROCC（Deep Robust One-Class Classification, ICML 2020, Goyal et al.）
on 冻结 51D 特征。**

- 选 DROCC 而非 DeepSVDD：DeepSVDD 有已知 hypersphere collapse 风险与架构约束；
  DROCC 专为该问题设计且在 tabular 任务上有公开验证（GPT 评审 #1，Kimi 接受）。
- 选 DROCC 而非 Normalizing Flow：本实验测的是"强一类表示学习能否挖出单记录信息"，
  不是"谁最会估计 51D 密度"（GPT 评审 #1）。
- DROCC 的对抗负样本由梯度上升**合成**，不接触任何真实攻击数据，保持 zero-positive。
- 禁止第二个模型进入本实验；禁止 family 专家；禁止新前端/重解码 PCAP。
- 实现方式：自包含脚本**逐行复刻** microsoft/EdgeML 官方
  `pytorch/edgeml_pytorch/trainer/drocc_trainer.py` 的 DROCCTrainer 算法
  （2026-08-07 取自官方仓库 master 分支原文核对），不引入 edgeml 依赖，
  避免依赖漂移；脚本内注释逐段标注对应的官方代码行。

### 2.1 架构与超参数（全部冻结，来源逐条标注）

| 项 | 冻结值 | 来源 |
|---|---|---|
| 输入 | 冻结 51D 过程特征（与 CKBW 完全相同的特征管线产物，不重算） | CKBW FROZEN |
| 标准化 | mean/std 只从 14,013 benign fit 行计算；std + 1e-4 防零；统计量 SHA-256 入 run_spec | 官方 load_data 惯例 + CKBW §3.3 |
| 网络 | MLP：Linear(51→128) + ReLU + Linear(128→1)，输出 logit 即异常分 | 官方 main_tabular.py MLP（hd=128） |
| optimizer | Adam，初始 lr = 1e-3 | 官方 main_tabular.py |
| lr 调度 | 官方 adjust_learning_rate 分段：epoch ≤ 30% 总数用 lr；≤60% 用 0.1×；≤90% 用 0.01×；其后 0.001× | 官方 main_tabular.py |
| lamda（对抗损失权重 μ） | 1 | 官方 tabular 默认 |
| gamma（投影外环倍数） | 2 | 官方 tabular 默认 |
| radius r | **7** | 规则 r≈√input_dim：√51≈7.14→7；与官方 6 维 r=2.5 / 8 维 r=3 / 274 维 r=16 的尺度模式一致 |
| ascent_step_size | 0.001 | 官方默认 |
| ascent_num_steps | 50；每 10 步向环带 [r, γr] 投影一次（含第 50 步） | 官方默认与官方投影逻辑 |
| 对抗点初始化 | x_adv = x + N(0, I)（标准化空间标准正态噪声） | 官方 one_class_adv_loss 首行 |
| only_ce_epochs | 50（前 50 epoch 纯 CE，之后 CE + λ·adv） | 官方默认 |
| batch_size | 256，每 epoch shuffle | 官方 tabular 设置 |
| total_epochs | 200 | 官方 tabular 设置 |
| 随机性 | 仅 seed 27：torch.manual_seed(27)、numpy seed 27、 DataLoader generator seed 27；设备固定 CPU 以保证可复现 | 本预注册 |
| seeds 37/47 | 继续锁定，本实验不触碰 | 主线纪律 |

**禁止用 VIEWED OOD / future attack / FINAL 数据选择任何超参数。**
允许的超参依据只有：上表官方默认值 + benign-only 验证损失（见 2.2）。

### 2.2 训练与 checkpoint 选择（benign-only）

- 从 14,013 benign fit 中切出 **benign 验证集**：**每个 source 内按时间顺序取尾部
  10%**（前 90% train，尾部 10% validation）。网络流量时序相关性强，随机切分会让
  训练/验证样本高度相邻造成泄漏；51D 本身 past-only，时序尾部切分符合部署逻辑
  （GPT round-8 #3）。
- **哈希兜底规则（冻结）**：若某 source 无法可靠定义时间顺序，对该 source 的行按
  `md5(uid 的 UTF-8 字节)` 取十六进制摘要末位字符，落入 `{9,a,b,c,d,e,f}` 中
  预先指定的**仅字符 `f`** 者入验证集（期望比例 1/16≈6.25%，取最接近 10% 的
  单字符方案；禁止为凑比例改用多字符），其余入训练。禁止临时随机切分。
  每个 source 用哪条规则（时序/哈希）必须写入 run_spec 逐 source 声明。
- 验证子集不得再用于训练；但标准化统计量仍按 §2.1 用全部 14,013 行计算
  （与官方惯例一致，benign-only，无泄漏）。
- checkpoint 选择（冻结）：每个 epoch 结束在 benign 验证集上计算**正常点 CE 损失
  （label=1 的 BCE mean）**，取验证损失最低的 epoch 的权重；并列取更早 epoch。
  **禁止用任何攻击或 held OOD 指标选 checkpoint。**
- support_val 69 条攻击**不参与**训练、不参与阈值、不参与 checkpoint 选择；
  仅在最终一次性评估中作为安全指标报告（GPT 评审 #3：保持 pure zero-positive，
  不降级为 attack-aware calibration）。

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

- **OP-1（PRIMARY capacity working point）**：select 分数的 99 分位（良性误报预算 1%）；
- **OP-0.1（预声明 secondary stress point）**：99.9 分位（预算 0.1%）。

两点都在预注册中定死、主副分明，**不得结果出来后择优晋升**（GPT round-8 #4）。
双点的科学用途：观察良性预算从 1% 收紧到 0.1% 时攻击召回是渐降还是崩塌——
这本身就是 capacity curve 信息。**禁止**根据 future 攻击召回反向调整；report 池
ROC/AUC 只作诊断输出，不得反馈进任何选择。

## 5. 双重门（GPT 评审 #4，措辞已收紧）

### Gate A — CAPACITY_SIGNAL（本实验的判据）

在冻结工作点（OP-1）上同时满足：

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

run_spec.json（含 §2.1 全部冻结超参与逐 source 切分规则声明）、
fit/select 逐行 provenance 与角色断言、标准化统计量 SHA-256、
特征快照 SHA-256（见 §9）、模型权重 SHA-256、DROCC 训练曲线（benign CE
与 adv 损失逐 epoch）、两个工作点的全套 per-family / per-pool 表、
与 C1 / FrozenCKBQ / CKBW M7 的同分母对照表、结果一次性评估声明（无重复窥探）。

## 8. 结果路由（措辞按 GPT round-8 #2 收紧）

- **Gate A FAIL（预期内结果）**：封死的是"**现有冻结 51D 表示上模型容量不够**"
  这一剩余替代解释。连同 conformal / reconstruction / tree / TabM / C1+51D 仲裁
  在同一 trade-off 上的重复失败，继续更换记录级学习器的科学边际价值已经很低，
  主线据此转向跨记录上下文/episode 证据。**我们不声称"所有可能的记录级表示
  均不可能"**（预训练流量表征等路线作为储备保留，见简报 round 8 假设库）——
  对审稿人的标准回答是：多类模型在统一因果表征下达到一致性能边界，因此选择
  增加新的上下文信息，而非继续增加模型复杂度。随后进入一次专门的
  **Episode Design Review**（统一比较 GPT/Kimi/Claude 的 episode 假设、明确相对
  CKBQ 旧时序分支的新增信息），通过后才起草 episode 预注册。
- **Gate A PASS**：暂停 episode，分析 DROCC 成功机制；是否转入主线由三方另行
  预注册决定，本实验不自动晋升。

## 9. 特征快照与复现合同（冻结）

- 51D 特征由 HPC 上的 CKBW 特征管线一次性导出为单个 `.npz` 快照
  （X float32，N 行 × 51 列，附 uid/held_value 行标识），**不重新装配、不改管线**；
  导出脚本只读复用 ckbu 装配函数。
- 快照行数必须等于 `ckbw_record_predictions.csv.gz` 行数（297,326），
  并按 uid 逐一 join 角色标签；join 失败行数必须为 0，否则实验中止。
- 快照 SHA-256 写入 run_spec 与结果文档；本地训练只读该快照。
- 若 HPC 导出失败，允许在同一冻结超参下改为 HPC 上直接训练（HPC 已有
  torch 2.0.1），仅拉回结果 JSON/CSV；除此路径变更外不得改任何科学面内容。

## 10. 冻结确认

- 草案 §9 全部开口项已关闭：超参数已填入（§2.1）、验证集切分规则已定（§2.2
  含哈希兜底）、双工作点已定（§4）、Gate A 门槛已定（§5）。
- 本文件 FROZEN 后，下一步仅限：特征快照导出 → 本地训练 → 一次性评估 →
  结果文档。任何超出此范围的动作需要新预注册。
