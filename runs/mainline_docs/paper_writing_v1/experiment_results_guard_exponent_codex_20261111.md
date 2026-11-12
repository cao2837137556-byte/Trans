# 实验对话回传：最终3D保护与指数消融

结果：183530正常完成，两项均验收通过；388202查询的冻结基准分数0误差、四头判定0差异，156冻结指标一致。
影响：保护在B保住295条集成攻击告警、代价28条正常误报；p=4相比冻结p=3进一步减少B/Edge误报，但撤去A的6条集成攻击告警。主方法与默认参数保持冻结。
下一步：可写入论文当前3D消融，不需要等待其余实验；不把本批作为重新选参或唯一最优性证明。

完整回传包：[`RESULT_READOUT.md`](../../paper_reading_ablations_acceptance_v1_20261111/RESULT_READOUT.md)。

分项入口：
- [保护开关结果](../../paper_reading_ablations_acceptance_v1_20261111/guard/RESULT_READOUT.md)，同目录含指标JSON/CSV、配对变化及核验回执。
- [指数四档结果](../../paper_reading_ablations_acceptance_v1_20261111/exponent/RESULT_READOUT.md)，同目录含全四头/视图/子组数据。
- [五配置主表](../../paper_reading_ablations_acceptance_v1_20261111/MAIN_METRICS.md)、[全部头配对表](../../paper_reading_ablations_acceptance_v1_20261111/ALL_HEAD_MAIN_PAIRED.md)、[正式验收](../../paper_reading_ablations_acceptance_v1_20261111/FORMAL_ACCEPTANCE.json)。

论文解释请保留三点：
1. B攻击查询全部命中SYN保护；p变化时检出不变不能独立证明几何/核映射对攻击安全。
2. Edge p4集成正常告警为0，但单头为1/28/0；种子227还额外丢失1条HTTP告警。A p3→p4单头损失10/2/6条，集成6条。不能只摘录Edge零误报。
3. p1→p3在A/B集成攻击不变，但A单头27/127仍损失3/1条。原全时段/单种子例外及Edge未达99.9%继续披露。

作业墙钟12:06，Python峰值约2.074GiB；保护项6.45秒、指数项25.22秒为缓存后计算/输出开销，非端到端吞吐。24个改变UID gzip留超算，路径及SHA见回传包。回传仅写新增结果文档，不覆盖正文，也未向其他对话自动发送消息。
