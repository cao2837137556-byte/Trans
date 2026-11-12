# 主张—证据映射（Codex，2026-11-08）

## 2026-11-12：当前主结果与新增证据

当前正文以完整库MLP p4为主结果，身份绑定见 `paper_main_configuration_p4_codex_20261112.json`。以下较早p3计数均保留为历史，不能回填当前p4主表。

|当前主张|直接证据|正文与范围|
|---|---|---|
|主系统CIC正常18/96041、攻击79050/79056；UNSW正常130/74444、攻击72543/72553；Edge正常0/20000、HTTP19958/20000、UDP19732/20000|`runs/p4_tabm_acceptance_v1_20261111/controls/METRICS.json`，P4_MAIN、ensemble、相应视图、ALL|表2/4/6；全头/视图普通/加权/HT见补充S3；零误报只限本次选中查询集成|
|同基准尺度p4下三空间保全：Edge HTTP多2976，正常均0；CIC多44，正常均18；UNSW多34正常、攻击不变|controls的P4_2D_BASE/P4_MAIN指标与配对|表3及4.3；不能延用p3的2296/7|
|p4旁路收益：UNSW攻击+428、正常+28，Edge HTTP+5|controls的P4_MAIN/P4_GUARD_OFF|表7/C3；不是p3的295|
|TabM模块迁移有收益但不统一优于主方法|`tabm_p4/METRICS.json`和`PAIRED_CHANGES.json`；TABM_RAW、TABM_3D_SELF_P4及MLP-self对照|表9、补充S4；原生概率域和自身尺度，不自动替换MLP|
|参考库规模不变，4936只是冗余候选|HISTORY_LINEAGE_COUNTS_CORRECTED、LINEAGE_METADATA_CORRECTION及FORMAL_ACCEPTANCE|3.5、讨论、附录D；未删库/压缩未验证；开发策略与逐点规则分别披露|

本次原始指标和配对共14,720/14,720条的本地一致性核对摘要见 `p4_tabm_writing_audit_codex_20261112.json`；保留原回执和未知的压缩后表现。

## 2026-11-11：最终3D保护与指数证据更新

|主张|直接证据|范围与正文位置|
|---|---|---|
|保护在当前3D中仍能保留攻击告警，并有正常误报代价|`runs/paper_reading_ablations_acceptance_v1_20261111/METRICS.json`与`PAIRED_CHANGES.json`：BASE/GUARD_OFF，UNSW主视图ensemble攻击+295、正常+28；Edge HTTP+5|表7、附录C3；不是新增RAW检测能力，CIC本批无变化|
|p1→p3减少误报，同时存在攻击代价|同目录：P1/BASE，CIC/UNSW/Edge正常−9/−2086/−412；Edge HTTP−3；CIC单头27/127攻击−3/−1|表8、附录C1/C2；集成攻击不变不等于所有种子无代价|
|p4在部分条件下更低误报，但不能称整体更优|BASE/P4：UNSW正常−80，Edge正常−24；CIC攻击−6且正常不变，Edge 227头HTTP−1|表8；Edge 0/20,000仅选中查询的集成，单头正常1/28/0|

完整性与摘要核对见 `guard_exponent_integration_codex_20261111.md`；两项从待补改为已完成，冻结方法、参数及原Edge外部角色不变。以下贡献框架和旧映射保留历史上下文。

## 2026-11-11：贡献叙事与当前正文位置

本次加强已有设计与证据的连接，不增加“首次、独有、最优、零攻击损失”等主张。下方2026-11-08映射保留原始记录；当前正文的术语、完整数值和新增基线以各后续核对文件为准。

|叙事作用|当前可写的内容|正文落点与证据|
|---|---|---|
|研究问题|固定源阈值下，正常历史能否减轻现场告警负担，同时限制额外攻击撤警？|引言与2.1；基础/完整系统同查询比较；排序与工作点分别报告|
|核心设计|设备上下文既参与判别，又成为正常参考减分的必要相容条件；同一条参考三空间联合匹配，查询需两个不同组件提供支持|引言贡献1、2.1、2.2结尾及2.4；冻结geometry/support定义与T2|
|机制分工|历史提供覆盖，尺度与支持核控制扣分幅度，上下文约束参考相容性|引言贡献2、2.3–2.6、4.3；T4及同库2×2，不能把三空间约束本身说成降低误报|
|最直接的上下文证据|同库同b尺度，Edge多保留2,296条HTTP告警，正常告警多7条|T2的2D_OLD与3D_OLD；是特定冻结条件下的收益与代价，不是普适安全保证|
|结构性质|同尺度/阈值条件下告警集合嵌套，约束方向但不保证额外攻击损失为0|命题1；数学推论与实际性能幅度分开|
|评价与用途|按源训练、源校准、合法正常参考及评价查询分工；开发评估与Edge外部角色分别披露|重写3.1；既有provenance_audit及附录B，不把规范数据划分单独包装成算法创新|

netFound权重、输入维数、小型分类头、分位数统计和具体参数值按复用组件或设计约定披露，不逐项宣称独立创新。双组件规则的独立必要性及现代检测头迁移仍待补；最终3D保护与指数的作用已由本文件顶部新增证据覆盖，其他参数不外推为已经最优。核心贡献的文献新颖性强度还需最接近工作逐项比较，机制可解释或效果改善本身不等于已完成新颖性证明。

## 原始主张—证据记录

路径以仓库根目录为基准。F=`runs/paper_results_freeze_v1_20261107/`；G=`runs/same_bank_context_v6_20261106/`；D=`runs/device_context_evaluation_v1_20261105/`。状态“已证实”仅指该行限定的本地封存证据，不代表普适结论或新独立复现实验。

ALL_METRICS按`pool,view,method,head,group`唯一定位；数值字段为`rows,alarm_count,sample_rate,hierarchical_rate`，Edge另有`HT_rate`。百分数为率乘100。原始来源为G/DIAGNOSE_RESULT.json的`pools[pool].views[view][method][head][group]`，由F/build_results.py:51起读取、校验并生成。前端来源见该脚本104–108行。

|主张|证据文件/字段或代码|模型、视图、头与权重|限制|状态|
|---|---|---|---|---|
|当前方法是790维融合头＋完整合法历史参考＋3D_OLD|F/METHOD_FREEZE.json：method、heads、correction、geometry、references|固定27/127/227；OLD仅扣分尺度|不是旧782分类器；不是旧少样本LR|已证实|
|A正常18/96041、攻击79056/79056；B正常210/74444、攻击72543/72553|F/ALL_METRICS.json；F/T1_MAIN.md|C5_3D_OLD；post_window_primary；ensemble；普通率|已消费开发数据；查询级|已证实|
|B相对原C5减少1089条正常误报，攻击数不变|同上，method=C5_FROZEN与C5_3D_OLD|相同UID、视图、阈值、ensemble；普通计数|不是外部检测器对比|已证实|
|Edge最终正常24/20000、HTTP19958/20000、UDP19732/20000|同上，pool=EDGE、view=full|ensemble；普通率0.12%、99.79%、98.66%|Edge未参与开发；跨数据集外部评价；非事件率|已证实|
|Edge正常加权1.220180%，HT约0.017457%|同上hierarchical_rate、HT_rate；D/reporting.py:_rate|同一方法/头/视图，不同权重|不能与0.12%混写；HT是抽样展开点估计|已证实|
|同库OLD尺度三维比二维多保住2296条HTTP，正常误报增加7条|F/T2_GEOMETRY_SCALE_ABLATION.md；ALL_METRICS对应2D_OLD/3D_OLD|Edge full ensemble普通计数；其余固定|三维保护不等于三维降低误报；不推论所有域|已证实|
|仅三维加当前尺度不足以解决误报|同表3D_FUSION：B2.153296%、Edge5.815%|B主视图、Edge full；ensemble普通率|收益是组合，不归因单因素|已证实|
|融合输入改善Edge RAW攻击覆盖，但并非处处更好|F/FRONTEND_RAW_METRICS.json；T3；D/AB_RESULT.json、EDGE_RESULT.json|OLD782/REFIT782/STATS8/FUSION790各自源CAL阈值；ensemble RAW|B正常RAW从旧782的39.898447%变为53.894202%；不能声称所有指标改善|已证实|
|完整历史库显著影响B误报|F/T4_REFERENCE_COVERAGE.md；G与runs/context_geometry_attribution_v2_20261106/DIAGNOSE_RESULT.json|固定790/OLD；3D：22772→210；B主视图ensemble普通计数|跨运行覆盖对照；不能称随机实验，也不能把历史资料当免费信息|已证实（描述性）|
|双组件支持是不同component_id，不是两个最近包|G/geometry.py:legal_indices、evaluate；repo/ood/constrained_onboarding_core_v3.py:_second_distinct|同partition/device/protocol合法库；组件内取最小，再跨组件取第二小|组件不同不证明统计独立|已证实实现|
|上下文是当前包计入的1/10秒统计|G/stream_core.py:Engine.advance、features；D/TRAINING_SPEC_FROZEN.json|逻辑capture/设备/协议；前缀时钟|B逻辑索引重放、A跨capture重置；非统一原PCAP块序|已证实实现及冻结约束|
|最终修正不新增RAW告警|D/common.py:correction、four；F/ALL_METRICS.json:added_vs_RAW|每头扣非负项后float64均值；阈值固定|Edge RAW HTTP99.83%、UDP98.66%是该修正可达上限；最终HTTP还撤8条|已证实实现与指标|
|并非全口径达标|F/S1_FULL_AND_SEEDS.md、S2_DEVICE_BREAKDOWN.md；METHOD_FREEZE.limitations|A full ensemble加权5.412342%；B WEMO full普通2.31%；Edge seed127加权3.610879%|不能删seed/设备/建档期；ensemble非第四独立种子|已证实反例|
|优于六个外部基线|当前基线EXECUTION_CARD；待各方法COMPLETE/EVALUATE、SHA、UID、校准及验收|共享790 RAW与完整系统分开；标签/参考权限披露|本轮未核验最终成绩；不能据启动快照排名|待核验|
|双组件规则本身优于简单近邻|需匹配同库/尺度/守卫/阈值的机制对照|仅T2不能隔离双组件规则的作用|不能用现有六个RAW基线替代这项机制证据|缺实验（若主张此点）|
|未见域泛化、显著优越、在线轻量、事件及时发现|F/EXPERIMENT_ROADMAP.md非基线缺口|分别需要未消费数据、相关性统计、全链路资源、完整事件序列|现有缓存计时、查询数均不足|缺相应证据|
|算法新颖或SOTA|需相关原论文/官方实现与同口径最终比较|已研读写作范例；尚未完成针对本方法的新颖性文献对照|候选贡献不是新颖性定论，不虚构引用|待核验|

## 需明确的来源差异

1. D/TRAINING_SPEC_FROZEN.json的“新头采用自身尺度”是早期前端/C5评价协议；论文最终冻结明确选OLD尺度。正文以F/METHOD_FREEZE.json为准，说明后处理开发选择，不能把旧训练规范写成最终扣分规则。
2. PAPER_RESULTS草稿中的“显著改善”本轮收窄成“观察到改善/减少具体计数”；没有统计检验，不使用统计显著性措辞。
3. 旧EXPERIMENT_ROADMAP的基线名单被当前六方法规则替代；其统计、外部确认和成本缺口仍适用。ModernNCA不恢复。
4. 归档支持数组包含历史守卫存储差异，G/support_contract.py用于复现存储语义；最终分数守卫统一应用于所有设备，不把历史四设备存储规则写成当前方法特例。

## Edge数据角色（2026-11-08）

Edge未参与开发，用于跨数据集外部评价；A/B用于开发评价。这是论文统一口径，不列为争议或待核验事项。已同步纠正接手导航、论文结果包、生成器与相关协作说明中的旧错误定性。模型、阈值、参考资格、实验指标及既有运行事实均不因此改变。
