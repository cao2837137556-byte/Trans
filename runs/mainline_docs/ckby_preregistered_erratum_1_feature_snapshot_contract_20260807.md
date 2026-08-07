# CKBY 预注册勘误 1：特征快照合同修正（执行前勘误）

- 日期：2026-08-07
- 对象：`ckby_drocc_record_capacity_baseline_preregistered_20260807.md`
  （FROZEN，SHA-256 `bbb113eaef19325099c997e8af8c8ff1a623ea60a01933fff7dcc3271a8a69f0`）§9。
- 性质：**执行前勘误**。发现于导出脚本编写前的接口核验，尚未训练、尚未导出、
  尚未评估任何数据。本勘误只修正快照覆盖范围的技术描述，不改变任何科学内容
  （假设、数据角色、超参数、工作点、双重门、路由全部不变）。

## 1. 原条款的事实错误

FROZEN §9 写道："快照行数必须等于 `ckbw_record_predictions.csv.gz` 行数
（297,326），并按 uid 逐一 join 角色标签；join 失败行数必须为 0"。

执行前核验发现该假设不成立：

1. `ckbw_record_predictions.csv.gz`（297,326 行，5 个 held_value 切片：
   GLOBAL 251,050 + 4 个 held 协议各 10,069/16,069）**只含 select 与 report
   阶段的行，不含任何 fit 行**（phase ∈ {select: 35,345, report: 261,981}）。
2. DROCC 训练需要 14,013 benign fit 行，这些行根本不在该表内。
3. 同一 uid 在 5 个 held_value 切片中重复出现（如 select 行每协议一份），
   唯一 uid 数少于 297,326。

因此"快照行数 = 297,326"既不可能也不正确；若按原条款执行，实验必然中止。

## 2. 修正后的快照合同（替换 §9 第二条）

- 快照覆盖 = 以下两者的**按 uid 去重并集**：
  (a) CKBW GLOBAL 装配的 `fit_records` 全部 18,398 行
      （14,013 benign + 4,385 attack；attack 行仅供合同完整性断言，
      DROCC 训练按 label 过滤后绝不接触）；
  (b) `ckbw_record_predictions.csv.gz` 全部 5 个 held_value 切片中出现的
      所有唯一 uid。
- 装配方式与 CKBW formal 逐行一致：复用 `assemble_protocol` 对全部 5 个
  协议装配，`assert_global_pool_contract` 与 `assert_protocol_identity`
  原样执行，特征经 `UnifiedFeatureStore.add` + `ton_records` 取得，
  **导出的为原始 51D 因果特征（quantile 变换前）**；DROCC 的标准化按
  FROZEN §2.1 在本地只从 14,013 benign fit 行计算。
- 快照每行携带元数据：uid、role、m1_phase、source、device_family、
  attack_family、label、recorded_index、raw51_observable、global_pool
  （fit / select_attack / select_benign / report-only）。
- 硬性断言（任一失败即中止，不得绕过）：
  1. 记录表全部唯一 uid 在快照中恰好出现一次（覆盖率 100%）；
  2. GLOBAL fit 行数 18,398、其中 benign 14,013、attack 4,385；
  3. GLOBAL select_benign_observable 7,000（aux 3,000 + ToN 4,000）、
     select_attack 69；
  4. 特征矩阵无 NaN/Inf，形状 (N, 51)。
- 快照 SHA-256 写入 run_spec 与结果文档；本地训练只读该快照。
- §9 其余条款（不改管线、只读复用、HPC 失败时的备用路径）不变。

## 3. 附带澄清（不改变评估口径）

- raw51 masked 行（hydraulic-system-1 的 1,353 个 target）属于 report 池，
  其 51D 特征存在于统一缓存中（CKBW job 157624 全局 `store.add` 成功即为
  证据）。CKBW 对这些行 fail-closed 到 FrozenCKBQ 是 CKBW 的机制；
  CKBY 作为纯容量基线将对所有 report 行直接打分，并在结果文档中
  单独列出 masked 子集口径以便与 CKBW 同分母对照。
- support_val 69 行在快照中标记为 select_attack，仅作安全指标报告，
  不参与训练/阈值/checkpoint（FROZEN §2.2 不变）。

## 4. 授权

本勘误由 Kimi 起草，依据用户 2026-08-07 15:37 治理指令（Codex 终审非阻塞）
生效；GPT 评审与 Codex 回归后审查通过 commit 记录进行。如有异议，
走新预注册，不回改本勘误或 FROZEN 原文。
