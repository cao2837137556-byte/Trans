# CKCZ attack-family 口径澄清（2026-08-09）

状态：**ACCEPTED CLARIFICATION**。本文件回答 Kimi 对 CKCZ DRAFT 的唯一待澄清项，并作为后续 FROZEN 稿的约束性输入。

## 1. 结论

CKBW 中的“12 个 attack family 等权”与 CKCZ DRAFT 中的“16 个 attack family 全表”属于两个不同阶段、两个不同用途的集合，**不做映射，也不共享分母**：

- **12 族**只属于 CKBW 的合法 fit/training 权重设计：10 个 Gotham `support_train` family，加 2 个 ToN `aux_process` mechanism family。它只决定训练损失如何等权，不是结果报告 taxonomy。
- **16 族**属于冻结 `GLOBAL_ATTACK_PRESERVATION` 报告池的经验 attack-family taxonomy。CKCZ 不训练模型，因此只沿用这 16 族报告口径。

禁止把 12 个训练 strata 合并、投影或重命名成 16 个报告 family；也禁止把 16 个报告 family 反向用于解释训练权重。

## 2. CKCZ 的冻结报告分母

攻击保持的全局分母固定为 CKBW 记录预测表中：

```text
held_value == GLOBAL_ATTACK_PRESERVATION
AND label_metric_only == 1
```

共 `244,050` 行，按 role 组成：

| role | rows |
|---|---:|
| support_val | 69 |
| same_file_query | 2,486 |
| future_query | 131,391 |
| sealed_final_attack | 110,104 |

16 个报告 family 及其全角色合并行数如下；本次实际均满足 `rows >= 15`：

| attack_family | rows |
|---|---:|
| C&C Communication | 179 |
| CoAP Amplification | 320 |
| File Download | 2,569 |
| Ingress Tool Transfer | 10,069 |
| Merlin C&C Communication | 9,926 |
| Merlin ICMP Flooding | 19,730 |
| Merlin TCP Flooding | 27,722 |
| Merlin UDP Flooding | 10,298 |
| Mirai C&C Communication | 369 |
| Mirai GRE Flooding | 27,722 |
| Mirai TCP Flooding | 27,721 |
| Mirai UDP Flooding | 27,722 |
| Reporting | 167 |
| TCP Scan | 39,711 |
| Telnet Brute Force | 39,712 |
| UDP Scan | 113 |

## 3. family 门的精确定义

“主要 family 相对 C1 不恶化超过 2 pp”精确定义为：

1. 在上述 `244,050` 行全局攻击保持池中，按 `attack_family` 分组；
2. 对每个总行数 `rows >= 15` 的 unique family，分别计算 CKCZ hard recall 与同一批行上的 C1 hard recall；
3. 对每一族要求 `CKCZ recall - C1 recall >= -2.0 pp`；
4. 任一符合 `rows >= 15` 的族失败即 family gate 失败，不允许事后删族或只报宏平均；
5. `support_val == 69/69` 仍是独立硬门；它不被 family gate 取代；
6. future-only `84.83%` 是另一条兼容参考/门槛，分母固定为 `future_query` 的 `131,391` 行，禁止与全角色 family 分母混写。

## 4. 代码与工件依据

- CKBW FROZEN §5.2 将 12 族明确限定为 attack-side 训练权重。
- `repo/ood/issue27ckbw_tail_margin_dual_control_v1.py` 冻结 `ATTACK_FAMILY_MIN_ROWS = 15` 与 `ATTACK_FAMILY_DROP_GATE_PP = 2.0`，并对 attack-preservation summary 中全部达标 family 取最差 delta。
- `repo/ood/issue27ckbj_tgn_m1_strict_formal_v2.py::attack_summary_rows` 在攻击保持 records 上逐 unique `attack_family` 生成 recall；不读取 12 族训练 strata。
- 本地冻结 CKBW 预测工件实测得到上述 `244,050` 行、四 role 与 16 族计数。

## 5. 对 CKCZ FROZEN 的约束

后续 FROZEN 稿必须吸收本文件第 1—3 节，不再保留“16 映射到 12”的开口项。CKCZ 的任何实现、诊断报告和 go/no-go 解释都必须同时标注：

- 16 族 family 表使用全角色 `GLOBAL_ATTACK_PRESERVATION` 分母；
- future-only recall 使用 `future_query` 分母；
- 12 族只作为 CKBW 训练历史，不参与 CKCZ 计算。
