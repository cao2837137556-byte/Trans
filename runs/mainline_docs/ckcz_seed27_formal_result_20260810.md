# CKCZ seed-27 正式结果：Endpoint-Pair Conflict Persistence Oracle（2026-08-10）

总体评估：**VALID SCIENTIFIC RESULT — `CKCZ_ORACLE_NO_INFORMATION` — 当前 CKCZ 路线封口**

这次任务没有训练或升级检测系统。它测试一个更窄的问题：冻结的 M7 低 OOD 起点上，使用
endpoint-pair 内 `C1=攻击、M7=正常` 冲突的四种因果 persistence scalar，是否存在任何
Oracle 全局 cut，能同时恢复攻击并保持 OOD 低误报。答案为否。

## 1. 工件身份与执行有效性

- Slurm job：`158078`，AMD，seed 27；状态 `COMPLETED`。
- bundle commit：`6ec2686f690ab29021f9b5225b8c8d469bbd9e42`。
- pullback：`issue27ckcz_endpoint_pair_conflict_diagnostic_seed27_amd_158078_pullback.tar.gz`。
- pullback bytes：46,996,641。
- pullback SHA-256：`ecc4f88ffc80a2d7fb9cc062234359a16eacc5d199e3fa9315cc18e0aa49cdb7`。
- tar：38 个安全成员；无绝对路径或 `..` 穿越。
- 结果根：28 个顶层文件，共 385,218,748 bytes；`SHA256SUMS` 26/26 独立重算通过；
  无 `.tmp` / `.dbk` / hidden atomic 残片。
- 正式 validator：`CKCZ_POST_RESULT_VALIDATION_PASS`；正式 verdict 标记
  `scientific_verdict_valid=true`、`bootstrap_complete=true`、`bootstrap_reps=200`。
- runtime：106 秒；最终 progress `stage=complete`、`sequence=111`、27 个科学输出。
- sstat 运行中证据：batch `MaxRSS=1,465,228K`、`AveCPU=00:01:22`、
  `MaxDiskRead=1,710,675,784`、`MaxDiskWrite=385,310,906`。集群终态 `sacct -X`
  未回填 MaxRSS/TotalCPU，因此资源结论只使用上述 sstat，不伪造缺失值。

## 2. 输入与数据质量

独立复核结果：**PASS，可用于本次预注册裁决。**

- 55 个 allowlisted source：Gotham 24 + auxiliary 31；cache schema、逐 source target-index
  唯一、timestamp finite 全通过。
- metadata 336,123 行，`(cache_kind, source_group, target_index)` 重复为 0；endpoint、PCAP
  member、timestamp 必需字段完整。
- pair-state 297,326 行，`(held_value, uid)` 重复为 0；五个 held-value 分母与冻结协议一致。
- 16 个 attack family；`review=True` 为 0；FINAL marker 为 0。
- Gotham lineage snapshot 287,448 行、键唯一；只读取
  `uid/source/role/m1_phase/recorded_index`，forbidden array 为 0。
- metadata join 的意外 miss 为 0。冻结协议预期的 ToN miss 为 20,000 行，逐 held-value
  各 4,000；这 20,000 行虽为 C1↔M7 conflict，但没有 endpoint state，按预注册全部保持 M7，
  没有偷偷补状态。
- event-position 顺序相对 timestamp 有 569 次逆序，分布在 8 个 PCAP member；timestamp
  无非有限值、event position 无重复。冻结实现按
  `interaction_key, timestamp, event_position, uid` 稳定排序构造因果状态，因此该审计现象不会
  造成未来信息进入当前行，但限制了把 recorded/event order 当作真实时间间隔的解释。

## 3. 预注册门与独立重算

每个 scalar 的 exact frontier 点必须同时满足：

- future attack recall `>=84.83%`；
- rows>=15 的 16 个 family 均相对 C1 不恶化超过 2pp；
- support-val `69/69`；
- 四池 OOD macro `<=30.27%`；
- review=0。

独立从四组 frontier、family 和 OOD pool CSV 重算：

- frontier 总点数 87,730；index 连续、cut 递减、首点为 `inf` no-veto；
- family 每点 16 行、OOD 每点 4 行；独立重算的 worst-family 与 OOD macro 逐点等于
  frontier 汇总列；
- 独立重算 `oracle_compatible` 与正式列逐点一致；四个 scalar 均为 0 个可行点；
- 更强的反证：四个 scalar 连 `future recall` 与 `OOD macro` 两门同时满足的点也都是 0，
  尚未加入 family 门就已经无解。

| scalar | frontier 点 | OOD 门内最高 future recall | 达 future 门时最低 OOD macro | 两门同时通过 |
|---|---:|---:|---:|---:|
| conflict count | 5,322 | 73.973% | 73.397% | 0 |
| consecutive conflicts | 3,576 | 66.205% | 93.092% | 0 |
| conflict fraction | 29,550 | 63.191% | 93.092% | 0 |
| conflict span seconds | 49,282 | 67.967% | 83.208% | 0 |

冻结 M7 no-veto 基线为 future recall 63.191%、OOD macro 0.153%。四种 scalar 的 frontier
最终都能把 future recall 推到最高 86.834%，但此时 OOD macro 已到 93.092%。这说明攻击冲突
与良性 OOD 冲突的 persistence 高度重叠：恢复攻击的同时会把大量 OOD 误报重新放回来。

OOD 门内“最高 future recall”点的 worst-family delta 分别为：count -27.480pp、
consecutive -55.400pp、fraction -95.305pp、span -45.849pp；family 门不是一个可忽略的小缺口。
这些只是完整 frontier 的审计极值，所有 cut 仍为 `FORBIDDEN_FOR_SELECTION`，不得转成方案参数。

机器可读复核摘要见 `ckcz_seed27_formal_frontier_audit_20260810.csv`。

## 4. Bootstrap 与不确定性边界

- 1,052,760 条 interval；每个 frontier 点固定 12 行；200 reps；cluster unit 仅为
  `source` / `pair`，没有记录级伪重复。
- CI 顺序与覆盖全部有效。靠近门的 pair-bootstrap 区间较宽，尤其 count 路线在达到 future
  门附近的 OOD interval 跨过 30.27%。因此本结果不能外推为“所有数据上 episode 信息论上
  永远不存在”。
- 预注册裁决基于当前冻结数据上的完整 exact frontier 点；bootstrap 用于报告不确定性，不能
  凭区间重写点估计门或事后创造一个 cut。当前数据与冻结协议下 0/87,730 可行点的结论成立。

## 5. 科学裁决与主线影响

正式 JSON、正式 validator 和独立重算三者一致：

```text
CKCZ_ORACLE_NO_INFORMATION
```

按 FROZEN 预注册，**当前 endpoint-pair conflict-persistence Episode Attack Veto 路线永久封口**：

- 不进入 D1-Legal；
- 不选择或实现任何本次 Oracle cut；
- 不增加 scalar、组合、k-of-n、family/source patch；
- 不跑 seed 37/47；不触碰 cooler-motor FINAL；
- 不把这次结果写成“所有 episode/session 方法均不可能”。

系统能力本身没有增强；本次增强的是结论确定性：一个看似便宜且合理的补救机制已经被完整
Oracle 上界否定，不应继续烧算力调参。下一步按预注册转向已登记的预训练 flow/session
representation 储备路线，重新做 Episode Design Review；新路线必须另起问题定义和预注册，
不能把本次 VIEWED frontier 数值带入选择。

## 6. 验证评级与待审边界

评级：**Ready to share for internal mainline decision**。

无阻塞性数据或计算问题。必须同时携带的 caveat：

1. 裁决只封口当前 interaction key、四 scalar、M7-OR-veto 形态和冻结数据覆盖；
2. 20,000 个预期 ToN metadata miss 无 episode state，这是冻结路线能力的一部分，也是未来新数据
   设计必须正面解决的覆盖缺口；
3. bootstrap 显示跨 source/pair 的不确定性较宽，禁止宣称普适的信息论不可能性；
4. Kimi 仍需对 pullback、聚合重算和封口措辞做独立终审后，主线才能把结果标为最终闭环。
