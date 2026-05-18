# 论文写作草稿：LOW-GUARD-Routed

单一适配器不足以覆盖所有部署阶段的漂移形态。在 primary low-OOD 场景中，LOW-GUARD-minimal 保持较低 OOD 告警，并提供稳定的攻击检出；但在 harder attack-side shift 场景中，它的攻击检出明显下降。LOW-GUARD+ 能显著修复 harder shift 下的攻击检出，但在 primary low-OOD 上会超过 1% OOD 告警预算。因此，直接用 V2 替代 V1 并不安全。

基于这一观察，本文后续方法应表述为 LOW-GUARD-Routed：一个部署阶段的低告警路由式适配系统。系统维护当前 champion adapter 和 shadow challenger adapter。候选适配器只有在低告警验证窗口中同时满足攻击检出代理收益、OOD 告警预算、review burden 和 provenance clean 条件时，才允许晋升为特定模式下的 champion。

该机制不是无约束的 V1/V2/V3 堆叠。未通过 promotion gate 的模型保持 shadow 状态或被拒绝；已上线模型若在运行时违反 OOD 告警或 review burden 约束，则回滚到上一 champion。V1 high / V2 low 的冲突样本进入 bounded review queue，而不是直接高优先告警，也不是丢弃。review queue 是安全兜底和审计入口，不应被解释为确认攻击样本池。

该设计的边界也必须明确：issue19b 只证明 V1 与 V2 在不同漂移模式下具有互补角色，并动机化 routing validation。LOW-GUARD-Routed 的策略有效性仍需要后续 issue20 routing validation 证明；alarm-budget curve 中的候选 operating point 也必须经过 locked validation，不能基于 final OOD eval 直接改变正式阈值。
