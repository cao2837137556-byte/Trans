# Reviewer Defense: Baseline Fairness

## Q1: 为什么有些 baseline 不用 attack supports？

无监督异常检测方法本身不使用攻击标签。给 Isolation Forest、OC-SVM 或 LOF attack supports 会改变它们的学习范式。公平做法是不给它们攻击标签，但给合理特征输入和相同的 1% OOD validation threshold。

## Q2: 为什么有些 baseline 和你们输入相同，有些不同？

公平性分层处理。Adapter-level baseline 必须同 source_rich_top64，因为它比较 adapter。Representation ablation 故意更换输入，因为它比较表示。Method-level baseline 可以使用方法合理输入，但必须遵守同样监督预算、阈值协议和 final eval 隔离。

## Q3: 你们是否 unfairly weaken baseline？

协议显式避免弱化 baseline。半监督和少样本 anomaly baseline 获得同样 32 个 confirmed attack supports；无监督 baseline 不获得 attack labels 是因为其定义不使用标签；所有方法共享同样低告警阈值协议。

## Q4: 为什么 threshold 都用 OOD validation？

论文问题是 benign-OOD drift 下的 low-alert adaptation。若 threshold 不受 OOD validation 约束，方法可能通过高误报获得高 detection，无法满足部署目标。

## Q5: 为什么 final eval 不参与选择？

final eval 必须只用于报告，否则会产生 threshold、超参、support、feature 或 architecture 泄漏，导致 strong baseline 结论不可审计。

## Q6: 如果 HistGB/DevNet/DeepSAD 赢了怎么办？

如其在同样低告警约束和监督预算下稳定优于 Enhanced LOW-GUARD+，应如实报告，并将其作为更强 adapter 或 baseline 证据。这不会削弱问题定义，反而说明 adapter 复杂度在固定 top64 表示下仍有价值。

## Q7: 如果无监督 baseline 赢了怎么办？

如果无监督 baseline 在同样 OOD threshold 下赢，应承认 few-shot attack supports 在该设置中不是必要条件，并重新定位方法贡献。不能为了保护主方法隐藏该结果。

## Q8: 为什么不用大规模持续学习 baseline？

当前论文主问题不是持续学习训练，而是低告警少样本适配。大规模持续学习需要不同数据流、记忆策略和长期标签协议。若协议不完整，应作为 design-only 或后续工作，而不是在 issue25c 中做不公平对比。
