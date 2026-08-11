# CKDA D0/D1 设计草案：预训练 Flow/Session 表征兼容性审计与冻结探针 Canary

日期：2026-08-11  
状态：**DRAFT — 仅授权方案评审；未冻结、未写实现、未提交 HPC、未触碰 FINAL**

本草案承接：

- CKCZ 正式裁决 `CKCZ_ORACLE_NO_INFORMATION` 及 Kimi 终审 PASS；
- `ckda_route_discussion_kimi_round1_20260811.md` 的四项加固；
- `ckda_route_discussion_kimi_round2_20260811.md` 的域内自监督候选与几何探针建议。

本草案只冻结前的讨论边界。任何 D0 数据读取、模型下载、PCAP 解码、embedding
生成、训练、HPC 提交或结果声明，均需后续 FROZEN 文档与用户逐步授权。

---

## 1. 已知事实与本轮问题

### 1.1 不重开的事实

1. 现有 51D 记录级学习器替换路线已封口；CKBY/DROCC 不能同时满足攻击召回与
   良性 OOD 误报约束。
2. CKCZ 已对冻结 C1/M7 冲突的四种 endpoint-pair persistence scalar 枚举
   87,730 个 oracle 点，0 点兼容；当前 `M7 OR conflict-persistence veto` 路线封口。
3. CKCZ 不构成“所有 episode/session 方法均不可能”的结论；失败的关键是只重组
   已有记录判断，没有获得足够的新增观测信息。
4. CKBQ 的 32-event MiniRocket 与既往 51D 时序尝试已覆盖“继续在同一有损摘要上
   叠窗口模型”的主要动机。该方向不占用 CKDA 主候选名额。

### 1.2 CKDA 唯一主问题

> 从原始 packet/flow/session 序列获得的冻结表示，是否在严格因果、无污染、
> fit/select/report 隔离下，为 unseen attack 与 unseen benign OOD 提供了现有 51D
> 和冻结分数之外的**可行动分离信号**？

本轮检验的是“新表示是否值得进入后续系统设计”，不是“某个大模型名字是否先进”，
也不是“换一个损失能否修好旧表示”。

---

## 2. 允许与禁止的路线形态

### 2.1 允许

- 从原始 PCAP 构造严格 past-and-current-only 的 session prefix；
- 冻结外部预训练编码器并提取 prefix embedding；
- 只在合法 fit/select 数据上训练域内自监督编码器；
- 对冻结 embedding 运行预声明的非参数几何、线性、小 MLP 三层探针；
- 只用与候选兼容性、覆盖、污染、因果性、复现性和工程成本有关的 D0 证据选择候选。

### 2.2 禁止

- 在 51D 序列上新增 LSTM/Transformer/MiniRocket 主候选；
- learned window classifier、family/source/mechanism 专家或专属阈值；
- 使用 CKCZ VIEWED frontier 数值选择 CKDA 模型、token、窗口、探针或阈值；
- 根据已见失败 family、样本或 FINAL 结果设计损失权重；
- 对 report/FINAL 做自监督预训练、词表拟合、归一化拟合、早停、超参选择或候选排序；
- 解码、散列内容、生成 embedding 或以任何方式打开 cooler-motor FINAL PCAP；
- seed 37/47 的任何模型使用；
- 在 D0/D1 结束前加入导师损失函数或其他多目标训练。

---

## 3. 数据角色与污染合同

### 3.1 角色原则

CKDA 必须继承现行 fit/select/report/FINAL 角色字典与 source/held-family 隔离，
不得因换到原始 PCAP 而重解释角色。

| 角色 | D0 | D1 embedding | 几何/探针拟合 | 选择/阈值 | 结果用途 |
|---|---:|---:|---:|---:|---|
| fit | 允许元数据审计 | 允许 | 允许 | 不单独拍板 | 训练/参考 |
| select | 允许元数据审计 | 允许 | 禁止监督训练；仅允许预注册选择 | 允许 | 选择 |
| report（非 FINAL） | 只允许白名单与覆盖审计 | 仅在全部选择冻结后一次生成 | 禁止 | 禁止 | 一次性 canary 裁决 |
| FINAL（cooler-motor、seed 37/47） | 仅验证排除断言 | **禁止解码/embedding** | 禁止 | 禁止 | 继续封存 |

“无标签”不等于“可训练”。对 report/FINAL 做 masked prediction、next-event prediction、
词表统计或归一化统计，仍属于 model usage，全部禁止。

### 3.2 域内自监督候选的污染边界

域内自监督候选不是自动“零污染”。只有同时满足以下条件，才可标记
`CONSTRUCTIVELY_HELD_OUT`：

1. tokenizer codebook、bucket edge、normalization、mask schedule 与 encoder 参数只从
   合法 fit 良性源产生；
2. held device/source、select、report 与 FINAL 不进入任何拟合统计；
3. source manifest、输入 SHA-256 与逐角色 packet/token 数完整记录；
4. 训练前已冻结 token 语义和 session/prefix 合同；
5. 不按已见攻击 family 构造伪异常或 hard negative。

否则只能标记具体风险，不得使用“零污染”措辞。

### 3.3 外部预训练语料审计

每个外部候选必须记录：官方论文/仓库/权重身份、预训练语料名称、采集时间、公开来源、
是否包含 IoT/ICS、是否可能包含 IoTSIM 或 ToN-IoT、作者是否披露去重，以及我们能否
独立排除重叠。

重叠风险分四级：

- `KNOWN_DISJOINT`：有可核验证据排除重叠；
- `NO_KNOWN_OVERLAP`：未发现重叠，但语料不足以证明互斥；
- `POSSIBLE_OVERLAP`：来源/时间/组成无法排除评测分布重叠；
- `CONFIRMED_OVERLAP`：确认包含评测数据或其直接派生物。

`CONFIRMED_OVERLAP` 直接淘汰；`POSSIBLE_OVERLAP` 不得成为主候选，只能作为污染敏感性
对照，且不得支撑泛化主张。

---

## 4. D0：四候选兼容性审计

### 4.1 候选集合

| ID | 候选 | 来源 | D0 身份 |
|---|---|---|---|
| E1 | ET-BERT 官方模型/权重 | 外部成熟组件 | 主候选 |
| E2 | YaTC 官方模型/权重 | 外部成熟组件 | 主候选 |
| E3 | netFound 官方模型/权重 | 外部成熟组件 | 主候选 |
| I1 | 域内小型自监督 session encoder | 本项目受控实现 | 候选兼受控基线 |

I1 与 E1–E3 接受同一硬门审计，但不因“领域匹配”自动优先。其成熟度、复现风险、
训练成本与超参自由度必须作为劣势如实计入。未经 D0 数据量与吞吐测量，不承诺“小时级”。

### 4.2 每候选必须填写的审计列

1. 官方论文、仓库、release/tag/commit、checkpoint URL 与 SHA-256；
2. 许可证是否允许研究复现、权重再分发和结果发表；
3. 预训练语料、污染风险等级与证据链接；
4. 原生输入单位：packet、flow、bidirectional flow 或 session；
5. 所需字段：payload、header、方向、长度、协议、timestamp/IAT、五元组等；
6. tokenizer/词表/bucket/normalization 是否需要目标数据拟合；
7. 是否支持严格 prefix 编码、最大长度、截断和 padding 语义；
8. 加密/无 payload/截断包/乱序/重复 timestamp 的处理；
9. 与现有 source/member/UID 的确定性 join 方案；
10. 非 FINAL 合法源覆盖率、不可编码原因和 ToN 20,000 metadata-miss 的处理；
11. 每 source/session/token 的预计数量、磁盘、RAM/VRAM、单卡/CPU 吞吐；
12. AMD/Intel/GPU 队列匹配度与预计 wall time；
13. 是否可离线固定依赖并生成可复核的输入/输出 hash；
14. 因果性合同是否可实现及其单测方案；
15. 代码成熟度、维护状态、最小适配量与自造组件比例。

### 4.3 D0 硬淘汰门

任一条件成立即淘汰该候选：

- 权重/代码不可合法获得或不可固定身份；
- `CONFIRMED_OVERLAP`；
- 必须使用 report/FINAL 拟合 tokenizer、词表或归一化；
- 无法产生严格 prefix 表征，或 prefix 只能通过先看完整 session 再裁剪得到；
- 无法将 embedding 确定性对齐到冻结 UID/target；
- 关键合法 attack/OOD 角色系统性不可编码且无统一、预声明的缺失状态；
- 资源需求超过现有可用队列且无可测的分块/checkpoint/resume 路径；
- 依赖无法在现有合规运行时中固定或验证。

### 4.4 D0 选择规则

D0 **不生成任何 attack/OOD 性能 embedding**，不得按可分性选模型。主候选按以下
词典序确定：

1. 通过全部硬门；
2. 污染风险更低；
3. 非 FINAL 合法角色覆盖更完整；
4. 原生支持严格因果 prefix；
5. 官方权重/代码/预处理更成熟、适配更少；
6. 实测资源与 wall time 更低；
7. 若仍并列，按候选 ID `E1 → E2 → E3 → I1` 固定顺序。

在成熟外部候选通过同等级合同的情况下，I1 不因域内语料而越级；I1 可作为预注册的
第二 canary/受控基线，但不得根据主候选 D1 的具体失败 family 临时修改目标。

D0 结束时必须冻结：一个 primary、至多一个 backup/control、确定的推进顺序，以及 D1
全部 token/session/probe 参数。若无候选通过，裁决为
`CKDA_D0_NO_COMPATIBLE_REPRESENTATION`，只封当前候选集合，不外推所有 flow model。

---

## 5. Session-prefix 与因果性合同

### 5.1 Prefix 定义

精确 session key（有向/无向五元组或候选原生定义）、source reset、timeout、最大 token
数、current-inclusive 语义、同 timestamp 排序键、截断方向与缺失字段编码，必须在 D0
结束时冻结。不得按 D1 可分性修改。

每个 target embedding 只能由同 source、同 session、排序不晚于当前 target 的 packet/token
产生。任何全局 session 汇总、未来 completion、完整流长度或双向结束状态不得泄漏到当前前缀。

### 5.2 D1 必过合同测试

1. **future mutation invariance**：新增、删除、修改当前 cut 之后的 packet，当前 prefix token
   与 embedding 不变；
2. **future-label invariance**：任何 label/family 字段不可进入 tokenizer/encoder/state；
3. **source reset isolation**：改变其他 source 的历史不改变当前 embedding；
4. **exact-cut/current-inclusive**：当前 packet 是否纳入与冻结合同逐例一致；
5. **equal-time ordering**：相同 timestamp 依靠冻结稳定键排序，不使用文件系统偶然顺序；
6. **prefix-vs-full trap**：禁止先编码完整 session 再切取隐藏状态；
7. **join completeness**：逐角色报告 target、embedded、missing、duplicate；
8. **deterministic replay**：同环境同输入重复生成的 UID 顺序、shape 与内容 hash 一致；
9. **FINAL exclusion**：运行时 source allowlist 与 denylist 双断言；命中即工程失败且无科学裁决。

浮点 embedding 若因官方 GPU kernel 无法逐位确定，D0 必须冻结确定性开关、容差与 hash
替代证据；不得在测试失败后放宽容差。

---

## 6. D1：冻结表示 Canary

### 6.1 原则

- encoder 在 D1 全程冻结；I1 的自监督训练必须在 embedding/report 打开前完成并钉死；
- 候选顺序、embedding 层、pooling、标准化、距离、k、探针结构、优化器、epoch、早停与
  阈值规则全部在见到任何 D1 embedding 性能前冻结；
- family/source 只用于分层报告和 bootstrap，不进入特征、权重或专家路由；
- report 只允许在 fit/select 选择全部完成后一次开启。

### 6.2 三层探针

#### G0：非参数几何探针

- 正常参考中心/协方差距离；
- 固定 k 的 kNN 距离或一致性；
- 距离、归一化、k 与参考角色必须在 D0 冻结。

G0 不做梯度训练，但会从参考数据构造状态，因此准确名称是“非参数几何探针”，不是
“零训练”或“无拟合”。若使用 attack label 构造类中心，其用途只限监督几何诊断，必须与
benign-only 异常分分开报告。

#### P1：线性探针

- 一个冻结输入上的线性/logistic head；
- 固定 family-balanced 或 class-balanced 规则；
- 只用合法 fit 训练、select 选择；
- 不搜索 embedding layer、feature subset 或 family weight。

#### P2：小 MLP 探针

- 固定单隐藏层结构与容量上限；
- 与 P1 使用相同数据角色、输出和阈值合同；
- 只用于检查有限非线性可读性，不升级为任意深度 classifier search。

P2 若失败，不得临时增加层数、注意力、序列头或 family loss。

### 6.3 必报指标

记录级与 session/episode 级口径必须并列，禁止用指标换算掩盖损失：

- future/report attack recall；
- 每 attack family recall 与相对冻结基线 delta；
- 四池 benign OOD hard rate 与 macro；
- support coverage；
- session detection rate、false-alert sessions per source、time-to-first-alert；
- source/session bootstrap CI；
- 按角色的 target/embedding/missing 数；
- 与 C1、FrozenCKBQ、M7 的同分母对照；
- 三层探针的 fit/select/report 使用审计。

16 个原始 attack family 与既有 12 族等权主门的映射必须在 FROZEN 前引用唯一字典并逐项
列出；未澄清前不得生成“macro family”裁决。

### 6.4 裁决状态与非对称性

D1 不使用 `NO_INFORMATION`。有限探针失败不能证明任意解码器下无信息。

1. `CKDA_D1_STRONG_GEOMETRIC_SIGNAL`：G0 在冻结门下形成可用双约束点；只授权继续验证，
   不等于系统 PASS。
2. `CKDA_D1_ACTIONABLE_PROBE_SIGNAL`：P1 或 P2 在一次性 report 上同时满足冻结 attack-safe、
   worst-family、support、OOD 门，并通过全部工程/因果/覆盖门；授权起草 D2，不授权 FINAL。
3. `CKDA_D1_WEAK_ONLY`：只在无部署门的排名指标或单一维度改善，或 G0/P1/P2 结论冲突；
   不进入 D2，最多授权一次预注册的解释性审计。
4. `CKDA_D1_NO_ACTIONABLE_SIGNAL_UNDER_FROZEN_PROBES`：G0、P1、P2 均无兼容点；封口当前
   candidate + tokenizer + prefix + probe set，不外推该 embedding 的全部信息，也不外推
   所有预训练 flow/session 表示。
5. `CKDA_D1_ENGINEERING_FAILURE`：覆盖、join、因果、污染、运行或验证失败；无科学裁决。

“有信号”与“无信号”判定不对称：任一预声明探针通过可证明存在可读的行动信号；全部探针
失败只能证明当前有限读取合同下没有行动信号。

### 6.5 Backup/control 推进

只有 primary 得到第 4 或第 5 类状态，且 D0 已预先冻结 backup/control，才可按固定顺序
推进下一候选。不得比较多个 report 结果后选最好者；每个 report opening 都必须独立记录，
并纳入多重尝试披露。

---

## 7. 导师损失函数与 D2 边界

导师提出的结构化对比/targeted latent loss 具有条件价值，但不属于 D0/D1：

1. D1 先回答新表示是否包含可读信息；
2. 只有 `CKDA_D1_ACTIONABLE_PROBE_SIGNAL` 才授权起草 D2；
3. D2 只能做单变量 `plain CE/reference objective` 对 `one frozen generic loss`；
4. 禁止按 CKAA/CKBW/CKCZ 已见失败 family 或 report 样本定向加权；
5. 损失必须统一作用于合法训练角色，并保留同一 probe/head、数据、阈值与资源合同；
6. I1 的 masked/next-event 自监督目标属于表示获取，不等于 D2 的监督 tail loss，二者必须
   分开命名和消融。

D1 失败时不得以“也许换 loss 能读出来”为理由直接进入 D2。

---

## 8. D0/D1 产出与提交纪律

### D0 产出

- 四候选兼容性与污染审计表；
- source/member/role/FINAL 排除清单及 SHA-256；
- PCAP/token/session/target 数量与资源估算；
- primary + backup/control 固定顺序；
- D1 tokenizer、prefix、embedding、G0/P1/P2 全参数冻结稿；
- 只读审计脚本、合同测试与审查报告。

### D1 产出

- 冻结 embedding manifest 与 hashes；
- 合同测试与因果变异测试报告；
- G0/P1/P2 fit/select/report 审计；
- 同分母指标、bootstrap、裁决 JSON；
- 工程失败时只写 failure verdict，不生成科学结论。

每一步继续执行：文档 → 独立审查 → commit → push → 用户授权。HPC 命令必须是完整
结果产出链，禁止用 standalone synthetic/audit job 代替正式 canary。正式提交前仍需本地
真实输入小规模彩排、bundle 审查和用户单独授权。

---

## 9. 本轮请求 Kimi 审查的开口项

1. 是否接受将 I1 定位为“同门审计的候选兼受控基线”，但成熟外部候选通过同等级合同时
   不允许 I1 自动越级？
2. 是否接受把 kNN/类中心改称“非参数几何探针”，并明确其参考状态仍属于拟合？
3. 是否接受用 `NO_ACTIONABLE_SIGNAL_UNDER_FROZEN_PROBES` 替代 `NO_INFORMATION`？
4. D0 词典序与固定 backup 推进能否充分防止多候选 report cherry-picking？
5. D1 的五态裁决是否需要合并或增加明确的 `GO_D2` 单一机器标记？
6. 16 family 与既有 12 族主门的唯一映射应引用哪份冻结字典？
7. I1 的合法 fit 良性 token/session 数量达到何种预声明下限才允许训练，应由 D0 统计后
   冻结，还是现在先给保守绝对门？

在上述开口项关闭前，本草案不得转 FROZEN，不写代码、不下载模型、不解码 PCAP、不提交 HPC。
