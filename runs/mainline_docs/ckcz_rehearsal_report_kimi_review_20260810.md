# CKCZ 本地彩排报告复审 — Kimi

日期：2026-08-10 | 审查者：Kimi | 对象：`ckcz_local_full_rehearsal_result_20260810.md`（commit `8cf3502`）

**总体结论：PASS。彩排门解除。剩余唯一门：用户明确授权 r3 正式 HPC 提交。**

---

## 1. 独立复核明细（非转述）

| 复核项 | 方法与结果 |
|---|---|
| 彩排输入包真实性 | 本地保留的 `ckcz_rehearsal_inputs_20260810.tar.gz`：bytes 15,256,311、SHA-256 `e4d3c3e4…3646` 与报告一致；**独立解包复验：58/58 内部哈希全 OK** |
| 输入边界 | 独立清点：gotham 24 npz + auxiliary 31 npz，恰为白名单集合；`selected_cache_audit.csv` 中 FINAL marker（cooler/seed37/seed47）检索为 0 |
| 数字内部一致性 | 四个 scalar 的 family=frontier×16、pool=frontier×4 全部验算成立（含 span：49,282×16=788,512、×4=197,128）；bootstrap 总行 12×87,730=1,052,760 成立；27 输出/26 哈希（排除自身）模式成立 |
| r2 卡死点回归 | span family 文件 101,417,030 bytes > 64 MiB 旧卡点且完成原子终结——流式修复的直接回归证据成立 |
| verdict 隔离 | 报告只含工程结构数据，无 Oracle 可行性数值；彩排输出声明已销毁，保留两个原始压缩包可复现——处理符合预先声明的隔离规则 |
| 工作区残留扫描 | 本地 runs 目录无 ckcz/rehearsal 残留输出目录，清理声明与工作区状态一致 |

## 2. 工程判断

r2 失败的完整链路（真实输入→完整 frontier→大文件流式写出→bootstrap→原子终结→SHA256SUMS）已在本地全部走通，73 秒、退出码 0。r3 在 HPC 上的剩余风险仅剩 Lustre 行为差异与调度排队——流式写正是针对前者设计的，风险已最小化。

## 3. 授权边界

本 PASS 仅确认彩排有效。HPC 正式提交需用户明确授权；授权后 Codex 交付 r3 提交命令（须带 `CKCZ_SUBMIT_AUTHORIZATION=YES`）。正式跑为 `bootstrap_reps=200`，其 verdict 经 post-result validator 验证后才是唯一科学裁决。
