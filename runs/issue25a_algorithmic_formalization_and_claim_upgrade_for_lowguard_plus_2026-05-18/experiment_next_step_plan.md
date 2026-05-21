# 下一步实验计划

## Priority 1

`issue25_strong_baseline_pack_for_enhanced_lowguard_top64_2026-05-18`

目的：

- 防御“只是 LR/特征工程/few-shot anomaly 已有”的 reviewer attack。
- 与 modern few-shot/semi-supervised anomaly baselines 比较。
- 固定 Enhanced LOW-GUARD+ top64，不继续调参。

## Priority 2

`issue26_second_environment_or_temporal_validation`

目的：

- 补足 external validity。
- 验证 top64 是否只在当前同数据集 hard-holdout 上有效。

## Priority 3

paper integration draft

目的：

- 将 problem formulation、method、ablation、boundary 整合为论文初稿。

## Stop Rules

- 不继续 adapter 微调。
- 不继续 routing/promotion。
- 不继续 topK 搜索。
- 不在 strong baselines 和 second environment 前宣称最终主方法。
