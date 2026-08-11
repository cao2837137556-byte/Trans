# CKDA D0 正式结果 — Kimi 终审

- 日期：2026-08-12
- 对象：job 158210 尾段恢复拉回包（14,045 bytes）+ 报告 `ckda_d0_result_20260811.md`（commit `e6077b6`）
- 冻结合同：`ac4e2c2093811929e0fd20b65bb0c727ef3f872f6f7586b3049cf5758fc9c8b5`

## 总结论：D0 RESULT PASS —— D0 正式收官，授权起草 D1 FROZEN

## 独立复验记录（全部本地重算，非转述）

| 项 | 实测 | 结果 |
|---|---|---|
| 拉回包 SHA-256 / bytes | `6bb7c1ec…2ca1bb` / 14,045，与侧车一致 | PASS |
| 科学 `SHA256SUMS` | 独立解包重算 8/8 | PASS |
| `TAIL_RECOVERY_SHA256SUMS` | 独立重算 16/16 | PASS |
| verdict | `CKDA_D0_PRIMARY_AND_OPTIONAL_BACKUP_FROZEN`，primary=I1，backup=E3 | PASS |
| census | sessions 4,764,022（门 500,000）/ tokens 11,705,453（门 10,000,000），gate PASS；FINAL=0、labels=0 | PASS |
| candidate audit CSV | SHA `3522319b…e785a` 与报告一致；**4 行 × 50 列**（P0-A 裁定落实）；E1/E2 FAIL、E3/I1 PASS；I1 `KNOWN_DISJOINT` + 88.26% encodable | PASS |
| pilot 集合 | 恰好 {E3, I1} | PASS |
| FINAL 排除审计 | 两源原因码分离（`FINAL_DENYLIST` / `UPSTREAM_RAW51_UNOBSERVABLE_MASK`，P0-B 裁定落实）；合同哈希一致 | PASS |
| 恢复 lineage | `final_or_labels_reopened=false`、原失败 stage 路径与 FAILED 态保留、`POST_RESULT_VALIDATION_PACKAGING` 分类在案 | PASS |
| validation report | PASS | PASS |

## 科学判定

1. **判决机制正确**：I1 与 E3 是仅有的两个过硬门候选；I1 按预声明词典序第一键（`KNOWN_DISJOINT < NO_KNOWN_OVERLAP`）胜出，encodable 分数同向。无人工裁量痕迹。
2. **E1/E2 的淘汰是工程/许可淘汰**（checkpoint 不可得、无许可），报告已明确这不构成其表征科学劣性的证据——表述诚实，接受。
3. **I1 token 余量仅 1.17×**：报告未夸大，明确禁止在 D1 前宣称 scaling 行为。接受。
4. **D0 的能力声明边界正确**：这只是兼容性/选择结果，不宣称任何检测提升。论文级声明仍锁定到 D1 信息探针 + 后续冻结评估过门。

## 授权边界

- 本 PASS **关闭 D0**，授权 Codex **起草 D1 FROZEN**（三层探针：非参数几何 → 线性 → 小 MLP；I1 primary、E3 backup/对照；因果/无前瞻可执行合同；FINAL 零接触）。
- 不授权 D1 实现、训练、embedding 生成或 HPC 提交。
- job 158210 在 Slurm 层面永久记 FAILED；恢复产物独立标记 PASS，两者不得混写。
