# CKDA D0 Python-3.9 修复 — Kimi 审查

- 日期：2026-08-11
- 对象：commit `536b71f`，修复脚本 `repo/ood/issue27ckda_netfound_py39_compat_v1.py`，报告 `ckda_d0_py39_repair_ready_for_kimi_review_20260811.md`
- 前置：job `158187` census 段已合法完成（I1 gate PASS），失败段为 resource pilot 导入期 `SyntaxError`

## 总结论：PASS（四个问题逐项裁定如下）

## Q1：match/case → if/elif 等价改写是否成立？——成立

独立核对 `OLD_BLOCK`/`NEW_BLOCK` 全文：

- 三个 case 均为**字面字符串模式**（`"regression"` / `"single_label_classification"` / `"multi_label_classification"`），match/case 的字面模式语义就是 `==` 比较；无捕获模式、无守卫、无序列解构，改写为 `if/elif` 无语义差。
- `case _: raise ValueError` 与 `else: raise ValueError` 一致。
- 改写只动了损失函数选择分支，模型结构、权重、前向逻辑零改动；checkpoint 身份不变（698,780,900 bytes / `e6237f49…f5105`）。
- 冻结科学合同不涉及 vendor 源码语法形式，改写不触及合同。

## Q2：17 文件 Python-3.9 门是否闭环？——对观测到的失败类别闭环

- 三重 fail-closed：上游文件 SHA 精确钉死（漂移即拒绝）+ 目标块字面唯一（`count != 1` 即拒绝）+ `replacement_count=1`。
- `ast.parse(feature_version=(3,9))` 对全部 vendor `.py` 做 3.9 文法解析，能捕获 match/case 及所有其他 3.10+ 语法特性；登录节点提交前再用冻结解释器实际编译一次，把这类失败从机时内挪到提交前。
- **非阻塞备注**：文法门关闭的是"语法类"不兼容；运行时级别的不兼容（如模块顶层执行 3.10+ 才有的表达式/标准库调用）编译期查不出。若 resource pilot 再次以 import/runtime 错误失败，仍按工程失败分类处理，不构成科学结论。接受此残余风险。

## Q3：复用 27 个 census checkpoint 是否成立？——成立

- census 段在导入失败**之前**已完整合法完成：`raw label columns read=0`、`FINAL files opened=0`，两个 manifest SHA 钉死（`9184cd01…89689`、`6e303e9f…a7c9f`）。
- census 逻辑与 netFound 代码零依赖，修复不改变 census 的任何输入、cutoff 或分母。
- 附带条件已满足：r2 必须重建并重新校验 census summary，不按名字跳过任何科学阶段。

## Q4：小型 repair overlay 替代 665 MB 重传是否接受？——接受

- overlay 由与已验 r1 的内容比对生成、拒绝删除操作，并在隔离目录"r1 副本 + overlay"上全量重算 r2 `SHA256SUMS` 验证——等价于重传 r2 全包的内容保证，传输量大幅降低。
- r1 远端目录与 job 158187 保留为失败证据，不清理。

## 独立复验

- 本地复跑合同测试：**33/33 PASS**（`Ran 33 tests ... OK`）。

## 授权边界

- 本 PASS 授权 Codex **构建完整验证 r2 + 小型 repair overlay**，并交付 HPC 命令。
- HPC 重新提交仍需用户明确授权。
