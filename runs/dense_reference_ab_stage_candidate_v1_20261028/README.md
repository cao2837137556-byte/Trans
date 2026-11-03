# A/B 先行密参考评价候选代码

2026-10-28。**待用户确认分阶段评价修订与本次云端执行范围；尚未运行真实目标评价。**

原登记三池中，`CIC_THREE_DEVICE_REGRESSION_CONSUMED` 缺少原冻结 BASE/B2/receipt。本候选包仅准备先完成 A/B 的三臂×四 ε×四 suffix；第三池始终明确为 `DEFERRED_MISSING_FROZEN_BASE_B2`，不宣称原三池完整。原 `dense_reference_matrix_v1_20261027` 及其封存输出保持原字节。

`src/matrix.py` 由原矩阵 runner 独立复制，新增范围及授权门禁，并保存逐 UID 原始/修正分数。三臂算法、源 λ 选择重放、固定切点与尺度、观察期后重赋权、全量并列和科学 FAIL 继续配对保持；`src/metrics.py` 和五个数学依赖逐字节复制。

生产 manifest schema 为 `dense-reference-ab-stage-input-v1`，`evaluation_scope=AB_DENSE_STAGE_PENDING_THIRD_POOL`。`pools` 必须恰好按顺序列出 `CIC_DEV`、`UNSW_DEV`，均为 `DENSE_MATRIX`。生产要求 `stage_matrix_ready=true`、`full_matrix_ready=false`、`original_registered_matrix_complete=false`，并绑定 `third_pool_deferred`。源补编码、真正密源 CAL 产物必须完整且 SHA 绑定。

生产授权 schema 为 `dense-reference-ab-stage-authorization-v1`，scope 必须为 `AB_DENSE_STAGE_PENDING_THIRD_POOL`，且同时确认 `protocol_amendment_confirmed`、`evaluated_pools`、`deferred_pool`、精确 manifest/source RESULT SHA 和真实用户 evidence。旧三池授权、旧编码/CAL 授权均无效。**本目录不提供真实 `APPROVED.json`；仅创建代码不构成用户批准。**

结果将分别保存 A/B 阶段科学状态与原三池完整状态。即使 A/B 阶段全部达标，原三池科学状态仍为未完成，不能提升为全矩阵 PASS。三臂各 ε 的 `*_decisions.npz` 除原 UID、base/corrected 判决外，新增三 seed 原始/修正 logits、固定顺序集成 logits、切点、λ、支持和资格，便于独立审计。没有阈值重选或 99% 召回诊断入口。

合成测试只使用临时测试数据：

```powershell
python -B -m unittest discover -s tests -v
```

`tests/original_matrix_frozen.py` 为原 runner 的冻结测试对照，不是生产入口。`ORIGINAL_CODE_PROVENANCE.json` 记录原样依赖身份。源 seal 的远端绝对路径在本地准备时须通过明确的 remote→local alias 解析及 SHA 核验，不得改写原 seal；此部分由候选输入准备工具另行记录。

候选超算入口为 `hpc/run_ab_stage.slurm`，仅执行一次 `src/launch_stage.py`。launcher 接受 `--package --assets-root --manifest --source-cal-result --approval-file --output`，新输出必须位于包外。授权还必须绑定 `sha(PACKAGE_SHA256SUMS)`、`total_wall_seconds≤7200` 和 `retries=0`。先验授权与包身份，后建只读输入视图；复用 179602 产物，不编码、不重算源 CAL、不训练。

资源固定 amd 单节点、4 CPU、16GiB Slurm、进程树 RSS 8GiB、2 小时 Slurm 总硬限、矩阵输出 2GiB、至少 12GiB 空闲；无自动重试。脚本先核原 `environment.sh` SHA，再加载环境，显式优先使用已验 179602 私有 NumPy 2.0.1 overlay；launcher 实际检查 NumPy 版本及模块路径。原 `common.py`、`supervisor.py` 原样复制；`hpc/fallback.py` 记录脚本启动失败，并保持第三池未完成状态。脚本和授权文件的创建不等于已提交；当前没有真实授权文件。
