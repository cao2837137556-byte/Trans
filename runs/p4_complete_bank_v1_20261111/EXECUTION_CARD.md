# 完整库p4新版：六控制配置、TabM衔接与来源审计

用户已选择完整库p4作为新版主结果，旧p3版本和结果永久保留。已有P4和RAW只作身份/算术复现及指标引用，不重新训练、编码或重做原敏感性实验。

六新增配置：完整库2D自身尺度、完整库2D基准b、完整库3D自身尺度、完整库3D基准b保护关闭、两小时2D基准b、两小时3D基准b。全部p4、λ=.25；除指定因素外模型/半径/资格/阈值/查询/权重固定。两小时是覆盖消融；Edge同库结果以别名复用，先核对支持与判定一致。

原始full support2/support3来自same_bank_context_v6，commissioning support2/support3来自context_geometry_attribution_v2的各池ATTRIBUTION缓存。各自SHA/UID/RAW/原p3分数判定及指标必须通过。不得用历史有效零支持关保护，不从完整库简单删点替代两小时支持。缺少任一真实缓存停止并报告，不自动重算距离。

控制作业1CPU8GiB1小时；先全三池冻结p3基准及既有P4指标复现，再六控制与配对统计，输出全部头/视图/分组、误报和攻击撤警、缓存SHA、六条CIC集成攻击原标签/时间/分数裕量/扣分明细。同步只读统计最终历史参考的来源、数量及保守的严格等价候选；不改变库、不运行压缩绩效实验。

TabM作业另用1CPU8GiB1小时，afterok依赖原p3作业183549及控制作业。读取已保存原生概率分数与自身FIT尺度/CAL阈值，复现p3修正后只追加p4；无新前向或训练、不裁剪、不套用MLP尺度。输出新版五行与保留的p3桥接行。原GPU任务不取消、不热改。

两项独立目录results/controls、results/tabm分别COMPLETE并自动取回重要JSON/CSV/Markdown，完整分数、查询元数据和改变UID gzip留超算。仅提交正常并能看到进度即结束对话，不持续轮询。

标准库resource与Slurm记录资源，不依赖/usr/bin/time。P4_METHOD.json记录本次后验选择日期、原p3冻结及原P4验收来源；新机制对照完成前不宣称全套已验收。参考发展过程及压缩提议见REFERENCE_DECISION_AUDIT.md。
