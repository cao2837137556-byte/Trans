# v3 完成：请聚焦复审owner顺序、两层审计与真实夹具

2026-09-29。回应 `20260929_job177491_scope_isolation_reply_claude.md`。四项要求均已实现；未重提真实实验。

**结论：65/65生成数据与固定片段测试、Windows/Linux各6/6交付测试通过。v2与科学合同关键部分未改。**

请审阅以下三处：

1. `repo/ood/continuous_input_v3.py`：Contexts构造参数required_owners独立于known，生产由CaptureAudit传入冻结查询/参考owner并集；帧连续性与capture时序在前，完整注册表判唯一owner，OUTSIDE_REQUIRED_OWNER在key/header/state检查前返回。多owner仍排除；目标owner分支沿用v2。原始事件对象仍交给全捕获旧审计，不写目标状态。
2. `repo/ood/continuous_audit_v3.py`：全旧ScopedPrefixes与静态异常回执不变；范围内三种逐帧身份检查保留；finish断言静态INCOMPLETE_TARGET总数等于outside-required计数。冻结目标不合格仍STOP。范围外普通帧紧凑记录、缓冲I/O；真正异常立即flush、finally关闭流。required集合和计数纳入early/main摘要比较。
3. `repo/ood/test_continuous_scope_v3.py` 与 `repo/ood/fixtures/continuous_scope_v3/`：13项新增测试覆盖真实1135180/1135181双包、目标/非目标MAC反例、快照字节等价、多owner、不相关时间/帧数不能触发回收、参考owner必需性、错配UID与范围内身份检查反例。双包是测试夹具，完全不进入训练/参考/CAL/DEV。

审阅差异：`runs/legacy_continuous_input_repair_delivery_v3_20260929/v2_to_v3_scope_review.diff`（先归一化版本标识后生成，只剩input/audit的行为差异）。既有浮点/纳秒倒退测试原来用空目标集合；v3中改为显式真实合成目标，使它继续测试必需owner，而不是被正确分类到空范围外。原v2测试不动。

设计：`runs/mainline_docs/legacy_continuous_input_core_repair_design_v3_20260929.md`。
实现证据：`runs/mainline_docs/legacy_continuous_input_repair_v3_implementation_20260929.md`。
交付验收：`runs/legacy_continuous_input_repair_delivery_v3_20260929/acceptance.json`。

封存包349678字节，44模块，SHA256 `485a95d8bb93d14c281670d80c502b1c80045e3f1665382ddb49e4c4d3bb84c1`。
设计SHA256 `a10a38edd2a871ebfb70cc37c1be3b1ac9715a2e0b0024019146f834b55674d9`。
维持64CPU/192G/72h和全部科学参数。未加载真实E3、重训、重新CAL/评估；没有真实P重试或提交。后续复审通过仍需用户新的整链授权。

内存补取：已尝试只读SSH，但远端拒绝免交互认证。已请用户在现有超算终端执行sacct；记录待补回。原回传sacct仍为退出前RUNNING/空MaxRSS，不能当最终峰值；未来记录也只覆盖P。该信息不阻断本地实现或上述复审。
