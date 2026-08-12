# CKDA D1 bundle — Kimi 包审

- 日期：2026-08-12
- 对象：`issue27ckda_d1_representation_probe_20260812_upload_bundle.tar.gz`
- 构建 commit：`fc55c59`，报告 commit：`8b8cc08`

## 总结论：BUNDLE PASS

## 独立复验记录（全部本地重算，非转述）

| 项 | 实测 | 结果 |
|---|---|---|
| archive SHA-256 / bytes | `10356525…f2a2` / 97,442，与侧车一致 | PASS |
| 内部 `SHA256SUMS` | 独立解包重算 25/25 | PASS |
| `bundle_commit.txt` = `identity.commit_sha` | `fc55c598…6233` | PASS |
| 包内 FROZEN 文档复算 | = 冻结合同 `ecb42992…50aa9` | PASS |
| D0 runtime 复用引用 | `d0_bundle_identity=…_r2`，netFound checkpoint `e6237f49…f5105`（不重传 665 MB，设计正确） | PASS |
| 成员范围 | 33 条目 = 25 文件 + 8 目录；仅代码/脚本/合同文档/allowlist，无数据、无权重、无 `.pyc` | PASS |
| FINAL/seed37/47 | `final_included=false`、`seed37_47_included=false`；两个 allowlist CSV 中 cooler-motor 出现 0 次 | PASS |
| CR 字节 | 全包 0 | PASS |
| 未授权提交门 | `CKDA_D1_SUBMIT_AUTHORIZATION` 非 YES 即 exit 3 | PASS |

## 工程备注

- GNU tar 对本包列目录报 `unexpected end of file`，但 Python tarfile 完整读出 33 条目且全量哈希通过、archive SHA 与侧车一致——判定为 gzip 封装格式差异（padding），非内容损坏。上传前建议在 HPC 端 `sha256sum -c` 侧车后以 Python tarfile 或 `tar -xzf` 实测解包；若 HPC GNU tar 拒绝解包，属工程问题，重打包即可，不影响科学内容。

## 授权边界

- 本 PASS 仅表示 bundle 合格。上传与 HPC 正式提交需用户明确授权。
