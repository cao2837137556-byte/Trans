# Issue25b Strong Baseline Protocol and Fairness Design Summary

## 任务目的

本轮只做 strong baseline 协议设计和公平性设计，不跑实验，不训练模型，不修改论文主稿，不修改历史实验数字，也不继续调整 topK、support、adapter 或 threshold。

目标是为下一轮 `issue25c_strong_baseline_pack_execution_for_enhanced_lowguard_top64_2026-05-18` 固化可审计的比较协议，避免 baseline 因输入、监督预算、阈值选择或超参选择不公平而削弱论文可信度。

## 已读取证据

- `issue25a`：Enhanced LOW-GUARD+ 已形式化为 OOD 安全的攻击分离表示选择、攻击支持样本核心集、低告警守卫少样本适配器和验证集校准阈值。
- `issue23`：V2_top64 在 locked bins 5/6/7/8 上为 moderate locked validation，locked mean 0.9497、min 0.8826、OOD max 0.0045。
- `issue24/24b/24c`：weighted LR、SVM、fusion 没有稳定替代 fixed guard LR，下一步不应继续 adapter 微调。
- `issue22/22b`：V2_top64 修复 V2_top32 的 primary OOD 超预算，并在 primary、holdout_bin_2、chrono_late 上形成统一候选证据。

## 监督范式定义

Enhanced LOW-GUARD+ 属于低告警少样本半监督异常适配：

- 使用 ID benign 训练和校准数据。
- 使用 OOD benign 训练或验证数据来约束低告警预算。
- 使用少量 confirmed attack supports，当前固定为 kcenter32。
- 在 benign-OOD high-alert alarm 不超过 1% 的约束下最大化 attack high detection。
- final attack eval 和 final OOD eval 只用于报告，不参与任何选择。

它不是纯无监督异常检测，也不是传统全监督分类，更不是持续学习或自动路由系统。

## 三层公平协议

1. Adapter-level fairness：固定 selected_source_rich_top64、同样 32 个 confirmed attack supports、同样 ID/OOD train-cal-val、同样 1% OOD validation 阈值协议，只比较 adapter。
2. Representation-level ablation：固定 fixed guard LR、kcenter32 和 1% OOD validation 阈值协议，只比较 original100、source_rich_top32、source_rich_top64、full_source_rich 等表示或 guard/support 组件。
3. Method-level strong baseline：按方法范式给合理输入和监督预算，无监督方法不给 attack labels，半监督/少样本方法给同样 32 个 confirmed attack supports，所有方法共享 final eval 隔离和 1% OOD validation threshold。

## Required Baselines

- V1 original100 fixed guard LR。
- V2_top32 source_rich fixed guard LR。
- Enhanced LOW-GUARD+ top64 fixed guard LR。
- top64 no guard。
- top64 random32。
- Isolation Forest。
- OC-SVM。
- HistGB shallow。
- DevNet-like lightweight。
- DeepSAD-like lightweight。

## 核心约束

- 所有超参只能用 train/cal/val 选择。
- 所有阈值只能由 ID calibration + OOD validation 在 1% OOD alarm target 下确定。
- final OOD eval 和 final attack eval 对所有方法都是 report-only。
- 如果某 baseline 缺少可审计 validation proxy，必须标为 diagnostic only，不能放入主比较 claim。

## 下一步

唯一建议：`issue25c_strong_baseline_pack_execution_for_enhanced_lowguard_top64_2026-05-18`。

若 issue25c 执行前发现 DevNet-like、DeepSAD-like 或 HistGB 的资产/实现无法满足 final eval 隔离，应先补齐资产或将对应方法降级为 design-only / appendix。
