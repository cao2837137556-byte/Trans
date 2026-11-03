# C2 已完成

**攻击保护修复通过，完整 2% 目标仍未达成。**

| 两小时观察后主视图，三头集成 | 误报率 | 攻击召回 |
|---|---:|---:|
| A | 3.3161% | 100% |
| B | 1.7505% | 99.9946% |

B 的误报保持不变，33 条新增漏报全部恢复，剩余 5 条属于 RAW 原有漏检。两池四头攻击保护均通过。

- 源域保存结果预检：完成，仅作开发诊断；G1/S 的正常 SYN 误报反弹已披露。
- HIST_DEV：PASS，误报相对 RAW 减少 57.58%。
- A/B：完成一次评价；主集成误报保持原值。
- 最终验收：PASS，328,202 行，51 项输入保持，18 件科学产物校验通过。
- 资源：149.14 秒，4 核，峰值约 1.24 GiB；无新训练、编码或邻居距离。

下一缺口：HeimVision 误报 6.6319%、WEMO Power 3.4781%。C3 尚未实施。

注意：B 的 227 单头误报升至 2.0211%；B 的 full 视图集成误报为 2.1003%。不能把主集成结果扩大成所有头/所有视图均无副作用。

[完整结果与给 Antigravity 的复核材料](D:/study/paper/anomaly_detection/paper04/worktrees/kitnet-exp-mainline/runs/mainline_docs/collab/20261031_history_normal_reference_c2_syn_guard_result_codex.md)
