# 问题重构

## 低级表述

“我们用 source_rich top64 + LR 提升 IDS 检测。”

这个表述会把工作降格为特征工程加线性分类器，也无法解释为什么 dA、Transformer、score fusion、routing/promotion、adapter upgrade 的负结果仍然有科研价值。

## 高级科研表述

在 benign-OOD drift 下，入侵检测系统的部署目标不是单纯提高普通攻击检测率，而是在低告警预算下同时处理两类冲突：benign OOD 会诱发误报，attack-side shift 会诱发漏检。本文研究如何在少量 confirmed attack supports 可用时，构造 OOD 安全且攻击可分的表示，并在低告警约束下进行少样本适配。

## 为什么这是前沿问题

- benign-OOD drift 会改变正常流量分布，使传统异常检测器在低告警工作点上失效。
- attack-side shift 会使少量攻击样本无法覆盖所有攻击形态，导致 harder holdout 上漏检。
- 现实部署中 confirmed attack supports 昂贵，方法必须 evidence-efficient。
- 安全系统不能只追求 detection，也必须满足低告警预算，否则无法部署。
- 普通 AUC/PR-AUC 不足以代表低告警部署性能，必须显式报告 OOD alarm 与 guarded threshold provenance。

## 本文不是

- 不是单纯替换 base detector。
- 不是持续学习系统。
- 不是 fully automatic routing。
- 不是纯特征工程。
- 不是靠复杂 adapter 或神经模型堆叠取得结果。

## 当前问题定义

低告警 benign-OOD drift 下的少样本部署适配：给定 ID benign、OOD benign、少量 confirmed attack supports 和目标 OOD alarm budget，学习一个攻击导向但 OOD 安全的检测评分函数，并用验证集阈值控制部署告警。
