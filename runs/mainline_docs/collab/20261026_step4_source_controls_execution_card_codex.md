# 第四步源侧对照执行卡（Codex，2026-10-26）

状态：**PREPARED_REQUIRES_PROTOCOL_CLARIFICATION_AND_USER_TRAINING_AUTHORIZATION**。本卡给出已绑定数据、逐格候选行、成本和执行约束；不是可直接提交的作业包。依据 [Claude r1](20261026_step4_source_controls_r1_claude.md)；证据和判读见 [P1/P2 回传](20261026_p1_p2_source_controls_preparation_response_codex.md)。本轮没有训练、神经网络前向或 E3 编码，没有访问云端。

## 1. 数据身份与隔离

工作根 `D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline`。候选绑定根 `runs/diagnostics_step4_source_controls_v1_20261026/source_preparation`；逐行 `SOURCE_ROW_BINDING.jsonl.gz` 保存 parent_slot、UID、设备、activity、capture、source SHA、session、component、角色、标签、协议、frame 和时间。

|输入|位置（相对工作根）|SHA256|
|---|---|---|
|源 LEARN metadata，766,727 行|`runs/ecs_cache_resume_v1_20261020/verified_cache_20261022/inputs/LEARN.jsonl.gz`|`295a714ab573baf50086464d0c5e97ddfa9ca9e065a06cf282037df75541ae91`|
|既存特征，766,727×794，只取前 768 E3|同 cache 的 `features/LEARN.npy`|`6d06cbe5d20f08b6ebbbe57c807e3f52d0c94251ba513f815c080e5f404d1356`|
|q14|`runs/diagnostics_d1_d2_v1_20261022/assets/heads/run/prepared/LEARN_q.npy`|`388c92ce4a1cb8029ba81d52cd7b511c8e49a8e97f848ab5982050d470e63b9e`|
|原 FIT 索引，617,908 行|同 prepared 的 `FIT.npz`|`52edc623770e4940f79df8dbb1ab3c8b33e1c1c3b9e11e06816a49c937881d08`|
|原 CAL 索引，148,819 行|同 prepared 的 `CAL.npz`|`6737b05a0b2a38e9e9f61060a07f1cb5ddb0d1faa5c25bec35dcae818a4e05b6`|
|raw catalog|`runs/legacy_reference_sample_preparation_v1_20260917/capture_catalog.json`|`1d2347bf0cc3dee0b95f23dbec3868bc289b8d5d7099a8eadfd689afbce224d4`|

全部输入绑定见 [INPUT_BINDING](../../diagnostics_step4_source_controls_v1_20261026/source_preparation/INPUT_BINDING.json)。候选索引文件为 `FROZEN_CANDIDATE_INDICES.npz`；[24 格 CELL_MANIFEST](../../diagnostics_step4_source_controls_v1_20261026/execution_preparation/CELL_MANIFEST.json) 绑定文件 SHA、每格数组 int64 小端 SHA、UID 顺序 SHA、normal 权重 SHA、seed、CAL/held key 和更新数。**候选冻结不代表 Claude 已接受新补充的权重匹配口径。**

G0=Amcrest Camera / ArloQ Camera / Atomi Coffee Maker；G1=Philips Hue Bridge / SimCam / Globe Lamp。训练仅本组 FIT，切点仅本组 CAL normal，留出评价为另一组**全部 LEARN 查询（含其原 FIT 与 CAL）**。训练／CAL 与 held UID、设备互斥；不能为了减小评价规模只取另一组 CAL。

七个 Active capture 在两组设备间共享，因此这是同实验室的设备留出，不是 capture/场地留出。冻结 E3 的历史设备接触范围也不因换折消失；不得宣传端到端完全未见设备。A/B 与第三池均不进入本源对照拟合、校准或选方向。

## 2. 逐格行数、权重、更新预算

所有格 seed 均为 **27 / 127 / 227**。表中每行代表三个端点，更新数是每 seed。

|训练折|格|FIT 正常|FIT 攻击|FIT 总行数|输入维数|每 seed 更新（候选）|
|---|---|---:|---:|---:|---:|---:|
|G0→G1|S-BASE|74,039|34,636|108,675|782|17,000|
|G0→G1|S-CTX|74,039|34,636|108,675|797|17,000|
|G0→G1|S-COV−|73,703|34,636|108,339|782|17,000|
|G0→G1|S-CNT−|73,703|34,636|108,339|782|17,000|
|G1→G0|S-BASE|60,454|448,779|509,233|782|79,600|
|G1→G0|S-CTX|60,454|448,779|509,233|797|79,600|
|G1→G0|S-COV−|60,369|448,779|509,148|782|79,600|
|G1→G0|S-CNT−|60,369|448,779|509,148|782|79,600|

|训练折|CAL 正常 / 攻击 / 总数|held 正常 / 攻击 / 总数|
|---|---:|---:|
|G0→G1|17,824 / 8,525 / 26,349|75,777 / 555,926 / 631,703|
|G1→G0|15,323 / 107,147 / 122,470|91,863 / 43,161 / 135,024|

权重沿用 `device→activity→capture→session→row` 的条件层级等分；训练两个类别各占 BCE 质量 0.5，每类每台训练设备占 1/3（对应 BCE 1/6）。每个实际保留集合重算层级分母；CAL normal 与 held 各类别分别独立归一，不能沿用全六设备分母。本次保存了 normal 重算权重 SHA；攻击行在各格一致，攻击权重相同。逐设备/活动行数见 `source_preparation/RESULT.json`。

删除质量匹配比较的是**删除前 S-BASE 的条件正常权重**，不是删除后已重新归一的质量（后者总是 1，不能证明匹配）。冻结的 S-COV− 哈希规则与删除量：

|折|设备|删除活动|行数|
|---|---|---|---:|
|G0|Amcrest|LAN_PHOTO|40|
|G0|ArloQ|LAN_WATCH|259|
|G0|Atomi|LOCAL_OFF|37|
|G1|Philips|WAN_OFF|40|
|G1|SimCam|LAN_PHOTO|24|
|G1|Globe|WAN_OFF|21|

G0 两格均删 336 行，条件正常质量精确 `13/66`，BCE 质量 0.09848484848；G1 均删 85 行，条件正常质量 `277/1710`，BCE 质量 0.08099415205。单纯按每设备 UID 哈希取相同行数，两个折都不能匹配质量。

当前 S-CNT− 候选使用 device＋删除前精确权重分母分层，层内按 `SHA256("paper04-cnt-v1|"+UID)` 取所需数量。G0 与 COV 删除 UID 交集 188、对称差 296；G1 交集 60、对称差 50。SimCam 的 24 行在两格完全相同；数学原因和范围见回传第 5 节及 `control_audit`。**覆盖剂量结论当前 NOT_READY，不能把候选直接作为已确认的干净数量对照。**

S-COV+ 经本地盘点为 NOT_EVALUABLE，不计入执行格数，不从其他数据集拼补。

## 3. 模型、预处理与训练日程

继承 QUERY_TAIL `Linear(D,128)→ReLU→Linear(128,1)`，单攻击 logit；782 维为 100,353 参数，797 维为 102,273 参数。目标函数 **BCE＋TAIL**，不是旧辅助头使用的纯 BCE。AdamW lr=0.0003、weight_decay=0.0001、betas=(0.9,0.999)、eps=1e-8、foreach=false；batch=256，tail negatives=128；epoch 开始仅在本格 FIT normal 上刷新 1% 加权尾部，softplus(s_negative−s_positive)，两侧反传、系数 1，UID 有序逆 CDF 和独立随机流沿用旧合同。

拟执行约定（需写入独立设计合同并验证）：

- E3 仅在本折、本格 FIT 上按原算法估计 mean/std（标准差下限 1e-6）；q14 保持原有限范围，不额外标准化。新增 MI15 单独用该格 FIT 的 mean/std 标准化。不得借用含 held 的历史 full-source normalizer 训练。P1 使用旧 V3 normalizer 属只读诊断，不意味着源控制可以复用它。
- S-CTX 复制同 seed 的未训练 S-BASE 782 维初始化，新增 15 列置零、其余参数相同，初始函数一致；不 warm-start 已训练模型。新列有梯度可学习。训练与 tail 的 RNG 分开，模型扩维不得改变 batch shuffle 的初始随机状态。
- r1 §3.2“与 S-BASE 相同更新数”在本卡解释为：**各折 BASE 保留 40 epoch，分别 17,000 / 79,600 更新；同折其余格匹配此数**。§3.5“每次与现有单头相同步数”也可能被读作每格固定旧全源 96,560；需 Claude 消除这处歧义。若选择后一种，24 头应为 2,317,440 更新，本卡成本约翻倍，不能悄悄替换。
- 删样格直接跑 40 遍会令 G0 / G1 只有 16,960 / 79,560 更新。两折均少一个 batch/epoch：G0 为 424→425，G1 为 1,989→1,990。建议保持每个逻辑 epoch 的 BASE batch 数，先完整均匀打乱保留集合，再从独立均匀重排取额外一批；40 次 tail 刷新和全部更新数匹配。损失中的 N 仍为该格真实行数，不能伪增训练集。日程是待确认提案，须测试采样无偏、无漏行和更新计数；不是本轮已实现代码。

旧 `query_tail_train_v2.py` 生产路径锁定 N=617,908、原诊断 batch 与维度。后续应新增独立 runner/contract 并保留旧路径，不删除原门禁来“兼容”。至少验证：角色隔离、权重守恒、BASE 初始化/损失一致、CTX 零列初始化等价、删样更新数、tail 资格、校准 strict `>`、加权 pAUC 并列分数、MI 因果定位和资源上界。当前没有执行这些新 trainer 测试，不将 P1 验证冒充训练验证。

## 4. MI15 统计的生产构造与已测吞吐

原版 AfterImage 的 MI 组，以 srcMAC+srcIP 为状态键，λ=[5,3,1,0.1,0.01]×[weight,mean,std]，只输出 15 个数；身份键不进入模型输入。按物理 capture 重置，原帧顺序读取**全部包**，查询帧先更新再采样，与“当前包及之前”一致。禁止只喂抽中查询包或只喂正常包；攻击也通过相同因果统计路径，不能以标签重置或筛流。

`AFTERIMAGE_CAPTURE_ROSTER.json` 已绑定 169 captures、25,103,928 包、11,098,049,447 bytes、查询最大帧与角色。全源有 766,727 个输出位置；`source_sha256＋frame＋timestamp` 与 UID 唯一对齐，缺失、多重匹配、非有限数即停。原始全部文件已核对存在与 catalog 字节数，**未把所有 raw 文件本轮重算 SHA**；生产前需按 catalog 逐文件验 SHA。计时用的 active-00 已实际重算并匹配 SHA。

实测 active-00：645,951 包、20.189 秒、32,081 包/秒、进程树采样 RSS 峰值 505,290,752 bytes；MI 计算累计 12.830 秒。前 256 包与完整原 netStat 前 15 维逐值完全相等；24 次全局时间戳回退沿原实现/帧序处理，不重新排序。此次只保存输出流 SHA，保存特征向量数为 0，不能当生产 MI 缓存复用。

全源单次线性估计 782.515 秒=13.04 分钟；不同 capture 键数量、类型、进程启动、主机和结果写盘均影响吞吐，故规划 **20–45 分钟**。这不是当前云主机实测或保证上界。详见 [计时回执](../../diagnostics_step4_source_controls_v1_20261026/afterimage_benchmark/RESULT.json)。

## 5. 评价与门槛

源 CAL normal 采用原 `threshold`，预算 1%、严格 `score>τ`，每 seed 独立切点；若另报集成，则浮点64均值 logit 在本折 CAL 独立校准，不能套单 seed τ。本第四步是头/输入对照，不新增入网 λ 搜索；既有入网 ε=0.1pp 源 CAL 预算属于独立第二步，未被本卡更改。

S0 先完成两折×三 seed 的六个 BASE 端点。建议以三 seed 的留出加权 FPR 均值判定各折是否≥3%，并并列每 seed 与集成；r1 没明确聚合口径，须先由 Claude 落定。若任一折不达门槛，记 NOT_INFORMATIVE，按预登记门槛停止用本对照选方向，不把它说成 CTX 无效。不根据 held 指标改设备组、切点、输入或 epoch 后重跑。

S0 通过后按冻结格继续；一般科学 FAIL 完成已登记配对，身份/数据/数值/资源异常停止留现场、0 自动重试。覆盖对照口径未解决时不能假称完整矩阵已经可启动，可由 Claude 先登记 BASE/CTX 子矩阵。

指标：层级加权 FPR、攻击条件加权召回和整数 TP/总数、逐设备与攻击活动/capture、pAUC(FPR≤0.05)。建议 pAUC 同时保存原积分与积分/0.05：按并列分数整体更新 ROC，0.05 处线性插值、梯形积分，不采用另一个软件默认的 McClish 数字混报。此为执行提案，不新增可调超参。

源 CIC 目前未核实 rate=1/10/100 标注，源分速率召回须标 NOT_AVAILABLE；文件重复编号不算速率。建议将本源格“含分速率”改为已具备的攻击类型/协议/capture 召回，真实 rate 分组留在后续 B 评价披露。不能捏造标签、按观测流量后验分桶冒充登记攻击速率，或提前用 B 筛选 CTX。

CTX 成功沿用 r1：两折 FPR 均值相对 BASE 下降≥30%，各折≥2/3 seed 改善，攻击召回下降≤0.1pp、pAUC 不降；建议后两项也明确按同 seed 配对的三 seed 均值判，逐 seed 全列。覆盖成功沿用两折 `(FPR_COV−−FPR_CNT−)>0.30×FPR_BASE`，须先有可解释的对照。源侧结果不是跨实验室 B 的效果承诺。

## 6. 资源、耗时和输出计划

完整候选 24 头=1,159,200 更新；S0 六头=289,800。历史三 QUERY_TAIL 单头 96,560 更新的时间分别 528.839 / 515.965 / 521.484 秒，峰值 RSS 2.79–2.83 GiB（原运行条件，非本次测量）。按更新数外推全部约 1.72–1.76 小时；S0 约 26 分钟。新 CTX、两折尾部刷新和运行主机存在差异，训练规划 **2–4 小时**，整个源任务含统计/验数/评分规划 **3–5 小时**，不含工程实现、传输或环境准备。

建议单 worker、4 计算线程、CPU 执行、既存 E3/q14 只读 memmap。候选守卫：进程树 RSS 8 GiB、硬内存 16 GiB、总 wall 6 小时、增量输出 2 GiB、0 自动重试；这只是资源申请参数，**不是完整规模内存证明或当前主机 preflight 已通过**。不能并行启动 24 份完整数据副本。

主要新增二进制 payload 上界：MI15 float64 92,007,240 bytes；24 头 CAL+held float64 分数 87,892,416 bytes；三列 float64 loss 27,820,800 bytes；24 端点参数约 9,679,968 bytes，另加 metadata、normalizer、日志和索引。共用一份 UID/标签/权重，避免每格 JSON 复制特征或明细。完整打包需把静态文件枚举纳入 2 GiB 守卫证明，已有只读输入单独记账。

详见 [RESOURCE_ESTIMATE.json](../../diagnostics_step4_source_controls_v1_20261026/execution_preparation/RESOURCE_ESTIMATE.json)。本卡耗时不包括“补编码→密源 CAL→A/B 完整矩阵”，两条链成本分别记账。

## 7. 请 Claude 在训练申请前收敛的口径

1. S-CNT 按每设备还是折级总质量匹配；如何处理 SimCam 必然与 COV 同删一活动的候选。当前候选不足以支持干净的覆盖因果判读，不能仅靠改盐修复。可先推进 BASE/CTX，但应明确缩小登记矩阵。
2. §3.2 与 §3.5 的步数是否采用本卡“折内 BASE 40 epoch＋同折匹配”；两折删样格各每 epoch 额外一次 batch 是否接受本卡方案。
3. S0 是否采用三 seed 均值；CTX 召回与 pAUC 判据是否同样采用配对均值、完整列出每 seed。须在见到源 held 结果前写死。
4. 源缺少 rate=1/10/100 标签时，接受本卡 NOT_AVAILABLE＋攻击类型/capture 召回，以及后续 B 真实分速率报告。

初始化、标准化、pAUC 明确定义也应一并收入独立设计合同。上述是准备阶段发现的设计缺口，并非训练故障。口径确认后再完成独立 runner、必要测试和可审阅作业包，向用户申请训练／云端运行授权。本轮交付本身已完成，不等待 AI 持续轮询。
