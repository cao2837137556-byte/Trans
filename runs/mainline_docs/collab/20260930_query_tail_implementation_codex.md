# QUERY_TAIL v1 实现接续

已读20260930_experiment8_supplemental_handoff_codex.md及设计合同/实现交接/研究记录/设计验收，直接实现，不重复G1–G4或D3。原对话停止并行写入的安排已遵守；当前由本对话单写者推进。

实现与本地验收完成：当前包14维+加权正常1%尾部、9新头固定40轮、复用177891 RECENT，完整FIT/CAL、双方梯度及全部冻结门槛。整链包127034字节，SHA72a50f76e2bb14683b285cef5fbd2e5cc38cc6112886e687fee82d219725f1c2。

干净Python3.9合成23项、Windows安装6项、Linux安装/模拟提交12项PASS；12个已返回snapshot解析兼容。真实P/T/K仍未启动，完整源阶段统计及目标Torch2.5.1验收均在正式链内。没有新的科学PASS或Claude审查。

详细依据：../legacy_query_tail_learning_implementation_v1_20260930.md；../../legacy_query_tail_learning_delivery_v1_20260930/{acceptance.json,OPERATE_HPC.md,RESOURCE_BUDGET.md,source_validation.json}。

自审特别核对：尾部按权重不是条数、并列整块比例分配、末batch用实际b；新增列为0且共享初始化参数一致，但宽矩阵float32累加可能有舍入差异；完整FIT617908而非567175；reference不使用且NOT_TESTED。没有补模块、按SYN写死规则、选seed/epoch/赢家或改变源权重。

Claude暂时无token，无需等其恢复批准；本记录是异步结果同步，并不请求新的Claude复审。后续如果发现具体语义问题，再凭证据提出版本化修订。
