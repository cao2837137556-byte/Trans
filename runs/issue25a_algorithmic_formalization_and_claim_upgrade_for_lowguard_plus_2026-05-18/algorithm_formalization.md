# Enhanced LOW-GUARD+ 算法形式化

## 总体定义

增强型低告警守卫适配（Enhanced LOW-GUARD+）由五个模块组成：

1. source-rich 表示构造。
2. OOD 安全的攻击分离特征选择。
3. 攻击支持样本核心集选择。
4. 低告警守卫少样本适配器训练。
5. OOD validation 阈值校准。

## Module 1：Source-rich 表示构造

输入为流量或窗口级原始特征，输出为 source_rich feature matrix。该模块扩展原始 original100 表示，使少量 confirmed attack supports 在更丰富的统计空间中呈现可分性。

当前论文中不应把该模块写成复杂 representation learning；它是可审计的增强表示，为后续 OOD-safe selection 服务。

## Module 2：OOD 安全的攻击分离特征选择

输入：

- attack supports。
- ID calibration。
- OOD validation。
- source_rich feature matrix。

输出：

- selected_source_rich_top64。

目标：

- 提高 attack supports 与 OOD validation/ID calibration 的分离。
- 避免选择 OOD tail 不安全的特征。
- 降低冗余，避免 topK 被高度相关特征占满。

当前实现是 empirical selection criterion，而不是闭式理论最优。可以描述为基于 effect size、OOD tail margin 和 redundancy pruning 的 operational criterion。不能伪造为已证明最优的数学目标。

## Module 3：攻击支持样本核心集选择

使用 kcenter32 从 local confirmed attack train pool 中选择支持样本。

算法意义：

- 在攻击标签预算有限时覆盖 attack train pool 的 feature space。
- 避免 random support 对 harder shift 覆盖不足。
- 将少样本采集问题转化为支持集覆盖问题。

边界：

- kcenter 是当前实现，不代表 support acquisition 已完全解决。
- support selection 不使用 attack eval 或 final OOD eval。

## Module 4：低告警守卫少样本适配器训练

适配器使用 fixed OOD guard LR：

- positives：selected confirmed attack supports。
- negatives：ID benign train + OOD benign train。
- OOD benign 权重固定。
- scaler 只在训练数据和 selected supports 上 fit。

LR 的定位：

- LR 不是贡献本身。
- LR 是低告警守卫少样本适配器的轻量、稳定、可审计实现。
- issue24/24c 显示更复杂或融合式 adapter 没有稳定替换 LR，因此保留 LR 是证据驱动选择。

## Module 5：OOD validation 阈值校准

阈值 tau 由 ID calibration + OOD validation 计算，official budget 为 1% OOD alarm。

final OOD eval 和 attack eval 仅用于最终报告，不用于 feature selection、support selection、adapter selection 或 threshold selection。

## 方法边界

Enhanced LOW-GUARD+ 当前是 unified candidate，不是 external generalization proof。issue23 给出 moderate locked validation，仍需 strong baselines 与 second environment / temporal validation。
