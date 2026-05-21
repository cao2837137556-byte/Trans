# Issue25a 算法形式化与证据固化摘要

## 任务目的

本轮不跑实验，不训练模型，不修改主稿，不改历史数字。目标是把当前实验链条从“source_rich top64 + kcenter32 + LR 的组合结果”提升为可写入论文方法部分的算法表述：增强型低告警守卫适配（Enhanced LOW-GUARD+）。

## 推荐方法名称

推荐名称：增强型低告警守卫适配（Enhanced LOW-GUARD+）。

该名称保留此前项目主线中的 LOW-GUARD 语义，同时强调当前版本不是普通 LR，也不是完整持续学习或路由系统，而是由低告警约束驱动的少样本适配方法。

## 算法创新定位

当前主方法应表述为：

增强型低告警守卫适配（Enhanced LOW-GUARD+）= OOD 安全的攻击分离表示选择 + 攻击支持样本核心集 + 低告警守卫少样本适配器 + 验证集校准阈值。

具体实现冻结为：

- 表示：selected_source_rich_top64。
- 支持样本：kcenter32 confirmed attack supports。
- 适配器：fixed OOD guard LR。
- 阈值：ID calibration + OOD validation 下 1% OOD alarm target。

## 当前证据强度

- 强可写证据：top64 修复 top32 在 primary_lowood 上 OOD 超预算的问题；top64 在 holdout_bin_2 与 chrono_late 上显著强于 V1；top64 在 primary_lowood 上 detection 与 OOD 均不退化。
- 中等证据：issue23 的 locked bins 5/6/7/8 给出 moderate locked validation，V2_top64 locked mean 0.9497、min 0.8826、OOD max 0.0045。
- 边界证据：V2_top64 不逐 bin 全面碾压 V1，bin6/bin7 略低于 V1，bin8 明显强于 V1。
- 负结果证据：weighted LR、SVM、fusion 均不能替换 V2_top64 LR；routing/promotion 当前不 clean。

## 不能夸大的边界

不能写成外部泛化已证明、routing/promotion 已解决、V2_top64 普遍优于 V1、或已达到 CCF-A/A 区就绪。当前方法可以作为统一候选和论文主方法候选，但仍需要 strong baseline pack 与第二环境或时间验证。

## 下一步唯一建议

`issue25_strong_baseline_pack_for_enhanced_lowguard_top64_2026-05-18`。

现在最缺的是强 baseline，而不是继续包装、继续 adapter 微调、继续 topK 搜索或继续 routing/promotion。
