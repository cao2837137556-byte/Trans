# 当前状态

1. **方法**：FUSION790＋完整历史正常参考＋C5_3D_OLD保持冻结，主模型不改。
2. **当前工作**：baseline_split_resource_v1_20261107，作业182752，1CPU8GiB2小时、8阶段，进度18806；88包材料/23依赖，真实结果待验收。
3. **源划分**：落实17个整组验证分组，预期训练457120/验证160788行；逐行核验UID、会话/组件隔离，6设备×两类覆盖，另审活动/协议缺失。
4. **资源**：DTE/SLAD/TabM真实完整轮次＋完整验证计时、TabM/DTE同进程恢复；探针用完整FIT，验证分数仅计时不得调参。其余方法硬件资格、跨进程恢复、逐个16配置仍待补，不提前正式放行。
5. **边界/入口**：不复现作者数据集成绩，不按输赢选基线，大工件留超算。见[启动回执](collab/20261107_baseline_split_resource_launch_codex.md)、[执行卡](../baseline_split_resource_v1_20261107/EXECUTION_CARD.md)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
