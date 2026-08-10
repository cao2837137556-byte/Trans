# CKCZ job 158038 流式写入修复审查 — Kimi

日期：2026-08-10 | 审查者：Kimi | 对象：实现 `f6e89ae` + 交接 `60ba7df`

**总体结论：PASS。授权将本审查文档纳入 r3 并构建验包；HPC 再提交仍需 r3 包审 + 用户重新授权。**

附带一项**强烈建议**（见 §3）：提交前做一次本地全流程彩排，终结"失败-修复-再失败"循环。

---

## 1. 逐项审查结论（交接文档 §5）

| 审查项 | 方法与证据 | 结论 |
|---|---|---|
| 1. 消除完整 payload 物化 | 通读 diff：新 `atomic_csv` 走"DictWriter→同目录临时文件（1 MiB 缓冲）→流式 readback→fsync→os.replace"；旧 `SpooledTemporaryFile→read().encode()→atomic_bytes` 路径已消失；`atomic_bytes` 加 8 MiB fail-closed 上限，剩余调用方仅小 JSON/SHA256SUMS | PASS |
| 2. 句柄关闭/fsync/readback/rename/异常清理 | gzip 三层句柄关闭顺序正确（text→zipped→raw）；`written==len(rows)` 断言；readback 校验 header+行数；`finally` 无条件删临时文件 | PASS |
| 3. 22 项合同测试 | **独立复跑**：22/22 全 PASS，旧 19 项零回归；新增 3 项（超大 atomic_bytes 拒绝、大 CSV 不经 atomic_bytes、node-local progress 到达 complete）均在 | PASS |
| 4. progress 不进科学判定 + watchdog 语义 | `ProgressRecorder` 写 node-local（SLURM_TMPDIR）原子 JSON，从不进 `--out` 科学目录；watchdog 仅在 progress 文件 mtime 静默 ≥1200s 时 fail-closed | PASS |
| 5. watchdog/TERM/KILL/cleanup 无 verdict 路径 | watchdog TERM→KILL 诊断进程并 TERM wrapper；wrapper cleanup trap 写 `job_failure.txt`；verdict 仅在 `run()` 末尾 validate_outputs 之后写入；`diagnostic_status!=0` 直接 exit，validator 不运行 | PASS |
| 6. installer wiring + r3 隔离 + r1/r2 作废 | installer 静态要求 `--progress-file`、`STALL_SECONDS=1200`、`CKCZ_PROGRESS_STALL` 三 token；r3 独立 bundle 名/独立 job-id 文件；文档作废标记齐全 | PASS |
| 7. FROZEN 零漂移 | diff 不涉及四 scalar、cuts、判门、bootstrap=200、分母、FINAL 排除；未删除任何大型明细 | PASS |

## 2. 补充深度核验（主动排查"下一个失败点"）

- **cp 顺序**：`mkdir "$RUN_ROOT/runtime_control"`（L271）先于 `cp "$PROGRESS_FILE" ...`（L273），无新增顺序 bug。
- **watchdog 误杀风险**：逐段排查了 progress 静默窗口——最长的静默段是 `build_causal_pair_state`（约 30 万行 Python 循环，无中途 progress）。job 158038 全程（含该段及 3.5 个 scalar）约 93 分钟，单段估算为数分钟级，**远在 1200s 阈值内**，误杀风险低。残余风险已记录，若真发生会有 `progress_stall.txt` 明确证据。
- **大输出已实证**：停滞的 67 MiB family 明细属于 `atomic_csv` 路径（已重写）；`atomic_dataframe_csv` 的 33.6 万行 metadata 与 29.7 万行 state 在 job 158038 中已在同一文件系统**实际写成功**，非修复盲区。
- **span_seconds frontier 规模**：浮点 span 的唯一值多 → cuts 多 → family/bootstrap 明细行数大（停滞文件 64 MiB 即证据）。新流式路径正是为此规模设计，readback 逐行计数，可承载。

## 3. 强烈建议：提交前本地全流程彩排（dress rehearsal）

两次 HPC 失败的共同根源：**本地测试用合成数据，真实输入路径只在超算上存在**，导致两类真实数据相关问题（lineage 坐标、真实规模写入）都漏到了 HPC 才暴露。

两个 cache 总共只有约 21 MiB（gotham 18 MiB + auxiliary 2.3 MiB）。建议：

1. 用户从 HPC 只拉回**严格 allowlisted 的 55 个 npz + 2 个 manifest**（24+31，按 manifest exact join 枚举文件名；**绝不整个目录拉**，gotham 目录 29 个 npz 中那 5 个非白名单文件不碰）；
2. 本地用**与 r3 完全相同的代码和全部真实输入**端到端跑一遍（`--bootstrap-reps 20` 走通全部代码路径即可，HPC 正式跑 200 是同一代码路径）；
3. 彩排 PASS 后再授权 r3 提交。

这样 HPC 正式跑失败的可能性从"每轮都有新惊喜"降到接近零——剩下的只有排队和调度风险。该彩排不产生任何科学结论（bootstrap 次数不足 200，verdict 标 INVALID），纯工程验证。

## 4. 授权边界

本 PASS 授权：审查文档纳入 r3 + 构建/验证 r3 bundle。r3 包建好后我再审一次包；HPC 再提交需用户在 r3 包 PASS 后重新明确授权。
