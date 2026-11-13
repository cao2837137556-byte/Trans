# 正常参考补证首轮本地接续

结果：本地实现和封包完成，M 已用真实参考元数据独立复算并固定 13,247 个 UID。五项合同回归、真实查询资产/窗口/权重分母核验、封包和接收端回归通过。

影响：未取得本批作业号，没有远端资产或 Slurm 验收回执。C0/C1 未构建或评价，D/M 无新科学成绩。完整库仍是论文主结果。

下一步：用户恢复已有超算 SSH 转发后，在当前实验对话接续。程序先核对远端运行目录、squeue 和 sacct 并验证资产 SHA，有同批任务则复核归属，不自动再交或取消。

## 核对证据

- 实验 11 的最后一轮在读取执行说明和源码后中断，所见记录无提交操作。本地没有继承的本批目录、JOB 回执或后台作业客户端。检查时 18806 是旧结果页，未见用户已建立的 SSH SOCKS 转发。远端本批状态未知。
- LOCAL_REFERENCE_AUDIT.json 记录 17 项本地参考资产通过 INPUT_PINS.json 的 SHA 校验，以及 M 配额和有序 UID SHA。LOCAL_M_UIDS.jsonl.gz 是本地参考侧清单，按其摘要与超算封存结果复核。两份参考上下文和上下文标准化器在本地未找到。
- LOCAL_QUERY_AUDIT.json 确认 148,316 条完整查询、146,997 条建档后查询、280 行指标分母、E3/q14 与原视图的 SHA 或 UID。p4 分数、原支持和查询上下文实际存在性待远端核验。
- CONFIG.json、INPUT_PINS.json、PACKAGE_MANIFEST.json 和 PACKAGE_RECEIPT.json 绑定真实输入与运行包。真实计算节点小切片通过后同作业产生完整 D，M/C0/C1 的资源由实际测量确定。
- 本地进度页 http://127.0.0.1:18807/。计算结束并取回时从 received/RESULTS_FOR_PAPER.md、received/FINAL_ACCEPTANCE.json 和 received/PULLBACK_MANIFEST.json 接论文写作。启动阶段没有结果入口或最终验收。
