# Frontend-F1 D0 count-only 普查：实现与结果

- 日期：2026-09-02
- 执行基线：`c74be24`
- 分支：`codex/exp-mainline`
- FROZEN 协议：`frontend_f1_teacher_constrained_unified_encoder_d0_d1_frozen_20260901.md`
- FROZEN SHA-256：`98f2b73a051ee9c392631e85f4cc84d787306ed8333bfe2125f77870790c41b4`
- 用户授权：Frontend-F1 D0 普查；不含 D1 训练

## 1. 结论

D0 的守恒普查、候选机械选择和合成资源门均完成，但总终态为：

```text
F1_D0_IDENTITY_OR_SCOPE_FAILURE
reason=AUTHORIZED_COUNT_ONLY_TEACHER_BENIGN_VERDICT_NOT_MATERIALIZED
```

该终态不是候选模型失败，也不是训练结果失败。旧 CKDA/CKDE 链没有把“合法 fit 良性在旧 P2 下的 hard/normal 精确计数”持久化成 D0 获准读取的 count-only 工件；而 FROZEN 明令 D0 不得打开 score、probe state、representation、checkpoint 或 PCAP。执行器因此拒绝用 missing 钉分、零填充、近邻或重算模型来伪造教师覆盖，并没有授权 D1。

## 2. 实现与验证

新增：

1. `repo/ood/issue27frontend_f1_d0_census_v1.py`
2. `repo/ood/issue27frontend_f1_d0_census_contract_tests_v1.py`

Python 3.9 合同测试：

```text
20/20 PASS
PY39_COMPILE_PASS
```

测试钉死了 Python 3.9 兼容性、四条守恒式、整 context 排除、只读 `uid/missing`、禁止 score/FINAL、B 侧不得伪造 teacher、零真实训练与零超参搜索等边界。

结果目录：`runs/frontend_f1_d0_census_v1_20260901_local/`。目录内 12 个被列入 `SHA256SUMS` 的结果工件已逐项独立重算，12/12 一致。

## 3. 守恒与训练池普查

全部冻结等式精确复现：

```text
18,266 + 132 = 18,398
18,398 + 7,069 = 25,467
12,889 + 5,298 = 18,187
40 - 11 = 29
```

关键分母：

| 项目 | 结果 |
|---|---:|
| 全部 target | 25,467 |
| A / B | 13,827 / 11,640 |
| fit / select | 18,398 / 7,069 |
| 跨 phase context | 19 |
| 被整体排除的 fit / select 行 | 132 / 32 |
| 合法 fit | 18,266 行 / 12,889 contexts |
| select | 7,069 行 / 5,298 contexts |
| B 合法 fit 攻击 context | 29 |

19 个跨 phase context 均按完整 context 排除，没有拆行或通过较早 target 回收。

## 4. 教师覆盖

A 合法 fit：

| 项目 | 结果 |
|---|---:|
| 全部 | 11,529 行 / 7,682 contexts |
| old finite embedding 覆盖 | 11,529 行 / 7,682 contexts（100%） |
| 真攻击 | 4,182 行 / 4,150 contexts |
| 真攻击 old P2 hard | 4,182 行 / 4,150 contexts（100%） |
| 真良性 | 7,347 行 / 3,532 contexts |
| 真良性 hard / normal | `NOT_MATERIALIZED_IN_AUTHORIZED_COUNT_ONLY_ARTIFACTS` |

旧 cap 工件足以证明合法 fit 攻击锚点全部为 hard；但不存在获准的 count-only 工件可把合法 fit 良性精确拆成 hard 与 normal。该缺口直接阻塞 §3.3，不允许用 D1 或真实性能数据绕过。

## 5. 候选与资源普查

固定兼容性清单只比较冻结字段，不读取真实表示或结果：

| 候选 | 参数量 | 机械资格 | 选择 |
|---|---:|---|---|
| `torch.nn.GRU` | 292,352 | PASS | YES |
| `torch.nn.LSTM` | 313,088 | PASS | NO |
| `torch.nn.TransformerEncoder` | 499,328 | PASS | NO |

按“维护上游 → 参数量小 → 字典序”的冻结次序，机械选择 `torch.nn.GRU`。这只是 D0 身份选择，不是性能胜出。

合成形状资源试跑：

| 项目 | 结果 |
|---|---:|
| synthetic median step | 3.394 s |
| synthetic extrapolation | 136,793 s |
| 机械 wall-time cap | 113.994 h |
| 绝对上限 | 168 h |
| resource gate | PASS |
| 真实训练次数 | 0 |
| 超参 sweep | 0 |

## 6. 边界证明

执行期计数全部为零：

```text
real_representation_opened=0
score_opened=0
probe_state_opened=0
checkpoint_opened=0
pcap_opened=0
viewed_opened=0
report_opened=0
final_opened=0
training_started=0
```

因此本轮没有生成模型能力结论，也没有改变 A 旧路径或 B 新路径的任何检测能力。

## 7. 唯一合法下一步

若继续 Frontend-F1，需先另立一个很窄的 **teacher-benign count-only materialization** 协议：只对冻结 old P2 和合法 fit 良性分母生成 hard/normal 聚合计数，钉死输入身份、行级 join、阈值语义和零 select/viewed/report/FINAL 接触。该动作需要新的明确授权；完成并审查后才能形成 numerical addendum，D1 训练仍需再次授权。

禁止把本次 scope failure 改写成候选失败，或直接跳到训练“看看效果”。
