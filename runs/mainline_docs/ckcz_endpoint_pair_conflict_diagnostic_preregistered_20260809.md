# CKCZ：Endpoint-Pair Conflict Persistence 只读诊断预注册（FROZEN）

> 状态：**FROZEN — IMPLEMENTATION AUTHORIZED — HPC SUBMISSION NOT AUTHORIZED**
>
> 日期：2026-08-09。Codex 负责起草、实现、测试与后续打包；Kimi 是本轮独立方案审查者；
> 用户负责 HPC 提交授权。用户明确不把 GPT 纳入本轮审查/签字链；GPT 仅在用户需要时
> 帮助其理解方案。未经新的用户授权，不得提交 HPC 作业。

## 1. 唯一研究问题

CKCZ 只回答：

> 在冻结 CKBW seed-27 记录决策上，`C1_hard=1` 且 `M7_hard=0` 的冲突记录，是否在
> source-local、PCAP-member-local 的匿名 endpoint pair 内表现出可用于后续合法选择的
> causal persistence；或者这种 persistence 在 VIEWED 良性 OOD 中同样存在，使
> Episode Attack Veto 在 oracle 层即不可行？

本轮不回答正式系统是否 GO，不选择系统阈值，不训练模型，也不证明 episode 路线最终
有效。

## 2. 已冻结的历史边界

- CKBY 已封口“冻结 51D 上继续更换记录级学习器”；不声称所有记录级表示不可能。
- CKBQ 已做 source-local 32-event raw9 MiniRocket；不得把固定事件窗换名重跑。
- CKAW/CKAY 已做 generic 60-second episode pooling；它把 385 个 packet support 压缩为
  约 42 个 positive episodes，stream OOD 仍高且 combined attack 明显下降。不得重启
  generic episode classifier/pooling。
- 本轮只诊断未来可能的非对称仲裁：

```text
hard_t = M7_hard_t OR V_episode_t
```

- `V_episode_t` 只允许救回当前 `C1_hard=1, M7_hard=0` 的 conflict 记录；不允许在
  C1 当前不 hard 时凭 episode 状态新增告警，不允许 retroactive backfill。

## 3. 数据等级与用途

### 3.1 LEGAL

- `support_val` 69 attack；
- frozen auxiliary select 3,000 benign；
- ToN-IoT `normal_2` 4,000 benign。

CKCZ 本轮不使用这些数据选择任何参数。它们只可用于输出 coverage/cardinality，为后续
独立 D1-Legal 设计准备事实。

### 3.2 VIEWED DIAGNOSTIC

- GLOBAL attack report：future_query、same_file_query、sealed_final_attack；
- 四个已看良性 OOD：hydraulic-system、ip-camera-street、predictive-maintenance、
  stream-consumer。

VIEWED 标签只在 label-free causal state 全部构造完成后接入指标层。VIEWED 可以否决
预声明机制，不能选择 score、cut、window、gap、key、feature subset 或系统复杂度。

### 3.3 FINAL

- cooler-motor 全部 source；
- seed 37/47 的所有工件。

二者不得进入参数、manifest、allowlist、缓存打开、导出、统计、日志或异常信息。

## 4. 冻结输入

### 4.1 CKBV 154917 Gotham cache

根目录：

```text
/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline/runs/issue27ckbv_checkpointed_process_formal_v1_2026-07-25_seed27_amd_154917
```

输入：

- `ckbu_gotham_unified_causal_manifest.csv`；
- `gotham_causal_cache/<source_cache_key>.npz`。

CKBW run_spec 钉住的 manifest SHA-256：

```text
aaef2a0c0e4cc28d3815dbff4152db2fbe8c7d953dc35cf05cd817c4135d4c22
```

用户 2026-08-09 登录节点只读检查已确认目录存在、可列出 NPZ/JSON，目录约 18 MiB。
这只是 `ONLINE_PRESENCE_PASS`，不是完整性证明；正式任务必须逐 manifest 行复验 cache
SHA-256 和 schema。

排除 FINAL 后的可读合同：24 个 cache source、317,523 target rows。原 source plan 的
`iotsim-hydraulic-system-1` 1,353 行由冻结 raw51 mask 排除，未进入 unified manifest；
这是已知缺口，不得重建或插值。

### 4.2 CKBV 154917 auxiliary cache

同一根目录下：

- `ckbu_auxiliary_unified_causal_manifest.csv`；
- `auxiliary_causal_cache/<source_cache_key>.npz`。

CKBW run_spec 钉住的 manifest SHA-256：

```text
f2a674235cb929ed4b7ebb8723c53a4f314f4e4563e727e3f4a2e0a4ab201e43
```

合同：31 个 source、18,600 rows，其中 aux_fit 6,600、aux_select 3,000、aux_report
9,000。predictive-maintenance 的 9,000 条 VIEWED OOD 位于该 cache；因此 CKCZ 不能只读
Gotham cache。

当前尚无 auxiliary cache 登录节点在线存在性的独立截图证据；这不是科学缺失，但构成
**HPC launch blocker**。实现必须提供与 Gotham 相同的只读存在性、manifest SHA、逐文件
hash/schema 检查；任一失败即 CKCZ 中止并报告，不重解码、不静默降为三池。

### 4.3 CKBW 157624 冻结预测

输入：

```text
runs/issue27ckbw_tail_margin_dual_control_v1_2026-08-03_seed27_amd_157624/ckbw_record_predictions.csv.gz
```

本地 pullback 已复验：

- bytes：6,341,170；
- SHA-256：`d1e905924e74bf390aaaae79ee68f10312dc0bc1cdebff88848d4d3ee64adf85`；
- rows：297,326；
- columns：30；
- 每个 `held_value` 内 UID 唯一。

协议切片行数：

| held_value | rows |
|---|---:|
| GLOBAL_ATTACK_PRESERVATION | 251,050 |
| iotsim-hydraulic-system | 10,069 |
| iotsim-ip-camera-street | 10,069 |
| iotsim-predictive-maintenance | 16,069 |
| iotsim-stream-consumer | 10,069 |

禁止把五个协议切片拼成一条序列。每个协议内独立 join、独立构造 state、独立断言 UID
唯一；同一 UID 跨协议重复是冻结协议事实，不得去重后混算。

## 5. Cache schema 与 UID 重建

### 5.1 Gotham NPZ 精确字段

```text
recorded_index
feature_available_time_epoch
target_event_position_within_capture
src_local_id
dst_local_id
causal_features
feature_names
raw_source_path
```

### 5.2 Auxiliary NPZ 精确字段

```text
target_row
feature_available_time_epoch
target_event_position_within_capture
src_local_id
dst_local_id
causal_features
feature_names
raw_source_path
```

Auxiliary UID 必须逐行按冻结函数复现：

```text
uid = "aux:{role}:{source_group}:{target_row}"
```

并与 CKBW 协议内 UID exact join。Gotham UID/target 映射必须复用冻结 target 输入与现有
Record 构造合同，不得从 outcome 表模糊匹配。

## 6. FINAL 正向 allowlist

实现必须生成两个显式 allowlist CSV：Gotham 24 source、auxiliary 31 source，并分别生成
SHA-256 侧车；bundle 构建前必须由独立审查确认。Exporter 的执行顺序固定为：

1. 读取 allowlist 与 manifest 元数据；
2. 断言 allowlist SHA；
3. 断言 allowlist 与冻结 FINAL source set 交集为空；
4. 断言 manifest 不缺、不多、source_cache_key/hash 完全一致；
5. 仅随后打开 allowlist 指向的 NPZ。

禁止用 `not contains cooler-motor` 代替正向 allowlist。日志不得打印 FINAL manifest 行或
路径。任何 seed 37/47 路径出现即合同失败。

## 7. Interaction key 与可恢复边界

Member-level builder 每个 PCAP member fresh reset，因此 local endpoint id 只在 member
内有效。唯一有向 key：

```text
(cache_kind, source_group, raw_source_path, src_local_id, dst_local_id)
```

并列报告无向 key，但当前事件方向必须保留。`source_group/raw_source_path` 只作状态隔离，
不得成为统计规则或未来模型特征。

从 51D 可恢复当前 TCP/UDP/ICMP 指示、粗 port class 与 well-known 标志；不能恢复 exact
port、stream id 或 5-tuple。本轮不声称 service-level episode。

Cache 只保存冻结 target 行的元数据。全量 raw packets 虽参与了 51D past state，却没有
逐事件保存在 cache；因此 CKCZ 研究的是 **target-conflict persistence**，不是完整 packet
session 重建。

## 8. 标签无关的 causal state 构造

对每个 `held_value`、每个 interaction key：

1. 按 `(feature_available_time_epoch, target_event_position_within_capture, uid)` 稳定排序；
2. 非有限 timestamp 记录标为 missing-state，不进入 pair state；
3. 对当前记录先读取冻结 `c1_hard` 与 `hard__M7-TabM-TailMargin-DualControl`；
4. 定义 `conflict_t = (c1_hard_t == 1 and m7_hard_t == 0)`；
5. 计算 current-inclusive causal summaries；
6. 随后更新该 pair 的状态；
7. 全过程不读取 `label_metric_only`、role、attack_family、device_family 决定 state。

无法 join metadata 的记录固定 `V_episode=0`，保留 `hard=M7_hard`；不得插值、回填或
重解码。必须逐 pool 报告 metadata coverage。hydraulic 的冻结 raw51 masked 缺口不得隐藏。

## 9. 预声明的唯一 Oracle 统计量

只允许以下四个 current-inclusive、pair-causal scalar：

1. `pair_conflict_count_so_far`；
2. `pair_consecutive_conflicts_so_far`：在该 pair 自身的 target 序列上连续，不以
   source-global 相邻为准；
3. `pair_conflict_fraction_so_far = conflict_count / pair_target_count`；
4. `pair_conflict_span_seconds_so_far`：第一条至当前 conflict 的真实时间跨度；只有当前
   conflict 且已有至少两条 conflict 时为正，否则为 0。

描述性但不进入规则选择的固定审计量：

- pair/source target 数；
- directed/unordered unique pair 数；
- singleton pair 比例；
- conflict delta-time median/MAD 与原始 ECDF；
- conflict 在 pair 间的 concentration/Gini；
- nonfinite timestamp、missing metadata、collision、duplicate UID 数；
- 每 source/member 的时间跨度与 timestamp monotonicity。

不允许新增统计量、组合统计量、learned classifier、手画区域、window W、inactivity gap、
k-of-n、family/source cut 或 VIEWED 后派生特征。

## 10. Oracle frontier：只用于判死

对第 9 节四个 scalar 分别、独立构造完整 exact cut frontier。候选 veto 必须同时满足：

```text
V_t = current_conflict_t AND (scalar_t >= global_cut)
hard_t = M7_hard_t OR V_t
```

每个 scalar 只用一个全局 cut；不组合、不择优晋升。Cut 由 VIEWED 值枚举只为计算 oracle
能力上界，任何数值均明确标记 `FORBIDDEN_FOR_SELECTION`。

每个 frontier 点必须报告：

- online record-level overall/future/same-file/sealed attack recall；
- 16 attack family 全表、相对 C1 差值、worst family；family 表固定使用下述
  `GLOBAL_ATTACK_PRESERVATION` 全角色攻击分母；
- 四池完整 record-level OOD hard rate 与 family macro；
- metadata-missing 行保持 M7 后的计数；
- rescued rows、首次触发前 misses、time-to-first-veto；
- source/pair bootstrap 区间；记录行不作独立重复。

攻击与 family 分母冻结如下：

- 全局攻击保持池固定为
  `held_value == GLOBAL_ATTACK_PRESERVATION AND label_metric_only == 1`，共 244,050 行：
  `support_val=69`、`same_file_query=2,486`、`future_query=131,391`、
  `sealed_final_attack=110,104`；
- 该全局池实有 16 个 unique attack family；12 个 CKBW fit/training 等权 strata 只属于
  历史训练损失，CKCZ 不训练且不做 12→16 映射；
- “主要 family”是上述 244,050 行中每个总 `rows >= 15` 的 unique family。本冻结池 16 族
  均满足；每一族必须满足 `CKCZ recall - C1 recall >= -2.0 pp`，禁止事后删族；
- future-only recall 的分母另固定为 `future_query` 131,391 行，不得与全角色 family 分母
  混写；
- `support_val=69/69` 是独立硬门，即使 69 行也进入全局 family 分组，仍不得用 family 门
  替代 support 门。

最低兼容能力参照仅用于 oracle 判死：

- future recall `>=84.83%`；
- 上述 rows>=15 的 16 个报告 family 均相对 C1 不恶化超过 2pp；
- support_val 69/69；
- 四池 OOD macro `<=30.27%`；
- review=0。

如果四个预声明 scalar 的完整 oracle frontier **全部**不存在同时满足上述条件的点，则裁决：

```text
CKCZ_ORACLE_NO_INFORMATION
```

当前 endpoint-pair conflict-persistence 路线封口，转已登记的预训练 flow/session
representation 储备路线。

若至少一个 scalar 存在 oracle 可行点，只能裁决：

```text
CKCZ_ORACLE_INFORMATION_EXISTS_LEGAL_NOT_TESTED
```

这只授权另起 D1-Legal 预注册。不得使用 oracle scalar 排名、cut 或最好图选择系统方案，
不得写 Episode Attack Veto 正式实现。

## 11. 一次任务的阶段与失败语义

同一只读结果任务依次执行：

1. `validate_inputs`：路径、manifest SHA、allowlist SHA、FINAL 零交集、cache file hashes；
2. `validate_schema`：Gotham/auxiliary NPZ 字段、shape、有限性、行数；
3. `export_metadata`：原子写 metadata CSV.GZ；
4. `pair_cardinality`：在 outcome join 前完成并固化；
5. `join_predictions`：逐 held slice exact UID join；
6. `build_causal_state`：不读标签；
7. `attach_metric_labels`：state 完成后才接指标字段；
8. `oracle_frontiers`：四个固定 scalar 全量输出；
9. `validate_outputs`：CSV readback、SHA-256、required-row/schema 断言；
10. `CKCZ_DIAGNOSTIC_COMPLETE`。

任一阶段失败返回非零，写 `job_failure.txt`，不得输出科学裁决。缓存缺失、hash/schema
漂移、FINAL 命中、UID collision、跨协议混行、required metric 缺失均为工程/合同失败，
不是 episode 不可行证据。

## 12. 必须输出

- `ckcz_input_audit.json`；
- `ckcz_source_allowlist_audit.csv`；
- `ckcz_target_metadata.csv.gz`；
- `ckcz_pair_cardinality_by_source.csv`；
- `ckcz_pair_cardinality_distribution.csv`；
- `ckcz_prediction_join_audit.csv`；
- `ckcz_pair_state_rows.csv.gz`；
- `ckcz_oracle_frontier_<scalar>.csv` × 4；
- `ckcz_attack_family_metrics_<scalar>.csv` × 4；
- `ckcz_ood_pool_metrics_<scalar>.csv` × 4；
- `ckcz_bootstrap_intervals.csv`；
- `ckcz_verdict.json`；
- `run_spec.json`；
- `SHA256SUMS`；
- pullback archive、archive `.sha256`、resource usage、Slurm identity/log。

CSV 写出必须使用全行 deterministic union schema、原子 finalization 与 readback；不同
role/group 的空字段合法但不得丢列。

## 13. 资源与运行纪律

- 只读已有 NPZ/CSV.GZ，不解码 PCAP、不训练、不调用 GPU；
- CPU/内存/时限在实现后用本地真实工件 microbenchmark 与 154917/157624 实际资源证据
  估算，不沿用最大配置；
- 正式提交时只允许一个结果 producing job，启动检查与诊断同链；
- 不提交独立环境-only/preflight-only 作业；
- 正式 job 必须输出阶段进度、终态、MaxRSS/TotalCPU/Elapsed，并打 pullback 包。

## 14. 本轮明确不做

- 不训练模型；
- 不选择阈值、window、gap、key 或 feature；
- 不写 family/source patch；
- 不做 generic episode pooling/classifier；
- 不做 TGN/Transformer；
- 不读取 cooler-motor 或 seed 37/47；
- 不重解码 PCAP；
- 不把 source-order L0 结果当 interaction 路线死刑门；
- 不把 oracle 可行点晋升为系统参数。

## 15. 审查闭环与授权边界

- Kimi 独立审查文档：
  `runs/mainline_docs/ckcz_prereg_kimi_review_20260809.md`（commit `a51fcb2`）；
- 审查结论：**PASS**。DRAFT §15 的六个问题全部接受，不要求删除统计量；
- 唯一澄清项“12 个训练 strata vs 16 个报告 family”已由
  `runs/mainline_docs/ckcz_attack_family_scope_clarification_20260809.md`（commit
  `97adfe0`）闭环，并已吸收进本 FROZEN §10；
- 用户于 2026-08-09 明确：GPT 不参与本轮审查/签字，只在用户需要理解方案时担任讲解者；
- 用户已授权 Codex 生成 FROZEN、实施代码、测试与构建 HPC bundle；
- **HPC 提交仍需用户单独明确授权**。本 FROZEN 不等于提交许可；
- 任一后续协议变更必须另起 amendment，经 Kimi 独立审查与用户冻结，不得静默修改本文。

## 16. 冻结声明

本文从其 Git commit 与同名 SHA-256 侧车共同落库时起生效。实现只能机械执行本文，
不得依据 VIEWED 结果新增统计量、选择 cut、改变 interaction key、删减 OOD 池或放宽
FINAL 隔离。Oracle 可行只授权另起 D1-Legal；Oracle 全失败才对当前 endpoint-pair
conflict-persistence 路线作封口裁决。
