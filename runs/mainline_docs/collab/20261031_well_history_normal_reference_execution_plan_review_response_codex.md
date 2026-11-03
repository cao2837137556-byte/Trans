# Codex → well：历史正常参考方案 V1 的只读复核

日期：2026-10-31。结论：`DESIGN_REVISION_REQUIRED_NOT_EXECUTION_READY`。

输入稿 SHA256 已核验为 `ad1f9043f0a5e0181af19b0881e6866a8d4deb3c9773beae90bb34171189e899`，原稿未改。本次只读源码、已保存的元数据和历史结果摘要，完成计数、时间范围与摘要算术核查；回写本文及证据。未补库、提取特征、编码、打新分、计算新距离/support、训练、提交超算或评价新 A/B。

**直接回答：Q1 是“依赖参考库，补库可以改变资格”；不能按 Q1 的否定分支结项。四台设备也确实覆盖了绝大部分残留误报。但这只证明存在作用入口，没有证明能在召回保护下达到 2%。V1 目前有实际的数据角色和算法缺口，不能直接实现为可执行实验。**

这不是原则确认稿。下面给出三个问题的实际答案、可填写的参数，以及必须改掉的具体条目。

## Q1：补入历史正常参考能否改变组件资格？

**能，条件是增加同一设备、同一协议下真实不同且因果合法的 `component_id`。** 资格并非查询自身永久不变的属性。

在 `ReferenceBank._evaluate_group` 中，程序先检查完整参考库结束时间与同 capture 帧界，再统计合法参考里的不同组件数：少于 2 个返回 `FEWER_THAN_TWO_LEGAL_COMPONENTS`；达到 2 个才置 `eligible=True`。随后用冻结几何计算两种距离，按组件取最小联合距离，再取第二个不同组件的距离，得到 `support = clip(1 − second_joint, 0, 1)`。

源码：[资格与支持计算，第219行起](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/repo/ood/constrained_onboarding_core_v3.py:219)；[组件身份，第77行起](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/repo/ood/constrained_onboarding_reference_v2.py:77)。

因此必须分清三件事：

1. **已有 1 个组件，补进第二个组件：** 可以由无资格变成合格。这里只是继续执行原来的 2C 规则，没有放宽为单组件修正，也没有复活独立源 1C 实验。
2. **已有合格 2C、support 为 0：** 新参考若改善两个不同组件的距离，可以变成正 support；仅改善一个组件不一定有效。
3. **已有正 support：** 本来就已经合格，不存在“先只有正支持，后才组件合格”的顺序。增加 support 能否跨越 cut，还受 λ、scale、原分数余量和攻击保护限制。

组件定义为 `digest([owner, canonical_key])`；canonical key 包含协议和排序后的两端 IP/端口。capture、日期、10分钟窗不在组件定义里。不同日期、不同 session 不自动等于不同组件；同组件再加 6,000 点也不能凭数量满足第二组件要求。

**已有一个无需新编码或距离计算的实物证据：** HeimVision 当前密库 TCP 有 2,521 行，但只有一个组件 `c0c44912…6902a3`；旧正常参考 TCP 有 1 行，组件为 `129349ec…c7233`，两者不同。若按新的历史合库合同合法纳入，TCP 的组件集合可从 1 变为 2。旧 HeimVision 还有 10 个 UDP 组件，与当前 2 个 UDP 组件不重叠。这里仅核对已存组件身份，没有实际合库或验证新 support。

还需注意合库接口：同一 `(partition, device)` 的所有参考行必须具有一致的 `reference_end`，否则报 `COMPLETE_BANK_END_MISMATCH`。旧 HeimVision 行的结束时间是 2021-10-06，当前密库是 2021-11-02；直接拼接会失败。新合同须保留原始时间/来源字段，同时明确完整合库可用时刻及每 capture 帧界，不能靠改早截止或改查询分母掩盖冲突。

**Q1 判定：机制入口成立；2% 可达性尚未证明，不作“不可达结项”，也不作性能通过。**

## Q2：179700 残留 FP 分布和四台设备的覆盖

口径沿用已保存的 179700 主结果残留分解：观察期后、原层级权重、主集成结果。以下只汇总原摘要，未重算候选评价。贡献单位是对所在池 FPR 的百分点，不是设备自身 FPR。

| 池 | 设备 | 残留 FP 行数 | 池 FPR 贡献（pp） | 占本池残留误报权重 |
|---|---|---:|---:|---:|
| A | HeimVision Camera | 63 | 3.993365575 | 99.997096% |
| A | Eufy Home Base | 1 | 0.000115955 | 0.002904% |
| B | WEMO Power Switch | 5,113 | 5.312907667 | 55.809882% |
| B | Samsung Camera | 5,001 | 1.908947908 | 20.052703% |
| B | TP Link Plug | 225 | 1.857751235 | 19.514903% |
| B | WEMO Motion Sensor | 93 | 0.237535684 | 2.495213% |
| B | Netatmo Camera | 4,309 | 0.202511455 | 2.127298% |

- A 合计 64 行、FPR **3.993481531%**；HeimVision 覆盖 63 行、**99.997096%** 加权残留误报。
- B 合计 14,741 行、FPR **9.519653949%**；目标三台合计 10,339 行、**95.377488%** 加权残留误报。其余两台共 4,402 行，贡献 **0.440047140pp**。
- 不能把行数覆盖率替代加权误报覆盖率。Netatmo 的 4,309 行权重小于 TP Link 的 225 行。
- 在其他设备结果和工作点不变、目标设备所有残留误报都免费消失的纯算术假设下，剩余池 FPR 才是 A 0.000115955%、B 0.440047140%。这是定位靶设备的依据，**不是可实现效果，更不是安全性保证**。

四台设备的残留原因如下，说明补库需同时处理资格和距离覆盖：

| 设备 | 不足两组件 | 合格但零 support | 正 support 但降幅不足 |
|---|---:|---:|---:|
| HeimVision | 42 | 0 | 21 |
| WEMO Power Switch | 5,109 | 3 | 1 |
| Samsung | 4,961 | 0 | 40 |
| TP Link | 0 | 136 | 89 |

来源：[179700 残留分解](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/dense_reference_ab_stage_dependency_repair_execution_20261028/result_retrieval_179700_20261028/RESIDUAL_FP_DECOMPOSITION.json)。

### 原稿必须纠正的三个数值解释

1. **6.869728% 是 TP Link 的设备级理想范围下界，不能写成 B 池下界。** 它对应“单组件＋现有正 support”的作用范围假设。如果只把 TP Link 全部 FP 免费消掉，B 池仍是 `9.519653949 − 1.857751235 = 7.661902714%`。这两句话不是同一个试验假设。
2. **A 0.173727%、B 0.421761% 不是“补历史参考全部成功的最好结果”。** 它们来自旧资产、指定最大作用范围、固定 λ=0.25/scale/cut 的幅度界限；没有证明某个算法能实现它们，更没有纳入新库重校准后的保护代价。新方案失败后，也不能把旧的 6.87%/2.51% 升格为所有未来补库方法的机制下界。
3. **seed127 HeimVision 的 1.471271pp 是最大范围假设下的潜在额外 TP 撤回暴露，不是 179700 已实际撤回。** Samsung 的 17.546136pp 同理。必须用冻结 RAW 对实际候选计算累计撤回，不能把潜在值记入已有漏报账。

来源：[原上界报告，第24行起](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/ab_reachable_bounds_readonly_v1_20261028/RESULT_REVIEW.md:24)。

## Q3：实际参数和时间边界

### V3 几何、参考行数与 RAW cut

主 A/B 冻结几何有两轴、分协议，**不是一个可以直接拿来除以二的欧氏半径**：

| 协议 | `rho_z`（归一化 E3 余弦距离） | `rho_q`（q14 RMS 距离） |
|---|---:|---:|
| TCP / 6 | 0.6350346595136246 | 0.3784318683067434 |
| UDP / 17 | 0.5389518932620280 | 0.27275012216397504 |

`z` 先经过冻结 E3 mean/scale，再单位化；`dz=clip(1−zq·zr,0,2)`，`dq=sqrt(mean((qq−qr)^2))`，联合距离为 `max(dz/rho_z,dq/rho_q)`。源 G0/G1 各折须绑定自己的 normalizer/geometry，不能默认套主 A/B 数值。

若下一稿明确选择“仅按归一化 E3 余弦距离做去重”，`0.5*rho_z` 的数值分别为 TCP **0.3175173297568123**、UDP **0.2694759466310140**；这只是原文公式在该特定解释下的算术值，并非已验证阈值。本稿未替方案选定距离或阈值。去重还必须说明是否跨组件，否则可能把最需要的第二个不同组件当作近重复删掉。

现有密参考数量为 **SOURCE_REFS 4,728 + A 8,574 + B 13,247 = 26,549**，这是三个分区的合计，不是单台目标设备的库，也不能混成一个 own bank。21,660 是当时新增编码位置。旧密库来自源侧 13 段早期 REFERENCE 和目标原 B2 窗口，**不是从 FIT/HELD∩FIT 查询中加点**。旧规则为每 `(设备, 协议)` 上限 4,096、保留锚点、组件轮转及组件内时间均匀，盐为 `claude-dense-reference-r1-20261025`。

主 A/B RAW cut 已有实际值：

| 头 | RAW cut | 原稿 `0.1*cut` 的结果 |
|---|---:|---:|
| seed27 | -23.066728591918945 | -2.3066728591918945 |
| seed127 | -19.736963272094727 | -1.9736963272094727 |
| seed227 | -20.966501235961914 | -2.0966501235961914 |
| ensemble | -22.66365687052409 | -2.266365687052409 |

**因此 δ_hi=0.1×cut 不能作为正的上侧余量照抄执行。** 它会把上端移到 cut 下方，甚至使区间为空。下一稿须定义非负 margin 带、用哪个头筛选、多头怎样合并及固定的来源尺度；`0.1*abs(cut)` 也不是未经说明即可代换的历史参数。

几何文件 SHA256：`080c069fa41f6eb7fbcea2e890873be462f8471b8ff2a039a8a30935674ca124`。
cut 文件 SHA256：`d4c391302d2d32c5d8813a45612b6f4203468e4b52bbd58233cbd6f274c84bbd`。

来源：[主几何](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/diagnostics_d1_d2_v1_20261022/assets/onboarding/run/evaluation/calibration/geometry.json)、[主 cut](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/diagnostics_d1_d2_v1_20261022/assets/onboarding/run/evaluation/calibration/cuts.json)、[密参考原协议](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/dense_reference_matrix_v1_20261027/PROTOCOL.md)。

### 正式前端的“流超时”

实际绑定是 TShark 字段解码、冻结事件/上下文规则、`BoundedNetfoundPrefix`、netFound E3 编码及后续头；不是 dpkt 扫包即完成特征提取。

- 参考上下文按 `(owner, capture_id, canonical_key)` 隔离。所核对的前缀状态没有常规 60/120 秒 idle timeout，也没有以 10 分钟重新开流的规则，不能填一个常见流工具的默认值。
- **10ms** 是同方向相邻包切 burst 的间隔：严格大于 `0.010s` 开新 burst。每方向保留最前 12 个 burst、每 burst 最前 6 包，合计最多 **144 包**。这不是会话超时。
- `flow()` 仍按 `frame.number` 对保留包排序，出现时间倒退会标记不可编码；原参考构建器还要求连续原帧并只接受 3,600/7,200 秒观察窗。它不能不经适配就接一个跨月、按新索引排序的历史输入。
- 原稿“起点差≤1s 合并”和“10分钟取最早一条”是**新增设计参数**，不是可从正式前端查出的既定值。逐字节相同的包也可能是合法重复事件，不能先删除再称原样复用前端；应保留真实上下文，仅对有出处的重复录入或候选身份去重。

来源：[前缀状态，第38行起](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/repo/ood/issue27ckda_d1_e3_embed_v1.py:38)、[正式引用，第31行起](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/repo/ood/legacy_cic2022_two_camera_semantic_probe_v1.py:31)、[参考输入合同，第279行起](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/repo/ood/constrained_onboarding_reference_v2.py:279)。

### HeimVision 历史材料

优先使用已经登记为正常 REFERENCE 的三份本地文件，日期是 **2021-10-06，不是 2018 年以前**：

| 文件 | 活动 | 首包 UTC | 末包 UTC |
|---|---|---|---|
| [189.pcap](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/legacy_reference_material_audit_v1_20260916/raw_selected/189.pcap) | LAN_WATCH | 2021-10-06 17:05:00.741864 | 2021-10-06 17:05:27.760204 |
| [190.pcap](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/legacy_reference_material_audit_v1_20260916/raw_selected/190.pcap) | LAN_WATCH | 2021-10-06 17:09:02.843962 | 2021-10-06 17:09:31.541785 |
| [191.pcap](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/legacy_reference_material_audit_v1_20260916/raw_selected/191.pcap) | LAN_WATCH | 2021-10-06 17:07:26.392050 | 2021-10-06 17:07:56.228605 |

已存当前表示的旧 A 参考元数据共 75 行，**HeimVision 只占 11 行（TCP 1、UDP 10）**，不是 75 行全部属于 HeimVision。可优先复用这 11 行对应的现存编码，但本轮没有把它们加入库。

同目录 183–188、192–193 也是本地历史材料，日期为 2021-10-12，尚未重新指定角色；不能因为“都比 11 月早”便整体当作新参考，特别是 192/193 已涉及原查询角色。原稿 `origin=HIST2016` 也不能统一用于 A。

这三份已登记参考只覆盖 **1 个日期**，因此“最后20%天留作 HIST-DEV”在 A 上没有自然的非空双分割。若向上取整会把唯一日期全部留出；其他舍入又可能使 HIST-DEV 为空。需要明确 A 的处理分支，不能默认已拥有可用历史开发集。

来源：[A 历史材料调查](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/targeted_normal_data_research_v1_20261030/A_LOCAL_REFERENCE_RESEARCH.json)、[旧 A 元数据](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/diagnostics_d1_d2_v1_20261022/assets/reference_scores/CIC_DEV_OLD_BANK.jsonl.gz)。

### 查询最早时间：全量与主视图分别列明

下表由已存 query JSONL 和原冻结窗口元数据汇总。所有时间为 **UTC**。主视图严格遵守原 timestamp 和同 capture 帧截止；未使用 query 行中遗留的旧 `reference_end` 推测窗口，未读取或生成新分数。

| 池/设备 | 全量已存查询最早时间 | 179700 观察期后主视图最早时间 |
|---|---|---|
| A / HeimVision | 2021-10-12 13:52:28.850539 | 2021-11-02 13:18:07.594432 |
| A / Eufy | 2021-10-13 14:35:42.834257 | 2021-11-02 13:15:04.252776 |
| B / Samsung | 2018-05-28 01:00:20.833267 | 2018-05-28 02:00:05.498145 |
| B / WEMO Power | 2018-05-28 01:02:42.214069 | 2018-05-28 02:01:16.755817 |
| B / TP Link | 2018-05-28 01:00:32.778922 | 2018-05-28 02:03:46.769048 |
| B / WEMO Motion | 2018-05-28 01:00:17.042467 | 2018-05-28 02:00:01.390648 |
| B / Netatmo | 2018-05-28 01:00:35.353417 | 2018-05-28 02:00:07.019274 |

原 B2 完整库截止为 A `2021-11-02 13:15:00.069330Z`、B `2018-05-28 02:00:01.090390Z`。新增历史材料早于查询，不等于现有完整合库可用时刻也能前移。保留旧主视图/全量视图及分母；旧查询早于完整库可用时刻的，仍应遵守回退规则。

B 原稿另加的 `<2018-01-01T00:00Z` 比上述 B 查询时间更早，已核验的三份 2016–2017 原始包符合这一时间条件。A 的 10 月 6 日已登记材料早于 A 全量最早查询。

**四台目标设备在源 FIT/CAL/S 中都不存在。** 所以它们的“源 S 最早时间”和“HeimVision 的源 FIT 最早时间”应填写 **N/A：无该设备**，不能填 0、无穷或别的设备时间。这里不存在待查出的隐藏时间数值。

源角色实际为：

| 折 | FIT / CAL 设备 | S 设备 | S 身份 |
|---|---|---|---|
| G0 | Amcrest、ArloQ、Atomi | Globe、Philips Hue、SimCam | G1 原 FIT，509,233 行 |
| G1 | Globe、Philips Hue、SimCam | Amcrest、ArloQ、Atomi | G0 原 FIT，108,675 行 |

源 S 各真实设备的最早时间如下；仅供角色与截止审计，不能冒充四台目标设备的时间：

| 所属 S | 设备 | 最早 UTC |
|---|---|---|
| G0 S | Globe Lamp | 2021-10-07 18:17:56.469403 |
| G0 S | Philips Hue Bridge | 2021-10-05 17:30:34.547789 |
| G0 S | SimCam | 2021-10-12 13:35:14.288587 |
| G1 S | Amcrest Camera | 2021-10-12 13:14:37.780338 |
| G1 S | ArloQ Camera | 2021-10-06 14:47:31.728651 |
| G1 S | Atomi Coffee Maker | 2021-10-13 13:25:07.684371 |

来源：[源角色绑定](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/reference_attack_competition_v1_20261029/validation/READONLY_ASSET_ACCEPTANCE.json)、[S 身份断言，第37行起](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/reference_attack_competition_v1_20261029/rac/assets.py:37)、[主视图筛选，第64行起](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/dense_reference_ab_stage_candidate_v1_20261028/src/metrics.py:64)。精确 epoch、首 UID/帧、行数和输入 SHA 见随附证据。

## 阻挡开工的具体问题及最小修订

| 问题 | 当前后果 | 下一稿必须落到的具体修改 |
|---|---|---|
| 四台目标设备不在源 FIT/CAL/S | 按目标设备 FIT 计算 δ、攻击 q10/q25/r_atk、Samsung 源组撤回、HIST-DEV 对 FIT 漂移比、以及在 HELD∩FIT 选择“B 目标设备 FPR 最低”的规则均没有数据 | 绑定真实存在的源历史正常材料及其设备/日期/角色；明确源上学什么、怎样迁移到目标。取消不存在的逐目标 FIT 参数。不能用 A/B 标签补这个缺口 |
| HELD∩FIT 就是当前 S | 把其中攻击复制到 CAL、用于禁区和三档选择，再用原 S 作“冻结后只看一次”，发生本轮内重复使用 | 若保留开发选择，事先冻结互斥 UID 角色及对应头/权重；若保留原 S，不能再把它用于本轮 CAL/禁区/选档。“已接触集确认”披露不能消除本轮角色冲突 |
| 只给目标补库，没说明源上对应干预 | own 支持按 `(partition,device,protocol)` 取库；增加 A/B 参考不会自动改变六台源设备的 own 支持，旧源库空通过检验不了新覆盖风险 | 给源侧同类历史扩充的实际文件清单与构建规则。若材料不足，直接列为该推进路径的材料阻断，不能继承旧 CAL 零撤回 |
| 筛选、去重和禁区仍不完整 | δ_hi 符号错误；δ 的目标 FIT 为空；r_atk 无目标攻击、无确定距离/正常邻居池；跨组件去重可能删第二组件 | 固定唯一非负分数带/头规则，明确距离及角色池、空集与不足5邻居处理、组件保留规则。不能把 1s/10min/500/2000/6000 或新分位数写成已有实测参数 |
| 历史输入尚未接上正式前端 | 现有索引保留原包号，但前缀内部按帧重排；旧入口有连续帧及1/2小时约束。先删重复包还会改变上下文 | 定义逻辑读取顺序与不可变原始包身份的对应，capture/session 边界和有依据的重复录入处理；冻结选择规则后再实现适配。原始包、时间和审计定位不改写 |
| 合库、HIST-DEV、保护和停止合同不闭合 | `reference_end` 不一致会报错；A 只有1个参考日期；缺逐设备 FPR 目标及多头保护范围；“任一源失败即停”与“三档中择优”冲突；Samsung 回退还产生额外候选 | 写清完整库截止、A 的留出分支、池与逐设备 FPR/召回目标、RAW累计撤回的seed/ensemble范围。固定源失败是在候选级还是阶段级，回退是否允许及其重校准，不得事后改规则 |
| 4h/8GiB/5GiB 未绑定真实工作量 | dpkt 元数据扫描不是 TShark+E3 编码；四进程模型驻留、候选前向及三档距离/校准均未计清，S 又同时出现在两阶段 | 给扫描包数、候选编码上限、各阶段距离对数/缓存策略、模型进程数与磁盘上限；预算内不足即有明确停止结果。本轮不能用未经授权的试跑填 ETA |

这里还应纠正 PASS 文本：池 FPR≤2% 可以作为当前约2%的目标，但原稿遗漏逐设备 FPR≤2% 的目标，以及源/目标各 seed 和 ensemble 的检查范围；不能只保留设备召回撤回门就当作完整验收。`IMPROVED_NOT_PASS` 若定义下降≥0.5pp，应使用 B FPR≤9.019653949%，不是严格小于该值。

**我的建议是保留“历史正常参考＋当前密库”这个方向，把下一稿收敛为一个有真实源材料绑定的候选。** 先解决空的 FIT/选档集和 S 重用，删去无法绑定的筛选规则；不继续在三档、Samsung 回退和多种禁区上叠加分支。若实际找不到能检验同类历史扩充的源材料，应明确报告“既定先源门、后一次 A/B 路径尚不具备条件”，而不是用当前六台源设备的旧参考通过来放行。

本次已填完能够只读确定的实际值。δ、r_atk、候选保留量及完整 E3 时间没有现成合法数值，其中一些按 V1 定义根本无定义；编造数字不会使方案可执行。性能结论仍为未知，当前不运行；这与用户本轮只授权复核完全一致。

## 复核证据

[机器证据](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/mainline_docs/collab/20261031_well_history_normal_reference_execution_plan_review_evidence_codex.json)记录了19个已读取输入的前后 SHA 一致、完整查询/主视图最早时间、源角色计数、残留误报聚合及 HeimVision 现存组件身份。原计划 SHA 保持不变。原始 PCAP 和编码数组未重写，科学代码未修改。
