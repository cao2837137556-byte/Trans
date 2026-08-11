# CKDA D0 正式 bundle — Kimi 验包终审

- 日期：2026-08-11
- 对象：`issue27ckda_d0_representation_compatibility_20260811_upload_bundle.tar.gz`
- 报告：`ckda_d0_bundle_ready_for_kimi_review_20260811.md`（commit `5381749`）
- 实现绑定 commit：`7178dccfd8d74d5b791846686e8015877099addd`

## 总结论：BUNDLE PASS

## 独立复验记录（全部本地重算，非转述）

| 项 | 期望 | 实测 | 结果 |
|---|---|---|---|
| archive SHA-256 | `c979638ecf430946cdd9e2614b082c42bc5f78f6cadd4bf545ff88afd70aade9` | 同左 | PASS |
| archive bytes | 665,814,425 | 665,814,425 | PASS |
| `.sha256` 侧车 | 与 archive 一致 | 一致 | PASS |
| tar 条目数（含目录） | 3,358 | 3,358 | PASS |
| 禁用标记（cooler-motor / seed37/47 全写法 / `.pyc` / `__pycache__`） | 0 | 0 | PASS |
| `bundle_commit.txt` = `bundle_identity.json.commit_sha` | `7178dcc…` | 一致 | PASS |
| 包内 `contract_sha256` | FROZEN `ac4e2c20…c9c8b5` | 一致 | PASS |
| `final_included` / `seed37_47_included` | false / false | false / false | PASS |
| 包内 netFound `model.safetensors` 流式复算 | 官方 `e6237f49…f5105`（698,780,900 bytes） | `e6237f49ce58840f8bf7d0cafa5ae80f58d05ea158053d031792d0369d7f5105` | PASS |

## 工程判定

- 两次本地组包拦截（B1 Windows 路径分隔符、B2 生成 JSON 的 CRLF）均为**本地打包缺陷**，未触及 HPC、未构成科学证据；修复 commit（`7a8be7d`、`7178dcc`）与回归门已在报告中钉死。接受定性。
- linux wheels 17 个全部带钉死哈希，`final_included=false`、`seed37_47_included=false` 写入身份文件。
- installer 需要字面环境变量 `CKDA_D0_SUBMIT_AUTHORIZATION=YES` 才提交作业，授权门在包内可执行。

## 授权边界

- 本 PASS 仅表示 **bundle 本身合格**。
- HPC 正式提交仍需**用户明确授权**。
- D0 verdict 即便 PASS，也只授权起草 D1 FROZEN，不授权训练、导师损失函数、seed 37/47 或 FINAL。
