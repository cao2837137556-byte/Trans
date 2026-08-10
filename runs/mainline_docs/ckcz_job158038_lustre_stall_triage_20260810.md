# CKCZ job 158038 Lustre 写入停滞定性（2026-08-10）

状态：**ENGINEERING FAILURE — HARD I/O STALL CONFIRMED — NO SCIENTIFIC VERDICT — R2 REVOKED**

## 1. 已确认事实

- AMD job `158038` 使用 r2 bundle SHA-256
  `4c29122a7844b0a772a9bad759e86ce6ede2ed9e2d842e90b8a7de33c490fc96`；
- bundle、冻结输入、29/31 cache、19 项合同测试、真实 253,326 Gotham protocol rows 的
  lineage `missing=0` 与 scheduler dry validation 全部通过；
- 正式诊断越过 job 158015 的 `join_predictions` 失败点，已落盘 prediction join、pair state、
  conflict audit、前三条 scalar frontier，并进入第四条
  `pair_conflict_span_seconds_so_far`；
- 未生成 `ckcz_verdict.json`，post-result validator 未运行，故没有科学 verdict；
- 用户已按取证后停止指令请求取消 job 158038，最终 Slurm 终态待回读。

## 2. 硬停滞证据

对以下对象连续三次、每 30 秒采样，全部字节级不变：

- 临时文件
  `.ckcz_attack_family_metrics_pair_conflict_span_seconds_so_far.csv.dbk_w6fc`；
- size：`67,108,864` bytes（精确 64 MiB）；
- mtime：`2026-08-10 13:08:58 +0800`；
- batch `AveCPU=00:01:19`、`MaxRSS=1,559,692K`、累计读写量均不再变化。

在运行约 1 小时 33 分时，通过同一 Slurm allocation 的只读进程检查确认：

```text
PID 111213  STAT=Il  TIME=00:01:18  WCHAN=osc_extent_wait
python -u ...issue27ckcz_endpoint_pair_conflict_diagnostic_v1.py
```

Lustre 证据：文件单 stripe、stripe size 1 MiB、落在 OST index 2。用户 quota 无 bquota/blimit；
`/public` 总体 41% 使用，OST2 47% 使用，排除全局容量和用户配额耗尽。

## 3. 根因

`atomic_csv` 先把完整 CSV 写入 `SpooledTemporaryFile`，随后执行：

```python
raw = stream.read().encode("utf-8")
atomic_bytes(path, raw)
```

`atomic_bytes` 再对完整 payload 执行一次 `handle.write(payload)`。第四条 family 明细为大型输出，
该单次整体写在 Lustre client 的 OSC extent 写回等待中硬停滞。原 heartbeat 只证明 Slurm shell
存活；没有完成单位或字节变化，不能作为有效进度。

## 4. 科学边界

- job 158038 是 compute/runtime engineering failure；
- 已落盘的部分 frontier、family、pool、bootstrap 临时文件均不得拼接、补算或引用；
- 本次不支持 `CKCZ_ORACLE_NO_INFORMATION`，也不支持 episode-veto 路线 GO；
- r2 bundle 与其 job-id 文件只保留为失败证据，严禁直接重提；
- cooler-motor、seed 37/47 与 FINAL 未触碰。

## 5. 永久修复合同

1. `atomic_csv` 必须直接流式写同目录临时文件，禁止完整 CSV `read().encode()` 和禁止调用
   `atomic_bytes` 承载大型 payload；完成流式 readback 后才能同文件系统 `os.replace`；
2. `atomic_bytes` 增加小对象上限，任何大型调用 fail-closed；
3. 合同测试必须拦截 `atomic_csv -> atomic_bytes` 回归，并覆盖超过旧 spool 阈值的多行输出、
   union schema、行数 readback 与无残留临时文件；
4. 诊断必须把内部完成阶段和 scalar/output 单元写入 node-local progress 文件；Slurm 必须报告
   完成单位，而不是只报 heartbeat；
5. result-producing job 内增加 no-progress watchdog。真实诊断超过冻结停滞阈值没有 progress
   更新时 fail-closed、无科学 verdict；
6. 修复、测试、真实工件审计、Kimi 独立审查、新 r3 bundle 审查和用户重新授权全部完成前，
   launch gate 保持关闭。

拒绝路径：延长 8 小时等待；增大内存；换 OST 或重提同一 r2；删除大型明细；使用 job 158038
部分结果续算；将 heartbeat/Slurm RUNNING 当作推进证据。
