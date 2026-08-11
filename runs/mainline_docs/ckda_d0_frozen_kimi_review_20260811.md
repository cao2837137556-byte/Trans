# CKDA D0 FROZEN 协议 — Kimi 终审

- 日期：2026-08-11
- 审查对象：`runs/mainline_docs/ckda_d0_representation_compatibility_audit_preregistered_20260811.md`
- 对象 commit：`0aac071`
- 正文 SHA-256（独立复算）：`ac4e2c2093811929e0fd20b65bb0c727ef3f872f6f7586b3049cf5758fc9c8b5`，与 `.sha256` 侧车一致
- 审查方式：全文通读（390 行），逐条对照 Kimi 草案审查（`27c391b`）的七项裁定

## 终审结论：PASS

## 一、七项裁定落实核对

| # | 裁定 | FROZEN 落实位置 | 结果 |
|---|------|----------------|------|
| 1 | 固定审计表模板，平局必须引证据 | §4，47 列模板含 `evidence_manifest_path` | PASS |
| 2 | `GO_D2` 别名消除 | §13：`GO_D2 == CKDA_D1_ACTIONABLE_PROBE_SIGNAL` | PASS |
| 3 | attack-family 唯一字典引用 | 首部引用 `ckcz_attack_family_scope_clarification_20260809.md`（commit `97adfe0`），16 族/244,050/rows≥15/−2pp/support 69/69/future 131,391 | PASS |
| 4 | I1 先验门在测量前冻结 | §6.2：`sessions ≥ 500,000 AND tokens ≥ 10,000,000`，先冻结后测量，顺序正确 | PASS |
| 5 | 域内候选不自动越级 | §11：I1 与外部候选同一硬门、同一词典序，无优先级倾斜 | PASS |
| 6 | 资源 pilot 口径固定 | §9：前 100 个非空 session + 100,000 raw packet 上限，中位吞吐 | PASS |
| 7 | FINAL 排除 fail-closed | §3/§10：命中即 `CKDA_D0_ENGINEERING_FAILURE_FINAL_EXCLUSION`，无候选排序、无科学结论 | PASS |

## 二、超出裁定要求的加严（接受）

- `POSSIBLE_OVERLAP` 从候选选择中**直接硬淘汰**（§5），只可记录为污染敏感性对照，D0 不 forward。这避免了"先排序后判资格"的循环定义，比草案更严格。接受。
- 候选身份歧义（`AMBIGUOUS_IDENTITY`）直接淘汰、不试多个 checkpoint（§2），防止 checkpoint 挑选。

## 三、机制审查

- 词典序完全机械化：`ranking_tuple` 九键固定（§11），浮点 1e-6 容差、成本 10% 平局规则，无人工裁量空间。
- 授权链正确：本 PASS 仅解除技术审查门；D0 执行仍需用户明确授权（§14）。D0 verdict 为 `PRIMARY_FROZEN` 时也只授权起草 D1 FROZEN，不自动授权训练、不自动授权导师损失函数（§1、§13）。
- D0 全程不生成性能 embedding、不解码 FINAL 数据（cooler-motor、seed 37/47）、不烧训练算力，与"先选编码器再谈方法"的路线定位一致。

## 四、非阻塞备注（不要求修改）

1. §9 资源 pilot 的吞吐测量依赖候选官方推理代码的可获得性；若某候选官方代码无法在其声明的许可下获取，应按 §2 身份审计的同一证据标准处理，不要现场写替代实现。
2. I1 census 只统计 fit 良性数据，执行时建议在审计输出中同时记录 census 所用的精确 split manifest 哈希，便于 D1 复查。

## 五、授权边界声明

- 本审查 **PASS 仅表示 FROZEN 文本技术合格**。
- **不授权** D0 执行；D0 执行需用户明确授权。
- **不授权** 下载任何模型权重以外的动作；若 D0 执行中需要下载官方权重，范围以各候选官方发布物为限。
- **不授权** 起草 D1 以外的任何实现、训练、HPC 提交。
