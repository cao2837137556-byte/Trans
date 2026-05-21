# 贡献重写

## Contribution 1：低告警 benign-OOD drift 下的少样本 IDS 适配问题

本文提出并实证研究一种低告警少样本入侵检测适配问题：在 benign-OOD drift 与 attack-side shift 同时存在时，检测器必须在提高攻击检出的同时保持 OOD benign 告警预算。

Supporting evidence files:

- issue13 deployment timeline。
- issue16b/16c harder holdout failure and diagnosis。
- issue22/22b/23 enhanced V2 evidence。

Allowed wording:

- “本文关注低告警 benign-OOD drift 下的部署阶段少样本适配。”

Forbidden overclaim:

- “本文解决所有 drift 场景。”

## Contribution 2：增强型 LOW-GUARD+ 方法

本文提出增强型低告警守卫适配（Enhanced LOW-GUARD+），将 OOD-safe source-rich feature selection、kcenter attack-support coreset 和 fixed guarded few-shot adapter 组合为一个可审计的低告警适配流程。

Supporting evidence files:

- issue22 method_comparison_summary。
- issue22b primary non-regression。
- issue23 locked validation。

Allowed wording:

- “Enhanced LOW-GUARD+ 在当前同数据集 hard-shift 与 locked bins 上表现出中等到较强的低告警适配证据。”

Forbidden overclaim:

- “top64 universal dominates V1。”

## Contribution 3：证据驱动的边界与负结果消融

本文保留 adapter upgrade、fusion、routing/promotion 的负结果，证明当前收益主要来自 OOD-safe representation 与 low-alert guard，而非复杂模型堆叠。

Supporting evidence files:

- issue24 adapter upgrade feasibility。
- issue24b adapter bottleneck diagnosis。
- issue24c targeted fusion retry。
- issue20/20b/21 routing and promotion boundary。

Allowed wording:

- “更复杂 adapter 和 routing/promotion 当前未提供稳定可替代收益，因此本文将其作为边界讨论。”

Forbidden overclaim:

- “routing/promotion 已验证成功。”
