# CKCZ job 158015 失败初筛（2026-08-10）

状态：**ENGINEERING FAILURE — ROOT CAUSE CONFIRMED — NO SCIENTIFIC VERDICT — DO NOT RESUBMIT ORIGINAL BUNDLE**

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

## 4. 精确 traceback 与根因

只读日志提取确认正式错误为：

```text
stage=join_predictions
RuntimeError: unexpected metadata join miss
support_val:select:0  -> processed/iotsim-combined-cycle-10.csv
support_val:select:13 -> processed/iotsim-ip-camera-museum-1.csv
```

job `158015` 在 node187 运行 22 秒，`State=FAILED`、`ExitCode=1:0`，未进入 validator；run root
仅有 metadata/cardinality/temporal audit 与 failure marker，没有 pair state、frontier、bootstrap
或 verdict。

根因不是 cache 缺失，也不是 allowlist/hash/schema 漂移。CKBJ/CKBW 的 Gotham UID 构造为：

```text
uid = "{role}:{m1_phase}:{row_index_in_frozen_role_frame}"
recorded_index = frozen_role_frame[row_index].recorded_index
```

两者是不同坐标。CKCZ r1 的 `_prediction_target_index` 错把 UID 最后一段 `row_index` 直接当作
cache 的 `recorded_index`。真实例：`support_val:select:0` 的 recorded_index 是 `16621`；
`support_val:select:13` 的 recorded_index 是 `9665572`。因此严格 join 正确地 fail-closed。

## 5. 永久修复合同

不允许把这些行降级为 expected missing，也不允许按 source 内位置、时间或标签模糊匹配。修复
只复用 CKBY job 157930 已冻结且成功复核的 lineage snapshot：

- `ckby_drocc_feature_snapshot_seed27.npz`；
- 287,448 行；
- SHA-256 `b2ef1f7d0244cc7abb8665c25364744f794190f411482e4e202e346cb850279c`；
- 只读取 `uid/source/role/m1_phase/recorded_index` 五个 lineage 数组，不读取 `x/label/family`；
- 以 `(uid, source_group, role, phase)` exact many-to-one join 恢复 Gotham recorded_index；
- auxiliary 继续使用冻结 `aux:{role}:{source_group}:{target_row}` 函数；ToN 继续是唯一 expected
  metadata missing。

新增回归门必须明确构造 `uid suffix != recorded_index` 的样例，并断言仍 exact join 成功；另在
本地真实 CKBW 297,326 行预测与 CKBY snapshot 上证明所有非-ToN Gotham UID lineage 覆盖。
