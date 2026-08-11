# CKDA D0 r2 repair overlay — Kimi 包审

- 日期：2026-08-11
- 对象：`issue27ckda_d0_representation_compatibility_20260811_r2_repair_overlay.tar.gz`
- 报告 commit：`d973c80`

## 总结论：OVERLAY PASS

## 独立复验记录（全部本地重算，非转述）

| 项 | 实测 | 结果 |
|---|---|---|
| overlay SHA-256 | `6dc832e59b4fc6e716f85dd7810e275c9c9b261dcd3fda4c086cac607e57e140`，与报告一致 | PASS |
| overlay bytes | 145,185 | PASS |
| overlay 成员数 | 7（6 个内容文件 + r2 `SHA256SUMS` 自身），无任何删除项 | PASS |
| r1 vs r2 差异集（独立从 r1 归档提取 SHA256SUMS 比对） | 恰好 = 2 新增（py39 兼容脚本、`PY39_COMPAT_AUDIT.json`）+ 4 变更（`bundle_commit.txt`、`bundle_identity.json`、installer、补丁后 `netFoundModels.py`），**无其他差异、无移除** | PASS |
| overlay 6 个内容文件哈希 vs r2 `SHA256SUMS` | 全部一致（首轮 mismatch 为路径前缀格式差异，规范化后 ALL MATCH） | PASS |
| 补丁后 `netFoundModels.py` | 哈希 `a66834ea194a…31526` 与 `PY39_COMPAT_AUDIT.json` 记录一致；与 r2 完整构建目录内副本一致 | PASS |
| 补丁后文件 Python 3.9 文法 | `ast.parse(feature_version=(3,9))` 通过；无 `match problem_type`，含 if/elif 改写 | PASS |
| `PY39_COMPAT_AUDIT.json` | `replacement_count=1`、`python39_ast_files=17`、`semantic_change=NONE_SYNTAX_EQUIVALENT_IF_ELIF`、上游 SHA `a70366ea…d0ed` 钉死 | PASS |

## 判定

- overlay 内容差异集**恰好**等于修复所需的最小集合，没有夹带任何其他变更。
- r1 + overlay 与完整 r2 的等价性：我以"r1 归档 SHA256SUMS vs r2 SHA256SUMS 全量比对"独立复证——差异仅这 6 个内容文件，等价门成立，无需重传 665 MB。
- 远端 r1 目录与 job 158187 保留为失败证据的约定不变。

## 授权边界

- 本 PASS 授权 Codex 交付 overlay 上传/安装命令。
- HPC 重新提交仍需用户明确授权。
