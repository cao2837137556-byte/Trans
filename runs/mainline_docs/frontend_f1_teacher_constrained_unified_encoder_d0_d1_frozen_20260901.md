# Frontend-F1 教师约束统一语义编码器 D0/D1 协议（FROZEN）

- 日期：2026-09-01
- 状态：`FROZEN`
- DRAFT 基线：`abe355c`
- 独立审查：`77e8a21`（ACCEPT + S1-S4）
- 路线：Frontend-F1（新谱系，不修改 CE FROZEN）
- 目标：先证明新语义编码器继承在役攻击能力，再判断其能否安全补齐旧前端盲区

## 0. 结论先行

本协议把“能力继承”操作化为一个可证伪问题：

> 在冻结 H1-H4 因果语义、冻结旧 E3/P2、排除所有跨 phase 上下文后，
> 一个统一训练的语义编码器能否在 A（旧 finite）上重现冻结攻击通道的
> 功能性判决，同时在 B（旧 missing）上产生可用表示和真实的良性收益？

第一阶段采用**统一训练、扩展部署**：

```text
训练：A + B 合法 fit 上下文
      -> 单一新编码器
      -> 768D 接口（可含一个冻结身份的轻量 adapter）
      -> 冻结 old normalizer + 冻结 P2

部署候选：
  A / old_missing=false -> 冻结旧 E3/P2，逐 target 原样复制
  B / old_missing=true  -> 新编码器 + 冻结 old normalizer/P2
```

因此，A 的在役能力由路由结构保护；新编码器仍必须在 A 上进行 shadow
继承考试。若 shadow 失败，最多只能形成 B 侧实验分支，不得声称“统一能力继承”。

本阶段不以 hydraulic 改善作为验收门。hydraulic 属于 A 的 finite-but-wrong
问题，在扩展部署下按构造不变；它继续作为后续 full-replacement/表征质量路线的
显式未解决目标，不得从项目目标中删除。

## 1. 已确立证据

### 1.1 冻结语义入口

ZT-2 已证明：

| 项目 | 冻结事实 |
|---|---:|
| 全部 target | 25,467 |
| A：旧 finite | 13,827 |
| B：旧 missing | 11,640 |
| H1 / H2 / H3 / H4 | 13,953 / 1,909 / 9,579 / 26 |
| 新语义 finite | 25,467 / 25,467 |
| 旧 finite 保留 | 13,827 / 13,827 |
| 旧 missing 恢复 | 11,640 / 11,640 |

这个 PASS 只证明语义上下文可构造，不是表示或检测性能结果。

### 1.2 CE 在役保护

CE 已冻结以下事实和规则：

- A 继续走冻结 E3/P2，score bytes、阈值身份和 hard verdict 逐 target 不变；
- B 才由 challenger 拥有；
- old-missing benign-select 合法分母为 4,812；
- 4,812 行 incumbent score 均由 fail-closed 约定钉在阈值并判 hard；
- material-gain 字面门为 482 行，且至少 3 个良性设备严格改善；
- 23 条 old-missing `support_val` 攻击只作 kill-only 安全哨兵；
- 任何普通 CE 失败都不得自动打开 full replacement。

### 1.3 blind-spot-only 路线的停止原因

同一冻结上下文跨 fit/select 时必须整 context 排除。现有冻结普查值为：

| 项目 | 冻结值 |
|---|---:|
| 全部独立语义上下文 | 18,187 |
| 合法 fit 行 / context（排除后） | 18,266 / 12,889 |
| select 行 / context | 7,069 / 5,298 |
| 跨 phase context | 19 |
| 跨界 fit / select 行 | 132 / 32 |
| B 良性合法 fit context | 5,178 |
| B 良性 select context | 4,157 |
| B 合法 fit attack context | 29 |

冻结口径还必须逐字满足以下四条守恒式：

```text
18,266 + 132 = 18,398
18,398 + 7,069 = 25,467
12,889 + 5,298 = 18,187
40 - 11 = 29
```

其中 19 个跨 phase context 整体归入 select 列，只出现一次，不得同时计入 fit
context；对应的 32 条跨界 select 行已经包含在 7,069 条 select 全量中。任一等式
不成立，直接终止为 `F1_D0_NO_IDENTIFIABLE_UNIFIED_FIT_DENOMINATOR`。

`29 < 30` 只终止“B 单独训练并独立证明攻击信息”路线。Frontend-F1 改为
A+B 统一训练，以 A 的合法攻击知识提供教师约束；它不得修改或降低原 30-context
门，也不得把 29 个 B 攻击 context 包装成逐族能力证据。

### 1.4 攻击与 viewed 边界

- 冻结 fit 攻击全集锚点为 4,385 行；D0 必须在 19-context 整体排除后重新报告
  实际可训练行/context，不能假定 4,385 全部仍可训练；
- 69 条 `support_val` 攻击只允许在候选、损失、阈值、门和 checkpoint 全部冻结后
  做一次 kill-only 检查；
- 已查看的 51,057 report 攻击只能枪毙已冻结候选，不能加分、选模型、改 loss、
  改 margin、改 adapter 或触发重跑；
- FINAL、cooler-motor 和任何未授权 report 继续封存。

## 2. 非目标与禁止项

本协议不允许：

1. 修改 H1-H4 上下文、endpoint token、时间回退或 causal cutoff；
2. 修改冻结 E3、P2、old normalizer、old threshold 或 CE 路由；
3. 为设备、source、协议、攻击族建立专属模型、权重、阈值或 parser；
4. 在训练前或训练中读取 select/viewed/report/FINAL 结果；
5. 将普通 score regression 当作教师蒸馏；
6. 在一个 run 内同时尝试 GRU、Transformer、MLP 等模型动物园；
7. 因 frozen P2 不兼容而自动训练第二个 head；
8. 把 A shadow 改善当成部署变化，或把 B 小样本结果夸成逐族攻击能力；
9. 宣称本阶段解决 hydraulic；
10. 使用 localwin checkpoint 作为未来 HPC 正式重放的论文级工件。

## 3. D0：count-only 训练池与资源普查

D0 不打开 representation、score、probe state、checkpoint 或 PCAP。它只读冻结
manifest、ZT target/context status、role/phase/label/family/source/device 元数据和
身份侧车。

### 3.1 身份门

D0 必须钉死并输出 SHA-256：

1. challenger requirements FROZEN；
2. CE FROZEN；
3. H1-H4 zero-training semantics FROZEN；
4. ZT-2 真实覆盖 verdict 与 25,467-row status；
5. CE learned blind-spot D0/D1 FROZEN；
6. 19 个跨 phase context 的排除清单；
7. 冻结 target/role/source/family/device manifest；
8. old E3/P2、normalizer、threshold marker 和 incumbent verdict 身份；
9. 本协议及未来 numerical addendum。

任一字节身份缺失或漂移，终态为 `F1_D0_IDENTITY_OR_SCOPE_FAILURE`，不得继续。

### 3.2 上下文守恒与整 context 排除

独立单位继续使用：

```text
semantic_context_key = (member_id, causal_context_id, context_epoch)
```

只要一个 context 含任意 select 行，该 context 全部退出 encoder fitting、内部验证、
词典/变换拟合和 loss 统计。不得拆行、重定义 key 或通过较早 target 回收。

D0 必须先精确复现 §1.3 的全部冻结值，再报告下列表格：

- A/B × fit/select × benign/attack 的 row/context 数；
- H1-H4 × A/B × fit/select × benign/attack；
- fit 攻击按 exact family/source/device/context 的排除前、跨界、排除后计数；
- B 良性 fit/select 按设备与协议层级的 context 数；
- 每 context target 数、event 数和 causal-context 长度分布；
- 19 个跨界 context 的完整 UID 守恒表。

任何守恒失败或一个 context 进入多个模型开发 split，终态为
`F1_D0_NO_IDENTIFIABLE_UNIFIED_FIT_DENOMINATOR`。

### 3.3 教师覆盖普查

教师信号只存在于 A。D0 必须 count-only 报告：

- A 合法 fit context 中具有 old finite embedding/score/verdict 的比例；
- A 合法 fit 的真攻击 hard、真良性 hard、真良性 normal 三类分母；
- 旧 P2 在合法 fit 攻击上的 hard 覆盖分母；
- B 不得伪造 teacher embedding 或 teacher score；
- missing 钉分行不得被当成学习到的教师行为。

教师覆盖不完整不得用 score pinning、零填充或最近邻教师补齐。

### 3.4 单一候选与资源门

D0 只允许一次窄兼容性选择，不看任何真实表示或结果。候选必须：

- 直接消费冻结 H1-H4 事件序列；
- target 位置因果、最长上下文 256、member/context 状态隔离；
- 原生输出 768D，或使用一个计入候选身份的轻量 768D adapter；
- 可被冻结 old normalizer/P2 调用；
- 支持 endpoint-identifier masked arm；
- Python 3.9 兼容；
- 具有 member/context checkpoint 和断点恢复；
- 本地资源预算内可完成一次训练，不依赖联网。

若多个候选同时满足上述机械条件，冻结的唯一选择次序为：

1. 有维护上游且 Python 3.9 兼容者优先；
2. 参数量小者优先；
3. 仍并列时按仓库/组件名称字典序选择。

选择过程只能使用本节兼容性与资源字段，禁止使用任何真实 representation、score、
label-derived performance 或 select/viewed 结果。D0 必须保存完整候选清单、逐项判定、
淘汰原因和最终词典序选择记录。

优先成熟、维护良好的实现；若成熟组件不能消费冻结语义，禁止反向修改 H1-H4
迁就它。自研范围只允许窄 adapter、输入封装、loss 和合同执行器。

D0 只能在 synthetic shapes 上测量单 step 时间、峰值内存、checkpoint 字节和推算
wall time，不得用真实 embedding/label 试跑候选。输出必须给出硬上限：

- 参数量；
- 每 batch 最大 event/target/context 数；
- 峰值 RAM/VRAM；
- checkpoint 间隔与最大重算窗口；
- 单次训练总 wall-time 上限；
- 仅一次训练、零超参 sweep。

训练 wall-time 上限机械冻结为：

```text
wall_time_cap = min(3 * synthetic 外推值, 168 墙钟小时)
```

synthetic 外推值、乘数、168 小时绝对上限和最终 cap 必须进入 numerical addendum，
经独立审查冻结后才可训练。若外推 cap 超过 168 小时，或执行计划无法保证在 cap
内完成，直接终止为 `F1_D0_RESOURCE_OR_CANDIDATE_NO_GO`；D0 后不得因硬件、
队列或运行结果上调。

无法形成单一候选或超出资源门，终态为 `F1_D0_RESOURCE_OR_CANDIDATE_NO_GO`。

### 3.5 D0 输出与授权边界

D0 PASS 需要：

```text
F1_D0_CENSUS_PASS
```

它只授权生成 numerical addendum 和 D1 实现草案，不授权真实训练。

## 4. D1：教师约束统一编码器

### 4.1 训练输入

只使用 D0 排除后、合法 `phase=fit` context：

- A+B 全部合法 fit context 可进入无标签表示目标；
- 只有合法 fit 标签可进入 label-aware 约束；
- select context 完全不可见；
- 一个 context 的全部 target 归同一内部 split；
- 内部验证按 source/member/context 分组，禁止 target-row 随机切分。

### 4.2 单一模型结构

候选由 D0 唯一钉死，至少包含：

```text
冻结 H1-H4 event sequence
-> 单一 causal sequence encoder
-> 768D representation
-> 可选但身份冻结的轻量 adapter
-> 冻结 old normalizer
-> 冻结 P2
```

P2、normalizer 和 threshold 不更新。adapter 若存在，属于 encoder 参数，必须与 encoder
一同训练、哈希和 checkpoint；不得按设备/族切换。

“逐坐标克隆 old E3”不是硬前提。硬前提是功能接口兼容和攻击能力继承。

### 4.3 label-aware 教师约束

普通全量 score MSE/KL 被禁止，因为会蒸馏教师误报。训练目标必须分三类：

1. **真攻击 fit**：新 P2 margin 必须保持 hard，并受到 tail/margin hinge 保护；
2. **真良性 fit、old P2 normal**：允许功能性教师保持，防止无故制造新误报；
3. **真良性 fit、old P2 hard**：明确不蒸馏 old hard；允许并鼓励其 margin 软化。

B 的 teacher score 不存在。B 只通过冻结语义、自监督目标和合法 fit 标签参与；
missing score pinning 不得进入 loss。

总 loss 只能由以下预声明项构成：

```text
L = L_semantic
  + lambda_sup * L_label_fit
  + lambda_attack * L_attack_margin
  + lambda_correct_teacher * L_correct_teacher_margin
```

- `L_semantic`：一个预声明的因果自监督目标；
- `L_label_fit`：全局二分类目标，不设 family/device/source 权重；
- `L_attack_margin`：仅合法 fit 真攻击；
- `L_correct_teacher_margin`：只作用于教师与 fit 真值一致的 A 行；
- old-hard 真良性不进入 teacher-hard 保持项。

模型结构、四项 loss 的字面定义、所有 lambda、margin、optimizer、epoch、batch、seed、
early-stop 与 checkpoint 规则必须在任何真实 representation/score 打开前写入 numerical
FROZEN addendum。不得依据真实结果修改。

### 4.4 endpoint shortcut 控制

同一模型必须有冻结的 endpoint-identifier masked arm：

- raw IP/MAC/端点字面标识被掩码；
- H1-H4 context partition、事件顺序和协议语义不变；
- masked arm 独立通过 availability、attack-information 和 A shadow 继承门；
- masked arm 失败可枪毙候选，不能触发另一个 encoder。

### 4.5 Stage 1：冻结 P2 接口继承考试

候选、loss、checkpoint、normalizer/P2/threshold 全冻结后，先在合法 fit/internal-val
上完成训练，再一次性打开 select shadow。

#### A：能力继承 shadow 门

A 的正式部署输出仍来自旧 E3/P2；以下只评价新编码器是否继承能力：

1. 所有 incumbent-hard select 攻击在新 shadow 路径仍为 hard；
2. 69/69 `support_val` 攻击在新 shadow 路径仍为 hard；
   D1 报告必须逐字记录全部 incumbent-hard select 攻击的字面分母、UID 守恒和
   零翻转计数；`hard` 继续使用 incumbent 的 `score >= threshold` 语义；
3. exact-family/worst-source 表必须完整报告，不以 macro 遮蔽；
4. 新 shadow 不得把任何 old-normal select 攻击变成宣传性正结果；
5. A fit 攻击 margin 保持只作训练诊断，不作独立正证据；
6. A 良性 hard 可软化，但不构成当前部署收益声明；
7. endpoint-masked arm 必须独立通过相同攻击继承门。

候选完全冻结后，51,057 viewed report 攻击可在另行授权下执行一次 kill-only：
任一 incumbent-hard 攻击在新 shadow 路径翻成 normal，即终态
`F1_NO_ATTACK_CAPABILITY_INHERITANCE`；零翻转也只是不否决，不能晋升候选。

#### B：blind-spot 表示与 CE utility 门

下列四门的语义不得在 D1 实现时重新解释，其规范性来源钉死为：

| 门 | 规范性定义 | 冻结 SHA-256 |
|---|---|---|
| availability | `runs/mainline_docs/frontend_f0_challenger_requirements_frozen_20260830.md` §5 Stage 1；`runs/mainline_docs/frontend_f0_ce_learned_blindspot_branch_d0_d1_frozen_20260901.md` §11.1；CE missing 子集补充见 `runs/mainline_docs/frontend_f0_coverage_extension_protocol_frozen_20260831.md` §6 | `b46caf0d308531f512ffedd3a9dea8d1438c22a8d136f7c1965dff8ea3f411b0`；`016d61a9d776f6ba6e0218ce1b753e3bf403fa3dab303630b2809beb6f6e5eea`；`0b102b7929e2a1ad2e269e35a5a225880a97d34bcc036d586b7066bcc5cddcfe` |
| collapse | `runs/mainline_docs/frontend_f0_ce_learned_blindspot_branch_d0_d1_frozen_20260901.md` §11.2 | `016d61a9d776f6ba6e0218ce1b753e3bf403fa3dab303630b2809beb6f6e5eea` |
| device/endpoint leakage | `runs/mainline_docs/frontend_f0_ce_learned_blindspot_branch_d0_d1_frozen_20260901.md` §11.3 | `016d61a9d776f6ba6e0218ce1b753e3bf403fa3dab303630b2809beb6f6e5eea` |
| attack-information | `runs/mainline_docs/frontend_f0_ce_learned_blindspot_branch_d0_d1_frozen_20260901.md` §11.4 | `016d61a9d776f6ba6e0218ce1b753e3bf403fa3dab303630b2809beb6f6e5eea` |

B 必须先通过 inherited full-universe/CE availability、collapse、device/endpoint leakage
和 attack-information 门，然后按 CE 原分母评价：

- 11,640/11,640 状态行齐全且 UID 唯一；
- missing-subset overall finite >=0.90；
- 每良性设备 finite >=0.80；
- 每个声明内 missing attack family finite >=0.80；
- 23/23 old-missing `support_val` 攻击 hard（kill-only）；
- 每个 B 良性设备 hard 数不比 incumbent baseline 更高；
- 至少 3 个 B 良性设备严格改善；
- 4,812 old-missing benign-select 至少减少 482 个 hard；
- 162 missing attack 行按 role/family/source/context 原样报告，小样本警示不可删除。

### 4.6 “继承成功”的字面含义

只有 A shadow 攻击继承门与 B CE utility 门同时通过，才能得到：

```text
F1_DEVELOPMENT_INHERITANCE_AND_EXTENSION_PASS
```

该状态只支持：

> 新语义编码器在开发数据上继承了冻结攻击通道的可观测功能，并对旧 missing
> 良性子集产生了机械定义的收益；正式部署候选仍保持 A 旧路、B 新路。

它不支持 full replacement、hydraulic 改善、逐族 B 攻击能力或 FINAL 结论。

### 4.7 第二阶段新 head 的唯一合法入口

本协议不训练第二个 head。只有以下合取成立才允许起草一次性新-head addendum：

1. encoder availability、collapse、shortcut 和 attack-information 均 PASS；
2. A shadow 表示中攻击信息可由冻结非参数/线性 canary 复现；
3. frozen P2 接口门失败的原因被具名为坐标/接口不兼容，而不是信息缺失；
4. B CE utility 不能仅因 frozen P2 无法消费表示而计算；
5. 没有打开 viewed/report/FINAL 来选择该分支。

满足时只产生：

```text
F1_P2_INTERFACE_NO_GO_BUT_REPRESENTATION_PASS
```

它仅授权起草一个全局新 head 协议。新 head 最多一次训练，仍受 label-aware
攻击保护、全部 viewed kill-only 门和无 family/device patch 约束。

## 5. 结果分支与路线后果

| 结果 | 字面终态 | 后果 |
|---|---|---|
| A shadow 继承 + B material gain | `F1_DEVELOPMENT_INHERITANCE_AND_EXTENSION_PASS` | 可起草一次性确认；A 仍旧路、B 新路 |
| B gain，但 A shadow 失败 | `F1_NO_ATTACK_CAPABILITY_INHERITANCE` | 不得声称统一继承；候选整体 NO-GO |
| A shadow 通过，但 B 无 material gain | `F1_NO_MATERIAL_BLINDSPOT_GAIN` | 新表示无系统增量，候选 NO-GO |
| 表示有信息但 frozen P2 不兼容 | `F1_P2_INTERFACE_NO_GO_BUT_REPRESENTATION_PASS` | 只允许起草一次新-head addendum |
| availability/collapse/shortcut/attack canary 失败 | `F1_REPRESENTATION_NO_GO` | 立即封口，不换第二 encoder |
| 身份/泄漏/边界失败 | `F1_ENGINEERING_OR_PROTOCOL_FAILURE` | 无科学判决，修复须独立审查 |

只有后续 CE one-shot 证明“B 安全改善，但整体 OOD 目标仍由 A finite 错误主导”，
才可触发 full-replacement **讨论**。hydraulic 必须在该后续协议中作为单独行恢复，
不能被 macro 隐藏。

## 6. 最低合同测试

实现前至少证明：

1. 25,467 UID 一一对应，A=13,827、B=11,640；
2. 19 个跨 phase context 整体排除，不能拆行回收；
3. 改 label/score/device/source/family 不能改变 CE owner；
4. A 正式输出逐 target 复制 incumbent score bytes 与 verdict；
5. A 正式路径从不调用新 encoder；
6. A shadow 与正式 A 输出物理隔离；
7. B 从不读取伪造 teacher embedding/score；
8. missing score pinning不能进入 teacher loss；
9. 真攻击 hard 约束和真良性 hard 可软化语义可由合成例区分；
10. select context/label 不进入训练、loss、early-stop 或 checkpoint selection；
11. viewed/report/FINAL 不得打开候选选择路径；
12. 一个 context 只能属于一个内部 split；
13. future packet mutation 不改变历史 target representation；
14. endpoint-masked arm 保持同一 context partition；
15. frozen P2/normalizer/threshold 参数和哈希运行前后不变；
16. adapter 若存在，身份与 encoder checkpoint 一同钉死；
17. 4,812/482/23/69 分母与门值精确；
18. 每设备 benign regression 可单独枪毙 macro improvement；
19. 51,057 viewed 攻击只能 kill、不能更新候选；
20. frozen P2 失败不能自动训练新 head；
21. 一个 run 不能激活第二 encoder 或 family patch；
22. Python 3.9 语法、运行时 API、原子写、SHA readback 全 PASS；
23. checkpoint resume 与 uninterrupted run 在合成数据上逐字节等价；
24. 工程失败删除科学 verdict；
25. report/FINAL/cooler-motor 打开计数始终为 0。

## 7. Durable outputs

### D0

1. input identity manifest；
2. 25,467-row UID/context/phase/owner conservation；
3. A/B × phase/role/label/tier/source/device/family census；
4. 19-context 排除清单与守恒表；
5. teacher coverage census；
6. B 良性设备/协议覆盖表；
7. single-candidate compatibility and frozen tie-break record（候选清单、逐项判定、淘汰原因、最终选择）；
8. synthetic-only resource pilot；
9. literal D0 verdict；
10. `SHA256SUMS`。

### D1

1. frozen numerical addendum and all identities；
2. context-grouped fit/internal-val manifest；
3. encoder/adapter checkpoints and resume ledger；
4. frozen P2/normalizer immutability audit；
5. label-aware loss ledger by term and role；
6. full-universe representation status；
7. A shadow inheritance tables by target/source/family；
8. B availability and CE utility tables by device/family/context；
9. endpoint-masked arm outputs；
10. sparse B attack disclaimer table；
11. open/boundary ledger；
12. literal verdict JSON；
13. `SHA256SUMS`。

## 8. 论文声明边界

即使开发 PASS，也只允许声明：

- 语义入口覆盖 25,467/25,467；
- 新编码器在开发 shadow 中保留了冻结攻击通道的可观测功能；
- CE 对旧 missing 良性子集出现了预定义、逐设备无退化的开发收益；
- B 攻击证据最多来自 29 个独立 fit context、5 个族，属于有限哨兵证据。

不得声明：

- full replacement 已安全；
- hydraulic 已解决；
- 新设备 commissioning 已解决；
- 未见工业域广义泛化；
- B 每个攻击族达到论文级召回；
- 本地结果替代正式 HPC/一次性确认。

## 9. 独立审查裁定（规范性）

1. 4,385 只作排除前 fit 攻击锚点；19-context 整体排除后的实际 row/context
   是唯一训练分母，并须满足 §1.3 的四条守恒式。
2. §4.3 四项 label-aware loss 结构获准进入 numerical addendum；old-hard 真良性
   继续明确排除于 teacher-hard 保持项。
3. A shadow 采用 target-level **零翻转**硬门，不设容差；D1 必须逐字报告
   incumbent-hard select 攻击的字面分母。
4. §4.7 五项新-head 入口获准；未来 addendum 仍须完整走
   DRAFT→独立审查→FROZEN，当前协议不授权实现或训练新 head。
5. 51,057 viewed attack kill-only 固定在候选完全冻结后、CE one-shot 前执行；
   只能产生“不否决”或 `F1_NO_ATTACK_CAPABILITY_INHERITANCE`。
6. hydraulic 移出第一阶段验收但保留为未来 full-replacement 单独必报行；
   不得被 macro 吸收。
7. D0 单一候选并列按 §3.4 的维护上游→参数量→字典序机械选择。

## 10. 当前授权边界

本 FROZEN 已机械落实独立审查 `77e8a21` 的 S1-S4 与全部开放项裁定，
科学规则自此不可变。

它仍不授权：

- 实现或执行 D0/D1；
- 打开真实 representation、score、probe state 或 checkpoint；
- PCAP 解码；
- 训练、threshold 选择、新 head；
- viewed/report/FINAL/cooler-motor；
- 网络检索、下载或 HPC 提交；
- 修改 CE、ZT、旧 E3/P2 或在役报警流。

合法下一步为：

```text
独立 SHA/diff 冻结终审
-> 用户另行授权 D0 实现/执行
-> D0 结果审查与 numerical addendum
-> 用户另行授权 D1 实现/训练
```
