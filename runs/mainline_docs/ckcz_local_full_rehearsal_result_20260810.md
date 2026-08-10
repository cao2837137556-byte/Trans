# CKCZ r3 本地真实输入全流程彩排结果（2026-08-10）

状态：**ENGINEERING REHEARSAL PASS — NO SCIENTIFIC VERDICT — NO HPC SUBMISSION AUTHORIZATION**

本报告只确认 r3 流式实现能在完整真实非 FINAL 输入上端到端完成，并专门复验 job 158038
曾卡死的大型 span CSV 写出路径。`bootstrap_reps=20` 仅用于走通工程路径；其产生的内部 verdict
禁止解释、禁止保存、禁止进入任何科学结论。

## 1. 冻结输入与代码身份

- r3 bundle：`issue27ckcz_endpoint_pair_conflict_diagnostic_20260810_r3_upload_bundle.tar.gz`
  - bytes：52,581
  - SHA-256：`0f68b154f0d2c45cc5520e25746d30a273a096a8026cf0df6fdbb1c1d8e9d59c`
  - `bundle_commit.txt`：`6ec2686f690ab29021f9b5225b8c8d469bbd9e42`
  - 包内 SHA：22/22 通过
- 严格拉回输入包：`ckcz_rehearsal_inputs_20260810.tar.gz`
  - bytes：15,256,311
  - SHA-256：`e4d3c3e479130b0e39664279d4f632a6d08458a7b8061bebaf5e54fcedc03646`
  - 包内 SHA：58/58 通过
  - cache：Gotham 24 NPZ + auxiliary 31 NPZ；仅来自冻结 allowlist 与 manifest exact join
- 记录预测：SHA-256
  `d1e905924e74bf390aaaae79ee68f10312dc0bc1cdebff88848d4d3ee64adf85`
- Gotham lineage snapshot：SHA-256
  `b2ef1f7d0244cc7abb8665c25364744f794190f411482e4e202e346cb850279c`
- 执行代码：从已验包的 r3 payload 直接运行，不从工作区复制或替换实现。
- 未加载或命名任何 `cooler-motor`、seed 37、seed 47 工件。

## 2. 彩排参数与运行结果

- Python：3.10.0；本地 Windows；8 线程环境变量与正式 Slurm 一致。
- 参数与正式任务一致，仅将 `bootstrap_reps` 从正式的 200 降为工程彩排的 20。
- 真实输入诊断退出码：0。
- 端到端运行时间：73 秒。
- 最终 progress：`stage=complete`、`sequence=111`、`output_files=27`。
- 生成文件：27 个，共 384,683,224 bytes；`SHA256SUMS` 覆盖的 26 个成员全部重算一致。
- 无失败 marker，无隐藏 atomic 临时文件，无 `.tmp` / `.dbk` 残片。

## 3. r2 卡死路径的直接回归证据

job 158038 曾在
`ckcz_attack_family_metrics_pair_conflict_span_seconds_so_far.csv` 的约 64 MiB 临时文件写入处
进入 Lustre 等待且长期无已完成单元。

r3 本地真实输入彩排中，同一正式工件已完成原子终结：

- 文件：`ckcz_attack_family_metrics_pair_conflict_span_seconds_so_far.csv`
- 完成大小：101,417,030 bytes
- 行数：788,512
- 其 SHA-256 进入并通过最终 `SHA256SUMS` 校验。

因此，旧的“整表内存物化后一次性写出”代码路径已不再存在于 r3；流式写出能够跨过此前的
64 MiB 卡点并完成最终 rename。该证据验证代码修复，但本地文件系统不能替代 Lustre 上的正式运行证据。

## 4. 工程合同独立复核

以下只核验结构与分母，不读取或解释 Oracle 可行性值：

- allowlist audit：55 source；metadata：336,123 行；pair state：297,326 行。
- Gotham lineage：287,448 行；读取数组严格为
  `uid/source/role/m1_phase/recorded_index`，forbidden arrays 为空。
- 五个 held-value 分母与冻结协议一致；unexpected metadata miss 为 0；ToN 预期 miss 为 20,000。
- pair-state `(held_value, uid)` 唯一；`review=True` 行为 0。
- 攻击 family 并集为 16；每个 frontier 点均有 16 条 family 行和 4 条 OOD pool 行。
- 四个 scalar 的 frontier/family/OOD 行数分别为：

| scalar | frontier | family | OOD pool |
|---|---:|---:|---:|
| `pair_conflict_count_so_far` | 5,322 | 85,152 | 21,288 |
| `pair_consecutive_conflicts_so_far` | 3,576 | 57,216 | 14,304 |
| `pair_conflict_fraction_so_far` | 29,550 | 472,800 | 118,200 |
| `pair_conflict_span_seconds_so_far` | 49,282 | 788,512 | 197,128 |

- bootstrap：1,052,760 行；每个 frontier 点 12 行；`bootstrap_reps=20` 全列一致；
  `cluster_unit` 仅为 `source` / `pair`，不存在记录级 bootstrap。
- 所有 frontier 的 `cut_use` 均为 `FORBIDDEN_FOR_SELECTION`。

## 5. verdict 隔离与清理

当前正式实现对 `reps>=20` 会生成内部 `ckcz_verdict.json`。本次彩排按预先声明的隔离规则：

1. 不验证、不摘录、不讨论其 status 或 compatibility 值；
2. 不运行正式 200-rep post-result validator，不生成科学结果包；
3. 只保留本报告中的工程结构证据；
4. 本报告落盘后删除受控临时目录中的全部彩排输出、内部 verdict、解包输入和临时验证器；
   原始经哈希验证的两个 `.tar.gz` 与 sidecar 保留供复现。

清理已执行并复核：受控临时目录共 113 个文件、402,576,902 bytes 已删除，目标路径已不存在；
上述两个原始压缩包及其 sidecar 均保留。删除内容不可从该临时目录恢复，但可由保留的输入包和 r3 包复现。

## 6. 结论与授权边界

结论：**r3 本地真实输入全流程彩排 PASS**。流式修复已通过完整输入、完整 frontier 枚举、
20-rep bootstrap 路径和大于 64 MiB 的关键写出回归。未发现新 lineage、FINAL、分母、原子终结或
输出覆盖问题。

本 PASS 只解除“本地真实输入彩排”门，不构成 Oracle 科学判断，也不自动授权 HPC 提交。
下一步为 Kimi 独立审查本报告；审查 PASS 后仍由用户单独授权 r3 正式提交。
