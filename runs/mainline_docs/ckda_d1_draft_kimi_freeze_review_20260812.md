# CKDA D1 冻结协议草案 — Kimi 冻结审查

- 日期：2026-08-12
- 对象：`ckda_d1_frozen_representation_probe_draft_20260812.md`（`eaf59b7` + `f762650`，全文 553 行通读）
- D0 授权基线：`bfbeaf9`

## 总结论：DRAFT PASS —— 六问全部确认，授权生成正式 FROZEN 稿 + SHA 侧车

## 六问逐项裁定

**Q1 §4 修正：确认，且这是本次草案最重要的科学守备。** D0 的 11,705,453 token 是"全部 fit-prefix 可编码 token"（含 support_train 攻击前缀与 aux_process_fit），不能冒充良性训练语料。D1 开训前对 §4.1 窄化后的良性 allowlist 重跑 `sessions ≥ 500,000 AND tokens ≥ 10,000,000` 合取门；门失败不偷加攻击/模糊语料，I1 记 `CKDA_D1_PRIMARY_PRECONDITION_FAILED` 并按 §11 转 E3。这个"宁失败不偷料"的设计正是本项目的核心纪律。

**Q2 双排除：确认。** support_train 是攻击前缀，排除出自监督理所当然；aux_process_fit 来源语义模糊，不靠文件名或直觉重新归类，排除是保守正确的选择。legal fit attack 保留给 P1/P2 有监督探针合法（探针本来就需要标签，且只用 legal fit 角色）。

**Q3 I1 单一身份：确认。** 256 包因果前缀、128 宽/4 块/4 头、四字段 next-event 交叉熵等权平均、3 epoch 取最终步、132D = 128 隐态 + 4 路 NLL（由消费当前包**之前**的状态产出，因果成立）、无层/池化/前缀长度/子集搜索。全部钉死，无挑选空间。

**Q4 阈值规则与 §10.2 合取：确认。** 阈值只用 69 support_val + 3,000 aux + 4,000 ToN benign，frontier 为实测有限分 + 双哨兵，六级确定性 tie-break，report 前冻结；§10.2 九条合取（69/69、全局 ≥ C1−0.5pp、16 族 ≥ −2pp、future ≥ 84.83%/131,391、OOD macro ≤ 30.2722%、单池 ≤ FrozenCKBQ+2pp、单池 ≤ 90%、review=0、分母/因果/有限值/FINAL 门全过）与继承分母完全一致。

**Q5 E3 身份与推进：确认。** masked-mean final-layer + missing flag，无层/burst/pooling 搜索；I1 → E3 固定顺序，I1  actionable 即停，I1 工程/前置失败才开 E3，无第三候选、无模型购物。

**Q6 状态机优先级：确认。** 仅 P1/P2 完整合取 = `GO_D2`；G0 `STRONG_GEOMETRIC_SIGNAL` 与 `WEAK_ONLY` 都是非晋升诊断；状态 4 正确命名 `NO_ACTIONABLE_SIGNAL_UNDER_FROZEN_PROBES`，不夸大为 NO_INFORMATION。

## 额外核查（非六问范围）

- §3 数据角色表：label-blind 不使 select/report/FINAL 可训练，tokenizer/bucket/normalization/loss/checkpoint/probe/calibration 全部禁入——闭环。
- §8.2 G0：reference 池 legal fit benign only、200k 确定性 cap（SHA256(uid) 最小值）、query 自排除、承认其为"非参数"而非"零训练"——与此前裁定一致。
- §13 因果九门 + Python 3.9 双节点 compileall + 真实 forward/原子写/validator smoke + match/case 与 write_text(newline=) 静态回归——D0 两次故障的教训已制度化。
- §15 冻结后禁改清单完整，任何改动须新命名路线 + 新预注册。

## 非阻塞备注（不要求修改）

1. §5.2 四字段 bucket 定义可推出各字段词表大小（direction 2 / length 32 / protocol 256 / IAT 33），实现时按 bucket 定义机械生成即可，无需协议补写。
2. §4.2 良性 census 若落在 token 门边缘（D0 全量仅 1.17× 余量，窄化后更紧），失败转 E3 是协议内合法路径，执行时不必视为项目挫折。

## 授权边界

- 本 PASS 授权 Codex 生成 **D1 正式 FROZEN 稿 + SHA-256 侧车**。
- FROZEN 生成后我复核哈希与文本一致性（diff 应仅状态头变化）。
- 不授权 D1 实现、训练、embedding、HPC；FROZEN 之后仍需用户明确授权执行。
