# 181403 超时诊断与工程验证缺口

结果：181403在9分24秒后失败，最终Linux门未通过。环境、输入和NORMAL前缀重放通过，停于HTTP上下文重放，模型编码、距离与外部效果评价尚未开始。
影响：先前两项环境/路径修复有效，但39项工程回归并未覆盖当前切片的真实吞吐。已保留远端数据库和日志，并验SHA取回小回执；本轮没有启动新超算作业，没有改数据、冻结方法或原包。
下一步：先做包外的临时状态存储、逐帧进度和统一有效deadline修复，并验证选中snapshot与原实现完全一致，再冻结下一次有界验证；不能直接延长墙钟或继续盲投。下述改进当前是待实现范围，不能写成已修复或已通过。

## 实际证据

- Slurm状态FAILED、ExitCode1:0、Elapsed00:09:24；外层回执为`OUTER_ENGINEERING_WALL_LIMIT_NO_RETRY`，elapsed563.184636秒。MaxRSS405112K，不是OOM证据。`FINAL_ACCEPTANCE.json`明确`linux_actual_preflight_pass=false`。
- 91是逻辑编码端点数（78切片+13探针），并非91个原包。当前切片须顺序重建NORMAL255220、HTTP228978、UDP16，共484214个原始上下文包。旧65端点解码计时13.656秒只覆盖126122包；当前总量3.84倍，HTTP前缀54.47倍，不能套用旧计时作为当前600秒可完成的证据。
- `decode_00`与`decode_01`均已创建，两个stderr日志与supervisor日志都为空；NORMAL完整结束后已进入HTTP。不存在stderr PIPE相互填满这一经典死锁：stderr直接写文件。现有证据不能证明所有其他等待均不存在。
- 远端只读元数据已通过结果tar与成员manifest SHA校验。NORMAL工作库73654272字节、14581个对象、序列化值68534439字节；HTTP工作库92540928字节、journal6589576字节。HTTP有未恢复journal，只读SQL返回`attempt to write a readonly database`；检查没有恢复或修改原库，前后字节数与mtime一致。不能据此虚构HTTP最终处理到哪一帧。
- Slurm TotalCPU83.900秒，其中UserCPU72.297、SystemCPU11.602；564秒墙钟仅约15%单核CPU占用。batch记录AveDiskRead4720.06M、AveDiskWrite1919.39M。这与共享/public上的SQLite频繁load/spill/journal相符，足以列为主要性能嫌疑；读量也包括SHA和manifest校验，不能将全部等待或读写归为SQLite或Lustre的唯一原因。

## 可避免的工程问题

`selected_snapshots`对全部前序包执行完整数值Contexts。状态存储固定256驻留项，SQLite位于共享输出目录。当前扩大切片没有目标Linux/共享存储上的完整数值重放吞吐实测；600秒是硬上限，不是已测得的可完成保证。

逐包循环没有帧心跳或分项计时，`Progress.guard`在整个角色的生成器完成之后才调用。内部deadline为worker启动后600秒，外层最多540秒并扣除setup；慢重放会先被外层杀死，内部来不及写准确STOP、当前帧和RESULT。每个角色的选中snapshot只保存在内存列表，NORMAL虽完成，也没有可复用的持久化snapshot。当前SpillMap明确属于不可重新打开的临时工作库，不能称其支持中途续跑。

因此，之前“已修复”只应限于已验证的共享库与路径错误，不能被理解为整条链路已打通。工程测试和真实同运行时预检必须分开报告，且预检自身也必须可观测、可早停、能保存已完成成果。

## 本轮无模型核查与后续边界

本地Windows/Python3.10用原冻结NumericalContexts重放HTTP32768包，1核、硬60秒、临时DB256MiB上限；11.781秒完成，8192包2.672秒。累计16732次spill、14389次load、74798370字节序列化，临时SQLite及journal峰22894168字节。未加载编码器、未生成snapshot、未算分数或距离，PCAP SHA前后相同；自建临时数据库已清理。

这说明本地小前缀可持续前进，不能替代完整前缀或Linux运行时门，也不能据此保证十分钟够用。优先只调整临时状态的物理存放位置：确认计算节点实际本地挂载、容量及清理范围，禁止静默回退共享盘；保留全原包、全部冻结因果/数值逻辑与当前选点，先验新旧所选snapshot完全一致。补每4096帧或每5秒的role/frame、读写与store统计，贯穿同一有效deadline，外层强杀前写STOP；每角色完成后持久化选中snapshot，明确只复用完整角色，不假称支持任意帧恢复。

主要机器证据：`runs/edge_linux_preflight_deployment_v1_20261103/{FINAL_ACCEPTANCE.json,TIMEOUT_READONLY_AUDIT.json}`；本地吞吐：`runs/edge_decode_throughput_diagnostic_v1_20261103/{diagnose.py,RESULT.json,README.md}`。本轮复核不构成追加云端预算或正式外部评价授权。
