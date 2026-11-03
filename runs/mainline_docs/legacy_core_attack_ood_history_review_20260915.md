# 旧主线攻击与 OOD 能力：历史复盘与可复用判断

日期：2026-09-15。性质：只读历史补学后的知识记录，不是新方案冻结或实验授权。

本次读了 20 份核心专题材料，覆盖早期 few-shot、C1/AfterImage、正常证据抑制、
过程监督、51D 损失与控制、有限 episode 诊断，以及 E3/P2 的形成。入口为
`mainline_workflow_and_hpc_continuity_20260909.md` 与实验索引；另定向读取了
CKBW 讨论简报中的口径更正。全文的 [Sxx] 对应末尾索引，来源字节身份保存在同 stem
`.sources.json`。没有打开原始流量、数组、模型或新封闭评估，没有执行历史命令。

## 先把主线说清楚

项目反复遇到的核心冲突一直是：**正常设备换了环境，容易被当成攻击；为了放过这些
正常流量而扩大正常区，又会放过部分攻击。** 这并不是直到换前端才出现的问题。
早期 few-shot 已证明少量攻击监督能明显改善某些低误报工作点；后来更严格的跨源、
跨设备和 future-query 检验暴露了这个收益的边界。[S01–S03]

历史并非一直没有进展，也不能只按“又换了一次模型”理解：

1. few-shot 证明了**学习目标对齐**有用，但未证明任意新攻击泛化。
2. CKBL 证明部分表示有跨源排序信息，但**排序好不等于一个阈值能跨环境工作**。
3. CKBP 的主臂出现确定性的冷启动假象；CKBQ 修复后，四个 OOD 池的正常证据
   改善才成为可信开发信号，但攻击保留仍失败。
4. CKBR/BS 阻止了把晚于既定 query 的同抓包数据纳入训练；CKBT 则提供了真正
   不同文件来源的机制监督。两者是数据资格成果，不是能力提升结果。
5. CKBW 表明“正常抑制很强”与“攻击保留很好”不能拆开报喜。E3/P2 后来确实把
   攻击与 OOD 两轴一起向前推进，是目前值得保留的资产；它仍没有解决全部 OOD 池。

当前旧系统是 **E3/netFound + 原 normalizer + P2 + 原阈值**。历史 C1、原始
KitNET/dA、raw AfterImage115、51D 过程头都不能不加名字地简称为同一个“旧模型”。
本文不替换最新交接控制面板，也不恢复历史中已经结束的下一步指令。

## 1. 早期 few-shot：证明目标对齐，未证明普适泛化

**假设与干预。** 无监督异常分数在压低正常 OOD 误报后检出塌陷，可能是训练目标
没有对齐 attack-vs-benign 的部署目标。在冻结的 original100 表示上训练 L2 logistic
head，正类只取 16/32 个高纯攻击样本，负类为 ID benign + OOD benign。[S01,S02]

**数据角色。** 16/32-shot 仅是攻击正样本预算，不是全部训练或评估规模。该历史切分
包含 ID train 8,000、OOD train 8,000；攻击训练候选池 4,122、攻击评估 1,375，
OOD 评估 10,000。五个正样本抽取 seed 为 42–46；guarded 阈值只使用 ID calibration
和 OOD validation，final OOD eval 不选阈值。[S02]

**结果。** 同一早期问题设置中，dA 在 guarded 工作点的攻击检出为 0.2909%；
original100 16-shot 的五 seed 平均检出为 96.7564%，最差为 91.4182%，OOD alarm
最大 0.92%。这是目标对齐的明确正信号。32-shot 平均检出反而为 94.0655%，
不能从预算增大推出单调收益。[S01]

**保留与限制。** 简单头也可以承载重要学习机制；复杂程度不决定论文价值。
dA 不用攻击标签，不能写成同监督信息下被 LR 公平击败。source-rich 在特定困难
holdout 更稳，未平均全面胜过 original100；反向时间 holdout 是鲁棒性诊断，
不是前向在线部署证据。上述成功不是今天 E3/P2 数据池上的可直接横比结果，更不是
完全未见攻击族的保证。早期 source-rich 分支原始运行工件本次未重审。[S02]

## 2. C1、事件上下文与 CKBL：信息和可用工作点开始分开

**假设与干预。** C1 是 CKAI 的 `C1_cicflow_style_only_histgb`，在汇总/Level-1
问题上有攻击保留和正常误报改善；严格排除设备家族后，stream 与 hydraulic 仍可
接近全池报警。于是历史上试过事件特征、episode pooling、E/R/H attention 与
成熟 TGN，再用 CKBL 专门检查输入信息，而不继续只换后端。[S03,S04]

**结果与角色。** CKBL 全源诊断只使用 8,671 个合法 fit 行，其中攻击 support 385、
正常 8,286。25 个外层 fold 中，207D C1 视图的未见攻击家族 origin 平均 AUROC
为 0.9176，原 TGN9 为 0.7941；69D 时序视图没有超过真正改变过历史顺序的置换
控制。合法内层阈值在外层仍经常产生很高误报；十个未见家族 fold 只有四个具有
完整合法内层阈值，不能只拿 AUROC 写成可部署低误报。[S04]

**复用判断。** “表示毫无信息”被这个诊断削弱；“已解决跨源校准”则没有成立。
无 label/future 泄漏的上下文也可能没有新增预测收益。episode pooling 还曾把
385 个正包压缩为约 42 个正 episode，监督数量和单位随之改变，不能当免费替换。
本次 C1 起源读取到当时交接及 CKBL 原结果，没有独立重建 CKAI 原始实验。[S03,S04]

## 3. CKBM / CKBO：更强分类头和更多正常来源并不自动安全

**CKBM。** 换成成熟 TabM/ExtraTrees，加 source-relative calibration。训练正常收敛，
385 条攻击 support 均被使用；主臂 stream 仍为 99.6% hard alarm，UDP Scan
召回从该次 C1 的 100% 降至 28.32%。同时发现实现只排除当前 held family，
没有在所有 fit/select 中排除两个永久 development canary，因此只能保留为负向
诊断，不能作为严格独立正向 benchmark。[S05]

**CKBO。** 修正全 canary 隔离后，比较成熟 raw AfterImage115、有无正常辅助源、
有无确定性多尺度 contrast。辅助正常 fit/select 按 11/5 个 source 分开；
385 个 support-train、69 个合法 support-val 与全部原始分母保留。raw115+Aux
比 raw115-NoAux 对 predictive/hydraulic 更好，但多损失 1.825 pp 整体攻击召回；
stream 仍约 99.7%。raw115+Aux 在四个 OOD 池及攻击保留上都不差于 contrast+Aux，
所以 contrast 不是有证据支持的创新增益。[S06]

**复用判断。** 不能再将“训练没充分跑”“只缺更复杂的头”作为默认解释；低训练损失
与合法 select 近零误报可以共存于跨域失败。新增正常源有真实但局部的收益，
是否覆盖目标变化比新增多少行更重要。CKBM 与 CKBO 的 C1 数字来自不同清理后的
范围/合同，不得用 99.9795% 对 91.300% 拼成同一模型突然退化的时间曲线。[S05,S06]

## 4. CKBP：低 OOD 误报中的冷启动假象

**假设与干预。** 以 raw AfterImage115 的正常证据，加有限样本 conformal rank 和
受限 source-local 校准，未知/冷状态 fail-closed；希望安全撤回 C1 告警。[S07]

**失败机制。** 69 个合法 support-val 分布在三个 source，分别只有 23/6/40 行，
全部落在每源 64 行 burn-in 内，哨兵攻击分数都为 1。选出的阈值也是 1；
而正常运行后的有限样本攻击分数严格小于 1。因此正常运行后几乎所有攻击和正常
都被放过，整体攻击召回从 91.2997% 降至 0.1451%。漂亮 OOD 数字基本就是冷启动
残留告警数，不能作为自适应正常识别的成功。[S07]

**另外的问题。** 状态只由被冻结评分的 target 行更新；攻击实验流中几乎全是攻击，
正常 OOD 实验流中全是正常。虽然程序不读 label，这个人为按类别形成的历史也不是
部署等价的无标签混合流。[S07]

**可复用证据。** 不依赖冷状态的 M1 static-normal 对照有真正跨家族正常信号，
但损失 9.0498 pp 整体攻击召回。必须把“操作兜底状态”与“可学习证据分数”分开，
阈值验证需有真正运行状态的攻击；无标签更新不等于数据使用天然合法或部署等价。

## 5. CKBQ：修复后确有 OOD 改善，攻击损失仍否决主臂

**干预与隔离。** 静态正常证据 + 32-event MiniRocket/Ridge 时序共识 + C1 shield。
最初两个作业在训练前停止，因为审计错误要求 source 内角色必须连续。修复依据
既有 immutable row-role split，逐 target 排除窗口内后续阶段的 target，不改385/69
数据。3,583-target 回归跳过283个禁止窗口出现，禁止/未来事件使用为0。[S08]

**真实结果。** 后来正式计算完成，只有尾部 validator 的 warm-up 常量和 hash 语义
错误，修复尾部后结果有效，没有重训。四池 OOD 从 C1 的
100/100/100/72.367% 降为 8.1/57.589/29.7/45.7%
（依次 IP-camera、predictive、stream、hydraulic），这次不是冷启动假象。
但整体攻击损失6.945 pp，future-query损失12.639 pp，正式判决NO_GO。[S09]

**为什么不能只调阈值。** 选定的 shield 高于所有 report C1 分数，实际保护为0；
时序分支只额外救回37条攻击、增加68条 hydraulic 误报，主臂近似静态分支。
该次授权的 post-hoc score-space 诊断在890个精确静态边界中无同时满足门槛的点。
这否定的是当前分数对/阈值族，不能外推成所有时序方法都无用。[S09]

**监督盲区。** 69/69 support-val 完美不能保护未覆盖的攻击机制和来源。385条
support 的十个完整标签包含 Merlin/Mirai C&C；不得把文中缺少裸标签
`C&C Communication` 简写成“所有C&C均未训练”。TCP Scan、Telnet、Reporting等
其他机制缺口及 future source 漂移需要分别处理。[S09,S12]

## 6. CKBR/BS / CKBT：训练资格与机制补充的真实进展

**CKBR/BS。** 想补TCP Scan和Telnet Brute Force；发现旧90,000行标签盘点把
role-local emitted ordinal 错当 processed-CSV row index，旧preferred PCAP又按
场景名猜配。唯一时间戳join纠正了身份。160条新候选特征全部物化正确，仍因来自
同一抓包且比既定query晚190/323秒而被全部隔离；500行间隔和行不重叠不够。[S10]

**CKBT。** 已有ToN conn.log + GroundTruth 精确一对一匹配，得到scan与brute-force
各2,000 fit、500 select。fit/select为不同文件，但没有声称campaign/host独立；
只是通用机制监督，不等价Gotham同名攻击标签。七个reserve日志当时零使用，
不是未触碰FINAL。没有记录log-emission时间，所以只能用于静态完成连接监督，
不能把完整连接字段放回首包时间用于因果memory。[S11]

**可复用判断。** 数据物化正确与训练合法是两道不同问题；完成连接的duration、
bytes、state不在连接开始时可用。“文件名normal”“GroundTruth没命中”“不同文件”
均不能单独推出正常标签或环境独立。历史4000/1000机制银行已经有用途，不能作为
今天刚找到的未使用新增数据。当前能否扩展原始支持由最新材料资格记录决定。

## 7. CKBW：共同训练正常与攻击早已做过，尾部损失未解决泛化

**假设与干预。** 接在统一51D因果过程缓存后，官方TabM单头学习攻击分数；
family/source balanced BCE + hard-tail pair margin + family-tail项，并以
normal/attack两个阈值对FrozenCKBQ作suppress/rescue。已有18,398 fit行：
14,013 normal +4,385 attack，后者含385 Gotham和4,000 ToN。
select为69攻击与7,000正常。不是纯few-shot，也不是只训练攻击。[S12]

**结果与正确口径。** 主臂四池OOD macro为0.153%左右，但future-query攻击
从C1的86.834%降到63.191%，损失23.64 pp；244,050整体攻击池则从91.30%
降到77.71%，损失13.59 pp。历史简报最前段曾把future召回与overall差值混写，
其后P0更正和结果分析已明确区分；不得重复混用。[S13；补充R03]

**关键约束。** rescue阈值选为1，合法select没有产生新增rescue；normal选择只面对
27个baseline-hard正常样本。69个support全保留与future失败并存。TailMargin
未显示比同数据普通CE更好的共同前沿，且对Merlin C&C更差。[S12,S13]

**保留与停止理由。** 拒绝把极低OOD误报单独当成果，也没有依据继续同一尾部损失
调参。该结果证明这套表示、监督覆盖、选择目标和控制形态失败；“合法cut没有
rescue”弱于“过程分数无攻击信息”。同样，有限两种损失不能证明任何头都学不到，
结果文档部分“信息不存在/根本盲区”的强因果措辞在今后决策中须按此收窄。

## 8. CKBY / CKCZ：记录级与episode上界各自只关闭有限路线

**CKBY。** benign-only DROCC在冻结51D表示上作容量诊断。primary OP-1的future
召回9.04%，四池OOD macro55.57%，两门失败。更关键的是实际选中epoch49的
纯CE warm-up模型，对抗阶段未被benign-only验证损失选中。[S14]

这提示选择准则可能奖励与方法目标不同的行为；单次轨迹不能证明对抗checkpoint
在任何条件下都“不可能被选中”，也不能用实际纯CE checkpoint裁决所有DROCC或
所有记录级模型的理论容量。当时停止继续51D换模型是边际收益判断，保留该NO_GO，
无需把旧文档的“解释彻底封死”作为今后不得思考的定理。

**CKCZ。** 没训练模型；检查endpoint-pair内C1与M7冲突的count、连续次数、比例、
跨度四个因果scalar。87,730个exact frontier点无满足联合门的点，甚至仅future
与OOD两门也无解。证明这个interaction key、四scalar、M7-OR-veto形态在当前数据
下无法靠一个cut破局；不证明一切session学习不可能。20,000个预期ToN metadata
缺失按合同不建episode状态，也限制外推。所有oracle cut仅诊断、不得选参。[S15]

## 9. CKDA：E3/P2提供共同改善，但其成功范围必须说准

**为什么转表示。** 在若干有限控制与episode信息上界失败后，CKDA查成熟流量
表示，先钉输入/权重/许可与资源，再作冻结表示probe。I1原拟域内自监督，E3为
netFound备用。ET-BERT/YaTC的兼容性门失败不是科学性能失败。[S16,S17]

**为什么实际用了E3。** D0全fit前缀的4,764,022 sessions/11,705,453 tokens
包含不能作为良性自监督的数据。D1对合法良性成员重普查仅8,735 sessions、
697,387 tokens；2,182,190是visible-packet上界，不是token数。I1未训练，E3
按预先冻结顺序开启，并非看结果后挑赢家。[S16–S18]

**学习内容与数据。** E3冻结，只在其768维表示加missing flag上训练P1线性头和
P2小MLP；P2为128隐藏单元、ReLU/Dropout0.1、50固定epoch。fit18,398，
select7,069；normalizer只拟合fit，阈值只选于69攻击/7000正常。fit/select中
11,640条missing保留分母，report中64,782条missing也保留。[S17–S20]

| 同次冻结probe | 整体攻击召回 | future-query召回 | 四池OOD macro |
|---|---:|---:|---:|
| P1 | 96.9392% | 96.2730% | 57.8889% |
| P2 | 97.3698% | 96.6786% | 29.8833% |

这是同次输入/数据下**攻击和OOD共同改善确实可能**的直接开发证据。P2在IP-camera
和stream上hard rate分别0.0667%和0.3333%，predictive42.8333%，hydraulic76.3%。
它通过多项门，但hydraulic比FrozenCKBQ恶化30.6 pp，所以判决仍为
`CKDA_D1_WEAK_ONLY / GO_D2=false`，不能被macro平均掩盖。[S20]

**保留限制。** 97.3698%是混合role整体召回，不是纯seen-attack；future-query
混合已知/未覆盖攻击族与来源变化，不是完全未见攻击族实验。不可编码行的zero
representation+missing flag属于另一条决策路径，不能凭整体率认定模型学会了这些
流量。当前恢复/增强比较应分开有效输入与missing处理。E3的外部预训练重叠仅有
`NO_KNOWN_OVERLAP`，不是已排除重叠；此时是本地应急运行，文档未完成其要求的
HPC确认。本次不连接HPC推断后续状态。[S17,S19,S20]

## 会影响后续方案的五条判断

1. **可行的共同改善有证据，稳定的四能力闭环没有证据。** 保留E3/P2是有依据的，
   不承诺小幅调参便能把seen attack推到99%并同步解决全部OOD。
2. **新机制要回答新增了什么可学习信息或更正确的训练约束。** balanced监督、
   正常+攻击联合训练、hard-tail margin、正常否决、有限时序聚合均已试过；
   只改名字不能当新路径。新环境内配对若要尝试，应说明与旧global-tail配对
   在数据身份、约束和可归因对照上的差异，不能仅凭新loss宣告创新。
3. **训练材料的难点是角色/标签/覆盖，不仅是条数。** 缺失机制、有限source和
   select运行状态都影响泛化；扩大已看数据不自动产生新环境或新设备证据。
4. **结构和分母需稳定比较。** 69个门控样本不能代替future/family检验；overall、
   future、完全未见family、有效输入覆盖必须分清。保留旧分母与失效样本，不能
   删除难例让继承看似成功，也不能将兜底全报算作学习能力。
5. **历史失败应该约束推断，不冻结未来思考。** 保留原NO_GO与封存状态；新路线
   可以质疑旧解释，但需新的可证伪假设及适用数据。是否开展由当前任务授权决定。

## 明确的泄漏/语义事件与继承边界

| 已记载事件 | 已验证事实 | 后续必须保留的区别 |
|---|---|---|
| CKBM跨canary使用 | 两个永久开发canary未在所有fit/select全局排除 | 合同实现漏项；本结果只作负诊断，不冒充独立正结果[S05] |
| CKBQ角色交错 | 行角色本身交错；错误源块断言在训练前停止，随后逐target隔离 | 是实现合同纠错，不是已发生的性能结果泄漏[S08] |
| CKBR错索引/猜PCAP | role-local ordinal非CSV原行号；scenario名不能证明映射 | 正确时间身份与标签必须先成立[S10] |
| CKBR晚时训练候选 |160条特征正确但晚于同capture既定query，全部隔离 | 检出了潜在反向时序训练；不能写成160条已经污染旧模型[S10] |
| CKBP历史组成 | 不读label，但状态由类别条件化target集合构成 | 数据生成语义可失真，不等同直接label特征泄漏[S07] |
| 反复查看开发池 | CKBW四OOD家族明确已被反复查看 | 可作机制诊断；不能再次称untouched FINAL[S12] |

历史中的`sealed_final_attack`是已披露报告池的角色名；cooler-motor等当时真正
未开的FINAL是不同边界。引用旧MD已披露数字不构成今天重新打开任何对应数组的
授权。当前任何新的CHECK/REPORT/FINAL资格，仍以最新角色台账为准。

## 已读材料与未覆盖部分

| ID | 本次读取的核心材料（相对本工作区） |
|---|---|
| S01 | `runs/original100_fewshot_official_control_2026-04-22/summary.md` |
| S02 | `runs/prism_handoffs/handoff_fewshot_target_alignment_2026-04-25.md` |
| S03 | `runs/mainline_docs/openworld_handoff_20260711.md` |
| S04 | `runs/mainline_docs/ckbl_fullsource_seed27_formal_result_20260714.md` |
| S05 | `runs/mainline_docs/ckbm_seed27_formal_result_20260714.md` |
| S06 | `runs/mainline_docs/ckbo_seed27_formal_result_20260715.md` |
| S07 | `runs/mainline_docs/ckbp_seed27_result_and_gate_diagnosis_20260717.md` |
| S08 | `runs/mainline_docs/ckbq_target_scope_correction_20260718.md` |
| S09 | `runs/mainline_docs/ckbq_seed27_formal_result_20260721.md` |
| S10 | `runs/mainline_docs/ckbr_ckbs_support_v2_and_process_frontend_gate_20260722.md` |
| S11 | `runs/mainline_docs/ckbt_toniot_aux_process_support_gate_20260722.md` |
| S12 | `runs/mainline_docs/ckbw_tail_margin_dual_control_preregistered_20260803.md` |
| S13 | `runs/mainline_docs/ckbw_seed27_result_analysis_20260807.md` |
| S14 | `runs/mainline_docs/ckby_drocc_seed27_result_20260809.md` |
| S15 | `runs/mainline_docs/ckcz_seed27_formal_result_20260810.md` |
| S16 | `runs/mainline_docs/ckda_d0_result_20260811.md` |
| S17 | `runs/mainline_docs/ckda_d1_frozen_representation_probe_preregistered_20260812.md`（问题/角色、I1门、E3/probe/阈值及判决章节） |
| S18 | `runs/mainline_docs/ckda_d1_local_precompute_result_20260814.md` |
| S19 | `runs/mainline_docs/ckda_d1_local_l1_codex_review_20260816.md` |
| S20 | `runs/mainline_docs/ckda_d1_local_l2_result_codex_review_20260817.md` |

补充导航：R01为工作流接续索引，R02为实验map有关段落，R03为CKBW briefing
第1轮P0更正及后续路由讨论；R03开头旧数字/强解释不覆盖后续纠错。

本记录不是全部半年历史的重新审计：早期每个unsupervised/TailReg/source-rich
分支、C1最初运行、CKBV每个恢复版本、CKDA以后局部修复及当前统一前端路线均未
逐一复验。缺失7月原任务历史已由另一份历史检索记录说明。数据数组与实际执行
未重放；来源MD的已披露数字不因此获得新的独立数值复算资格。超算经验沿用R01，
新使用前仍需核对当次环境，不继承旧任务的提交/重试许可。

当前用途：给后续E3/P2增强、数据支持与新设备入网设计提供已有反例和有效资产，
防止重复宣布“第一次尝试共同学习正常与攻击”，也防止把所有有限失败读成项目无解。
