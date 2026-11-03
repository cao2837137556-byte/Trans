# AB 起点对照：真实 T → E 授权

2026-09-12。用户在实现完成与完整真实 T→E 范围说明后明确回复“授权继续”。
本授权覆盖冻结 AB-start v1 的一次完整真实执行：T 入口核对并复用旧 P，
C0_AB / R_AB 各独立从封存 AB 开始，各 20 轮、3940 更新；两臂终点核验
封存通过后自动进入一次固定 E。正常阶段转移不再询问；异常停止、零重试。
科学表现不佳仍完整报告，不据此加训、换 checkpoint 或更改规则。

执行前已核对 codex/exp-mainline，HEAD
4b28747b09480471e2bac1beb3a9badf27280efb；既有无关修改保留。
check-implementation 返回 IMPLEMENTATION_READY_NO_REAL_EXECUTION；
T/E 均 NOT_STARTED，未有重复尝试。实现报告 SHA 侧车一致。
实现包 SHA256SUMS SHA：
03f0091297052b0a4e0d8816bea424e5f3a48faff3cfecf450d0baa2635c34c2。

执行入口：scripts/start_frontend_ab_start_control_v1.ps1
-Stage TE -AuthorizeTraining -AuthorizeEvaluation。
状态入口：scripts/show_frontend_ab_start_control_v1.ps1。
阶段目录：runs/frontend_ab_start_control_t_v1_20260912/ 与
runs/frontend_ab_start_control_e_v1_20260912/。
每阶段 status.html 自动刷新；supervisor_terminal.json 与封存校验决定终态。

无新 P、数据下载、HPC、历史实验重跑、超参搜索、定时 LLM 轮询。
T 上限 4 小时，E 上限 30 分钟，采用冻结资源限制与本地持久监督。
授权不代表结果成功；历史严格继承 FAIL、联合 NOT_REACHED、
新设备入网 NOT_EVALUATED 在新结果核验前保持。
