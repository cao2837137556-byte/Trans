# 依赖修复版A/B正式评价：新179700提交与启动验收

**终态补充：179700已正常完成，完整产物已下载并通过SHA及192份指标的独立离线核验。** A/B密参考主集成FPR为3.993482%/9.519654%，召回100%/99.966594%；科研目标未达，非工程故障。见[正式结果回传](20261028_dense_reference_ab_final_result_readout_codex.md)。以下启动时RUNNING与待读数文字均为历史记录。

2026-10-28。用户已明确“赶紧修复异常 重新开始运行”，批准[修复版具体执行卡](../../dense_reference_ab_stage_dependency_repair_v1_20261028/EXECUTION_CARD.md)。**已新提交一次179700，node185正常RUNNING，已进入CIC_DEV的错设备密参考支持计算。** 这是已获新授权后的独立新尝试，不是后台自动重试。原179680失败现场、原候选和原r1封包保持。

## 授权与单次提交

- 新授权SHA：`7798502dc25f9aa1a17adca460cbe19bb37bf1e94f95a8dd1dbdfe54fc557e23`。
- 修复包清单SHA：`85637f3ae213ef08bf3cb70976a3188246eb03554d4b7fe7393f4cfe4414d9e8`。
- archive SHA：`034a576d8c04bb1f06f3330f79a7ca1333e27e2ac4f77d1ac27c68373541ff5f`，618,516字节。
- 修复前已通过超算11项测试及328,202条metadata预检，见[工程修复回执](20261028_dense_reference_ab_stage_dependency_repair_codex.md)。本轮新授权同时绑定修复SHA、原包/矩阵/源CAL SHA和新的用户证据，旧179680授权未复用。

通过既有school-hpc的远端Linux终端执行固定单次bootstrap；完整包SHA和新授权检查后排他创建SUBMISSION_STARTED，再仅调用一次固定sbatch。收到真实`job_id=179700`回执，随后以该job的认证只读快照交叉核对。错误、超时或不确定提交结果均不自动第二次调用。没有新建SSH登录、没有重传大数据、没有修改共享环境。

## 真实启动证据

启动验收快照显示调度器RUNNING、node185、真实matrix worker存活；修复授权、原输入及NumPy2.0.1原179602 overlay门已通过。科学stage已由启动进入`CIC_DEV / SUPPORT_R-DENSE-WRONG`，峰值进程树RSS约1.49GiB，低于8GiB限制，原缺模块阻塞已越过。尚无完整池结果，不能报告新的A/B误报或召回。

本轮固定amd、4CPU、16GiB、最多2小时、进程树RSS8GiB、输出2GiB、0自动重试。只评价原登记A/B两池的原参考/密参考/错设备密参考，四ε、三seed及集成；主ε=.1个百分点、观察期后为主、全量并列。编码与源CAL继续只读复用179602，新增前向、训练、编码和CAL均0；不调整目标阈值、λ、窗口或供体。第三池仍延期、未评价，原三池完整性为false。

证据目录为 `runs/dense_reference_ab_stage_dependency_repair_execution_20261028/`，包括 `APPROVED.json`、`AUTHORIZATION_RECEIPT.json`、`SUBMIT_UI_RECEIPT.json`、`STARTUP_EVIDENCE.json`、`STARTUP_ACCEPTANCE.json`、`EXECUTION.json` 及 `remote_progress/job_179700/`。启动验收只证明该可信快照时正常，后续以普通进度同步的最新状态为准。

## 进度入口保持不变

- [18771主进度页](http://127.0.0.1:18771/)现在显示179700的新作业状态、真实池/支持臂及终态。
- [18773历史失败页](http://127.0.0.1:18773/)保留179680，不将其失败历史改写为成功。
- 原179602编码/CAL历史仍在18770与页面历史入口。

普通隐藏pythonw负责5秒状态同步，完成/异常时保存终态；页面对断连显示未知，不把旧快照当正常运行。进度组件16项测试通过，未弹出系统终端；AI仅做提交和启动必要验收，不持续轮询。
