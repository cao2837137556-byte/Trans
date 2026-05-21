# Reviewer Defense：算法新颖性答辩

## Q1：你们是不是只是 LR？

A：不是。LR 是 guarded few-shot adapter 的轻量实现，不是贡献的全部。核心方法包括 OOD-safe source-rich representation selection、kcenter attack-support coreset、OOD-benign guard 与 validation-calibrated low-alert threshold。issue24/24c 还表明复杂 adapter 和 fusion 未稳定替代 LR，因此保留 LR 是证据驱动的工程-科研选择。

## Q2：top64 是不是普通特征工程？

A：不是普通特征工程。top64 的选择由 low-alert OOD constraint 驱动，目标是在 attack supports 与 ID/OOD benign 之间获得分离，同时避免 OOD tail 不安全特征。top64 相比 top32 修复了 primary OOD 超预算问题，并在 hard-shift 与 locked bins 上给出证据。

## Q3：为什么不是深度模型？

A：在 few-shot、tabular、low-alert deployment 条件下，复杂模型可能提高表达能力，也可能过拟合支持集或推高 OOD tail。issue24 中 SVM 失败且 OOD 超预算，weighted LR 无 detection 增益，fusion 也不能替换 LR。后续 strong baseline pack 会继续比较 semi-supervised anomaly baselines，但当前主方法不应靠未经验证的复杂度升级。

## Q4：locked validation 不是强阳性怎么办？

A：按 moderate positive 写。issue23 显示 top64 locked mean 0.9497、min 0.8826、OOD max 0.0045，但 bin6/bin7 略低于 V1，bin8 明显更强。因此本文应强调 mean/min/OOD safety 和 hardest-bin improvement，不写全面碾压。

## Q5：routing/promotion 失败会不会削弱论文？

A：不会削弱主方法，但会限制部署系统 claim。routing/promotion 当前应放入 discussion boundary，说明自动 promotion 需要更强 validation proxy，不作为本文主贡献。

## Q6：是否需要 external validation？

A：需要。当前 locked bins 是同数据集 leave-one-bin 证据，不等价于 external environment。下一阶段必须做 strong baselines 与 second environment / temporal validation。
