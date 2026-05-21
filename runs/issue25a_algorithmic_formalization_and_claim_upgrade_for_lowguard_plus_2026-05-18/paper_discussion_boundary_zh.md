# 讨论与边界中文草稿

Enhanced LOW-GUARD+ 当前提供了低告警少样本适配的有力候选，但其证据边界必须明确。首先，V2_top64 并未逐 bin 全面优于 V1。在 locked validation 中，V2_top64 的 mean detection 为 0.9497，OOD max 为 0.0045，但 bin6/bin7 相比 V1 略低，bin8 则明显更强。因此，该结果应表述为 moderate locked validation，而不是 universal dominance。

其次，routing/promotion 目前不能作为主贡献。issue20、issue20b 和 issue21 显示，当前 validation-side proxy 和 active review evidence 都未能 cleanly 判断何时从 V1 切换到 V2。本文可将其作为部署边界讨论，而不能写成 fully automatic routing 已解决。

第三，更复杂 adapter 并未稳定提升当前主方法。issue24 中 weighted LR 不提升 detection，SVM 违反 OOD 预算；issue24c 中 fusion 只有弱信号且不能替换 V2_top64 LR。这支持保留 LR 作为轻量 guarded adapter，但不意味着所有复杂模型都无效。

最后，当前验证仍主要来自同数据集 hard-holdout 与 locked bins。高水平投稿前仍需 strong baseline pack、modern few-shot/semi-supervised anomaly baselines，以及 second environment 或 temporal validation。
