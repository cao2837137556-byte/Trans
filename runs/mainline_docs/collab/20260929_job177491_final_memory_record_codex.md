# Job177491 最终内存记账补录

2026-09-29。来源：用户粘贴的最终 sacct 输出；不是助手远程实测。内存补取事项已完成。

- 作业及 batch：FAILED，退出码1:0，耗时00:09:47。
- 申请192G，分配64CPU；batch位于node188，MaxRSSTask=0。
- batch MaxRSS=7291960K，按Slurm K为KiB换算约6.9542 GiB；AveRSS同值。主job行内存字段为空，不等于零。
- 这是已执行P预检部分的Slurm记账值，不保证代表整个多进程树的同步总峰值；AveRSS也不是时间平均内存曲线。
- 本次真实E3/T/K未运行，不能据此降低后续资源。仍维持192G。
- 与既有first_failure证据一致，本次直接停止原因是MISSING_NAMESPACE_HEADERS；sacct没有报告OUT_OF_MEMORY状态。

原始输出与来源说明：runs/legacy_continuous_input_job177491_memory_followup_20260929/。
v3代码、交付包、封存验收和实现报告保持原字节；其中“sacct待回”是交付当时状态，由本补录更新。v3仍待代码复审及单独真实整链执行授权，本条不授权提交。
