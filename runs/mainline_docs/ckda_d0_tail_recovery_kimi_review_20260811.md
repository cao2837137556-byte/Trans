# CKDA D0 job 158210 尾段恢复 — Kimi 审查

- 日期：2026-08-11
- 对象：commit `f82eabf`，报告 `ckda_d0_tail_recovery_ready_for_kimi_review_20260811.md`
- 失败签名：`TypeError: write_text() got an unexpected keyword argument 'newline'`（Python 3.9 无此关键字）

## 总结论：PASS（六问逐项裁定）

**Q1 失败分类：成立。** 崩溃点在 `validate_and_finalize`，发生在 census、E3/I1 双 pilot、候选排序、verdict、FINAL/label 边界审计**全部完成之后**。判为 `POST_RESULT_VALIDATION_PACKAGING_FAILURE` 正确，不构成对 I1/E3/CKDA 的科学证据。与 CKBV 154917 恢复先例同类。

**Q2 explicit-open 原子写：成立。** `temp.open("w", encoding, newline="\n")` + `handle.write` + `os.replace`，3.9 兼容且保持 LF/原子语义。运行时合同测试（LF 字节精确读回 + 临时文件零残留）本地复跑 PASS（`CKDA_D0_VALIDATOR_CONTRACT_PASS`）。

**Q3 AST + 运行时测试：对观测类别充分。** 独立扫描确认 CKDA 模块中 `write_text(newline=` 残留为零（唯一命中是恢复脚本里匹配错误签名的字符串，属预期）；其他 3.10+ API（removeprefix/match 等）扫描为零。本地复跑 **36/36 PASS**。非阻塞备注：静态门只覆盖已观测类别，残余风险由"登录节点+计算节点双合同测试"兜底，可接受。

**Q4 复制保留原件的恢复边界：成立。** 原 hidden stage 与 `job_failure.txt` 不动，复制到 `.tail_recovery.stage`，标记改为 prior-failure lineage 并记 recovery-lineage JSON；不谎称 158210 成功。

**Q5 恢复前门槛：充分。** sacct FAILED 态 + 精确失败阶段 + 精确 TypeError 签名 + census/pilot/verdict/边界数值与双 lineage 哈希先验证后复制 + 恢复后重验证要求 ranking `[I1, E3]`、pilot 集 `[E3, I1]`、FINAL/label/embedding 三零。足以防止恢复不完整或科学无效的阶段。

**Q6 先建小恢复包、执行仍需用户授权：接受。**

## 附带确认

恢复脚本不 sbatch、不解码 PCAP、不跑模型、不重开源数据、不碰 FINAL、不读 label。恢复只重跑修正后的 validator，科学结果（census/pilot/verdict）零重算。

## 授权边界

- 本 PASS 授权 Codex **构建 SHA 钉死的小型恢复包**并交付登录节点命令。
- 恢复执行仍需用户明确授权。
