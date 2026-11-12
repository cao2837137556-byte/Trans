# TabM检测头 × 冻结3D正常参考：首轮迁移比较

结果：准备固定五行，不重训，不晋升主方法。先复现TabM RAW及原生全指标，再计算参考修正。
影响：检验两个已固定训练流程在共同参考规则下的误报削减和攻击撤警，不把架构/损失差异全部隔离，不扩展指数/λ搜索。
下一步：同运行时真实小切片 → 已保存资产/UID核验 → 完整源FIT必要打分与原生RAW全量回算 → 自身尺度/CAL核验 → 五行全量配对评价。

## 五行

MLP-RAW；MLP-3D-SELF（本头源FIT尺度）；TabM-RAW；TabM-3D-SELF（本头源FIT尺度）；FROZEN-MAIN（原MLP、旧源尺度）。原有MLP三行按同库缓存复算及指标核验后复用。上一批保护/指数消融不重跑，仅复用其基准加载和原始support3核验代码。

TabM固定已训练三种子27/127/227，每个模型32成员攻击概率均值，原float32输出转float64，种子按固定顺序float64平均。三头各使用完整617908条源FIT、原device/activity/capture/session层级权重且正常/攻击各半，尺度为最低观测值累计质量定义的Q90−Q10；权重字节SHA必须与原MLP训练一致。读取MLP原FIT分数，按同权重重算三个自身尺度，须与原校准/冻结记录完全相同。

TabM原33147条源正常CAL分数独立校准每头及ensemble的1%加权误报阈值，必须复现已发布RAW阈值。集成阈值不平均单头阈值。完整FIT概率分数需要新增前向；已有源CAL及目标评分会用固定权重完整回算，最大概率误差预先限定2e-7且四头判定差必须0。原缓存分数仍作为五行表的原生RAW值，避免微小算术变化隐式改变既有结果；误差与原指标必须披露，失败即停止而不调阈值。

所有三池TabM RAW原指标（包括原生评价器的全部可用分组）通过后才进入参考修正。MLP-RAW/C5_3D_FUSION/C5_3D_OLD的468条既有指标须全部复现；MLP自身尺度修正分数与保存值逐位一致。

统一修正：p=3、λ=.25、SYN保护开、冻结原始support3、库/半径/双组件资格及UID顺序。TabM不用MLP logit尺度，不转logit，不裁剪；修正后允许负值且解释为判别分数。自身尺度0时修正自然退化RAW。保护命中保持RAW；各修正告警集合为自身RAW子集，不设绩效通过门、不删负面结果。

## 输入/输出与运行

复用baseline_remaining_three_v2_20261108的TabM模型与评价缓存、baseline_training_readiness_v6_20261107的FIT_X，以及same_bank_context_v6_20261106的原始support3。模型/分数/输入/查询SHA及新FIT权重/分数SHA记录在结果中。只生成新目录，不改老模型、缓存、部署或既有结果。

申请与原TabM一致的RTX4090一张、8CPU、16GiB、2小时上限；实际阶段计时和Python/Slurm内存独立记录，不依赖可选/usr/bin/time。不宣称这是已实测耗时或端到端吞吐。真实原包小切片包含解码、编码、距离/支持核验；与本次主要缓存重放分别记账。

results包括：SOURCE_FIT_IDENTITY、TABM_SOURCE_CALIBRATION（q10/q90/scale/cuts）、TABM_RAW_REPRODUCTION、TABM_NATIVE_METRIC_REPRODUCTION、SCALE_AND_THRESHOLD_FREEZE、五行METRICS.json/csv、PAIRED_CHANGES.json/csv、CHANGED_UID_MANIFEST、EVALUATION_GATES、RESULT_READOUT、RUN_COMPLETE。artifacts中的完整打分、五行分数和改变UID gzip留超算，只取小汇总。

全部四头、A/B full及post_window_primary、Edge原选中查询；普通/层级加权/HT及保护/设备/活动分组全部保留。既有原始RAW评分与UID逐项对应，不能单看均值阈值或AUROC。补充跨头配对表只作两个固定系统比较，不作纯架构因果推断。

该候选在既有结果已知后追加，必须如实披露，不把它变成新的独立外部确认。上游材料和本实验历史对Edge开发角色有表述差异；本任务只记录这个差异，不静默改写原冻结角色或据本次目标成绩作选择。主方法替换另行讨论。
