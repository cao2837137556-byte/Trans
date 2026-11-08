# 当前状态

1. **方法**：FUSION790＋完整历史正常参考＋C5_3D_OLD冻结，主模型不改。
2. **最新验收**：182752 COMPLETED/0:0，50:29、峰值3.588GiB、135项检查；八阶段工程PASS，无新作业，大工件留超算。
3. **已完成**：新源划分457120/160788行，六设备两类覆盖、会话/组件隔离通过；DTE/SLAD/TabM整轮及全验证计时通过，TabM约42:26+2:40。资源探针分数有训练重叠，不用于调参/论文指标。
4. **未放行**：5个协议切片、52个活动切片单侧缺失（可重叠），ArloQ TCP仅验证、4设备UDP仅训练。先审独立组数，协议优先分层；单组无法双侧时保留隔离并设计交叉验证/披露限制。不得随机拆会话凑覆盖。
5. **后续**：跨进程恢复、TabR/Disent/ModernNCA/CatBoost资源、逐个16配置仍待补；GPU清单不等于完整大显存卡可用。见[验收报告](collab/20261108_baseline_split_resource_acceptance_codex.md)、[验收JSON](../baseline_split_resource_v1_20261107/ACCEPTANCE.json)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
