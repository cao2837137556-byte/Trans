# 论文方法部分中文草稿

## 1. Overview

本文提出增强型低告警守卫适配（Enhanced LOW-GUARD+），用于 benign-OOD drift 场景下的少样本入侵检测适配。与普通异常检测器不同，该方法不只优化攻击检出率，而是在固定低告警预算下学习攻击导向评分函数。方法由 source-rich 表示、OOD 安全的攻击分离特征选择、攻击支持样本核心集、守卫式少样本适配器和验证集阈值校准组成。

## 2. Source-rich 表示与 OOD 安全特征选择

给定原始流量特征，首先构造 source-rich 表示，以扩展少量 confirmed attack supports 可表达的统计空间。随后在训练和验证侧进行特征选择。特征选择以攻击支持样本与 ID/OOD benign 的分离为目标，同时考虑 OOD validation tail 的安全性和特征冗余。当前实现使用经验式 operational criterion，而非声称理论最优；其作用是从 source-rich 空间中选择更符合低告警约束的 top64 表示。

## 3. 攻击支持样本核心集选择

由于 confirmed attack labels 昂贵，本文使用 kcenter coreset 从本地 attack train pool 中选择 32 个攻击支持样本。该步骤旨在用有限标签覆盖攻击训练池的特征空间，降低随机支持样本对 attack-side shift 覆盖不足的风险。支持样本选择仅使用 attack train pool，不使用 attack eval 或 final OOD eval。

## 4. Guarded few-shot adapter

在 selected_source_rich_top64 上训练守卫式少样本适配器。正样本为 kcenter32 confirmed attack supports，负样本为 ID benign train 与 OOD benign train。OOD benign 样本以固定权重参与训练，使适配器在学习攻击方向的同时保持 OOD benign 低分。当前实现采用 LR，是因为其在少样本、表格特征和低告警阈值约束下稳定、可审计，且后续复杂 adapter 消融未显示稳定替代收益。

## 5. Low-alert threshold calibration

适配器输出攻击导向分数后，阈值由 ID calibration 和 OOD validation 决定，目标为 1% OOD alarm budget。final OOD eval 与 attack eval 仅用于报告性能，不参与特征选择、support selection、adapter selection 或 threshold selection。

## 6. Complexity and deployment consideration

Enhanced LOW-GUARD+ 的训练复杂度主要来自 top64 特征筛选、kcenter support selection 和线性适配器训练。与复杂神经 adapter 相比，当前实现更易审计，并能保留 threshold provenance。该方法不声称替代 base detector 或解决 fully automatic routing；它定位为 deployment-stage low-alert adaptation module。
