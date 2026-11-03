# 持续输入修复 v3：按冻结监测对象隔离异常

2026-09-29。父版本 v2 设计 SHA256 `8396629e6e2495d98bfc1d4a5288f0570bc1a95d653596419005eb96470f55bd`。
v3 合同位于 `runs/legacy_continuous_input_core_repair_design_v3_20260929/design_contract.json`，SHA256 `a10a38edd2a871ebfb70cc37c1be3b1ac9715a2e0b0024019146f834b55674d9`。

## 问题与范围

Job177491 在 P 预检因非监测设备的 UDP 首分片缺少解码端口字段而停止；真实 E3、训练与评分均未开始。
原始包、冻结查询与参考的身份诊断见 `collab/20260929_job177491_preflight_diagnosis_codex.md`。
Claude 的四项要求见 `collab/20260929_job177491_scope_isolation_reply_claude.md`。

v3 只修复执行范围与异常致停范围的错位。模型、损失、训练参数、seed、数据角色、UID/分母、CAL、门槛、CPU/内存及并发均继承 v2。
它不新增通用分片支持，不把后续分片内容回填首片，也不宣称攻击迁移已恢复。

## 判定与状态

每个 capture 的 required_owners 是全部冻结查询与参考 owner 的并集，不依赖标签、分数或查询时间。
保留完整 known 注册表：两端出现两台已知设备时仍排除，不能通过缩小注册表把多owner流量变为单owner。

逐帧连续性与 capture 时序记录在前；按完整注册表判定唯一owner，若该owner不在必需集合，则记录 OUTSIDE_REQUIRED_OWNER 并退出当前状态处理；之后沿用v2的协议、头字段、namespace倒退、poison/taint、payload截断和当前包快照逻辑。
目标owner的完整历史合格上下文保留，不能只处理冻结查询帧。缺端口的目标首分片仍STOP。

不相关owner不写states、last_seen、poison、taint或触发回收。共享容量上限不变。回收与重置仍遵循目标自身的既有时序契约，加入任意数量或远未来时间的不相关owner帧不能提前回收目标。

## 两层审计

- 旧 ScopedPrefixes 仍按完整注册表遍历全捕获，用于静态回执核对，包括1/346、2/7424及UNSW INCOMPLETE_TARGET 14/2。
- 必需owner帧继续做 LEGACY_NAMESPACE_IDENTITY、LEGACY_NS_ANOMALY_IDENTITY、LEGACY_INCOMPLETE_IDENTITY 逐帧检查。
- 已有静态回执的全部 INCOMPLETE_TARGET 必须同时被分类为 OUTSIDE_REQUIRED_OWNER，否则STOP。既有源捕获预期为0，UNSW预期14/2；未按MAC或帧号硬编码例外。
- 所有固定目标仍检查资格、UID、owner、session、时间、协议及完整覆盖，范围排除不能删除目标。
- 摘要增加required_owners、required_identity_frames和legacy_incomplete_outside_required_owner。先行预检与正式spool调用同一审计器，完整摘要必须相等。
- 范围外普通帧使用紧凑逐帧记录并缓冲写入；真实旧异常立即flush，异常退出finally关闭流，降低新增诊断日志的I/O。没有丢弃逐帧身份。

## 夹具与验收

v3 包含原始帧1135180/1135181的固定双包PCAPNG及解码头字段JSON，仅作为语义回归夹具，不进入训练/参考/CAL/评估。包内夹具SHA256为 `1bcb7e6b72c5a33e3c3283fbe430732e6cb17c25ec6c300fb35a9109e8ecfada`。
运行环境会用自己的tshark解码这两个包，核对关键字段。无关owner时目标快照必须逐字节不变；同一首片改成目标MAC必须STOP。
补充多owner、跨capture时序、帧连续性、容量和过期、标签/时间无关、静态不完整归属、目标身份错配、范围内逐帧审计未禁用等验证。

## 执行与授权

本次授权是v3实现、验证、打包及补查历史sacct记录；没有授权重提真实P/T/K。
独立v3包供Claude聚焦复审；复审与新的完整执行授权完成后，由用户上传、提交一次和拉回。
资源维持amd单节点64CPU/192G/72h，程序70h、16特征进程、4训练进程、零自动重试。
失败作业177491的P采样不能用于调低后续E3/T/K内存。论文仍暂停，独立ID尚未补做。
