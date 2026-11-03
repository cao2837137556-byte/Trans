# 密参考 A/B 先行：授权部署与运行回执

## 最新真实终态：179680 技术异常停止

**179680 / node185：FAILED、exit 70:0、耗时48秒；尚无A/B正式指标。** 原包、授权、NumPy 2.0.1环境和输入身份已过，随后第一个 own-reference trace 初始化时，冻结核心的真实查询/参考UID重叠分支触发 lazy import，因封包漏含 `causal_reference_overlap_v1.py` 停止。原19项合成测试没有查询/参考UID重叠，未覆盖这一真实路径。这是工程依赖闭包错误，不能记为方法科学FAIL或资源不足。

已补传缺失的1,241,109,775字节静态输入，27件静态与7件179602派生产物均已核SHA；修复后可复用，不需重新传大数据、编码或CAL。目标metadata、features和head scores读取已经开始，但完成支持计算、池结果与正式A/B指标均为0。worker峰值RSS为1,024,995,328字节，清理确认通过，无遗留worker。

证据见 `runs/dense_reference_ab_stage_deployment_20261028/STARTUP_ACCEPTANCE.json`、`EXECUTION.json` 及 `remote_progress/job_179680/bundle.json`。本轮单次授权已消费，自动重试0；原候选、r1归档、179680现场及原科学参数保留。当前另建依赖修复层，准备冻结六模块闭包、真实metadata资格预检与合法/非法重叠UID隔离回归；修复验收不代表已重新提交。

[18771进度页](http://127.0.0.1:18771/)已经显示 `EXCEPTION_STOP` 与具体缺模块原因，普通同步在终态退出，页面离线保留。新修复包、本地独审与超算只读预检进展见[独立修复回执与具体执行卡](20261028_dense_reference_ab_stage_dependency_repair_codex.md)；它不自动授权第二次提交。下文部署前及待启动表述为历史快照。

2026-10-28。用户明确“开始运行。”，批准此前[具体执行卡](../../dense_reference_ab_stage_candidate_v1_20261028/EXECUTION_CARD.md)：A/B两池三臂先行，第三池延期且保持未评价；单次amd4CPU/16GiB/最多2小时，RSS8GiB、0自动实验重试。原三池协议与历史产物保持。

## 授权与封包

- 用户原话与授权范围：`runs/dense_reference_ab_stage_deployment_20261028/AUTHORIZATION_RECEIPT.json`。
- 真实授权SHA：`731e6223492c02bd02f5074537599ac4350d9afcc52eedb032914950c68298dc`。
- 包清单SHA：`6870ae7c60ecfb82e4e8c0bc8a18306cad6ee0cf62ed640a82ca254da1fa8f61`。
- 归档SHA：`b37e9213bf7546134205cfcc52192c54d493fb99d4f393a78383d51dbf417937`，650,274字节。
- 源目录与独立解包19项合成测试、候选独审、12项进度状态测试、12项传输测试及独立传输审阅均通过；均不替代真实评价结果。

通过用户既有 VS Code `school-hpc` 认证连接，终端hostname核对为node168；未新建SSH登录。临时固定端点传输桥只接受本包与27件静态清单、7件只读派生输入，私有token不写科学封包/页面。已上传封包并核SHA；当前正在部署核查，未报告真实目标结果。

## 执行范围

A/CIC_DEV 179,886查询，B/UNSW_DEV 148,316查询；原参考、密参考、错设备密参考三臂；四ε、三seed及集成；观察期后主视图、全量并列。固定源选择、阈值、几何、尺度、窗口和供体，预计912,302,797距离对。

只评价保存分数与已编码特征；新增前向、训练、编码、源CAL全部0。第三池保持 `DEFERRED_MISSING_FROZEN_BASE_B2`，阶段完成不能称原三池完整。99%阈值权衡不在本次运行范围；保存逐UID原始/修正分数以供后续登记分析。

## 进度与停止规则

新页预留 <http://127.0.0.1:18771/>，保留上一轮179602的18770终态。普通隐藏程序负责显示调度器、连接、池/支持臂/指标阶段；AI不持续轮询。科学FAIL继续登记配对，身份/数据/数值/资源异常停止并保留现场，零自动重跑。

**当前提交及启动终态以稍后本文件追加回执与deployment的SUBMIT/MONITOR/STARTUP_ACCEPTANCE为准。本文此段为提交前部署快照，不是已开始评价的证据。**
