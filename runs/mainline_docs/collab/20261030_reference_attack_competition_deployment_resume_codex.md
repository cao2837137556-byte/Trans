# 正常／攻击参考竞争：恢复投递状态

2026-10-30。用户已要求继续，原“把实验运行上超算吧”的运行授权保持；不重复索取提交许可。

**代码包已上传，远端源输入只读预检已通过；本对话尚未调用提交器。当前阻断为school-hpc SSH主动断开，尚无本轮作业ID或运行进度。**

## 已完成并保存的事实

- 科学包99项本地测试通过，冻结科学设计不变。
- 部署zip SHA256：`fe7fa08de72329b8ed8b7607a27795bc5f4c6a22ba46e6a90903573139e409ab`。
- 已通过现有VS Code SSH隧道上传，远端node168写入104个缺失文件；其余同SHA既有文件复用，没有覆盖历史文件。回执见部署目录`runtime/REMOTE_UPLOAD_RECEIPT.json`。
- 中断前的`POST /probe`已经完成，回执成功落到本地`runtime/REMOTE_SOURCE_INPUT_ACCEPTANCE.json`：69项依赖、63源输入，共178个合并文件／2,625,596,968 bytes身份通过，errors为空。预检时间UTC 2026-10-29 15:55:16，即北京时间10月29日23:55:16。只哈希，真实前向／距离／训练／A/B均0。
- 远端部署bridge在node168，18784；新只读sidecar为18785。没有改用旧180007的18782或覆盖旧终态。

## 本次恢复检查

原本地SOCKS端口60106已经无监听。权限允许后实际检查仍为ConnectionRefused，不是把沙箱网络拒绝当成远端故障。未找到存活的school-hpc SSH进程。

已重新打开VS Code的school-hpc工作区，但其Remote SSH日志与一次非交互`hostname`检查均报告`Connection closed by 172.24.3.168 port 2222`。当前未建立新的SSH隧道，不能读取远端环境／测试／提交锁或继续执行提交。没有修改SSH、VPN、安全设置或代填认证。

## 恢复连接后的固定下一步

1. 从实际存活的VS Code SSH进程更新本地私有SOCKS端口，不打印token；先GET部署`/state`和只读快照，确认是否有提交回执或作业登记，不能根据中断自动重提。
2. 沿用超算Python3.11执行固定`POST /environment`，再执行`POST /tests`核对99项HPC合成测试；不足或失败即停，不提交。
3. 上述通过后仅一次`POST /submit_source`；提交器在sbatch前创建持久独占锁。结果未知时只查询回执／调度，不重试提交。
4. 确认真实job ID后登记源任务，启动普通只读同步器与本地18783页面，在Codex右侧显示真实调度及工作心跳。

用户只需恢复VS Code的school-hpc连接并看到远端Linux终端提示符，不需要重新批准科学范围。源4CPU／8GiB／4h及全部科学保护门不变；条件主阶段仍在源PASS及主CAL门之后。本次没有产生新的科学结果。
