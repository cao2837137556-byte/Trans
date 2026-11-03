# Codex → well：历史正常参考方案 r1 复核

日期：2026-10-31。状态：`R1_REVISION_REQUIRED_BEFORE_IMPLEMENTATION`。

原稿 SHA256：`d2bd3063f11b8e087f402ecf2db9a140a1d2b52b7e857ffc3cac0dc330c44fde`，已核验，未改原稿。本轮只有源码、现存回执/目录/元数据读取、计数和静态工作量算术；未下载、提取/解码 PCAP、补库、编码、打分、计算距离/support、训练、提交超算或运行实验。

**结论：r1 消除了 V1 的目标 FIT 空集、S 重用、负 cut 筛选等问题；一个冻结工作点、无选档的开发级补库实验在逻辑上可以成立。但仍有挡住实现的硬伤，主要集中在前端绑定、历史流身份/上下文、HIST-DEV 参考截止和候选枚举/上限。两个核实问题的答案分别是“没有现成已验收的额外开发攻击集，但存在明确候选”和“3,600 秒逻辑切片按本文写法不能直接满足现行合同”。**

## 先纠正我上一轮回复中的前端错误

上一轮把旧 `BoundedNetfoundPrefix` 的“无 idle reset、每方向保留最前 12×6 包、最多144包”当成了 `constrained_onboarding_reference_v2.py:279` 的实际前端。这是我的追踪错误，r1 据此沿用的部分应当更正。

实际调用链为：

`constrained_onboarding_reference_v2` → `continuous_input_engineering_v1.Contexts` → `continuous_input_v3.Contexts / RecentState`。

本轮对上述三个文件与冻结 encoding_v2 vendor 的 SHA 逐一比较，**三者全部相同**。现存 B2 编码回执也明确记录：

- `input_version = continuous-input-core-repair-design-v3-20260929`
- `input_readout = RECENT_CURRENT_INCLUSIVE`
- `real_recent_features = true`

实际规则是：相邻合法同 key 事件间隔 **>60秒重置**；同方向间隔 **>10ms** 切 burst；每 burst 保留**最近6包**；快照从双方向合并后取**最近12个 burst**，再过滤超过60秒的包，总计**最多72包**，必须含当前包。状态还有1秒/10秒半衰期的衰减统计及缺头/倒序污染处理。只有事件解析等部分复用了 legacy 工具，不能由此推断还在用旧前缀。

证据：[直接入口导入，第22行起](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/repo/ood/constrained_onboarding_reference_v2.py:22)、[实际状态类，第70行起](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/repo/ood/continuous_input_v3.py:70)、[现存 B2 编码回执](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/diagnostics_d1_d2_v1_20261022/assets/onboarding/run/encoded/CIC_DEV/B2/receipt.json)。旧回复作为已交接的封存记录不改 SHA，本回复及项目入口明确更正；不能继续照旧回复的前端段实现。

## Q1：四台设备在 A/B 之外有没有合法攻击资产？

需要区分**已验收可直接用于开发的资产**与**数据集中已知的候选材料**。

**在本轮核对的现有绑定和回执中，没有找到可直接接入的四台设备额外开发攻击集。不能把这扩大成“数据集中不存在 A/B 之外的攻击”。四台都有具体候选，其中 A 的候选原压缩包还在本地。**

### A / HeimVision

当前 A 的 HeimVision 攻击查询来自 `interaction-attack-194…200` 七个 capture：1份 HTTP、3份 TCP、3份 UDP。这七个 capture 都已经进入 A；从同一 capture 抽取未抽中的包，不会自动变成与 A 独立的攻击开发材料。

但是，已经保存的完整攻击归档目录中还有以下**实际 PCAP 成员**，不在当前302项 capture catalog 和 A 的攻击来源中：

| 归档内部成员，均在 `6-Attacks/2-RTSP Brute Force/Nmap/HeimVision Camera/` | 字节 |
|---|---:|
| `HeimVisionCamRTSP_1.pcap` | 2,304,619 |
| `HeimVisionCamRTSP_2.pcap` | 2,118,260 |
| `HeimVisionCamRTSP_3.pcap` | 2,163,709 |

三份合计 **6,586,588字节**，所在 [6-Attacks.tar.gz](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/legacy_cic2022_attack_acquisition_v1_20260915/raw/6-Attacks.tar.gz) 当前存在。本轮读取的是已存目录，没有解包。`._HeimVisionCamRTSP_4/5.pcap` 等是 AppleDouble 元数据，不能算额外抓包。

这些候选**尚未取得同 MAC、攻击者/受害者/服务/事件标签、时间与当前前端可接纳性验收**。旧归档评估明确写的是 capture/文件夹级来源，不是逐包真值；不能给整个 Nmap 文件统一贴攻击标签，或套用已验收洪泛/Hydra 的标签规则。它们也不当然覆盖此次担心的同类贴线攻击风险。

来源：[归档成员清单](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/legacy_cic2022_attack_acquisition_v1_20260915/inspection/members.jsonl)、[归档元数据评估](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/legacy_cic2022_attack_acquisition_v1_20260915/metadata_assessment.json)、[现有 capture catalog](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/legacy_reference_sample_preparation_v1_20260917/capture_catalog.json)。

### B / Samsung、WEMO Power、TP Link

当前 B 三台设备的所有攻击查询来自 **`unsw-mixed-20180601`**，SHA `befc3f6882a2b3137652a81af1deba4f71d3cbd4b80db6344c2d64a9fc112bed`。三台各有3个已绑定 annotation；已存查询攻击行数分别为 Samsung 14,506、Power 14,513、TP Link 14,604。

官方 annotation 元数据还列出同 MAC 的其他攻击日期：

| 设备 | 非 06-01 annotation 区间总数 | 其中值得优先核验的直接 TCP/UDP 候选 |
|---|---:|---|
| WEMO Power | 12 | 06-02 TcpSynDevice 3段；06-05 TcpSynDevice 3段 |
| Samsung | 30 | 06-02 TcpSynDevice 3段、UdpDevice 6段；06-05 TcpSynDevice 3段 |
| TP Link | 16 | 06-02 TcpSynDevice 3段；06-05 TcpSynDevice 3段 |

因此 **06-05 是一份可能同时补三台开发攻击材料的具体日期候选**；06-02 还提供 Samsung 的 UDP 候选。其余条目包含反射攻击、PingOfDeath 等，不能把条目数等同于前端可用攻击点数。

已存官方页面观察列有这些每日 mixed PCAP；但当前已核验的原始绑定只有 05-28 benign 和 06-01 mixed。06-02/06-05 的原始 SHA、实际时钟、受害者/攻击者及端口、包标签、前端可用位置、完整历史使用/依赖隔离尚未验收。本轮未在线下载或以区间标注推断全部包为攻击，也未读取 workbook 原表重新分析，只用了已保存的 JSON 元数据。

来源：[官方 annotation 元数据](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/legacy_commissioning_external_source_research_v1_20260925/annotation_metadata_rows.json)、[官方来源记录](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/legacy_commissioning_external_source_research_v1_20260925/official_source_notes.md)、[06-01 窄标签合同](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/legacy_commissioning_unsw_evaluation_preparation_v1_20260926/label_contract.json)。

**对 §3 的判定：** 可以提出“本候选主动不使用额外攻击开发、固定工作点、最后一次 A/B 才判保护”的受限设计，但必须如实写成**未纳入已知但尚未验收的候选资产**。不能把它论证为“数据不存在，所以只能这样”。最后的 A/B 保护门是评价后判失败的规则，不是进入 A/B 前已验证安全。冻结 λ/scale/cut 是减少自由度的设计选择；源 own bank 不变只说明旧源结果检验不了此次目标干预，不能证明新目标库继承原保护。

本轮不要求为了讨论继续扩展下载。是否先验收这些攻击候选，属于下一步设计取舍；r1 的受限单候选也可以保留，但须明确其证据边界，不能与有开发攻击保护的路线混称。

## Q2：3,600秒逻辑 capture 能否不改语义满足 v2:279？

**按 r1 原文不能。** `duration_seconds=3600` 只满足一项枚举值检查，完整合同还包含以下具体条件。旁路表解决原始定位问题，不能单独解决状态语义和身份问题。

| 代码位置 | 实际合同 | r1 的冲突或缺项 |
|---|---|---|
| v2:288–291 | 允许时长3600/7200；真实正常来源；`capture_spec.t0 == t0`；合法 `sha256` | 时长可接受，但逻辑 capture 的来源身份和正常证据仍需正式绑定 |
| v2:293–304 | decoder 必须声明完整、未预过滤，`occurrence=f`；已知设备名册完整；实例化新的 `Contexts(capture_id)` | 不能先删未解码/分片/不合格行再送入状态机；这些行须按现行规则被观察和处理。每小时新建 Contexts 还会重置上下文 |
| v2:313–315 | 帧号从1连续；**首包真实时间必须等于 t0** | 固定整点网格的窗起点通常不是首包时间。若改成首包时间，`t0+3600` 又未必等于原网格终点；必须选一个明确合同 |
| v2:317–321、354–358 | 必须观察到时间**严格大于**截止的边界帧；否则要求包数完整且 `recorded_capture_end >= t0+3600` | 仅交付窗内包，最后包往往早于截止，无法证明完整一小时。不能把人为网格终点伪填为真实记录结束。最后不足一小时的片段尤其不能通过 |
| v2:335、`_row_identity`:86 | `uid=digest([source_sha256,frame,owner])`，不含 capture_id | 若 source SHA 仍是同一原成员、每小时逻辑帧重置，会产生同输入三元组，无法保证全局 UID 唯一。只改 capture_id 或加旁路原包号不能修复主 UID |
| v2:304、continuous_input_v3:91–96、167起 | 状态按 owner/capture/key 管理；真实合法事件间隔>60秒才按 idle 规则重置，污染账本也持续存在 | 人为按小时切新 capture 会截断跨窗且间隔≤60秒的连接、衰减状态和污染历史。不能声称与原完整流上下文等价；补60秒包也未必复现持续衰减统计 |
| v2:346–352、364 | 每个窗口只留下每 `(owner,component)` 的**最后一个**合法端点，回执为 `ALL_LEGAL_ENDPOINTS_LAST_PER_COMPONENT` | 它不是原密库“所有合法位置”的枚举器。直接套用会先把候选域缩为每小时/组件末端；后面的时间均匀抽样已不是原密库的同一候选域 |

源码：[v2 输入和枚举合同](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/repo/ood/constrained_onboarding_reference_v2.py:279)、[原 UID 身份检查](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/repo/ood/constrained_onboarding_reference_v2.py:77)、[现行 Contexts](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/repo/ood/continuous_input_v3.py:167)。另有工程接口要求 `capture_id` 是非空字符串；r1 的 `(成员SHA,窗号)` 应规定规范字符串编码，不能直接把 tuple/list 传入 [ReferenceBank 元数据检查](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/repo/ood/constrained_onboarding_core_v3.py:34)。

### 建议的最小实现路径

**建议删去“强行每小时变成新 capture 以套 v2:279”的做法，增加一个明确的历史材料适配器，复用现行 `Contexts/RecentState`、快照/q14 校验和冻结 E3。** 这属于历史输入接口扩展，不需要改模型或组件定义，但必须承认新历史输入合同，不能叫原 v2 一小时入口直接复用。

可以按以下单一路径固定：

1. B 每个原始成员建立一条稳定时间序的逻辑流，保留原时间与原包定位；流内逻辑帧全程连续，不在每小时重置上下文。绑定排序/解码规则、真实来源 SHA、实际 EOF 与全量包数；若使用派生输入 SHA，必须明确它指向的真实派生对象/清单，而不是用一个任意 hash 冒充原始文件 SHA。
2. 给整个派生流一个唯一来源身份与字符串 capture_id，保留原成员 SHA＋原包号映射；用当前 UID/快照合同产生自洽的新身份，不能与原编码 UID 混用。合库保留历史原身份；A 的11行直接复用现存身份和当前编码，不经这个适配器重编号。
3. 按日期绑定 HIST-REF/HIST-DEV 角色。完整时序上下文可以依法处理此前包，但参考候选不得使用 DEV 未来包；候选截止与完整历史参考可用时刻分别记账。声明候选域是全部合法端点，按冻结的有界组件轮转选点；先选定身份，再只为选中位置提取快照/编码，避免生成所有端点的巨量快照。
4. A 的189/190/191只有几十秒，不送入要求完整3600秒的构建器，直接用已核验的11行历史表示。这与r1“优先复用”应升级为明确执行分支。

如果坚持逻辑小时 capture，必须把小时重置明确登记为新的历史上下文定义，并解决 t0、真实闭合、全局唯一来源身份、候选域与所有尾段处理；不能再宣称“不改代码语义”。本回复没有替方案执行或验证任何适配器。

## 其他需要在实现前写清的条目

### 1. HIST-DEV 必须有独立的历史库元数据视图

r1 §1.6 把新增行的 `reference_end` 统一为2018年的完整目标库截止，§2 又要用这些历史行去支持2016–2017年的 DEV。若实现直接复用合库行，即使已经去掉现有2018参考，`ReferenceBank` 仍会因查询早于 `reference_end` 返回 `BANK_NOT_YET_AVAILABLE`，所有支持归零，DEV门退化。

必须固定两个可用时刻，不能只删行：

- `HIST_DEV_BANK`：仅 HIST-REF；同设备行统一采用真实的历史参考完成截止，且严格早于该设备最早 DEV 查询；保留对应的 capture 帧界。
- `AB_BANK`：原密库＋同一批 HIST-REF（A为11行旧参考）；同设备行采用现有 B2 完整截止，沿用原 A/B 主/全视图。DEV 结束后不把 HIST-DEV 再并库。

这两种元数据视图可以共用同一历史编码，不需重编码。它们是不同可用时刻下的两次支持计算；HIST-DEV评估的是历史子库，不能把它的50%下降当作最终合库在A/B上的预期下降。

### 2. “每个新组件一个锚点”和4,096上限冲突时怎么办

历史跨多月，组件按完整 IP/端口五元组定义，新组件数可能超过4,096。不能同时保证“全部新组件至少一个锚点”与“新增行上限4,096”。这不是已经发生溢出的结论，而是实现缺少必须处理的输入分支。

建议规定：旧库全部保留；对历史候选使用确定的组件排序/轮转，在4,096预算内给组件名额；组件超过预算时按冻结排序选最多4,096个并披露覆盖，而不是突破上限。已有旧锚点与新组件优先的顺序也要固定。新盐 `well-hist-r1-20261031` 是本轮登记选择，可用，但不能称为完全复用旧盐。

HIST-DEV 的“每设备最多4,096、按同规则”还需明确 TCP/UDP 如何共同分配这4,096，不能实现成每协议4,096再仍宣称≤12,288。RAW FP=0时50%相对降幅无定义，应明确返回无改善空间的停止状态，不能发生除零。以上均可直接写成确定分支，无需再作方案讨论。

### 3. 停止和保护语义

- “任一设备新增组件为0就停止”可以保留为保守设计门，但它**不是机制不可达证明**。TP Link 原本已合格，补同组件的新几何覆盖也可能改善零support；其所需条件与HeimVision补第二TCP组件不同。
- PASS 的逐设备 FPR≤2% 应覆盖全部原评价设备。三个未补设备无需新支持运算，可复用其已存结果，但不能从验收表中静默移除。
- 池召回≥99%、设备1pp/组5pp、RAW低召回不得撤回均须按计划要求在三seed及ensemble明确执行。现有ε=0.1主成绩是比较基线；r1若只采用绝对召回≥99%及分组撤回门，不应声称还保持了旧池ε=0.1预算。固定λ并不自动保住原ε。最终实现需把这项保护范围写清，不能按结果临时解释。

### 4. 预算可以补成实际静态上界，无需试跑 ETA

用现存 A/B 查询的协议计数和现有密库行数，只做行数乘法；A新增仅现存TCP1/UDP10行，B每设备/协议新增最多4,096。完整 A/B 视图中四台需更新的 own 距离对保守上界为：

| 部分 | 距离对上界 |
|---|---:|
| A / HeimVision | 164,437,656 |
| B / 三台目标 | 364,845,140 |
| A/B 合计 | **529,282,796** |
| HIST-DEV：至多12,288查询×每协议至多4,096 HIST-REF | **50,331,648** |
| 两部分合计 | **579,614,444** |

这是保守枚举上界，包含可能因资格/因果条件提前退出的对；不是新距离结果或耗时保证。每次支持可复用于三seed、ensemble和主/全视图，不再乘4或2；未补设备使用旧结果。A 11行复用时，真正新增 E3 上界可缩为 B参考24,576＋DEV12,288＝**36,864**，r1写的45,056总上界则仍是宽松上界。

4CPU/16GiB/20GiB/8h可作为拟定硬限，需明确单模型进程、候选快照磁盘守卫和资源超限停止；不能把静态对数证明成8小时可完成，也不能把新16GiB写成旧8GiB授权已覆盖。本轮只审阅，不启动该预算下的作业。

## 回写结论

**接受 r1 的单候选、无分数选点、固定工作点及如实降级为开发级评价的主体方向；不接受现有前端段和“没有攻击候选”的过强解释。** 上述修订是明确的接口与分支修订，不需要再写原则稿。建议下一稿直接采用整成员连续历史适配器、A11行直复用、双截止元数据视图和有上限的确定性轮转，并明确暂不纳入哪些攻击候选。完成这些才能交实现；本轮没有替它实现或开跑。

[机器证据](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/mainline_docs/collab/20261031_well_history_normal_reference_execution_plan_r1_review_evidence_codex.json)保存23项输入的前后SHA一致、冻结vendor匹配、当前A/B攻击来源、额外候选清单与静态对数。原r1和上一轮回复均保留原SHA，科学代码与原始数据未改。
