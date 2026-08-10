# CKCZ job 158038 流式写入修复：待 Kimi 独立审查（2026-08-10）

状态：**IMPLEMENTED AND LOCALLY VALIDATED — KIMI REVIEW REQUIRED — LAUNCH GATE CLOSED**

## 1. 修复范围与提交

- 失败定性：`f4138cb`；
- 实现提交：`f6e89ae`；
- 修改严格限于：
  - `repo/ood/issue27ckcz_endpoint_pair_conflict_diagnostic_v1.py`；
  - `repo/ood/issue27ckcz_endpoint_pair_conflict_contract_tests_v1.py`；
  - `scripts/issue27ckcz_endpoint_pair_conflict_diagnostic_formal.slurm`；
  - `scripts/issue27ckcz_install_and_submit.sh`。

FROZEN prereg、erratum、allowlist、四个 scalar、exact cuts、Oracle 判门、bootstrap=200、
family/pool 分母、FINAL 排除均未改变。没有删除任何大型明细，也没有 family 补丁。

## 2. 实现修复

### 2.1 大 CSV 流式原子写入

旧路径：

```text
rows -> SpooledTemporaryFile -> read all -> encode all -> atomic_bytes -> one large write
```

新路径：

```text
rows -> csv.DictWriter -> same-directory temp file -> streaming readback -> fsync -> os.replace
```

- 不再生成完整 CSV `bytes`；
- 每 100,000 行 flush 并报告完成行数；
- 临时文件流式 readback，逐行确认 union header 与精确行数；
- 只有 readback PASS 后才执行同文件系统 atomic rename；
- 异常路径删除本次临时文件，不产生 verdict。

`atomic_bytes` 新增 `8 MiB` 小对象上限，未来任何大型 payload 调用直接 fail-closed。

### 2.2 完成单位与 no-progress watchdog

- 诊断通过 `--progress-file` 写 node-local 原子 JSON，不进入科学输出、不参与 verdict；
- progress 含 sequence、内部 stage、scalar、artifact、expected/written rows；
- heartbeat 现在报告 `diagnostic_stage/sequence/age_seconds`，不再只报 shell 存活；
- Slurm 以冻结 `STALL_SECONDS=1200` 监视 node-local progress；20 分钟无完成单位时写
  `progress_stall.txt`、终止诊断并 fail-closed；
- 失败时复制最后 progress 到 control evidence；成功时随 runtime_control 打包；
- watchdog failure 不能生成 `ckcz_verdict.json`，validator 仍只在诊断返回 0 后运行。

## 3. 本地验证证据

### 3.1 22 项合同测试

`status=PASS`。原 19 项全部保持；新增：

1. `oversized_atomic_bytes_fail_closed`；
2. `large_csv_streams_without_atomic_bytes`；
3. `node_local_progress_reaches_complete`。

大型 CSV 回归样例：

- `5,000` 行；
- `10,292,802` bytes（超过旧 8 MiB spool threshold）；
- 临时 monkeypatch 令任何 `atomic_bytes` 调用立即失败；
- 新实现完成 union schema `row,payload,late_field`、精确 5,000 行 readback；
- 临时文件泄漏 `0`。

### 3.2 语法与静态门

- 两份 Python `py_compile`：PASS；
- Slurm、installer、validator `bash -n`：PASS；
- installer 静态要求 `--progress-file`、`STALL_SECONDS=1200`、
  `CKCZ_PROGRESS_STALL` 三个 wiring token；
- 搜索确认旧 `stream.read().encode()` / `atomic_csv -> atomic_bytes` 路径已消失。

### 3.3 真实冻结工件

对本地拉回的 CKBW 157624 + CKBY 157930 复核：

```text
prediction_rows=297326
gotham_protocol_rows=253326
unique_uids=253050
snapshot_rows=287448
missing=0
```

本修复没有改变 join、记录分母或 lineage 语义。

## 4. r3 隔离

builder 已改为独立名称：

```text
issue27ckcz_endpoint_pair_conflict_diagnostic_20260810_r3
```

r3 使用独立 bundle root 与独立 job-id 文件；r1/r2 文档均作废。builder 尚未执行；必须先取得
Kimi 对本实现、测试、Slurm watchdog 和 builder wiring 的 PASS，再把该 PASS 文档纳入包并构建。

## 5. 请求 Kimi 审查

请独立核验：

1. `atomic_csv` 是否完全消除完整 payload materialization 与大型 `atomic_bytes`；
2. gzip/non-gzip close、fsync、readback、rename、异常清理是否正确；
3. 22 项合同测试独立复跑是否全 PASS，旧 19 项是否零回归；
4. node-local progress 是否不进入科学判定，watchdog 是否只在 1,200 秒无完成单位时 fail-closed；
5. watchdog/TERM/KILL/cleanup 任一路径是否都不可能产生科学 verdict；
6. installer 静态 wiring、r3 隔离和旧 r2 作废是否完备；
7. FROZEN 科学合同是否零漂移。

请求授权边界：若 PASS，只授权把 Kimi 审查文档纳入 builder 并构建/验证 r3 bundle。
HPC 再提交仍需 r3 bundle 独立审查与用户新的明确授权。
