# CKDA D0 提交前 P0 裁定 — Kimi

- 日期：2026-08-11
- 审查对象：commit `90e699c`，实现 `repo/ood/issue27ckda_d0_representation_compatibility_audit_v1.py`，报告 `ckda_d0_authorized_implementation_and_local_gate_20260811.md`
- 约束协议：`ckda_d0_representation_compatibility_audit_preregistered_20260811.md`，SHA-256 `ac4e2c2093811929e0fd20b65bb0c727ef3f872f6f7586b3049cf5758fc9c8b5`

## 总结论：PASS（两项歧义均裁定关闭，授权 Codex 构建正式 D0 bundle）

## P0-A：47 列 vs 50 列

**裁定：50 个逐项枚举字段为规范，"47"为散文计数笔误。无需重新冻结。**

独立验证：从 FROZEN §4 代码块机械提取字段名，逐行计数为 **50**（含末尾 `evidence_manifest_path`）；实现 `AUDIT_FIELDS` 与之**逐名逐序完全一致**；合同测试 `test_02_literal_schema_has_fifty_fields` 钉死该字面 schema。

理由：FROZEN 的可执行内容是逐项枚举清单（"字段顺序固定如下，不得增删"），散文中的"47"不具备可执行性；实现的忠实对象是枚举清单，选择正确。注：Kimi 自己的终审文档（`efe705d`）同样沿用了"47 列"表述，属于同一笔误的传播，一并更正。

记录要求：本裁定文档即 erratum；后续 D0 verdict 与 D1 引用该表时以 50 字段枚举为准。

## P0-B：`hydraulic-system-1` 分母边界

**裁定：接受现行 allowlist 方案（选项 a）。该 source 统一记为 `UPSTREAM_RAW51_UNOBSERVABLE_MASK` 缺失/不可观测态，census 不打开。拒绝选项 b（重建 raw lineage）。**

理由：

1. **它从未属于任何基线的 fit universe**。上游 `raw51_observable_v1` 的 1,353 行不可观测 mask 导致该 source 没有任何 target 产出，C1/M7/CKBW 全部基线均未见过它。census 若包含它，会引入基线不可比的数据，破坏对称性。
2. **没有 lineage 就没有合法 cutoff**。该 source 无 CKBU causal lineage cache，fit 边界无法定义。在没有 cutoff 的情况下把它纳入"fit-only"语料，正是本项目最禁止的边界模糊型泄漏。排除是唯一合法干净的选择。
3. **选项 b 成本无科学回报**。重建 raw-session lineage 需另冻合同、重解码 PCAP，耗时数周；即便建成，该 source 对 D0 的目的（I1 数据门 + fit encodable 分数）只贡献一个基线不可比的孤岛。

附带条件（必须落实）：

1. 该 source 的状态**永远以独立原因码记录**，不得与 `FINAL_DENYLIST` 合并或静默等同。实现已满足：`EXPECTED_NONALLOWLIST_FIT_SOURCES` 两项原因码分离，`test_22_expected_nonallowlist_sources_are_exact` 断言精确排除集合。
2. I1 的 `sessions/tokens` 数据门分母即排除该 source 后的合法 fit universe，门槛数值不变（先冻结后测量原则已覆盖分母缩小的情况）。
3. D1 FROZEN 起草时必须继承同一排除，适用于 tokenizer 拟合与编码器预训练语料。
4. 未来若任何工作想启用该 source，须先另冻 raw-session lineage 合同；CKDA 全线不处理。

## 实现审查（独立复验）

- 本地复跑合同测试：**25/25 PASS**（`Ran 25 tests ... OK`，0.085s）。
- FINAL 防护：`fail_if_final` 在任何 raw open 前执行，markers 覆盖 cooler-motor 及 seed 37/47 全部写法变体；`test_05/test_06` 钉死 fail-closed。
- allowlist-before-open 顺序由 `test_18` 钉死；allowlist schema 漂移与空 allowlist 均拒绝。
- 工程定性正确：E1 残片不作身份 hash（`test_13`）；E2 无许可硬淘汰（`test_12`）；`POSSIBLE_OVERLAP` 硬失败（`test_14`）；I1 双门合取（`test_15`）；缺 pilot 阻断 PASS（`test_16`）。
- 原子写与空数值语义正确（`test_17`、`test_21`：空 ≠ 0）。
- cutoff 彩排分母：27 prefixes / 25 sources、`final_files_opened=0`、七项输入哈希钉死，与报告一致。

## 授权边界

- 本 PASS 授权 Codex **构建正式 D0 bundle 并交付 HPC census/pilot 命令**。
- HPC 提交仍需用户明确授权。
- 不授权 D1 起草以外的任何后续步骤；E1 权重若再次尝试下载，仅限官方 Google Drive 发布物。
