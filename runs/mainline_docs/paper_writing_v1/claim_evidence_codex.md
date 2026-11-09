# 主张—证据映射（Codex，2026-11-08）

路径以仓库根目录为基准。F=`runs/paper_results_freeze_v1_20261107/`；G=`runs/same_bank_context_v6_20261106/`；D=`runs/device_context_evaluation_v1_20261105/`。状态“已证实”仅指该行限定的本地封存证据，不代表普适结论或新独立复现实验。

ALL_METRICS按`pool,view,method,head,group`唯一定位；数值字段为`rows,alarm_count,sample_rate,hierarchical_rate`，Edge另有`HT_rate`。百分数为率乘100。原始来源为G/DIAGNOSE_RESULT.json的`pools[pool].views[view][method][head][group]`，由F/build_results.py:51起读取、校验并生成。前端来源见该脚本104–108行。

|主张|证据文件/字段或代码|模型、视图、头与权重|限制|状态|
|---|---|---|---|---|
|当前方法是790维融合头＋完整合法历史参考＋3D_OLD|F/METHOD_FREEZE.json：method、heads、correction、geometry、references|固定27/127/227；OLD仅扣分尺度|不是旧782分类器；不是旧少样本LR|已证实|
|A正常18/96041、攻击79056/79056；B正常210/74444、攻击72543/72553|F/ALL_METRICS.json；F/T1_MAIN.md|C5_3D_OLD；post_window_primary；ensemble；普通率|已消费开发数据；查询级|已证实|
|B相对原C5减少1089条正常误报，攻击数不变|同上，method=C5_FROZEN与C5_3D_OLD|相同UID、视图、阈值、ensemble；普通计数|不是外部检测器对比|已证实|
|Edge最终正常24/20000、HTTP19958/20000、UDP19732/20000|同上，pool=EDGE、view=full|ensemble；普通率0.12%、99.79%、98.66%|用户明确Edge未参与开发；盲测流程待核对；非事件率|已证实|
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
|算法新颖或SOTA|需相关原论文/官方实现与同口径最终比较|本轮未进行外部文献检索|候选贡献不是新颖性定论，不虚构引用|待核验|

## 需明确的来源差异

1. D/TRAINING_SPEC_FROZEN.json的“新头采用自身尺度”是早期前端/C5评价协议；论文最终冻结明确选OLD尺度。正文以F/METHOD_FREEZE.json为准，说明后处理开发选择，不能把旧训练规范写成最终扣分规则。
2. PAPER_RESULTS草稿中的“显著改善”本轮收窄成“观察到改善/减少具体计数”；没有统计检验，不使用统计显著性措辞。
3. 旧EXPERIMENT_ROADMAP的基线名单被当前六方法规则替代；其统计、外部确认和成本缺口仍适用。ModernNCA不恢复。
4. 归档支持数组包含历史守卫存储差异，G/support_contract.py用于复现存储语义；最终分数守卫统一应用于所有设备，不把历史四设备存储规则写成当前方法特例。

## Edge角色纠正（2026-11-08）

用户明确指出Edge未参与开发。本轮撤回先前将A/B/Edge一并定性为开发数据的表述。该旧判断来自接手包、论文冻结selection_scope及同库验收中的文字结论，本写作对话没有独立验证其因果时间线。另一方面，D/TRAINING_SPEC_FROZEN.json:training.model_selection明确写明none; no Edge/CIC_DEV/UNSW_DEV tuning。该字段支持训练/选模规则，但单独不能证明完整方法设计的时间线。当前正文按用户更正将Edge列为跨数据集外部评价；历史文件保持原样，记录冲突，不修改冻结工件。若进一步使用“独立盲测”，应核对方法/规则冻结时间、首次查看Edge结果时间，以及是否存在据Edge反馈改变输入、规则或最终版本的具体记录；不能仅以评价多次、事后诊断或正常参考访问推出参与开发。
