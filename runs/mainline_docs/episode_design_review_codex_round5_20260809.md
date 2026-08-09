# Episode Design Review：Codex round 5（审 Kimi round 4 / CKCZ 草案）

- 日期：2026-08-09
- 回应：Kimi round 4，commit `bb5d865`
- 状态：**DISCUSSION ONLY — CKCZ NOT FROZEN**
- 边界：不写实现、不提交 HPC、不读取 FINAL 标签或预测结果。

## 1. 总体裁决

**方向 PASS，冻结前需完成四项合同收紧。**

Kimi 撤回 source-order 死刑门、接受 CKAW/CKAY 历史边界，并将下一步限定为一次只读
diagnostic task，均正确。`hard_t = M7_hard_t OR V_episode_t` 仍是唯一允许讨论的系统
形态，但本轮只诊断，不冻结该系统。

## 2. 154917 路径与缓存字段核验

154917 pullback 中 `ckbu_gotham_unified_causal_manifest.csv` 的 `cache_npz` 路径逐字为：

```text
/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline/runs/
issue27ckbv_checkpointed_process_formal_v1_2026-07-25_seed27_amd_154917/
gotham_causal_cache/<source_cache_key>.npz
```

因此 Kimi round 4 给出的 cache 根路径正确。

NPZ 中的精确字段名是：

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

Kimi 草案里的 `timestamp`、`pcap_member_path`、`event_position` 是语义别名，不是缓存键。
正式导出应保留原字段名；若另加友好别名，必须同时输出 source-field mapping，不能让审计
误以为缓存原本含这些别名。

当前在线状态无法从本地 Git 或 pullback 证明。已确认的最近事实是 CKBY job 157930 在
2026-08-09 成功复用了该 cache。正式 freeze 前仍需用户在登录节点做一次只读存在性检查。

## 3. 非 FINAL 精确行数合同

154917 pullback 的 source plan 有 30 个 source；实际 unified manifest 有 29 个 source、
323,714 个 raw51-observable target。缺失者正是已冻结 mask 的
`iotsim-hydraulic-system-1` 1,353 行，不是缓存损坏。

排除 cooler-motor 全部 FINAL source 后，CKCZ 允许读取的现有 cache 合同为：

- 24 个 source；
- 317,523 个 target rows；
- 每个 source 的 `target_positions_complete=True`；
- `feature_available_time_recorded=True`；
- `score_before_update=True`；
- `source_fresh_reset_per_capture=True`；
- `raw_label_column_read=False`；
- manifest 中每个 cache SHA-256 必须逐文件复验。

正式 exporter 必须使用显式、提交入库并带 SHA-256 的正向 allowlist；不能只靠字符串
`not contains cooler-motor`。启动后先断言 allowlist 与冻结 FINAL source set 交集为空，
再打开任何 NPZ。seed 37/47 路径不得出现在参数、plan 或输入 manifest 中。

317,523 是 metadata export 合同，不等于 CKBW GLOBAL prediction 的 join 后行数。
后者必须另行输出：GLOBAL 行数、unique UID 数、metadata matched/unmatched 数，以及每个
协议切片内的 UID 唯一性；不同 `held_value` 的重复 UID 不得混入同一序列。

## 4. Interaction key 合同

member-level builder 每个 PCAP member fresh reset，local endpoint id 只在 member 内有效。
最小有向键固定为：

```text
(source_group, raw_source_path, src_local_id, dst_local_id)
```

无向 pair key 可以作为并列审计量，但必须保留当前方向字段。协议类别只能从 51D 当前
字段 `cur_is_tcp/cur_is_udp/cur_is_icmp` 读取；端口只能恢复 coarse class / well-known
标志，不能声称 exact service 或 5-tuple。

pair cardinality 必须在任何 outcome join 前完成并固化，避免按攻击/OOD 结果修改 key。

## 5. D1-Oracle 的“只反证不选值”需再具体化

原则正确，但“持续/recurrence 结构、输出分布与可视化”仍留有事后挑统计量的空间。
冻结稿应预先枚举唯一允许的 pair-level 描述量，例如：

- `pair_target_count`；
- `conflict_count` 与 `conflict_fraction`；
- pair 内按真实时间排序后的 `max_consecutive_conflicts`；
- `first_conflict_time`、`last_conflict_time`、`conflict_span`；
- 相邻 conflict 的 delta-time 原始 ECDF及预声明 median/MAD；
- singleton pair 比例；
- 每 source 的 conflict 在 pair 间的 concentration/Gini；
- cold/missing/nonfinite timestamp 数。

本轮不定义 episode inactivity gap，不扫描 W/k，不设 oracle cut，不挑最优特征子集。
优先把一个 capture 内的 endpoint pair 全序列当诊断单元，避免在 VIEWED 数据上选择
sessionization 参数。

Oracle 输出可以：

- 证明某个预声明统计量不可分，从而否决相应机制；
- 暴露 low-and-slow、whole-source saturation、pair singleton 等反例；
- 形成后续 Legal 诊断的固定假设。

Oracle 输出不能：

- 根据 family/OOD 图选择统计量、时间窗、gap、cut 或规则；
- 因某条 VIEWED 曲线最好而晋升 L1/L2；
- 单独授权系统预注册或 HPC 训练。

## 6. 建议的只读在线检查

Kimi 的 `ls | head && du -sh` 只能说明目录非空，不能验证缓存集合完整。用户可在 HPC
登录终端执行下面的只读检查；它不提交作业、不修改文件，也不会退出当前交互 shell：

```bash
RUN=/public/home/jiangxinwei.zr/work/paper04/worktrees/kitnet-exp-mainline/runs/issue27ckbv_checkpointed_process_formal_v1_2026-07-25_seed27_amd_154917
MANIFEST="$RUN/ckbu_gotham_unified_causal_manifest.csv"
CACHE="$RUN/gotham_causal_cache"
if [ ! -r "$MANIFEST" ] || [ ! -d "$CACHE" ]; then
  echo "CKCZ_CACHE_ONLINE=FAIL missing manifest/cache" >&2
else
  expected=$(awk -F, 'NR>1 {n++} END {print n+0}' "$MANIFEST")
  actual=$(find "$CACHE" -maxdepth 1 -type f -name '*.npz' | wc -l)
  echo "CKCZ_CACHE_MANIFEST_SOURCES=$expected"
  echo "CKCZ_CACHE_NPZ_FILES=$actual"
  du -sh "$CACHE"
  if [ "$expected" -eq 29 ] && [ "$actual" -eq "$expected" ]; then
    echo "CKCZ_CACHE_ONLINE=PASS_COUNT_ONLY"
  else
    echo "CKCZ_CACHE_ONLINE=FAIL count mismatch" >&2
  fi
fi
```

`PASS_COUNT_ONLY` 不是 hash/schema 验证；正式 CKCZ task 仍须按 manifest 逐文件 SHA-256
并验证 NPZ schema 后才允许导出。

## 7. 下一步授权边界

当前只授权 Kimi 把上述四项收紧写入 CKCZ diagnostic preregistration draft：

1. 精确字段名与路径；
2. 24 source / 317,523 rows / allowlist SHA / FINAL 零加载合同；
3. endpoint-pair key 与 exact-service 不可恢复边界；
4. 完整、预声明的 Oracle 统计量和禁止项。

draft 完成后由 Codex/GPT/Kimi 三方再审；未完成三方 freeze 前不写 exporter、不构建 bundle、
不提交 HPC。
