# CKBW：共享过程评分器的 Tail-Pair Margin 与双边控制预注册（FROZEN）

> 状态：**FROZEN SCIENTIFIC PROTOCOL — AWAITING KIMI FINAL REVIEW AND USER IMPLEMENTATION AUTHORIZATION**
>
> 冻结日期：**2026-08-03**。本文内容由独立 SHA-256 锁定；Kimi 对该精确版本终审且用户明确授权前，不得据此写正式模型代码、构建 HPC bundle 或提交作业。任何内容变更必须生成新的版本文件与 SHA-256，不得静默改写本文件。

## 1. 本轮要回答的问题

CKBV seed 27 已证明统一 51D 因果过程前端能够提供跨 source 的攻击与正常过程信号，但原主候选采用：

```text
Frozen CKBQ hard OR TabM process attack evidence
```

OR 规则只能新增 hard，不能撤销 Frozen CKBQ 的 hard，因此从数学上不可能把良性 OOD hard false-alarm 降到 Frozen CKBQ 以下。与此同时，CKBV 的 TabM 头使整体攻击 hard recall 提升 7.42 percentage points（pp），却使 Merlin C&C Communication 相对 C1 下降 9.27 pp；同一前端下 ExtraTrees 对照只下降约 1.23 pp，说明主要问题位于过程评分头的尾部决策边界，而不是 51D 前端整体不可用。

CKBW 的唯一研究问题是：

> 在不增加 family 专家、不读取 held 标签、不引入 review 的前提下，能否用一个共享 51D 过程评分器，同时学习可迁移的攻击证据和强正常证据，从而保护攻击 hard recall，并进一步降低未见良性环境的 hard false-alarm？

正式创新候选为：

```text
统一 51D 因果过程前端
        ↓
共享 TabM 过程评分器
        ↓
family-balanced tail-pair margin
        ↓
一个攻击阈值 + 一个强正常阈值
        ↓
对 Frozen CKBQ 做双边、保守控制
```

这不是为 Merlin、UDP Scan、stream 或其他单个 family 增加补丁。所有攻击 family 共用一个评分器、同一损失、同一组阈值和同一决策规则。

## 2. 冻结输入与不可修改边界

### 2.1 复用资产

CKBW 必须复用 CKBV AMD job 154917 的已验证资产：

- 51D source-local、past-only 因果过程缓存；
- Gotham、auxiliary 和 ToN-IoT 输入与对齐结果；
- `raw51_observable_v1` eligibility mask；
- 冻结 CKBQ hard 决策；
- 原严格 1M 数据角色与 target；
- CKBV 的 C1、Frozen CKBQ、ExtraTrees-OR、TabM-OR 结果作为冻结对照。

不得重新解码 PCAP，不得修改原 manifest、target、role、mask、C1、Frozen CKBQ、review 或 held 定义。

### 2.2 51D 前端合同

过程特征必须继续满足：

- TShark 4.6.6 解析；
- source-local 匿名状态；
- 每个 source fresh reset；
- 当前事件先构造/评分，再更新状态；
- 只使用在当前决策时刻已经可用的字段；
- past-only；
- 不使用 source 身份、文件名、数据集名或 attack family 名作为特征；
- 不读取 raw label 更新状态；
- report 阶段 `torch.no_grad()`；
- report 阶段不更新模型、标准化、阈值或任何训练统计。

`raw51_observable_v1` 的冻结事实：

| 项目 | 数值 |
|---|---:|
| frozen target | 325,067 |
| observable target | 323,714 |
| masked target | 1,353 |
| 唯一 masked source | `iotsim-hydraulic-system-1` |
| mask SHA-256 | `b16017d2755feaedbe6d3ad76fd7d1e2444cf66a14a70f6bca35f270734ad2df` |

任何没有合法 51D 表示的记录必须 fail-closed 回退到 Frozen CKBQ 原决策；不得对该记录进行 rescue 或 suppress。

## 3. 冻结数据角色

### 3.1 Fit

| 类型 | 来源 | 行数 | 用途 |
|---|---|---:|---|
| benign core `id_calib` | combined-cycle-tls-3/4/5 | 809 | 训练共享过程评分器 |
| benign core `ood_val` | building-monitor-2/3 | 2,604 | 训练共享过程评分器 |
| benign auxiliary | 冻结 auxiliary fit | 6,600 | 训练共享过程评分器 |
| benign ToN-IoT | `normal_1` | 4,000 | 训练共享过程评分器 |
| attack Gotham | `support_train` | 385 | 逐条监督 |
| attack ToN-IoT | `aux_process` | 4,000 | 共享过程攻击监督 |

总计：

- benign fit：14,013；
- attack fit：4,385；
- formal fit：18,398。

`id_calib=809` 的源构成已经核验：

| source | 行数 |
|---|---:|
| `processed/iotsim-combined-cycle-tls-3.csv` | 270 |
| `processed/iotsim-combined-cycle-tls-4.csv` | 270 |
| `processed/iotsim-combined-cycle-tls-5.csv` | 269 |

上述源不含 cooler-motor，也不含 stream-consumer、hydraulic-system、ip-camera-street 或 predictive-maintenance。

`ood_val=2,604` 的源构成：

| source | 行数 |
|---|---:|
| `processed/iotsim-building-monitor-2.csv` | 1,690 |
| `processed/iotsim-building-monitor-3.csv` | 914 |

building-monitor 已进入 fit，永久失去 held/final 资格。

### 3.2 Select

阈值、损失权重和候选 checkpoint 只能使用：

| 类型 | 来源 | 行数 |
|---|---|---:|
| attack select | `support_val` | 69 |
| benign select | frozen auxiliary select | 3,000 |
| benign select | ToN-IoT `normal_2` | 4,000 |

benign select 共 7,000 行。core `id_calib`、core `ood_val` 和任何 held/report/final 数据均不进入 select。

### 3.3 Report / held / final

以下数据不得进入 fit、标准化、tail mining、阈值选择、checkpoint 选择或任何超参数选择：

- development canary：stream-consumer、hydraulic-system；
- repeated-view report：ip-camera-street、predictive-maintenance；
- final held：cooler-motor；
- future、sealed、same-file、domotic、combined attack report；
- 其他 report/future/sealed 数据。

cooler-motor 在 CKBW seed 27 期间继续封存，不得查看其标签或结果。

### 3.4 Support-train family 分布与最低监督门

385 条 support_train 必须每个 epoch 逐条使用至少一次，不得 episode pooling：

| attack family | 行数 |
|---|---:|
| File Download | 15 |
| Ingress Tool Transfer | 18 |
| Merlin C&C Communication | 30 |
| Merlin ICMP Flooding | 43 |
| Merlin TCP Flooding | 60 |
| Merlin UDP Flooding | 30 |
| Mirai C&C Communication | 9 |
| Mirai GRE Flooding | 60 |
| Mirai TCP Flooding | 60 |
| Mirai UDP Flooding | 60 |

实现前必须验证：

- 每个 support family 至少 8 行；
- 每个 family 每 epoch 至少形成 128 个合法 tail pairs；
- 不满足时直接判定实现合同失败；不得事后合并 family、删除 family 或改阈值继续跑。

## 4. 候选臂与可归因消融

### 4.1 冻结基线

- `M0-C1`：冻结 C1；
- `M1-Frozen-CKBQ`：冻结 CKBQ；
- `A2-ExtraTrees-OR`：CKBV 已完成的冻结模型类别对照；
- `M4-TabM-CE-OR-frozen`：CKBV 已完成的主候选对照。

### 4.2 CKBW 新臂

TabM 的干净 2×2：

| 过程头训练 | 决策 | 角色 |
|---|---|---|
| CE | OR | 冻结 M4；复用 CKBV 154917 结果，不重跑 |
| CE | Dual | 复用 CKBV 154917 的冻结 TabM-CE 逐条连续分数；只执行本协议的 Dual 阈值选择与决策，不重训 |
| Tail-pair margin | OR | 损失贡献 |
| Tail-pair margin | Dual | **预注册 PRIMARY** |

额外模型类别对照：

- `ExtraTrees-Dual`：直接复用 CKBV 154917 的冻结 A2 ExtraTrees 逐条连续分数与模型哈希；只执行本协议的 Dual 阈值选择与决策，不重训树头。

ExtraTrees 没有神经损失，因此不属于损失 2×2；它只回答“双边控制是否依赖 TabM”。

冻结分数复用必须以 CKBV 154917 的逐条预测工件为准：TabM 使用 `tabm_process_score`，ExtraTrees 使用 `extra_process_score`。复用前必须核验每条所需 select/report 记录均有有限连续分数、UID 唯一、行数和模型 SHA-256 与 154917 审计一致；任一不满足即合同失败，不得以重新训练或缺失行插值代替。

### 4.3 禁止事后晋升

- PRIMARY 固定为 `TabM-TailMargin-Dual`；
- PRIMARY 失败即 CKBW `NO_GO`；
- CE-Dual、TailMargin-OR、ExtraTrees-Dual 或任何冻结对照不得因 held 数字更好而事后晋升；
- 所有臂同时预注册、同时输出；
- seed 27 结束后不得根据 held 结果改损失、阈值、候选身份或成功标准。

## 5. 共享过程评分器

### 5.1 固定骨干

继续使用 CKBV 已采用的成熟 TabM 实现与骨干：

- official TabM v0.0.3；
- input dim = 51；
- width = 192；
- blocks = 3；
- ensemble dimension `k = 16`；
- batch size = 512；
- epochs = 24；
- 不使用 numerical embeddings；
- 一个共享二分类过程评分头，输出 `q(x) ∈ [0,1]`，越大表示攻击过程证据越强。

除下文明确预注册的损失项外，不修改网络宽度、深度、输入或训练轮数。

### 5.2 基础监督

基础项为 family/source-balanced binary cross entropy：

- attack：按 attack family 等权。Gotham 的 385 条 support_train 依照第 3.4 节的 10 个冻结 family 分组；ToN-IoT 的 4,000 条 `aux_process` 依照冻结 `mechanism_family` 分成 `ToN-reconnaissance_scan`（2,000）与 `ToN-credential_bruteforce`（2,000）两个独立 family，不得合并为一个 ToN 块；因此 attack 侧共 12 个等权 family，每个 family 获得相同的 attack-side 总权重；
- benign：按 source 等权；
- 每个 epoch 所有合法 fit 行至少使用一次；
- 385 条 support_train 每 epoch 全部逐条监督；
- 不使用 held/report 产生任何训练 pair。

二分类两侧总权重固定各为 `0.5`：attack 侧的 `0.5` 在上述 12 个 family 间等分，再在各 family 行内等分；benign 侧的 `0.5` 在合法 benign source 间等分，再在各 source 行内等分。实现必须输出 12 个 attack family 与全部 benign source 的行数、单行权重和总权重，并断言两侧总权重及 family/source 等权关系成立。

### 5.3 Tail-pair margin

正式损失：

```text
L = L_balanced_CE + λ_tail · L_tail + λ_family · L_family
```

第 1 个 epoch 只使用 `L_balanced_CE`。从第 2 个 epoch 开始，在每个 epoch 开始时，用上一 epoch 冻结 checkpoint 对全部合法 fit 行做一次 `no_grad` 评分，再冻结本 epoch 的 hard-tail 集合。禁止用同一 batch 更新后的即时分数自由改变 pair。

#### 攻击尾部

对每个 support attack family `f`，选择攻击分数最低的：

```text
k_f = min(16, n_f)
```

条记录，记为 `A_f^-`。排序以 `(q ascending, stable_uid ascending)` 决定。

#### 良性尾部

从合法 benign fit 中选攻击分数最高的 16 条，记为 `B^+`，但必须 source-balanced：

1. 每个 source 内按 `(q descending, stable_uid ascending)` 排序；
2. 按 rank round-robin 取候选；
3. 同一 rank 内按 `(q descending, source_group ascending, stable_uid ascending)` 排序；
4. 取满 16 条；
5. 输出每个 source 的贡献数，禁止单一 source 无审计地主导 benign tail。

#### Pairwise 项

固定 margin `m = 0.10`：

```text
L_tail =
  (1 / |F|) Σ_f
  (1 / (|A_f^-| · |B^+|)) Σ_(a,b)
  max(0, m - q(a) + q(b))
```

每个 family 等权，不能让大 family 用样本数淹没小 family。

#### Family-tail 项

```text
L_family =
  (1 / |F|) Σ_f
  max(0, m - Q25(q(A_f)) + Q95(q(B_fit)))
```

其中 quantile 只从合法 fit 行计算。该项约束每个 support family 的低分尾部高于 benign 高分尾部。

### 5.4 固定搜索空间

只允许：

```text
λ_tail   ∈ {0.25, 0.50}
λ_family ∈ {0.25, 0.50}
```

CE 臂等价于两者均为 0。`m=0.10`、24 epochs、骨干结构和 tail 大小均固定，不进入 held 调参。

所有 λ、checkpoint 和阈值只能根据第 3.2 节合法 select 选择。不得查看四个 held family 或 cooler-motor 后调整。

## 6. 双边控制

令：

- `h0 ∈ {0,1}` 为 Frozen CKBQ hard 决策；
- `q` 为共享过程攻击分数；
- `τ_normal < τ_attack`。

PRIMARY 的唯一决策规则：

```text
if h0 == 0 and q >= τ_attack:
    hard = 1          # rescue：明确攻击过程证据
elif h0 == 1 and q <= τ_normal:
    hard = 0          # suppress：明确稳定正常过程证据
else:
    hard = h0         # 中间区保持 Frozen CKBQ
```

约束：

- 不做简单分数相加；
- 不因 source/family 使用不同阈值；
- 不增加 family 专家；
- 不允许 rescue 和 suppress 同时触发；
- `review=0`；
- 缺失或无效 51D 时 `hard=h0`。

OR 消融只保留第一条 rescue，永不 suppress。

## 7. 合法选择协议

### 7.1 阈值选择数据

只使用：

- 69 条 support_val attack；
- 3,000 条 frozen auxiliary benign select；
- 4,000 条 ToN-IoT `normal_2` benign select。

必须分别报告 auxiliary 与 ToN-IoT 的 select 结果，不能只给混合 7,000 行结果。

### 7.2 `τ_attack`

对每个候选 checkpoint：

1. 在精确 score frontier 上寻找阈值；
2. 要求 dual 后 69/69 support_val 最终均为 hard；
3. 要求原本 `h0=1` 的 support_val 不被 suppress；
4. 在满足上述约束的阈值中，选择使 benign select rescue 数最少的最大可行 cut；
5. 输出所有相同最优点及确定性 tie-break。

### 7.3 `τ_normal`

在满足 `τ_normal < τ_attack` 的精确 score frontier 上：

1. 不得 suppress 任何 `h0=1` 的 support_val attack；
2. dual 后 support_val 必须保持 69/69 hard；
3. 在满足攻击约束的点中，最大化 benign select 的合法 suppress 数；
4. 同时最小化 benign select 的新增 rescue 数；
5. 分别报告 auxiliary 和 ToN-IoT 的 suppress/rescue 数量及比例。

### 7.4 λ 与 checkpoint 的词典序选择

对通过 69/69 攻击保真约束的候选，按以下固定顺序选择：

1. 最大化 benign select 净 hard 减少量；
2. 最小化 benign select 新增 rescue；
3. 最大化 support_val 的 worst-family score margin；
4. 选择更早 epoch；
5. 选择更小 `λ_tail`；
6. 选择更小 `λ_family`。

任何 held/report 指标不得进入此排序。

其中 benign select 净 hard 减少量的唯一定义为：

```text
net_hard_reduction
  = N(h0 = 1 and q <= τ_normal) - N(h0 = 0 and q >= τ_attack)
  = N_frozen_hard - N_dual_hard
  = suppress_count - rescue_count
```

计数母集固定为合法 benign select 7,000 行。`suppress_count` 只计冻结 `h0=1` 经 Dual 变为 0 的行；`rescue_count` 只计冻结 `h0=0` 经 Dual 变为 1 的行。必须同时输出混合 7,000 行、auxiliary 3,000 行和 ToN-IoT 4,000 行的四个原始量：`N_frozen_hard`、`N_dual_hard`、`suppress_count`、`rescue_count`，并断言上述两个等式逐组成立。

## 8. UDP Scan 的处理

CKBV 中 C1、Frozen CKBQ 和新过程臂对 UDP Scan 均没有形成可靠检测信号。CKBW 不为 UDP Scan 增加专门模型、阈值、特征或损失权重。

只允许进行预注册的可观测性诊断：

- target 与 51D 对齐完整性；
- raw51 mask 命中情况；
- TCP/UDP、端口、端点扩张、重试/响应等可用字段覆盖；
- 各冻结臂与 CKBW 臂的 score 分布；
- 与其他 attack family 的分布重叠。

该诊断不参与模型、λ、epoch 或阈值选择，也不能改变 CKBW GO/NO_GO 后再生成 UDP Scan 专家。

## 9. Seed 27 成功门槛

以下门槛只评价预注册 PRIMARY：`TabM-TailMargin-Dual`。

### 9.1 Attack preservation

相对 `M0-C1`：

- overall attack hard recall 下降不超过 0.5 pp；
- 每个 `rows >= 15` 的 attack family 下降不超过 2 pp；
- support_val final hard recall = 69/69；
- review = 0。

“主要 family”沿用冻结 CKBV 规则：attack preservation 表中每个 `rows >= 15` 的 unique family，禁止事后挑选。正式报告必须包括：

- overall；
- same-file；
- future；
- sealed；
- domotic；
- combined；
- 每个 attack family；
- worst-family recall；
- 与 C1 和 Frozen CKBQ 的差值。

UDP Scan 保留逐 family 报告和诊断，但因冻结 C1 recall 已为 0，不将“提升 UDP Scan”设为 CKBW 训练或放行条件。

### 9.2 OOD hard false-alarm

相对 `M1-Frozen-CKBQ`：

| 指标 | Frozen 基线 |
|---|---:|
| hydraulic-system | 45.70% |
| ip-camera-street | 8.10% |
| predictive-maintenance | 57.5889% |
| stream-consumer | 29.70% |
| 四 family macro | 35.2722% |

PRIMARY 必须同时满足：

- 四 family macro 至少下降 5 pp，即不高于 30.2722%；
- 任一 family 不得比 Frozen CKBQ 恶化超过 2 pp；
- 四个 required held family 的 hard false-alarm 均不高于 90%；
- multi-held signal 不得缺失。

分组报告但不分组调参：

- development canary：stream-consumer、hydraulic-system；
- repeated-view report：ip-camera-street、predictive-maintenance。

上述四个 family 都已被多次查看，不能称为 untouched final。cooler-motor 继续封存。

### 9.3 合同门

以下任一情况直接 `NO_GO`：

- held/report 进入 fit、标准化、tail mining、select 或 hard-pair；
- support_train 未全部逐条使用；
- source reset、score-before-update、past-only 或 no-grad 合同失败；
- target 对齐不完整；
- raw51 mask 记录没有 fail-closed；
- source 身份或 family 身份进入特征；
- review 不为 0；
- required metric 缺失；
- 任何结果臂被事后晋升；
- 根据 held 结果修改 λ、epoch、阈值或候选身份。

## 10. 停止与扩种子规则

- 第一轮只跑 seed 27；
- seed 37/47 继续锁定；
- PRIMARY seed 27 必须通过第 9 节全部门槛，才允许冻结方法并运行 seed 37/47；
- seed 27 失败后不得用更好的消融臂替换 PRIMARY；
- 多 seed 通过后，才允许按独立预注册协议首次打开 cooler-motor final held；
- cooler-motor 打开后不得再调整方法，只能报告。

## 11. 必须输出的证据

### 11.1 科研指标

- 全部候选臂的 attack preservation；
- 全部候选臂的 held OOD hard false-alarm；
- C1、Frozen CKBQ、CKBV A2/M4 与 CKBW 新臂的同表对比；
- canary 与 repeated-view 两组 macro；
- source/episode bootstrap 置信区间，不把 packet 当独立样本。

### 11.2 训练审计

- 每个 role/source/family 的行数；
- 385 support 每 epoch 的实际使用次数；
- 每个 family 的 `n_f`、`k_f`、pair 数；
- 每 epoch benign tail 的 source 构成；
- `L_balanced_CE`、`L_tail`、`L_family` loss CSV；
- 每个 family 的 Q25 attack score、benign Q95、最低 margin；
- λ、epoch 与 checkpoint 的完整合法选择 frontier；
- NaN/Inf 检查；
- seed、环境版本、commit SHA、manifest/mask/cache hash；
- wall time、TotalCPU、MaxRSS。

### 11.3 阈值与决策审计

- `τ_normal`、`τ_attack` 精确 frontier；
- 69 support_val 在每个阈值点的最终 hard 数；
- auxiliary 3,000 与 ToN 4,000 分源的 rescue/suppress/net hard 变化；
- held 每个 family 的 `kept / rescued / suppressed` 数；
- raw51 missing/fail-closed 数；
- Frozen CKBQ 与 PRIMARY 的逐行决策转换矩阵；
- 证明 threshold/gate 没有读取 held 标签的 scope audit。

### 11.4 可归因性

必须用同一输入、同一 seed、同一 split 输出：

- CE-OR vs CE-Dual：双边控制贡献；
- CE-OR vs TailMargin-OR：tail margin 贡献；
- TailMargin-OR vs TailMargin-Dual：组合贡献；
- ExtraTrees-OR vs ExtraTrees-Dual：模型类别下的 dual control 对照；
- PRIMARY 与 Frozen CKBQ、C1 的最终差值。

## 12. 本轮明确不做

- 不增加 per-family expert；
- 不增加 source-specific threshold；
- 不做 OpenOOD、Fishr、DANN、GroupDRO、SupCon、prototype bank；
- 不重启 TGN/GraphMixer/DyGFormer 路线；
- 不做普通 MLP、普通 pooling、普通 attention 或简单分数相加；
- 不做 review-only 修复；
- 不看 cooler-motor；
- 不跑 seed 37/47；
- 不为 UDP Scan 写补丁；
- 不重新提取或修改 154917 的缓存。

## 13. 解释边界

若 seed 27 通过，只能声称：

> 在预注册的 source-disjoint、held-family 协议和当前两类跨数据来源下，共享的因果过程表示、family-balanced tail-margin 与双边控制同时显示了攻击保持和良性 OOD false-alarm 降低的单 seed go signal。

在多 seed 与 cooler-motor final held 完成前，不得声称：

- 已解决任意未知设备/任意未知攻击；
- 已取得统计稳健的最终结果；
- 已完成跨数据集普适泛化；
- 已达到最终论文结论。

## 14. 审查与实现授权

本冻结版完成后的授权顺序固定为：

1. Kimi 按本文件 SHA-256 对数据合法性、损失、阈值、消融、不可晋升和输出清单做最终审查；
2. 用户确认最终系统含义、成功门槛并明确授权实现；
3. 只有上述两项均完成后才允许写 CKBW 实现；
4. 实现完成后再次独立代码审查，逐项验证本协议及第 14.1 节配置一致性硬门；
5. 用户最终批准后才允许构建并提交 seed 27 HPC。

### 14.1 实现期配置一致性硬门

实现完成后的独立代码审查必须逐项核对 CKBW TabM 与 CKBV 实际实现中的固定配置：`width=192`、`blocks=3`、`k=16`、`batch_size=512`、`epochs=24`、`numerical_embeddings=false`。当前仓库 CKBV formal 参数接口已显示这些数值，但它们不因写入本预注册而自动视为运行事实；CKBW 必须在模型构造、命令行默认/显式参数、run spec、model audit 和最终输出五处一致。任一缺失或不一致均阻断 bundle 构建与 HPC 提交，不得运行后补写。

当前状态为：**科学协议已冻结；等待 Kimi 对精确 SHA-256 终审；未授权实现、未授权提交 HPC**。
