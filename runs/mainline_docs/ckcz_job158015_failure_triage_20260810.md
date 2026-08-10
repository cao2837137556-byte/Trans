# CKCZ job 158015 失败初筛（2026-08-10）

状态：**ENGINEERING FAILURE — ROOT CAUSE PENDING LOG EXTRACTION — NO SCIENTIFIC VERDICT — DO NOT RESUBMIT**

## 1. 已确认事实

用户提交终端截图显示：

- bundle SHA、冻结输入、cache 在线门与 18 项合同测试均已通过，installer 到达 scheduler dry validation；
- `sbatch --test-only` 显示的 `158014` 是调度器 dry-validation 编号，不是正式科学作业；
- 唯一正式提交 job 为 AMD `158015`，installer 已记录
  `CKCZ_AMD_JOB_ID=158015` 与 `CKCZ_SUBMISSION_RECORDED`；
- runtime gate 终态：

```text
CKCZ_RUNTIME_GATE_FAIL job=158015 phase=diagnostic_real_inputs state=FAILED
status=FAILED
phase=diagnostic_real_inputs
exit_code=1
failed_utc=2026-08-10T03:10:00Z
CKCZ_SUBMISSION_RUNTIME_FAILED
```

## 2. 当前分类与证据边界

分类：**compute/runtime engineering failure**。正式 Python 已进入真实输入阶段，但未返回，
post-result validator 未运行，故：

- 不能解释为 `CKCZ_ORACLE_NO_INFORMATION`；
- 不能解释为 endpoint-pair 路线失败；
- 任何 partial CSV/metadata 均不是结果；
- job id 持久化文件必须保留，当前 bundle 不得原样直接重提。

截图只显示 Slurm 外层 failure marker，尚未显示正式程序在 run root 写入的 JSON failure 或 control
目录中的 traceback。因此根因、可复用产物、最小修复与回归门仍待一次只读日志提取。

## 3. 下一步：只读日志提取

读取且不修改以下对象：

- run root `job_failure.txt` / `slurm_failure.txt`；
- control root `job_failure.txt` / `diagnostic_stdout.log`；
- Slurm stdout/stderr；
- `sacct` 终态与资源记录。

在精确 traceback 落库、根因分类、永久回归门通过前，禁止删除 job 158015、清除 job-id 文件或
再次 `sbatch`。
