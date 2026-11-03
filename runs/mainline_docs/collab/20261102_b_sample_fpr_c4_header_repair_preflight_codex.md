# C4 布尔字段工程修复：已上传，超算预检中

2026-11-02启动快照，尚未取得新作业号，不代表最终通过。

180591实际失败为`AUDIT_INVALID_INTEGER:tcp.flags.syn`：固定TShark输出True/False，新增包头校验器误按整数解析。新隔离目录修复四个TCP布尔位的严格解析，其余整数/地址/长度/时间/原包索引仍核验；未知格式仍拒绝。所有246个真实告警包的原始EPB逐一核验通过；59项工程测试、8项交付测试通过。下游保存A/B四头双视图、旧DEV与参考的只读核验通过。

复用三设备20480条编码、Netatmo完整3592947候选清单/索引及8192REF+4096DEV既定选点。只重放未完成连续上下文，再做剩余编码及原合同验收；不是从失败帧原地恢复，也不是四设备重跑。科学规则、λ、盐值、容量、模型和门控不变。

修复代码4741120字节已上传并安装；2405307756字节远端已有输入未重传。普通pipeline PID20356已启动；当前INSTALLED，正在超算预检，无已知新错误。预检通过自动唯一提交、更新右侧18789并取回/验收；无持续AI监控。独立有界本地收据归档PID35920只等待提交/启动收据，将写正式提交文档和指针，不运行科学计算或再次提交。

累计原8小时预算已扣24534秒，剩4266秒（71分6秒），未重置；4CPU/8GiB/20GiB、编码36864与距离10亿上限保持。剩余时间包括编码和本地评价，不保证在预算内完成。A/B仍为CONSUMED_DEVELOPMENT_ONLY。

- 新实现：`../history_sample_coverage_c4_header_repair_v1_20261101/`
- 真实包头证据：`../history_sample_coverage_c4_header_deployment_20261101/REAL_HEADER_AUDIT.json`
- 当前核验：`../history_sample_coverage_c4_header_deployment_20261101/CURRENT_DELIVERY_CHECK.json`
- 后续真实作业号：同部署目录`SUBMIT_RECEIPT.json`
- 后续最终验收：新实现目录`FINAL_ACCEPTANCE.json`

执行卡SHA256：`fdd491483c8408b8054cf195de5cfaee82c2f0772d56313ee1ae5ca34633350b`。
