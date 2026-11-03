# Job 176411 调度证据补充

来源：用户在已连接超算终端执行 `sacct -j 176411 --format=JobID,State,ExitCode,DerivedExitCode,Elapsed,Timelimit,MaxRSS,ReqMem,NodeList,Reason -P` 后提供的完整文本。助手未远程查询。原文保存在 delivery 的 `scheduler_review_job176411/sacct_user_provided.txt`。

作业和 batch 均 FAILED，退出码 `1:0`，耗时 08:18:01，节点 node188；申请内存 96G，作业时限 3 天。batch MaxRSS 为 9,204,120K，按 KiB 换算约 8.78 GiB。作业 DerivedExitCode 为 `0:0`，Reason 为 `None`。

## 结论的边界

- 不是达到这份记录中的作业时限后停止，也没有 Slurm OUT_OF_MEMORY 状态或 batch 终止信号标记。没有依据通过延长时限或增加申请内存解决本次故障。
- batch 的 `1:0` 表示 shell 以错误码 1 退出、该字段没有终止信号；它不表示 Python 子进程没有被主进程 kill。普通 subprocess 不各自成为 sacct 作业步骤，当前记录没有四个 worker 的退出码。
- DerivedExitCode 的 `0:0` 不覆盖作业 FAILED，不证明所有 Python 子进程成功。Reason None 也不证明没有程序内部异常。
- MaxRSS 是调度器采样统计，不能视为所有时刻的完整进程树精确峰值。它显著低于申请量且没有 OOM 标记，但仍不排除所有瞬时系统事件或文件系统错误。
- 结合已返回主进程 traceback、四个无 traceback 的 worker 日志及合成复现，继续优先修复执行监控与错误持久化；临时文件竞争仍为有代码依据的候选触发点，而非本次已证明的首因。首个监控异常已丢失，不能靠这些汇总字段补造。

## 下一步决定

无需继续要求用户反复查询同一份状态，也不因这个错误改科学路线、重新找数据或提高资源。下一步是工程修复和受控恢复准备：修复磁盘统计竞争，保留首个异常/traceback/各 worker 退出码，完善终态和可验证批次 checkpoint，检查复用已封存 manifests/flows 的路径。

已有 92.5% 进度仍不等于认证 checkpoint。四个部分 features.npy 的有效前缀尚未获准复用；须给出身份、顺序、落盘完整性及验证方案，不凭进度直接跳过样本。禁止用新 checkpoint 机制追认旧文件已经具备该机制的保证。

本次只补充诊断记录；没有修改交付执行器、没有实现/提交恢复任务、没有实际训练或评分。原 Job 176411 FAILED 保留；旧报告和两个合成复现记录不原地改写。原始冻结门槛、分母、模型、seed、因果规则与零自动重试约束不变。
