# v3 实现与交付记录

2026-09-29。状态：实现和本地验证通过，供Claude聚焦代码复审。真实P/T/K未重新执行。

v3修复非必需owner的首分片导致全作业停止的问题。除版本名和合同指纹外，生产代码实际行为变更仅在 `repo/ood/continuous_input_v3.py` 与 `repo/ood/continuous_audit_v3.py`；模型、训练、数据、评分、导出及主调度逻辑为v2版本化副本。差异审阅文件：`runs/legacy_continuous_input_repair_delivery_v3_20260929/v2_to_v3_scope_review.diff`。

## 四项落地

1. 完整注册表求唯一owner，范围外在namespace缺头检查前记录并返回；帧连续性与capture时间记录仍在前。目标与其它已知设备间的多owner流量继续排除，目标缺端口继续STOP。
2. 不相关owner不占用states/last_seen或触发回收。max_states等上限不变；测试在仅1个状态容量下插入200条远未来不相关owner流量，目标快照不变；随后目标自身10s/60s/严格>60s边界仍按原规则处理。
3. 全捕获旧ScopedPrefixes继续保留。新旧逐帧身份核对只在必需owner执行。静态回执的INCOMPLETE_TARGET必须全部属于OUTSIDE_REQUIRED_OWNER，目标/参考固定UID覆盖和早期/正式摘要一致性仍是硬检查。额外统计与紧凑逐帧记录随回传包保存。
4. 固定原始1135180/1135181双包及其头字段夹具：无关owner时目标快照逐字节一致，改为目标owner时STOP。执行环境还会用自己的tshark验证夹具字段，以暴露解码版本差异。

## 验证与边界

- 65/65测试通过：继承52项，新增13项范围/真实片段语义检查。完整套件在源码与干净解包下均通过。
- Windows/Linux各6/6安装、篡改/越界/覆盖拒绝、失败导出测试通过；4个Bash文件语法和模拟调度测试通过，未调用真实sbatch。
- Python3.9干净解包通过，PowerShell实际ParamBlock/Mode参数及语法通过；传输脚本保留百分比和断点续传。
- 合同的model、arms、training、calibration、data、evaluation与v2逐项相同。D1历史可行性结果直接按原哈希保留，未重算旧分数。
- 原v2源码/包、HEAD/分支、8项无关改动、论文暂停快照保持不变。
- 本地测试中曾修正版本化脚本的日期路径和传输模板源路径；修复后进行了上述干净包验证。没有真实实验重试。未完成的初次本地bundle保留为build_attempt1_incomplete，不是交付包。
- 本次只读取固定双包夹具，未重新解码完整捕获、未加载真实编码器、未训练真实模型、未做真实CAL或评分。工程通过不等于科学能力通过。

## 交付身份

- 包：`runs/legacy_continuous_input_repair_delivery_v3_20260929/legacy_continuous_input_repair_v3_20260929.tar.gz`
- SHA256：`485a95d8bb93d14c281670d80c502b1c80045e3f1665382ddb49e4c4d3bb84c1`
- 大小：349678字节；44个Python模块；两个固定原始报文仅供回归测试，不进入模型数据。
- 合同SHA256：`a10a38edd2a871ebfb70cc37c1be3b1ac9715a2e0b0024019146f834b55674d9`
- 指令：同目录`OPERATE_HPC.md`，传输为`transfer_v3.ps1`，安装器为`repair_install_v3.py`。
- 资源保持64CPU/192G/72h、16特征进程、4训练进程与70h程序保护。真实链重提需新的整链授权，用户操作上传/提交/拉回。

## 177491内存记录

尝试了用户授权的只读SSH查询，本地免交互认证被远端拒绝，尚未取得最终sacct数据。已向用户发出可在现有VS Code超算终端运行的命令；状态记录在 `runs/legacy_continuous_input_job177491_memory_followup_20260929/status.json`。
原包内sacct是在退出前抓取，仍为RUNNING且MaxRSS为空。status的7.03498GiB是P阶段最后采样，不是历史峰值。补回的最终sacct也仅覆盖P，不用于降低E3/T/K内存。
